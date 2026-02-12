#!/bin/bash
# Model Health Unified Runner
# Purpose: Consolidate check_model_health.sh + detect_model_fallback.sh into one 5-min runner
# Cron: */5 * * * * /Users/dayejeong/openclaw/skills/model-health-orchestrator/scripts/model_health_unified.sh
# Policy: Silent operation (no success logs), alerts only on state transitions/high risk

set -euo pipefail

# Configuration
CLAWD_ROOT="$HOME/openclaw"
SCRIPT_DIR="$CLAWD_ROOT/skills/model-health-orchestrator/scripts"
STATE_FILE="$CLAWD_ROOT/vault/state/model_health_unified.json"
DATA_TEMP="/tmp/model_health_data_$$.json"
GATEWAY_LOG="$HOME/.clawdbot/logs/gateway.log"
GATEWAY_ERR_LOG="$HOME/.clawdbot/logs/gateway.err.log"
AUTH_PROFILES="$HOME/.clawdbot/agents/main/agent/auth-profiles.json"
TELEGRAM_GROUP_ID="-1003242721592"  # JARVIS HQ

# Cleanup on exit
trap 'rm -f "$DATA_TEMP"' EXIT

# Ensure state directory exists
mkdir -p "$(dirname "$STATE_FILE")"

# Initialize state file if not exists
init_state() {
    if [ ! -f "$STATE_FILE" ]; then
        cat > "$STATE_FILE" <<'EOF'
{
  "lastCheck": 0,
  "health_state": "unknown",
  "quota_risk": "low",
  "cooldown_models": [],
  "available_models": [],
  "rate_limit_count_5min": 0,
  "last_alert_state": "unknown"
}
EOF
    fi
}

# Collect data sources
collect_data() {
    local now=$(date +%s)

    # 1) openclaw status --deep (best effort)
    local status_deep=""
    if command -v openclaw &> /dev/null; then
        status_deep=$(openclaw status --deep 2>/dev/null || echo "")
    fi

    # 2) auth profiles cooldown (best effort JSON string)
    local cooldown_data='{}'
    if [ -f "$AUTH_PROFILES" ]; then
        cooldown_data=$(python3 - <<'PY' "$AUTH_PROFILES" "$now"
import json,sys
p=sys.argv[1]
now_ms=int(sys.argv[2])*1000
out={}
try:
    d=json.load(open(p))
    usage=d.get('usageStats',{})
    for profile,stats in usage.items():
        c=int((stats or {}).get('cooldownUntil',0) or 0)
        if c>now_ms:
            out[profile]={"cooldown_until":c,"remaining_sec":int((c-now_ms)/1000)}
except Exception:
    pass
print(json.dumps(out, ensure_ascii=False))
PY
)
    fi

    # 3) gateway log patterns
    local rate_limit_count=0
    local failover_errors=0
    local all_cooldown_detected=false
    if [ -f "$GATEWAY_ERR_LOG" ]; then
        rate_limit_count=$(tail -100 "$GATEWAY_ERR_LOG" | grep -ci "rate_limit" || true)
        failover_errors=$(tail -100 "$GATEWAY_ERR_LOG" | grep -ci "FailoverError" || true)
        rate_limit_count=${rate_limit_count:-0}
        failover_errors=${failover_errors:-0}
        if tail -50 "$GATEWAY_ERR_LOG" | grep -qi "all.*in cooldown"; then
            all_cooldown_detected=true
        fi
    fi

    # 4) quota probe JSON (best effort)
    local quota_probe_data='{"quota_sources":{},"quota_confidence":"estimated","direct_quota_available":false}'
    if [ -f "$SCRIPT_DIR/quota_hybrid_probe.py" ]; then
        quota_probe_data=$(python3 "$SCRIPT_DIR/quota_hybrid_probe.py" 2>/dev/null || echo "$quota_probe_data")
    fi

    # 5) session token data — openclaw sessions --json --active 120 (last 2h)
    local session_json='[]'
    if command -v openclaw &> /dev/null; then
        session_json=$(openclaw sessions --json --active 120 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(json.dumps(d.get('sessions', []) if isinstance(d, dict) else d))
except Exception:
    print('[]')
" 2>/dev/null || echo '[]')
    fi

    # 6) Compose JSON robustly in python (avoid heredoc JSON breakage)
    python3 - <<'PY' "$DATA_TEMP" "$now" "$status_deep" "$cooldown_data" "$rate_limit_count" "$failover_errors" "$all_cooldown_detected" "$quota_probe_data" "$session_json"
import json,sys
out_path=sys.argv[1]
now=int(sys.argv[2])
status=sys.argv[3]
cooldown_raw=sys.argv[4]
rate=int(sys.argv[5] or 0)
fail=int(sys.argv[6] or 0)
all_cd=(str(sys.argv[7]).lower()=="true")
probe_raw=sys.argv[8]
sessions_raw=sys.argv[9]

def parse_obj(s, default):
    try:
        v=json.loads(s)
        return v if isinstance(v,dict) else default
    except Exception:
        return default

def parse_list(s):
    try:
        v=json.loads(s)
        return v if isinstance(v,list) else []
    except Exception:
        return []

obj={
  "timestamp": now,
  "status_deep": status,
  "cooldown_data": parse_obj(cooldown_raw, {}),
  "rate_limit_count": rate,
  "failover_errors": fail,
  "all_cooldown_detected": all_cd,
  "quota_probe": parse_obj(probe_raw, {"quota_sources":{},"quota_confidence":"estimated","direct_quota_available":False}),
  "sessions": parse_list(sessions_raw)
}
with open(out_path,'w',encoding='utf-8') as f:
    json.dump(obj,f,ensure_ascii=False)
PY
}

# Send Telegram alert
send_alert() {
    local message="$1"
    
    if [ -n "$message" ]; then
        clawdbot message send -t "$TELEGRAM_GROUP_ID" "$message" 2>/dev/null || {
            echo "[$(date)] Failed to send Telegram alert" >&2
        }
    fi
}

# Main execution
main() {
    init_state
    
    # Collect data from all sources
    collect_data
    
    # Analyze using Python helper and capture alert message
    # Analyze using Python helper
    # - stdout: alert message (only on transitions/high-risk)
    # - stderr: written to local file (no Telegram spam)
    local alert_message=""
    local err_log="/tmp/model_health_unified.err.log"
    alert_message=$(python3 "$SCRIPT_DIR/analyze_model_health.py" "$DATA_TEMP" "$STATE_FILE" 2>>"$err_log" || true)
    
    # Send alert only if needed (non-empty message)
    if [ -n "$alert_message" ]; then
        send_alert "$alert_message"
        # Also emit to stdout for cron visibility
        echo "$alert_message"
    fi
}

# Execute
main "$@"
