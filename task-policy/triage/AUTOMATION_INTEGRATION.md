# Automation Logger Integration Guide
**Purpose:** Ensure all cron jobs and automation scripts leave execution traces in Notion

## Quick Start

### Python Scripts
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Import automation logger
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from skills.task_policy.triage.automation_logger import log_automation_run

def main():
    automation_name = "Morning Brief"
    
    try:
        # Your automation logic here
        result = send_morning_brief()
        
        # Log success
        log_automation_run(
            automation_name=automation_name,
            status="success",
            summary=f"Sent morning brief to Telegram (topic: 일정/준비 관련)",
            message_id=result.get("message_id"),  # Optional
            metadata={
                "items_count": len(result.get("items", [])),
                "target": "JARVIS HQ"
            }
        )
        
    except Exception as e:
        # Log failure
        log_automation_run(
            automation_name=automation_name,
            status="failure",
            summary="Failed to send morning brief",
            error=str(e)
        )
        raise

if __name__ == "__main__":
    main()
```

### Shell Scripts
```bash
#!/bin/bash
# Wrap existing shell scripts with logging

AUTOMATION_NAME="Stock Report (KR)"
LOG_CMD="python3 skills/task-policy/triage/automation_logger.py log"

# Run your automation
if OUTPUT=$(python3 scripts/stock_report_kr.py 2>&1); then
    # Success
    MESSAGE_ID=$(echo "$OUTPUT" | grep "message_id:" | cut -d: -f2)
    $LOG_CMD "$AUTOMATION_NAME" success "Sent KR stock report" --message-id "$MESSAGE_ID"
else
    # Failure
    $LOG_CMD "$AUTOMATION_NAME" failure "Failed to send KR stock report" --error "$OUTPUT"
    exit 1
fi
```

### Clawdbot Agent Prompts
For cron jobs defined in agent prompts, add logging instruction:

```
Create a cron job:
- Name: "Morning Brief"
- Schedule: "0 9 * * *"
- Action: |
    1. Fetch calendar events for today
    2. Generate morning brief
    3. Send to Telegram JARVIS HQ (topic: 일정/준비 관련)
    4. **CRITICAL:** Log execution to Notion:
       ```python
       from skills.task_policy.triage.automation_logger import log_automation_run
       log_automation_run(
           automation_name="Morning Brief",
           status="success" if no_errors else "failure",
           summary="Brief summary of what was done",
           message_id=telegram_message_id
       )
       ```
```

## Integration Patterns

### Pattern 1: Wrapper Function (Recommended)
Create a wrapper that automatically logs:

```python
from functools import wraps
from skills.task_policy.triage.automation_logger import log_automation_run

def with_automation_log(automation_name: str):
    """Decorator to auto-log automation runs"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                log_automation_run(
                    automation_name=automation_name,
                    status="success",
                    summary=result.get("summary", "Execution completed"),
                    message_id=result.get("message_id")
                )
                return result
            except Exception as e:
                log_automation_run(
                    automation_name=automation_name,
                    status="failure",
                    summary=f"Failed: {str(e)[:100]}",
                    error=str(e)
                )
                raise
        return wrapper
    return decorator

# Usage
@with_automation_log("Morning Brief")
def send_morning_brief():
    # Your logic here
    return {"summary": "Brief sent", "message_id": "12345"}
```

### Pattern 2: Try-Catch Block
For existing code, wrap in try-catch:

```python
automation_name = "Daily AI Trends"

try:
    result = existing_function()
    log_automation_run(automation_name, "success", "Trends sent", message_id=result["msg_id"])
except Exception as e:
    log_automation_run(automation_name, "failure", "Failed", error=str(e))
    raise
```

### Pattern 3: Shell Wrapper Script
Create a wrapper for shell-based crons:

```bash
#!/bin/bash
# automation_wrapper.sh
# Usage: ./automation_wrapper.sh "Automation Name" "python3 script.py"

AUTOMATION_NAME="$1"
shift
COMMAND="$@"

LOGGER="python3 skills/task-policy/triage/automation_logger.py log"

if OUTPUT=$($COMMAND 2>&1); then
    $LOGGER "$AUTOMATION_NAME" success "Execution completed"
else
    $LOGGER "$AUTOMATION_NAME" failure "Execution failed" --error "$OUTPUT"
    exit 1
fi
```

## Deduplication Strategy

**Problem:** Same automation runs multiple times (e.g., every morning)

**Solution:** Logs are appended chronologically to single Automation Log Task
- Each run = new section in the Task body
- Latest logs appear at bottom
- Old logs can be archived manually (not auto-deleted)

**Alternative (if needed):** Daily aggregation
```python
# In automation_logger.py, modify to group by date
# Only create new section if date changed since last log
```

## Monitoring

### View Recent Logs
```bash
python3 skills/task-policy/triage/automation_logger.py list --limit 20
```

### Check Automation Log Task
- **Task Name:** "🤖 Automation Logs (System)"
- **Status:** Always "In Progress"
- **Location:** Tasks DB (NEW HOME workspace)
- **URL:** Auto-cached at `~/.config/notion/automation_log_task_id`

### Notion Search
In Notion:
1. Go to Tasks DB
2. Search: `🤖 Automation Logs`
3. Open page to see all logs

## Migration Checklist

For each existing cron job:
- [ ] Identify cron job name and script
- [ ] Add `log_automation_run()` call after execution
- [ ] Test manually to verify log appears in Notion
- [ ] Monitor for 24h to ensure no duplicates
- [ ] Update cron job documentation

## Existing Cron Jobs to Update

Based on `clawdbot cron list`:
1. **Morning Brief** - `96764124-1713-4006-ab6d-ba129df195b8`
2. **Stock Report (KR)** - `305f56f6-bacc-4694-8dde-f61b209dec7f`
3. **Stock Report (US)** - `8817f11b-9287-46cb-b094-edd48168040a`
4. **Daily AI Trends** - `5b90302b-1bcf-470b-ba4d-b2362df6457a`
5. **탈잉 아침 리마인더** - `5bc992ed-f7d5-476c-8b86-a54ab5ff3760`
6. **PT 숙제 루틴** - `c80cc277-2c3e-4ba8-b445-5862995f2a51`
7. **Evening Prep** - `adb94346-d3e9-4a46-9cea-d7397c851759`

**Priority:** Morning Brief, Stock Reports (most frequent)

## Troubleshooting

### "Automation Log Task not found"
- Delete cached ID: `rm ~/.config/notion/automation_log_task_id`
- Run any automation - new Task will be created

### "Duplicate logs"
- Check if multiple cron jobs have same name
- Ensure only one call to `log_automation_run()` per execution

### "Log not appearing"
- Check Notion API key: `cat ~/.config/notion/api_key_daye_personal`
- Verify Tasks DB ID: `8e0e8902-0c60-4438-8bbf-abe10d474b9b`
- Check Notion integration has access to Tasks DB

## Future Enhancements

- [ ] Dashboard view (summary of last 24h)
- [ ] Error rate tracking
- [ ] Automatic alerting on repeated failures
- [ ] Integration with heartbeat monitoring
- [ ] Log retention policy (archive logs older than 30 days)
