#!/bin/bash
# Claude Code → Telegram 알림
# Hook에서 호출: notify.sh [event_type]
# 수동 테스트: echo '{}' | ./notify.sh permission "승인 대기"
#
# stop 이벤트는 session_logger.py가 LLM 요약과 함께 전송하므로
# 이 스크립트에서는 Notification만 처리한다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_FILE="$(dirname "$SCRIPT_DIR")/telegram.conf"

# telegram.conf 읽기
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

# 세션 채널 우선, fallback 기본 CHAT_ID
[ -n "$CHAT_ID_SESSION" ] && CHAT_ID="$CHAT_ID_SESSION"
[ -z "$TOKEN" ] || [ -z "$CHAT_ID" ] && exit 0

# stdin JSON 읽기 (hook에서 전달)
INPUT="$(cat 2>/dev/null || echo '{}')"

EVENT="${1:-notification}"
MSG="${2:-}"

# stop 이벤트는 session_logger.py가 처리 → 스킵
[ "$EVENT" = "stop" ] && exit 0

# JSON에서 필드 추출 (grep 실패 시 빈 문자열)
SID="$(echo "$INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4 | cut -c1-8 || true)"
[ -z "$SID" ] && SID="manual"

# stdin JSON에서 notification 상세 정보 추출
NOTIF_TYPE="$(echo "$INPUT" | grep -o '"notification_type":"[^"]*"' | cut -d'"' -f4 || true)"
TRANSCRIPT="$(echo "$INPUT" | grep -o '"transcript_path":"[^"]*"' | cut -d'"' -f4 || true)"

# transcript에서 마지막 assistant 텍스트 추출
LAST_MSG=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  # 마지막 assistant 메시지의 text 블록을 추출 (200자 제한)
  RAW="$(grep '"type":"assistant"' "$TRANSCRIPT" | tail -1 | grep -o '"text":"[^"]*"' | tail -1 | cut -d'"' -f4 | cut -c1-200 || true)"
  # JSON 이스케이프(\n, \t) → 실제 문자로 변환
  LAST_MSG="$(printf '%b' "$RAW")"
fi

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

# notification_type 기반 이모지/메시지 결정
case "${NOTIF_TYPE:-}" in
  permission_prompt)
    EMOJI="🔐"
    [ -z "$MSG" ] && MSG="승인 대기 중"
    ;;
  idle_prompt)
    EMOJI="⏳"
    [ -z "$MSG" ] && MSG="입력 대기 중"
    ;;
  *)
    case "$EVENT" in
      permission) EMOJI="🔐"; [ -z "$MSG" ] && MSG="승인 대기 중" ;;
      idle)       EMOJI="⏳"; [ -z "$MSG" ] && MSG="입력 대기 중" ;;
      error)      EMOJI="❌"; [ -z "$MSG" ] && MSG="오류 발생" ;;
      *)          EMOJI="🔔"; [ -z "$MSG" ] && MSG="알림이 있습니다" ;;
    esac
    ;;
esac

PROJECT="$(basename "${PWD:-unknown}")"
BRANCH="$(git branch --show-current 2>/dev/null || echo '-')"

# 마지막 어시스턴트 메시지 컨텍스트
CONTEXT=""
if [ -n "${LAST_MSG:-}" ]; then
  CONTEXT="
${LAST_MSG}"
fi

TEXT="${EMOJI} Claude Code ${SID}
${MSG}
📂 ${PROJECT} (${BRANCH})${CONTEXT}"

# 백그라운드 전송 — hook 블로킹 최소화
curl -sf -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=$CHAT_ID" \
  --data-urlencode "text=$TEXT" \
  >/dev/null 2>&1 &

exit 0
