#!/bin/bash
# Stop hook: 워크플로우 보고 리마인드 (1회만, non-blocking)
# 세션당 한 번만 리마인드하고, 이후는 통과. 멈추는 것을 막지 않음.

INPUT="$(cat 2>/dev/null || echo '{}')"
SID="$(echo "$INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4 | cut -c1-12 || true)"
[ -z "$SID" ] && exit 0

# 세션당 1회만
DEDUP_DIR="/tmp/claude-workflow-stop"
mkdir -p "$DEDUP_DIR"
DEDUP_FILE="${DEDUP_DIR}/${SID}"

if [ -f "$DEDUP_FILE" ]; then
  exit 0
fi

echo "$(date +%s)" > "$DEDUP_FILE"
find "$DEDUP_DIR" -type f -mmin +60 -delete 2>/dev/null || true

# non-blocking 리마인드: stopReason으로 메시지 전달, 멈추는 건 허용
cat <<'HOOKJSON'
{
  "stopReason": "워크플로우 보고 리마인드: 뭘 했는지, 다음 뭔지 보고했는지 확인하라."
}
HOOKJSON
