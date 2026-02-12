#!/usr/bin/env python3
"""
Model Health State Analyzer (v3 - Unified Report)
- provider별 health/quota/source를 포함한 상태 JSON 생성
- 세션 토큰 사용량을 모델별로 그룹핑하여 통합 리포트 생성
- 상태 전이, 고위험, 토큰 임계값 초과 시 알림 메시지 생성
- ping_ok는 실제 inference 성공 여부 기반 (not /v1/models ping)
"""

import json
import sys
from datetime import datetime


# ── Display constants ──────────────────────────────────────

MODEL_DISPLAY = {
    "gpt-5.3-codex": ("GPT-5.3 Codex", "🤖"),
    "gpt-5.2": ("GPT-5.2", "🤖"),
    "gpt-4o-mini": ("GPT-4o Mini", "🤖"),
    "claude-opus-4-6": ("Claude Opus 4.6", "🔵"),
    "claude-opus-4-5": ("Claude Opus 4.5", "🔵"),
    "claude-sonnet-4-5": ("Claude Sonnet 4.5", "🔵"),
    "claude-haiku-4-5": ("Claude Haiku 4.5", "🔵"),
    "gemini-3-pro-preview": ("Gemini 3 Pro", "🟢"),
    "gemini-3-flash-preview": ("Gemini 3 Flash", "🟢"),
    "gemini-1.5-flash": ("Gemini 1.5 Flash", "🟢"),
}

PROVIDER_DISPLAY = {
    "openai_oauth_work": "OpenAI (OAuth)",
    "openai_key_embedding": "OpenAI (Key)",
    "anthropic": "Anthropic",
    "gemini": "Gemini",
}

HEALTH_ICON = {
    "healthy": "✅",
    "degraded": "⚠️",
    "down": "🔴",
    "unknown": "❓",
}

TOKEN_WARNING_PCT = 80


# ── Session grouping ──────────────────────────────────────

def _session_pct(s: dict) -> int:
    """Get or compute session usage percent."""
    pct = s.get("percentUsed")
    if pct is not None:
        return int(pct)
    total = int(s.get("totalTokens", 0) or 0)
    ctx = int(s.get("contextTokens", 0) or 0)
    if ctx > 0:
        return int(total / ctx * 100)
    return 0


def _group_sessions_by_model(sessions: list) -> dict:
    """Group sessions by model, deduplicate by sessionId."""
    seen_ids = set()
    groups = {}

    for s in sessions:
        sid = s.get("sessionId", "")
        if not sid or sid in seen_ids:
            continue
        seen_ids.add(sid)

        model = s.get("model", "unknown")
        if model not in groups:
            groups[model] = {
                "context_tokens": int(s.get("contextTokens", 0) or 0),
                "sessions": [],
                "max_percent": 0,
                "main_session": None,
                "warning_count": 0,
                "full_count": 0,
            }

        pct = _session_pct(s)
        groups[model]["sessions"].append(s)
        groups[model]["max_percent"] = max(groups[model]["max_percent"], pct)

        if pct >= TOKEN_WARNING_PCT:
            groups[model]["warning_count"] += 1
        if pct >= 100:
            groups[model]["full_count"] += 1

        key = s.get("key", "")
        if ":main" in key and ":cron:" not in key:
            groups[model]["main_session"] = s

    return groups


def _fmt_tokens(tokens: int) -> str:
    """Format token count: 88000 → '88k', 1500 → '2k', 0 → '0'."""
    if tokens >= 1000:
        return f"{round(tokens / 1000)}k"
    return str(tokens)


# ── Provider analysis (unchanged) ─────────────────────────

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


def _provider_health(provider: str, cooldown: bool, all_cooldown: bool, source_mode: str, ping_ok: bool | None = None) -> str:
    if all_cooldown:
        return "down"
    if source_mode == "unavailable":
        return "unknown"
    if ping_ok is False:
        return "degraded"
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
    if all_cooldown:
        return 5
    base = 90
    base -= min(rate_limit_count, 5) * 15
    if cooldown:
        base -= 25
    return max(0, min(100, base))


# ── Trend tracking (unchanged) ────────────────────────────

def _week_key(dt):
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _trend_increment(provider: str, rate_limit_count: int, cooldown: bool, all_cooldown: bool) -> float:
    if provider == "openai_oauth_work":
        inc = 1.0 + (0.5 * min(rate_limit_count, 5))
        if cooldown:
            inc += 1.5
        if all_cooldown:
            inc += 2.0
        return inc
    if provider == "openai_key_embedding":
        inc = 0.25 + (0.2 * min(rate_limit_count, 5))
        if all_cooldown:
            inc += 0.5
        return inc
    return 0.3


def _trend_thresholds(provider: str):
    if provider == "openai_oauth_work":
        return {"day": 120.0, "week": 700.0, "month": 3000.0}
    if provider == "openai_key_embedding":
        return {"day": 40.0, "week": 220.0, "month": 900.0}
    return {"day": 80.0, "week": 450.0, "month": 1800.0}


def _update_trend(prev_provider: dict, provider: str, rate_limit_count: int, cooldown: bool, all_cooldown: bool):
    now = datetime.now().astimezone()
    day_key = now.strftime("%Y-%m-%d")
    week_key = _week_key(now)
    month_key = now.strftime("%Y-%m")

    prev = (prev_provider or {}).get("trend_estimate", {})

    day_units = float(prev.get("daily_units", 0.0)) if prev.get("day_key") == day_key else 0.0
    week_units = float(prev.get("weekly_units", 0.0)) if prev.get("week_key") == week_key else 0.0
    month_units = float(prev.get("monthly_units", 0.0)) if prev.get("month_key") == month_key else 0.0

    inc = _trend_increment(provider, rate_limit_count, cooldown, all_cooldown)
    day_units += inc
    week_units += inc
    month_units += inc

    th = _trend_thresholds(provider)
    pct = (month_units / th["month"] * 100.0) if th["month"] > 0 else 0.0
    if pct >= 90:
        level = "critical"
    elif pct >= 70:
        level = "warning"
    else:
        level = "ok"

    return {
        "day_key": day_key,
        "week_key": week_key,
        "month_key": month_key,
        "daily_units": round(day_units, 2),
        "weekly_units": round(week_units, 2),
        "monthly_units": round(month_units, 2),
        "daily_threshold": th["day"],
        "weekly_threshold": th["week"],
        "monthly_threshold": th["month"],
        "monthly_pct_of_threshold": round(min(999.0, pct), 2),
        "warning_level": level,
        "basis": "estimated_activity_units",
    }


# ── Unified report formatter ─────────────────────────────

def _format_unified_report(
    health_state: str,
    prev_health: str,
    state_changed: bool,
    active_model: str,
    fallback_active: bool,
    quota_risk: str,
    providers: dict,
    session_groups: dict,
    ping_fail_providers: list,
    now_iso: str,
) -> str:
    now = datetime.now().astimezone()
    time_str = now.strftime("%H:%M")

    total_sessions = sum(len(g["sessions"]) for g in session_groups.values())

    lines = []
    lines.append(f"📊 세션 토큰 사용량 ({time_str} 기준)")
    lines.append(f"📋 활성 세션: {total_sessions}개 (최근 2시간)")

    # ── Section 1: Session token usage by model ──
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if session_groups:
        sorted_models = sorted(
            session_groups.items(),
            key=lambda x: -x[1]["max_percent"],
        )
        for model, group in sorted_models:
            name, icon = MODEL_DISPLAY.get(model, (model, "🔹"))
            ctx = group["context_tokens"]
            ctx_k = _fmt_tokens(ctx)

            lines.append("")
            lines.append(f"{icon} {name} ({ctx_k} ctx)")

            main_s = group["main_session"]
            if main_s:
                m_pct = _session_pct(main_s)
                m_total = int(main_s.get("totalTokens", 0) or 0)
                warn = " ⚠️" if m_pct >= TOKEN_WARNING_PCT else ""
                lines.append(
                    f"• 메인 세션:{warn} {m_pct}% ({_fmt_tokens(m_total)}/{ctx_k})"
                )

            cron_sessions = [
                s for s in group["sessions"]
                if ":cron:" in s.get("key", "")
            ]
            if cron_sessions:
                active = len(cron_sessions)
                max_pct = max(_session_pct(s) for s in cron_sessions)
                max_total = max(int(s.get("totalTokens", 0) or 0) for s in cron_sessions)
                warn = " ⚠️" if max_pct >= TOKEN_WARNING_PCT else ""
                lines.append(
                    f"• Cron {active}개:{warn} 최대 {max_pct}% ({_fmt_tokens(max_total)}/{ctx_k})"
                )
    else:
        lines.append("")
        lines.append("세션 데이터 없음")

    # ── Section 2: Provider health ──
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    state_label = {"healthy": "정상", "degraded": "성능 저하", "critical": "장애"}
    state_icon = HEALTH_ICON.get(health_state, "❓")
    lines.append(f"🏥 시스템: {state_icon} {state_label.get(health_state, health_state)}")

    for p_key in ["openai_oauth_work", "openai_key_embedding", "anthropic", "gemini"]:
        pv = providers.get(p_key, {})
        h = pv.get("health", "unknown")
        h_icon = HEALTH_ICON.get(h, "❓")
        q = pv.get("quota_status", "unknown")
        p_name = PROVIDER_DISPLAY.get(p_key, p_key)
        lines.append(f"• {p_name}: {h_icon} {h} | 쿼터 {q}")

    # ── Section 3: Summary ──
    lines.append("")
    risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    lines.append(f"📈 쿼터 리스크: {risk_icon.get(quota_risk, '⚪')} {quota_risk}")
    lines.append(f"🎯 활성 모델: {active_model}")
    if fallback_active:
        lines.append("↳ 폴백 활성화됨")

    # ── Section 4: Warnings ──
    warnings = []

    if state_changed:
        warnings.append(f"상태 변경: {prev_health} → {health_state}")

    if ping_fail_providers:
        warnings.append(f"Inference 실패: {', '.join(ping_fail_providers)}")

    for model, group in session_groups.items():
        name, _ = MODEL_DISPLAY.get(model, (model, ""))
        if group["full_count"] > 0:
            warnings.append(f"{name} 세션 {group['full_count']}개 100% 도달")
        elif group["warning_count"] > 0:
            warnings.append(f"{name} 세션 {group['warning_count']}개 {TOKEN_WARNING_PCT}%+")

    if warnings:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for w in warnings:
            lines.append(f"💡 {w}")

    return "\n".join(lines)


# ── Main analysis ─────────────────────────────────────────

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

    # Session token data
    sessions_raw = data_json.get("sessions", [])
    session_groups = _group_sessions_by_model(sessions_raw)

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
    prev_providers = prev_state.get("providers", {}) if isinstance(prev_state, dict) else {}

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
        ping_ok = src.get("ping_ok")
        ping_error = src.get("ping_error")
        ping_endpoint = src.get("ping_endpoint")

        trend = _update_trend(
            prev_providers.get(provider, {}),
            provider,
            rate_limit_count,
            cooldown_flags[cooldown_group],
            all_cooldown,
        )

        providers[provider] = {
            "health": _provider_health(provider, cooldown_flags[cooldown_group], all_cooldown, mode, ping_ok),
            "quota_status": _provider_quota_status(rate_limit_count, cooldown_flags[cooldown_group], mode, all_cooldown),
            "quota_source": mode,
            "quota_used": direct_used,
            "quota_limit": direct_limit,
            "quota_remaining_pct": direct_rem if direct_rem is not None else est_pct,
            "quota_remaining_pct_source": rem_source if direct_rem is not None else "estimated",
            "ping_ok": ping_ok,
            "ping_error": ping_error,
            "ping_endpoint": ping_endpoint,
            "identity": src.get("identity", {}),
            "trend_estimate": trend,
            "note": src.get("note", ""),
        }

    prev_health = prev_state.get("health_state", "unknown")
    state_changed = prev_health != health_state

    ping_fail_providers = [
        p for p, v in providers.items()
        if v.get("ping_ok") is False and p in {"anthropic", "openai_oauth_work", "openai_key_embedding", "gemini"}
    ]

    # Token usage threshold trigger
    current_max_session_pct = max(
        (g["max_percent"] for g in session_groups.values()),
        default=0,
    )
    prev_max_session_pct = int(prev_state.get("max_session_pct", 0) or 0)
    token_warning_new = (
        current_max_session_pct >= TOKEN_WARNING_PCT
        and prev_max_session_pct < TOKEN_WARNING_PCT
    )

    should_alert = (
        state_changed
        or (quota_risk == "critical" and health_state != "healthy")
        or len(ping_fail_providers) > 0
        or token_warning_new
    )

    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")

    # Session summary for state persistence
    session_summary = {}
    for model, group in session_groups.items():
        session_summary[model] = {
            "count": len(group["sessions"]),
            "max_percent": group["max_percent"],
            "context_tokens": group["context_tokens"],
            "warning_count": group["warning_count"],
            "full_count": group["full_count"],
        }

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
        "ping_fail_providers": ping_fail_providers,
        "max_session_pct": current_max_session_pct,
        "session_summary": session_summary,
    }

    alert_message = None
    if should_alert:
        alert_message = _format_unified_report(
            health_state=health_state,
            prev_health=prev_health,
            state_changed=state_changed,
            active_model=active_model,
            fallback_active=fallback_active,
            quota_risk=quota_risk,
            providers=providers,
            session_groups=session_groups,
            ping_fail_providers=ping_fail_providers,
            now_iso=now_iso,
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
