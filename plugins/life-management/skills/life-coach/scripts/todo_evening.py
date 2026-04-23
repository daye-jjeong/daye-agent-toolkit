#!/usr/bin/env python3
"""저녁 액션 — 계획 vs 실제 대조 JSON 출력.

동작:
  1) 해당 날짜 daily_checkin (morning_intent, morning_wip_ids) 조회
  2) 해당 날짜 tasks 조회. 비어있으면 work-digest Step 1-3 시도
     - Step 4는 LLM이 수행 (스크립트 아님) → needs_llm_task_generation=true 플래그
     - 실패 시 raw_sessions 폴백
  3) loose matching: repo/title keyword로 매칭
  4) stdout JSON

Usage:
    python3 todo_evening.py --date YYYY-MM-DD [--skip-digest]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO_ROOT / "mcp" / "life-dashboard"))
from db import get_conn, get_tasks, get_daily_checkin

WORK_DIGEST_DIR = REPO_ROOT / "plugins" / "dev-tools" / "skills" / "work-digest" / "scripts"
KST = ZoneInfo("Asia/Seoul")


def _slim_task(t: dict) -> dict:
    return {
        "id": t["id"],
        "tag": t["tag"],
        "summary": t["summary"],
        "repo": t.get("repo"),
        "duration_min": t.get("duration_min"),
        "status": t.get("status"),
        "follow_up": t.get("follow_up"),
        "project_name": t.get("project_name"),
    }


def _fetch_raw_sessions(conn, date: str) -> list[dict]:
    rows = conn.execute("""
        SELECT session_id, repo, tag, summary, start_at, end_at, duration_min, status
        FROM sessions
        WHERE date = ?
        ORDER BY start_at
    """, (date,)).fetchall()
    return [dict(r) for r in rows]


def _try_work_digest(date: str) -> tuple[bool, str]:
    """Step 1 (scanner) + Step 3 (extract) 시도. 결과는 DB에 쌓임.

    Step 2 (세션 요약, LLM)와 Step 4 (task 생성, LLM)는 이 스크립트가 하지 않음.
    LLM 수행은 Claude 세션의 몫.

    Returns:
        (success, message)
    """
    try:
        r = subprocess.run(
            ["python3", str(WORK_DIGEST_DIR / "active_session_scanner.py")],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return False, f"scanner failed: {r.stderr[:200]}"
        r2 = subprocess.run(
            ["python3", str(WORK_DIGEST_DIR / "extract_day.py"),
             "--date", date, "--no-scan"],
            capture_output=True, text=True, timeout=120,
        )
        if r2.returncode != 0:
            return False, f"extract_day failed: {r2.stderr[:200]}"
        return True, "ok"
    except subprocess.TimeoutExpired as e:
        return False, f"timeout: {e}"
    except FileNotFoundError as e:
        return False, f"work-digest script not found: {e}"


def _tokens(text: str) -> set[str]:
    """간단 한국어/영문 단어 토큰. 2글자 이상."""
    if not text:
        return set()
    raw = re.findall(r"[A-Za-z가-힣0-9]{2,}", text.lower())
    return set(raw)


def _match_score(wip_title: str, task_summary: str, wip_repo: str | None, task_repo: str | None) -> float:
    """loose match score 0.0 ~ 1.0."""
    score = 0.0
    if wip_repo and task_repo:
        w = wip_repo.split("/")[-1].lower()
        t = task_repo.split("/")[-1].lower()
        if w == t:
            score += 0.5
    wip_toks = _tokens(wip_title)
    task_toks = _tokens(task_summary)
    if wip_toks and task_toks:
        overlap = wip_toks & task_toks
        score += min(0.5, 0.1 * len(overlap))
    return round(min(score, 1.0), 2)


def build_evening(conn, date: str, skip_digest: bool = False) -> dict:
    # 1. 아침 체크인
    checkin = get_daily_checkin(conn, date) or {
        "morning_intent": None, "morning_wip_ids": [], "missing_wip_ids": [], "evening_reflection": None
    }

    # 2. tasks 조회
    tasks = get_tasks(conn, date)
    fallback = False
    raw_sessions: list[dict] = []
    needs_llm = False

    if not tasks and not skip_digest:
        ok, msg = _try_work_digest(date)
        if ok:
            # Step 1-3 성공. tasks 재조회 시도 (LLM Step 4 안 돌았으면 여전히 비어있음)
            tasks = get_tasks(conn, date)
            if not tasks:
                # Step 4 (LLM)가 필요하다는 flag
                needs_llm = True
                fallback = True
                raw_sessions = _fetch_raw_sessions(conn, date)
        else:
            # Step 1-3 실패 → 폴백
            fallback = True
            raw_sessions = _fetch_raw_sessions(conn, date)

    elif not tasks and skip_digest:
        fallback = True
        raw_sessions = _fetch_raw_sessions(conn, date)

    # 3. loose matching (tasks 있을 때만)
    loose_matches: list[dict] = []
    unmatched_actual: list[dict] = []

    if tasks:
        wip_ids = checkin.get("morning_wip_ids") or []
        wip_todos = []
        if wip_ids:
            placeholders = ",".join("?" * len(wip_ids))
            rows = conn.execute(f"""
                SELECT t.*, p.name as project_name
                FROM todos t LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.id IN ({placeholders})
            """, wip_ids).fetchall()
            wip_todos = [dict(r) for r in rows]

        matched_task_ids: set[int] = set()
        for w in wip_todos:
            wip_repo = None
            if w.get("project_id"):
                pr = conn.execute(
                    "SELECT repo FROM projects WHERE id = ?", (w["project_id"],)
                ).fetchone()
                if pr:
                    wip_repo = pr["repo"]
            matches = []
            for t in tasks:
                s = _match_score(w["title"], t["summary"], wip_repo, t.get("repo"))
                if s >= 0.3:
                    matches.append({**_slim_task(t), "match_score": s})
                    matched_task_ids.add(t["id"])
            loose_matches.append({
                "wip_id": w["id"],
                "wip_title": w["title"],
                "matched_tasks": sorted(matches, key=lambda x: -x["match_score"]),
            })
        unmatched_actual = [
            _slim_task(t) for t in tasks if t["id"] not in matched_task_ids
        ]

    return {
        "date": date,
        "morning_intent": checkin.get("morning_intent"),
        "morning_wip_ids": checkin.get("morning_wip_ids") or [],
        "missing_wip_ids": checkin.get("missing_wip_ids") or [],
        "actual_tasks": [_slim_task(t) for t in tasks],
        "fallback": fallback,
        "raw_sessions": raw_sessions,
        "loose_matches": loose_matches,
        "unmatched_actual": unmatched_actual,
        "needs_llm_task_generation": needs_llm,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--skip-digest", action="store_true",
                    help="work-digest 재시도 없이 현재 tasks/sessions만 사용")
    args = ap.parse_args()

    conn = get_conn()
    try:
        result = build_evening(conn, args.date, skip_digest=args.skip_digest)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
