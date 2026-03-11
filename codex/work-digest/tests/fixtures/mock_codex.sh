#!/bin/bash

set -euo pipefail

ARGS_FILE="${MOCK_CODEX_ARGS_FILE:?}"
SESSION_ROOT="${CODEX_SESSION_ROOT:?}"
TRANSCRIPT_PATH="${MOCK_CODEX_TRANSCRIPT_PATH:-$SESSION_ROOT/2026/03/10/mock-session.jsonl}"
SESSION_ID="${MOCK_CODEX_SESSION_ID:-019cd9ff-aaaa-7bbb-8ccc-abcdef123456}"
MODE="${MOCK_CODEX_TRANSCRIPT_MODE:-none}"
EXIT_CODE="${MOCK_CODEX_EXIT_CODE:-0}"
DELAY_SEC="${MOCK_CODEX_DELAY_SEC:-0.1}"

mkdir -p "$(dirname "$TRANSCRIPT_PATH")"
printf '%s\n' "$*" > "$ARGS_FILE"
cat > "$TRANSCRIPT_PATH" <<EOF
{"timestamp":"2026-03-10T15:00:00.000Z","type":"session_meta","payload":{"id":"$SESSION_ID","timestamp":"2026-03-10T15:00:00.000Z","cwd":"$PWD","originator":"codex_cli_rs","cli_version":"0.112.0"}}
{"timestamp":"2026-03-10T15:00:01.000Z","type":"event_msg","payload":{"type":"user_message","message":"wrapper 테스트를 실행해.","images":[],"local_images":[],"text_elements":[]}}
EOF

if [ "$MODE" = "compaction" ]; then
  sleep "$DELAY_SEC"
  cat >> "$TRANSCRIPT_PATH" <<'EOF'
{"timestamp":"2026-03-10T15:00:02.000Z","type":"compacted","payload":{"message":"","replacement_history":[{"type":"message","role":"user","content":[{"type":"input_text","text":"wrapper compaction test"}]}]}}
{"timestamp":"2026-03-10T15:00:02.050Z","type":"event_msg","payload":{"type":"context_compacted"}}
EOF
fi

sleep "$DELAY_SEC"
exit "$EXIT_CODE"
