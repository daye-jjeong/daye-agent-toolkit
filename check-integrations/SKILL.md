---
name: check-integrations
description: Enhanced integration health checker with granular permission checks, OAuth diagnostics, and detailed service breakdowns. Checks AI APIs (OpenAI, Claude, Gemini), Notion workspaces with DB/page listings, Google services per-account (Gmail, Calendar, Drive, Contacts), GitHub org-level access, and provides OAuth token expiry analysis.
---

# Check Integrations Skill

**Version:** 0.1.0 | **Updated:** 2026-02-03 | **Status:** Experimental

Comprehensive status check of all external service integrations with granular permission analysis and OAuth diagnostics.

## What It Checks

| Service | Key Checks |
|---------|------------|
| AI Models (OpenAI, Claude, Gemini) | API connectivity, model count, auth type |
| Notion (Personal + Work) | User count, top 10 DBs/pages by name |
| Google (per-account) | Gmail, Calendar, Drive, Contacts, Tasks per account |
| GitHub | User, org memberships, token scopes |

**상세 (서비스별 세부 항목, OAuth 진단)**: `{baseDir}/references/service-details.md` 참고

## Trigger

- `/check_integrations` (Telegram command)
- Manual: `python3 ~/clawd/scripts/check_integrations.py`

## Core Workflow

1. Check AI API keys (OpenAI, Claude, Gemini) -- connectivity + auth type
2. Query Notion workspaces -- list accessible DBs and pages
3. Test Google services per account -- individual API permissions
4. Verify GitHub -- org access + token scopes
5. Generate OAuth diagnostic report -- expiry, refresh, disconnect analysis
6. Format and output status report

## Command

```bash
# Standalone script (recommended, 0 LLM tokens)
python3 ~/clawd/scripts/check_integrations.py
```

Note: Converted to standalone script to reduce LLM token costs. Runs without clawdbot/LLM dependencies.

## Output Format

Markdown report with per-service status, permission details, and OAuth summary.

**상세**: `{baseDir}/references/output-example.md` 참고

## When to Use

- Daily health check -- verify services and permissions
- Debugging integration issues -- see which APIs are accessible
- OAuth troubleshooting -- understand disconnect reasons
- Permission audit -- know what data each integration can access
- Before critical operations / after auth changes

## Requirements

- Python 3
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`
- Notion keys in `~/.config/notion/`
- CLI tools: `gog` (Google OAuth), `gh` (GitHub OAuth)

## Notes

- Checks have 5-10 second timeouts to prevent hanging
- Notion checks show actual accessible resources, not just connection status
- Google breakdown shows individual API permissions per account
- Auto-refresh recommendations included for OAuth services
