#!/bin/bash
# Stop hook: 워크플로우 보고 리마인드 (1회만)
# 세션당 한 번만 block하고, 이후는 통과

INPUT="$(cat 2>/dev/null || echo '{}')"
SID="$(echo "$INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4 | cut -c1-12 || true)"
[ -z "$SID" ] && exit 0

# 세션당 1회만 block
DEDUP_DIR="/tmp/claude-workflow-stop"
mkdir -p "$DEDUP_DIR"
DEDUP_FILE="${DEDUP_DIR}/${SID}"

if [ -f "$DEDUP_FILE" ]; then
  # 이미 한 번 리마인드했으므로 통과
  exit 0
fi

# 첫 번째 stop: 리마인드 + 마킹
echo "$(date +%s)" > "$DEDUP_FILE"
# 1시간 지난 dedup 파일 정리
find "$DEDUP_DIR" -type f -mmin +60 -delete 2>/dev/null || true

cat <<'HOOKJSON'
{
  "decision": "block",
  "reason": "워크플로우 보고 체크:\n1. 이번에 뭘 했는지 한 줄 요약\n2. M/L 작업이면: simplify + pr-review 돌렸는지\n3. 다음에 뭘 해야 하는지\n\n보고 후 다시 멈춰라."
}
HOOKJSON
