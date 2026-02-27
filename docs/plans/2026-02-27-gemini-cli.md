# gemini-cli Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Gemini CLI를 래핑하는 범용 스킬 — 디자인 위임, 코드 리뷰, 범용 LLM 호출

**Architecture:** `shared/gemini-cli/` 디렉토리에 SKILL.md + call.sh 래퍼 + 모드별 프롬프트 템플릿 구성. call.sh가 `--mode`에 따라 references/prompts.md에서 시스템 프롬프트를 추출하여 `gemini -p`에 주입. 기존 reddit-fetch/youtube-fetch 패턴 준수.

**Tech Stack:** bash, python3 (stdlib only), gemini-cli

**Design doc:** `docs/plans/2026-02-27-gemini-cli-design.md`

---

### Task 1: Create references/prompts.md

**Files:**
- Create: `shared/gemini-cli/references/prompts.md`

**Step 1: Create the prompts file**

```markdown
## design

You are an expert UI/UX designer and visual artist.
Generate production-ready code (HTML/CSS/SVG) that is:
- Visually polished with modern aesthetics
- Responsive and accessible
- Using clean, semantic markup
- Creative and original — avoid generic/template-like designs

When asked for visual art (posters, banners, cards), produce SVG or HTML/CSS.
When asked for UI components or pages, produce complete HTML with inline CSS.
Always include the full, runnable code — not snippets or placeholders.

## review

You are a senior code reviewer.
Analyze the provided code and give constructive feedback on:
- Design quality (visual hierarchy, spacing, color)
- Code quality (structure, maintainability)
- Accessibility and responsiveness
- Specific improvement suggestions with code examples

Be direct and actionable. Prioritize high-impact issues.
```

**Step 2: Verify file exists**

Run: `cat shared/gemini-cli/references/prompts.md`
Expected: The content above is printed.

---

### Task 2: Create scripts/call.sh

**Files:**
- Create: `shared/gemini-cli/scripts/call.sh`

**Depends on:** Task 1 (prompts.md must exist for mode extraction)

**Step 1: Write call.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPTS_FILE="${SCRIPT_DIR}/../references/prompts.md"

PROMPT=""
MODE=""
MODEL="gemini-2.5-pro"
FILE=""
RAW=false

while [[ $# -gt 0 ]]; do
	case "$1" in
		--mode)  MODE="$2"; shift 2 ;;
		--model) MODEL="$2"; shift 2 ;;
		--file)  FILE="$2"; shift 2 ;;
		--raw)   RAW=true; shift ;;
		*)       PROMPT="$1"; shift ;;
	esac
done

if [[ -z "$PROMPT" ]]; then
	echo "Usage: call.sh [--mode design|review] [--model MODEL] [--file PATH] [--raw] \"<prompt>\"" >&2
	exit 1
fi

# Check gemini is installed
if ! command -v gemini &>/dev/null; then
	echo "Error: gemini-cli is not installed." >&2
	echo "Install with: npm install -g @google/gemini-cli" >&2
	exit 1
fi

# Extract system prompt for mode
SYSTEM_PROMPT=""
if [[ -n "$MODE" && -f "$PROMPTS_FILE" ]]; then
	SYSTEM_PROMPT=$(python3 -c "
import sys

mode = sys.argv[1]
content = open(sys.argv[2]).read()

# Find section starting with ## <mode>
marker = f'## {mode}'
start = content.find(marker)
if start == -1:
    sys.exit(0)

start = content.index('\n', start) + 1

# Find next ## or end of file
next_section = content.find('\n## ', start)
if next_section == -1:
    section = content[start:]
else:
    section = content[start:next_section]

print(section.strip())
" "$MODE" "$PROMPTS_FILE" 2>/dev/null) || true
fi

# Build the full prompt
FULL_PROMPT=""

if [[ -n "$SYSTEM_PROMPT" ]]; then
	FULL_PROMPT="${SYSTEM_PROMPT}

---

"
fi

# Append file content if provided
if [[ -n "$FILE" ]]; then
	if [[ ! -f "$FILE" ]]; then
		echo "Error: File not found: $FILE" >&2
		exit 1
	fi
	FILE_CONTENT=$(cat "$FILE")
	FULL_PROMPT="${FULL_PROMPT}File: ${FILE}
\`\`\`
${FILE_CONTENT}
\`\`\`

"
fi

FULL_PROMPT="${FULL_PROMPT}${PROMPT}"

# Call gemini
if $RAW; then
	gemini -m "$MODEL" -p "$FULL_PROMPT" --output-format json
else
	gemini -m "$MODEL" -p "$FULL_PROMPT"
fi
```

**Step 2: Make executable**

Run: `chmod +x shared/gemini-cli/scripts/call.sh`

**Step 3: Test dependency check**

Run: `bash shared/gemini-cli/scripts/call.sh 2>&1 || true`
Expected: Usage message printed to stderr.

**Step 4: Test basic call**

Run: `bash shared/gemini-cli/scripts/call.sh "Say hello in one word"`
Expected: Gemini responds with a greeting.

**Step 5: Test design mode**

Run: `bash shared/gemini-cli/scripts/call.sh --mode design "Create a minimal 404 page"`
Expected: Gemini returns HTML/CSS code for a 404 page.

---

### Task 3: Create .claude-skill

**Files:**
- Create: `shared/gemini-cli/.claude-skill`

**Step 1: Write .claude-skill**

```json
{
  "name": "gemini-cli",
  "version": "1.0.0",
  "description": "Gemini CLI 래퍼 — 디자인 위임, 코드 리뷰, 범용 LLM 호출",
  "entrypoint": "SKILL.md"
}
```

---

### Task 4: Create SKILL.md

**Files:**
- Create: `shared/gemini-cli/SKILL.md`

**Depends on:** Task 2 (call.sh interface finalized)

**Step 1: Write SKILL.md**

```markdown
---
name: gemini-cli
description: Gemini CLI 래퍼 — 디자인 위임, 코드 리뷰, 범용 LLM 호출. 사용자가 명시적으로 Gemini를 요청할 때만 사용.
---

# Gemini CLI

Gemini CLI를 통해 디자인, 리뷰, 범용 질문을 Gemini에게 위임합니다.

## When to Use

- **사용자가 "Gemini"를 명시적으로 언급할 때만** 사용
- Claude가 자의적으로 Gemini를 호출하지 않음
- 주 용도: 디자인 위임 (UI/UX, 시각적 아트)
- 부 용도: 코드/디자인 리뷰, 범용 질문

## Usage

### Design Mode — UI/UX + 시각적 아트

\`\`\`bash
{baseDir}/scripts/call.sh --mode design "대시보드 레이아웃 만들어줘"
{baseDir}/scripts/call.sh --mode design --file src/app.tsx "이 컴포넌트 리디자인"
\`\`\`

### Review Mode — Second Opinion

\`\`\`bash
{baseDir}/scripts/call.sh --mode review --file src/app.tsx "이 코드 리뷰해줘"
\`\`\`

### General — 범용 질문

\`\`\`bash
{baseDir}/scripts/call.sh "질문 내용"
\`\`\`

### Options

- `--mode design|review` — 모드 선택 (시스템 프롬프트 자동 주입)
- `--file PATH` — 파일 컨텍스트 포함
- `--model MODEL` — 모델 지정 (기본: gemini-2.5-pro)
- `--raw` — JSON 출력 (디버깅용)

## Post-Processing

Gemini 결과를 받은 후:
- **HTML/CSS/SVG 코드** → 파일로 저장하고 경로 안내
- **텍스트 리뷰** → 요약해서 사용자에게 전달
- **필요시** Claude가 결과를 검증하고 수정/보완

## Prerequisites

gemini-cli 설치 필요:
\`\`\`bash
npm install -g @google/gemini-cli
\`\`\`

## Extending Modes

새 모드 추가: `{baseDir}/references/prompts.md`에 `## <mode-name>` 섹션 추가.
```

---

### Task 5: Install and verify

**Depends on:** Tasks 1-4

**Step 1: Run make install-cc**

Run: `make install-cc`
Expected: `gemini-cli` symlink created in `~/.claude/skills/`.

**Step 2: Verify symlink**

Run: `ls -la ~/.claude/skills/gemini-cli`
Expected: Symlink pointing to `shared/gemini-cli`.

**Step 3: Commit**

```bash
git add shared/gemini-cli/
git commit -m "feat: add gemini-cli skill — design delegation, review, general LLM calls"
```
