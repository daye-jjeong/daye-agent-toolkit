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


def parse_tasks_yml(file_path):
    """Parse tasks.yml with simple line-by-line parsing (no PyYAML)."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    tasks = []
    current = None

    for line in lines:
        stripped = line.rstrip()

        # New task entry: "  - id: t-xxx-nnn"
        m = re.match(r'^\s+-\s+id:\s+(.+)', stripped)
        if m:
            if current:
                tasks.append(current)
            current = {'id': m.group(1).strip()}
            continue

        if current is None:
            continue

        # Key-value pairs within a task
        m = re.match(r'^\s{4,}(\w+):\s+(.+)', stripped)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            if key in ('title', 'status', 'priority', 'owner', 'completed'):
                # Remove quotes
                current[key] = val.strip('"').strip("'")

    if current:
        tasks.append(current)

    return tasks


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
    path = Path(file_path)
    for parent in path.parents:
        if parent.parent == PROJECTS_DIR:
            return parent.name
    return None


def build_summary(file_path, tasks_or_data):
    project = detect_project(file_path)
    if not project:
        return None

    filename = Path(file_path).name
    today = datetime.now(KST).strftime('%Y-%m-%d')

    if filename == 'tasks.yml' and isinstance(tasks_or_data, list):
        tasks = tasks_or_data
        in_progress = [t for t in tasks if t.get('status') == 'in_progress']
        done_today = [t for t in tasks if t.get('status') == 'done' and t.get('completed') == today]

        lines = [f"📋 {project} tasks.yml 변경됨"]

        for t in done_today:
            lines.append(f"  ✅ {t.get('id', '?')}: {t.get('title', '?')} 완료")

        for t in in_progress:
            lines.append(f"  🔄 {t.get('id', '?')}: {t.get('title', '?')}")

        if len(lines) == 1:
            # No in_progress or done_today, just note the change
            total = len(tasks)
            lines.append(f"  총 {total}개 태스크")

        return '\n'.join(lines)

    if filename == 'project.yml' and isinstance(tasks_or_data, dict):
        name = tasks_or_data.get('name', project)
        status = tasks_or_data.get('status', '?')
        return f"📋 {name} 프로젝트 설정 변경됨 (status: {status})"

    if filename.startswith('t-') and filename.endswith('.md'):
        return f"📋 {project}/{filename} 태스크 파일 변경됨"

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
    if not any(x in file_path for x in ['tasks.yml', 'project.yml', '/t-']):
        sys.exit(0)

    # Cooldown check
    if check_cooldown(file_path):
        sys.exit(0)

    # Parse
    filename = Path(file_path).name
    if filename == 'tasks.yml':
        data = parse_tasks_yml(file_path)
    elif filename == 'project.yml':
        data = parse_project_yml(file_path)
    else:
        data = filename  # t-*.md — just pass filename

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
