#!/usr/bin/env python3
"""Claude Code 환경 설정 (인터랙티브).

make init에서 호출되거나 단독 실행 가능.
~/.claude/settings.json + cc-config.json 생성.

Usage: python3 _infra/scripts/setup_env.py
Called by: make init (CC 기본 모드)
"""

import json
import shutil
import sys
from pathlib import Path

# ── 경로 ───────────────────────────────────────────

CC_DIR = Path(__file__).resolve().parent.parent / "cc"  # _infra/cc/
CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
CONFIG_FILE = CLAUDE_DIR / "cc-config.json"


# ── 플러그인 그룹 ──────────────────────────────────

PLUGIN_GROUPS = {
    1: {
        "name": "Core",
        "desc": "superpowers, commit, code-review, feature-dev, PR, skill-creator",
        "plugins": [
            "superpowers@claude-plugins-official",
            "superpowers-lab@superpowers-marketplace",
            "commit-commands@cube-claude-skills",
            "code-review@cube-claude-skills",
            "feature-dev@cube-claude-skills",
            "pr-checklist@cube-claude-skills",
            "release-note@cube-claude-skills",
            "skill-creator@cube-claude-skills",
            "mcp-builder@cube-claude-skills",
        ],
    },
    2: {
        "name": "Awesome Skills",
        "desc": "template, research, artifacts, changelog, file-organizer",
        "plugins": [
            "template-skill@awesome-claude-skills",
            "internal-comms@awesome-claude-skills",
            "lead-research-assistant@awesome-claude-skills",
            "content-research-writer@awesome-claude-skills",
            "artifacts-builder@awesome-claude-skills",
            "changelog-generator@awesome-claude-skills",
            "file-organizer@awesome-claude-skills",
        ],
    },
    3: {
        "name": "Cube Work",
        "desc": "cube-context, health, logs, devops, pm-bot",
        "plugins": [
            "cube-context@cube-claude-skills",
            "cube-health@cube-claude-skills",
            "cube-logs@cube-claude-skills",
            "cube-devops@cube-claude-skills",
            "cube-devops-improve@cube-claude-skills",
            "pm-bot@cube-claude-skills",
        ],
    },
    4: {
        "name": "Style",
        "desc": "ralph-wiggum, learning, explanatory output",
        "plugins": [
            "ralph-wiggum@claude-code-plugins",
            "explanatory-output-style@claude-code-plugins",
            "learning-output-style@cube-claude-skills",
        ],
    },
}


# ── Vault 자동 탐지 ────────────────────────────────

def find_obsidian_vaults() -> list[Path]:
    """알려진 위치에서 Obsidian vault 탐색."""
    candidates = []
    search_dirs = [
        Path.home() / "openclaw" / "vault",
        Path.home() / "Documents",
        Path.home() / "Library" / "Mobile Documents"
        / "iCloud~md~obsidian" / "Documents",
    ]

    for d in search_dirs:
        if not d.exists():
            continue
        # 이 디렉토리 자체가 vault인지
        if (d / ".obsidian").exists():
            candidates.append(d)
            continue
        # 한 단계 아래 확인
        try:
            for child in sorted(d.iterdir()):
                if child.is_dir() and (child / ".obsidian").exists():
                    candidates.append(child)
        except PermissionError:
            continue

    return candidates


def ask_vault_path() -> Path:
    print("── Obsidian Vault 경로 ──\n")

    vaults = find_obsidian_vaults()

    if vaults:
        print("발견된 vault:")
        for i, v in enumerate(vaults, 1):
            print(f"  {i}. {v}")
        print(f"  {len(vaults) + 1}. 직접 입력")
        print()

        while True:
            choice = input(f"선택 [1-{len(vaults) + 1}]: ").strip()
            try:
                n = int(choice)
                if 1 <= n <= len(vaults):
                    return vaults[n - 1]
                if n == len(vaults) + 1:
                    break
            except ValueError:
                pass
            print("다시 선택해주세요.")

    # 직접 입력
    while True:
        path = input("Vault 절대 경로: ").strip()
        p = Path(path).expanduser()
        if p.exists() and (p / ".obsidian").exists():
            return p
        if p.exists():
            confirm = input(
                ".obsidian 폴더가 없습니다. 그래도 사용? [y/N]: "
            ).strip().lower()
            if confirm == "y":
                return p
        else:
            print(f"경로가 존재하지 않습니다: {p}")


# ── 모델 선택 ──────────────────────────────────────

def ask_model() -> str:
    print("\n── 기본 모델 ──\n")
    models = ["opus", "sonnet", "haiku"]
    for i, m in enumerate(models, 1):
        default = " (기본)" if i == 1 else ""
        print(f"  {i}. {m}{default}")
    print()

    while True:
        choice = input("선택 [1-3, Enter=opus]: ").strip() or "1"
        try:
            n = int(choice)
            if 1 <= n <= 3:
                return models[n - 1]
        except ValueError:
            pass
        print("다시 선택해주세요.")


# ── 플러그인 선택 ──────────────────────────────────

def ask_plugins() -> list[str]:
    print("\n── 플러그인 그룹 선택 ──\n")

    for num, group in PLUGIN_GROUPS.items():
        count = len(group["plugins"])
        print(f"  {num}. {group['name']} ({count}개) — {group['desc']}")
    print(f"  5. 전체 선택")
    print()

    while True:
        choice = input("선택 (쉼표로 구분, 예: 1,2 또는 5=전체): ").strip()

        if choice == "5":
            all_plugins = []
            for g in PLUGIN_GROUPS.values():
                all_plugins.extend(g["plugins"])
            return all_plugins

        try:
            nums = [int(x.strip()) for x in choice.split(",")]
            if all(1 <= n <= 4 for n in nums):
                selected = []
                for n in nums:
                    selected.extend(PLUGIN_GROUPS[n]["plugins"])
                return selected
        except ValueError:
            pass

        print("다시 선택해주세요. (예: 1,3 또는 5)")


# ── 설정 생성 ──────────────────────────────────────

def generate_settings(
    vault_path: Path, selected_plugins: list[str], model: str
):
    """~/.claude/settings.json 생성."""
    statusline_path = str(CC_DIR / "statusline.sh")

    settings = {
        "env": {
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
        },
        "permissions": {
            "allow": [
                "Bash", "Read", "Edit", "Write", "WebFetch", "WebSearch",
            ],
            "deny": [
                "Bash(rm -rf /)",
                "Bash(rm -rf /*)",
                "Bash(rm -rf ~)",
                "Bash(rm -rf ~/*)",
            ],
            "ask": [
                "Bash(rm *)",
                "Bash(git push --force *)",
                "Bash(git push -f *)",
                "Bash(git reset --hard *)",
                "Bash(git clean -f *)",
                "Bash(git checkout -- .)",
                "Bash(git branch -D *)",
            ],
        },
        "model": model,
        "statusLine": {
            "type": "command",
            "command": statusline_path,
        },
        "enabledPlugins": {p: True for p in selected_plugins},
    }

    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

    # 기존 설정 백업
    if SETTINGS_FILE.exists():
        backup = SETTINGS_FILE.with_suffix(".json.bak")
        shutil.copy2(SETTINGS_FILE, backup)
        print(f"  기존 설정 백업 → {backup}")

    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False)
    )
    print(f"  ✓ {SETTINGS_FILE}")


def generate_config(vault_path: Path):
    """~/.claude/cc-config.json 생성 (머신별 설정)."""
    config = {
        "vault_root": str(vault_path),
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"  ✓ {CONFIG_FILE}")


# ── 의존성 확인 ────────────────────────────────────

def check_dependencies():
    missing = []
    if shutil.which("jq") is None:
        missing.append("jq — statusline에 필요 (brew install jq)")
    if shutil.which("git") is None:
        missing.append("git")
    if missing:
        print("\n주의: 누락된 의존성")
        for m in missing:
            print(f"  - {m}")


# ── main ───────────────────────────────────────────

def main():
    print("=" * 45)
    print("  Claude Code 환경 설정")
    print("=" * 45)
    print()

    vault_path = ask_vault_path()
    model = ask_model()
    selected_plugins = ask_plugins()

    # 요약
    print("\n── 설정 요약 ──\n")
    print(f"  Vault:    {vault_path}")
    print(f"  Model:    {model}")
    print(f"  Plugins:  {len(selected_plugins)}개")
    print(f"  Hooks:    (none)")
    print(f"  Scripts:  {CC_DIR}")
    print()

    confirm = input("적용? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("취소됨.")
        sys.exit(0)

    print("\n생성 중...\n")
    generate_settings(vault_path, selected_plugins, model)
    generate_config(vault_path)

    # statusline 실행 권한
    statusline = CC_DIR / "statusline.sh"
    if statusline.exists():
        statusline.chmod(0o755)
        print(f"  ✓ {statusline} (chmod +x)")

    check_dependencies()

    print("\n" + "=" * 45)
    print("  완료! Claude Code를 재시작하세요.")
    print("=" * 45)


if __name__ == "__main__":
    main()
