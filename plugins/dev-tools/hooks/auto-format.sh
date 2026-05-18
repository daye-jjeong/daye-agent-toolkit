#!/bin/bash
# PostToolUse hook: Edit/Write/MultiEdit 직후 방금 편집된 단일 파일만 포맷.
# best-effort — 포매터 없거나 실패해도 조용히 통과(exit 0). PostToolUse라 차단 불가.
# minimal-scope: 방금 건드린 파일 하나만. 전체 포맷 금지.

set -u

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# 파일 경로 없거나 실재하지 않으면 통과
[ -z "$FILE_PATH" ] && exit 0
[ -f "$FILE_PATH" ] || exit 0

case "$FILE_PATH" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$FILE_PATH" >/dev/null 2>&1 || true
    fi
    ;;
  *.js|*.jsx|*.ts|*.tsx|*.json|*.md|*.css|*.scss|*.html|*.yaml|*.yml)
    # prettier가 PATH에 있을 때만. npx 폴백은 매 편집마다 콜드스타트라 의도적으로 제외.
    if command -v prettier >/dev/null 2>&1; then
      prettier --write "$FILE_PATH" >/dev/null 2>&1 || true
    fi
    ;;
esac

exit 0
