# 파이프라인 복원력 + 데이터 흐름 설계

## 배경

qa-patrol deep 검증과 3/28~3/30 데이터 품질 분석에서 5개 문제를 발견했다.

### 발견 경위

- 3/25~3/27: compound-review-mingming LLM timeout 3일 연속 → 워커 4명 compound-review 미실행 (batch SPOF)
- 3/28: compound-review 빈 summary로 completed, failure_reason NULL
- 3/29: pipeline-gate 날짜 경계 버그로 daily-digest → compound-review 연쇄 실패 (이미 수정)
- 3/30: 수동 파이프라인 검증에서 전체 흐름 정상 동작 확인 + 데이터 품질 분석 수행

### 이미 수정된 것

| 수정 | 커밋 | 효과 |
|------|------|------|
| night throttle UTC→KST | `0ec6ed2f` | 새벽 시간대 오판 해소 |
| batch 크론 pipeline gate 스킵 | `0ec6ed2f` | batch 크론 gate 차단 해소 |
| pipeline gate 날짜 경계 + no-recipients | `aded86d7` | 직전 run 상태 확인 + skip 성공 처리 |
| --date 옵션 | `aded86d7` | 과거 날짜 재실행 지원 |
| --force duplicate guard 우회 | `cc086dc3` | 강제 재실행 지원 |
| compound-review 크론 이중 이름 정리 | DB 직접 수정 | bob-bob → batch 1개로 통일 |

### 남은 문제

이 스펙은 아직 수정되지 않은 5개 문제를 다룬다.

---

## Part 1: 인프라 수정 (dy-minions-squad 코드)

### 1-1. Batch 크론 SPOF 해소

**문제:** batch 크론(compound-review, meditation, journal-sweep 등)은 오케스트레이터 명의(`{name}-mingming`)로 1개만 등록되고, 실행 시 `minions cron dispatch --target {name}`으로 전 에이전트에 배포한다. 오케스트레이터의 크론 실행이 실패하면(LLM timeout, circuit breaker 등) dispatch 자체가 안 되어 **전 에이전트가 미실행**.

3/25~3/27에 실제 발생: compound-review-mingming LLM timeout 3일 연속 → bob/carl/phil/stuart 미실행 4일.

**해결 방향:** batch 크론 실행은 두 단계다:
1. 크론 트리거 → `minions cron exec compound-review-mingming` 실행
2. exec 내부에서 `minions cron dispatch --target compound-review` 호출 → 전 에이전트 큐 push

1단계가 LLM 호출이 아니라 CLI 명령 실행이므로 LLM timeout과 무관해야 한다. 하지만 현재 batch 크론의 `execution_type = "batch"`이고 `command = "minions cron dispatch --target compound-review"` — 이건 CLI 직접 실행이라 LLM 없이 돌아야 한다.

**근본 원인 추적 필요:** compound-review-mingming이 왜 LLM timeout으로 실패했는지. batch 크론이 CLI 직접 실행인데 LLM timeout이 나왔다면:
- `execution_type`이 실제로는 `batch`가 아니었거나 (queued로 잘못 등록 — 이미 발견 및 수정)
- 또는 크론 실행 경로가 batch인데도 LLM을 호출하는 코드 경로가 있거나

**수정:**
- watchdog이 batch 크론 dispatch 실패를 감지하면 자동 retry하는 로직 추가
- 또는 batch dispatch를 command-type으로 실행해서 LLM 의존성 제거 (현재 구조 확인 필요)

### 1-2. failure_reason NULL 방지

**문제:** compound-review-mingming 3/25~3/27 실패 시 `failure_reason`과 `error_log`가 모두 NULL. 에러 메시지가 `summary` 필드에만 기록됨 ("Error: All models failed..."). qa-patrol이 원인 판정할 때 failure_reason을 읽는데, NULL이면 판정 불가.

**원인:** `failCronRun` 호출 시 failure_reason이 전달되지 않는 코드 경로가 있거나, 에이전트 세션이 비정상 종료되면서 summary에만 기록되는 경우.

**수정:**
- `failCronRun`의 모든 호출부에서 failure_reason 필수 전달
- 에이전트 세션 crash 시 spawn-wrapper가 exit code + stderr를 failure_reason으로 기록
- summary에 "Error:" 패턴이 있는데 failure_reason이 NULL인 cron_runs를 watchdog이 감지하여 failure_reason 자동 보정

### 구현 위치

| 파일 | 변경 |
|------|------|
| `src/core/workspace/cron-runs.ts` | `failCronRun` failure_reason 필수화 |
| `src/core/workspace/watchdog-checks.ts` | batch dispatch 실패 감지 + failure_reason NULL 보정 |
| `src/cli/cron.ts` | batch 크론 dispatch 실패 시 retry 로직 |

---

## Part 2: 파이프라인 데이터 흐름 (dy-minions-squad 스킬 문서)

### 2-1. Self-improvement deliverable 파일 생성

**문제:** self-improvement-daily의 산출물이 `cron_runs.summary`에만 기록되고 deliverable 파일이 없다. 다른 단계(meditation 등)가 SI 결과를 참조하려면 structured output이 필요하다.

**현재 SI가 소비하는 데이터:**
- evaluations (tasks 테이블)
- daily-digest (`minions digest list --limit 7`)
- 각 에이전트 learnings/rules.json, MEMORY.md, BELIEFS.md
- meditation breakthrough (`minions meditate list`)

**SI가 생산해야 하는 deliverable:**
```json
{
  "date": "2026-03-30",
  "reject_patterns": [...],
  "success_patterns": [...],
  "proposals": [
    { "id": "P001", "type": "beliefs", "content": "...", "status": "pending" }
  ],
  "rules_applied": [...],
  "rules_effectiveness": [...],
  "agent_signals": [
    { "agent": "stuart", "signal": "meditation-stagnation", "days": 27 }
  ],
  "stages_completed": [1,2,3,4,5,6,7,8]
}
```

**수정:**
- `self-improvement/SKILL.md` 실행 절차에 "deliverable 파일 저장" 단계 추가
- 저장 경로: `brain/library/reviews/self-improvement/daily-{date}.json` (현재 경로와 동일, 실제로 파일을 쓰도록 instructions 보강)
- `references/pattern-detection.md`에 output schema 명시

### 2-2. 승인 병목 해소

**문제:** Phase 1 제안(P001 등)이 사람 승인을 기다리며 적체. 3/28 P001 제안 → 3/30 "2번째 관측" 재제안. 피드백 루프가 닫히지 않음.

**현재 승인 경로:**
- SI가 제안 → thread mention으로 밍밍이에게 보고 → 사람이 "P001 승인" 응답 → SI가 rules.json에 추가

**문제점:**
- 사람이 매일 thread를 확인하고 승인 응답을 해야 함
- 승인 안 하면 SI가 같은 제안을 반복

**해결 방향:**
- **자동 승인 조건 추가** (Phase 1.5): 같은 제안이 3회 이상 반복 관측되면 자동 승인
- 또는 **배치 승인**: 밍밍이가 주간 리뷰(weekly-review)에서 미승인 제안을 일괄 리뷰하도록 team-lead 스킬에 추가
- `rule-lifecycle.md`에 자동 승인 조건 명시

### 2-3. Meditation ↔ SI 연결

**문제:** SI가 감지한 에이전트 시그널(stuart meditation 27일+ 정체)을 meditation이 소비하지 않음. meditation은 MEDITATION.md만 읽고 자기 성찰을 함.

**해결:**
- SI deliverable (2-1에서 생성)의 `agent_signals`를 meditation instructions에 주입
- compound-review가 meditate 시 해당 에이전트의 SI 시그널을 참조하도록 `references/compound.md` 보강
- 또는 meditation cron instructions에 "SI 시그널 확인" 단계 추가: `brain/library/reviews/self-improvement/daily-{yesterday}.json`의 agent_signals 섹션을 읽고, 자기 에이전트에 해당하는 시그널이 있으면 명상 주제에 반영

### 구현 위치

| 파일 | 변경 |
|------|------|
| `core-skills/self-improvement/SKILL.md` | deliverable 저장 단계 추가 |
| `core-skills/self-improvement/references/pattern-detection.md` | output schema 명시 |
| `core-skills/self-improvement/references/rule-lifecycle.md` | 자동 승인 조건 (Phase 1.5) 또는 배치 승인 경로 |
| `core-skills/memory/SKILL.md` | meditation 절차에 SI 시그널 참조 추가 |
| `core-skills/memory/references/compound.md` | SI deliverable 참조 단계 추가 |
| `core-skills/team-lead/references/suggestion-review.md` 또는 weekly-review | 미승인 제안 배치 리뷰 |

---

## 우선순위

| 순서 | 항목 | 근거 |
|------|------|------|
| 1 | 2-1 SI deliverable | 다른 항목의 전제 조건. 파일이 있어야 다른 단계가 읽을 수 있다 |
| 2 | 2-3 meditation ↔ SI | deliverable이 있으면 바로 연결 가능 |
| 3 | 2-2 승인 병목 | 프로세스 변경이라 코드 수정 없이 스킬 문서만으로 가능 |
| 4 | 1-2 failure_reason NULL | 기록 표준화. 당장 기능 영향은 없지만 qa-patrol 원인 판정에 필요 |
| 5 | 1-1 batch SPOF | night throttle 수정으로 직접 원인은 해소. 구조적 개선이지만 우선순위 낮음 |

---

## 제외 사항

- pipeline-gate 날짜 경계, no-recipients, --date, --force: 이미 수정 완료
- compound-review 크론 이중 이름: 이미 DB 정리 완료
- night throttle UTC 버그: 이미 수정 완료
- daily-digest `tasks_blocked` 항상 0: 별도 이슈 (이 스펙 범위 밖)
