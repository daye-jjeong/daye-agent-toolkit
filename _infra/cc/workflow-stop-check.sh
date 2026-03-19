#!/bin/bash
# Stop hook: 워크플로우 보고 강제
# 모델이 멈추려 할 때 현재 위치 + 다음 행동 보고를 리마인드

# stdin에서 transcript 정보 읽기
INPUT="$(cat 2>/dev/null || echo '{}')"

# transcript에서 마지막 assistant 메시지 추출
TRANSCRIPT="$(echo "$INPUT" | grep -o '"transcript_path":"[^"]*"' | cut -d'"' -f4 || true)"

# 마지막 assistant 메시지에 보고 패턴이 있는지 체크
HAS_REPORT=false
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  # "태스크 N/N" 또는 "완료" 또는 "다음" 패턴 확인
  LAST_MSG="$(grep '"type":"assistant"' "$TRANSCRIPT" | tail -1 || true)"
  if echo "$LAST_MSG" | grep -qE '(태스크.*[0-9]+/[0-9]+|완료|다음.*진행|next step|다음 행동|worktree|finishing)'; then
    HAS_REPORT=true
  fi
fi

if [ "$HAS_REPORT" = false ]; then
  cat <<'HOOKJSON'
{
  "decision": "block",
  "reason": "워크플로우 보고 체크:\n1. 이번에 뭘 했는지 한 줄 요약\n2. M/L 작업이면: simplify + pr-review 돌렸는지\n3. 다음에 뭘 해야 하는지\n\n보고 없이 멈추지 마라."
}
HOOKJSON
fi

exit 0
