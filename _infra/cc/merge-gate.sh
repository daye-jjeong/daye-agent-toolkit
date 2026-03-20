#!/bin/bash
# PreToolUse hook: git merge 전 리뷰 + 승인 확인
# Bash tool에서 git merge 명령 감지 시 차단 메시지 출력

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Bash tool만 체크
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

# git merge 명령 감지 (git merge, git merge --no-ff 등)
if echo "$TOOL_INPUT" | grep -qE 'git\s+merge\b'; then
  echo "🛑 머지 전 체크리스트:"
  echo ""
  echo "  1. /simplify 실행했는가?"
  echo "  2. pr-review-toolkit:review-pr 실행했는가?"
  echo "  3. 변경 요약을 사용자에게 보여줬는가? (변경 파일, 뭘 바꿨는지, 어떤 효과)"
  echo "  4. 사용자에게 머지 승인을 받았는가?"
  echo ""
  echo "4개 모두 완료했으면 이 메시지를 무시하고 진행해도 됩니다."
  echo "하나라도 안 했으면 먼저 완료하세요."
  exit 2
fi

exit 0
