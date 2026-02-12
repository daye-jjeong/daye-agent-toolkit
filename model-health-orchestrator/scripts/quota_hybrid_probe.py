#!/usr/bin/env python3
"""
Quota Hybrid Probe
- Provider별 direct/estimated/unavailable 판정
- OpenAI를 oauth(작업용) / key(임베딩용)으로 분리
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


def _http_get_json(url, headers=None, timeout=8):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get(url, headers=None, timeout=8):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read().decode("utf-8")


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


def _load_oauth_profile():
    if not AUTH_PROFILES_PATH.exists():
        return None
    try:
        d = json.loads(AUTH_PROFILES_PATH.read_text(encoding="utf-8"))
        key = (d.get("lastGood", {}) or {}).get("openai-codex", "openai-codex:default")
        prof = (d.get("profiles", {}) or {}).get(key)
        if not prof:
            prof = (d.get("profiles", {}) or {}).get("openai-codex:default")
        return prof
    except Exception:
        return None


def probe_openai_oauth_work():
    prof = _load_oauth_profile()
    if not prof or prof.get("type") != "oauth":
        return {
            "mode": "unavailable",
            "note": "OpenAI OAuth profile not found",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "runtime",
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

    return {
        "mode": "runtime",
        "note": "Runtime usage source (OpenClaw session/model usage)",
        "quota_used": None,
        "quota_limit": None,
        "quota_remaining_pct": None,
        "quota_remaining_pct_source": "runtime",
        "identity": identity,
    }


def probe_openai_key_embedding():
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
            "identity": {},
        }

    budget = os.getenv("OPENAI_MONTHLY_BUDGET_USD", "").strip()
    quota_limit = float(budget) if budget.replace(".", "", 1).isdigit() else None

    identity = {}
    try:
        _, headers, _ = _http_get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
        identity["key_org_header"] = headers.get("openai-organization")
        identity["key_project_header"] = headers.get("openai-project")
    except Exception:
        pass

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
            "identity": identity,
        }
    except Exception as e:
        note = f"Direct API unavailable ({type(e).__name__}) - using cooldown estimation"
        if isinstance(e, urllib.error.HTTPError):
            identity["key_org_header"] = e.headers.get("openai-organization") or identity.get("key_org_header")
            identity["key_project_header"] = e.headers.get("openai-project") or identity.get("key_project_header")
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            if e.code == 403 and "api.usage.read" in body:
                note = "Missing OpenAI scope: api.usage.read (key/org role permission required)"
            elif e.code == 401:
                note = "OpenAI auth failed (invalid key or token)"
            else:
                note = f"OpenAI direct API HTTP {e.code} - using cooldown estimation"

        return {
            "mode": "estimated",
            "note": note,
            "quota_used": None,
            "quota_limit": quota_limit,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "identity": identity,
        }


def probe_anthropic():
    admin_key = _read_key([
        "env:ANTHROPIC_ADMIN_KEY",
        "~/.config/jarvis/keys/anthropic_admin_api_key",
    ])

    if not admin_key:
        return {
            "mode": "estimated",
            "note": "No Anthropic admin key - using cooldown estimation",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "identity": {},
        }

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
            "identity": {},
        }
    except Exception as e:
        return {
            "mode": "estimated",
            "note": f"Anthropic direct API unavailable ({type(e).__name__}) - using cooldown",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "identity": {},
        }


def probe_gemini():
    oauth_path = Path.home() / ".config/jarvis/keys/google_oauth_personal.json"
    if oauth_path.exists():
        return {
            "mode": "estimated",
            "note": "Gemini quota endpoint not integrated - using cooldown estimation",
            "quota_used": None,
            "quota_limit": None,
            "quota_remaining_pct": None,
            "quota_remaining_pct_source": "estimated",
            "identity": {},
        }
    return {
        "mode": "unavailable",
        "note": "No credentials found - quota tracking unavailable",
        "quota_used": None,
        "quota_limit": None,
        "quota_remaining_pct": None,
        "quota_remaining_pct_source": "unavailable",
        "identity": {},
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
