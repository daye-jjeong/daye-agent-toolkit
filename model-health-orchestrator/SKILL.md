---
name: model-health-orchestrator
description: 모델 헬스 체크, 폴백 로직, 쿼터 리스크 평가를 수행하는 오케스트레이터
argument-hint: |
  Input sources (optional flags):
    --deep: Include openclaw status --deep
    --auth: Include auth-profiles cooldownUntil
    --logs: Include gateway logs (rate_limit/FailoverError)
    --queue: Include failed_tasks_queue
  
  Output: JSON {health_state, recommended_model, quota_risk, reason, next_action, should_alert}
---

# model-health-orchestrator

**목적:** 모델 헬스 상태 모니터링, 폴백 로직 분석, 쿼터 리스크 평가를 통합 수행하여 시스템 안정성 확보.

**스코프:** 모니터링 + 분석 + 권장사항 제공 (⚠️ **라우팅 실행은 하지 않음** - 권장만 제공).

---

## 🎯 핵심 기능

### 1. 입력 소스 통합
- `openclaw status --deep`: 모델별 상태, 토큰 사용량, 에러율
- **auth-profiles cooldownUntil**: 모델별 쿨다운 타임스탬프
- **Gateway logs**: `rate_limit`, `FailoverError`, "all models in cooldown" 패턴
- **failed_tasks_queue** (선택): 실패한 태스크 큐 (재시도 대상)
- **Real Inference Probes** (v2): 각 provider별 실제 추론 경로 테스트
  - OpenAI OAuth: `/v1/chat/completions` (minimal payload)
  - OpenAI API Key: `/v1/embeddings` (minimal payload)
  - Anthropic: `/v1/messages` (minimal payload, token auth 지원)
  - Gemini: `generateContent` (OAuth access token)

### 2. 출력 스키마 (JSON)

**이 스킬은 라우팅을 실행하지 않고, 권장사항만 제공합니다.**

```json
{
  "timestamp": "2026-02-12T12:59:00+09:00",
  "health_state": "healthy|degraded|critical",
  "recommended_model": "anthropic/claude-opus-4-6",
  "quota_risk": "low|medium|high|critical",
  "reason": "...",
  "next_action": "switch_primary|wait|alert_admin",
  "should_alert": false,
  "providers": {
    "openai": {
      "health": "healthy|degraded|down|unknown",
      "quota_status": "ok|warning|critical|unknown",
      "quota_source": "direct|estimated|unavailable",
      "note": "..."
    },
    "anthropic": {"health": "...", "quota_status": "...", "quota_source": "...", "note": "..."},
    "gemini": {"health": "...", "quota_status": "...", "quota_source": "...", "note": "..."}
  }
}
```

**필드 설명(요청사항 반영):**
- `providers.<provider>.health`: **프로바이더별 health** (inference 성공 여부 기반)
- `providers.<provider>.quota_status`: **프로바이더별 quota 상태**
- `providers.<provider>.quota_source`: quota가 `direct`(직접)인지 `estimated`(추정)인지
- `providers.<provider>.ping_ok`: 실제 inference probe 성공 여부 (not /v1/models ping)
- `providers.<provider>.ping_endpoint`: 성공한 inference endpoint (예: "completions", "messages")
- `providers.<provider>.note`: 판단 근거/제약 설명
- `quota_confidence`, `direct_quota_available`는 보조 지표로 유지 (참고용)

**v2 변경사항 (2026-02-12):**
- ✅ Health는 실제 inference 성공 여부로 판정 (/v1/models ping 아님)
- ✅ Anthropic token auth (from auth-profiles type=token) first-class 지원
- ✅ Admin key 없어도 Anthropic health 체크 가능 (quota는 estimated)
- ✅ Quota API 실패가 health를 degraded로 만들지 않음 (note/source에만 기록)
- ✅ 모든 probes는 minimal tokens, short timeout (safe & low-cost)

---

## 🔍 분석 로직

### A. 쿨다운 체크
```python
# Pseudo-code
for model in auth_profiles:
    if model.cooldownUntil > now():
        cooldown_models.append(model.name)
```

### B. 로그 패턴 분석
- **rate_limit 카운트**: 최근 5분 내 3회 이상 → `quota_risk: high`
- **FailoverError**: 폴백 실패 → `health_state: degraded`
- **"all in cooldown"**: 모든 모델 불능 → `health_state: critical` + `should_alert: true`

### C. 쿼터 리스크 평가
```python
if rate_limit_count >= 3: return "critical"
elif rate_limit_count == 2: return "high"
elif rate_limit_count == 1: return "medium"
else: return "low"
```

### D. 헬스 상태 판정

**참조:** `references/thresholds.md` (임계값 테이블)

| State | 조건 | 대응 |
|-------|------|------|
| **healthy** | Primary 정상, 폴백 2개 이상 가능 | 유지 |
| **degraded** | Primary 쿨다운, 폴백 1개 가능 | 폴백 권장 |
| **critical** | 모든 모델 쿨다운 또는 사용 가능 모델 0개 | 즉시 알림 |

---

## 📢 알림 정책 (State Transition Only)

**알림 조건:**
1. **상태 변화**: `healthy → degraded` / `degraded → critical` / `critical → healthy`
2. **High-risk 임계값**: `quota_risk: critical` + 사용 가능 모델 1개 이하

**알림 억제:**
- 동일 상태 유지 시 알림 금지 (상태 변화에만 반응)
- `should_alert: false`로 기본 설정, 조건 충족 시만 `true`

**상태 저장:** `memory/state/model_health_unified.json` (이전 상태 비교용)

**상세 매트릭스:** `references/thresholds.md` § Alert Matrix 참조

---

## 🛠️ 실행 예시

### 기본 실행
```bash
# 모든 입력 소스 활성화
clawdbot skill model-health-orchestrator --deep --auth --logs --queue
```

### 출력 예시 (Critical)
```json
{
  "health_state": "critical",
  "recommended_model": "google-gemini-cli/gemini-3-pro-preview",
  "quota_risk": "critical",
  "reason": "All primary models in cooldown. GPT-5.3: 15min, Opus: 10min, Sonnet: 5min",
  "next_action": "alert_admin",
  "should_alert": true,
  "timestamp": "2026-02-12T12:45:00+09:00",
  "cooldown_models": [
    "openai-codex/gpt-5.3-codex",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-5"
  ],
  "available_models": [
    "google-gemini-cli/gemini-3-pro-preview",
    "anthropic/claude-haiku-4-5"
  ]
}
```

---

## 🔄 Cron 설정 (통합 완료)

```bash
*/5 * * * * /Users/dayejeong/clawd/skills/model-health-orchestrator/scripts/model_health_unified.sh >> /tmp/model_health_unified.log 2>&1
*/15 9-22 * * * /Users/dayejeong/clawd/skills/model-health-orchestrator/scripts/status_deep_check.sh >> /tmp/status_deep_check.log 2>&1
```

### 스킬 내 스크립트

| 스크립트 | 역할 | 호출 방식 |
|----------|------|-----------|
| `scripts/model_health_unified.sh` | 통합 헬스체크 (health + fallback) | cron 5분 |
| `scripts/status_deep_check.sh` | openclaw 종합 진단 | cron 15분 (09-22시) |
| `scripts/analyze_model_health.py` | 상태 분석 + 전이 판정 | unified.sh에서 호출 |
| `scripts/quota_hybrid_probe.py` | 쿼터 소스 프로브 | unified.sh에서 호출 |

**완료 사항:**
- ✅ 레거시 스크립트 아카이브 (`check_model_health.sh`, `detect_model_fallback.sh` → `scripts/_archive/`)
- ✅ 상태 전이/고위험일 때만 알림 (정상 시 무음)
- ✅ 결과를 `memory/state/model_health_unified.json`로 일원화

---

## 📚 참조 문서

- **임계값 설정**: `references/thresholds.md`
- **모델 폴백 체인**: `config/session-models.json`
- **Rate Limit 복구**: `docs/RATE_LIMIT_RECOVERY.md`
- **알림 정책**: `AGENTS.md` § 4 커뮤니케이션

---

## ✅ 검증 체크리스트

- [ ] `openclaw status --deep` 파싱 정상
- [ ] auth-profiles cooldownUntil 읽기 성공
- [ ] Gateway 로그 패턴 매칭 정확
- [ ] JSON 출력 스키마 유효
- [ ] 상태 변화 감지 로직 동작
- [ ] 알림 억제 (동일 상태) 확인
- [ ] Cron 통합 테스트 (5분 주기)

---

**버전:** 1.0.0  
**최초 작성:** 2026-02-12  
**마지막 업데이트:** 2026-02-12
