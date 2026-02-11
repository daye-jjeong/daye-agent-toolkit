---
name: check-integrations
description: Enhanced integration health checker with granular permission checks, OAuth diagnostics, and detailed service breakdowns. Checks AI APIs (OpenAI, Claude, Gemini), Notion workspaces with DB/page listings, Google services per-account (Gmail, Calendar, Drive, Contacts), GitHub org-level access, and provides OAuth token expiry analysis.
---

# Check Integrations Skill (Enhanced)


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

Comprehensive status check of all external service integrations with **granular permission analysis** and **OAuth diagnostics**.

## What it checks

### 🤖 AI Models (with OAuth Investigation)
- **OpenAI** - API connectivity + model count
  - Auth type: API Key
  - Expiry analysis
- **Claude (Anthropic)** - API connectivity
  - Auth type: API Key
  - Disconnect analysis
- **Gemini** - API connectivity + model count
  - Auth type: API Key
  - Quota/expiry diagnostics

### 📝 Notion Workspaces (Detailed Permissions)
- **Personal (NEW HOME)** - `~/.config/notion/api_key_daye_personal`
  - User count
  - **Top 10 accessible databases** (by name)
  - **Top 10 accessible pages** (by name)
- **Work (RONIK PROJECT)** - `~/.config/notion/api_key`
  - User count
  - **Top 10 accessible databases** (by name)
  - **Top 10 accessible pages** (by name)

### 📧 Google Services (Per-Account OAuth)
Per account breakdown showing **individual service access**:
- **daye.jjeong@gmail.com**
  - Gmail ✅/❌
  - Calendar ✅/❌
  - Drive ✅/❌
  - Contacts ✅/❌
  - Tasks ✅/❌
  - OAuth token status
  - Auto-refresh capability
- **daye@ronik.io**
  - Same detailed breakdown
  - Token file location

**OAuth Diagnostic Report:**
- Token expiry detection
- Refresh mechanism analysis
- Disconnect root cause identification
- Auto-refresh recommendations

### 🛠️ GitHub (Org-Level Access)
- **User account** name
- **Organization memberships** (list all orgs)
- **Token scopes** (permissions granted)
- OAuth refresh status
- Disconnect diagnostics

## Enhanced Features

### 1. Granular Permission Checks
Instead of just "Connected", see **exactly what you can access**:
- Notion: Lists actual databases and pages by name
- Google: Shows which specific APIs are accessible (not just "Gmail")
- GitHub: Shows org memberships and token scopes

### 2. OAuth Investigation
For OAuth-based services (Google, GitHub):
- **Auth type**: OAuth 2.0 vs API Key
- **Token expiry**: When tokens expire
- **Refresh mechanism**: Auto-refresh enabled/disabled
- **Disconnect reasons**: Why services might disconnect
- **Action steps**: How to fix disconnections

### 3. Detailed Diagnostics
Full OAuth summary section explaining:
- Which services use OAuth vs API keys
- Token lifecycle for each service
- Common disconnect scenarios
- Preventive maintenance recommendations

## Command (Telegram)

```
/check_integrations
```

Or run manually:

```bash
# NEW: Converted to standalone script (2026-02-02)
python3 ~/clawd/scripts/check_integrations.py

# OLD: Skill location (deprecated, use script above)
# python3 ~/clawd/skills/check-integrations/check_integrations.py
```

**Note:** This skill has been converted to a standalone script (`scripts/check_integrations.py`) to reduce LLM token costs. The script runs without any clawdbot/LLM dependencies.

## Enhanced Output Format

```markdown
# 🔄 Integration Status Report (Detailed)

*Generated: 2026-02-02 13:01:30*

## 🤖 AI Models
- ✅ **OpenAI**: Connected (112 models)
  - Auth: API Key
  - Expires: N/A (API keys don't expire)
- ✅ **Claude (Anthropic)**: Connected
  - Auth: API Key
  - Disconnect reason: Only if manually revoked

## 📝 Notion Workspaces
- ✅ **Personal (NEW HOME)**: Connected: 2 users, 15 DBs, 25 pages
  - Databases (15): Tasks, Projects, Reading List, Notes, Ideas...
  - Pages (25): DAYE HQ, Weekly Review, Goals 2026...
- ✅ **Work (RONIK PROJECT)**: Connected: 4 users, 8 DBs, 12 pages
  - Databases (8): Romeo Task Dashboard, Client Projects, Roadmap...
  - Pages (12): Romeo 제안서, 문서 관리 체계...

## 📧 Google Services (OAuth)
- **daye.jjeong@gmail.com**
  - Auth: OAuth 2.0
  - Services: Gmail, Calendar, Drive, Contacts, Tasks
  - Auto-refresh: Yes (gog handles it)
  - Token: `~/.config/gog/tokens/daye.jjeong@gmail.com.json`

  **OAuth Diagnostic:**
  - ✅ Using OAuth 2.0 (recommended)
  - ✅ Auto-refresh enabled
  - Disconnect reason: Token revoked, quota exceeded, or refresh failed
  - **Action**: Run `gog auth login daye.jjeong@gmail.com` to fix

## 🛠️ GitHub (OAuth)
- ✅ **GitHub**: Connected as daye-jjeong (2 orgs)
  - User: `daye-jjeong`
  - Organizations: DMgathering, ronik-corp
  - Token scopes: repo, gist, read:org, workflow

  **OAuth Diagnostic:**
  - ✅ OAuth token (managed by gh CLI)
  - ✅ Auto-refresh enabled
  - Disconnect reason: Very rare (gh CLI is stable)

## 📊 OAuth Summary
**AI Services (API Keys):**
- Stable, no expiry, disconnect only if manually revoked

**Google Services (OAuth 2.0):**
- Tokens expire but auto-refresh via gog
- May disconnect if access revoked or quota exceeded

**GitHub (OAuth):**
- Very stable, auto-refresh enabled, rarely disconnects

**Notion (Integration Tokens):**
- No expiry, stable unless manually revoked
```

## When to use

- **Daily health check** - Verify all services and their specific permissions
- **Debugging integration issues** - See exactly which APIs are accessible
- **OAuth troubleshooting** - Understand why services disconnect
- **Permission audit** - Know what data each integration can access
- **Before critical operations** - Ensure all required permissions are granted
- **After auth changes** - Verify new scopes/permissions took effect

## Requirements

- Python 3
- API keys in environment or config:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GEMINI_API_KEY` or `GOOGLE_API_KEY`
  - Notion keys in `~/.config/notion/`
- CLI tools:
  - `gog` (for Google OAuth services)
  - `gh` (for GitHub OAuth)

## Notes

- Checks have 5-10 second timeouts to prevent hanging
- OAuth diagnostics explain **why** services disconnect
- Notion checks show **actual accessible resources**, not just connection status
- Google service breakdown shows **individual API permissions**
- GitHub check includes **org-level access** and **token scopes**
- Auto-refresh recommendations included for OAuth services

## Upgrade History

**v2.0 (2026-02-02)** - Enhanced with:
- Granular Notion permission checks (DB/page listings)
- Per-service Google API breakdown
- GitHub org-level access
- OAuth token expiry investigation
- Auto-refresh diagnostics
- Disconnect root cause analysis

**v1.0** - Basic connectivity checks
