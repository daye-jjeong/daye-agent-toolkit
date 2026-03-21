---
name: work-digest
description: 일일 작업 다이제스트 — CC 세션 자동 기록 + 데이터 준비 파이프라인. 세션 수집, 요약, 토픽 분해를 담당한다. "오늘 뭐 했지?", "작업 정리", "요약해줘" 등의 요청이나, life-coach 등 다른 스킬이 데이터 준비를 필요로 할 때 사용.
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Work Digest Skill

CC 세션 로그를 자동 기록하고, 데이터 준비 파이프라인으로 작업 단위를 분해+요약한다.

## 스킬 경계

| 역할 | 담당 |
|------|------|
| 세션 기록 (hook) | work-digest |
| 데이터 준비 (수집→요약→토픽) | work-digest |
| 코칭 생성 + 리포트 | life-coach |

## 구조

```
work-digest/
├── SKILL.md
├── scripts/
│   ├── session_logger.py         # SessionEnd hook — 세션 메타+원본 자동 기록 (LLM 없음)
│   ├── active_session_scanner.py # 열린 세션 스캔 + 기록
│   ├── extract_session.py        # .jsonl → segments 추출 (결정적)
│   ├── extract_day.py            # 하루치 전체 세션 segments 추출
│   └── validate_topics.py        # 토픽 검증
```

## 자동 기록 (LLM 없음, 항상 동작)

### SessionEnd hook

```
세션 종료 → session_logger.py
  → parse_transcript_by_date(): 트랜스크립트를 날짜별 분할
  → sessions INSERT (start_at, end_at, duration_min, tokens, repo)
  → session_content INSERT (user_messages, files_changed, commands)
  → daily_stats 갱신
  → signals 추출 (LLM subprocess — decision/mistake/pattern)
  → 텔레그램 알림
```

## 데이터 준비 파이프라인

사용자 요청이나 다른 스킬(life-coach 등)의 호출로 실행된다.
5단계를 순서대로 따른다.

**원칙: 코드가 시간, LLM이 내용.**

### Step 1: 세션 수집

```bash
python3 {baseDir}/scripts/active_session_scanner.py
```

열린 세션을 탐색하여 DB에 반영한다.

### Step 2: 세션 요약

```bash
# 미요약 세션 확인
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py unsummarized --date <DATE>
```

미요약 세션마다 태그+요약+status를 생성하여 저장:
```bash
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-summary \
    --session-id <SID> --date <DATE> --tag "태그" --summary "요약" \
    --status completed
```
- `--status`: `completed`, `in_progress`, `blocked`, `follow_up`
- `--follow-up`: follow_up/blocked일 때 구체적 다음 행동 명시

### Gate A: 요약 품질 검증

Step 2 완료 후, Step 3 진입 전에 실행.

1. `unsummarized --date <DATE>` 재실행 → 0건이어야 통과
2. `-claude` 레포 세션은 tag="eval", summary="자동 스킬 eval 세션"으로 일괄 처리 (LLM 요약 불필요)
3. eval 세션 시간대와 겹치는 건강 기록(health_exercises, health_symptoms, health_meals) 확인 → 있으면 삭제
4. 미요약 잔존 시 해당 세션 요약 후 재확인

### Step 3: Segment 추출 (결정적)

```bash
python3 {baseDir}/scripts/extract_day.py --date <DATE>
```

출력: 세션별 segments (시간 경계 확정, idle gap 기준 분리, 각 구간의 user messages + file edits)

### Step 4: 토픽 생성 (LLM)

extract_day.py 출력의 segments를 보고 각 구간에 토픽을 만든다.

**핵심 원칙 3가지:**

1. **시간은 코드가 결정** — segment의 start/end/duration을 그대로 사용한다. 추정하거나 병합하면 idle gap이 사라져서 리포트에서 실제 작업 시간이 왜곡된다.

2. **토픽 = 기능 단위** — "설계/코딩/리뷰"로 나누면 하나의 기능이 3개로 쪼개진다. pipeline-redesign이라는 하나의 기능 안에서 설계→구현→리뷰를 했으면 하나의 토픽.

3. **코칭에 쓸 수 있는 수준** — 이 요약만 읽고 "뭘 했고, 왜 했고, 결과가 뭐고, 다음에 뭘 해야 하는지" 판단 가능해야 한다. "cron 수정"은 부족. "cron 중복 해결 — mingming 직접 분석 문제, PROPOSAL 상태 추가, simplify+PR review 후 머지"는 충분.

**구체 지침:**

- segment 1:1로 토픽 생성 (segment 수 = topic 수)
- tag는 실제 활동과 일치 (확인만 했으면 ops, 코드 작성했으면 코딩)
- 여러 작업이 섞인 segment: (1)(2)(3) + 시간 비중 표기
- 다른 세션 연결: `[세션ID에서 이어짐]`
- completed이면 결과 명시 (머지, spec 완료 등)
- follow_up은 구체적 (모호한 "대응" 금지)
- 반복 패턴은 몇 번째인지 명시

**signals 동시 생성** — 각 토픽에서 의사결정/실수/패턴을 같이 추출.

**완성 예시**: `{baseDir}/references/topic-creation-guide.md` 참조

### Step 5: 저장 + 검증

```bash
# 각 세션별로 update-topics 실행
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-topics \
    --session-id <SID> --date <DATE> \
    --topics '<JSON array>'

# 모든 세션 저장 후 자동 검증
python3 {baseDir}/scripts/validate_topics.py --date <DATE>
```

validate_topics.py가 자동 확인:
- segment 수 = topic 수 (1:1)
- 모든 start_at/end_at/duration이 segment 값과 일치
- tag가 실제 활동과 일치 (메시지 내용 대조)

### Gate B-1: 구조 검증

    python3 {baseDir}/scripts/validate_topics.py --fix --date <DATE>

- eval 세션(`-claude` 레포) 면제, repo NULL 자동 채움, eval 태그 자동 변경
- 에러 0이면 Gate B-2로 진행
- 에러 있으면 해당 토픽 재생성 후 재검증 (최대 2회)
- 2회 실패 시 파이프라인 중단, 사용자에게 보고

### Gate B-2: 내용 품질 검증 (LLM 자기 검증)

`daily_coach.py --json` 출력의 topics + sessions(user_messages)를 읽고 판단.

통과 기준:
- **PASS**: 모든 항목 이상 없음 → Phase 2로 진행
- **WARN**: 경미한 품질 이슈 → 진행하되 로그 기록
- **FAIL**: 내용 불일치, eval 혼입, 병합 필요 → 수정 후 Gate B-1부터 재실행

체크 항목:
1. 토픽 summary가 user_messages 내용과 일치하는지 (태그-활동 불일치 감지)
2. 같은 레포 연속 5분 미만 세션이 하나의 맥락이면 병합
3. 요약이 코칭에 쓸 수 있는 수준인지 (명령어 나열 아닌 뭘/왜/결과)
4. 1-2분 단순 명령(/exit, /clear)은 독립 토픽으로 만들지 않음
5. eval 세션이 실제 작업 토픽에 섞이지 않았는지

## 데이터 흐름

```
트랜스크립트 .jsonl (CC 실시간)
  ↓ SessionEnd hook
sessions + session_content + daily_stats + signals (자동)
  ↓ 데이터 준비 파이프라인 (사용자 요청 or life-coach 호출)
Step 1: scanner → 열린 세션 DB 반영
Step 2: unsummarized → 세션 요약
Step 3: extract_day.py → segments (결정적)
Step 4: LLM → session_topics (기능 단위, 정확한 시간)
Step 5: update-topics + validate
  ↓ life-coach
daily_report + coaching
```
