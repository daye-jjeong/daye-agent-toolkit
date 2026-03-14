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

elif [[ "$MODE" == "exec" ]]; then
	ARGS=("exec")

	[[ -n "$MODEL" ]] && ARGS+=("-m" "$MODEL")
	ARGS+=("--sandbox" "read-only")

	if [[ -z "$PROMPT" && -z "$FILE" ]]; then
		echo "Usage: call.sh --mode exec \"<prompt>\"" >&2
		exit 1
	fi

	# Build prompt via temp file to avoid ARG_MAX for large files
	TMPFILE=$(mktemp)
	trap 'rm -f "$TMPFILE"' EXIT

	if [[ -n "$FILE" ]]; then
		if [[ ! -f "$FILE" ]]; then
			echo "Error: File not found: $FILE" >&2
			exit 1
		fi
		printf 'File: %s\n```\n' "$FILE" > "$TMPFILE"
		cat "$FILE" >> "$TMPFILE"
		printf '\n```\n\n' >> "$TMPFILE"
	fi
	[[ -n "$PROMPT" ]] && printf '%s\n' "$PROMPT" >> "$TMPFILE"

	"$CODEX_BIN" "${ARGS[@]}" - < "$TMPFILE"
else
	echo "Error: Unknown mode '$MODE'. Use 'review' or 'exec'." >&2
	exit 1
fi
