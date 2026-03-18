#!/usr/bin/env python3
"""하루치 모든 세션의 segments를 추출.

Usage:
    python3 extract_day.py                    # 오늘
    python3 extract_day.py --date 2026-03-16  # 특정 날짜

Output: 세션별 merged segments (JSON stdout)
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_session import extract

_MCP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "shared" / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import get_conn

KST = timezone(timedelta(hours=9))
MERGE_GAP_MIN = 15  # 15분 이하 gap만 병합
MIN_SEGMENT_MIN = 3  # 3분 이하 segment는 인접에 흡수


def merge_segments(segments):
    """연속 segment 중 gap ≤ MERGE_GAP_MIN인 것만 병합."""
    if not segments:
        return []
    merged = [dict(segments[0])]
    for s in segments[1:]:
        prev = merged[-1]
        ph, pm = map(int, prev["end"].split(":"))
        sh, sm = map(int, s["start"].split(":"))
        gap = (sh * 60 + sm) - (ph * 60 + pm)
        if gap <= MERGE_GAP_MIN:
            merged[-1]["end"] = s["end"]
            merged[-1]["duration_min"] += s["duration_min"]
            merged[-1]["messages"] = merged[-1]["messages"] + s["messages"]
            merged[-1]["file_edits"] = merged[-1]["file_edits"] + s["file_edits"]
        else:
            merged.append(dict(s))
    # 3분 이하 segment → 인접에 흡수
    final = []
    for seg in merged:
        if seg["duration_min"] <= MIN_SEGMENT_MIN and final:
            final[-1]["end"] = seg["end"]
            final[-1]["duration_min"] += seg["duration_min"]
            final[-1]["messages"] = final[-1]["messages"] + seg["messages"]
            final[-1]["file_edits"] = final[-1]["file_edits"] + seg["file_edits"]
        else:
            final.append(seg)
    return final


def find_transcripts(date_str: str) -> list[dict]:
    """해당 날짜의 세션 목록 + transcript 경로 수집."""
    projects_dir = Path.home() / ".claude" / "projects"

    # DB에서 세션 목록
    conn = get_conn()
    rows = conn.execute(
        "SELECT session_id, repo, start_at, end_at, duration_min FROM sessions WHERE date = ? ORDER BY start_at",
        (date_str,),
    ).fetchall()
    conn.close()

    seen_sids = set()
    results = []

    for r in rows:
        sid = r["session_id"]
        seen_sids.add(sid)
        transcript = _find_transcript(projects_dir, sid)
        results.append({
            "session_id": sid,
            "repo": r["repo"],
            "transcript": transcript,
        })

    # DB에 없는 열린 세션 — .jsonl 직접 탐색
    home_prefix = str(Path.home()).replace("/", "-").lstrip("-")
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob("*.jsonl"):
            sid = jsonl.stem
            if sid in seen_sids:
                continue
            try:
                stat = jsonl.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime, KST)
                if mtime.strftime("%Y-%m-%d") != date_str or stat.st_size < 10000:
                    continue
            except OSError:
                continue
            # project hash에서 repo 추출
            ph = project_dir.name
            user_prefix = f"-{home_prefix}-"
            if ph.startswith(user_prefix):
                remainder = ph[len(user_prefix):]
                repo = remainder.replace("git-workplace-", "") if "git-workplace-" in remainder else remainder
            else:
                repo = ph
            seen_sids.add(sid)
            results.append({
                "session_id": sid,
                "repo": repo,
                "transcript": str(jsonl),
            })

    return results


def _find_transcript(projects_dir: Path, session_id: str) -> str | None:
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return str(candidate)
    return None


def _run_scanner():
    """열린 세션을 DB에 반영 — 리포트 전 데이터 신선도 보장."""
    scanner = Path(__file__).resolve().parent / "active_session_scanner.py"
    if scanner.exists():
        import subprocess
        subprocess.run([sys.executable, str(scanner)],
                       capture_output=True, timeout=30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--no-scan", action="store_true", help="scanner 생략")
    args = ap.parse_args()

    if not args.no_scan:
        _run_scanner()

    sessions = find_transcripts(args.date)
    output = []

    for s in sessions:
        if not s["transcript"]:
            continue
        data = extract(s["transcript"], args.date)
        merged = merge_segments(data.get("segments", []))
        if not merged:
            continue

        # messages를 요약용으로 정리
        for seg in merged:
            seg["message_texts"] = [m["text"] for m in seg["messages"][:20]]
            seg["file_names"] = list(dict.fromkeys(f["file"] for f in seg["file_edits"]))[:15]
            del seg["messages"]
            del seg["file_edits"]

        output.append({
            "session_id": s["session_id"],
            "repo": (s["repo"] or "unknown").split("/")[-1],
            "segments": merged,
        })

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()
    print(f"[extract_day] {args.date}: {len(output)} sessions, {sum(len(s['segments']) for s in output)} segments", file=sys.stderr)


if __name__ == "__main__":
    main()
