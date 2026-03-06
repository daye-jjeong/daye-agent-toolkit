#!/bin/bash
# Claude Code → Telegram 알림
# Hook에서 호출: notify.sh [event_type]
# 수동 테스트: echo '{}' | ./notify.sh permission "승인 대기"
#
# stop 이벤트는 session_logger.py가 LLM 요약과 함께 전송하므로
# 이 스크립트에서는 permission/idle/error만 처리한다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_FILE="$(dirname "$SCRIPT_DIR")/telegram.conf"

# telegram.conf 읽기
CHAT_ID=""
TOKEN=""
THREAD_SESSION=""
if [ -f "$CONF_FILE" ]; then
  while IFS='=' read -r key value; do
    key="$(echo "$key" | xargs)"
    value="$(echo "$value" | xargs)"
    case "$key" in
      BOT_TOKEN) TOKEN="$value" ;;
      CHAT_ID) CHAT_ID="$value" ;;
      THREAD_SESSION) THREAD_SESSION="$value" ;;
    esac
  done < <(grep -v '^#' "$CONF_FILE" | grep '=')
fi

[ -z "$TOKEN" ] || [ -z "$CHAT_ID" ] && exit 0

# stdin JSON 읽기 (hook에서 전달)
INPUT="$(cat 2>/dev/null || echo '{}')"

EVENT="${1:-notification}"
MSG="${2:-}"

# stop 이벤트는 session_logger.py가 처리 → 스킵
[ "$EVENT" = "stop" ] && exit 0

# JSON에서 session_id 추출
SID="$(echo "$INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4 | cut -c1-8)"
[ -z "$SID" ] && SID="manual"

# 중복 알림 방지: 같은 세션에서 30초 이내 재알림 스킵
DEDUP_DIR="/tmp/claude-notify-dedup"
mkdir -p "$DEDUP_DIR"
DEDUP_FILE="${DEDUP_DIR}/${SID}"
NOW=$(date +%s)
if [ -f "$DEDUP_FILE" ]; then
  LAST=$(cat "$DEDUP_FILE")
  DIFF=$((NOW - LAST))
  if [ "$DIFF" -lt 30 ]; then
    exit 0
  fi
fi
echo "$NOW" > "$DEDUP_FILE"
find "$DEDUP_DIR" -type f -mmin +60 -delete 2>/dev/null || true

# 이벤트별 기본 메시지 + 이모지
case "$EVENT" in
  permission) EMOJI="🔐"; [ -z "$MSG" ] && MSG="승인 대기 중" ;;
  idle)       EMOJI="⏳"; [ -z "$MSG" ] && MSG="입력 대기 중" ;;
  error)      EMOJI="❌"; [ -z "$MSG" ] && MSG="오류 발생" ;;
  *)          EMOJI="🔔"; [ -z "$MSG" ] && MSG="알림이 있습니다" ;;
esac

PROJECT="$(basename "${PWD:-unknown}")"
BRANCH="$(git branch --show-current 2>/dev/null || echo '-')"

TEXT="${EMOJI} *Claude Code* \`${SID}\`
${MSG}
📂 \`${PROJECT}\` (\`${BRANCH}\`)"

# 백그라운드 전송 — hook 블로킹 최소화
CURL_DATA=(-d chat_id="$CHAT_ID" -d text="$TEXT" -d parse_mode="Markdown")
[ -n "$THREAD_SESSION" ] && CURL_DATA+=(-d message_thread_id="$THREAD_SESSION")

curl -sf -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  "${CURL_DATA[@]}" \
  >/dev/null 2>&1 &

exit 0
