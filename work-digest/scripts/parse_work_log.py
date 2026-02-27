#!/usr/bin/env python3
"""Parse Work Log — daily MD → structured JSON.

Reads work-digest/work-log/YYYY-MM-DD.md (produced by session_logger.py)
and optionally goal-planner daily YAML → structured JSON to stdout.

Usage:
    python3 parse_work_log.py [--date YYYY-MM-DD]
    # default: today (KST)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent.parent          # work-digest/
TOOLKIT_ROOT = BASE_DIR.parent                             # daye-agent-toolkit/
WORK_LOG_DIR = BASE_DIR / "work-log"

# ── Goal YAML candidate paths ───────────────────────
GOAL_CANDIDATE_DIRS = [
    Path.home() / "openclaw" / "vault" / "goals" / "daily",
    TOOLKIT_ROOT / "goal-planner" / "goals" / "daily",
]

# ── Regex patterns ───────────────────────────────────

# Matches both formats:
#   ## 세션 13:46 (8ed2bc46, daye-agent-toolkit)         ← session_logger.py
#   ## 세션 13:46 (claude-code, 8ed2bc46, daye-agent-toolkit)  ← vault/openclaw
RE_SESSION_HEADER = re.compile(
    r"^##\s+세션\s+(\d{1,2}:\d{2})\s+\("
    r"(?:[\w-]+,\s*)?"                          # optional tool name prefix
    r"([0-9a-f]{8}),\s*"                        # session_id (8-hex)
    r"([^\)]+)"                                 # repo name
    r"\)\s*$"
)

# > 파일 3개 | 7분  OR  > 수정 파일 3개 | 7분
RE_BLOCKQUOTE = re.compile(
    r"^>\s+(?:수정\s+)?파일\s+(\d+)개\s*\|\s*(\d+|[?？])분"
)

RE_TOPIC = re.compile(r"^\*\*주제\*\*:\s*(.+)$")
RE_FILE_ITEM = re.compile(r"^-\s+`(.+?)`\s*$")
RE_CMD_ITEM = re.compile(r"^-\s+`(.+?)`\s*$")
RE_ERROR_ITEM = re.compile(r"^-\s+(.+)$")

# Test keywords in commands
TEST_KEYWORDS = {"pytest", "jest", "test", "vitest"}
TEST_PATTERNS = ["npm run test", "npx test", "npm test", "bun test"]


# ── Section extraction ───────────────────────────────

def _subsection_name(line: str) -> str | None:
    """Return normalized subsection name from ### header, or None."""
    m = re.match(r"^###\s+(.+)$", line)
    if not m:
        return None
    name = m.group(1).strip()
    # Normalize known subsection names
    if "파일" in name:
        return "files"
    if "명령" in name:
        return "commands"
    if "에러" in name or "이슈" in name:
        return "errors"
    return name


def parse_session_block(lines: list[str]) -> dict | None:
    """Parse a single session block (lines between ## 세션 headers)."""
    if not lines:
        return None

    header_match = RE_SESSION_HEADER.match(lines[0])
    if not header_match:
        return None

    time_str = header_match.group(1)
    session_id = header_match.group(2)
    repo = header_match.group(3).strip()

    file_count = 0
    duration_min = None
    topic = ""
    files: list[str] = []
    commands: list[str] = []
    errors: list[str] = []

    current_subsection: str | None = None
    # State for multi-line backtick commands
    pending_cmd: str | None = None

    i = 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1

        # Handle multi-line backtick continuation
        if pending_cmd is not None:
            if "`" in stripped:
                # Closing backtick found — capture first line only
                commands.append(pending_cmd)
                pending_cmd = None
            # else: still inside multi-line block, skip
            continue

        if not stripped:
            continue

        # Blockquote (file count + duration)
        bq = RE_BLOCKQUOTE.match(stripped)
        if bq:
            file_count = int(bq.group(1))
            dur_str = bq.group(2)
            duration_min = int(dur_str) if dur_str.isdigit() else None
            continue

        # Topic
        tm = RE_TOPIC.match(stripped)
        if tm:
            topic = tm.group(1).strip()
            continue

        # Subsection header
        sub = _subsection_name(stripped)
        if sub is not None:
            current_subsection = sub
            continue

        # List items under subsections
        if current_subsection == "files":
            fm = RE_FILE_ITEM.match(stripped)
            if fm:
                files.append(fm.group(1))
        elif current_subsection == "commands":
            # Single-line: - `cmd here`
            cm = RE_CMD_ITEM.match(stripped)
            if cm:
                commands.append(cm.group(1))
            else:
                # Multi-line: - `cmd start...  (no closing backtick on same line)
                ml = re.match(r"^-\s+`(.+)$", stripped)
                if ml:
                    pending_cmd = ml.group(1)
        elif current_subsection == "errors":
            em = RE_ERROR_ITEM.match(stripped)
            if em:
                errors.append(em.group(1))

    # Flush any unclosed multi-line command
    if pending_cmd is not None:
        commands.append(pending_cmd)

    return {
        "time": time_str,
        "session_id": session_id,
        "repo": repo,
        "file_count": file_count,
        "duration_min": duration_min,
        "topic": topic,
        "files": files,
        "commands": commands,
        "errors": errors,
    }


# ── Main parsing ─────────────────────────────────────

def parse_work_log(date_str: str) -> dict:
    """Parse work-log/YYYY-MM-DD.md → structured dict."""
    md_path = WORK_LOG_DIR / f"{date_str}.md"

    result = {
        "date": date_str,
        "sessions": [],
        "summary": None,
        "goals": None,
    }

    if not md_path.exists():
        return result

    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Split into session blocks at ## 세션 headers
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        if RE_SESSION_HEADER.match(line.strip()):
            if current_block:
                blocks.append(current_block)
            current_block = [line.strip()]
        elif current_block:
            current_block.append(line)

    if current_block:
        blocks.append(current_block)

    # Parse each block
    sessions = []
    for block in blocks:
        session = parse_session_block(block)
        if session:
            sessions.append(session)

    result["sessions"] = sessions

    # Build summary
    if sessions:
        repos: dict[str, int] = {}
        total_duration = 0
        total_files = 0
        total_errors = 0
        has_tests = False
        has_commits = False

        for s in sessions:
            repo = s["repo"]
            repos[repo] = repos.get(repo, 0) + 1
            if s["duration_min"] is not None:
                total_duration += s["duration_min"]
            total_files += s["file_count"]
            total_errors += len(s["errors"])

            for cmd in s["commands"]:
                cmd_lower = cmd.lower()
                if not has_tests:
                    for kw in TEST_KEYWORDS:
                        if kw in cmd_lower:
                            has_tests = True
                            break
                    if not has_tests:
                        for pat in TEST_PATTERNS:
                            if pat in cmd_lower:
                                has_tests = True
                                break
                if not has_commits and "git commit" in cmd_lower:
                    has_commits = True

        result["summary"] = {
            "total_sessions": len(sessions),
            "total_duration_min": total_duration,
            "repos": repos,
            "total_files": total_files,
            "total_errors": total_errors,
            "has_tests": has_tests,
            "has_commits": has_commits,
        }

    # Load goals
    result["goals"] = load_goals(date_str)

    return result


# ── Goal loader ──────────────────────────────────────

def load_goals(date_str: str) -> dict | None:
    """Try to load goal-planner daily YAML. Returns dict or None."""
    for candidate_dir in GOAL_CANDIDATE_DIRS:
        yml_path = candidate_dir / f"{date_str}.yml"
        if yml_path.exists():
            return _parse_yaml_file(yml_path)
    return None


def _parse_yaml_file(path: Path) -> dict | None:
    """Load YAML file using PyYAML if available, otherwise skip."""
    try:
        import yaml  # type: ignore
    except ImportError:
        print(
            f"[parse_work_log] PyYAML not installed, skipping goals: {path}",
            file=sys.stderr,
        )
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        # Extract relevant fields
        result: dict = {}
        if "top3" in data:
            result["top3"] = data["top3"]
        if "checklist" in data:
            result["checklist"] = data["checklist"]
        return result if result else None
    except Exception as e:
        print(f"[parse_work_log] Failed to parse {path}: {e}", file=sys.stderr)
        return None


# ── CLI ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Parse work-log daily MD → structured JSON"
    )
    parser.add_argument(
        "--date",
        default=datetime.now(KST).strftime("%Y-%m-%d"),
        help="Date in YYYY-MM-DD format (default: today KST)",
    )
    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Error: invalid date format '{args.date}', expected YYYY-MM-DD",
              file=sys.stderr)
        sys.exit(1)

    result = parse_work_log(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
