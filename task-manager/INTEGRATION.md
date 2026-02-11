# Task Manager Integration Guide

## For Main Agent

### Heartbeat Integration

Add this to your heartbeat routine in `HEARTBEAT.md`:

```javascript
// Check for pending tasks
const { execSync } = require('child_process');

try {
  const output = execSync('node skills/task-manager/index.js 2>&1', { 
    encoding: 'utf8',
    timeout: 5000 
  });
  
  // Extract JSON output
  const jsonMatch = output.match(/\{[^}]+\}/);
  
  if (jsonMatch) {
    const status = JSON.parse(jsonMatch[0]);
    
    if (status.status === 'READY') {
      const rec = status.recommendation;
      
      // Spawn with cheap model (VIP Lane protection)
      await sessions_spawn({
        message: rec.prompt,
        model: rec.model,  // google-gemini-flash or claude-haiku-3-5
        background: true
      });
      
      // Remove task from queue after successful spawn
      execSync('node skills/task-manager/process-task.js');
      
      console.log(`✅ Spawned task with ${rec.model}`);
      
    } else if (status.status === 'DEFERRED') {
      // VIP Lane protected - max concurrency reached
      console.log(`⏸️ Task deferred: ${status.reason} (${status.pending_count} pending)`);
    }
  }
} catch (error) {
  console.error('Task manager check failed:', error.message);
}
```

### Adding Tasks Programmatically

```javascript
// From main agent or sub-agent
const fs = require('fs');
const tasksFile = 'memory/pending_tasks.json';

function addTask(prompt, priority = 1) {
  const tasks = JSON.parse(fs.readFileSync(tasksFile, 'utf8'));
  
  tasks.push({
    prompt: prompt,
    priority: priority,
    added_at: new Date().toISOString(),
    metadata: {
      source: 'agent',
      retry_count: 0
    }
  });
  
  fs.writeFileSync(tasksFile, JSON.stringify(tasks, null, 2));
}

// Example
addTask('Analyze yesterday's stock performance', 2);
```

### Command Line Helper

```bash
# Add task manually
./skills/task-manager/add-task.sh "Research AI trends"

# Check queue
cat memory/pending_tasks.json | jq

# Force run task manager
node skills/task-manager/index.js
```

## Status Codes

Task manager outputs JSON with these statuses:

### READY
Task is ready to spawn. Main agent should:
1. Call `sessions_spawn` with recommended model
2. Remove task with `process-task.js`

```json
{
  "status": "READY",
  "recommendation": {
    "model": "google-gemini-flash",
    "prompt": "Task description...",
    "metadata": {},
    "priority": 1
  },
  "pending_count": 3,
  "message": "Ready to spawn task with google-gemini-flash"
}
```

### DEFERRED
Task cannot run now due to VIP Lane protection:

```json
{
  "status": "DEFERRED",
  "reason": "concurrency_limit",
  "pending_count": 2,
  "active_sessions": 1
}
```

Reasons:
- `concurrency_limit`: Max background tasks reached
- `high_load`: System load too high (mock for now)

### NO_TASKS
No pending tasks:

```json
{
  "status": "NO_TASKS",
  "pending_count": 0
}
```

## Safety Guarantees

✅ **VIP Lane Protected**: Max 1 concurrent background task  
✅ **Cheap Models Only**: Forces gemini-flash or haiku  
✅ **Lock File**: Prevents race conditions  
✅ **Load Check**: Defers when system busy  
✅ **Main Session**: Never blocked or slowed  

## Error Handling

If spawning fails, keep the task in the queue:
- Main agent logs error
- Task remains in `pending_tasks.json`
- Will retry on next heartbeat

```javascript
try {
  await sessions_spawn(rec);
  execSync('node skills/task-manager/process-task.js');
} catch (error) {
  console.error('Spawn failed, task remains queued:', error);
  // Task stays in queue for next heartbeat
}
```
