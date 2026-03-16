#!/usr/bin/env python3
"""트랜스크립트 .jsonl에서 토픽 생성에 필요한 데이터만 추출.

Usage:
    python3 extract_session.py <jsonl_path>
    python3 extract_session.py <jsonl_path> --date 2026-03-16

Output: JSON (stdout)
    {
        "messages": [{"ts": "HH:MM", "text": "..."}, ...],
        "file_edits": [{"ts": "HH:MM", "file": "..."}, ...],
        "idle_gaps": [{"from": "HH:MM", "to": "HH:MM", "minutes": N}, ...],
        "active_minutes": N,
        "wall_minutes": N
    }
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
IDLE_THRESHOLD_SEC = 300  # 5분


def extract(jsonl_path: str, target_date: str | None = None) -> dict:
    messages = []
    file_edits = []
    all_timestamps = []

    with open(jsonl_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            ts_raw = entry.get("timestamp")
            if not ts_raw:
                continue
            try:
                dt = datetime.fromisoformat(ts_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                kst = dt.astimezone(KST)
            except (ValueError, TypeError):
                continue

            entry_date = kst.strftime("%Y-%m-%d")
            if target_date and entry_date != target_date:
                continue

            all_timestamps.append(kst)
            hhmm = kst.strftime("%H:%M")
            entry_type = entry.get("type", "")

            # user messages
            if entry_type == "user":
                msg = entry.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""
                text = ""
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()[:200]
                            break
                elif isinstance(content, str):
                    text = content.strip()[:200]
                if text:
                    messages.append({"ts": hhmm, "text": text})

            # file edits (Edit/Write tool calls)
            if entry_type == "assistant":
                msg = entry.get("message", {})
                content = msg.get("content", []) if isinstance(msg, dict) else []
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        tool = block.get("name", "")
                        if tool in ("Edit", "Write"):
                            fp = block.get("input", {}).get("file_path", "")
                            if fp:
                                file_edits.append({"ts": hhmm, "file": fp.split("/")[-1]})

    if not all_timestamps:
        return {"messages": [], "file_edits": [], "idle_gaps": [], "active_minutes": 0, "wall_minutes": 0}

    # idle gaps + active time
    sorted_ts = sorted(all_timestamps)
    idle_gaps = []
    active_sec = 0
    for i in range(1, len(sorted_ts)):
        gap = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()
        if gap > IDLE_THRESHOLD_SEC:
            idle_gaps.append({
                "from": sorted_ts[i - 1].strftime("%H:%M"),
                "to": sorted_ts[i].strftime("%H:%M"),
                "minutes": int(gap / 60),
            })
        else:
            active_sec += gap

    wall_sec = (sorted_ts[-1] - sorted_ts[0]).total_seconds()

    return {
        "messages": messages,
        "file_edits": file_edits,
        "idle_gaps": idle_gaps,
        "active_minutes": max(1, int(active_sec / 60)),
        "wall_minutes": max(1, int(wall_sec / 60)),
        "start": sorted_ts[0].strftime("%H:%M"),
        "end": sorted_ts[-1].strftime("%H:%M"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", help="Path to transcript .jsonl")
    ap.add_argument("--date", help="Filter by date (YYYY-MM-DD)")
    args = ap.parse_args()

    result = extract(args.jsonl, args.date)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
