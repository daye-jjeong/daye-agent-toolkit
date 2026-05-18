#!/bin/bash
# PreToolUse hook: git merge 전 체크리스트 리마인더 (어드바이저리 — 안 막음).
# git merge 감지 시 stderr로 체크리스트만 출력하고 exit 0. 워크플로우는 그대로 진행.
# 입력: stdin JSON (plan-review-gate.sh와 동일).

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[ "$TOOL_NAME" = "Bash" ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# 'git merge ...' 감지. macOS BSD grep 호환 위해 \s/\b 대신 [[:space:]] 사용.
# git mergetool 은 제외 (merge 뒤 공백/끝일 때만 매치).
if echo "$CMD" | grep -qE 'git[[:space:]]+merge([[:space:]]|$)'; then
  {
    echo "⚠ 머지 전 체크리스트 (리마인더 — 차단 안 함):"
    echo "  1. /simplify  2. pr-review-toolkit:review-pr"
    echo "  3. 변경 요약을 사용자에게 제시  4. 머지 승인"
    echo "  미완료면 먼저 완료 권장. 완료했으면 그대로 진행."
  } >&2
fi

exit 0
