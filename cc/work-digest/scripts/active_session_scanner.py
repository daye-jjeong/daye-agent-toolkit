#!/usr/bin/env python3
"""Active Session Scanner — find open CC sessions and record them.

열려있는 CC 세션의 transcript를 탐색하여 work-log에 기록.
session_logger.py의 scan_and_record()를 재사용.

Usage:
    python3 active_session_scanner.py              # scan all active sessions
    python3 active_session_scanner.py --dry-run    # list only, don't record
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_logger import scan_and_record

KST = timezone(timedelta(hours=9))
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _cwd_to_project_hash(cwd: str) -> str:
    """cwd 경로를 CC project hash로 변환.

    /Users/dayejeong/git_workplace/cube-backend → -Users-dayejeong-git-workplace-cube-backend
    """
    return "-" + cwd.lstrip("/").replace("/", "-").replace("_", "-")


def _resolve_cwd_for_worktree(cwd: str) -> str | None:
    """worktree cwd에서 원본 레포 경로를 추출."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (Path(cwd) / git_common).resolve()
            return str(git_common.parent)
    except Exception:
        pass
    return None


def find_transcript(session_id: str, cwd: str) -> Path | None:
    """세션 ID와 cwd로 transcript JSONL 경로를 탐색."""
    # 1차: cwd 직접 변환
    project_hash = _cwd_to_project_hash(cwd)
    candidate = PROJECTS_DIR / project_hash / f"{session_id}.jsonl"
    if candidate.exists():
        return candidate

    # 2차: worktree → 원본 레포 경로로 재시도
    original_cwd = _resolve_cwd_for_worktree(cwd)
    if original_cwd and original_cwd != cwd:
        project_hash = _cwd_to_project_hash(original_cwd)
        candidate = PROJECTS_DIR / project_hash / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    # 3차: projects 전체 검색 (fallback)
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate

    return None


def _is_pid_alive(pid: int) -> bool:
    """프로세스가 살아있는지 확인."""
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


def get_active_sessions() -> list[dict]:
    """~/.claude/sessions/*.json에서 활성 세션 목록 수집."""
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions

    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(session_file.read_text())
            sessions.append({
                "pid": data["pid"],
                "session_id": data["sessionId"],
                "cwd": data["cwd"],
                "started_at": data.get("startedAt", 0),
                "alive": _is_pid_alive(data["pid"]),
                "file": session_file,
            })
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"[scanner] failed to read {session_file}: {e}", file=sys.stderr)

    return sessions


def scan_active_sessions(dry_run: bool = False) -> int:
    """모든 활성 세션을 스캔하여 work-log에 기록.

    Returns: 기록된 세션 수.
    """
    sessions = get_active_sessions()
    if not sessions:
        return 0

    recorded_count = 0
    for s in sessions:
        session_id = s["session_id"]
        cwd = s["cwd"]

        transcript = find_transcript(session_id, cwd)
        if not transcript:
            print(f"[scanner] no transcript for {session_id[:8]} ({Path(cwd).name})", file=sys.stderr)
            continue

        if dry_run:
            status = "ALIVE" if s["alive"] else "DEAD"
            started = datetime.fromtimestamp(s["started_at"] / 1000, KST).strftime("%m/%d %H:%M")
            print(f"  {status} | {started} | {Path(cwd).name} | {session_id[:8]} | {transcript}")
            continue

        try:
            result = scan_and_record(session_id, str(transcript), cwd, force=False)
            if result:
                dates = ", ".join(sorted(result.keys()))
                print(f"[scanner] {session_id[:8]} ({Path(cwd).name}): recorded {dates}", file=sys.stderr)
                recorded_count += len(result)
        except Exception as e:
            print(f"[scanner] {session_id[:8]} failed: {e}", file=sys.stderr)

    return recorded_count


def main():
    parser = argparse.ArgumentParser(description="Scan active CC sessions")
    parser.add_argument("--dry-run", action="store_true", help="List sessions only")
    args = parser.parse_args()

    count = scan_active_sessions(dry_run=args.dry_run)
    if not args.dry_run:
        print(f"[scanner] Total: {count} date-slices recorded", file=sys.stderr)


if __name__ == "__main__":
    main()
