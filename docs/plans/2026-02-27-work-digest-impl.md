# work-digest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a unified work-digest skill that logs Claude Code sessions and sends daily summary + suggestions via Telegram.

**Architecture:** Hybrid pipeline — session_logger.py (CC hook, Tier 1) records sessions to work-log/*.md, parse_work_log.py (Tier 1) extracts structured JSON, daily_digest.py (Tier 2) uses LLM to generate summary + gap analysis + pattern feedback and sends via Telegram.

**Tech Stack:** Python 3 (stdlib only for Tier 1), clawdbot CLI (Telegram), PyYAML (goal-planner YAML parsing)

**Design doc:** `docs/plans/2026-02-27-work-digest-design.md`

---

### Task 1: Create skill skeleton

**Files:**
- Create: `work-digest/SKILL.md`
- Create: `work-digest/.claude-skill`
- Create: `work-digest/work-log/.gitkeep`
- Create: `work-digest/references/prompt-template.md`

**Step 1: Create directory structure**

```bash
mkdir -p work-digest/scripts work-digest/work-log/state work-digest/references
```

**Step 2: Create .claude-skill**

```json
{
  "name": "work-digest",
  "version": "1.0.0",
  "description": "일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림",
  "entrypoint": "SKILL.md"
}
```

**Step 3: Create SKILL.md**

Write frontmatter + overview + trigger + file structure + automation + scripts table.

Key content:
- name: work-digest
- description: 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림
- Trigger: 크론 21:00 (자동) 또는 수동 호출
- 2개 파이프라인: session_logger (CC 훅) + daily_digest (크론)
- 스크립트 테이블: session_logger.py (Tier 1), parse_work_log.py (Tier 1), daily_digest.py (Tier 2)
- 자동화 테이블: 크론 `0 21 * * *`

**Step 4: Create references/prompt-template.md**

LLM 프롬프트 템플릿:
- 시스템 프롬프트: "당신은 개발자의 일일 작업을 분석하는 어시스턴트입니다."
- 입력 JSON 스키마 설명
- 출력 포맷: 4섹션 (요약, 레포별, 목표 대비, 패턴 피드백)
- 제약: 텔레그램 4096자 제한, 이모지 사용, 한국어

**Step 5: Create work-log/.gitkeep**

```bash
touch work-digest/work-log/.gitkeep
```

**Step 6: Commit**

```bash
git add work-digest/
git commit -m "feat(work-digest): add skill skeleton — SKILL.md, .claude-skill, prompt template"
```

---

### Task 2: Create session_logger.py (CC hook)

**Files:**
- Create: `work-digest/scripts/session_logger.py`
- Reference: `_cc/vault_recorder.py` (기존 코드 — 이관 후 삭제 예정)

This is a refactored version of `_cc/vault_recorder.py` with these changes:
- 저장 경로: `~/openclaw/vault/` → `work-digest/work-log/` (스크립트 기준 상대경로)
- `cc-config.json` 의존 제거
- 태스크 진행 로그 (t-*.md append) 기능 제거
- 상태 파일: `work-digest/work-log/state/session_logger_state.json`

**Step 1: Write session_logger.py**

```python
#!/usr/bin/env python3
"""Session Logger — Claude Code hook for work-digest skill.

CC 세션 종료 시 work-log/YYYY-MM-DD.md에 세션 정보를 기록한다.

Hook events:
- PreCompact → 세션 마커 (mid-session 백업)
- SessionEnd → 세션 마커 (최종 기록)

stdin: { session_id, transcript_path, cwd, hook_event_name, ... }
"""

import sys
import json
import fcntl
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent.parent  # work-digest/
WORK_LOG_DIR = BASE_DIR / "work-log"
STATE_FILE = WORK_LOG_DIR / "state" / "session_logger_state.json"
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def parse_stdin():
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return None


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"recorded": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def already_recorded(session_id: str, event: str) -> bool:
    state = load_state()
    key = f"{session_id}:{event}"
    if key in state.get("recorded", []):
        return True
    state.setdefault("recorded", []).append(key)
    state["recorded"] = state["recorded"][-50:]
    save_state(state)
    return False


def detect_repo(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except Exception:
        pass
    return Path(cwd).name


def parse_transcript(transcript_path: str) -> dict:
    files_modified = set()
    commands_run = []
    errors = []
    first_user_msg = ""
    session_start = None
    session_end = None

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if session_start is None:
                        session_start = ts
                    session_end = ts

                entry_type = entry.get("type", "")
                msg = entry.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""

                if not first_user_msg and entry_type == "user":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                first_user_msg = block.get("text", "")[:120]
                                break
                    elif isinstance(content, str):
                        first_user_msg = content[:120]

                if entry_type == "assistant" and isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        tool = block.get("name", "")
                        inp = block.get("input", {})
                        if tool in ("Edit", "Write"):
                            fp = inp.get("file_path", "")
                            if fp:
                                files_modified.add(fp)
                        if tool == "Bash":
                            cmd = inp.get("command", "")
                            if cmd:
                                commands_run.append(cmd[:80])

                if entry_type == "tool_result":
                    data_field = entry.get("data", {})
                    text = ""
                    if isinstance(data_field, dict):
                        text = str(data_field.get("output", ""))[:120]
                    if text and ("error" in text.lower() or "Error" in text):
                        errors.append(text[:120])

    except (FileNotFoundError, PermissionError):
        pass

    duration_min = None
    if session_start and session_end:
        try:
            start = datetime.fromisoformat(session_start)
            end = datetime.fromisoformat(session_end)
            duration_min = int((end - start).total_seconds() / 60)
        except (ValueError, TypeError):
            pass

    return {
        "files": sorted(files_modified),
        "commands": commands_run[:10],
        "errors": errors[:5],
        "topic": first_user_msg,
        "duration_min": duration_min,
    }


def build_frontmatter(now):
    date_str = now.strftime("%Y-%m-%d")
    weekday = WEEKDAYS_KO[now.weekday()]
    return (
        f"---\ndate: {date_str}\ntype: work-log\n"
        f"tags: [work-log]\n---\n\n# {date_str} ({weekday})\n\n"
    )


def build_session_section(session_id, data, now, repo):
    time_str = now.strftime("%H:%M")
    sid_short = session_id[:8] if session_id else "unknown"

    lines = []
    lines.append(f"## 세션 {time_str} ({sid_short}, {repo})")

    file_count = len(data["files"])
    duration = f"{data['duration_min']}분" if data["duration_min"] else "?분"
    lines.append(f"> 파일 {file_count}개 | {duration}")
    lines.append("")

    if data["topic"]:
        lines.append(f"**주제**: {data['topic']}")
        lines.append("")

    if data["files"]:
        lines.append("### 수정된 파일")
        home = str(Path.home())
        for fp in data["files"]:
            lines.append(f"- `{fp.replace(home, '~')}`")
        lines.append("")

    if data["commands"]:
        lines.append("### 실행 명령")
        for cmd in data["commands"][:5]:
            lines.append(f"- `{cmd}`")
        lines.append("")

    if data["errors"]:
        lines.append("### 에러")
        for err in data["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_session_marker(session_id, data, now, repo):
    WORK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    daily_file = WORK_LOG_DIR / f"{now.strftime('%Y-%m-%d')}.md"
    is_new = not daily_file.exists()
    section = build_session_section(session_id, data, now, repo)

    with open(daily_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            if is_new:
                f.write(build_frontmatter(now))
            f.write(section)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def main():
    hook_input = parse_stdin()
    if not hook_input:
        sys.exit(0)

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", "")
    event = hook_input.get("hook_event_name", "")

    if not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    now = datetime.now(KST)
    repo = detect_repo(cwd) if cwd else "unknown"
    data = parse_transcript(transcript_path)

    if not data["files"] and not data["commands"] and not data["topic"]:
        sys.exit(0)

    if already_recorded(session_id, event):
        sys.exit(0)

    write_session_marker(session_id, data, now, repo)


if __name__ == "__main__":
    main()
```

**Step 2: Verify script runs without errors**

```bash
echo '{}' | python3 work-digest/scripts/session_logger.py
echo $?  # Expected: 0
```

**Step 3: Commit**

```bash
git add work-digest/scripts/session_logger.py
git commit -m "feat(work-digest): add session_logger.py — CC hook for session recording"
```

---

### Task 3: Create parse_work_log.py (Tier 1 parser)

**Files:**
- Create: `work-digest/scripts/parse_work_log.py`

Parses work-log/YYYY-MM-DD.md + goal-planner daily YAML → structured JSON to stdout.

**Step 1: Write parse_work_log.py**

```python
#!/usr/bin/env python3
"""Parse work-log daily .md + goal-planner YAML → JSON stdout.

Usage:
    python3 parse_work_log.py [--date YYYY-MM-DD]  # default: today
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent.parent  # work-digest/
WORK_LOG_DIR = BASE_DIR / "work-log"

# goal-planner daily YAML 경로 (이 레포 기준)
TOOLKIT_ROOT = BASE_DIR.parent  # daye-agent-toolkit/
# goal-planner가 vault에 저장하므로 직접 참조는 어려움
# cc-config.json에서 vault_root를 읽거나 환경변수로 전달
GOALS_DIR_CANDIDATES = [
    Path.home() / "openclaw" / "vault" / "goals" / "daily",
    TOOLKIT_ROOT / "goal-planner" / "goals" / "daily",
]


def find_goals_dir() -> Path | None:
    for d in GOALS_DIR_CANDIDATES:
        if d.exists():
            return d
    return None


def parse_daily_md(file_path: Path) -> list[dict]:
    """Parse work-log/YYYY-MM-DD.md → list of session dicts."""
    if not file_path.exists():
        return []

    text = file_path.read_text(encoding="utf-8")
    sessions = []
    # Split by ## 세션 headers
    parts = re.split(r"^## 세션 ", text, flags=re.MULTILINE)

    for part in parts[1:]:  # skip frontmatter/header
        session = {"time": "", "repo": "", "topic": "", "files": [],
                   "commands": [], "errors": [], "file_count": 0, "duration_min": None}

        # First line: "11:00 (sid, repo)"
        first_line = part.split("\n")[0]
        time_match = re.match(r"(\d{2}:\d{2})\s+\(([^,]+),\s*(.+)\)", first_line)
        if time_match:
            session["time"] = time_match.group(1)
            session["repo"] = time_match.group(3).strip().rstrip(")")

        # Blockquote: "> 파일 N개 | M분"
        bq_match = re.search(r">\s*파일\s*(\d+)개\s*\|\s*(\d+|[?])분", part)
        if not bq_match:
            bq_match = re.search(r">\s*수정 파일\s*(\d+)개\s*\|\s*(\d+|[?])분", part)
        if bq_match:
            session["file_count"] = int(bq_match.group(1))
            dur = bq_match.group(2)
            session["duration_min"] = int(dur) if dur != "?" else None

        # Topic
        topic_match = re.search(r"\*\*주제\*\*:\s*(.+)", part)
        if topic_match:
            session["topic"] = topic_match.group(1).strip()[:120]

        # Files (- `path`)
        if "### 수정된 파일" in part:
            file_section = part.split("### 수정된 파일")[1].split("###")[0]
            session["files"] = re.findall(r"- `(.+?)`", file_section)

        # Commands
        if "### 실행 명령" in part:
            cmd_section = part.split("### 실행 명령")[1].split("###")[0]
            session["commands"] = re.findall(r"- `(.+?)`", cmd_section)

        # Errors
        if "### 에러" in part:
            err_section = part.split("### 에러")[1].split("###")[0]
            session["errors"] = re.findall(r"- (.+)", err_section)

        sessions.append(session)

    return sessions


def parse_daily_goals(date_str: str) -> dict | None:
    """Parse goal-planner daily YAML for the given date."""
    goals_dir = find_goals_dir()
    if not goals_dir:
        return None

    goal_file = goals_dir / f"{date_str}.yml"
    if not goal_file.exists():
        return None

    try:
        import yaml
        with open(goal_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            "top3": data.get("top3", []),
            "checklist": data.get("checklist", []),
        }
    except ImportError:
        # yaml not available — skip goals
        return None
    except Exception:
        return None


def build_summary(sessions: list[dict]) -> dict:
    repos: dict[str, int] = {}
    total_duration = 0
    total_files = 0
    total_errors = 0
    has_tests = False
    has_commits = False

    for s in sessions:
        repo = s["repo"]
        repos[repo] = repos.get(repo, 0) + 1
        if s["duration_min"]:
            total_duration += s["duration_min"]
        total_files += s["file_count"]
        total_errors += len(s["errors"])

        for cmd in s["commands"]:
            if any(kw in cmd for kw in ["pytest", "jest", "test", "vitest"]):
                has_tests = True
            if "git commit" in cmd:
                has_commits = True

    return {
        "total_sessions": len(sessions),
        "total_duration_min": total_duration,
        "repos": repos,
        "total_files": total_files,
        "total_errors": total_errors,
        "has_tests": has_tests,
        "has_commits": has_commits,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse work-log → JSON")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today KST)")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now(KST).strftime("%Y-%m-%d")

    daily_file = WORK_LOG_DIR / f"{date_str}.md"
    sessions = parse_daily_md(daily_file)

    if not sessions:
        json.dump({"date": date_str, "sessions": [], "summary": None, "goals": None},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.exit(0)

    summary = build_summary(sessions)
    goals = parse_daily_goals(date_str)

    output = {
        "date": date_str,
        "sessions": sessions,
        "summary": summary,
        "goals": goals,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
```

**Step 2: Test with today's existing vault log (dry-run)**

Copy today's vault log temporarily to test parsing:

```bash
cp ~/openclaw/vault/2026-02-27.md work-digest/work-log/2026-02-27.md
python3 work-digest/scripts/parse_work_log.py --date 2026-02-27 | python3 -m json.tool | head -40
```

Expected: valid JSON with sessions array and summary.

**Step 3: Remove temporary test file, commit**

```bash
rm work-digest/work-log/2026-02-27.md
git add work-digest/scripts/parse_work_log.py
git commit -m "feat(work-digest): add parse_work_log.py — Tier 1 work-log parser"
```

---

### Task 4: Create daily_digest.py (Tier 2 LLM + Telegram)

**Files:**
- Create: `work-digest/scripts/daily_digest.py`
- Reference: `work-digest/references/prompt-template.md`

Reads parse_work_log.py JSON from stdin, calls LLM for analysis, sends result to Telegram.

**Step 1: Write daily_digest.py**

```python
#!/usr/bin/env python3
"""Daily Work Digest — Tier 2 LLM analysis + Telegram delivery.

Usage:
    python3 parse_work_log.py | python3 daily_digest.py
    python3 daily_digest.py --dry-run < input.json  # preview without sending
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

TELEGRAM_GROUP = "-1003242721592"
THREAD_ID = None  # work-digest 전용 토픽 — 생성 후 설정
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_TEMPLATE = BASE_DIR / "references" / "prompt-template.md"
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def load_prompt_template() -> str:
    try:
        return PROMPT_TEMPLATE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def build_fallback_message(data: dict) -> str:
    """LLM 없이 템플릿 기반 메시지 생성 (fallback)."""
    summary = data.get("summary")
    if not summary:
        return f"📋 {data['date']} — 오늘 기록된 세션이 없습니다."

    date_str = data["date"]
    total = summary["total_sessions"]
    hours = summary["total_duration_min"] // 60
    mins = summary["total_duration_min"] % 60
    files = summary["total_files"]

    lines = [f"📋 {date_str} 작업 다이제스트", ""]
    lines.append(f"⏱ {total}세션 · {hours}시간 {mins}분 · 파일 {files}개")
    lines.append("")

    # Repos
    lines.append("📂 레포별:")
    for repo, count in sorted(summary["repos"].items(), key=lambda x: -x[1]):
        # Find topics for this repo
        topics = [s["topic"][:40] for s in data["sessions"]
                  if s["repo"] == repo and s["topic"]]
        topic_str = f" ({', '.join(topics[:2])})" if topics else ""
        lines.append(f"  {repo} {count}세션{topic_str}")
    lines.append("")

    # Goals
    goals = data.get("goals")
    if goals and goals.get("top3"):
        lines.append("🎯 목표:")
        for item in goals["top3"]:
            status = item.get("status", "todo")
            icon = "✅" if status == "done" else "⚠️" if status == "in_progress" else "❌"
            lines.append(f"  {icon} {item.get('title', '?')}")
        lines.append("")

    # Pattern feedback
    lines.append("💡 패턴:")
    if len(summary["repos"]) >= 4:
        lines.append(f"  • {len(summary['repos'])}개 레포 컨텍스트 스위칭")
    if summary["total_errors"] > 0:
        lines.append(f"  • 에러 {summary['total_errors']}건 발생")
    if not summary["has_tests"]:
        lines.append("  • 테스트 실행 0건")
    if not summary["has_commits"]:
        lines.append("  • 커밋 0건")

    return "\n".join(lines)


def send_telegram(message: str):
    cmd = ["clawdbot", "message", "send", "-t", TELEGRAM_GROUP]
    if THREAD_ID:
        cmd.extend(["--thread-id", THREAD_ID])
    cmd.extend(["-m", message])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as e:
        print(f"Telegram send failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Daily work digest")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending")
    args = parser.parse_args()

    data = json.loads(sys.stdin.read())

    if not data.get("sessions"):
        if not args.dry_run:
            send_telegram(f"📋 {data.get('date', '?')} — 오늘 기록된 세션이 없습니다.")
        else:
            print("No sessions recorded today.")
        return

    # Fallback: template-based message (no LLM)
    # TODO: LLM analysis integration (Phase 2)
    message = build_fallback_message(data)

    if args.dry_run:
        print(message)
    else:
        send_telegram(message)
        print(f"Sent digest for {data['date']}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

Note: LLM integration is marked TODO — start with the template-based fallback first, then add LLM in a follow-up. This keeps the initial delivery simple and testable.

**Step 2: Test with dry-run**

```bash
cp ~/openclaw/vault/2026-02-27.md work-digest/work-log/2026-02-27.md
python3 work-digest/scripts/parse_work_log.py --date 2026-02-27 | python3 work-digest/scripts/daily_digest.py --dry-run
```

Expected: formatted digest message printed to stdout.

**Step 3: Clean up test file, commit**

```bash
rm work-digest/work-log/2026-02-27.md
git add work-digest/scripts/daily_digest.py
git commit -m "feat(work-digest): add daily_digest.py — template-based digest + Telegram"
```

---

### Task 5: Update CC hooks + cleanup old recorder

**Files:**
- Modify: `~/.claude/settings.json` (hooks.PreCompact, hooks.SessionEnd)
- Delete: existing vault_recorder reference (hooks only — don't delete source file yet)

**Step 1: Get the absolute path for the new hook**

```bash
realpath work-digest/scripts/session_logger.py
```

Expected: `/Users/dayejeong/git_workplace/daye-agent-toolkit/work-digest/scripts/session_logger.py`

**Step 2: Update ~/.claude/settings.json hooks**

Change both PreCompact and SessionEnd hooks from:
```
python3 /Users/dayejeong/openclaw-origin/skills/_cc/vault_recorder.py
```
to:
```
python3 /Users/dayejeong/git_workplace/daye-agent-toolkit/work-digest/scripts/session_logger.py
```

**Step 3: Verify hook works**

```bash
echo '{"session_id":"test123","transcript_path":"/nonexistent","cwd":"/tmp","hook_event_name":"SessionEnd"}' | python3 work-digest/scripts/session_logger.py
echo $?  # Expected: 0 (graceful exit — transcript doesn't exist)
```

**Step 4: Commit (in this repo only)**

```bash
git add -A
git commit -m "feat(work-digest): wire CC hooks to session_logger.py"
```

---

### Task 6: Update skills.json + CLAUDE.md

**Files:**
- Modify: `skills.json` — add "work-digest" to local_skills
- Modify: `CLAUDE.md` — add work-digest to skill tables

**Step 1: Add to skills.json local_skills array**

Add `"work-digest"` after `"task-dashboard"` (alphabetical-ish).

**Step 2: Update CLAUDE.md skill tables**

Add to "Claude Code + OpenClaw 양쪽" table (or "Claude Code 전용" if not OpenClaw):
```
| work-digest | 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림 |
```

**Step 3: Commit**

```bash
git add skills.json CLAUDE.md
git commit -m "chore: register work-digest in skills.json and CLAUDE.md"
```

---

### Task 7: End-to-end test + .gitignore

**Files:**
- Create: `work-digest/.gitignore` (ignore work-log/*.md and state/)

**Step 1: Create .gitignore**

```
work-log/*.md
work-log/state/
```

Keep `work-log/.gitkeep` but ignore actual logs and state (these are local data, not code).

**Step 2: End-to-end dry-run**

```bash
# 1. Simulate a session log by copying today's vault data
cp ~/openclaw/vault/2026-02-27.md work-digest/work-log/2026-02-27.md

# 2. Run full pipeline
python3 work-digest/scripts/parse_work_log.py --date 2026-02-27 | python3 work-digest/scripts/daily_digest.py --dry-run

# 3. Clean up
rm work-digest/work-log/2026-02-27.md
```

**Step 3: Commit**

```bash
git add work-digest/.gitignore
git commit -m "chore(work-digest): add .gitignore for work-log data"
```

---

### Task 8: Delete old _cc/vault_recorder.py

**Files:**
- Delete: `_cc/vault_recorder.py`

**Step 1: Verify hooks no longer reference old file**

```bash
grep "vault_recorder" ~/.claude/settings.json
```

Expected: no matches.

**Step 2: Delete**

```bash
rm _cc/vault_recorder.py
# Check if _cc/ directory is now empty (may have other files)
ls _cc/
```

If `_cc/` is empty, remove it too.

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove old vault_recorder.py — replaced by work-digest/session_logger.py"
```

---

## Follow-up (not in this plan)

- **LLM integration**: Replace `build_fallback_message()` in daily_digest.py with actual LLM call (clawdbot sessions spawn or direct API)
- **Telegram topic**: Create dedicated work-digest thread in Telegram group, set THREAD_ID
- **Cron setup**: Add `0 21 * * *` cron for `parse_work_log.py | daily_digest.py`
- **Goal-planner path**: Finalize where daily goals YAML lives after OpenClaw migration
