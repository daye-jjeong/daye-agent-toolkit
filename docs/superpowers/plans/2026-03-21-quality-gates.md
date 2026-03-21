# Quality Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코치 데이터 파이프라인에 5-layer quality gate를 추가하여 깨진 리포트가 사용자에게 전달되지 않도록 한다.

**Architecture:** validate_topics.py를 확장하여 --fix 모드 추가 (Gate B-1). daily_report.py에 --validate 플래그 추가 (Gate C). save-task에 중복 방지 로직 추가. SKILL.md에 Gate A/B-2 프로세스 명시.

**Tech Stack:** Python 3, SQLite, HTML 파싱 (re)

**Spec:** `docs/superpowers/specs/2026-03-21-quality-gates-design.md`

---

## File Structure

| 파일 | 역할 | 변경 유형 |
|------|------|-----------|
| `cc/work-digest/scripts/validate_topics.py` | Gate B-1 구조 검증 + --fix | 대폭 수정 |
| `shared/life-dashboard-mcp/db.py` | save-task 중복 방지 | 함수 수정 |
| `shared/life-coach/scripts/daily_report.py` | Gate C --validate | 함수 추가 |
| `cc/work-digest/SKILL.md` | Gate A, B-1, B-2 프로세스 | 섹션 추가 |
| `shared/life-coach/SKILL.md` | Gate C, 자가개선 루프 | 섹션 추가 |
| `shared/life-coach/references/coaching-prompts.md` | 태스크 중복 방지 지침 | 줄 추가 |
| `shared/life-coach/references/gate-c-issues.json` | 이슈 로그 | 신규 |

---

### Task 1: validate_topics.py --fix 모드 (Gate B-1)

**Files:**
- Modify: `cc/work-digest/scripts/validate_topics.py`

- [ ] **Step 1: validate 함수 전체 재작성 — --fix + eval 면제 + repo/summary 체크**

기존 validate() 함수를 교체. 변경 사항:
- `fix=False` 파라미터 추가
- `--fix` 시: repo NULL 채움, `-claude` 레포 → eval 태그 변경
- eval 세션(`-claude` 레포) 검증 skip
- 기존 체크(segment:topic 1:1, 시간, tag, summary 길이) 유지
- 추가: repo NULL 체크, summary 3건+ 동일 반복 감지

```python
def validate(date_str: str, fix: bool = False) -> bool:
    sessions = find_transcripts(date_str)
    conn = get_conn()

    if fix:
        # repo NULL → 부모 세션에서 채움
        conn.execute("""
            UPDATE session_topics SET repo = (
                SELECT s.repo FROM sessions s
                WHERE s.source = session_topics.source
                AND s.session_id = session_topics.session_id
                AND s.date = session_topics.date
            ) WHERE repo IS NULL AND date = ?
        """, (date_str,))
        # -claude 레포 → eval 태그 (session_topics + sessions 양쪽)
        conn.execute("""
            UPDATE session_topics SET tag = 'eval'
            WHERE date = ? AND session_id IN (
                SELECT session_id FROM sessions WHERE repo = '-claude'
            ) AND tag != 'eval'
        """, (date_str,))
        conn.execute("""
            UPDATE sessions SET tag = 'eval'
            WHERE date = ? AND repo = '-claude' AND tag != 'eval'
        """, (date_str,))
        conn.commit()

    # eval 세션 ID 집합 (-claude 레포 = eval)
    eval_sids = {r[0] for r in conn.execute(
        "SELECT session_id FROM sessions WHERE repo = '-claude' AND date = ?",
        (date_str,)
    )}

    total_segments = 0
    total_topics = 0
    errors = []

    for s in sessions:
        if not s.get("transcript"):
            continue
        sid = s["session_id"]
        if sid in eval_sids:
            continue  # eval 면제

        data = extract(s["transcript"], date_str)
        segments = merge_segments(data.get("segments", []))
        if not segments:
            continue

        topics = conn.execute(
            "SELECT start_at, end_at, duration_estimate_min, tag, summary, repo "
            "FROM session_topics WHERE session_id = ? AND date = ? ORDER BY topic_order",
            (sid, date_str),
        ).fetchall()

        total_segments += len(segments)
        total_topics += len(topics)

        if len(segments) != len(topics):
            errors.append(f"{sid[:8]}: segments={len(segments)} topics={len(topics)} MISMATCH")
            continue

        for i, (seg, top) in enumerate(zip(segments, topics)):
            # 시간 일치
            raw_start = top["start_at"] or ""
            if len(raw_start) >= 16:
                topic_start = raw_start[11:16]
            elif len(raw_start) == 5:
                topic_start = raw_start
            else:
                topic_start = "?"
            if seg["start"] != topic_start:
                errors.append(f"{sid[:8]} #{i}: seg.start={seg['start']} topic.start={topic_start}")

            # tag 유효성
            if not top["tag"] or top["tag"] == "기타":
                errors.append(f"{sid[:8]} #{i}: tag={top['tag']} (should be specific)")

            # summary 길이
            if not top["summary"] or len(top["summary"]) < 10:
                errors.append(f"{sid[:8]} #{i}: summary too short ({len(top['summary'] or '')} chars)")

            # repo NULL
            if not top["repo"]:
                errors.append(f"{sid[:8]} #{i}: repo is NULL")

    # summary 반복 감지 (eval 제외 전체)
    repeated = conn.execute(
        "SELECT summary, COUNT(*) as cnt FROM session_topics "
        "WHERE date = ? AND tag != 'eval' GROUP BY summary HAVING cnt >= 3",
        (date_str,)
    ).fetchall()
    for row in repeated:
        errors.append(f"summary repeated {row[1]}x: \"{row[0][:50]}\"")

    conn.close()

    print(f"segments: {total_segments}, topics: {total_topics}")
    if errors:
        print(f"\n{len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")
        return False
    else:
        print("✓ all checks passed")
        return True
```

- [ ] **Step 2: main()에 --fix 인자 연결**

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--fix", action="store_true", help="Auto-fix repo NULL, eval tags")
    args = ap.parse_args()
    ok = validate(args.date, fix=args.fix)
    sys.exit(0 if ok else 1)
```

- [ ] **Step 3: 테스트 — 3/20 데이터로 검증**

```bash
python3 cc/work-digest/scripts/validate_topics.py --date 2026-03-20
# Expected: eval 면제되어 실제 작업 세션만 검증. 에러 수 확인.

python3 cc/work-digest/scripts/validate_topics.py --fix --date 2026-03-20
# Expected: fix 후 exit 0 (all checks passed)
```

- [ ] **Step 4: 커밋**

```bash
git add cc/work-digest/scripts/validate_topics.py
git commit -m "feat: validate_topics.py --fix 모드 + eval 면제 + repo NULL 체크"
```

---

### Task 2: save-task 중복 방지

**Files:**
- Modify: `shared/life-dashboard-mcp/db.py` — `upsert_task_suggestion` 함수

- [ ] **Step 1: 기존 pending 태스크 중복 체크 로직 추가**

description에서 한국어 핵심어(첫 명사구)로 매칭. 앞 3단어 이상 일치하면 기존 것 업데이트.

```python
def upsert_task_suggestion(conn: sqlite3.Connection, data: dict):
    # 중복 체크: pending 태스크 중 앞 3단어 동일한 것이 있으면 업데이트
    desc_words = data["description"].split()[:3]
    if len(desc_words) >= 2:
        prefix = " ".join(desc_words)
        existing = conn.execute(
            "SELECT id FROM task_suggestions WHERE status = 'pending' AND description LIKE ? || '%'",
            (prefix,)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE task_suggestions
                SET suggested_date = ?, description = ?, estimated_min = ?,
                    priority = ?, source_type = ?
                WHERE id = ?
            """, (data["suggested_date"], data["description"], data["estimated_min"],
                  data["priority"], data["source_type"], existing["id"]))
            return

    conn.execute("""
        INSERT INTO task_suggestions (suggested_date, description, estimated_min,
            priority, source_type, origin_session_id, status)
        VALUES (:suggested_date, :description, :estimated_min,
            :priority, :source_type, :origin_session_id, :status)
        ON CONFLICT(suggested_date, description) DO UPDATE SET
            estimated_min=excluded.estimated_min, priority=excluded.priority,
            source_type=excluded.source_type, origin_session_id=excluded.origin_session_id
    """, data)
```

변경점: 5단어 → 3단어 (한국어 태스크명은 "사주앱 기획", "이번 주" 등 짧으므로), 최소 2단어.

- [ ] **Step 2: 테스트 — 중복 저장 시도**

```bash
# 같은 주제 2번 저장 (앞 3단어 "사주앱 기획 착수" 동일)
python3 shared/life-dashboard-mcp/activity_writer.py save-task \
    --date 2026-03-21 --description "사주앱 기획 착수 — 중복 체크 1" --estimated-min 30 --priority 1
python3 shared/life-dashboard-mcp/activity_writer.py save-task \
    --date 2026-03-22 --description "사주앱 기획 착수 — 중복 체크 2 (업데이트됨)" --estimated-min 60 --priority 1

# 검증: "사주앱 기획 착수" pending이 1건이고, 날짜가 3/22, estimated_min이 60인지 확인
python3 -c "
import sqlite3
conn = sqlite3.connect('/Users/dayejeong/life-dashboard/data.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(\"SELECT id, suggested_date, description, estimated_min FROM task_suggestions WHERE status='pending' AND description LIKE '사주앱 기획 착수%'\").fetchall()
for r in rows: print(dict(r))
assert len(rows) == 1, f'Expected 1, got {len(rows)}'
assert rows[0]['suggested_date'] == '2026-03-22', f'Expected 2026-03-22, got {rows[0][\"suggested_date\"]}'
assert rows[0]['estimated_min'] == 60, f'Expected 60, got {rows[0][\"estimated_min\"]}'
print('✓ dedup test passed')
"
```

- [ ] **Step 3: 테스트 데이터 정리 + 커밋**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/Users/dayejeong/life-dashboard/data.db')
conn.execute(\"DELETE FROM task_suggestions WHERE description LIKE '사주앱 기획 착수 — 중복%'\")
conn.commit()
"
git add shared/life-dashboard-mcp/db.py
git commit -m "feat: save-task 중복 방지 — pending 태스크 앞 3단어 매칭"
```

---

### Task 3: daily_report.py --validate (Gate C)

**Files:**
- Modify: `shared/life-coach/scripts/daily_report.py`
- Create: `shared/life-coach/references/gate-c-issues.json`

- [ ] **Step 1: validate_report 함수 추가**

`_build_repos_detail` 함수 위에 추가 (line ~318 부근):

```python
def validate_report(html: str, data: dict) -> list[dict]:
    """Gate C: HTML 리포트 프리뷰 검증. 이슈 목록 반환."""
    import re as _re
    issues = []
    date_str = data.get("date", "")

    # 1. 세션 수에 eval 포함
    m = _re.search(r'stat-val">(\d+)</div><div class="stat-lbl">세션', html)
    real_count = len([s for s in data.get("sessions", []) if s.get("tag") != "eval"])
    if m and int(m.group(1)) != real_count:
        issues.append({"type": "eval-leak", "detail": f"stats sessions {m.group(1)} != real {real_count}"})

    # 2. tag pill에 eval 표시
    if _re.search(r'tag-pill[^>]*>eval', html):
        issues.append({"type": "eval-leak", "detail": "eval tag in tag pills"})

    # 3. 토큰 수에 eval 포함
    eval_tokens = sum(s.get("token_total", 0) for s in data.get("sessions", []) if s.get("tag") == "eval")
    if eval_tokens > 0:
        m = _re.search(r'stat-val">([\d.]+)M</div><div class="stat-lbl">토큰', html)
        if m:
            total_tokens = sum(s.get("token_total", 0) for s in data.get("sessions", []))
            real_tokens = total_tokens - eval_tokens
            displayed = float(m.group(1)) * 1_000_000
            if abs(displayed - real_tokens) > real_tokens * 0.1:
                issues.append({"type": "eval-leak", "detail": f"tokens include eval: displayed={m.group(1)}M"})

    # 4. 레포명 unknown
    for m in _re.finditer(r'repo-name[^>]*>([^<]+)<', html):
        name = m.group(1).strip()
        if name in ("unknown", "", "None"):
            issues.append({"type": "repo-null", "detail": f"repo name: '{name}'"})

    # 5. 건강 데이터: eval 시간대 겹침 (주 기준)
    try:
        _mcp = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
        sys.path.insert(0, str(_mcp))
        from db import get_conn as _get_conn
        conn = _get_conn()
        eval_exists = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE date = ? AND repo = '-claude'",
            (date_str,)
        ).fetchone()[0]
        if eval_exists:
            for table in ["health_exercises", "health_symptoms", "health_meals"]:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE date = ?", (date_str,)
                ).fetchone()[0]
                if count:
                    issues.append({"type": "fake-health", "detail": f"{table}: {count} records on eval day"})
        conn.close()
    except Exception:
        pass

    # 6. 가짜 키워드 (보조)
    for kw in ["테스트용", "스크립트 검증", "알수없는음식"]:
        if kw in html:
            issues.append({"type": "fake-health", "detail": f"keyword '{kw}'"})

    # 7. 제안 태스크 중복
    task_texts = _re.findall(r'work-summary[^>]*>([^<]{5,})', html)
    from collections import Counter
    prefix_counter = Counter(" ".join(t.split()[:3]) for t in task_texts if len(t.split()) >= 3)
    for prefix, cnt in prefix_counter.items():
        if cnt >= 3:
            issues.append({"type": "task-dup", "detail": f"'{prefix}' x{cnt}"})

    # 8. 타임라인에 eval 잔존
    if _re.search(r'data-tag="eval"', html) or _re.search(r'"-claude"', html):
        issues.append({"type": "eval-leak", "detail": "eval in timeline data"})

    # 9. 빈 섹션
    if 'coaching-placeholder' in html or 'coaching-empty' in html:
        issues.append({"type": "empty-section", "detail": "coaching section empty"})

    # 10. 1-2분 단순 명령 독립 항목 (Gate B-2 실패 감지용)
    trivial_patterns = [r'/exit[^a-z]', r'/clear[^a-z]', r'/login[^a-z]', r'/reload']
    for pat in trivial_patterns:
        matches = _re.findall(pat, html)
        if len(matches) > 1:
            issues.append({"type": "trivial-topic", "detail": f"'{pat}' appears {len(matches)}x as topics"})

    return issues
```

- [ ] **Step 2: --validate 플래그를 main()에 연결**

`daily_report.py` main() 함수 (line 858~)를 수정. `parser.add_argument` 뒤에 `--validate` 추가.
`html = build_daily_report(...)` 다음에 검증 로직 삽입:

```python
# argparse에 추가 (line ~863)
parser.add_argument("--validate", action="store_true", help="Gate C: validate report before saving")

# html 생성 후, 파일 저장 전에 삽입 (line ~892, html = build_daily_report(...) 다음)
if args.validate:
    vi = validate_report(html, raw)
    if vi:
        print(f"[daily_report] ⚠ Gate C: {len(vi)} issues", file=sys.stderr)
        for iss in vi:
            print(f"  ✗ [{iss['type']}] {iss['detail']}", file=sys.stderr)
        log_path = Path(__file__).resolve().parent.parent / "references" / "gate-c-issues.json"
        existing = json.loads(log_path.read_text()) if log_path.exists() else []
        for iss in vi:
            existing.append({"date": date_str, **iss, "auto_fixed": False})
        log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
        print("[daily_report] Gate C failed. Fix issues and retry.", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 3: gate-c-issues.json 초기 파일 생성**

```bash
echo '[]' > shared/life-coach/references/gate-c-issues.json
```

- [ ] **Step 4: 테스트**

```bash
# 먼저 JSON 데이터가 /tmp에 있는지 확인
python3 shared/life-coach/scripts/daily_coach.py --json --date 2026-03-20 2>/dev/null > /tmp/_coach_data_2026-03-20.json

# --validate 실행
python3 shared/life-coach/scripts/daily_report.py \
  --input /tmp/_coach_data_2026-03-20.json --coaching /tmp/coaching_2026-03-20.md --validate
# Expected: exit 1 with issue list (건강 데이터 이미 삭제했지만 eval-leak은 남아있을 수 있음)
# 또는: exit 0 (모든 이슈 해결됨)
```

- [ ] **Step 5: 커밋**

```bash
git add shared/life-coach/scripts/daily_report.py shared/life-coach/references/gate-c-issues.json
git commit -m "feat: daily_report.py --validate (Gate C 리포트 프리뷰 검증)"
```

---

### Task 4: SKILL.md 프로세스 업데이트

**Files:**
- Modify: `cc/work-digest/SKILL.md` — Step 2 뒤에 Gate A, Step 5 뒤에 Gate B-1/B-2 삽입
- Modify: `shared/life-coach/SKILL.md` — Phase 3에 Gate C + 자가개선 루프 추가
- Modify: `shared/life-coach/references/coaching-prompts.md` — 태스크 중복 방지 지침

- [ ] **Step 1: work-digest SKILL.md — Step 2와 Step 3 사이에 Gate A 삽입**

`### Step 3: Segment 추출` 직전에:
```markdown
### Gate A: 요약 품질 검증

Step 2 완료 후, Step 3 진입 전에 실행.

1. `unsummarized --date <DATE>` 재실행 → 0건이어야 통과
2. `-claude` 레포 세션은 tag="eval", summary="자동 스킬 eval 세션"으로 일괄 처리 (LLM 요약 불필요)
3. eval 세션 시간대와 겹치는 건강 기록(health_exercises, health_symptoms, health_meals) 확인 → 있으면 삭제
4. 미요약 잔존 시 해당 세션 요약 후 재확인
```

- [ ] **Step 2: work-digest SKILL.md — Step 5 뒤에 Gate B-1, B-2 삽입**

`### Step 5: 저장 + 검증` 뒤에:
```markdown
### Gate B-1: 구조 검증

```bash
python3 {baseDir}/scripts/validate_topics.py --fix --date <DATE>
```

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
```

- [ ] **Step 3: life-coach SKILL.md — Phase 3에 Gate C + 자가개선 추가**

Phase 3 섹션 끝에:
```markdown
4. **Gate C: 리포트 프리뷰 검증** — `daily_report.py --validate` 또는 LLM이 직접 `validate_report()` 호출
   - 통과하면 `open`
   - 실패하면:
     - 데이터 문제 → 데이터 수정 후 리포트 재생성
     - 코칭 문제 (가짜 데이터 참조 등) → 코칭 재생성 후 리포트 재생성
   - 이슈를 `references/gate-c-issues.json`에 기록
   - 같은 type이 2일 이상 반복 → 스크립트 업데이트 제안 (사용자 승인 후 적용)
```

- [ ] **Step 4: coaching-prompts.md — 태스크 중복 방지 지침**

`### 🎯 내일 할 일` 섹션의 지침 목록 끝에:
```markdown
- 기존 pending 태스크와 같은 주제면 새로 만들지 말고 기존 것 참조. `save-task`가 앞 3단어 매칭으로 자동 중복 방지.
```

- [ ] **Step 5: 커밋**

```bash
git add cc/work-digest/SKILL.md shared/life-coach/SKILL.md shared/life-coach/references/coaching-prompts.md
git commit -m "docs: SKILL.md에 Gate A/B-1/B-2/C + 자가개선 루프 프로세스 추가"
```

---

### Task 5: 통합 테스트 — 3/20 리포트 재생성

이 태스크는 LLM이 직접 수행하는 통합 테스트. 스크립트 실행 + LLM 판단 혼합.

- [ ] **Step 1: Gate B-1 실행**

```bash
python3 cc/work-digest/scripts/validate_topics.py --fix --date 2026-03-20
# Expected: exit 0, "✓ all checks passed"
```

- [ ] **Step 2: Gate B-2 — LLM이 JSON 데이터 검증**

```bash
python3 shared/life-coach/scripts/daily_coach.py --json --date 2026-03-20 2>/dev/null > /tmp/_coach_data_2026-03-20.json
```
JSON의 topics를 읽고 Gate B-2 체크 수행. 이슈 발견 시 토픽 수정 후 Step 1부터 재실행.

- [ ] **Step 3: 코칭 재생성**

가짜 건강 데이터가 삭제되었으므로 코칭을 재작성. `coaching-prompts.md` 프레임 적용.
건강 데이터 없는 상태에서 건강 섹션: "건강 기록 없음" 또는 생략.
`/tmp/coaching_2026-03-20.md`에 저장.

- [ ] **Step 4: Gate C 실행**

```bash
python3 shared/life-coach/scripts/daily_report.py \
  --input /tmp/_coach_data_2026-03-20.json \
  --coaching /tmp/coaching_2026-03-20.md \
  --validate
# Expected: exit 0 (모든 Gate C 이슈 해결)
# 실패 시: 이슈 확인 → 데이터/코칭 수정 → 재실행
```

- [ ] **Step 5: 리포트 열기 + 최종 확인**

```bash
open /tmp/daily_report_2026-03-20.html
```

검증:
- 레포명: dy-minions-squad, daye-agent-toolkit, cube-admin, cube-agent-toolkit만 표시
- eval 세션: 없음
- 건강 섹션: 가짜 데이터 없음
- 태스크: 중복 없음

- [ ] **Step 6: 커밋**

```bash
git add shared/life-coach/references/gate-c-issues.json
git commit -m "chore: 3/20 리포트 Gate C 통과 확인"
```
