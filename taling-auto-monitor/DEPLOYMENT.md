# Deployment Guide - Taling Auto Monitor

## Pre-Deployment Checklist

- [ ] Telegram Bot created (@BotFather)
- [ ] Bot token exported in `~/.zshrc`
- [ ] Bot added to JARVIS HQ group (`-1003242721592`)
- [ ] Script tested manually (`./scripts/taling_auto_monitor_v2.py check`)
- [ ] State file created (`memory/taling_daily_status.json`)
- [ ] Log directory exists (`logs/`)

## Deployment Steps

### 1. Verify Environment

```bash
# Check token
echo $TELEGRAM_BOT_TOKEN
# Should output: 123456789:ABCdef...

# Check script permissions
ls -la scripts/taling_auto_monitor_v2.py
# Should show: -rwxr-xr-x (executable)

# Check bot access
./scripts/taling_auto_monitor_v2.py check
# Should output: "🔍 Checking for new messages..."
```

### 2. Install Cron Jobs

```bash
# Backup current crontab
crontab -l > ~/crontab_backup_$(date +%Y%m%d).txt

# Edit crontab
crontab -e

# Add these lines:
*/10 8-23 * * * /Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py check >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1
0 23 * * * /Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py report >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1

# Verify
crontab -l | grep taling
```

### 3. Test Cron Execution

```bash
# Wait 10 minutes or manually trigger
/Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py check >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1

# Check log
tail -20 logs/taling_auto_monitor.log

# Expected output:
# 🔍 Checking for new messages... (HH:MM:SS)
# ℹ️  No new updates
# or
# 📥 Found N new updates
```

### 4. Upload Test File

```bash
# 1. Open Telegram JARVIS HQ
# 2. Go to topic 168 (탈잉 챌린지)
# 3. Upload image with caption "불렛저널 테스트"
# 4. Wait 30 seconds
# 5. Run: ./scripts/taling_auto_monitor_v2.py check
# 6. Check log for: "✅ Classified: 불렛저널 테스트 → 불렛저널"
```

### 5. Monitor for 1 Week

```bash
# Daily checks
tail -f logs/taling_auto_monitor.log

# Weekly summary
grep "✅ Classified" logs/taling_auto_monitor.log | wc -l
# Should show number of files processed

# Check state file
cat memory/taling_daily_status.json | jq '.daily_files'
```

## Post-Deployment Monitoring

### Daily Checks (First Week)

```bash
# Morning (09:00)
tail -50 logs/taling_auto_monitor.log
# Verify overnight cron runs

# Evening (23:30)
# Check if report was sent at 23:00
```

### Weekly Review

```bash
# Files processed
grep "✅ Classified" logs/taling_auto_monitor.log | wc -l

# Alerts sent
grep "📤 Alert sent" logs/taling_auto_monitor.log | wc -l

# Errors
grep "❌" logs/taling_auto_monitor.log
```

### State File Health

```bash
# Check structure
cat memory/taling_daily_status.json | jq

# Expected keys:
# - last_update_id (number)
# - daily_files (object with dates)
# - daily_reviews (object with dates)

# Clean old data (monthly)
# Remove entries older than 30 days from daily_files/daily_reviews
```

## Rollback Plan

### If Issues Arise

```bash
# Stop cron
crontab -e
# Comment out taling lines with #

# Restore backup
crontab ~/crontab_backup_YYYYMMDD.txt

# Reset state
mv memory/taling_daily_status.json memory/taling_daily_status.json.backup
# Will auto-create on next run

# Fallback to manual monitoring
# User posts "체크해줘" and agent runs check manually
```

## Success Criteria

After 1 week, verify:
- [ ] **Uptime**: Cron runs every 10 minutes (8 AM - 11 PM)
- [ ] **Detection**: All uploaded files classified correctly
- [ ] **Alerts**: Immediate notification on file upload
- [ ] **Reports**: 23:00 daily report sent
- [ ] **Accuracy**: No false positives/negatives in classification
- [ ] **Performance**: Logs show no errors or timeouts

## Known Issues & Workarounds

### Issue: "No new updates" despite uploads

**Cause**: Bot not in group or topic  
**Fix**: Re-add bot to JARVIS HQ, verify topic 168 access

### Issue: Classification fails

**Cause**: Filename/caption lacks keywords  
**Fix**: Update FILE_PATTERNS in script or guide user on naming

### Issue: Cron not running

**Cause**: PATH or TELEGRAM_BOT_TOKEN not available in cron env  
**Fix**: Add to cron header:
```cron
SHELL=/bin/zsh
PATH=/usr/local/bin:/usr/bin:/bin
TELEGRAM_BOT_TOKEN=your_token_here
```

## Maintenance

### Monthly
- Review and archive old logs (>30 days)
- Clean old state file entries
- Verify bot token still valid

### Before Challenge End (60 days)
- Export final statistics
- Archive all logs
- Document lessons learned
- Decide on system retention/decommission

## Support

- **Logs**: `logs/taling_auto_monitor.log`
- **State**: `memory/taling_daily_status.json`
- **Docs**: `skills/taling-auto-monitor/README.md`
- **Code**: `scripts/taling_auto_monitor_v2.py`
