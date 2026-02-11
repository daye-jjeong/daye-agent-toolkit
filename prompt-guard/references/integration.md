# Integration - Detailed Reference

## Standalone Script

```bash
# Scan a message
python3 skills/prompt-guard/guard.py --message "Ignore previous instructions"

# From file
python3 skills/prompt-guard/guard.py --file /path/to/message.txt

# JSON output
python3 skills/prompt-guard/guard.py --json --message "test message"

# Dry run (verbose logging)
python3 skills/prompt-guard/guard.py --dry-run --message "test"

# With metadata
python3 skills/prompt-guard/guard.py \
  --message "test" \
  --metadata '{"username": "daye", "user_id": 12345}'
```

## Shell Wrapper

```bash
# Simple usage
./scripts/guard_prompt_injection.sh "message text"

# From stdin
echo "message text" | ./scripts/guard_prompt_injection.sh

# Dry run
./scripts/guard_prompt_injection.sh --dry-run "message"
```

## Agent Pipeline Integration

### Option A: Pre-processing Hook (Recommended)

Modify agent message handler to call guard before processing:

```python
from skills.prompt_guard.guard import PromptGuard

guard = PromptGuard()

def handle_user_message(message, metadata):
    # Scan message first
    result = guard.scan(message, metadata=metadata)

    if result['blocked']:
        # Refuse and explain
        return {
            'response': f"I cannot process this request. Reason: {result['reason']}",
            'blocked': True,
            'severity': result['severity']
        }

    # Safe to process
    return process_message_normally(message)
```

### Option B: Gateway Middleware (Future)

Create a gateway plugin that intercepts all incoming messages.
