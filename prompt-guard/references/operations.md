# Operations - Detailed Reference

## Migration & Rollback

### Enable Prompt Guard

1. **Install skill** (already done if following this guide)
2. **Configure** `config.json` with desired settings
3. **Test** in dry-run mode:
   ```bash
   # Edit config: "dry_run": true
   # Send test messages
   # Review logs
   ```
4. **Integrate** with agent pipeline (see Integration reference)
5. **Deploy** with `dry_run: false`

### Disable Prompt Guard

**Option A: Config toggle**
```json
{
  "enabled": false
}
```

**Option B: Remove integration**
- Comment out guard calls in agent code
- Or rename skill folder:
  ```bash
  mv skills/prompt-guard skills/prompt-guard.disabled
  ```

**Option C: Set threshold to CRITICAL only**
```json
{
  "severity_threshold": "CRITICAL"
}
```

### Emergency Rollback

If guard is blocking legitimate traffic:

1. **Immediate:** Set `dry_run: true` (logs but doesn't block)
2. **Review** logs to identify issue
3. **Fix** patterns or whitelist
4. **Re-enable** after verification

## Troubleshooting

### Guard Not Blocking

**Check:**
1. `enabled: true` in config
2. `dry_run: false`
3. `severity_threshold` not too high
4. User not in `owner_whitelist`
5. Message not starting with safe command prefix

### Too Many False Positives

**Actions:**
1. Enable `dry_run: true` temporarily
2. Review logs to identify problematic patterns
3. Make patterns more specific (add context)
4. Increase `severity_threshold` to `CRITICAL`
5. Add safe command prefixes

### Logs Not Appearing

**Check:**
1. Log path exists: `~/.clawdbot/agents/main/logs/`
2. Permissions: `ls -la ~/.clawdbot/agents/main/logs/`
3. Guard is actually running: Add `--dry-run` flag for verbose output

### Telegram Alerts Not Sent

**Check:**
1. `notify_critical: true` in config
2. `telegram_group_id` is correct
3. Clawdbot has access to group
4. Message severity is `CRITICAL`
5. Check gateway logs: `clawdbot logs`
