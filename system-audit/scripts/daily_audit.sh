#!/bin/bash
# Daily System Audit — Tier 1 린트 → Tier 3 LLM 분석 하이브리드 파이프라인
# Cron: 0 9 * * * /Users/dayejeong/clawd/skills/system-audit/scripts/daily_audit.sh
#
# 1단계: lint_docs.py (Tier 1, 0토큰) → 구문 결과 JSON
# 2단계: clawdbot 세션 (Tier 3) → 의미 분석 + 세션/크론 감사
# 결과: memory/reports/audit/YYYY-MM-DD.md + Telegram (Critical만)

set -euo pipefail

DATE=$(date +"%Y-%m-%d")
TASK_LABEL="daily-audit-$DATE"
LOG_FILE="/tmp/daily-audit.log"
CLAWD_ROOT="$HOME/clawd"
SKILL_DIR="$CLAWD_ROOT/skills/system-audit"
REPORT_DIR="$CLAWD_ROOT/memory/reports/audit"
LINT_RESULT="/tmp/lint_result_${DATE}.json"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 리포트 디렉토리 보장
mkdir -p "$REPORT_DIR"

log "=== Daily Audit Start: $DATE ==="

# ─── 1단계: Tier 1 구문 린트 (0토큰) ───
log "Stage 1: Running lint_docs.py..."
python3 "$SKILL_DIR/scripts/lint_docs.py" --format json > "$LINT_RESULT" 2>/dev/null || true

LINT_ERRORS=$(python3 -c "import json,sys; d=json.load(open('$LINT_RESULT')); print(d.get('errors',0))" 2>/dev/null || echo "?")
LINT_WARNINGS=$(python3 -c "import json,sys; d=json.load(open('$LINT_RESULT')); print(d.get('warnings',0))" 2>/dev/null || echo "?")
log "Stage 1 done: ${LINT_ERRORS} errors, ${LINT_WARNINGS} warnings"

# ─── 2단계: Tier 3 LLM 의미 분석 ───
log "Stage 2: Spawning LLM session..."

# lint 결과를 프롬프트에 포함
LINT_SUMMARY=$(python3 -c "
import json, sys
try:
    d = json.load(open('$LINT_RESULT'))
    issues = d.get('issues', [])
    if not issues:
        print('구문 린트 통과 (이슈 없음)')
    else:
        for i in issues[:20]:
            sev = {'error':'🔴','warning':'⚠️','info':'ℹ️'}.get(i['severity'],'?')
            print(f\"{sev} [{i['check']}] {i['file']}:{i.get('line','')} — {i['message']}\")
        if len(issues) > 20:
            print(f'... 외 {len(issues)-20}건')
except Exception as e:
    print(f'린트 결과 파싱 실패: {e}')
" 2>/dev/null || echo "린트 결과 없음")

clawdbot sessions spawn \
  --agent main \
  --label "$TASK_LABEL" \
  --model "anthropic/claude-sonnet-4-5" \
  --task "매일 시스템 감사 ($DATE):

## 1단계 결과: 구문 린트 (자동 실행 완료)
$LINT_SUMMARY

## 2단계: LLM 의미 분석 (네가 할 일)

### A. 의미적 문서 분석
시스템 .md 파일 (AGENTS.md, HEARTBEAT.md, SOUL.md, TOOLS.md, CLAUDE.md)을 읽고:
- 정책 간 **의미적 충돌** 발견 (A 파일에선 X라 하고 B 파일에선 반대)
- **의미적 중복** 발견 (같은 개념을 다른 표현으로 두 군데 기술)
- **deprecated/outdated 정보** 판단 (현재 시스템 상태와 맞지 않는 내용)
- 1단계 린트에서 발견된 이슈의 **심각도 재분류** (False positive 필터링)

### B. 세션 감사
- sessions_list로 활성 세션 확인
- 24시간+ 오래된 세션 식별
- 정리 대상 제안

### C. 크론 감사
- crontab -l 실행 → 스크립트 경로 존재 + 실행 권한 확인
- 깨진 경로 발견 시 Critical

### D. 리포트 생성
- 파일: memory/reports/audit/$DATE.md
- 이전 감사 결과가 있으면 diff 비교
- 우선순위: Critical > High > Medium

### E. 알림
- Critical 문제만 Telegram JARVIS HQ 알림
- 정상 시 무음 (Telegram 전송 금지)"

log "=== Daily Audit Spawned: $TASK_LABEL ==="

# 린트 임시 파일 정리 (7일 후)
find /tmp -name "lint_result_*.json" -mtime +7 -delete 2>/dev/null || true
