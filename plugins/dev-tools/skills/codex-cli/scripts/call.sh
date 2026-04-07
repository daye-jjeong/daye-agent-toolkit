#!/usr/bin/env bash
set -euo pipefail

MODE="review"
MODEL=""
BASE=""
COMMIT=""
FILE=""
PROMPT=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--mode)   MODE="$2"; shift 2 ;;
		--model)  MODEL="$2"; shift 2 ;;
		--base)   BASE="$2"; shift 2 ;;
		--commit) COMMIT="$2"; shift 2 ;;
		--file)   FILE="$2"; shift 2 ;;
		*)        PROMPT="${PROMPT:+${PROMPT} }$1"; shift ;;
	esac
done

# Resolve real codex binary (skip wrapper if present)
resolve_codex() {
	if [[ -n "${CODEX_REAL_BIN:-}" && -x "${CODEX_REAL_BIN}" ]]; then
		printf '%s\n' "$CODEX_REAL_BIN"
		return 0
	fi
	# Check well-known paths, then fall back to PATH
	for candidate in /opt/homebrew/bin/codex /usr/local/bin/codex "$(command -v codex 2>/dev/null || true)"; do
		[[ -n "$candidate" && -x "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
	done
	echo "Error: codex is not installed." >&2
	echo "Install with: npm install -g @openai/codex" >&2
	exit 1
}

CODEX_BIN="$(resolve_codex)"

if [[ "$MODE" == "review" ]]; then
	ARGS=("review")

	# codex review doesn't support -m; use -c model="..." instead
	[[ -n "$MODEL" ]] && ARGS+=("-c" "model=\"$MODEL\"")
	[[ -n "$BASE" ]] && ARGS+=("--base" "$BASE")
	[[ -n "$COMMIT" ]] && ARGS+=("--commit" "$COMMIT")

	# Default: review uncommitted changes
	if [[ -z "$BASE" && -z "$COMMIT" ]]; then
		ARGS+=("--uncommitted")
	fi

	[[ -n "$PROMPT" ]] && ARGS+=("$PROMPT")

	"$CODEX_BIN" "${ARGS[@]}"

elif [[ "$MODE" == "adversarial" ]]; then
	# Adversarial review: challenges design decisions, tradeoffs, failure modes
	SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	ADV_PROMPT_FILE="${SCRIPT_DIR}/adversarial-prompt.md"
	if [[ ! -f "$ADV_PROMPT_FILE" ]]; then
		echo "Error: adversarial prompt not found: $ADV_PROMPT_FILE" >&2
		exit 1
	fi

	ADV_PROMPT="$(cat "$ADV_PROMPT_FILE")"
	[[ -n "$PROMPT" ]] && ADV_PROMPT="${ADV_PROMPT}"$'\n\n'"Additional focus: ${PROMPT}"

	if [[ -n "$FILE" ]]; then
		# File specified: use exec mode with adversarial prompt
		if [[ ! -f "$FILE" ]]; then
			echo "Error: File not found: $FILE" >&2
			exit 1
		fi
		ARGS=("exec")
		[[ -n "$MODEL" ]] && ARGS+=("-m" "$MODEL")
		ARGS+=("--sandbox" "read-only")
		ARGS+=("Read and analyze this file: $(realpath "$FILE")"$'\n\n'"${ADV_PROMPT}")
		"$CODEX_BIN" "${ARGS[@]}"
	else
		# No file: use codex review with adversarial prompt
		ARGS=("review")
		[[ -n "$MODEL" ]] && ARGS+=("-c" "model=\"$MODEL\"")
		[[ -n "$BASE" ]] && ARGS+=("--base" "$BASE")
		[[ -n "$COMMIT" ]] && ARGS+=("--commit" "$COMMIT")
		if [[ -z "$BASE" && -z "$COMMIT" ]]; then
			ARGS+=("--uncommitted")
		fi
		ARGS+=("$ADV_PROMPT")
		"$CODEX_BIN" "${ARGS[@]}"
	fi

elif [[ "$MODE" == "exec" ]]; then
	ARGS=("exec")

	[[ -n "$MODEL" ]] && ARGS+=("-m" "$MODEL")
	ARGS+=("--sandbox" "read-only")

	if [[ -z "$PROMPT" && -z "$FILE" ]]; then
		echo "Usage: call.sh --mode exec \"<prompt>\"" >&2
		exit 1
	fi

	FULL_PROMPT=""
	if [[ -n "$FILE" ]]; then
		if [[ ! -f "$FILE" ]]; then
			echo "Error: File not found: $FILE" >&2
			exit 1
		fi
		FULL_PROMPT="Read and analyze this file: $(realpath "$FILE")"
		[[ -n "$PROMPT" ]] && FULL_PROMPT="${FULL_PROMPT}"$'\n\n'"${PROMPT}"
	else
		FULL_PROMPT="$PROMPT"
	fi

	"$CODEX_BIN" "${ARGS[@]}" "$FULL_PROMPT"
else
	echo "Error: Unknown mode '$MODE'. Use 'review', 'adversarial', or 'exec'." >&2
	exit 1
fi
