# QA Patrol Deep + 기본 패트롤 보강 설계

## 배경

dy-minions-squad의 qa-patrol은 시스템 건강(큐, 태스크, 크론, 데이터, 메타)을 하루 2회 점검한다. 그러나 두 가지 gap이 있다:

1. **기본 패트롤 품질**: 이상 감지 시 원인을 파악하지 않음. "6일 미실행", "ghost 에이전트" 등 현상만 보고하고 왜인지를 안 밝힘.
2. **자가개선 루프 검증 부재**: 시스템에 8개 자가개선 루프(self-improvement, compound-review, meditation 등)가 있지만, 이 루프들이 실제로 개선을 만들어내는지, 루프 설계 자체에 결함이 없는지 점검하는 메커니즘이 없음.

### 하네스 엔지니어링 관점

하네스의 3축 중 dy-minions-squad는 Context Engineering만 강하고, Architectural Constraints와 Garbage Collection이 약하다. 이 설계는 Garbage Collection(불일치를 주기적으로 찾아 정리)을 강화하는 것이 목적이다.

## 변경 범위

| 대상 | 변경 |
|------|------|
| `core-skills/qa-patrol/references/checks.md` | 영역 3, 4 보강 (원인 분류 필수화) |
| `core-skills/qa-patrol/cron.json` | `qa-patrol-deep` 크론 엔트리 추가 |
| `core-skills/qa-patrol/SKILL.md` | 딥 패트롤 모드 섹션 추가 |
| `core-skills/qa-patrol/references/deep-checks.md` | 신규: 딥 패트롤 검증 영역 상세 |

기존 기본 패트롤의 동작은 유지. 딥 패트롤은 별도 크론 엔트리로 추가.

---

## Part 1: 기본 패트롤 보강

### 원칙: 영역 3, 4의 P0-P2 발견에 원인 분류 필수

현상만 보고하는 것을 금지한다. 이상 감지 → 원인 파악이 한 세트다.

적용 범위: 영역 3(크론 실행), 영역 4(데이터 누적). 영역 1(큐), 2(태스크), 5(메타)는 기존 checks.md 유지.

### 영역 3 (크론 실행) 보강

크론 미실행/실패 감지 시, 아래 판정 순서에 따라 원인을 분류한다.

#### 원인 판정 순서

크론이 안 도는 이유가 여러 계층에 걸칠 수 있다. **위에서부터 순서대로 확인하고, 첫 번째로 일치하는 원인을 리포트에 포함한다.**

| 순서 | 계층 | 확인 소스 | 확인 내용 |
|------|------|-----------|-----------|
| 1 | **Registry** | `crons` 테이블 | `enabled=0` → disabled. 해당 cron name 없음 → 미등록. |
| 2 | **Agent** | `agent_state` 테이블, `skills.json` | `suspended_active=1` → suspended. 스킬 미활성화 → skill not enabled. |
| 3 | **Gate** | `cron_runs.skip_reason` | 값이 있으면 그대로 포함. gate subtype 분류 (아래 참조). |
| 4 | **Runtime** | `cron_runs.failure_reason` | 값이 있으면 그대로 포함. |
| 5 | **Retry** | `crons.retry_count`, `crons.next_retry_at` | `retry_count >= max_retries` → exhausted. `next_retry_at > now` → backoff 대기. |
| 6 | **Watchdog** | watchdog issue kind | `cron_run_missed` → 스케줄 시간에 fire 안 됨. |
| 7 | **Unknown** | 위 항목 모두 해당 없음 | "원인 미기록" → **P 레벨 1단계 상향** |

순서 1-2(Registry, Agent)는 `cron_runs` 행이 없어도 판정 가능하다. 순서 7(Unknown)은 모든 소스를 확인한 후에만 적용한다.

#### Gate subtype 분류

`cron_runs.skip_reason`의 gate를 의도적(intentional)과 장애(failure)로 구분한다. 심각도 판정에서 다르게 취급한다.

| Subtype | skip_reason 패턴 | 의미 | 심각도 영향 |
|---------|-----------------|------|------------|
| **intentional** | `night throttle` | 설계된 동작. 23:00-08:00 자동 스킵. | 단독으로는 이상 아님 (P3 이하) |
| **failure** | `pipeline-gate:`, `circuit breaker`, `agent suspended` | 장애 또는 앞 단계 실패로 인한 차단 | 3일+ 연속 = P1 |

#### 리포트 형식 변경

```
# Before (현재)
[P2] compound-review 6일 미실행

# After (보강)
[P2] compound-review 6일 미실행
- 원인: pipeline-gate: journal-sweep not completed for bob (gate/failure)
- 판정 경로: Registry OK → Agent OK → Gate hit (skip_reason)
- 최초 미실행: 2026-03-23
- 영향: compound-review 이후 단계(self-improvement, meditation)도 빈 입력 가능성
```

### 영역 4 (데이터 누적) 보강

ghost 에이전트 감지 시 출처를 명시한다.

#### 확인 순서

1. `config.json`의 에이전트 목록 조회
2. 다음 소스에서 config에 없는 에이전트 ID 탐색:
   - 큐 (`minions queue list --json`)
   - 크론 레지스트리 (`crons` 테이블)
   - agent-health (`agent_state` 테이블)
3. 발견 시 출처를 리포트에 명시

#### 리포트 형식 변경

```
# Before
[P3] hana 큐 4.4일 stale

# After
[P3] hana — config.json에 없는 에이전트
- 출처: 큐(job q-hana-xxx, 4.4일 stale) + 크론 레지스트리(3건 등록)
- AUTO-FIX 대상: orphan 크론 비활성화 (auto-fix.md #1)
- ASK 대상: 큐 stale job 정리 (밍밍이 판단)
```

---

## Part 2: 딥 패트롤 신설

### 개요

| 항목 | 값 |
|------|---|
| 크론 이름 | `qa-patrol-deep` |
| 스케줄 | `0 14 * * *` (매일 오후 2시 KST) |
| 에이전트 | phil |
| 기본 분석 범위 | 최근 7일 (항목별 lookback은 아래 참조) |

### 대상: 자가개선 파이프라인

#### 야간 파이프라인 (순서 의존적)

```
01:00  journal-sweep        → 세션 수거
01:30  activity-compile     → 활동 로그 합본
02:00  daily-digest         → 데일리 업무일지
02:30  compound-review      → 일지 → MEMORY.md/operations.md 승격
03:00  self-improvement     → 8단계 분석 → 규칙 제안
04:00  meditation           → 명상 → 돌파구 추적
```

#### 주요 자가개선 루프 4개

| 루프 | 사이클 | 개선 대상 |
|------|--------|-----------|
| **self-improvement-daily** | reject/approve 분석 → 패턴 분류 → 규칙 제안 → 승인 → 적용 → 효과 검증 | `learnings/rules.json`, `BELIEFS.md`, `TEAM.md` |
| **compound-review** | 일지 분석 → 고신호 항목 추출 → MEMORY.md/operations.md 승격 | `MEMORY.md`, `learnings/operations.md` |
| **meditation** | 주제 생성 → 5단계 숙성(define→explore→refine→verify→evaluate) → 돌파구 감지 | `MEDITATION.md`, `SOUL.md`(승인 필요) |
| **goal-lifecycle** | 월간→주간→일간 cascade → 아침 브리핑 → 저녁 체크 → 회고 | `personal_goals`, `personal_todos`, `retrospectives` |

#### 보조 피드백 루프

| 루프 | 역할 |
|------|------|
| **beliefs elevation** | 2+ 에이전트 동일 규칙 → BELIEFS.md 승격 |
| **suggestion-review** | 워커 제안 → 승인 → 태스크 생성 → 평가 → self-improvement 입력 |
| **memory-pruning** | 90일+ 메모리 → 관련성 분석 → 아카이브 |

### 검증 3차원

#### 차원 1: 완주 (파이프라인이 끝까지 도는가?)

| 검증 항목 | 확인 소스 | 방법 | lookback | 심각도 기준 |
|-----------|-----------|------|----------|------------|
| 야간 파이프라인 순서 완주 | `cron_runs` 테이블: cron_id IN (journal-sweep, activity-compile, daily-digest, compound-review, self-improvement-daily, meditation), status/skip_reason | 7일간 각 단계 완료 여부. failure gate skip 횟수 집계 (intentional gate 제외) | 7일 | failure gate 3일+ 연속 = P1 |
| 빈 입력 전파 (false positive) | `cron_runs`: 같은 날짜의 앞 단계 status=failed/skipped AND 뒷 단계 status=completed. `deliverables`: 뒷 단계 산출물 파일 크기 | journal-sweep 실패일에 compound-review "정상 완료"이면서 산출물 0건 또는 < 1KB | 7일 | 발견 시 P1 |
| goal-lifecycle 쌍 완료 | `cron_runs`: cron_id IN (goal-morning-brief, goal-evening-check, goal-weekly-plan, goal-weekly-retro). 같은 날짜/주에 쌍이 모두 completed인지 | morning-brief ↔ evening-check 쌍, weekly plan ↔ retro 쌍 | 7일 | 3일+ morning만 있고 evening 없음 = P2 |
| self-improvement 8단계 완주 | `deliverables`: self-improvement-daily 크론의 산출물(daily-*.json). `result_data` JSON에서 stages 배열 확인 | daily report에 8단계 모두 포함되었는지 | 7일 | 3일+ 불완전 = P2 |

#### 차원 2: 효과 (개선을 만드는가?)

| 검증 항목 | 확인 소스 | 방법 | lookback | 최소 표본 | 심각도 기준 |
|-----------|-----------|------|----------|-----------|------------|
| self-improvement 제안 승인률 | `deliverables`: self-improvement daily report의 proposals[]. `thread_messages`: 멘션에서 "승인"/"approve" 포함 응답. join key: proposal ID (P001 등) | 제안 N건 중 승인 M건 비율 | 14일 | 제안 5건+ | 승인률 50% 미만 = P2 |
| 규칙 적용 후 reject 감소 | `learnings/rules.json`: 규칙 적용일(added_at). `cron_runs` + `deliverables`: self-improvement analysis의 category별 reject 집계. join key: rule category | 규칙 적용 카테고리의 reject 빈도 before(4주)/after(2주) 비교 | 42일 (4+2주) | 적용 규칙 3건+ AND 해당 카테고리 reject 5건+ | 감소 없음 = P3 (INFO) |
| compound-review 승격 건수 | `workspace-{agent}/MEMORY.md`: git log로 최근 변경 횟수. `workspace-{agent}/learnings/operations.md`: 같은 방법. join key: agent_id + date | MEMORY.md/operations.md 변경(승격) 건수/주 | 14일 | — | 전 에이전트 0건/주 2주 연속 = P2 |
| meditation 돌파구 빈도 | `workspace-{agent}/meditation/`: 파일 내 breakthrough/★ 태그 존재 여부. `MEDITATION.md` Growth 섹션 변경 이력 | breakthrough 태그 건수 | 30일 | — | 0건/월 = P3 (INFO) |
| beliefs 검증 처리율 | `minions beliefs list --format json`: status=unverified 건수, created_at 기준 최고령 | unverified 누적 대비 처리 비율 | 30일 | unverified 5건+ | 30일+ unverified 10건+ = P2 |
| 승인 후 미적용 규칙 | `thread_messages`: "승인" 응답 있는 proposal ID. `learnings/rules.json`: 해당 ID로 추가된 규칙 존재 여부. join key: proposal ID | 승인됐지만 rules.json에 반영 안 된 건 | 14일 | — | 발견 시 P2 |

#### 차원 3: 설계 결함 (루프 자체가 잘못된 건 없는가?)

| 검증 항목 | 확인 소스 | 방법 | lookback | 심각도 기준 |
|-----------|-----------|------|----------|------------|
| 빈 입력 전파 | 차원 1의 "빈 입력 전파" 검증과 동일 소스 | 앞 단계 실패를 뒷 단계가 감지 못하고 빈 데이터로 "정상" 처리하는 패턴 | 7일 | 발견 시 P1 |
| 규칙 충돌 | `learnings/rules.json` (전 에이전트): 최근 추가 규칙의 category + rule text. `BELIEFS.md`: 기존 항목. join key: category | 신규 규칙이 기존 BELIEFS.md 또는 다른 에이전트 rules.json과 의미적 모순 | 14일 | — | 발견 시 P2 |
| 승인 병목 | `deliverables`: self-improvement daily report의 proposals[]. `thread_messages`: proposal ID에 대한 응답 유무. join key: proposal ID | Phase 1 제안이 미승인 상태로 적체 | 14일 | 미승인 5건+ | 7일+ 미승인 10건+ = P2 |
| 목표 드리프트 | `personal_goals` 테이블: status=active인 목표. `current_tasks` 테이블: 활성 태스크. join key: goal_id ↔ task의 goal_link (있는 경우) 또는 키워드 매칭 | 활성 목표에 연결된 태스크 0건 | 7일 | 활성 목표 3건+ | 발견 시 P2 |
| 루프 stagnation | 각 루프의 산출물 소스 (위 차원 2와 동일) | 동일 루프가 어떤 변경도 만들지 않음 (산출물 0건) | 30일 | — | P2 |
| suggestion-review 폐루프 | `proactive_suggestions` 테이블: status=approved. `current_tasks`: 해당 suggestion에서 생성된 태스크. `cron_runs`: 태스크 완료 후 self-improvement 입력 여부. join key: suggestion_id → task_id → evaluation | 승인된 제안 → 태스크 생성 → 완료 → 평가 → self-improvement 입력까지 도달한 비율 | 14일 | 승인 제안 3건+ | 완주율 0% = P2 |
| 중복 규칙 churn | `learnings/rules.json` (전 에이전트): 같은 category에 유사 rule text (문자열 유사도 > 80%). `BELIEFS.md`: 같은 내용의 중복 항목 | 실질적으로 같은 규칙이 반복 생성되는 패턴 | 30일 | — | 발견 시 P3 (INFO) |
| memory-pruning backlog | `workspace-{agent}/MEMORY.md`: 항목 수. `memory-pruning` cron_runs: 최근 실행 여부 | MEMORY.md 항목 300+ AND 최근 30일 pruning 미실행 | 30일 | — | 발견 시 P2 |

### 딥 패트롤 리포트 형식

```
## QA Patrol Deep — {날짜} {시간}

### 파이프라인 완주 (7일 요약)
| 단계 | 완주율 | gate skip (failure) | gate skip (intentional) | 비고 |
|------|--------|---------------------|------------------------|------|
| journal-sweep | 6/7 | 0 | 1 (night throttle) | |
| compound-review | 5/7 | 2 (pipeline-gate: journal-sweep) | 0 | 연쇄 실패 |
| self-improvement | 7/7 | 0 | 0 | 8단계 완주 확인 |
| meditation | 7/7 | 0 | 0 | |

### 루프 효과 (lookback별)
- self-improvement (14일): 제안 12건, 승인 9건 (75%) — Phase 2 기준 미달. 승인 후 미적용 0건.
- compound-review (14일): MEMORY.md 승격 3건, operations.md 승격 1건
- meditation (30일): 돌파구 0건 (4주 연속) [P3-INFO]
- beliefs (30일): unverified 8건 (최고령 15일)
- suggestion-review (14일): 승인 5건 → 태스크 생성 4건 → 완료 2건 → SI 입력 1건 (완주율 20%)

### 설계 결함
1. [P1] 빈 입력 전파: 3/25 journal-sweep 실패 → compound-review "정상 완료" (산출물 0건)
   - 확인: cron_runs(journal-sweep, 3/25, status=failed) + cron_runs(compound-review, 3/25, status=completed) + deliverable 크기 0KB
   - 판단: compound-review가 입력 부재를 감지하지 않음. 빈 입력 시 skip 처리 필요.
2. [P2] 승인 병목: Phase 1 미승인 제안 7건 (최고령 12일)
   - 확인: deliverables(self-improvement daily reports) proposals[] 중 thread_messages에 승인 응답 없는 건
   - 판단: 피드백 루프가 닫히지 않아 self-improvement 효과 측정 불가.

### 트렌드
- [RECURRING] compound-review 연쇄 실패 (journal-sweep 의존)
- [RESOLVED] meditation stagnation (3/20 돌파구 발생으로 해소)

### Check (다음 딥 패트롤)
- [ ] compound-review 빈 입력 감지 로직 추가 여부
- [ ] Phase 1 미승인 적체 해소 여부
```

### 크론 엔트리

```json
{
  "name": "qa-patrol-deep",
  "schedule": "0 14 * * *",
  "tz": "Asia/Seoul",
  "target": "qa-patrol-deep",
  "reason": "자가개선 루프 라이프사이클 검증",
  "instructions": "qa-patrol 스킬의 '딥 패트롤' 절차를 따르세요. references/deep-checks.md를 참조하세요. 항목별 lookback 기간을 준수하세요."
}
```

---

## 구현 위치

모든 변경은 `dy-minions-squad` 레포의 `core-skills/qa-patrol/` 에서 수행.

| 파일 | 변경 유형 |
|------|-----------|
| `SKILL.md` | 수정: 딥 패트롤 모드 섹션 추가, 크론 테이블에 qa-patrol-deep 추가 |
| `cron.json` | 수정: qa-patrol-deep 엔트리 추가 |
| `references/checks.md` | 수정: 영역 3 원인 판정 순서 + gate subtype 분류 추가, 영역 4 ghost 출처 명시 |
| `references/deep-checks.md` | 신규: 딥 패트롤 3차원 검증 상세 (확인 소스, join key, lookback 포함) |
| `references/auto-fix.md` | 변경 없음 |
| `references/trend.md` | 변경 없음 |

---

## 제외 사항

- 하네스 코드 강제 (hooks, PreToolUse 등): 이번 범위 밖. 리서치 완료 상태이며 별도 설계 필요.
- 크론 미실행 원인 분류 체계의 코드 레벨 검증 CLI: 기존 `minions` CLI와 SQLite 쿼리로 충분. 별도 도구 불필요.
- health.json manifest (접근법 C): 루프가 더 늘어나면 점진적 도입 검토.
- 영역 1(큐), 2(태스크), 5(메타)의 원인 분류: 이번 범위 밖. 영역 3, 4에서 효과 확인 후 점진 확대.
