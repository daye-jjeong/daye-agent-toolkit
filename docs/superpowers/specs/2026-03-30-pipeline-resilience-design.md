# 파이프라인 복원력 + 데이터 흐름 설계

## 배경

qa-patrol deep 검증과 3/28~3/30 데이터 품질 분석에서 6개 문제를 발견했다.

### 발견 경위

- 3/25~3/27: compound-review-mingming LLM timeout 3일 연속 → 워커 4명 compound-review 미실행 (batch SPOF). 원인: night throttle UTC 버그로 잘못된 시간에 실행 + execution_type queued 오등록.
- 3/28: compound-review 빈 summary로 completed, failure_reason NULL
- 3/29: pipeline-gate 날짜 경계 버그로 daily-digest → compound-review 연쇄 실패 (이미 수정)
- 3/30: 수동 파이프라인 검증에서 전체 흐름 정상 동작 확인 + 데이터 품질 분석 수행
- 데이터 품질 등급: Digest A-, Compound-review B-, Self-improvement C+, Meditation B+, Cross-stage flow D+

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

이 스펙은 아직 수정되지 않은 6개 문제를 다룬다.

---

## Part 1: 인프라 수정 (dy-minions-squad 코드)

### 1-1. Batch 크론 SPOF 해소 + 멱등 retry

**문제:** batch 크론(compound-review, meditation, journal-sweep 등)은 오케스트레이터 명의(`{name}-mingming`)로 1개만 등록되고, 실행 시 `minions cron dispatch --target {name}`으로 전 에이전트에 배포한다. 오케스트레이터의 크론 실행이 실패하면 dispatch 자체가 안 되어 **전 에이전트가 미실행**.

3/25~3/27에 실제 발생: compound-review-mingming이 queued로 잘못 등록되어 LLM 세션으로 실행 → LLM timeout → bob/carl/phil/stuart 미실행 4일.

**근본 원인:** execution_type이 queued로 오등록된 것이 직접 원인이고, 이건 이미 수정됐다. batch 크론은 CLI 직접 실행이라 정상적으로는 LLM timeout이 발생하지 않는다.

**남은 위험:** batch dispatch가 부분 성공할 수 있다 (5명 중 3명만 큐 push 성공). retry 시 이미 enqueue된 에이전트에 중복 실행이 발생할 수 있다.

**수정:**
- watchdog이 batch 크론 dispatch 실패를 감지하면 멱등(idempotent) retry: 이미 enqueue된 에이전트는 스킵하고 누락된 에이전트만 push
- `dispatchBatchCron`에 이미 queued/running인 에이전트 dedup 로직 확인 (기존 `createQueueJob`에 dedup이 있으면 충분)
- cron_runs에 dispatch 결과(성공/실패 에이전트 목록) 기록

### 1-2. failure 메타데이터 구조화

**문제:** compound-review-mingming 3/25~3/27 실패 시 `failure_reason`과 `error_log`가 모두 NULL. 에러 메시지가 `summary` 필드에만 기록됨 ("Error: All models failed..."). qa-patrol이 원인 판정할 때 failure_reason을 읽는데, NULL이면 판정 불가.

**원인:** 에이전트 세션이 비정상 종료되면서 spawn-wrapper가 summary에만 기록하고 failure_reason을 안 채운 것.

**수정:**
- `failCronRun`의 모든 호출부에서 failure_reason 필수 전달
- 에이전트 세션 crash 시 spawn-wrapper가 exit code + stderr를 failure_reason으로 기록
- summary에서 failure_reason을 역추론하지 않음 (Codex 리뷰 지적: 관측값과 진단값 혼합 위험)
- 대신 qa-patrol checks.md의 원인 판정 순서 7단계에서 failure_reason NULL인 경우를 "Unknown" (순서 7)으로 처리하고 P 레벨 상향 — 이미 구현됨

### 1-3. 빈 입력 전파 방지 (false positive completed)

**문제:** 앞 단계가 실패했는데 뒷 단계가 빈 입력으로 "정상 완료"하는 케이스. 예: journal-sweep 실패 → compound-review가 빈 일지로 "승격 0건, 정상" 보고 → cron_runs에 completed로 기록.

딥 패트롤이 이걸 P1 설계 결함으로 감지하지만, 감지만 하고 방지는 안 한다.

**수정:**
- compound-review/self-improvement SKILL.md에 "입력 부재 감지" 단계 추가
- 입력 부재 시 `completed` 대신 `skipped` (skip_reason: "upstream data unavailable") 처리
- 구체적으로: compound-review가 전날 일지(`workspace-*/memory/YYYY-MM-DD.md`)가 없으면 skip. self-improvement가 직전 compound-review가 skip/failed이면 skip.

### 구현 위치

| 파일 | 변경 |
|------|------|
| `src/core/workspace/cron-runs.ts` | `failCronRun` failure_reason 필수화 |
| `src/core/workspace/watchdog-checks.ts` | batch dispatch 실패 감지 + 멱등 retry |
| `src/cli/cron.ts` | batch dispatch 결과 기록 |
| `core-skills/memory/references/compound.md` | 입력 부재 감지 → skip 처리 규칙 |
| `core-skills/self-improvement/SKILL.md` | upstream skip/failed 감지 → skip 처리 |

---

## Part 2: 파이프라인 데이터 흐름 (dy-minions-squad 스킬 문서)

### 2-1. Self-improvement deliverable 출력 계약

**문제:** self-improvement-daily의 산출물이 `cron_runs.summary`에만 기록되고 deliverable 파일이 없다. 다른 단계(meditation, qa-patrol deep)가 SI 결과를 참조하려면 structured output이 필요하다.

**현재 SI가 소비하는 데이터:**
- evaluations (tasks 테이블)
- daily-digest (`minions digest list --limit 7`)
- 각 에이전트 learnings/rules.json, MEMORY.md, BELIEFS.md
- meditation breakthrough (`minions meditate list`)

**SI 출력 계약 (deliverable schema):**
```json
{
  "date": "2026-03-30",
  "reject_patterns": [
    { "worker": "stuart", "category": "output-accuracy", "count": 2, "description": "..." }
  ],
  "success_patterns": [
    { "worker": "phil", "category": "output-quality", "pattern": "독립 크로스체크", "count": 3 }
  ],
  "proposals": [
    { "id": "SI-20260330-001", "type": "beliefs|rules", "target_agent": "all|{agent}", "content": "...", "observation_count": 2, "first_seen": "2026-03-28", "status": "pending" }
  ],
  "rules_applied": [
    { "rule_id": "R001", "agent": "phil", "category": "process", "applied_at": "2026-03-25" }
  ],
  "rules_effectiveness": [
    { "rule_id": "R001", "category": "process", "rejects_before": 3, "rejects_after": 0, "verdict": "effective" }
  ],
  "agent_signals": [
    { "agent": "stuart", "signal": "meditation-stagnation", "days": 27, "recommendation": "방향 전환 또는 breakthrough 선언" }
  ],
  "stages_completed": [1,2,3,4,5,6,7,8]
}
```

**proposal ID 규약:** `SI-{YYYYMMDD}-{NNN}` 형식으로 글로벌 유일. 날짜별 P001 재사용 금지. 같은 내용의 제안이 반복 관측되면 `observation_count` 증가 + `first_seen` 유지.

**수정:**
- `self-improvement/SKILL.md` 실행 절차에 "deliverable 파일 저장" 단계 추가
- 저장 경로: `brain/library/reviews/self-improvement/daily-{date}.json`
- `cron_runs.result_data`에도 동일 JSON 저장 (64KB 제한 내)
- `references/pattern-detection.md`에 output schema 명시
- qa-patrol deep-checks.md가 참조하는 경로/키와 일치 확인

### 2-2. 승인 병목 해소 — 주간 배치 리뷰

**문제:** Phase 1 제안이 사람 승인을 기다리며 적체. 피드백 루프가 닫히지 않음.

**해결 — 주간 배치 리뷰만 (자동 승인은 제외):**
- 밍밍이가 주간 리뷰(weekly-review)에서 미승인 제안을 일괄 리뷰
- `team-lead` 스킬의 주간 리뷰 절차에 "SI 미승인 제안 리뷰" 단계 추가
- 밍밍이가 각 제안을 승인/거부/수정하고, 결과를 SI가 다음 daily에서 소비

자동 승인(Phase 1.5)은 proposal ID fingerprint, observation_count 추적 등 스키마 변경이 필요하므로 이번 범위에서 제외. 2-1의 proposal ID 규약이 정착된 후 별도 스펙으로 진행.

**수정:**
- `core-skills/team-lead/references/weekly-review.md` (또는 해당 reference)에 "SI 미승인 제안 리뷰" 섹션 추가
- SI deliverable의 `proposals[status=pending]`을 읽어서 리뷰 대상 목록 제시

### 2-3. Meditation ↔ SI 연결

**문제:** SI가 감지한 에이전트 시그널(stuart meditation 27일+ 정체)을 meditation이 소비하지 않음.

**날짜 기준 (Codex 리뷰 반영):** SI는 03:00, meditation은 04:00에 같은 날 실행된다. meditation이 `daily-{yesterday}`를 읽으면 방금 생성된 오늘 SI 산출물을 무시하게 된다. **meditation은 `daily-{today}`를 읽어야 한다** (같은 날 03:00에 생성된 파일).

**수정:**
- `core-skills/memory/SKILL.md` meditation 절차에 "SI 시그널 확인" 단계 추가
- 경로: `brain/library/reviews/self-improvement/daily-{today}.json`의 `agent_signals` 섹션
- 자기 에이전트에 해당하는 시그널이 있으면 명상 주제에 반영
- 시그널이 없으면 기존 절차 유지

### 구현 위치

| 파일 | 변경 |
|------|------|
| `core-skills/self-improvement/SKILL.md` | deliverable 저장 단계 + output schema 참조 |
| `core-skills/self-improvement/references/pattern-detection.md` | output schema 명시 |
| `core-skills/team-lead/references/weekly-review.md` | SI 미승인 제안 배치 리뷰 |
| `core-skills/memory/SKILL.md` | meditation 절차에 SI 시그널 참조 추가 |

---

## 우선순위

| 순서 | 항목 | 근거 |
|------|------|------|
| 1 | 2-1 SI deliverable 출력 계약 | 모든 항목의 전제 조건. 파일/스키마가 있어야 다른 단계가 읽을 수 있다 |
| 2 | 1-1 batch SPOF + 멱등 retry | 생산 장애 방지. dispatch 실패 시 전 에이전트 미실행 |
| 3 | 1-2 failure 메타데이터 | qa-patrol 원인 판정에 필요. 1-1 수정 시 같이 작업 가능 |
| 4 | 1-3 빈 입력 전파 방지 | false positive completed 제거. 스킬 문서 수정 |
| 5 | 2-3 meditation ↔ SI | 2-1 deliverable이 있으면 바로 연결 가능 |
| 6 | 2-2 승인 병목 (배치 리뷰) | 프로세스 변경. 주간 리뷰 reference 수정만으로 가능 |

---

## 제외 사항

- pipeline-gate 날짜 경계, no-recipients, --date, --force: 이미 수정 완료
- compound-review 크론 이중 이름: 이미 DB 정리 완료
- night throttle UTC 버그: 이미 수정 완료
- daily-digest `tasks_blocked` 항상 0: 별도 이슈 (이 스펙 범위 밖)
- Phase 1.5 자동 승인: proposal ID fingerprint 정착 후 별도 스펙
- result_data/session_id 완결성: Domain 6 스펙에서 다룸
