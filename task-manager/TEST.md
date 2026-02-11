# Task Manager - Test & Verification

## Quick Test

### 1. Add a test task
```bash
./skills/task-manager/add-task.sh "Test: Generate a haiku about AI"
```

### 2. Check the queue
```bash
cat memory/pending_tasks.json | jq
```

### 3. Run task manager
```bash
node skills/task-manager/index.js
```

Expected output:
```json
{
  "status": "READY",
  "recommendation": {
    "model": "google-gemini-flash",
    "prompt": "Test: Generate a haiku about AI",
    ...
  }
}
```

Or if busy:
```json
{
  "status": "DEFERRED",
  "reason": "concurrency_limit",
  "active_sessions": 1
}
```

### 4. Remove task (simulate spawn)
```bash
node skills/task-manager/process-task.js
```

### 5. Verify empty queue
```bash
cat memory/pending_tasks.json
# Should show: []
```

## Test VIP Lane Protection

### Scenario 1: Normal Operation (No Background Tasks)
```bash
# Add task
echo '[{"prompt":"Low priority task","priority":2}]' > memory/pending_tasks.json

# Run manager
node skills/task-manager/index.js

# Should output: READY with google-gemini-flash
```

### Scenario 2: Concurrency Limit (Background Task Running)
```bash
# Simulate by having active sessions
# Manager will detect and output: DEFERRED
```

### Scenario 3: High Load
```bash
# Currently mocked - will randomly defer ~20% of the time
# Run multiple times to see both READY and DEFERRED states
```

## Verify Cheap Model Enforcement

Check the output JSON - should ALWAYS recommend:
- ✅ `google-gemini-flash` (preferred)
- ✅ `claude-haiku-3-5` (fallback)
- ❌ NEVER `claude-sonnet-4` or other expensive models

## Integration Test

Add to a test heartbeat script:

```bash
#!/bin/bash
# test-heartbeat.sh

echo "🔍 Checking pending tasks..."

OUTPUT=$(node skills/task-manager/index.js 2>&1)
JSON=$(echo "$OUTPUT" | grep -E '^\{' | tail -1)

if [ -n "$JSON" ]; then
  STATUS=$(echo "$JSON" | jq -r '.status')
  
  case $STATUS in
    READY)
      echo "✅ Task ready to spawn"
      MODEL=$(echo "$JSON" | jq -r '.recommendation.model')
      echo "   Model: $MODEL (cheap ✓)"
      ;;
    DEFERRED)
      REASON=$(echo "$JSON" | jq -r '.reason')
      echo "⏸️  Task deferred: $REASON"
      echo "   VIP Lane protection active ✓"
      ;;
    *)
      echo "ℹ️  No tasks pending"
      ;;
  esac
fi
```

## Success Criteria

✅ Task queue persists in `memory/pending_tasks.json`  
✅ Manager outputs valid JSON status  
✅ Only cheap models recommended  
✅ Concurrency limit enforced (max 1)  
✅ Lock file prevents race conditions  
✅ Tasks can be added/removed cleanly  
✅ Integrates with heartbeat process  
