#!/bin/bash
# Claude Code → Telegram 알림
# Hook에서 호출: notify.sh [event_type]
# 수동 테스트: echo '{}' | ./notify.sh stop "빌드 완료"

set -euo pipefail

CHAT_ID="8514441011"
TOKEN="8584213613:AAE5h2B3m9hGD1nIMUmLvcTmSwJDph25lic"

# stdin JSON 읽기 (hook에서 전달)
INPUT="$(cat 2>/dev/null || echo '{}')"

# 토큰 없으면 조용히 종료
[ -z "$TOKEN" ] && exit 0

EVENT="${1:-notification}"
MSG="${2:-}"

# JSON에서 session_id + transcript_path 추출
SID="$(echo "$INPUT" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4 | cut -c1-8)"
[ -z "$SID" ] && SID="manual"
TRANSCRIPT="$(echo "$INPUT" | grep -o '"transcript_path":"[^"]*"' | cut -d'"' -f4)"

# transcript에서 마지막 텍스트 응답 추출 (100자 제한)
SUMMARY=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  SUMMARY="$(python3 -c "
import json,sys
with open('$TRANSCRIPT') as f:
    lines=f.readlines()
for line in reversed(lines):
    d=json.loads(line)
    if d.get('message',{}).get('role')!='assistant': continue
    for c in d['message']['content']:
        if c.get('type')=='text' and c['text'].strip():
            print(c['text'].strip().replace('\n',' ')[:100]); exit()
" 2>/dev/null)"
fi

# 이벤트별 기본 메시지 + 이모지
case "$EVENT" in
  stop)       EMOJI="✅"; [ -z "$MSG" ] && MSG="작업 완료 — 확인해주세요" ;;
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

# 작업 내용 요약 추가
if [ -n "$SUMMARY" ]; then
  TEXT="${TEXT}
💬 ${SUMMARY}"
fi

# 백그라운드 전송 — hook 블로킹 최소화
curl -sf -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="$TEXT" \
  -d parse_mode="Markdown" \
  >/dev/null 2>&1 &

exit 0
