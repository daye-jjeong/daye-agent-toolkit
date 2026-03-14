#!/usr/bin/env python3
"""Self-Profile data collector — DB → JSON snapshot."""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SIGNAL_TYPES = ("decision", "mistake", "pattern")
_TOP_SIGNALS_LIMIT = 20
_CORRECTION_RE = re.compile(r"correction-(\d{8})-(\d{4})-(.+)\.md$")


def _add_dual(bucket: dict, key: str, duration: int):
    """Add count + total_min to a bucket entry."""
    if key not in bucket:
        bucket[key] = {"count": 0, "total_min": 0}
    bucket[key]["count"] += 1
    bucket[key]["total_min"] += duration


def _normalize_tag(tag: str | None) -> str:
    """NULL/빈 tag → '기타'."""
    if not tag or not tag.strip():
        return "기타"
    return tag


def _query_activities(conn, start: str, next_end: str) -> list:
    """activities 테이블 1회 쿼리. sessions + daily_trend 양쪽에서 사용."""
    return conn.execute("""
        SELECT source, repo, tag, start_at, duration_min
        FROM activities
        WHERE start_at >= ? AND start_at < ?
        ORDER BY start_at
    """, (start, next_end)).fetchall()


def _build_sessions(rows) -> dict:
    """Build session breakdown from pre-fetched activity rows."""
    total = len(rows)
    total_min = sum(r["duration_min"] or 0 for r in rows)
    by_weekday: dict = {}
    by_hour: dict = {}
    by_tag: dict = {}
    by_repo: dict = {}
    by_source: dict = {}

    for r in rows:
        dur = r["duration_min"] or 0
        tag = _normalize_tag(r["tag"])
        source = r["source"] or "unknown"
        repo = r["repo"] or "unknown"

        start_dt = r["start_at"][:10] if r["start_at"] else None
        if start_dt:
            wd = datetime.strptime(start_dt, "%Y-%m-%d").weekday()
            _add_dual(by_weekday, WEEKDAY_NAMES[wd], dur)

        hour_str = r["start_at"][11:13] if r["start_at"] and len(r["start_at"]) > 12 else None
        if hour_str:
            _add_dual(by_hour, hour_str, dur)

        _add_dual(by_tag, tag, dur)
        _add_dual(by_repo, repo, dur)
        _add_dual(by_source, source, dur)

    return {
        "total": total,
        "avg_duration_min": round(total_min / total, 1) if total else 0,
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "by_tag": by_tag,
        "by_repo": by_repo,
        "by_source": by_source,
    }


def _build_daily_trend(rows, start_dt: datetime, end_dt: datetime) -> list[dict]:
    """Build daily trend with 0-fill from pre-fetched activity rows."""
    by_date: dict[str, dict] = {}
    for r in rows:
        date = r["start_at"][:10] if r["start_at"] else None
        if not date:
            continue
        if date not in by_date:
            by_date[date] = {"date": date, "sessions": 0, "total_min": 0, "tags": {}}
        entry = by_date[date]
        entry["sessions"] += 1
        entry["total_min"] += r["duration_min"] or 0
        tag = _normalize_tag(r["tag"])
        entry["tags"][tag] = entry["tags"].get(tag, 0) + 1

    # 0-fill + finalize hours
    trend = []
    current = start_dt
    while current <= end_dt:
        ds = current.strftime("%Y-%m-%d")
        if ds in by_date:
            e = by_date[ds]
            trend.append({
                "date": ds,
                "sessions": e["sessions"],
                "hours": round(e["total_min"] / 60, 1),
                "tags": e["tags"],
            })
        else:
            trend.append({"date": ds, "sessions": 0, "hours": 0.0, "tags": {}})
        current += timedelta(days=1)

    return trend


def _collect_behavioral_signals(conn, start: str, end: str) -> dict:
    """Query behavioral_signals and build summary."""
    rows = conn.execute("""
        SELECT signal_type, content, date, repo
        FROM behavioral_signals
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    """, (start, end)).fetchall()

    by_type: dict[str, list[dict]] = {st: [] for st in SIGNAL_TYPES}
    content_counts: dict[str, dict] = {}

    for r in rows:
        entry = {"content": r["content"], "date": r["date"], "repo": r["repo"] or ""}
        st = r["signal_type"]
        if st in by_type:
            by_type[st].append(entry)

        key = r["content"]
        if key not in content_counts:
            content_counts[key] = {"content": key, "count": 0, "type": st}
        content_counts[key]["count"] += 1

    repeat_signals = sorted(
        [v for v in content_counts.values() if v["count"] >= 2],
        key=lambda x: x["count"], reverse=True
    )

    return {
        "summary": {f"{st}s_count": len(by_type[st]) for st in SIGNAL_TYPES},
        "top_decisions": by_type["decision"][:_TOP_SIGNALS_LIMIT],
        "top_mistakes": by_type["mistake"][:_TOP_SIGNALS_LIMIT],
        "top_patterns": by_type["pattern"][:_TOP_SIGNALS_LIMIT],
        "repeat_signals": repeat_signals[:_TOP_SIGNALS_LIMIT],
    }


def _collect_corrections(project_roots: list[str]) -> list[dict]:
    """Scan correction-*.md files from project roots."""
    corrections = []
    for root in project_roots:
        rules_dir = Path(root) / ".claude" / "rules"
        if not rules_dir.is_dir():
            continue
        for f in rules_dir.iterdir():
            m = _CORRECTION_RE.match(f.name)
            if not m:
                continue
            date_str = m.group(1)
            created = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            try:
                preview = f.read_text(encoding="utf-8")[:200].strip()
            except Exception:
                preview = ""
            corrections.append({
                "filename": f.name,
                "created": created,
                "project": Path(root).name,
                "content_preview": preview,
            })
    corrections.sort(key=lambda x: x["created"], reverse=True)
    return corrections


def _collect_from_conn(conn, start: str, end: str, project_roots: list[str]) -> dict:
    """Collect profile data from a DB connection. Testable entry point."""
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    days = (end_dt - start_dt).days + 1
    next_end = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    # 1회 쿼리로 sessions + daily_trend 양쪽 커버
    activity_rows = _query_activities(conn, start, next_end)

    return {
        "period": {"start": start, "end": end, "days": days},
        "sessions": _build_sessions(activity_rows),
        "behavioral_signals": _collect_behavioral_signals(conn, start, end),
        "corrections": _collect_corrections(project_roots),
        "daily_trend": _build_daily_trend(activity_rows, start_dt, end_dt),
    }


def collect(days: int = 30, since: str | None = None,
            project_roots: list[str] | None = None) -> dict:
    """Collect profile data and return as dict."""
    _MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
    sys.path.insert(0, str(_MCP_DIR))
    from db import get_conn

    conn = get_conn()
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        if since:
            start = since
        else:
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if project_roots is None:
            wp = Path.home() / "git_workplace"
            project_roots = [str(p) for p in wp.iterdir() if p.is_dir()] if wp.exists() else []

        return _collect_from_conn(conn, start, end, project_roots)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Self-profile data collector")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--project-roots", type=str, default=None,
                        help="Comma-separated project root paths")
    args = parser.parse_args()

    roots = args.project_roots.split(",") if args.project_roots else None
    result = collect(days=args.days, since=args.since, project_roots=roots)

    # Save snapshot
    snapshot_dir = Path.home() / "life-dashboard"
    snapshot_path = snapshot_dir / "profile-snapshot.json"
    prev_path = snapshot_dir / "profile-snapshot.prev.json"

    if snapshot_path.exists():
        prev_path.write_text(snapshot_path.read_text(), encoding="utf-8")

    output = json.dumps(result, ensure_ascii=False, indent=2)
    snapshot_path.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
