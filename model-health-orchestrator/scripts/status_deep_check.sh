#!/bin/bash
# OpenClaw Status Deep Check - 주기적 시스템 종합 진단
# Cron: */15 9-22 * * * /Users/dayejeong/clawd/skills/model-health-orchestrator/scripts/status_deep_check.sh
#
# - openclaw status --deep 실행
# - critical/warn 파싱
# - 문제 발견 시 Telegram 알림
# - 정상 시 무음 (로컬 로그만)
# - --force: quiet hours 무시

LOG_FILE="/tmp/status_deep_check.log"
STATE_FILE="$HOME/clawd/memory/state/status_deep.json"
TELEGRAM_GROUP_ID="-1003242721592"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

notify() {
    local message="$1"
    clawdbot message send -t "$TELEGRAM_GROUP_ID" "$message" 2>/dev/null || true
    log "ALERT: $message"
}

# --force 플래그 체크
FORCE=0
[ "$1" = "--force" ] && FORCE=1

# 조용한 시간 체크 (23:00-08:00)
if [ "$FORCE" -eq 0 ]; then
    HOUR=$(date +%H)
    if [ "$HOUR" -ge 23 ] || [ "$HOUR" -lt 8 ]; then
        log "Quiet hours - skipping deep check"
        exit 0
    fi
fi

# status --deep 실행
OUTPUT=$(openclaw status --deep 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    notify "🔴 openclaw status --deep 실행 실패 (exit: $EXIT_CODE)"
    log "FAIL: exit code $EXIT_CODE"
    exit 1
fi

# Security audit 요약 파싱: "N critical · M warn · K info"
AUDIT_LINE=$(echo "$OUTPUT" | grep -o '[0-9]* critical' | head -1)
CRITICAL=${AUDIT_LINE%% *}
CRITICAL=${CRITICAL:-0}

WARN_LINE=$(echo "$OUTPUT" | grep -o '[0-9]* warn' | head -1)
WARN_COUNT=${WARN_LINE%% *}
WARN_COUNT=${WARN_COUNT:-0}

# Gateway 상태
GATEWAY_REACHABLE=1
if echo "$OUTPUT" | grep -qi "unreachable\|Gateway.*DOWN\|Gateway.*FAIL"; then
    GATEWAY_REACHABLE=0
fi

# 채널 상태
CHANNEL_ISSUES=$(echo "$OUTPUT" | grep -E "WARN|DOWN|FAIL" | grep -iv "security audit\|Summary\|reverse proxy\|models.*below" | head -5)

# 상태 JSON 저장
mkdir -p "$(dirname "$STATE_FILE")"
cat > "$STATE_FILE" << EOF
{
  "lastCheck": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "exitCode": $EXIT_CODE,
  "criticalCount": $CRITICAL,
  "warnCount": $WARN_COUNT,
  "gatewayReachable": $([ "$GATEWAY_REACHABLE" -eq 1 ] && echo "true" || echo "false"),
  "status": "$([ "$CRITICAL" -gt 0 ] || [ "$GATEWAY_REACHABLE" -eq 0 ] && echo "critical" || echo "ok")"
}
EOF

# 알림: critical > 0
if [ "$CRITICAL" -gt 0 ]; then
    DETAILS=$(echo "$OUTPUT" | grep -B1 -A2 "critical" | grep -v "Summary\|^--$" | head -10)
    notify "🔴 시스템 진단: ${CRITICAL}개 critical

$DETAILS"
    exit 0
fi

# 알림: Gateway unreachable
if [ "$GATEWAY_REACHABLE" -eq 0 ]; then
    GW_LINE=$(echo "$OUTPUT" | grep "Gateway " | head -1)
    notify "🔴 Gateway 접근 불가

$GW_LINE"
    exit 0
fi

# 정상 — 무음
log "OK: ${CRITICAL} critical, ${WARN_COUNT} warn, gateway reachable"
