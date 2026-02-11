# Check Integrations Skill

> 🔄 All-in-one integration status checker for Clawdbot

## Quick Start

### From Telegram
```
/check_integrations
```

### Direct Execution
```bash
python3 ~/clawd/skills/check-integrations/check_integrations.py
```

## What it does

Checks connectivity and authentication status for:
- 🤖 AI APIs (OpenAI, Claude, Gemini)
- 📝 Notion workspaces (Personal + Work)
- 📧 Google services (Gmail, Calendar via gog)
- 🛠️ GitHub CLI auth

## Output Example

```
# 🔄 Integration Status Report

## 🤖 AI Models
- ✅ **OpenAI**: Connected
- ✅ **Claude (Anthropic)**: Connected
- ❌ **Gemini**: API Key missing

## 📝 Notion
- ✅ **Personal (New Home)**: Connected (2 users)
- ✅ **Work (Ronik)**: Connected (4 users)

## 📧 Google Services
- **daye.jjeong@gmail.com**
  - Gmail/Calendar: ✅ Connected (10 services)
- **daye@ronik.io**
  - Gmail/Calendar: ✅ Connected (1 services)

## 🛠️ DevOps
- ✅ **GitHub**: Connected

---
✨ Check complete!
```

## When to use

- 🐛 Debugging integration issues
- ✅ Daily health checks
- 🔄 After system restart
- 🚀 Before critical operations

## Files

- `SKILL.md` - Skill documentation
- `check_integrations.py` - Main script (no dependencies!)
- `README.md` - This file

## See Also

- Original guide: `scripts/CHECK_INTEGRATION_GUIDE.md`
- Command mapping: `AGENTS.md` → Custom Commands section
