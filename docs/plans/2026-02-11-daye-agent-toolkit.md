# daye-agent-toolkit 구축 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 개인 범용 스킬 전용 빈 레포를 만들어 Claude Code + OpenClaw 양쪽에서 접근 가능하게 구성. 추가로 외부 마켓플레이스 플러그인도 `skills.json` 매니페스트로 선언적 관리.

**Architecture:**
- 스킬 없는 빈 레포로 시작 (추후 사용자가 선택적으로 추가)
- `skills.json` 매니페스트로 로컬 스킬 + 외부 플러그인 + OpenClaw 설정을 한 곳에서 선언
- `setup.sh`가 매니페스트를 읽어 환경별 설치를 자동화
- 새 머신에서 `./setup.sh`만 실행하면 전체 스킬 환경 재현

**Tech Stack:** Claude Code Plugin System, SKILL.md (Agent Skills 표준), bash, python3 (json 파싱), git, gh CLI

---

## 접근 방식

| 환경 | 위치 | 접근 방식 |
|------|------|-----------|
| Claude Code | 로컬 Mac | `setup.sh` → 마켓플레이스 등록 + 외부 플러그인 설치 + 로컬 스킬 symlink |
| OpenClaw | 원격 서버 | `setup.sh --openclaw` → `~/.openclaw/openclaw.json`의 `skills.load.extraDirs` 자동 설정 |

---

## 최종 디렉토리 구조

```
daye-agent-toolkit/
├── .claude-plugin/
│   └── marketplace.json          # Claude Code 마켓플레이스 매니페스트
├── .claude/
│   └── settings.local.json       # (기존 — 유지, gitignore됨)
├── .gitignore
├── CLAUDE.md                     # 스킬 작성 컨벤션 + 레포 가이드
├── README.md                     # 사용자 문서
├── skills.json                   # 스킬 매니페스트 (로컬 + 외부 + OpenClaw)
├── setup.sh                      # 환경 설치 스크립트
└── docs/plans/                   # 계획 문서
```

> 스킬은 아직 없음. 추후 사용자가 선택적으로 추가.

---

## Task 1: 레포 기본 구조 생성

**Files:**
- Modify: `.claude-plugin/marketplace.json` (이전 실행에서 생성됨 — 내용 확인)
- Verify: `.gitignore` (이전 실행에서 생성됨 — 내용 확인)
- Keep: `.claude/settings.local.json` (기존 유지)

**Step 1: marketplace.json 확인 (빈 plugins 배열)**

`.claude-plugin/marketplace.json` — 이미 생성됨, 내용 확인:
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "daye-agent-toolkit",
  "version": "1.0.0",
  "description": "Daye's personal agent toolkit - general-purpose skills for Claude Code and OpenClaw",
  "owner": {
    "name": "Daye Jeong"
  },
  "plugins": []
}
```

**Step 2: .gitignore 확인**

```
.DS_Store
*.swp
*.swo
*~
.claude/settings.local.json
```

**Step 3: 검증**

Run: `cat .claude-plugin/marketplace.json && cat .gitignore`
Expected: 위 내용과 일치

---

## Task 2: skills.json 매니페스트 작성

**Files:**
- Create: `skills.json`

**Step 1: skills.json 작성**

superpowers만 우선 등록. 추가 플러그인은 사용자가 점진적으로 추가.

```json
{
  "$comment": "daye-agent-toolkit 스킬 매니페스트. setup.sh가 이 파일을 읽어 환경을 구성합니다.",
  "local_skills": [],
  "marketplaces": [
    {
      "name": "claude-plugins-official",
      "source": "github",
      "repo": "anthropics/claude-plugins-official"
    }
  ],
  "plugins": [
    { "marketplace": "claude-plugins-official", "name": "superpowers" }
  ]
}
```

**Step 2: 검증**

Run: `python3 -c "import json; json.load(open('skills.json'))"`
Expected: 에러 없이 종료 (유효한 JSON)

---

## Task 3: setup.sh 작성

**Files:**
- Create: `setup.sh`

**Step 1: setup.sh 작성**

skills.json을 읽어서 환경별 설치를 자동화하는 스크립트:

```bash
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
LOCAL_COUNT=0
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
```

**Step 2: 실행 권한 부여**

```bash
chmod +x setup.sh
```

**Step 3: 검증**

Run: `bash -n setup.sh`
Expected: 문법 오류 없음

---

## Task 4: CLAUDE.md 작성

**Files:**
- Create: `CLAUDE.md`

**Step 1: CLAUDE.md 작성**

```markdown
# daye-agent-toolkit

개인 범용 스킬 전용 레포. Claude Code + OpenClaw 양쪽에서 사용.
외부 마켓플레이스 플러그인도 `skills.json`으로 선언적 관리.

## 접근 방식

| 환경 | 접근 방식 |
|------|-----------|
| Claude Code (로컬) | `./setup.sh` → 마켓플레이스 등록 + 플러그인 설치 + symlink |
| OpenClaw (원격) | `./setup.sh --openclaw` → extraDirs 설정 안내 |

## skills.json 매니페스트

모든 스킬 선언은 `skills.json`에서 관리:

- `local_skills`: 이 레포에 있는 SKILL.md 스킬 이름 배열
- `marketplaces`: 등록할 외부 마켓플레이스 목록
- `plugins`: 설치할 외부 플러그인 목록

새 스킬/플러그인 추가 시 skills.json을 수정하고 `./setup.sh` 재실행.

## 스킬 포맷

- `<skill-name>/SKILL.md` — 스킬 본문 (Claude Code + OpenClaw 공통)
- `<skill-name>/.claude-skill` — 스킬 메타데이터
- `<skill-name>/.claude-plugin/plugin.json` — Claude Code plugin (slash command 필요 시)
- `<skill-name>/commands/*.md` — Claude Code slash command (필요 시)

## 포맷 선택 기준

| 조건 | 포맷 |
|------|------|
| 슬래시 커맨드 불필요 | SKILL.md only |
| 슬래시 커맨드 필요 + OpenClaw도 사용 | Dual (SKILL.md + plugin.json) |
| Claude Code 전용 기능 (hooks, agents) | Plugin only |

## 새 스킬 추가 절차

1. `<skill-name>/` 디렉토리 생성
2. `SKILL.md` + `.claude-skill` 작성
3. slash command 필요 시: `.claude-plugin/plugin.json` + `commands/<name>.md` 추가
4. `skills.json`의 `local_skills`에 스킬 이름 추가
5. Plugin 포맷이면: `.claude-plugin/marketplace.json`의 `plugins`에도 추가
6. `./setup.sh` 실행
7. 커밋 + push (OpenClaw 원격 서버에 자동 반영)

## 외부 플러그인 추가 절차

1. `skills.json`의 `marketplaces`에 마켓플레이스 추가 (필요 시)
2. `skills.json`의 `plugins`에 플러그인 추가
3. `./setup.sh` 실행
4. 커밋

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- `{baseDir}/scripts/` 경로로 SKILL.md에서 참조

## 방침

- cube-claude-skills는 건드리지 않음
- 이 레포는 개인 범용 스킬만 관리
- Cube 업무용 스킬은 cube-claude-skills에 유지
```

---

## Task 5: README.md 작성

**Files:**
- Create: `README.md`

**Step 1: README.md 작성**

````markdown
# daye-agent-toolkit

Daye's personal agent toolkit — general-purpose skills for Claude Code and OpenClaw.

`skills.json` 매니페스트로 로컬 스킬 + 외부 플러그인을 선언적으로 관리.
새 머신에서 `./setup.sh`만 실행하면 전체 스킬 환경 재현.

## Setup

### Claude Code (로컬)

```bash
# 전체 환경 설치 (마켓플레이스 등록 + 플러그인 설치 + symlink)
./setup.sh

# 설치 상태 확인
./setup.sh --status
```

### OpenClaw (원격 서버)

```bash
# 1. 레포 클론
git clone https://github.com/daye-jjeong/daye-agent-toolkit.git ~/daye-agent-toolkit

# 2. extraDirs 설정 안내 보기
./setup.sh --openclaw

# 3. (선택) cron으로 자동 동기화
# */30 * * * * cd ~/daye-agent-toolkit && git pull --ff-only
```

## skills.json

```json
{
  "local_skills": ["my-skill"],
  "marketplaces": [
    { "name": "some-marketplace", "source": "github", "repo": "owner/repo" }
  ],
  "plugins": [
    { "marketplace": "some-marketplace", "name": "some-plugin" }
  ]
}
```

## Skills

현재 로컬 스킬 없음. 추후 선택적으로 추가.

## Cleanup

```bash
./setup.sh --clean
```
````

---

## Task 6: Git 초기화 + GitHub 레포 + 마켓플레이스 등록

**Step 1: Git 초기화 + 초기 커밋**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit
git init
git add .claude-plugin/marketplace.json .gitignore CLAUDE.md README.md skills.json setup.sh docs/
git commit -m "feat: initial daye-agent-toolkit setup

Personal agent toolkit with skills.json manifest for declarative
skill management across Claude Code and OpenClaw."
```

**Step 2: GitHub 레포 생성 + push**

```bash
gh repo create daye-jjeong/daye-agent-toolkit --public --source=. --push
```

**Step 3: Claude Code 마켓플레이스 등록**

```bash
claude plugin marketplace add /Users/dayejeong/git_workplace/daye-agent-toolkit
```

**Step 4: 검증**

Run: `claude plugin marketplace list`
Expected: `daye-agent-toolkit`이 목록에 포함

---

## Task 7: 전체 검증

**Step 1: setup.sh 문법 검증**

Run: `bash -n setup.sh`
Expected: 에러 없음

**Step 2: skills.json 유효성 검증**

Run: `python3 -c "import json; json.load(open('skills.json')); print('valid')"`
Expected: `valid`

**Step 3: 마켓플레이스 검증**

Run: `claude plugin marketplace list`
Expected: `daye-agent-toolkit` 포함

**Step 4: 레포 구조 검증**

Run: `ls -la /Users/dayejeong/git_workplace/daye-agent-toolkit/`
Expected: `.claude-plugin/`, `.gitignore`, `CLAUDE.md`, `README.md`, `skills.json`, `setup.sh`, `docs/`

**Step 5: GitHub 확인**

Run: `gh repo view daye-jjeong/daye-agent-toolkit`
Expected: 레포 정보 정상 출력

**Step 6: setup.sh --status 테스트**

Run: `./setup.sh --status`
Expected: 로컬 스킬 + 플러그인 상태 출력

---

## 요약

| Task | 내용 | 파일 수 |
|------|------|--------|
| 1 | 레포 기본 구조 확인 (marketplace.json, .gitignore) | 2 (기존) |
| 2 | skills.json 매니페스트 | 1 |
| 3 | setup.sh (매니페스트 기반 설치 스크립트) | 1 |
| 4 | CLAUDE.md | 1 |
| 5 | README.md | 1 |
| 6 | Git + GitHub + 마켓플레이스 | - |
| 7 | 전체 검증 | - |
