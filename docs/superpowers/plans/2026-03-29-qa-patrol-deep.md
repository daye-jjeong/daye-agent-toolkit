# QA Patrol Deep 구현 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** qa-patrol의 기본 패트롤에 원인 분류를 추가하고, 자가개선 루프 라이프사이클을 검증하는 딥 패트롤을 신설한다.

**Architecture:** 기존 qa-patrol 스킬(SKILL.md + references/)에 딥 패트롤 모드를 추가. checks.md 영역 3, 4를 보강하고, deep-checks.md를 신규 생성. cron.json에 qa-patrol-deep 엔트리 추가. 모든 변경은 마크다운/JSON 문서.

**Tech Stack:** Markdown, JSON (dy-minions-squad/core-skills/qa-patrol/)

**Target repo:** `/Users/dayejeong/dy-minions-squad`

---

### Task 1: checks.md 영역 3 보강 — 원인 판정 순서 + gate subtype

**Files:**
- Modify: `core-skills/qa-patrol/references/checks.md:38-55`

- [ ] **Step 1: 영역 3 헤더 아래에 원인 판정 순서 섹션 추가**

`checks.md`의 `## 3. 크론 실행/메모리 사이클` 섹션을 아래로 교체한다. CLI 명령과 기존 테이블은 유지하되, 원인 판정 순서와 gate subtype 분류를 추가한다.

```markdown
## 3. 크론 실행/메모리 사이클

```bash
minions cron run list --format json
minions health status --format json
```

이 두 결과는 이후 auto-fix 단계(circuit breaker 판단 등)에서도 사용하므로 보존해둔다.

| 조건 | 심각도 | 근거에 포함할 것 |
|------|--------|----------------|
| 크론 running 2시간+ | P1 | cron_id, 에이전트, 시작 시각, 경과 시간 |
| 크론 completed인데 일지 크론(`compound-review`, `journal-sweep`, `meditation`)의 산출물 없음 | P2 | cron_id, 에이전트, 완료 시각 |
| 오늘 일지 없는 에이전트 | P2 | 에이전트 ID, 마지막 일지 날짜 |
| 최근 3일간 `meditation` 또는 `compound-review` 크론 미실행 에이전트 | P2 | 에이전트 ID, 크론명, 마지막 실행일 |

### 원인 판정 (P0-P2 필수)

크론 미실행/실패 감지 시, 아래 순서대로 확인하고 **첫 번째로 일치하는 원인**을 리포트에 포함한다.

| 순서 | 계층 | 확인 소스 | 확인 내용 |
|------|------|-----------|-----------|
| 1 | **Registry** | `crons` 테이블 | `enabled=0` → disabled. 해당 cron name 없음 → 미등록. |
| 2 | **Agent** | `agent_state` 테이블, `skills.json` | `suspended_active=1` → suspended. 스킬 미활성화 → skill not enabled. |
| 3 | **Gate** | `cron_runs.skip_reason` | 값이 있으면 그대로 포함. gate subtype 분류 (아래 참조). |
| 4 | **Runtime** | `cron_runs.failure_reason` | 값이 있으면 그대로 포함. |
| 5 | **Retry** | `crons.retry_count`, `crons.next_retry_at` | `retry_count >= max_retries` → exhausted. `next_retry_at > now` → backoff 대기. |
| 6 | **Watchdog** | watchdog issue kind | `cron_run_missed` → 스케줄 시간에 fire 안 됨. |
| 7 | **Unknown** | 위 항목 모두 해당 없음 | "원인 미기록" → **P 레벨 1단계 상향** |

순서 1-2(Registry, Agent)는 `cron_runs` 행이 없어도 판정 가능하다.

### Gate subtype 분류

`cron_runs.skip_reason`의 gate를 의도적(intentional)과 장애(failure)로 구분한다.

| Subtype | skip_reason 패턴 | 의미 | 심각도 영향 |
|---------|-----------------|------|------------|
| **intentional** | `night throttle` | 설계된 동작. 23:00-08:00 자동 스킵. | 단독으로는 이상 아님 (P3 이하) |
| **failure** | `pipeline-gate:`, `circuit breaker`, `agent suspended` | 장애 또는 앞 단계 실패로 인한 차단 | 3일+ 연속 = P1 |

### 리포트 형식

크론 미실행 보고 시 아래 형식을 따른다:

```
[P2] compound-review 6일 미실행
- 원인: pipeline-gate: journal-sweep not completed for bob (gate/failure)
- 판정 경로: Registry OK → Agent OK → Gate hit (skip_reason)
- 최초 미실행: 2026-03-23
- 영향: compound-review 이후 단계(self-improvement, meditation)도 빈 입력 가능성
```

**일지 확인:**
해당 에이전트의 workspace 경로에서 오늘 날짜 파일 존재 여부를 확인.
```

- [ ] **Step 2: 변경 확인**

Run: `head -80 core-skills/qa-patrol/references/checks.md`
Expected: 영역 3에 "원인 판정" 섹션과 "Gate subtype 분류" 섹션이 포함됨

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/references/checks.md
git commit -m "feat(qa-patrol): 영역 3 원인 판정 순서 + gate subtype 분류 추가"
```

---

### Task 2: checks.md 영역 4 보강 — ghost 에이전트 출처 명시

**Files:**
- Modify: `core-skills/qa-patrol/references/checks.md:57-69`

- [ ] **Step 1: 영역 4의 ghost 에이전트 항목 보강**

`## 4. 데이터 누적/오염` 섹션을 아래로 교체한다. 기존 CLI 명령과 테이블은 유지하되, ghost 에이전트 확인 절차와 리포트 형식을 추가한다.

```markdown
## 4. 데이터 누적/오염

```bash
minions mention list --status NEW --json
```

크론 레지스트리 확인은 영역 3의 `cron run list` 결과와 `minions health status` 결과에서 에이전트 목록을 대조한다.

| 조건 | 심각도 | 근거에 포함할 것 |
|------|--------|----------------|
| 미처리(NEW) 멘션 20개+ | P2 | 멘션 수, 가장 오래된 멘션 시각, 대상 에이전트 |
| config.json에 없는 ghost 에이전트 | P3 | 에이전트 ID, 출처 목록 (아래 절차 참조) |
| 레지스트리에 config에 없는 에이전트의 크론 | P3 | 크론명, 에이전트 ID |

### Ghost 에이전트 출처 확인

config.json에 없는 에이전트 ID가 감지되면, 아래 소스를 모두 확인하여 출처를 리포트에 명시한다.

1. 큐 (`minions queue list --json`): 해당 에이전트의 job 존재 여부, job ID, 경과 시간
2. 크론 레지스트리 (`crons` 테이블): 해당 에이전트의 등록 크론 수, 크론명
3. agent-health (`agent_state` 테이블): 해당 에이전트의 상태 레코드 존재 여부

### 리포트 형식

```
[P3] hana — config.json에 없는 에이전트
- 출처: 큐(job q-hana-xxx, 4.4일 stale) + 크론 레지스트리(3건 등록)
- AUTO-FIX 대상: orphan 크론 비활성화 (auto-fix.md #1)
- ASK 대상: 큐 stale job 정리 (밍밍이 판단)
```
```

- [ ] **Step 2: 변경 확인**

Run: `grep -A 20 "Ghost 에이전트 출처" core-skills/qa-patrol/references/checks.md`
Expected: "Ghost 에이전트 출처 확인" 섹션이 출력됨

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/references/checks.md
git commit -m "feat(qa-patrol): 영역 4 ghost 에이전트 출처 확인 절차 추가"
```

---

### Task 3: deep-checks.md 신규 생성 — 차원 1 (완주)

**Files:**
- Create: `core-skills/qa-patrol/references/deep-checks.md`

- [ ] **Step 1: deep-checks.md 생성 — 헤더 + 차원 1**

```markdown
# 딥 패트롤 검증 영역 상세

자가개선 루프의 라이프사이클을 3차원으로 검증한다. 기본 분석 범위는 7일이지만, 항목별 lookback이 다르다.

## 야간 파이프라인 (순서 의존적)

```
01:00  journal-sweep        → 세션 수거
01:30  activity-compile     → 활동 로그 합본
02:00  daily-digest         → 데일리 업무일지
02:30  compound-review      → 일지 → MEMORY.md/operations.md 승격
03:00  self-improvement     → 8단계 분석 → 규칙 제안
04:00  meditation           → 명상 → 돌파구 추적
```

---

## 차원 1: 완주 (파이프라인이 끝까지 도는가?)

### 1-1. 야간 파이프라인 순서 완주

**확인 소스:** `cron_runs` 테이블 — `cron_id IN ('journal-sweep-{agent}', 'activity-compile-{agent}', 'daily-digest', 'compound-review-{agent}', 'self-improvement-daily', 'meditation-{agent}')`, `status`, `skip_reason`
**Lookback:** 7일
**방법:** 7일간 각 단계의 완료 여부를 에이전트별로 집계. `skip_reason`의 gate subtype(checks.md 참조)을 분류하여, failure gate skip만 카운트.

```bash
# 야간 파이프라인 크론 실행 상태 조회 (최근 7일)
minions cron run list --format json
```

결과에서 야간 파이프라인 크론 ID를 필터하고, 날짜별 status를 확인.

| 조건 | 심각도 |
|------|--------|
| failure gate 3일+ 연속 skip (같은 단계, 같은 에이전트) | P1 |
| failure gate 1-2일 | P2 |
| intentional gate skip만 | 이상 아님 (리포트 정상 영역에 기록) |

### 1-2. 빈 입력 전파 (false positive)

**확인 소스:**
- `cron_runs`: 같은 날짜의 앞 단계 `status=failed` 또는 `skipped` AND 뒷 단계 `status=completed`
- `deliverables`: 뒷 단계 산출물 파일 크기 (deliverable의 `outputs` 필드 → 파일 경로 → 크기 확인)

**Lookback:** 7일
**방법:** 파이프라인 의존 관계를 따라 검사:
- journal-sweep 실패 → compound-review 정상 완료 + 산출물 < 1KB = false positive
- compound-review 실패 → self-improvement 정상 완료 + 산출물 없음 = false positive

| 조건 | 심각도 |
|------|--------|
| false positive 감지 | P1 |

### 1-3. goal-lifecycle 쌍 완료

**확인 소스:** `cron_runs` — `cron_id IN ('goal-morning-brief', 'goal-evening-check', 'goal-weekly-plan', 'goal-weekly-retro')`
**Lookback:** 7일
**방법:** 같은 날짜에 morning-brief와 evening-check가 모두 completed인지 확인. 주간은 같은 주에 plan과 retro 쌍 확인.

| 조건 | 심각도 |
|------|--------|
| 3일+ morning만 completed, evening 없음 | P2 |
| weekly plan 있는데 같은 주 retro 없음 | P2 |

### 1-4. self-improvement 8단계 완주

**확인 소스:** `deliverables` — self-improvement-daily 크론의 산출물. `cron_runs`에서 해당 run의 `outputs` 필드 → 파일 경로. 파일 내용에서 stages 배열 또는 "Stage 1" ~ "Stage 8" 존재 확인.
**Lookback:** 7일
**방법:** daily report 파일을 읽고 8단계 모두 포함되었는지 텍스트 검색.

| 조건 | 심각도 |
|------|--------|
| 3일+ 불완전 (8단계 미만) | P2 |
```

- [ ] **Step 2: 파일 생성 확인**

Run: `wc -l core-skills/qa-patrol/references/deep-checks.md`
Expected: 약 70-80줄

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/references/deep-checks.md
git commit -m "feat(qa-patrol): deep-checks.md 차원 1 (완주) 검증 추가"
```

---

### Task 4: deep-checks.md 차원 2 (효과) 추가

**Files:**
- Modify: `core-skills/qa-patrol/references/deep-checks.md` (append)

- [ ] **Step 1: 차원 2 섹션 추가**

deep-checks.md 끝에 아래 내용을 추가한다.

```markdown

---

## 차원 2: 효과 (개선을 만드는가?)

### 2-1. self-improvement 제안 승인률

**확인 소스:**
- `deliverables`: self-improvement daily report의 proposals 섹션. proposal ID (P001, P002 등) 추출.
- `thread_messages` 테이블: proposal ID를 포함하는 멘션 응답에서 "승인"/"approve" 존재 확인.
- **Join key:** proposal ID

**Lookback:** 14일
**최소 표본:** 제안 5건 이상일 때만 판정

| 조건 | 심각도 |
|------|--------|
| 승인률 50% 미만 (표본 5건+) | P2 |
| 표본 5건 미만 | 판정 보류 (P3 INFO로 표본 수 기록) |

### 2-2. 규칙 적용 후 reject 감소

**확인 소스:**
- `workspace-{agent}/learnings/rules.json`: 규칙 목록. `added_at` 필드로 적용일 확인, `category` 필드로 분류.
- `deliverables`: self-improvement analysis report의 reject 집계 (category별).
- **Join key:** rule category ↔ reject category

**Lookback:** 42일 (적용 전 4주 + 적용 후 2주)
**최소 표본:** 적용 규칙 3건+ AND 해당 카테고리 reject 5건+

| 조건 | 심각도 |
|------|--------|
| reject 감소 없음 (표본 충족) | P3 (INFO) |
| 표본 미달 | 판정 보류 |

### 2-3. compound-review 승격 건수

**확인 소스:**
- `workspace-{agent}/MEMORY.md`: git log로 최근 변경 횟수 (`git log --oneline --since="14 days ago" -- workspace-{agent}/MEMORY.md | wc -l`)
- `workspace-{agent}/learnings/operations.md`: 같은 방법.
- **Join key:** agent_id + date

**Lookback:** 14일

| 조건 | 심각도 |
|------|--------|
| 전 에이전트 0건/주 2주 연속 | P2 |

### 2-4. meditation 돌파구 빈도

**확인 소스:**
- `workspace-{agent}/meditation/`: 파일 내 `breakthrough` 또는 `★` 태그 존재 여부.
- `workspace-{agent}/MEDITATION.md` Growth 섹션: git log로 변경 이력 확인.

**Lookback:** 30일

| 조건 | 심각도 |
|------|--------|
| 전 에이전트 돌파구 0건/월 | P3 (INFO) |

### 2-5. beliefs 검증 처리율

**확인 소스:**
```bash
minions beliefs list --format json
```
- `status=unverified` 건수, `created_at` 기준 최고령 확인.

**Lookback:** 30일
**최소 표본:** unverified 5건+

| 조건 | 심각도 |
|------|--------|
| 30일+ unverified 10건+ | P2 |
| unverified 5건 미만 | 판정 보류 |

### 2-6. 승인 후 미적용 규칙

**확인 소스:**
- `thread_messages`: "승인"/"approve" 응답이 있는 proposal ID 추출.
- `workspace-{agent}/learnings/rules.json`: 해당 proposal ID로 추가된 규칙 존재 확인.
- **Join key:** proposal ID

**Lookback:** 14일

| 조건 | 심각도 |
|------|--------|
| 승인됐지만 rules.json에 미반영 | P2 |
```

- [ ] **Step 2: 변경 확인**

Run: `grep "^### 2-" core-skills/qa-patrol/references/deep-checks.md`
Expected: 2-1 ~ 2-6까지 6개 항목 출력

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/references/deep-checks.md
git commit -m "feat(qa-patrol): deep-checks.md 차원 2 (효과) 검증 추가"
```

---

### Task 5: deep-checks.md 차원 3 (설계 결함) 추가

**Files:**
- Modify: `core-skills/qa-patrol/references/deep-checks.md` (append)

- [ ] **Step 1: 차원 3 섹션 추가**

deep-checks.md 끝에 아래 내용을 추가한다.

```markdown

---

## 차원 3: 설계 결함 (루프 자체가 잘못된 건 없는가?)

### 3-1. 빈 입력 전파

차원 1-2의 "빈 입력 전파 (false positive)" 검증과 동일. 차원 1에서 발견된 false positive는 여기에도 기록하되, 설계 결함 관점의 판단을 추가한다.

| 조건 | 심각도 |
|------|--------|
| 앞 단계 실패를 뒷 단계가 감지 못하고 빈 데이터로 "정상" 처리 | P1 |

**판단 포함사항:** 뒷 단계가 빈 입력을 감지하는 로직이 있는지, skip 처리가 필요한지 제안.

### 3-2. 규칙 충돌

**확인 소스:**
- `workspace-{agent}/learnings/rules.json` (전 에이전트): 최근 추가 규칙의 `category` + `rule` 텍스트.
- `BELIEFS.md`: 기존 항목의 내용.
- **Join key:** category

**Lookback:** 14일
**방법:** 최근 추가된 규칙의 category가 BELIEFS.md 또는 다른 에이전트 rules.json에 같은 category로 존재할 때, rule 텍스트의 의미가 모순인지 판단.

| 조건 | 심각도 |
|------|--------|
| 의미적 모순 발견 | P2 |

### 3-3. 승인 병목

**확인 소스:**
- `deliverables`: self-improvement daily report의 proposals[].
- `thread_messages`: proposal ID에 대한 응답 유무.
- **Join key:** proposal ID

**Lookback:** 14일
**최소 표본:** 미승인 5건+

| 조건 | 심각도 |
|------|--------|
| 7일+ 미승인 제안 10건+ 적체 | P2 |
| 미승인 5건 미만 | 판정 보류 |

### 3-4. 목표 드리프트

**확인 소스:**
- `personal_goals` 테이블: `status=active`인 목표.
- `current_tasks` 테이블: 활성 태스크.
- **Join key:** `goal_id` ↔ 태스크의 `goal_link` (있는 경우) 또는 목표 키워드 매칭

**Lookback:** 7일
**최소 표본:** 활성 목표 3건+

| 조건 | 심각도 |
|------|--------|
| 활성 목표에 연결된 태스크 0건 (목표 3건+) | P2 |
| 활성 목표 3건 미만 | 판정 보류 |

### 3-5. 루프 stagnation

**확인 소스:** 각 루프의 산출물 소스 (차원 2와 동일)
**Lookback:** 30일
**방법:** 동일 루프가 30일간 어떤 변경도 만들지 않음 (MEMORY.md 변경 0건, rules.json 추가 0건, 돌파구 0건 등).

| 조건 | 심각도 |
|------|--------|
| 30일간 산출물 0건 | P2 |

### 3-6. suggestion-review 폐루프

**확인 소스:**
- `proactive_suggestions` 테이블: `status=approved`.
- `current_tasks` 테이블: 해당 suggestion에서 생성된 태스크.
- `cron_runs` + `deliverables`: 태스크 완료 후 self-improvement 입력 여부.
- **Join key:** `suggestion_id` → `task_id` → evaluation

**Lookback:** 14일
**최소 표본:** 승인 제안 3건+

| 조건 | 심각도 |
|------|--------|
| 완주율 0% (승인 → 태스크 → 완료 → 평가 → SI 입력 전 단절) | P2 |
| 승인 제안 3건 미만 | 판정 보류 |

### 3-7. 중복 규칙 churn

**확인 소스:**
- `workspace-{agent}/learnings/rules.json` (전 에이전트): 같은 `category`에 유사 `rule` 텍스트.
- `BELIEFS.md`: 같은 내용의 중복 항목.

**Lookback:** 30일
**방법:** 같은 category 내 rule 텍스트의 유사도가 높은(80%+) 쌍을 탐지.

| 조건 | 심각도 |
|------|--------|
| 실질 중복 규칙 발견 | P3 (INFO) |

### 3-8. memory-pruning backlog

**확인 소스:**
- `workspace-{agent}/MEMORY.md`: 항목 수 (줄 수 기반 추정).
- `cron_runs`: `cron_id` LIKE `memory-pruning%`, 최근 실행 여부.

**Lookback:** 30일

| 조건 | 심각도 |
|------|--------|
| MEMORY.md 300줄+ AND 최근 30일 pruning 미실행 | P2 |
```

- [ ] **Step 2: 변경 확인**

Run: `grep "^### 3-" core-skills/qa-patrol/references/deep-checks.md`
Expected: 3-1 ~ 3-8까지 8개 항목 출력

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/references/deep-checks.md
git commit -m "feat(qa-patrol): deep-checks.md 차원 3 (설계 결함) 검증 추가"
```

---

### Task 6: deep-checks.md 리포트 형식 추가

**Files:**
- Modify: `core-skills/qa-patrol/references/deep-checks.md` (append)

- [ ] **Step 1: 리포트 형식 섹션 추가**

deep-checks.md 끝에 아래 내용을 추가한다.

```markdown

---

## 딥 패트롤 리포트 형식

```
## QA Patrol Deep — {날짜} {시간}

### 파이프라인 완주 (7일 요약)
| 단계 | 완주율 | gate skip (failure) | gate skip (intentional) | 비고 |
|------|--------|---------------------|------------------------|------|
| journal-sweep | {N}/7 | {N} ({reason}) | {N} ({reason}) | |
| activity-compile | {N}/7 | {N} | {N} | |
| daily-digest | {N}/7 | {N} | {N} | |
| compound-review | {N}/7 | {N} | {N} | |
| self-improvement | {N}/7 | {N} | {N} | |
| meditation | {N}/7 | {N} | {N} | |

### 루프 효과 (lookback별)
- self-improvement ({lookback}일): 제안 {N}건, 승인 {M}건 ({%}) — Phase 2 기준 대비. 승인 후 미적용 {N}건.
- compound-review ({lookback}일): MEMORY.md 승격 {N}건, operations.md 승격 {N}건
- meditation ({lookback}일): 돌파구 {N}건
- beliefs ({lookback}일): unverified {N}건 (최고령 {N}일)
- suggestion-review ({lookback}일): 승인 {N}건 → 태스크 {N}건 → 완료 {N}건 → SI 입력 {N}건 (완주율 {%})

### 설계 결함
1. [P{X}] {항목}: {현상}
   - 확인: {evidence source + 데이터}
   - 판단: {분석 + 제안}

### 트렌드
- [RECURRING] / [CHRONIC] / [RESOLVED] / [PATTERN] (trend.md와 동일 규칙)

### Check (다음 딥 패트롤)
- [ ] {이전 딥 패트롤에서 요청한 확인 사항}
```

### 전송

```bash
# 설계 결함 P1 발견 시
minions thread add --author {agentId} --mentions mingming --tags alert,deep-patrol --content "리포트"

# P2 이하만
minions thread add --author {agentId} --mentions mingming --tags report,deep-patrol --content "리포트"

# 이상 없음
minions thread add --author {agentId} --tags report,deep-patrol --content "QA Patrol Deep — {날짜}: 3차원 검증 완료, 이상 0건."
```
```

- [ ] **Step 2: 변경 확인**

Run: `grep "전송" core-skills/qa-patrol/references/deep-checks.md`
Expected: "### 전송" 출력

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/references/deep-checks.md
git commit -m "feat(qa-patrol): deep-checks.md 리포트 형식 + 전송 규칙 추가"
```

---

### Task 7: SKILL.md 딥 패트롤 섹션 추가

**Files:**
- Modify: `core-skills/qa-patrol/SKILL.md:110-119`

- [ ] **Step 1: "## CLI Commands" 앞에 딥 패트롤 섹션 삽입**

SKILL.md의 `## CLI Commands` 바로 앞에 아래 섹션을 삽입한다.

```markdown
## 딥 패트롤

매일 1회 자가개선 루프의 라이프사이클을 검증한다. 기본 패트롤과 별도 크론으로 실행.

### 실행 절차

1. **완주 검증**: 야간 파이프라인 순서 완주, 빈 입력 전파, goal-lifecycle 쌍 → references/deep-checks.md 차원 1
2. **효과 검증**: 제안 승인률, reject 감소, 승격 건수, 돌파구, beliefs 처리율 → references/deep-checks.md 차원 2
3. **설계 결함 검증**: 빈 입력 전파, 규칙 충돌, 승인 병목, 목표 드리프트, stagnation → references/deep-checks.md 차원 3
4. **트렌드**: 이전 딥 패트롤 리포트와 비교 → references/trend.md (기본 패트롤과 동일 규칙)
5. **보고**: 리포트 작성 → references/deep-checks.md 리포트 형식

심각도 분류, 트렌드 태그는 기본 패트롤과 동일 규칙을 따른다.
항목별 lookback 기간이 다르므로 references/deep-checks.md의 각 항목을 반드시 참조한다.

```

- [ ] **Step 2: Cron 테이블에 qa-patrol-deep 추가**

SKILL.md 하단의 `## Cron` 테이블을 아래로 교체한다.

```markdown
## Cron

| 이름 | schedule | 설명 |
|------|----------|------|
| qa-patrol | `0 10,20 * * *` | 하루 2회 QA 순찰 |
| qa-patrol-deep | `0 14 * * *` | 매일 1회 자가개선 루프 라이프사이클 검증 |
```

- [ ] **Step 3: 변경 확인**

Run: `grep -n "딥 패트롤\|qa-patrol-deep" core-skills/qa-patrol/SKILL.md`
Expected: "딥 패트롤" 섹션과 Cron 테이블에 qa-patrol-deep 출력

- [ ] **Step 4: Commit**

```bash
git add core-skills/qa-patrol/SKILL.md
git commit -m "feat(qa-patrol): SKILL.md에 딥 패트롤 모드 섹션 추가"
```

---

### Task 8: cron.json에 qa-patrol-deep 엔트리 추가

**Files:**
- Modify: `core-skills/qa-patrol/cron.json`

- [ ] **Step 1: cron.json에 엔트리 추가**

기존 qa-patrol 엔트리 뒤에 qa-patrol-deep을 추가한다.

```json
[
	{
		"name": "qa-patrol",
		"schedule": "0 10,20 * * *",
		"tz": "Asia/Seoul",
		"target": "qa-patrol",
		"reason": "시스템 실행 결과 사후 검증",
		"instructions": "qa-patrol 스킬의 '실행 절차' 5단계를 따르세요. references/checks.md, references/auto-fix.md, references/trend.md를 참조하세요."
	},
	{
		"name": "qa-patrol-deep",
		"schedule": "0 14 * * *",
		"tz": "Asia/Seoul",
		"target": "qa-patrol-deep",
		"reason": "자가개선 루프 라이프사이클 검증",
		"instructions": "qa-patrol 스킬의 '딥 패트롤' 절차를 따르세요. references/deep-checks.md를 참조하세요. 항목별 lookback 기간을 준수하세요."
	}
]
```

- [ ] **Step 2: JSON 유효성 확인**

Run: `python3 -c "import json; json.load(open('core-skills/qa-patrol/cron.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add core-skills/qa-patrol/cron.json
git commit -m "feat(qa-patrol): cron.json에 qa-patrol-deep 크론 엔트리 추가"
```

---

### Task 9: 전체 일관성 검증

- [ ] **Step 1: SKILL.md에서 참조하는 references 파일이 모두 존재하는지 확인**

Run: `ls core-skills/qa-patrol/references/`
Expected: `auto-fix.md`, `checks.md`, `deep-checks.md`, `trend.md` 4개 파일

- [ ] **Step 2: checks.md에서 원인 판정 순서가 7단계 모두 있는지 확인**

Run: `grep -c "| [1-7] |" core-skills/qa-patrol/references/checks.md`
Expected: `7`

- [ ] **Step 3: deep-checks.md에서 차원별 항목 수 확인**

Run: `grep -c "^### [1-3]-" core-skills/qa-patrol/references/deep-checks.md`
Expected: `18` (차원 1: 4개 + 차원 2: 6개 + 차원 3: 8개)

- [ ] **Step 4: cron.json에 2개 엔트리 있는지 확인**

Run: `python3 -c "import json; data=json.load(open('core-skills/qa-patrol/cron.json')); print(len(data), [d['name'] for d in data])"`
Expected: `2 ['qa-patrol', 'qa-patrol-deep']`

- [ ] **Step 5: SKILL.md Cron 테이블에 qa-patrol-deep 있는지 확인**

Run: `grep "qa-patrol-deep" core-skills/qa-patrol/SKILL.md`
Expected: `| qa-patrol-deep | ...` 출력

- [ ] **Step 6: 스펙 커버리지 확인**

스펙(`docs/superpowers/specs/2026-03-28-qa-patrol-deep-design.md`)의 각 요구사항이 구현되었는지 확인:
- Part 1 영역 3 보강 → Task 1 (checks.md 원인 판정)
- Part 1 영역 4 보강 → Task 2 (checks.md ghost 출처)
- Part 2 차원 1 → Task 3 (deep-checks.md)
- Part 2 차원 2 → Task 4 (deep-checks.md)
- Part 2 차원 3 → Task 5 (deep-checks.md)
- Part 2 리포트 형식 → Task 6 (deep-checks.md)
- SKILL.md 딥 패트롤 섹션 → Task 7
- cron.json 엔트리 → Task 8
