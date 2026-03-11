#!/bin/bash
# Codex CLI notify hook -> Telegram

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIGEST_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONF_FILE="${TELEGRAM_CONF_PATH:-$WORK_DIGEST_DIR/telegram.conf}"
FALLBACK_CONF="$REPO_ROOT/cc/work-digest/telegram.conf"

if [ ! -f "$CONF_FILE" ] && [ -f "$FALLBACK_CONF" ]; then
  CONF_FILE="$FALLBACK_CONF"
fi

PAYLOAD_RAW="${1:-}"
if [ -z "$PAYLOAD_RAW" ]; then
  PAYLOAD_RAW="$(cat 2>/dev/null || true)"
fi
[ -n "$PAYLOAD_RAW" ] || exit 0

PARSED_JSON="$(
PAYLOAD="$PAYLOAD_RAW" python3 - <<'PY'
import json
import os
import re


def looks_like_question(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    patterns = [
        "?",
        "할까요",
        "할지",
        "원하나요",
        "괜찮나요",
        "맞나요",
        "do you want",
        "would you like",
        "should i",
        "can i",
    ]
    return any(pattern in lowered for pattern in patterns)


def looks_like_progress(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    patterns = [
        "다음으로",
        "이제",
        "하겠습니다",
        "진행 중",
        "살펴보겠습니다",
        "확인하겠습니다",
        "구현하겠습니다",
        "moving on",
        "next",
        "will implement",
        "i'll",
    ]
    return any(pattern in lowered for pattern in patterns)


def looks_like_completion(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    patterns = [
        "완료",
        "마쳤",
        "구현했",
        "추가했",
        "정리했",
        "수정했",
        "연결했",
        "남겼",
        "기록했",
        "fixed",
        "implemented",
        "completed",
        "updated",
        "done",
    ]
    return any(pattern in lowered for pattern in patterns)


raw = os.environ.get("PAYLOAD", "").strip()
if not raw:
    print(json.dumps({"send": False}))
    raise SystemExit(0)

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print(json.dumps({"send": False}))
    raise SystemExit(0)

event_type = str(payload.get("type", "")).strip()
thread_id = str(payload.get("thread-id") or payload.get("thread_id") or "").strip()
cwd = str(payload.get("cwd", "")).strip()
last_message = str(
    payload.get("last-assistant-message")
    or payload.get("last_assistant_message")
    or ""
).strip()
input_messages = payload.get("input-messages") or payload.get("input_messages") or []
if not isinstance(input_messages, list):
    input_messages = []

send = False
label = ""
reason = ""

if event_type == "approval-requested":
    send = True
    label = "승인 필요"
    reason = "approval"
elif event_type == "user-input-requested":
    send = True
    label = "확인 필요"
    reason = "question"
elif event_type == "agent-turn-complete":
    if looks_like_question(last_message):
        send = True
        label = "확인 필요"
        reason = "question"
    elif looks_like_progress(last_message):
        send = False
    elif looks_like_completion(last_message):
        send = True
        label = "작업 완료"
        reason = "completion"

print(
    json.dumps(
        {
            "send": send,
            "label": label,
            "reason": reason,
            "event_type": event_type,
            "thread_id": thread_id,
            "cwd": cwd,
            "last_message": last_message,
            "input_message": next((str(item).strip() for item in input_messages if str(item).strip()), ""),
        },
        ensure_ascii=False,
    )
)
PY
)"

SEND_FLAG="$(printf '%s' "$PARSED_JSON" | python3 -c 'import json,sys; print("1" if json.load(sys.stdin).get("send") else "0")')"
[ "$SEND_FLAG" = "1" ] || exit 0

THREAD_ID="$(printf '%s' "$PARSED_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("thread_id",""))')"
LABEL="$(printf '%s' "$PARSED_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("label",""))')"
CWD_VALUE="$(printf '%s' "$PARSED_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("cwd",""))')"
LAST_MESSAGE="$(printf '%s' "$PARSED_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("last_message",""))')"
INPUT_MESSAGE="$(printf '%s' "$PARSED_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("input_message",""))')"

STATE_DIR="${NOTIFY_STATE_DIR:-/tmp/codex-notify-dedup}"
mkdir -p "$STATE_DIR"
DEDUP_HASH="$(
THREAD_ID="$THREAD_ID" LABEL="$LABEL" LAST_MESSAGE="$LAST_MESSAGE" python3 - <<'PY'
import hashlib
import os

key = "|".join(
    [
        os.environ.get("THREAD_ID", ""),
        os.environ.get("LABEL", ""),
        os.environ.get("LAST_MESSAGE", ""),
    ]
)
print(hashlib.sha1(key.encode("utf-8")).hexdigest())
PY
)"
DEDUP_FILE="$STATE_DIR/$DEDUP_HASH"
NOW_TS="${NOTIFY_NOW:-$(date +%s)}"

if [ -f "$DEDUP_FILE" ]; then
  LAST_TS="$(cat "$DEDUP_FILE" 2>/dev/null || echo 0)"
  if [ $((NOW_TS - LAST_TS)) -lt 30 ]; then
    exit 0
  fi
fi
printf '%s' "$NOW_TS" > "$DEDUP_FILE"
find "$STATE_DIR" -type f -mmin +60 -delete 2>/dev/null || true

PROJECT="$(basename "${CWD_VALUE:-${PWD:-unknown}}")"
BRANCH=""
if [ -n "$CWD_VALUE" ]; then
  BRANCH="$(git -C "$CWD_VALUE" branch --show-current 2>/dev/null || true)"
fi

TEXT="[Codex] ${LABEL}
${PROJECT}${BRANCH:+ ($BRANCH)}
${LAST_MESSAGE}"

if [ -n "$INPUT_MESSAGE" ] && [ "$LABEL" = "승인 필요" ]; then
  TEXT="${TEXT}
요청: ${INPUT_MESSAGE}"
fi

if [ "${TELEGRAM_DRY_RUN:-0}" = "1" ]; then
  printf '%s\n' "$TEXT"
  exit 0
fi

CHAT_ID=""
CHAT_ID_SESSION=""
TOKEN=""
if [ -f "$CONF_FILE" ]; then
  while IFS='=' read -r key value; do
    key="$(echo "$key" | xargs)"
    value="$(echo "$value" | xargs)"
    case "$key" in
      BOT_TOKEN) TOKEN="$value" ;;
      CHAT_ID) CHAT_ID="$value" ;;
      CHAT_ID_SESSION) CHAT_ID_SESSION="$value" ;;
    esac
  done < <(grep -v '^#' "$CONF_FILE" | grep '=')
fi

[ -n "$CHAT_ID_SESSION" ] && CHAT_ID="$CHAT_ID_SESSION"
[ -n "$TOKEN" ] && [ -n "$CHAT_ID" ] || exit 0

curl -sf -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=$CHAT_ID" \
  --data-urlencode "text=$TEXT" \
  >/dev/null 2>&1 &

exit 0
