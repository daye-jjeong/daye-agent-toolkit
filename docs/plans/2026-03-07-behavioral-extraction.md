# Behavioral Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** CC 세션에서 사용자의 의사결정/시행착오/패턴을 자동 추출하여 코칭에 제공

**Architecture:** SessionEnd hook에서 sonnet 2회 호출(요약 + 행동 추출) → work-log 기록 → sync_cc가 behavioral_signals 테이블에 저장 → 코칭이 SQL 집계로 소비

**Tech Stack:** Python3 stdlib, SQLite, Claude CLI (sonnet)

**Design doc:** `docs/plans/2026-03-07-behavioral-extraction-design.md`

---

### Task 1: DB 스키마 — behavioral_signals 테이블

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql` (끝에 추가)
- Modify: `shared/life-dashboard-mcp/db.py` (insert 함수 추가)

**Step 1: schema.sql에 테이블 추가**

```sql
CREATE TABLE IF NOT EXISTS behavioral_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    content TEXT NOT NULL,
    repo TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_signals_date ON behavioral_signals(date);
CREATE INDEX IF NOT EXISTS idx_signals_type ON behavioral_signals(signal_type);
```

**Step 2: db.py에 insert/query 함수 추가**

기존 `upsert_activity()` 패턴을 따라 `insert_behavioral_signal(conn, signal)` 추가.
`get_repeated_signals(conn, date_str, days=7, min_count=2)` — 코칭용 반복 패턴 집계.

**Step 3: DB 마이그레이션 실행**

Run: `python3 -c "from db import get_conn; get_conn()" ` (shared/life-dashboard-mcp/ 에서)
기존 DB에 테이블이 자동 생성되는지 확인. schema.sql이 `CREATE TABLE IF NOT EXISTS`라서 안전.

**Step 4: Commit**

```bash
git add shared/life-dashboard-mcp/schema.sql shared/life-dashboard-mcp/db.py
git commit -m "feat(db): behavioral_signals 테이블 + insert/query 함수"
```

---

### Task 2: session_logger — 모델 업그레이드 + user 메시지 추출

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py`

**Step 1: haiku → sonnet 변경**

`summarize_session()` 함수의 `--model haiku`를 `--model sonnet`으로 변경.
`SUMMARY_TIMEOUT_SEC`을 30 → 60으로 증가 (sonnet이 느림).

**Step 2: extract_user_messages() 함수 추가**

`extract_conversation()`을 참조하되 user 메시지만 추출:
- `entry_type == "user"`만 필터
- assistant 응답 제외
- 동일한 `strip_system_tags()` 적용
- `CONVERSATION_MAX_CHARS = 8000` 동일 적용

**Step 3: 검증**

Run: `python3 -c "from session_logger import extract_user_messages; ..."`
실제 transcript .jsonl 파일로 테스트 (있으면).

**Step 4: Commit**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "feat(session_logger): sonnet 업그레이드 + extract_user_messages"
```

---

### Task 3: session_logger — 행동 추출 함수 + main 통합

**Files:**
- Modify: `cc/work-digest/scripts/session_logger.py`

**Step 1: extract_behavioral_signals() 함수 추가**

`summarize_session()`과 동일한 구조로:
- 입력: `extract_user_messages()` 결과 + repo
- sonnet에게 JSON 출력 요청: `{"decisions": [...], "mistakes": [...], "patterns": [...]}`
- 파싱: JSON 추출 + validation (각 항목 string, 빈 배열 허용)
- 실패 시 None 반환

프롬프트:
```
레포: {repo}

다음은 Claude Code 세션에서 사용자가 보낸 메시지들이다.

{user_messages}

이 사용자의 행동 신호를 추출해라. 각 항목은 1줄, 30자 이내.
없으면 빈 배열.

JSON으로만 출력. 다른 텍스트 없이:
{"decisions": [...], "mistakes": [...], "patterns": [...]}
```

**Step 2: main()에 행동 추출 호출 추가**

`if event == "SessionEnd":` 블록에서 요약 호출 후:
```python
user_msgs = extract_user_messages(transcript_path)
signals = extract_behavioral_signals(user_msgs, repo)
if signals:
    data["behavioral_signals"] = signals
```

**Step 3: build_session_section()에 행동 신호 표시 추가**

work-log 마크다운에 표시:
```markdown
**결정**: A 대신 B 선택, sonnet 사용
**시행착오**: 테스트 없이 배포 후 롤백
```

빈 배열이면 해당 줄 생략.

**Step 4: 검증**

Run: `python3 -c "from session_logger import extract_behavioral_signals, _parse_signals_response; ..."`
mock JSON으로 파싱 함수 테스트.

**Step 5: Commit**

```bash
git add cc/work-digest/scripts/session_logger.py
git commit -m "feat(session_logger): 행동 추출 파이프라인 + work-log 기록"
```

---

### Task 4: parse_work_log — 행동 신호 파싱

**Files:**
- Modify: `cc/work-digest/scripts/parse_work_log.py`

**Step 1: 행동 신호 regex + 파싱 추가**

`parse_session_block()`에서 `**결정**:`, `**시행착오**:` 줄을 파싱.
기존 `RE_SUMMARY` 패턴을 참고해서:
```python
RE_DECISIONS = re.compile(r"^\*\*결정\*\*:\s*(.+)$")
RE_MISTAKES = re.compile(r"^\*\*시행착오\*\*:\s*(.+)$")
```

반환 dict에 `decisions`, `mistakes` 필드 추가.

**Step 2: 검증**

Run: `python3 parse_work_log.py --date 2026-03-07` (수정 후 기존 데이터가 깨지지 않는지)

**Step 3: Commit**

```bash
git add cc/work-digest/scripts/parse_work_log.py
git commit -m "feat(parse_work_log): 행동 신호(결정/시행착오) 파싱"
```

---

### Task 5: sync_cc — behavioral_signals INSERT

**Files:**
- Modify: `shared/life-dashboard-mcp/sync_cc.py`

**Step 1: sync_date()에 행동 신호 INSERT 추가**

각 세션의 `decisions`, `mistakes`를 `behavioral_signals` 테이블에 INSERT.
session_id + signal_type + content로 중복 방지 (INSERT OR IGNORE 또는 존재 체크).

```python
from db import get_conn, upsert_activity, update_daily_stats, insert_behavioral_signal

# 세션 루프 안에서:
for decision in s.get("decisions", []):
    insert_behavioral_signal(conn, {
        "session_id": session_id,
        "date": date_str,
        "signal_type": "decision",
        "content": decision,
        "repo": s.get("repo", ""),
    })
# mistakes, patterns도 동일
```

**Step 2: 검증**

Run: `python3 sync_cc.py --date 2026-03-07` (기존 데이터가 정상 sync되는지)
Run: `sqlite3 <db_path> "SELECT * FROM behavioral_signals LIMIT 5"`

**Step 3: Commit**

```bash
git add shared/life-dashboard-mcp/sync_cc.py
git commit -m "feat(sync_cc): behavioral_signals INSERT 추가"
```

---

### Task 6: 코칭 프롬프트 — 반복 패턴 데이터 주입

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py`
- Modify: `shared/life-coach/references/coaching-prompts.md`

**Step 1: daily_coach.py — get_today_data()에 행동 신호 추가**

```python
signals = conn.execute("""
    SELECT signal_type, content FROM behavioral_signals WHERE date = ?
""", (date_str,)).fetchall()

repeated = conn.execute("""
    SELECT content, COUNT(*) as cnt FROM behavioral_signals
    WHERE date >= ? AND signal_type IN ('mistake', 'pattern')
    GROUP BY content HAVING cnt >= 2
    ORDER BY cnt DESC LIMIT 5
""", (seven_days_ago,)).fetchall()
```

`data`에 `signals`와 `repeated_patterns` 추가.

**Step 2: build_template_report()에 행동 신호 섹션 추가**

```
🧠 오늘의 행동 신호:
  결정: A 선택, B 선택
  시행착오: C 발생

⚠️ 반복 패턴 (최근 7일):
  - "테스트 없이 배포" (3회)
  - "설계 없이 코딩 시작" (2회)
```

**Step 3: coaching-prompts.md 업데이트**

코칭 프롬프트에 반복 패턴 데이터 참조 지시 추가.
"🔍 코칭" 섹션에: "반복 패턴 데이터가 있으면 구체적으로 짚고, 개선 방법 또는 자동화(hook, 스킬) 제안."

**Step 4: 검증**

Run: `python3 daily_coach.py --dry-run --date 2026-03-07`
기존 리포트가 깨지지 않는지 + 신규 섹션이 데이터 있을 때만 표시되는지.

**Step 5: Commit**

```bash
git add shared/life-coach/scripts/daily_coach.py shared/life-coach/references/coaching-prompts.md
git commit -m "feat(coaching): 행동 신호 + 반복 패턴 데이터 주입"
```

---

### Task 7: hook 예외 규칙 명시

**Files:**
- Modify: `.claude/rules/correction-20260307-2030-no-subprocess-llm.md`

**Step 1: hook 스크립트 예외 추가**

기존 규칙 끝에:
```markdown
## 예외: hook 스크립트

session_logger.py는 CC hook 스크립트이며 스킬 스크립트가 아니다.
SessionEnd에서의 LLM subprocess 호출(요약 + 행동 추출)은 허용.
이유: hook은 세션 외부에서 실행되며, 데이터 수집 인프라의 일부.
```

**Step 2: Commit**

```bash
git add .claude/rules/correction-20260307-2030-no-subprocess-llm.md
git commit -m "chore: hook 스크립트 LLM subprocess 예외 명시"
```
