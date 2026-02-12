#!/usr/bin/env python3
"""
Quota Hybrid Probe (v2 - Real Inference Probes)
- Provider별 direct/estimated/unavailable 판정
- OpenAI를 oauth(작업용) / key(임베딩용)으로 분리
- **Real inference probes**: 각 provider의 실제 추론 경로 테스트
- 가능한 경우 direct usage/cost 수집 (best effort)
- 실패 시 hard-fail 없이 estimated/unavailable로 fallback
"""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


AUTH_PROFILES_PATH = Path.home() / ".clawdbot/agents/main/agent/auth-profiles.json"


def _read_key(candidates):
    for c in candidates:
        if c.startswith("env:"):
            v = os.getenv(c.split(":", 1)[1], "").strip()
            if v:
                return v
        else:
            p = Path(c).expanduser()
            if p.exists():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
    return ""


def _http_post_json(url, headers, payload, timeout=8):
    """POST JSON payload and return response JSON."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_json(url, headers=None, timeout=8):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get(url, headers=None, timeout=8):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read().decode("utf-8")


def _safe_inference_probe(provider_type, url, headers, payload, timeout=6):
    """
    Run minimal inference request and return (success, error_msg, endpoint_used).
    Returns: (bool, str|None, str)
    """
    try:
        _http_post_json(url, headers, payload, timeout=timeout)
        return True, None, url.split("/")[-1]
    except Exception as e:
        if isinstance(e, urllib.error.HTTPError):
            return False, f"HTTP {e.code}", url.split("/")[-1]
        return False, type(e).__name__, url.split("/")[-1]


def _month_start_epoch():
    now = time.localtime()
    month_start = time.struct_time((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, -1))
    return int(time.mktime(month_start))


def _parse_jwt_payload(jwt_token: str):
    try:
        parts = jwt_token.split(".")
        if len(parts) < 2:
            return {}
        p = parts[1]
        p += "=" * ((4 - len(p) % 4) % 4)
        decoded = base64.urlsafe_b64decode(p.encode("utf-8")).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return {}


def _load_oauth_profile(provider_key: str, fallback_profile: str):
    if not AUTH_PROFILES_PATH.exists():
        return None
    try:
        d = json.loads(AUTH_PROFILES_PATH.read_text(encoding="utf-8"))
        key = (d.get("lastGood", {}) or {}).get(provider_key, fallback_profile)
        prof = (d.get("profiles", {}) or {}).get(key)
        if not prof:
            prof = (d.get("profiles", {}) or {}).get(fallback_profile)
        return prof
    except Exception:
        return None


def probe_openai_oauth_work():
    """
    OpenAI OAuth work probe - uses real chat/completions inference.
    Health determined by inference success, not /v1/models ping.
    """
    prof = _load_oauth_profile("openai-codex", "openai-codex:default")
    if not prof or prof.get("type") != "oauth":
        return {
            "mode": "unavailable",
            "note": "OpenAI OAuth profile not found",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "runtime",
            "ping_ok": False,
            "ping_error": "oauth_profile_missing",
            "ping_endpoint": None,
            "identity": {},
        }

    access = str(prof.get("access", ""))
    payload = _parse_jwt_payload(access)
    auth_claims = (payload.get("https://api.openai.com/auth") or {}) if isinstance(payload, dict) else {}

    identity = {
        "oauth_account_id": prof.get("accountId"),
        "oauth_user_id": auth_claims.get("user_id") or auth_claims.get("chatgpt_user_id"),
        "oauth_email": ((payload.get("https://api.openai.com/profile") or {}).get("email") if isinstance(payload, dict) else None),
        "oauth_plan": auth_claims.get("chatgpt_plan_type"),
    }

    # Real inference probe: minimal chat/completions request
    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json"
    }
    inference_payload = {
        "model": "gpt-4o-mini",  # Cheap model for health check
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0
    }
    
    ping_ok, ping_err, endpoint = _safe_inference_probe(
        "openai",
        "https://api.openai.com/v1/chat/completions",
        headers,
        inference_payload,
        timeout=6
    )

    return {
        "mode": "runtime",
        "note": "Runtime usage source (OpenClaw session/model usage)",
        "quota_used": None,
        "quota_limit": None,
        "quota_remaining_pct": None,
        "quota_remaining_pct_source": "runtime",
        "ping_ok": ping_ok,
        "ping_error": ping_err,
        "ping_endpoint": endpoint,
        "identity": identity,
    }


def probe_openai_key_embedding():
    """
    OpenAI API key probe - uses real embeddings inference.
    Quota from /v1/organization/costs if available.
    """
    key = _read_key([
        "env:OPENAI_USAGE_ADMIN_KEY",
        "env:OPENAI_API_KEY",
        "~/.config/jarvis/keys/openai_api_key",
    ])
    if not key:
        return {
            "mode": "estimated",
            "note": "No API key found - using cooldown estimation",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "ping_ok": False,
            "ping_error": "api_key_missing",
            "ping_endpoint": None,
            "identity": {},
        }

    budget = os.getenv("OPENAI_MONTHLY_BUDGET_USD", "").strip()
    quota_limit = float(budget) if budget.replace(".", "", 1).isdigit() else None

    identity = {}
    
    # Real inference probe: minimal embeddings request
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    inference_payload = {
        "model": "text-embedding-3-small",
        "input": "test",
        "encoding_format": "float"
    }
    
    ping_ok, ping_err, endpoint = _safe_inference_probe(
        "openai",
        "https://api.openai.com/v1/embeddings",
        headers,
        inference_payload,
        timeout=6
    )
    
    # Capture identity from response headers (best effort)
    try:
        _, headers_resp, _ = _http_get("https://api.openai.com/v1/models", headers=headers)
        identity["key_org_header"] = headers_resp.get("openai-organization")
        identity["key_project_header"] = headers_resp.get("openai-project")
    except Exception:
        pass

    # Try to get quota data (separate from health check)
    try:
        params = urllib.parse.urlencode({
            "start_time": _month_start_epoch(),
            "bucket_width": "1d",
            "limit": 31,
        })
        url = f"https://api.openai.com/v1/organization/costs?{params}"
        data = _http_get_json(url, headers={"Authorization": f"Bearer {key}"})

        used = 0.0
        for b in data.get("data", []) if isinstance(data, dict) else []:
            amt = b.get("amount") or {}
            if isinstance(amt, dict):
                used += float(amt.get("value", 0) or 0)
            else:
                used += float(b.get("cost", 0) or 0)

        rem_pct = None
        if quota_limit and quota_limit > 0:
            rem_pct = max(0.0, min(100.0, 100.0 * (quota_limit - used) / quota_limit))

        return {
            "mode": "direct",
            "note": "OpenAI costs API read success",
            "quota_used": round(used, 4),
            "quota_limit": quota_limit,
            "quota_remaining_pct": round(rem_pct, 2) if rem_pct is not None else None,
            "quota_remaining_pct_source": "direct" if rem_pct is not None else "estimated",
            "ping_ok": ping_ok,
            "ping_error": ping_err,
            "ping_endpoint": endpoint,
            "identity": identity,
        }
    except Exception as e:
        note = f"Quota API unavailable ({type(e).__name__}) - health from inference probe"
        if isinstance(e, urllib.error.HTTPError):
            identity["key_org_header"] = e.headers.get("openai-organization") or identity.get("key_org_header")
            identity["key_project_header"] = e.headers.get("openai-project") or identity.get("key_project_header")
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            if e.code == 403 and "api.usage.read" in body:
                note = "Missing OpenAI scope: api.usage.read (quota unavailable, health OK if inference succeeds)"
            elif e.code == 401:
                note = "OpenAI auth failed for quota API (but inference probe determines health)"
            else:
                note = f"OpenAI quota API HTTP {e.code} - health from inference probe"

        return {
            "mode": "estimated",
            "note": note,
            "quota_used": None,
            "quota_limit": quota_limit,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "ping_ok": ping_ok,
            "ping_error": ping_err,
            "ping_endpoint": endpoint,
            "identity": identity,
        }


def probe_anthropic():
    """
    Anthropic probe - supports both token and admin key auth.
    Token mode (from auth-profiles type=token) is first-class.
    Admin key only needed for optional quota source.
    Health determined by /v1/messages inference success.
    """
    # Try token-based auth first (runtime inference auth)
    prof = _load_oauth_profile("anthropic", "anthropic:default")
    token_auth = None
    identity = {}
    
    if prof and prof.get("type") == "token":
        token_auth = str(prof.get("access", "")).strip()
        identity["profile_type"] = "token"
        identity["profile_name"] = prof.get("name")
    
    # Admin key for quota (optional)
    admin_key = _read_key([
        "env:ANTHROPIC_ADMIN_KEY",
        "~/.config/jarvis/keys/anthropic_admin_api_key",
    ])
    
    # Determine auth to use for health probe
    probe_auth = token_auth or admin_key
    
    if not probe_auth:
        return {
            "mode": "unavailable",
            "note": "No Anthropic credentials found (token or admin key)",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "ping_ok": False,
            "ping_error": "credentials_missing",
            "ping_endpoint": None,
            "identity": identity,
        }

    # Real inference probe: minimal /v1/messages request
    headers = {
        "x-api-key": probe_auth,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    inference_payload = {
        "model": "claude-3-haiku-20240307",  # Cheapest model
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}]
    }
    
    ping_ok, ping_err, endpoint = _safe_inference_probe(
        "anthropic",
        "https://api.anthropic.com/v1/messages",
        headers,
        inference_payload,
        timeout=6
    )

    # Try to get quota data if admin key available (separate from health)
    if admin_key:
        try:
            start_date = time.strftime("%Y-%m-01")
            url = f"https://api.anthropic.com/v1/organizations/cost_report?starting_at={start_date}"
            data = _http_get_json(
                url,
                headers={
                    "x-api-key": admin_key,
                    "anthropic-version": "2023-06-01",
                },
            )

            used = 0.0
            rows = data.get("data", []) if isinstance(data, dict) else []
            for r in rows:
                used += float(r.get("cost_usd", 0) or 0)

            budget = os.getenv("ANTHROPIC_MONTHLY_BUDGET_USD", "").strip()
            quota_limit = float(budget) if budget.replace(".", "", 1).isdigit() else None
            rem_pct = None
            if quota_limit and quota_limit > 0:
                rem_pct = max(0.0, min(100.0, 100.0 * (quota_limit - used) / quota_limit))

            return {
                "mode": "direct",
                "note": "Anthropic admin cost API read success",
                "quota_used": round(used, 4),
                "quota_limit": quota_limit,
                "quota_remaining_pct": round(rem_pct, 2) if rem_pct is not None else None,
                "quota_remaining_pct_source": "direct" if rem_pct is not None else "estimated",
                "ping_ok": ping_ok,
                "ping_error": ping_err,
                "ping_endpoint": endpoint,
                "identity": identity,
            }
        except Exception as e:
            note = f"Quota API unavailable ({type(e).__name__}) - health from inference probe"
            return {
                "mode": "estimated",
                "note": note,
                "quota_used": None,
                "quota_limit": None,
                "quota_remaining_pct": None,
                "quota_remaining_pct_source": "estimated",
                "ping_ok": ping_ok,
                "ping_error": ping_err,
                "ping_endpoint": endpoint,
                "identity": identity,
            }
    else:
        # No admin key = estimated quota, but health still valid from inference
        return {
            "mode": "estimated",
            "note": "No admin key - quota estimation only (health from inference probe)",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "ping_ok": ping_ok,
            "ping_error": ping_err,
            "ping_endpoint": endpoint,
            "identity": identity,
        }


def probe_gemini():
    """
    Gemini probe - uses OAuth access token for real generateContent inference.
    Health determined by inference success.
    """
    prof = _load_oauth_profile("google-gemini-cli", "google-gemini-cli:default")
    access = str((prof or {}).get("access", "")).strip()
    identity = {}

    if not access:
        return {
            "mode": "unavailable",
            "note": "No Gemini OAuth credentials found",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "unavailable",
            "ping_ok": False,
            "ping_error": "credentials_missing",
            "ping_endpoint": None,
            "identity": {},
        }

    identity = {
        "gemini_email": (prof or {}).get("email"),
        "gemini_project_id": (prof or {}).get("projectId"),
    }

    # Real inference probe: minimal generateContent request
    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json"
    }
    inference_payload = {
        "contents": [{
            "parts": [{"text": "ping"}]
        }],
        "generationConfig": {
            "maxOutputTokens": 1,
            "temperature": 0
        }
    }
    
    ping_ok, ping_err, endpoint = _safe_inference_probe(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        headers,
        inference_payload,
        timeout=6
    )

    return {
        "mode": "estimated",
        "note": "Gemini quota endpoint not integrated - using cooldown estimation (health from inference probe)",
        "quota_used": None,
        "quota_limit": None,
        "quota_remaining_pct": None,
        "quota_remaining_pct_source": "estimated",
        "ping_ok": ping_ok,
        "ping_error": ping_err,
        "ping_endpoint": endpoint,
        "identity": identity,
    }


def calc_confidence(sources):
    modes = [v.get("mode", "unavailable") for v in sources.values()]
    direct = modes.count("direct")
    est = modes.count("estimated")
    if direct > 0 and est > 0:
        return "mixed"
    if direct > 0:
        return "high"
    return "estimated"


def compare_openai_identity(sources):
    oauth = sources.get("openai_oauth_work", {}).get("identity", {})
    key = sources.get("openai_key_embedding", {}).get("identity", {})

    oauth_user = str(oauth.get("oauth_user_id") or "")
    key_org = str(key.get("key_org_header") or "")

    same = None
    reason = "insufficient_identity_data"
    if oauth_user and key_org:
        # observed pattern: user-A81... vs user-a81...; org header may match oauth user id token
        same = oauth_user.lower() == key_org.lower()
        reason = "matched_user_vs_org_header" if same else "mismatch_user_vs_org_header"

    return {
        "same_account": same,
        "reason": reason,
        "oauth_user_id": oauth_user or None,
        "key_org_header": key_org or None,
        "key_project_header": key.get("key_project_header"),
    }


def main():
    sources = {
        "openai_oauth_work": probe_openai_oauth_work(),
        "openai_key_embedding": probe_openai_key_embedding(),
        "anthropic": probe_anthropic(),
        "gemini": probe_gemini(),
    }
    direct_any = any(v.get("mode") == "direct" for v in sources.values())
    result = {
        "quota_sources": sources,
        "quota_confidence": calc_confidence(sources),
        "direct_quota_available": direct_any,
        "openai_identity_check": compare_openai_identity(sources),
        "probed_at": int(time.time()),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        fallback = {
            "quota_sources": {
                "openai_oauth_work": {"mode": "unavailable", "note": f"Probe failed: {type(e).__name__}"},
                "openai_key_embedding": {"mode": "unavailable", "note": "Probe failed"},
                "anthropic": {"mode": "unavailable", "note": "Probe failed"},
                "gemini": {"mode": "unavailable", "note": "Probe failed"},
            },
            "quota_confidence": "estimated",
            "direct_quota_available": False,
            "openai_identity_check": {"same_account": None, "reason": "probe_failed"},
            "probed_at": int(time.time()),
        }
        print(json.dumps(fallback, ensure_ascii=False))
