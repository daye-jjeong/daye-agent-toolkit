#!/bin/bash
# Prompt Injection Guard
# 
# Scans incoming messages for prompt injection and jailbreak attempts.
# Used by gateway/agent before processing user messages.
#
# Usage:
#   ./scripts/guard_prompt_injection.sh "message text"
#   echo "message text" | ./scripts/guard_prompt_injection.sh
#   ./scripts/guard_prompt_injection.sh --dry-run "message text"
#
# Exit codes:
#   0 - Safe to process
#   1 - Blocked (threat detected)
#   2 - Error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$SCRIPT_DIR/.."
GUARD_SCRIPT="$SKILL_DIR/guard.py"

# Check if guard script exists
if [ ! -f "$GUARD_SCRIPT" ]; then
    echo "❌ Error: Prompt Guard not found at $GUARD_SCRIPT" >&2
    exit 2
fi

# Parse arguments
DRY_RUN=""
if [ "$1" = "--dry-run" ]; then
    DRY_RUN="--dry-run"
    shift
fi

# Get message text
if [ $# -gt 0 ]; then
    MESSAGE="$*"
else
    MESSAGE=$(cat)
fi

# Run guard
if python3 "$GUARD_SCRIPT" $DRY_RUN --message "$MESSAGE"; then
    # Safe
    exit 0
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 1 ]; then
        # Blocked
        echo "" >&2
        echo "⚠️  This message has been blocked by Prompt Guard." >&2
        echo "   If this is a false positive, please rephrase or contact admin." >&2
        echo "" >&2
        echo "   Log: ~/.clawdbot/agents/main/logs/prompt-guard.log" >&2
    fi
    exit $EXIT_CODE
fi
