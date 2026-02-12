#!/bin/bash
# Proactive Agent Cron Wrapper
# Runs proactive checks and handles errors gracefully
# Part of Internal Log Suppression Policy (2026-02-07)

set -euo pipefail

WORKSPACE="/Users/dayejeong/clawd"
SCRIPT="${WORKSPACE}/scripts/proactive_check.py"
LOG_FILE="/tmp/proactive_check.log"

cd "$WORKSPACE"

# Check if script exists
if [[ ! -f "$SCRIPT" ]]; then
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] ERROR: Script not found at $SCRIPT" >> "$LOG_FILE"
    exit 1
fi

# Run with timeout and log errors ONLY
if timeout 60s /Users/dayejeong/clawd/.venv/bin/python "$SCRIPT" >> "$LOG_FILE" 2>&1; then
    # SUCCESS: Log silently (no output to avoid status messages)
    # The script itself handles notifications for genuine issues
    :
else
    EXIT_CODE=$?
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] ERROR: Proactive check failed with exit code $EXIT_CODE" >> "$LOG_FILE"
    # NOTE: Critical failures are already alerted by the Python script
fi

# Rotate log if > 1MB
if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE") -gt 1048576 ]]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] Log rotated" >> "$LOG_FILE"
fi
