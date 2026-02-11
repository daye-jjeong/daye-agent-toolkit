# Task Manager - Auto-Resume System

**Version:** 0.1.0
**Updated:** 2026-02-09
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

## Purpose

Automatically resume failed or interrupted tasks with adaptive model selection while protecting the main session's API quota through VIP Lane protection.

## Key Features

### 1. **VIP Lane Protection**
- Max 3 concurrent background tasks
- Cheap models for simple/moderate work (Gemini Flash, Haiku)
- Complex tasks always use Opus with reserved capacity

### 2. **Adaptive Model Selection**
- Simple → Gemini Flash or Haiku
- Moderate → Sonnet (only when user quiet)
- Complex → Opus (VIP lane protected)

### 3. **Task Queue**
- Stored in: `memory/pending_tasks.json` (JSON format)
- FIFO processing with priority support
- Persistent across restarts with retry logic

## Usage

### From Main Agent (Heartbeat)
The main agent should call this during heartbeat checks:

```javascript
// In heartbeat logic
const result = execSync('node skills/task-manager/index.js 2>&1', { encoding: 'utf8' });
const jsonMatch = result.match(/\{.*\}/);

if (jsonMatch) {
  const status = JSON.parse(jsonMatch[0]);
  
  if (status.status === 'READY') {
    // Spawn the task with the recommended model
    const rec = status.recommendation;
    sessions_spawn({
      message: rec.prompt,
      model: rec.model  // Forces cheap model (gemini-flash or haiku)
    });
    
    // Remove task from queue
    execSync('node skills/task-manager/process-task.js');
  } else if (status.status === 'DEFERRED') {
    // VIP Lane protected - do nothing or log
    console.log(`Task deferred: ${status.reason}`);
  }
}
```

### Manual Run
```bash
node skills/task-manager/index.js
```

### Add Task to Queue
```bash
# Programmatically
node -e "
const fs = require('fs');
const tasks = JSON.parse(fs.readFileSync('memory/pending_tasks.json'));
tasks.push({
  prompt: 'Analyze this data...',
  priority: 1,
  added_at: new Date().toISOString()
});
fs.writeFileSync('memory/pending_tasks.json', JSON.stringify(tasks, null, 2));
"
```

### View Queue
```bash
cat memory/pending_tasks.json | jq
```

## Heartbeat Integration

Added to `HEARTBEAT.md` under automated checks:
```
- Run task manager every heartbeat
- Check for stuck tasks
- Report queue status if non-empty
```

## Configuration

Edit `skills/task-manager/index.js`:
- `PREFERRED_MODEL`: Default cheap model
- `MAX_CONCURRENT_TASKS`: Concurrency limit
- `MAX_LOAD_THRESHOLD`: System load limit (%)

## Safety Mechanisms

1. **Lock File**: Prevents multiple managers running
2. **Concurrency Limit**: Max 1 background task
3. **Load Check**: Defers tasks when system busy
4. **Model Enforcement**: Forces cheap models for all background work

## Task Schema

```json
[
  {
    "prompt": "Task description or prompt",
    "priority": 1,
    "added_at": "2026-02-01T12:00:00Z",
    "complexity": "simple|moderate|complex",
    "attempts": 0,
    "maxAttempts": 3,
    "nextRetryAt": "2026-02-01T12:05:00Z",
    "lastError": "Error message from previous attempt",
    "metadata": {
      "source": "heartbeat",
      "retry_count": 0
    }
  }
]
```

### Retry Logic

**Exponential Backoff:**
- Attempt 1 fails → wait 1 minute
- Attempt 2 fails → wait 2 minutes
- Attempt 3 fails → wait 4 minutes
- After 3 attempts → send fallback alert and remove from queue

**Fields:**
- `attempts`: Current attempt count (starts at 0)
- `maxAttempts`: Maximum attempts before giving up (default: 3)
- `nextRetryAt`: ISO timestamp when next retry should occur
- `lastError`: Error message from previous attempt

## Monitoring

Logs output to stdout with timestamps:
```
[2026-02-01T12:00:00.000Z] [INFO] Loaded 3 pending task(s)
[2026-02-01T12:00:01.000Z] [WARN] Max concurrent tasks reached (1/1)
[2026-02-01T12:00:01.000Z] [INFO] VIP Lane protected: deferring new tasks
```
