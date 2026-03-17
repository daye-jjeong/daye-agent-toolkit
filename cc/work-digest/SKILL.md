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

extract_day.py 출력의 segments를 보고 각 구간에 대해:

1. **segment = topic 1:1 원칙**:
   - segment를 병합하지 마라. 각 segment가 하나의 토픽.
   - 시간은 segment에서 온 값만 사용. 절대 추정하지 마라.
   - segment 사이 gap = idle. 이 gap을 없애는 병합 금지.

2. **토픽 = 기능 단위** (활동 유형이 아님):
   - 같은 기능의 설계→구현→리뷰가 하나의 segment에 있으면 하나의 토픽
   - 나쁜: [설계] spec / [코딩] 구현 / [리뷰] PR review (활동 유형별)
   - 좋은: pipeline-redesign — spec + 구현 + 리뷰 완료 (기능 단위)

3. **tag는 실제 활동과 일치**:
   - 코드 작성했으면 "코딩", 상태 확인만 했으면 "ops", 설계 논의했으면 "설계"
   - 메시지 2개로 확인만 했는데 tag="코딩" 금지

4. **짧은 segment(≤3분)**:
   - 실제 활동이 짧았던 것. 억지로 늘리지 마라.
   - summary는 실제로 한 것만. 안 한 걸 적지 마라.

5. **하나의 segment에 여러 작업이 섞여있으면**:
   - segment 시간 내에서 분리하지 않는다 (시간 추정 금지)
   - summary에 (1)(2)(3)으로 순서 표기
   - **각 작업의 대략적 시간 비중도 표기**: "(1) 멘션 처리 (~20분). (2) retry 진단 (~30분). (3) cron 구조 검토 (~70분)"

6. **다른 세션에서 이어진 작업은 연결 표기**:
   - 같은 기능을 다른 세션에서 이어했으면 `[세션ID에서 이어짐]` 또는 `[세션ID로 이어짐]` 추가
   - 예: "[f9524da1에서 cron 구조 검토 시작됨]", "[f9524da1→5a45a36d로 cron 수정 이어짐]"

7. **summary에 결과/산출물 명시**:
   - completed이면 반드시 결과를 적어라: "커밋", "머지", "spec 작성 완료", "설정 완료"
   - 나쁜: "리포트 개선" (뭘 개선했는지 모름)
   - 좋은: "리포트 개선 — UTC→KST 변환, 조리시간 KPI 추가, 방치 주문 기준 명시"

8. **각 토픽에 채울 것**:
   - `tag`: 실제 활동과 일치
   - `summary`: 무엇을/왜/결과/의사결정. "다음에 뭘 해야 하는지" 판단 가능한 수준
   - `status`: completed / in_progress / blocked / follow_up
   - `follow_up`: 후속 작업 (없으면 생략). **"모델 제한 대응"처럼 모호하게 적지 마라** → "haiku 모델 응답 품질 저하 — sonnet 전환 검토 또는 프롬프트 강화"
   - `start_at`, `end_at`: segment에서 온 값 그대로
   - `duration_estimate_min`: segment의 duration_min 그대로

9. **반복 패턴/문제는 명시적 기록** (예: "rule 있는데 에이전트가 반복 위반 — 3번째")

10. **signals 동시 생성**:
    각 토픽을 만들면서 해당 구간의 의사결정, 실수, 패턴을 같이 추출.
    - `decision`: 왜 그렇게 결정했는지 reasoning 포함. "A 대신 B를 선택 — 이유: ..."
    - `mistake`: 뭘 잘못했고 왜 문제인지. "X를 안 해서 Y가 발생"
    - `pattern`: 반복되는 것. 몇 번째인지, 이전에 언제 발생했는지 포함

    ```bash
    # signals 저장 (DB 직접 또는 activity_writer CLI)
    python3 -c "
    from db import get_conn, insert_signal
    conn = get_conn()
    insert_signal(conn, {
        'session_id': '<SID>', 'date': '<DATE>',
        'signal_type': 'decision|mistake|pattern',
        'content': '내용',
        'reasoning': '이유',
        'repo': 'repo-name'
    })
    conn.commit(); conn.close()
    "
    ```

### Step 3: 저장

```bash
# 각 세션별로 update-topics 실행
python3 {baseDir}/../../shared/life-dashboard-mcp/activity_writer.py update-topics \
    --session-id <SID> --date <DATE> \
    --topics '<JSON array>'
```

### Step 4: 검증

토픽 저장 후 반드시 확인:
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
