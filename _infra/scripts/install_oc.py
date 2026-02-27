#!/usr/bin/env python3
"""OpenClaw extraDirs 설정 스크립트.

Called by: make install-oc
Usage: python3 _infra/scripts/install_oc.py <repo_dir>
"""

import json
import os
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: install_oc.py <repo_dir>", file=sys.stderr)
        sys.exit(1)

    repo_dir = sys.argv[1]
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")

    if not os.path.exists(config_path):
        print("⚠ openclaw.json not found")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    skills = config.setdefault("skills", {})
    load = skills.setdefault("load", {})

    new_dirs = [
        os.path.expanduser("~/.openclaw/core-skills"),
        repo_dir + "/shared",
        repo_dir + "/openclaw",
    ]
    load["extraDirs"] = new_dirs

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("✓ extraDirs updated:")
    for d in new_dirs:
        print(f"  {d}")


if __name__ == "__main__":
    main()
