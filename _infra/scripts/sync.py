#!/usr/bin/env python3
"""
Skill Sync — daye-agent-toolkit 양방향 동기화

OpenClaw PC에서 사용. 이 레포를 clone한 뒤 스킬 변경사항을 push/pull.

Usage:
    make sync                                    # sync (기본: push → pull)
    python _infra/scripts/sync.py sync           # 로컬 변경 커밋+푸시 → 원격 최신본 pull
    python _infra/scripts/sync.py pull           # 원격에서 최신 변경사항 가져오기
    python _infra/scripts/sync.py push           # 로컬 변경사항 커밋 + 푸시
    python _infra/scripts/sync.py push "메시지"  # 커밋 메시지 지정
    python _infra/scripts/sync.py status         # 레포 상태 확인
"""

import sys
import subprocess
from pathlib import Path

# ─── Config ───
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # daye-agent-toolkit/


def run_cmd(cmd, cwd=None, quiet=False):
    """Run a shell command and return (success, output)"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd or REPO_ROOT, check=True, text=True, capture_output=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not quiet:
            print(f"  Command failed: {' '.join(cmd)}", file=sys.stderr)
            if e.stderr:
                print(f"     {e.stderr.strip()}", file=sys.stderr)
        return False, e.stderr.strip()


def ensure_repo():
    """Ensure directory is a git repo"""
    if not (REPO_ROOT / ".git").exists():
        print(f"Git repo not found: {REPO_ROOT}")
        return False
    return True


def cmd_pull():
    """Pull latest changes from remote"""
    if not ensure_repo():
        return False

    print("Pulling latest changes...")

    ok, status = run_cmd(["git", "status", "--porcelain"])
    has_local_changes = ok and status.strip()

    if has_local_changes:
        print("  Stashing local changes...")
        run_cmd(["git", "stash"])

    ok, msg = run_cmd(["git", "pull", "--rebase", "origin", "main"])
    if not ok:
        print(f"Pull failed: {msg}")
        if has_local_changes:
            run_cmd(["git", "stash", "pop"])
        return False

    if has_local_changes:
        pop_ok, pop_msg = run_cmd(["git", "stash", "pop"])
        if not pop_ok:
            print(f"  Stash pop conflict — resolve manually: cd {REPO_ROOT}")

    print("Pull done")
    return True


def cmd_push(message=None):
    """Commit and push local changes"""
    if not ensure_repo():
        return False

    ok, status = run_cmd(["git", "status", "--porcelain"])
    if not status.strip():
        print("No changes")
        return True

    print("Changed files:")
    for line in status.strip().split("\n"):
        print(f"  {line}")

    if not message:
        changed_files = status.strip().split("\n")
        skills_changed = set()
        for line in changed_files:
            parts = line.strip().split()
            if len(parts) >= 2:
                filepath = parts[-1]
                skill_name = filepath.split("/")[0] if "/" in filepath else filepath
                skills_changed.add(skill_name)

        if len(skills_changed) == 1:
            skill = skills_changed.pop()
            message = f"update({skill}): auto-sync changes"
        else:
            message = f"update: auto-sync {len(skills_changed)} skills ({', '.join(sorted(skills_changed))})"

    run_cmd(["git", "add", "-A"])

    ok, msg = run_cmd(["git", "commit", "-m", message])
    if not ok:
        print(f"Commit failed: {msg}")
        return False
    print(f"  Committed: {message}")

    ok, msg = run_cmd(["git", "push", "origin", "main"])
    if not ok:
        print(f"Push failed (local commit done): {msg}")
        print(f"   Manual: cd {REPO_ROOT} && git push origin main")
        return False

    print("Push done")
    return True


def cmd_sync(message=None):
    """Push local changes then pull remote"""
    if not ensure_repo():
        return False

    print("Bidirectional sync...")

    ok, status = run_cmd(["git", "status", "--porcelain"])
    if ok and status.strip():
        print("\n-- Push local changes --")
        if not cmd_push(message):
            return False
    else:
        print("  No local changes")

    print("\n-- Pull remote --")
    if not cmd_pull():
        return False

    print("\nSync done")
    return True


def cmd_status():
    """Show repo status"""
    if not ensure_repo():
        return False

    print(f"Repo: {REPO_ROOT}")

    ok, branch = run_cmd(["git", "branch", "--show-current"], quiet=True)
    if ok:
        print(f"  Branch: {branch}")

    ok, status = run_cmd(["git", "status", "--porcelain"])
    if status.strip():
        print("  Local changes:")
        for line in status.strip().split("\n"):
            print(f"     {line}")
    else:
        print("  No local changes")

    run_cmd(["git", "fetch", "--dry-run"], quiet=True)
    ok, log = run_cmd(
        ["git", "log", "HEAD..origin/main", "--oneline"], quiet=True
    )
    if ok and log.strip():
        print("  Remote commits:")
        for line in log.strip().split("\n"):
            print(f"     {line}")

    categories = ["shared", "cc", "openclaw"]
    skills = []
    for cat in categories:
        cat_dir = REPO_ROOT / cat
        if cat_dir.is_dir():
            cat_skills = sorted(
                d.name for d in cat_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            )
            skills.extend(cat_skills)
            if cat_skills:
                print(f"  {cat} ({len(cat_skills)}): {', '.join(cat_skills)}")
    print(f"\n  Total: {len(skills)} skills")

    return True


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"

    if action == "sync":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        success = cmd_sync(message)
    elif action == "pull":
        success = cmd_pull()
    elif action == "push":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        success = cmd_push(message)
    elif action == "status":
        success = cmd_status()
    else:
        print(f"Unknown command: {action}")
        print(__doc__)
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
