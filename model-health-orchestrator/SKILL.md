---
name: model-health-orchestrator
description: 모델 헬스체크 + 세션 토큰 사용량 + 쿼터 리스크 통합 리포트
argument-hint: |
  Input sources (optional flags):
    --deep: Include openclaw status --deep
    --auth: Include auth-profiles cooldownUntil
    --logs: Include gateway logs (rate_limit/FailoverError)
    --queue: Include failed_tasks_queue

  Output: Unified Telegram report (session tokens + provider health + quota risk)
---

# model-health-orchestrator

**목적:** 모델 헬스 상태 모니터링, 세션 토큰 사용량 추적, 폴백 로직 분석, 쿼터 리스크 평가를 통합 수행하여 시스템 안정성 확보.

**스코프:** 모니터링 + 분석 + 권장사항 제공 (⚠️ **라우팅 실행은 하지 않음** - 권장만 제공).

---

## 🎯 핵심 기능

### 1. 입력 소스 통합
- `openclaw sessions --json --active 120`: **세션별 토큰 사용량** (모델별 그룹핑)
- `openclaw status --deep`: 모델별 상태, 에러율
- **auth-profiles cooldownUntil**: 모델별 쿨다운 타임스탬프
- **Gateway logs**: `rate_limit`, `FailoverError`, "all models in cooldown" 패턴
- **Real Inference Probes**: 각 provider별 실제 추론 경로 테스트

### 2. 통합 리포트 출력 (Telegram)

알림 발생 시 아래 형식의 통합 리포트를 Telegram으로 전송:

```
📊 세션 토큰 사용량 (20:00 기준)
📋 활성 세션: 46개 (최근 2시간)
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔵 Claude Haiku 4.5 (200k ctx)
• Cron: 12개 | ⚠️ 최대 100% (200k/200k)

🤖 GPT-5.3 Codex (272k ctx)
• 메인 세션: 24% 사용 (65k/272k)
• Cron: 31개 | 최대 32% (88k/272k)

🟢 Gemini 3 Pro (1000k ctx)
• Cron: 1개 | 최대 10% (101k/1000k)

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏥 시스템: ✅ 정상
• OpenAI (OAuth): ✅ healthy | 쿼터 ok
• OpenAI (Key): ✅ healthy | 쿼터 ok
• Anthropic: ✅ healthy | 쿼터 ok
• Gemini: ✅ healthy | 쿼터 ok

📈 쿼터 리스크: 🟢 low
🎯 활성 모델: openai-codex/gpt-5.3-codex

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Claude Haiku 4.5 세션 1개 100% 도달
```

### 3. 상태 JSON (내부)

`vault/state/model_health_unified.json`에 저장. `session_summary` 필드 추가:

```json
{
  "health_state": "healthy|degraded|critical",
  "quota_risk": "low|medium|high|critical",
  "max_session_pct": 100,
  "session_summary": {
    "claude-haiku-4-5": {
      "count": 12,
      "max_percent": 100,
      "context_tokens": 200000,
      "warning_count": 2,
      "full_count": 1
    }
  },
  "providers": { "..." : "..." }
}
```

---

## 🔍 분석 로직

### A. 세션 토큰 그룹핑 (v3 신규)
- `openclaw sessions --json --active 120` → 최근 2시간 세션 수집
- sessionId 기준 중복 제거 (run 키 vs base 키)
- 모델별 그룹핑: 메인 세션 / Cron 세션 구분
- 사용률 내림차순 정렬

### B. 쿨다운 체크
```python
for model in auth_profiles:
    if model.cooldownUntil > now():
        cooldown_models.append(model.name)
```

### C. 로그 패턴 분석
- **rate_limit 카운트**: 최근 5분 내 3회 이상 → `quota_risk: high`
- **FailoverError**: 폴백 실패 → `health_state: degraded`
- **"all in cooldown"**: 모든 모델 불능 → `health_state: critical`

### D. 헬스 상태 판정

| State | 조건 | 대응 |
|-------|------|------|
| **healthy** | Primary 정상, 폴백 2개 이상 가능 | 유지 |
| **degraded** | Primary 쿨다운, 폴백 1개 가능 | 폴백 권장 |
| **critical** | 모든 모델 쿨다운 또는 사용 가능 모델 0개 | 즉시 알림 |

---

## 📢 알림 정책

**알림 트리거:**
1. **상태 변화**: `healthy → degraded` / `degraded → critical` / `critical → healthy`
2. **High-risk 임계값**: `quota_risk: critical` + 사용 가능 모델 1개 이하
3. **Inference 실패**: provider inference probe 실패
4. **토큰 임계값** (v3): 세션 사용률이 처음으로 80% 돌파 시

**알림 억제:**
- 동일 상태 유지 시 알림 금지 (상태 변화에만 반응)
- 토큰 80% 경고는 최초 돌파 시 1회만 발생

**상태 저장:** `vault/state/model_health_unified.json` (이전 상태 비교용)

---

## 🔄 Cron 설정

```bash
*/5 * * * * /Users/dayejeong/openclaw/skills/model-health-orchestrator/scripts/model_health_unified.sh >> /tmp/model_health_unified.log 2>&1
*/15 9-22 * * * /Users/dayejeong/openclaw/skills/model-health-orchestrator/scripts/status_deep_check.sh >> /tmp/status_deep_check.log 2>&1
```

### 스킬 내 스크립트

| 스크립트 | 역할 | 호출 방식 |
|----------|------|-----------|
| `scripts/model_health_unified.sh` | 통합 헬스체크 + 세션 토큰 수집 | cron 5분 |
| `scripts/status_deep_check.sh` | openclaw 종합 진단 | cron 15분 (09-22시) |
| `scripts/analyze_model_health.py` | 상태 분석 + 통합 리포트 생성 | unified.sh에서 호출 |
| `scripts/quota_hybrid_probe.py` | 쿼터 소스 프로브 | unified.sh에서 호출 |

---

## 📚 참조 문서

- **임계값 설정**: `references/thresholds.md`
- **모델 폴백 체인**: `config/session-models.json`
- **Rate Limit 복구**: `docs/RATE_LIMIT_RECOVERY.md`
- **알림 정책**: `AGENTS.md` § 4 커뮤니케이션

---

**버전:** 3.0.0
**최초 작성:** 2026-02-12
**마지막 업데이트:** 2026-02-12
