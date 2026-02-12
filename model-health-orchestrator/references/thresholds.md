# Thresholds - Model Health Orchestrator

**목적:** 모델 헬스 상태 판정 및 알림 트리거 임계값 정의.

**효력:** 2026-02-12

---

## 📊 임계값 테이블

### Provider별 상태 표기 규칙 (요청 반영)

| 필드 | 값 | 의미 |
|---|---|---|
| `providers.<p>.health` | `healthy` | 해당 provider 정상 |
|  | `degraded` | 쿨다운/오류 징후 있음 |
|  | `down` | 사용 불가 상태 |
|  | `unknown` | 데이터 없음 |
| `providers.<p>.quota_status` | `ok` | quota 여유/문제 없음 |
|  | `warning` | 제한 징후(쿨다운/일시적 rate limit) |
|  | `critical` | 강한 제한/연쇄 실패 |
|  | `unknown` | 판단 불가 |
| `providers.<p>.quota_source` | `direct` | provider API/직접 소스 기반 |
|  | `estimated` | cooldown/log 패턴 기반 추정 |
|  | `unavailable` | 인증/데이터 소스 없음 |


### 1. Quota Risk Levels

| Level | Rate Limit Count (5분) | Cooldown Models | 설명 |
|-------|------------------------|-----------------|------|
| **low** | 0 | 0-1 | 정상 운영, 여유 있음 |
| **medium** | 1 | 1-2 | 주의 필요, 모니터링 강화 |
| **high** | 2 | 2-3 | 위험 수준, 폴백 준비 |
| **critical** | 3+ | 4+ 또는 전체 | 즉시 조치 필요 |

### 2. Health State Thresholds

| State | Primary Available | Fallback Available | Cooldown Count | 조건 |
|-------|-------------------|--------------------| --------------|------|
| **healthy** | ✅ Yes | ≥2 | 0-1 | Primary 정상, 충분한 폴백 |
| **degraded** | ❌ No | 1-2 | 1-3 | Primary 실패, 폴백 제한적 |
| **critical** | ❌ No | 0 | 4+ | 모든 모델 불능 |

**Primary 모델:** `openai-codex/gpt-5.3-codex` (기본 설정)

### 3. Error Rate Thresholds

| Metric | Normal | Caution | High | 조치 |
|--------|--------|---------|------|------|
| **Error Rate** | <5% | 5-15% | >15% | >15% 시 알림 |
| **Failover Rate** | <10% | 10-25% | >25% | >25% 시 즉시 알림 |
| **Avg Response Time** | <2s | 2-5s | >5s | >5s 시 폴백 권장 |

---

## 🚨 State Transition Alert Matrix

**알림 발송 조건:** 상태 **변화 시**에만 알림.

### Transition Table

| From → To | Alert? | Priority | Message Template |
|-----------|--------|----------|------------------|
| healthy → healthy | ❌ No | - | (무음) |
| healthy → degraded | ✅ Yes | Medium | "⚠️ 모델 헬스 저하: {reason}" |
| healthy → critical | ✅ Yes | **High** | "🚨 긴급: 모든 모델 불능 - {reason}" |
| degraded → degraded | ❌ No | - | (무음) |
| degraded → healthy | ✅ Yes | Low | "✅ 복구 완료: {reason}" |
| degraded → critical | ✅ Yes | **High** | "🚨 악화: 모든 모델 불능 - {reason}" |
| critical → critical | ❌ No | - | (무음) |
| critical → degraded | ✅ Yes | Medium | "⚠️ 부분 복구: {reason}" |
| critical → healthy | ✅ Yes | Low | "✅ 완전 복구: {reason}" |

### Alert Priority 설명
- **High:** 즉시 Telegram 알림 + 소리
- **Medium:** Telegram 알림 (소리 없음)
- **Low:** 로그 기록 + 선택적 알림

---

## 📈 상태 판정 로직 (Pseudo-code)

```python
def determine_health_state(models_status, cooldown_list):
    primary = "openai-codex/gpt-5.3-codex"
    available = [m for m in models_status if m not in cooldown_list]
    
    # Critical: 사용 가능 모델 없음
    if len(available) == 0:
        return "critical"
    
    # Degraded: Primary 불능, 폴백 제한적
    if primary in cooldown_list and len(available) <= 2:
        return "degraded"
    
    # Healthy: Primary 정상 또는 충분한 폴백
    return "healthy"

def determine_quota_risk(rate_limit_count, cooldown_count):
    if rate_limit_count >= 3 or cooldown_count >= 4:
        return "critical"
    elif rate_limit_count == 2 or cooldown_count == 3:
        return "high"
    elif rate_limit_count == 1 or cooldown_count == 2:
        return "medium"
    else:
        return "low"

def should_alert(current_state, previous_state):
    # 상태 변화 시에만 True
    return current_state != previous_state
```

---

## 🔧 구성 가능 파라미터

**파일 위치:** `.state/model_health_config.json` (선택 사항)

```json
{
  "primary_model": "openai-codex/gpt-5.3-codex",
  "thresholds": {
    "rate_limit_window_minutes": 5,
    "critical_rate_limit_count": 3,
    "high_quota_risk_count": 2,
    "minimum_fallback_models": 2
  },
  "alert": {
    "telegram_chat_id": "-1003242721592",
    "telegram_topic_id": 171,
    "suppress_same_state": true
  }
}
```

**기본값:** 위 테이블의 값. 설정 파일 없으면 기본값 사용.

---

## 📝 예시 시나리오

### Scenario 1: Healthy → Degraded

**상황:**
- Primary (GPT-5.3-codex) rate limit 도달
- Fallback 2개 가능 (Opus, Sonnet)

**판정:**
```json
{
  "health_state": "degraded",
  "quota_risk": "medium",
  "recommended_model": "anthropic/claude-opus-4-6",
  "should_alert": true,
  "reason": "Primary model (GPT-5.3-codex) in cooldown. Fallback to Opus recommended."
}
```

**알림:** ⚠️ Medium priority

---

### Scenario 2: Degraded → Critical

**상황:**
- GPT-5.3-codex, Opus, Sonnet 모두 쿨다운
- Gemini만 가능

**판정:**
```json
{
  "health_state": "critical",
  "quota_risk": "critical",
  "recommended_model": "google-gemini-cli/gemini-3-pro-preview",
  "should_alert": true,
  "reason": "All primary models in cooldown. Only Gemini available."
}
```

**알림:** 🚨 High priority

---

### Scenario 3: Critical → Healthy (복구)

**상황:**
- 모든 모델 쿨다운 해제
- Primary 복구 완료

**판정:**
```json
{
  "health_state": "healthy",
  "quota_risk": "low",
  "recommended_model": "openai-codex/gpt-5.3-codex",
  "should_alert": true,
  "reason": "All models recovered. Primary model back online."
}
```

**알림:** ✅ Low priority (복구 완료)

---

## 🔍 로그 패턴 매칭

### Gateway Log Patterns

**파일:** `~/.clawdbot/gateway/logs/gateway.log` (최근 5분)

| Pattern | Severity | Action |
|---------|----------|--------|
| `rate_limit` | High | quota_risk +1 |
| `FailoverError` | Medium | health_state → degraded |
| `all models in cooldown` | Critical | health_state → critical, alert |
| `429 Too Many Requests` | High | quota_risk +1 |
| `ECONNREFUSED` | Medium | 특정 모델 제외 |

---

**버전:** 1.0.0  
**최초 작성:** 2026-02-12  
**마지막 업데이트:** 2026-02-12
