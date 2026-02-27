#!/bin/bash
# setup.sh — daye-agent-toolkit 환경 설치 스크립트
#
# Claude Code:
#   1. 환경 설정 (인터랙티브: vault 경로, 모델, 플러그인 선택)
#   2. 마켓플레이스 등록 + 플러그인 설치
#   3. 로컬 스킬 symlink
#
# OpenClaw:
#   git clone + 스킬 enable + cron (비대화)
#
# Usage:
#   ./setup.sh                # Claude Code 전체 셋업 (인터랙티브)
#   ./setup.sh --skip-env     # CC 환경 설정 건너뛰고 스킬만 설치
#   ./setup.sh --openclaw     # OpenClaw PC: clone + enable + cron
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
  REPO_URL="https://github.com/daye-jjeong/daye-agent-toolkit.git"
  SKILLS_TARGET="$HOME/openclaw/skills"

  echo "=== daye-agent-toolkit OpenClaw setup ==="
  echo ""

  # 1. 기존 skills 디렉토리 처리
  echo "── skills 디렉토리 ──"
  if [ -d "$SKILLS_TARGET" ]; then
    if [ -d "$SKILLS_TARGET/.git" ]; then
      # 이미 git repo — remote 확인
      current_remote=$(git -C "$SKILLS_TARGET" remote get-url origin 2>/dev/null || echo "")
      if echo "$current_remote" | grep -q "daye-agent-toolkit"; then
        echo "✓ 이미 daye-agent-toolkit clone"
        echo "  pulling latest..."
        git -C "$SKILLS_TARGET" pull --rebase origin main
        echo ""
      else
        # 다른 repo — 백업 후 재clone
        backup="$SKILLS_TARGET.bak.$(date +%Y%m%d%H%M%S)"
        echo "⚠ 다른 repo 감지: $current_remote"
        echo "  백업: $backup"
        mv "$SKILLS_TARGET" "$backup"
        git clone "$REPO_URL" "$SKILLS_TARGET"
        echo "✓ clone 완료"
      fi
    else
      # git repo가 아닌 일반 디렉토리 — 백업 후 clone
      backup="$SKILLS_TARGET.bak.$(date +%Y%m%d%H%M%S)"
      echo "기존 skills 백업: $backup"
      mv "$SKILLS_TARGET" "$backup"
      git clone "$REPO_URL" "$SKILLS_TARGET"
      echo "✓ clone 완료"
    fi
  else
    # skills 디렉토리 없음 — 새로 clone
    mkdir -p "$(dirname "$SKILLS_TARGET")"
    git clone "$REPO_URL" "$SKILLS_TARGET"
    echo "✓ clone 완료"
  fi
  echo ""

  # 2. ~/openclaw/.gitignore에 skills/ 추가
  echo "── .gitignore ──"
  CLAWD_GITIGNORE="$HOME/openclaw/.gitignore"
  if [ -f "$CLAWD_GITIGNORE" ]; then
    if grep -qF "skills/" "$CLAWD_GITIGNORE"; then
      echo "✓ skills/ 이미 제외됨"
    else
      echo "skills/" >> "$CLAWD_GITIGNORE"
      echo "✓ skills/ 추가"
    fi
  else
    echo "skills/" > "$CLAWD_GITIGNORE"
    echo "✓ .gitignore 생성 + skills/ 추가"
  fi
  echo ""

  # 3. openclaw.json 스킬 entries 설정
  echo "── 스킬 enable 설정 ──"
  OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
  mkdir -p "$HOME/.openclaw"

  # OpenClaw에서 로드할 스킬 목록 (Claude Code 전용 제외)
  ENABLED_SKILLS=(
    banksalad-import check-integrations doc-lint
    health-coach health-tracker investment-report investment-research
    meal-tracker news-brief notion openclaw-docs orchestrator
    pantry-manager prompt-guard quant-swing saju-manse
    session-manager skill-forge taling-auto-monitor
    task-dashboard task-manager task-policy
  )

  # Claude Code 전용 → OpenClaw에서 비활성화
  DISABLED_SKILLS=(mermaid-diagrams professional-communication)

  python3 -c "
import json, os

config_path = '$OPENCLAW_CONFIG'
if os.path.exists(config_path):
    with open(config_path) as f:
        config = json.load(f)
else:
    config = {}

skills = config.setdefault('skills', {})
entries = skills.setdefault('entries', {})

enabled = '${ENABLED_SKILLS[*]}'.split()
disabled = '${DISABLED_SKILLS[*]}'.split()

for name in enabled:
    entries.setdefault(name, {})['enabled'] = True
for name in disabled:
    entries.setdefault(name, {})['enabled'] = False

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print(f'✓ enabled: {len(enabled)}개, disabled: {len(disabled)}개')
"
  echo ""

  # 4. cron 자동 pull 설정 (선택)
  CRON_CMD="*/30 * * * * cd $SKILLS_TARGET && python3 scripts/sync.py pull >> /tmp/skill-sync.log 2>&1"

  echo "── 자동 동기화 ──"
  if crontab -l 2>/dev/null | grep -qF "scripts/sync.py"; then
    echo "✓ cron 이미 설정됨"
  else
    echo "30분마다 auto-pull cron을 추가할까요? (y/N)"
    read -r answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
      (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
      echo "✓ cron 등록"
    else
      echo "→ 건너뜀. 수동 추가:"
      echo "  $CRON_CMD"
    fi
  fi

  echo ""
  echo "=== Done! ==="
  echo "  동기화: cd $SKILLS_TARGET && python3 scripts/sync.py"
  echo "  상태:   cd $SKILLS_TARGET && python3 scripts/sync.py status"
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
echo "=== daye-agent-toolkit setup (Claude Code) ==="
echo ""

# 0. 환경 설정 (인터랙티브)
SETUP_ENV="$REPO_DIR/_cc/setup_env.py"
if [ "${1:-}" != "--skip-env" ]; then
  if [ -f "$HOME/.claude/settings.json" ]; then
    echo "── 환경 설정 ──"
    echo "기존 ~/.claude/settings.json 발견."
    read -p "환경을 다시 설정할까요? [y/N]: " reconfigure
    echo ""
    if [ "$reconfigure" = "y" ] || [ "$reconfigure" = "Y" ]; then
      python3 "$SETUP_ENV"
      echo ""
    else
      echo "→ 환경 설정 건너뜀"
      echo ""
    fi
  else
    python3 "$SETUP_ENV"
    echo ""
  fi
fi

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
echo ""
echo "설정 파일:"
echo "  ~/.claude/settings.json    (hooks, permissions, plugins, model)"
echo "  ~/.claude/cc-config.json   (vault 경로 등 머신별 설정)"
echo ""
echo "재설정: ./setup.sh"
echo "스킬만: ./setup.sh --skip-env"
