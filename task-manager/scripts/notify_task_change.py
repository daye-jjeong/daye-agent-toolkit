#!/usr/bin/env python3
"""Task change notifier for Obsidian Shell Commands plugin.

Obsidian Shell Commands 플러그인의 "File content modified" 이벤트로 호출됨.
변경된 태스크 파일을 파싱하여 OpenClaw에 알림을 보낸다.

No external dependencies — stdlib only.

Usage (Obsidian Shell Commands):
    python3 ~/clawd/scripts/notify_task_change.py "{{event_file_path}}"

Flow:
    Obsidian detects file change → this script → clawdbot agent → OpenClaw
"""

import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
VAULT_ROOT = Path.home() / "clawd" / "memory"
PROJECTS_DIR = VAULT_ROOT / "projects"

COOLDOWN_FILE = VAULT_ROOT / "state" / "task_notify_cooldown.json"
COOLDOWN_SECONDS = 30


def load_cooldown():
    try:
        with open(COOLDOWN_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cooldown(state):
    COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COOLDOWN_FILE, 'w') as f:
        json.dump(state, f)


def check_cooldown(file_path):
    state = load_cooldown()
    now = datetime.now(KST).timestamp()
    last = state.get(file_path, 0)
    if now - last < COOLDOWN_SECONDS:
        return True
    state[file_path] = now
    save_cooldown(state)
    return False


def parse_task_md(file_path):
    """Parse t-*.md frontmatter (stdlib only)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        return {}

    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip().strip("'\"")
    return fm


def parse_project_yml(file_path):
    """Parse project.yml for name and status."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    data = {}
    for line in lines:
        m = re.match(r'^(\w+):\s+(.+)', line.rstrip())
        if m:
            data[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return data


def detect_project(file_path):
    """Detect project name from file path (e.g., 'work/ronik')."""
    path = Path(file_path)
    try:
        rel = path.relative_to(PROJECTS_DIR)
        # rel is like work/ronik/t-ronik-001.md → take first 2 parts
        parts = rel.parts
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except ValueError:
        pass
    return None


def build_summary(file_path, data):
    project = detect_project(file_path)
    if not project:
        return None

    filename = Path(file_path).name

    if filename.startswith('t-') and filename.endswith('.md') and isinstance(data, dict):
        task_id = data.get('id', filename)
        title = data.get('title', '?')
        status = data.get('status', '?')

        icon = {'done': '✅', 'in_progress': '🔄', 'blocked': '🚫'}.get(status, '📋')
        return f"{icon} {project}/{task_id}: {title} ({status})"

    if filename == '_project.md' and isinstance(data, dict):
        name = data.get('name', project)
        status = data.get('status', '?')
        return f"📋 {name} 프로젝트 설정 변경됨 (status: {status})"

    return None


TELEGRAM_TARGET = "-1003242721592"


def notify_openclaw(message):
    """Send notification via clawdbot message to Telegram."""
    try:
        result = subprocess.run(
            [
                'clawdbot', 'message', 'send',
                '--channel', 'telegram',
                '--target', TELEGRAM_TARGET,
                '--message', message,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def notify_telegram_direct(message):
    import os
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

    if not bot_token or not chat_id:
        return False

    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({'chat_id': chat_id, 'text': message}).encode()
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    file_path = sys.argv[1]

    # Resolve relative paths (Obsidian may pass vault-relative paths)
    fp = Path(file_path)
    if not fp.is_absolute():
        fp = VAULT_ROOT / fp
    file_path = str(fp.resolve())

    # Only process task-related files in projects/
    if 'projects/' not in file_path:
        sys.exit(0)
    filename = Path(file_path).name
    if not (filename.startswith('t-') and filename.endswith('.md')) and filename != '_project.md':
        sys.exit(0)

    # Cooldown check
    if check_cooldown(file_path):
        sys.exit(0)

    # Parse
    if filename.startswith('t-') and filename.endswith('.md'):
        data = parse_task_md(file_path)
    elif filename == '_project.md':
        data = parse_project_yml(file_path)
    else:
        data = {}

    if not data:
        sys.exit(0)

    summary = build_summary(file_path, data)
    if not summary:
        sys.exit(0)

    # Try clawdbot agent first, fallback to direct Telegram
    if not notify_openclaw(summary):
        notify_telegram_direct(summary)


if __name__ == '__main__':
    main()
