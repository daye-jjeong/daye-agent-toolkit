#!/bin/bash
# setup.sh — daye-agent-toolkit 환경 설치 스크립트
#
# skills.json 매니페스트를 읽어서:
#   - 로컬 SKILL.md 스킬 → ~/.claude/skills/ symlink
#   - 외부 마켓플레이스 등록 + 플러그인 설치
#   - 이 레포를 Claude Code 마켓플레이스에 등록
#
# Usage:
#   ./setup.sh                # Claude Code 환경 설치
#   ./setup.sh --openclaw     # OpenClaw extraDirs 설정 안내
#   ./setup.sh --clean        # symlink 제거
#   ./setup.sh --status       # 현재 설치 상태 확인

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_JSON="$REPO_DIR/skills.json"
SKILLS_DIR="$HOME/.claude/skills"

# ── helpers ──────────────────────────────────────
read_json() {
  python3 -c "
import json, sys
data = json.load(open('$SKILLS_JSON'))
$1
"
}

# ── --clean ──────────────────────────────────────
if [ "${1:-}" = "--clean" ]; then
  read_json "
for skill in data.get('local_skills', []):
    print(skill)
" | while read -r skill; do
    dest="$SKILLS_DIR/$skill"
    if [ -L "$dest" ]; then
      rm "$dest"
      echo "✓ removed $skill"
    fi
  done
  echo "Done. 외부 플러그인은 'claude plugin uninstall'로 개별 제거하세요."
  exit 0
fi

# ── --openclaw ───────────────────────────────────
if [ "${1:-}" = "--openclaw" ]; then
  echo "OpenClaw 설정 안내:"
  echo ""
  echo "~/.openclaw/openclaw.json에 다음을 추가하세요:"
  echo ""
  echo '  {'
  echo '    "skills": {'
  echo '      "load": {'
  echo "        \"extraDirs\": [\"$REPO_DIR\"],"
  echo '        "watch": true'
  echo '      }'
  echo '    }'
  echo '  }'
  echo ""
  echo "자동 동기화 (cron):"
  echo "  */30 * * * * cd $REPO_DIR && git pull --ff-only"
  exit 0
fi

# ── --status ─────────────────────────────────────
if [ "${1:-}" = "--status" ]; then
  echo "=== Local Skills ==="
  read_json "
for skill in data.get('local_skills', []):
    print(skill)
" | while read -r skill; do
    dest="$SKILLS_DIR/$skill"
    if [ -L "$dest" ]; then echo "  ✓ $skill (symlinked)"
    elif [ -d "$dest" ]; then echo "  ⚠ $skill (directory, not symlink)"
    else echo "  ✗ $skill (not installed)"
    fi
  done

  echo ""
  echo "=== Marketplace Plugins ==="
  echo "(claude plugin list 로 확인)"
  exit 0
fi

# ── main: Claude Code 설치 ───────────────────────
echo "=== daye-agent-toolkit setup ==="
echo ""

# 1. 이 레포를 마켓플레이스에 등록
echo "── 마켓플레이스 등록 ──"
if claude plugin marketplace list 2>/dev/null | grep -q "daye-agent-toolkit"; then
  echo "✓ daye-agent-toolkit 이미 등록됨"
else
  claude plugin marketplace add "$REPO_DIR" && echo "✓ daye-agent-toolkit 마켓플레이스 등록" || echo "⚠ 마켓플레이스 등록 실패"
fi
echo ""

# 2. 외부 마켓플레이스 등록
echo "── 외부 마켓플레이스 ──"
read_json "
for m in data.get('marketplaces', []):
    if m.get('source') == 'github':
        print(f\"github:{m['repo']}:{m['name']}\")
    elif m.get('source') == 'git':
        print(f\"git:{m['url']}:{m['name']}\")
" | while IFS=: read -r source repo_or_url name; do
  if claude plugin marketplace list 2>/dev/null | grep -q "$name"; then
    echo "✓ $name 이미 등록됨"
  else
    if [ "$source" = "github" ]; then
      claude plugin marketplace add --github "$repo_or_url" && echo "✓ $name 등록" || echo "⚠ $name 등록 실패"
    else
      claude plugin marketplace add --git "$repo_or_url" && echo "✓ $name 등록" || echo "⚠ $name 등록 실패"
    fi
  fi
done
echo ""

# 3. 외부 플러그인 설치
echo "── 외부 플러그인 설치 ──"
read_json "
for p in data.get('plugins', []):
    print(f\"{p['marketplace']}:{p['name']}\")
" | while IFS=: read -r marketplace name; do
  echo "→ $name ($marketplace)"
  claude plugin install "$marketplace" "$name" 2>/dev/null || echo "  ⚠ 이미 설치됨 또는 설치 실패"
done
echo ""

# 4. 로컬 SKILL.md 스킬 symlink
echo "── 로컬 스킬 symlink ──"
read_json "
for skill in data.get('local_skills', []):
    print(skill)
" | while read -r skill; do
  src="$REPO_DIR/$skill"
  dest="$SKILLS_DIR/$skill"

  if [ ! -d "$src" ]; then
    echo "⚠ skip: $skill (not found in repo)"
    continue
  fi

  mkdir -p "$SKILLS_DIR"

  if [ -L "$dest" ]; then rm "$dest"
  elif [ -d "$dest" ]; then
    echo "⚠ $skill: 기존 디렉토리 발견 — 수동 확인 필요"
    continue
  fi

  ln -s "$src" "$dest"
  echo "✓ $skill → $src"
done

echo ""
echo "=== Done! Claude Code를 재시작하면 반영됩니다. ==="
