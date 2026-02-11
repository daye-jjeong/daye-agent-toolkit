# Prompt Guard

**Injection detection and defense system for Clawdbot.**

## Quick Start

```bash
# Test the guard
./scripts/guard_prompt_injection.sh "Your message here"

# Run tests
python3 skills/prompt-guard/test_guard.py

# Check logs
tail -f ~/.clawdbot/agents/main/logs/prompt-guard.log
```

## What It Does

Scans incoming messages for:
- ✅ Prompt injection attempts
- ✅ Jailbreak patterns
- ✅ Data exfiltration
- ✅ Harmful commands

## Configuration

Edit `config.json`:
- `severity_threshold`: Sensitivity level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `dry_run`: Test mode (log but don't block)
- `owner_whitelist`: Trusted users who bypass checks
- `notify_critical`: Send Telegram alerts

## Files

- **`guard.py`**: Main detection engine
- **`config.json`**: Configuration
- **`test_guard.py`**: Unit tests
- **`SKILL.md`**: Complete documentation
- **`examples.sh`**: Usage examples

## Exit Codes

- `0` - Safe to process
- `1` - Blocked (threat detected)
- `2` - Error

## See Full Docs

Read [`SKILL.md`](./SKILL.md) for:
- Architecture details
- Detection categories
- Integration guide
- Troubleshooting
- Security considerations

## Status

**Active** - Integrated as Layer 1 defense in Clawdbot message pipeline.
