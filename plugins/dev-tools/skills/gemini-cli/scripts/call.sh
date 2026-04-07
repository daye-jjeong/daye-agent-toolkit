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
		*)       PROMPT="${PROMPT:+${PROMPT} }$1"; shift ;;
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
