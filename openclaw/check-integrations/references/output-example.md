# Check Integrations Output Example

```markdown
# Integration Status Report (Detailed)

*Generated: 2026-02-02 13:01:30*

## AI Models
- **OpenAI**: Connected (112 models)
  - Auth: API Key
  - Expires: N/A (API keys don't expire)
- **Claude (Anthropic)**: Connected
  - Auth: API Key
  - Disconnect reason: Only if manually revoked

## Notion Workspaces
- **Personal (NEW HOME)**: Connected: 2 users, 15 DBs, 25 pages
  - Databases (15): Tasks, Projects, Reading List, Notes, Ideas...
  - Pages (25): DAYE HQ, Weekly Review, Goals 2026...
- **Work (RONIK PROJECT)**: Connected: 4 users, 8 DBs, 12 pages
  - Databases (8): Romeo Task Dashboard, Client Projects, Roadmap...
  - Pages (12): Romeo 제안서, 문서 관리 체계...

## Google Services (OAuth)
- **daye.jjeong@gmail.com**
  - Auth: OAuth 2.0
  - Services: Gmail, Calendar, Drive, Contacts, Tasks
  - Auto-refresh: Yes (gog handles it)
  - Token: `~/.config/gog/tokens/daye.jjeong@gmail.com.json`

  **OAuth Diagnostic:**
  - Using OAuth 2.0 (recommended)
  - Auto-refresh enabled
  - Disconnect reason: Token revoked, quota exceeded, or refresh failed
  - **Action**: Run `gog auth login daye.jjeong@gmail.com` to fix

## GitHub (OAuth)
- **GitHub**: Connected as daye-jjeong (2 orgs)
  - User: `daye-jjeong`
  - Organizations: DMgathering, ronik-corp
  - Token scopes: repo, gist, read:org, workflow

  **OAuth Diagnostic:**
  - OAuth token (managed by gh CLI)
  - Auto-refresh enabled
  - Disconnect reason: Very rare (gh CLI is stable)

## OAuth Summary
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
