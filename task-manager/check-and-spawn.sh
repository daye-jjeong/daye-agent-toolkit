#!/bin/bash
# Task Manager Integration for Main Agent
# Usage: Call this from heartbeat, it outputs JSON with recommendation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run task manager and capture output
OUTPUT=$(node "$SCRIPT_DIR/index.js" 2>&1)

# Extract JSON from output (last line)
JSON_OUTPUT=$(echo "$OUTPUT" | grep -E '^\{' | tail -1)

if [ -n "$JSON_OUTPUT" ]; then
  echo "$JSON_OUTPUT"
  
  # Check if we got a READY status
  STATUS=$(echo "$JSON_OUTPUT" | jq -r '.status // empty')
  
  if [ "$STATUS" = "READY" ]; then
    # Return special exit code to signal main agent should spawn
    exit 10
  fi
fi

exit 0
