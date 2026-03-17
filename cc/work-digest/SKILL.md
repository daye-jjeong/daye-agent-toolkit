---
name: work-digest
description: 일일 작업 다이제스트 — CC 세션 자동 기록 + "정리해줘"로 작업 단위 분해. 사용자가 "정리해줘", "오늘 뭐 했지?", "작업 정리", "요약해줘" 등을 요청할 때 사용.
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Work Digest Skill

CC 세션 로그를 자동 기록하고, 사용자 요청 시 작업 단위로 분해+요약한다.

## 구조

```
work-digest/
├── SKILL.md
├── scripts/
│   ├── session_logger.py         # SessionEnd hook — 세션 메타+원본 자동 기록 (LLM 없음)
│   ├── active_session_scanner.py # 열린 세션 스캔 + 기록
│   ├── extract_session.py        # .jsonl → segments 추출 (결정적)
│   └── extract_day.py            # 하루치 전체 세션 segments 추출
```

## 자동 기록 (LLM 없음, 항상 동작)

### SessionEnd hook

```
세션 종료 → session_logger.py
  → parse_transcript_by_date(): 트랜스크립트를 날짜별 분할
  → sessions INSERT (start_at, end_at, duration_min, tokens, repo)
  → session_content INSERT (user_messages, files_changed, commands)
  → daily_stats 갱신
  → behavioral_signals 추출 (LLM subprocess — 결정/실수/패턴)
  → 텔레그램 알림
```

### Scanner

```
cron 또는 수동 → active_session_scanner.py
  → 열린 세션 탐색 (sessions dir + projects dir)
  → sessions + session_content 갱신
```

## "정리해줘" — 작업 단위 분해

사용자가 "정리해줘", "오늘 뭐 했지?", "작업 정리해줘" 등을 요청할 때 실행.

**원칙: 코드가 시간, LLM이 내용.**

### Step 1: 추출 (코드, 결정적)

```bash
python3 {baseDir}/scripts/extract_day.py --date <DATE>
```

출력: 세션별 segments (시간 경계 확정, idle gap 기준 분리, 각 구간의 user messages + file edits)

### Step 2: 토픽 생성 (LLM)

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

### Step 3: 저장 + 검증

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

## 데이터 흐름

```
트랜스크립트 .jsonl (CC 실시간)
  ↓ SessionEnd hook
sessions + session_content + daily_stats + signals (자동)
  ↓ "정리해줘" (사용자 트리거)
extract_day.py → segments (결정적)
  ↓ LLM
session_topics (기능 단위, 정확한 시간)
  ↓ life-coach
daily_report + coaching
```
