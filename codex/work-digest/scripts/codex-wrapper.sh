#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION_ROOT="${CODEX_SESSION_ROOT:-$HOME/.codex/sessions}"
SESSION_LOGGER="${CODEX_SESSION_LOGGER:-$SCRIPT_DIR/session_logger.py}"
POLL_INTERVAL="${CODEX_WRAPPER_POLL_INTERVAL:-1}"
DISCOVERY_TIMEOUT="${CODEX_WRAPPER_DISCOVERY_TIMEOUT:-10}"
START_TS="$(date +%s)"
WRAPPER_PATH="$SCRIPT_DIR/codex-wrapper.sh"
COMPACTION_FLAG="$(mktemp -t codex-compaction.XXXXXX)"

cleanup() {
  rm -f "$COMPACTION_FLAG"
}
trap cleanup EXIT

resolve_real_codex_bin() {
  if [ -n "${CODEX_REAL_BIN:-}" ] && [ -e "${CODEX_REAL_BIN}" ]; then
    printf '%s\n' "${CODEX_REAL_BIN}"
    return 0
  fi

  for candidate in "$(command -v codex 2>/dev/null || true)" /opt/homebrew/bin/codex /usr/local/bin/codex; do
    [ -n "$candidate" ] || continue
    [ -e "$candidate" ] || continue
    if [ "$(cd "$(dirname "$candidate")" && pwd)/$(basename "$candidate")" = "$WRAPPER_PATH" ]; then
      continue
    fi
    printf '%s\n' "$candidate"
    return 0
  done

  return 1
}

run_real_codex() {
  if [[ "$REAL_CODEX_BIN" == *.sh ]]; then
    bash "$REAL_CODEX_BIN" "$@"
  else
    "$REAL_CODEX_BIN" "$@"
  fi
}

run_session_logger() {
  local event="$1"
  local transcript_path="$2"
  local session_id="$3"
  local cwd_value="$4"

  [ -n "$transcript_path" ] || return 0
  [ -f "$transcript_path" ] || return 0

  if [[ "$SESSION_LOGGER" == *.py ]]; then
    python3 "$SESSION_LOGGER" --event "$event" --transcript-path "$transcript_path" --session-id "$session_id" --cwd "$cwd_value" || true
  elif [[ "$SESSION_LOGGER" == *.sh ]]; then
    bash "$SESSION_LOGGER" --event "$event" --transcript-path "$transcript_path" --session-id "$session_id" --cwd "$cwd_value" || true
  else
    "$SESSION_LOGGER" --event "$event" --transcript-path "$transcript_path" --session-id "$session_id" --cwd "$cwd_value" || true
  fi
}

discover_transcript() {
  SESSION_ROOT="$SESSION_ROOT" START_TS="$START_TS" python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["SESSION_ROOT"])
start_ts = float(os.environ["START_TS"])
if not root.exists():
    raise SystemExit(0)

candidates = []
for path in root.rglob("*.jsonl"):
    try:
        stat = path.stat()
    except OSError:
        continue
    if stat.st_mtime + 1 >= start_ts:
        candidates.append((stat.st_mtime, str(path)))

if not candidates:
    for path in root.rglob("*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        candidates.append((stat.st_mtime, str(path)))

if candidates:
    print(max(candidates)[1])
PY
}

extract_session_id() {
  local transcript_path="$1"
  TRANSCRIPT_PATH="$transcript_path" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["TRANSCRIPT_PATH"])
session_id = path.stem
try:
    with path.open() as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "session_meta":
                continue
            payload = entry.get("payload") or {}
            value = payload.get("id")
            if isinstance(value, str) and value.strip():
                session_id = value.strip()
                break
except OSError:
    pass

print(session_id)
PY
}

has_compaction() {
  local transcript_path="$1"
  TRANSCRIPT_PATH="$transcript_path" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["TRANSCRIPT_PATH"])
try:
    with path.open() as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "compacted":
                raise SystemExit(0)
            if entry.get("type") == "event_msg":
                payload = entry.get("payload") or {}
                if payload.get("type") == "context_compacted":
                    raise SystemExit(0)
except OSError:
    pass

raise SystemExit(1)
PY
}

monitor_compaction() {
  local cwd_value="$1"
  while true; do
    local transcript_path
    transcript_path="$(discover_transcript)"
    if [ -n "$transcript_path" ] && [ -f "$transcript_path" ] && [ ! -s "$COMPACTION_FLAG" ] && has_compaction "$transcript_path"; then
      local session_id
      session_id="$(extract_session_id "$transcript_path")"
      run_session_logger "compaction" "$transcript_path" "$session_id" "$cwd_value"
      printf '1' > "$COMPACTION_FLAG"
    fi
    sleep "$POLL_INTERVAL"
  done
}

REAL_CODEX_BIN="$(resolve_real_codex_bin || true)"
[ -n "$REAL_CODEX_BIN" ] || exit 127

CURRENT_CWD="$(pwd)"

monitor_compaction "$CURRENT_CWD" &
MONITOR_PID=$!

run_real_codex "$@" &
CODEX_PID=$!

EXIT_CODE=0
wait "$CODEX_PID" || EXIT_CODE=$?

kill "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" 2>/dev/null || true

TRANSCRIPT_PATH=""
DEADLINE=$(( $(date +%s) + DISCOVERY_TIMEOUT ))
while [ -z "$TRANSCRIPT_PATH" ] && [ "$(date +%s)" -le "$DEADLINE" ]; do
  TRANSCRIPT_PATH="$(discover_transcript)"
  [ -n "$TRANSCRIPT_PATH" ] && break
  sleep "$POLL_INTERVAL"
done

if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
  SESSION_ID="$(extract_session_id "$TRANSCRIPT_PATH")"
  if [ ! -s "$COMPACTION_FLAG" ] && has_compaction "$TRANSCRIPT_PATH"; then
    run_session_logger "compaction" "$TRANSCRIPT_PATH" "$SESSION_ID" "$CURRENT_CWD"
    printf '1' > "$COMPACTION_FLAG"
  fi
  run_session_logger "session_end" "$TRANSCRIPT_PATH" "$SESSION_ID" "$CURRENT_CWD"
fi

exit "$EXIT_CODE"
