#!/bin/bash

set -euo pipefail

LOG_FILE="${MOCK_SESSION_LOGGER_LOG:?}"
printf '%s\n' "$*" >> "$LOG_FILE"
