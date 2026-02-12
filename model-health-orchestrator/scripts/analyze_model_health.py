#!/usr/bin/env python3
"""
Model Health State Analyzer
- provider별 health/quota/source를 포함한 상태 JSON 생성
- 상태 전이 또는 고위험에서만 알림 메시지 생성
"""

import json
import sys
from datetime import datetime


def _provider_cooldown_flags(cooldown_data: dict) -> dict:
    flags = {"openai": False, "anthropic": False, "gemini": False}
    for profile_key in (cooldown_data or {}).keys():
        k = str(profile_key).lower()
        if "openai" in k:
            flags["openai"] = True
        if "anthropic" in k or "claude" in k:
            flags["anthropic"] = True
        if "gemini" in k or "google" in k:
            flags["gemini"] = True
    return flags


def _provider_health(provider: str, cooldown: bool, all_cooldown: bool, source_mode: str) -> str:
    if all_cooldown:
        return "down"
    if source_mode == "unavailable":
        return "unknown"
    if cooldown:
        return "degraded"
    return "healthy"


def _provider_quota_status(rate_limit_count: int, cooldown: bool, source_mode: str, all_cooldown: bool) -> str:
    if source_mode == "unavailable":
        return "unknown"
    if all_cooldown or rate_limit_count >= 3:
        return "critical"
    if cooldown or rate_limit_count >= 1:
        return "warning"
    return "ok"


def _estimated_remaining_pct(rate_limit_count: int, cooldown: bool, all_cooldown: bool) -> int:
    """Heuristic remaining quota percent (0~100)."""
    if all_cooldown:
        return 5
    base = 90
    base -= min(rate_limit_count, 5) * 15
    if cooldown:
        base -= 25
    return max(0, min(100, base))


def analyze_health(data_json, state_file):
    try:
        with open(state_file) as f:
            prev_state = json.load(f)
    except Exception:
        prev_state = {
            "health_state": "unknown",
            "quota_risk": "low",
            "last_alert_state": "unknown",
        }

    cooldown_data = data_json.get("cooldown_data", {})
    rate_limit_count = int(data_json.get("rate_limit_count", 0) or 0)
    failover_errors = int(data_json.get("failover_errors", 0) or 0)
    all_cooldown = bool(data_json.get("all_cooldown_detected", False))

    quota_probe = data_json.get("quota_probe", {})
    quota_sources = quota_probe.get("quota_sources", {})
    quota_confidence = quota_probe.get("quota_confidence", "estimated")
    direct_quota_available = bool(quota_probe.get("direct_quota_available", False))
    openai_identity_check = quota_probe.get("openai_identity_check", {})

    cooldown_models = list((cooldown_data or {}).keys())
    all_models = [
        "openai-codex/gpt-5.3-codex",
        "openai-codex/gpt-5.2",
        "anthropic/claude-opus-4-6",
        "anthropic/claude-sonnet-4-5",
        "google-gemini-cli/gemini-3-pro-preview",
        "anthropic/claude-haiku-4-5",
    ]

    cooldown_flags = _provider_cooldown_flags(cooldown_data)

    available_models = []
    for model in all_models:
        m = model.lower()
        blocked = False
        if "openai" in m and cooldown_flags["openai"]:
            blocked = True
        if "anthropic" in m and cooldown_flags["anthropic"]:
            blocked = True
        if "gemini" in m and cooldown_flags["gemini"]:
            blocked = True
        if not blocked:
            available_models.append(model)

    if rate_limit_count >= 3 or all_cooldown:
        quota_risk = "critical"
    elif rate_limit_count == 2:
        quota_risk = "high"
    elif rate_limit_count == 1:
        quota_risk = "medium"
    else:
        quota_risk = "low"

    primary_model = "openai-codex/gpt-5.3-codex"

    if all_cooldown or len(available_models) == 0:
        health_state = "critical"
        recommended_model = "google-gemini-cli/gemini-3-flash-preview"
        reason = "All models in cooldown or unavailable"
        next_action = "alert_admin"
    elif len(cooldown_models) > 0 and len(available_models) <= 2:
        health_state = "degraded"
        recommended_model = available_models[0] if available_models else "anthropic/claude-haiku-4-5"
        reason = f"{len(cooldown_models)} cooldown profile(s), {len(available_models)} model(s) available"
        next_action = "switch_fallback"
    else:
        health_state = "healthy"
        recommended_model = primary_model
        reason = "All systems operational"
        next_action = "maintain"

    # Active model labeling (사용자 요청)
    if health_state == "healthy":
        active_model = primary_model
        fallback_active = False
        fallback_model = None
    else:
        active_model = recommended_model
        fallback_active = True
        fallback_model = recommended_model
    provider_defs = [
        ("openai_oauth_work", "openai"),
        ("openai_key_embedding", "openai"),
        ("anthropic", "anthropic"),
        ("gemini", "gemini"),
    ]

    providers = {}
    for provider, cooldown_group in provider_defs:
        src = quota_sources.get(provider, {"mode": "unavailable", "note": "No source info"})
        mode = src.get("mode", "unavailable")
        est_pct = _estimated_remaining_pct(rate_limit_count, cooldown_flags[cooldown_group], all_cooldown)

        direct_used = src.get("quota_used")
        direct_limit = src.get("quota_limit")
        direct_rem = src.get("quota_remaining_pct")
        rem_source = src.get("quota_remaining_pct_source", "estimated")

        providers[provider] = {
            "health": _provider_health(provider, cooldown_flags[cooldown_group], all_cooldown, mode),
            "quota_status": _provider_quota_status(rate_limit_count, cooldown_flags[cooldown_group], mode, all_cooldown),
            "quota_source": mode,
            "quota_used": direct_used,
            "quota_limit": direct_limit,
            "quota_remaining_pct": direct_rem if direct_rem is not None else est_pct,
            "quota_remaining_pct_source": rem_source if direct_rem is not None else "estimated",
            "identity": src.get("identity", {}),
            "note": src.get("note", ""),
        }

    prev_health = prev_state.get("health_state", "unknown")
    state_changed = prev_health != health_state
    should_alert = state_changed or (quota_risk == "critical" and health_state != "healthy")

    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")

    new_state = {
        "timestamp": now_iso,
        "lastCheck": int(data_json.get("timestamp", 0) or 0),
        "health_state": health_state,
        "primary_model": primary_model,
        "active_model": active_model,
        "fallback_active": fallback_active,
        "fallback_model": fallback_model,
        "recommended_model": recommended_model,
        "quota_risk": quota_risk,
        "reason": reason,
        "next_action": next_action,
        "should_alert": should_alert,
        "providers": providers,
        "quota_sources": quota_sources,
        "quota_confidence": quota_confidence,
        "direct_quota_available": direct_quota_available,
        "openai_identity_check": openai_identity_check,
        "cooldown_models": cooldown_models,
        "available_models": available_models,
        "rate_limit_count_5min": rate_limit_count,
        "failover_errors_5min": failover_errors,
        "last_alert_state": health_state if should_alert else prev_state.get("last_alert_state", "unknown"),
        "state_transition": f"{prev_health} -> {health_state}" if state_changed else None,
    }

    alert_message = None
    if should_alert:
        icon = "🔴" if health_state == "critical" else ("⚠️" if health_state == "degraded" else "✅")
        title = (
            "시스템 장애 감지"
            if health_state == "critical"
            else ("모델 성능 저하" if health_state == "degraded" else "시스템 복구됨")
        )

        provider_lines = []
        for p in ["openai_oauth_work", "openai_key_embedding", "anthropic", "gemini"]:
            pv = providers[p]
            provider_lines.append(
                f"- {p}: health={pv['health']}, quota={pv['quota_status']}, source={pv['quota_source']}"
            )

        alert_message = (
            f"{icon} **{title}**\n\n"
            f"📍 상태: {prev_health} → {health_state}\n"
            f"📍 Main(Primary): {primary_model}\n"
            f"📍 Active 모델: {active_model}\n"
            f"📍 Fallback 활성화: {'yes' if fallback_active else 'no'}\n"
            f"📍 쿼터 리스크: {quota_risk}\n"
            f"📍 권장 모델: {recommended_model}\n"
            f"📍 사유: {reason}\n"
            f"📍 시각: {now_iso}\n\n"
            f"Provider 상태:\n" + "\n".join(provider_lines)
        )

    return new_state, alert_message


def main():
    if len(sys.argv) < 3:
        print("Usage: analyze_model_health.py <data_json_file> <state_file>", file=sys.stderr)
        sys.exit(1)

    data_json_file = sys.argv[1]
    state_file = sys.argv[2]

    with open(data_json_file) as f:
        data_json = json.load(f)

    new_state, alert_message = analyze_health(data_json, state_file)

    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=2, ensure_ascii=False)

    if alert_message:
        print(alert_message)


if __name__ == "__main__":
    main()
