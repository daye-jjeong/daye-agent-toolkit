# Coaching Quality v2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코칭 시스템에 미완료 작업 감지, mistake 반복 분류, 과거 태그 보정, 주간 점검 4종을 추가하여 "다음 할 일 추천 + 반복 실수 교정"을 가능하게 한다.

**Architecture:** `daily_coach.py`에 pending_work 데이터 추가 (git worktree + 미머지 branch), `db.py`에 mistake 트렌드 쿼리 추가, `mistake_categories.json`으로 키워드 기반 분류 + 주간 LLM 교정, `weekly_coach.py`에 점검 4종 데이터 추가, `backfill_tags.py`로 과거 "기타" 태그 일괄 보정.

**Tech Stack:** Python 3 (stdlib only), SQLite, JSON

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `shared/life-coach/references/mistake-categories.json` | mistake 키워드 카테고리 매핑 |
| Create | `shared/life-dashboard-mcp/backfill_tags.py` | 과거 "기타" 태그 일괄 보정 one-off 스크립트 |
| Modify | `shared/life-dashboard-mcp/db.py` | `get_mistake_trends()` 함수 추가 |
| Modify | `shared/life-coach/scripts/_helpers.py` | `get_pending_work()` 함수 추가 |
| Modify | `shared/life-coach/scripts/daily_coach.py` | `pending_work` + `mistake_trends` 데이터 추가 |
| Modify | `shared/life-coach/scripts/weekly_coach.py` | 주간 점검 4종 데이터 추가 |
| Modify | `shared/life-coach/SKILL.md` | 주간 코칭에 점검 단계 + mistake 카테고리 교정 절차 추가 |

---

## Chunk 1: Mistake 분류 인프라

### Task 1: mistake_categories.json 생성

**Files:**
- Create: `shared/life-coach/references/mistake-categories.json`

- [x] **Step 1: 카테고리 파일 작성**

behavioral_signals 테이블의 `signal_type='mistake'` content를 분류하는 키워드 매핑.
LLM이 주간 코칭 때 실제 데이터를 보고 교정한다.

```json
{
  "_meta": {
    "description": "mistake 키워드→카테고리 매핑. 주간 코칭에서 LLM이 교정.",
    "last_reviewed": "2026-03-14"
  },
  "categories": {
    "scope-creep": {
      "label": "범위 초과",
      "keywords": ["scope", "범위", "추가 작업", "예상보다", "더 많이"]
    },
    "wrong-assumption": {
      "label": "잘못된 가정",
      "keywords": ["가정", "assumption", "알고 보니", "착각", "오해"]
    },
    "tool-misuse": {
      "label": "도구 오용",
      "keywords": ["tool", "도구", "명령어", "CLI", "잘못된 사용"]
    },
    "missing-test": {
      "label": "테스트 누락",
      "keywords": ["test", "테스트", "검증", "확인 안"]
    },
    "config-error": {
      "label": "설정 오류",
      "keywords": ["config", "설정", "환경", "경로", "path"]
    },
    "communication": {
      "label": "소통 미스",
      "keywords": ["소통", "전달", "이해", "요구사항"]
    },
    "repeat-work": {
      "label": "반복 작업",
      "keywords": ["다시", "반복", "중복", "또"]
    }
  }
}
```

- [x] **Step 2: Commit**

```bash
git add shared/life-coach/references/mistake-categories.json
git commit -m "feat: add mistake_categories.json for behavioral signal classification"
```

---

### Task 2: db.py에 get_mistake_trends() 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/db.py` (line 154 뒤에 추가)

- [x] **Step 1: get_mistake_trends() 함수 추가**

`behavioral_signals`에서 mistake 타입을 추출하고, `mistake_categories.json`의 키워드로 카테고리 분류.

```python
def get_mistake_trends(conn: sqlite3.Connection, date_str: str, days: int = 14) -> dict:
    """최근 N일간 mistake 신호를 카테고리별로 집계.

    Returns: {
        "by_category": [{"category": str, "label": str, "count": int, "examples": [str]}],
        "uncategorized": [{"content": str, "count": int}],
        "total": int,
    }
    """
    since = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT content, COUNT(*) as cnt
        FROM behavioral_signals
        WHERE date >= ? AND signal_type = 'mistake'
        GROUP BY content ORDER BY cnt DESC
    """, (since,)).fetchall()

    # Load categories
    cat_path = Path(__file__).resolve().parent.parent / "life-coach" / "references" / "mistake-categories.json"
    categories: dict = {}
    if cat_path.exists():
        import json as _json
        categories = _json.loads(cat_path.read_text()).get("categories", {})

    by_cat: dict[str, list[tuple[str, int]]] = {}
    uncategorized = []
    total = 0

    for r in rows:
        content, cnt = r["content"], r["cnt"]
        total += cnt
        content_lower = content.lower()
        matched = False
        for cat_key, cat_def in categories.items():
            if any(kw.lower() in content_lower for kw in cat_def.get("keywords", [])):
                by_cat.setdefault(cat_key, []).append((content, cnt))
                matched = True
                break
        if not matched:
            uncategorized.append({"content": content, "count": cnt})

    result_cats = []
    for cat_key, items in sorted(by_cat.items(), key=lambda x: sum(c for _, c in x[1]), reverse=True):
        cat_def = categories[cat_key]
        result_cats.append({
            "category": cat_key,
            "label": cat_def.get("label", cat_key),
            "count": sum(c for _, c in items),
            "examples": [c for c, _ in items[:3]],
        })

    return {"by_category": result_cats, "uncategorized": uncategorized, "total": total}
```

- [x] **Step 2: db.py 상단 import 확인**

`json`과 `Path`는 이미 import되어 있으므로 추가 불필요.

- [x] **Step 3: 함수 동작 검증**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/coaching-quality-v2
python3 -c "
import sys; sys.path.insert(0, 'shared/life-dashboard-mcp')
from db import get_conn, get_mistake_trends
conn = get_conn()
result = get_mistake_trends(conn, '2026-03-14', days=14)
print('total:', result['total'])
print('categories:', len(result['by_category']))
print('uncategorized:', len(result['uncategorized']))
for c in result['by_category'][:3]:
    print(f'  {c[\"label\"]}: {c[\"count\"]}건 — {c[\"examples\"][:2]}')
conn.close()
"
```

Expected: total >= 0, 에러 없이 실행.

- [x] **Step 4: Commit**

```bash
git add shared/life-dashboard-mcp/db.py
git commit -m "feat: add get_mistake_trends() — categorize mistake signals"
```

---

## Chunk 2: 일일 코칭 데이터 보강

### Task 3: _helpers.py에 get_pending_work() 추가 + daily_coach.py 연결

**Files:**
- Modify: `shared/life-coach/scripts/_helpers.py`
- Modify: `shared/life-coach/scripts/daily_coach.py`

- [x] **Step 1: _helpers.py에 get_pending_work() 추가**

`_helpers.py` 파일 끝에 추가. `subprocess`는 모듈 상단에 import.

```python
import subprocess

def get_pending_work() -> list[dict]:
    """활성 git worktree에서 미완료 작업 감지."""
    pending = []
    home = Path.home()
    git_dirs = [home / "git_workplace"]
    for git_dir in git_dirs:
        if not git_dir.exists():
            continue
        for repo_dir in git_dir.iterdir():
            if not (repo_dir / ".git").exists():
                continue
            try:
                result = subprocess.run(
                    ["git", "worktree", "list", "--porcelain"],
                    capture_output=True, text=True, cwd=str(repo_dir),
                    timeout=5,
                )
                if result.returncode != 0:
                    continue
                worktrees = []
                current = {}
                for line in result.stdout.strip().split("\n"):
                    if line.startswith("worktree "):
                        if current and current.get("branch"):
                            worktrees.append(current)
                        current = {"path": line[9:], "repo": repo_dir.name}
                    elif line.startswith("branch "):
                        branch = line[7:].split("/")[-1]
                        if branch not in ("main", "master"):
                            current["branch"] = branch
                if current and current.get("branch"):
                    worktrees.append(current)
                pending.extend(worktrees)
            except Exception:
                continue
    return pending
```

- [x] **Step 2: daily_coach.py import 수정**

`daily_coach.py:18` — db import에 `get_mistake_trends` 추가.
`daily_coach.py:28` — _helpers import에 `get_pending_work` 추가.

```python
from db import get_conn, get_coach_state, set_coach_state, get_repeated_signals, \
    query_exercises, query_symptoms, query_meals, query_check_ins, query_expiring_pantry, \
    get_mistake_trends

from _helpers import find_project_memory, group_sessions_by_repo_branch, has_meaningful_branches, get_pending_work
```

- [x] **Step 3: get_today_data() return에 pending_work, mistake_trends 추가**

`daily_coach.py` — `get_today_data()` 함수의 return 직전에 두 필드 수집 + return dict에 추가.

```python
    # pending work (worktrees)
    try:
        pending = get_pending_work()
    except Exception:
        pending = []

    # mistake trends (최근 14일)
    try:
        mistake_trends = get_mistake_trends(conn, date_str, days=14)
    except Exception:
        mistake_trends = {"by_category": [], "uncategorized": [], "total": 0}

    return {
        # ... 기존 필드 유지 ...
        "pending_work": pending,
        "mistake_trends": mistake_trends,
    }
```

- [x] **Step 4: 동작 검증**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/coaching-quality-v2
python3 shared/life-coach/scripts/daily_coach.py --json --date 2026-03-14 | python3 -c "
import json, sys
data = json.load(sys.stdin)
print('pending_work:', len(data.get('pending_work', [])))
for p in data.get('pending_work', [])[:3]:
    print(f'  {p[\"repo\"]} / {p[\"branch\"]}')
mt = data.get('mistake_trends', {})
print(f'mistake_trends: total={mt.get(\"total\", 0)}, categories={len(mt.get(\"by_category\", []))}')
"
```

Expected: pending_work에 활성 worktree 목록, mistake_trends에 집계 데이터.

- [x] **Step 5: Commit**

```bash
git add shared/life-coach/scripts/_helpers.py shared/life-coach/scripts/daily_coach.py
git commit -m "feat: add pending_work + mistake_trends to daily coaching data"
```

---

## Chunk 3: 과거 태그 보정

### Task 4: backfill_tags.py 생성

**Files:**
- Create: `shared/life-dashboard-mcp/backfill_tags.py`

- [x] **Step 1: 스크립트 작성**

activities 테이블에서 `tag='기타'`인 행을 찾아 `_sync_common.auto_tag`으로 재분류.

```python
#!/usr/bin/env python3
"""One-off: backfill '기타' tags using auto_tag.

Usage:
    python3 backfill_tags.py              # dry-run (변경 사항만 출력)
    python3 backfill_tags.py --apply      # 실제 DB 업데이트
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_conn
from _sync_common import auto_tag


def main():
    parser = argparse.ArgumentParser(description="Backfill '기타' tags")
    parser.add_argument("--apply", action="store_true", help="Actually update DB")
    args = parser.parse_args()

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, source, session_id, repo, tag, summary, raw_json "
            "FROM activities WHERE tag = '기타' OR tag = '' OR tag IS NULL"
        ).fetchall()
        print(f"Found {len(rows)} untagged/기타 activities", file=sys.stderr)

        updated = 0
        for r in rows:
            raw = json.loads(r["raw_json"] or "{}")
            summary = r["summary"] or ""
            topic = raw.get("topic", "")
            commands = " ".join(raw.get("commands", [])[:5])
            new_tag = auto_tag(summary, topic, commands)
            if new_tag != "기타":
                print(f"  [{r['source']}] {r['session_id'][:8]}.. "
                      f"{r['repo']}: {r['tag']!r} → {new_tag!r}  ({summary[:60]})")
                if args.apply:
                    conn.execute(
                        "UPDATE activities SET tag = ? WHERE id = ?",
                        (new_tag, r["id"]),
                    )
                updated += 1

        if args.apply and updated > 0:
            conn.commit()
            # daily_stats도 재계산
            dates = conn.execute(
                "SELECT DISTINCT substr(start_at, 1, 10) as d FROM activities"
            ).fetchall()
            from db import update_daily_stats
            for d in dates:
                update_daily_stats(conn, d["d"])
            conn.commit()

        print(f"\n{'Applied' if args.apply else 'Would update'}: {updated}/{len(rows)} activities",
              file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [x] **Step 2: dry-run 검증**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/coaching-quality-v2
python3 shared/life-dashboard-mcp/backfill_tags.py
```

Expected: 변경될 태그 목록 출력, DB 변경 없음.

- [x] **Step 3: --apply로 실행**

```bash
python3 shared/life-dashboard-mcp/backfill_tags.py --apply
```

Expected: 업데이트된 건수 출력.

- [x] **Step 4: Commit**

```bash
git add shared/life-dashboard-mcp/backfill_tags.py
git commit -m "feat: add backfill_tags.py — reclassify '기타' activities"
```

---

## Chunk 4: 주간 점검 + SKILL.md 업데이트

### Task 5: weekly_coach.py에 주간 점검 4종 데이터 추가

**Files:**
- Modify: `shared/life-coach/scripts/weekly_coach.py`

- [x] **Step 1: import에 get_mistake_trends 추가**

`weekly_coach.py:19` — db import에 `get_mistake_trends` 추가.

```python
from db import get_conn, get_coach_state, query_exercises, query_symptoms, query_meals, query_check_ins, get_repeated_signals, get_mistake_trends
```

- [x] **Step 2: _helpers import에 get_pending_work 추가**

`weekly_coach.py:27` — 기존 `from _helpers import find_project_memory` 라인에 `get_pending_work` 추가.

```python
from _helpers import find_project_memory, get_pending_work
```

- [x] **Step 3: get_week_data()에 주간 점검 데이터 수집 추가**

`weekly_coach.py` — `get_week_data()` 함수의 return 직전에 4종 점검 데이터 추가.

```python
    # ── 주간 점검 4종 ──
    review_items = {}

    # 1) "기타" 태그 세션 수
    try:
        untagged = conn.execute(
            "SELECT COUNT(*) as cnt FROM activities "
            "WHERE start_at >= ? AND start_at < ? AND (tag = '기타' OR tag = '' OR tag IS NULL)",
            (mon, next_sun),
        ).fetchone()
        review_items["untagged_sessions"] = untagged["cnt"]
    except Exception:
        review_items["untagged_sessions"] = 0

    # 2) 미분류 mistake 수
    try:
        mt = get_mistake_trends(conn, sun, days=7)
        review_items["uncategorized_mistakes"] = len(mt.get("uncategorized", []))
        review_items["mistake_trends"] = mt
    except Exception:
        review_items["uncategorized_mistakes"] = 0
        review_items["mistake_trends"] = {"by_category": [], "uncategorized": [], "total": 0}

    # 3) empty summary 세션 수
    try:
        empty_sum = conn.execute(
            "SELECT COUNT(*) as cnt FROM activities "
            "WHERE start_at >= ? AND start_at < ? AND (summary = '' OR summary IS NULL)",
            (mon, next_sun),
        ).fetchone()
        review_items["empty_summaries"] = empty_sum["cnt"]
    except Exception:
        review_items["empty_summaries"] = 0

    # 4) stale worktrees (_helpers.get_pending_work 재사용)
    try:
        review_items["stale_worktrees"] = get_pending_work()
    except Exception:
        review_items["stale_worktrees"] = []
```

`return` dict에 `"review_items": review_items` 추가.

- [x] **Step 3: _build_review_section() 추가 + build_template_report에 연결**

텔레그램 템플릿 리포트에 점검 결과 요약 섹션 추가.

```python
def _build_review_section(data: dict) -> str | None:
    """주간 점검 결과."""
    ri = data.get("review_items", {})
    if not ri:
        return None
    lines = []
    untagged = ri.get("untagged_sessions", 0)
    if untagged > 0:
        lines.append(f"  🏷 미분류 태그: {untagged}세션")
    uncategorized = ri.get("uncategorized_mistakes", 0)
    if uncategorized > 0:
        lines.append(f"  ⚠️ 미분류 mistake: {uncategorized}건")
    empty = ri.get("empty_summaries", 0)
    if empty > 0:
        lines.append(f"  📝 빈 summary: {empty}세션")
    stale = ri.get("stale_worktrees", [])
    if stale:
        repos = set(w.get("repo", "") for w in stale)
        lines.append(f"  🌿 활성 worktree: {len(stale)}개 ({', '.join(sorted(repos)[:5])})")
    if not lines:
        return None
    return "🔍 주간 점검:\n" + "\n".join(lines)
```

`build_template_report()` 내 reflect 섹션 앞에 review 섹션 삽입:

```python
    review = _build_review_section(data)
    if review:
        sections.append(review)
```

- [x] **Step 4: 동작 검증**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/coaching-quality-v2
python3 shared/life-coach/scripts/weekly_coach.py --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
ri = data.get('review_items', {})
print('untagged:', ri.get('untagged_sessions'))
print('uncategorized:', ri.get('uncategorized_mistakes'))
print('empty_summaries:', ri.get('empty_summaries'))
print('stale_worktrees:', len(ri.get('stale_worktrees', [])))
"
```

Expected: 4종 점검 데이터 출력.

- [x] **Step 5: Commit**

```bash
git add shared/life-coach/scripts/weekly_coach.py
git commit -m "feat: add weekly review data — untagged, uncategorized, empty, stale"
```

---

### Task 6: SKILL.md에 주간 점검 절차 + mistake 카테고리 교정 추가

**Files:**
- Modify: `shared/life-coach/SKILL.md`

- [x] **Step 1: 주간 코칭 구성에 점검 단계 추가**

`SKILL.md:143-151` — "주간 코칭 구성" 섹션에 8번 항목 추가.

기존:
```
7. **다음 주 생각해볼 것** — 패턴 기반 reflect 질문
```

변경:
```
7. **다음 주 생각해볼 것** — 패턴 기반 reflect 질문
8. **주간 점검** — review_items 데이터 기반 4종 점검 + 교정

### 주간 점검 절차

주간 코칭에서 `review_items` 데이터를 확인하고 다음을 교정한다:

1. **미분류 태그 (untagged_sessions)**: "기타"로 분류된 세션의 raw_json을 보고 올바른 태그로 수정. 반복되는 패턴이면 `_sync_common.py`의 TAG_KEYWORDS에 키워드 추가.
2. **미분류 mistake (uncategorized_mistakes)**: 분류되지 않은 mistake 신호를 확인하고 `references/mistake-categories.json`에 새 키워드 추가.
3. **빈 summary (empty_summaries)**: summary가 비어있는 세션을 확인. sync 로직 개선이 필요한지 판단.
4. **stale worktree (stale_worktrees)**: 오래된 worktree가 있으면 머지 또는 정리 여부를 사용자에게 제안.
```

- [x] **Step 2: version 업데이트**

`SKILL.md:10` — version `0.6.0` → `0.7.0`.

- [x] **Step 3: Commit**

```bash
git add shared/life-coach/SKILL.md
git commit -m "docs: add weekly review procedure + mistake category maintenance to SKILL.md"
```

---

## Summary

| Task | 파일 | 설명 |
|------|------|------|
| 1 | `mistake-categories.json` | mistake 키워드 카테고리 매핑 |
| 2 | `db.py` | `get_mistake_trends()` 함수 |
| 3 | `daily_coach.py` | `pending_work` + `mistake_trends` 데이터 |
| 4 | `backfill_tags.py` | 과거 "기타" 태그 일괄 보정 |
| 5 | `weekly_coach.py` | 주간 점검 4종 데이터 + 템플릿 |
| 6 | `SKILL.md` | 주간 점검 절차 문서화 |

실행 순서: Task 1 → 2 → 3 → 4 (독립) → 5 → 6
Task 4는 Task 1과 2 완료 후 언제든 실행 가능 (one-off).
