# Check Integrations Service Details

## AI Models (with OAuth Investigation)

- **OpenAI** - API connectivity + model count
  - Auth type: API Key
  - Expiry analysis
- **Claude (Anthropic)** - API connectivity
  - Auth type: API Key
  - Disconnect analysis
- **Gemini** - API connectivity + model count
  - Auth type: API Key
  - Quota/expiry diagnostics

## Notion Workspaces (Detailed Permissions)

- **Personal (NEW HOME)** - `~/.config/notion/api_key_daye_personal`
  - User count
  - **Top 10 accessible databases** (by name)
  - **Top 10 accessible pages** (by name)
- **Work (RONIK PROJECT)** - `~/.config/notion/api_key`
  - User count
  - **Top 10 accessible databases** (by name)
  - **Top 10 accessible pages** (by name)

## Google Services (Per-Account OAuth)

Per account breakdown showing **individual service access**:
- **daye.jjeong@gmail.com**
  - Gmail / Calendar / Drive / Contacts / Tasks
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

## GitHub (Org-Level Access)

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

## Upgrade History

**v2.0 (2026-02-02)** - Enhanced with:
- Granular Notion permission checks (DB/page listings)
- Per-service Google API breakdown
- GitHub org-level access
- OAuth token expiry investigation
- Auto-refresh diagnostics
- Disconnect root cause analysis

**v1.0** - Basic connectivity checks
