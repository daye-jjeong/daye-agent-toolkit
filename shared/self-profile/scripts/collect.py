#!/usr/bin/env python3
"""Self-Profile data collector — DB → JSON snapshot."""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def _collect_from_conn(conn, start: str, end: str, project_roots: list[str]) -> dict:
    """Collect profile data from a DB connection. Testable entry point."""
    raise NotImplementedError


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
    snapshot_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
