#!/bin/bash
# PreToolUse hook: git merge 전 리뷰 + 승인 확인.
# Bash tool에서 git merge 감지 시 차단(exit 2).
# 입력: stdin JSON (plan-review-gate.sh와 동일). $CLAUDE_TOOL_* env는
# Claude Code가 채우지 않아 no-op 됐었음 — stdin+jq로 교정.

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[ "$TOOL_NAME" = "Bash" ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# 'git merge ...' 감지. macOS BSD grep 호환 위해 \s/\b 대신 [[:space:]] 사용.
# git mergetool 은 제외 (merge 뒤 공백/끝일 때만 매치).
if echo "$CMD" | grep -qE 'git[[:space:]]+merge([[:space:]]|$)'; then
  # PreToolUse exit 2: stderr가 차단 사유로 모델에 전달됨.
  {
    echo "🛑 머지 전 체크리스트:"
    echo ""
    echo "  1. /simplify 실행했는가?"
    echo "  2. pr-review-toolkit:review-pr 실행했는가?"
    echo "  3. 변경 요약을 사용자에게 보여줬는가? (변경 파일, 뭘 바꿨는지, 어떤 효과)"
    echo "  4. 사용자에게 머지 승인을 받았는가?"
    echo ""
    echo "4개 모두 완료했으면 이 메시지를 무시하고 진행해도 됩니다."
    echo "하나라도 안 했으면 먼저 완료하세요."
  } >&2
  exit 2
fi

exit 0
