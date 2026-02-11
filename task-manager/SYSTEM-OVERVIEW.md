# Auto-Resume System - Complete Overview

## 🎯 Mission

**Protect the VIP Lane:** Keep the main session responsive and preserve Sonnet quota by running background tasks with cheap models only.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MAIN AGENT                             │
│                    (Claude Sonnet)                          │
│                  💎 VIP LANE - Protected                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Heartbeat Check
                       ▼
           ┌───────────────────────┐
           │   Task Manager        │
           │   (index.js)          │
           │                       │
           │  • Check queue        │
           │  • Check load         │
           │  • Check concurrency  │
           │  • Recommend model    │
           └───────────┬───────────┘
                       │
                       │ JSON Output
                       ▼
              ┌────────────────┐
              │   STATUS:      │
              │   READY or     │
              │   DEFERRED     │
              └────────┬───────┘
                       │
           ┌───────────┴────────────┐
           │                        │
       READY                    DEFERRED
           │                        │
           ▼                        ▼
    ┌──────────────┐        ┌──────────────┐
    │ Spawn Task   │        │ Do Nothing   │
    │ with Cheap   │        │ (Protected)  │
    │ Model        │        │              │
    └──────┬───────┘        └──────────────┘
           │
           ▼
    ┌──────────────────┐
    │  SUB-AGENT       │
    │  (Gemini Flash   │
    │   or Haiku)      │
    │  🚌 Economy Lane │
    └──────────────────┘
```

## 📁 Files

```
skills/task-manager/
├── index.js              # Main task manager logic
├── process-task.js       # Remove task after spawn
├── add-task.sh          # CLI helper to add tasks
├── check-and-spawn.sh   # Shell wrapper (optional)
├── README.md            # Quick start guide
├── SKILL.md             # Skill specification
├── INTEGRATION.md       # Integration guide for main agent
├── TEST.md              # Test procedures
└── SYSTEM-OVERVIEW.md   # This file

memory/
├── pending_tasks.json   # Task queue (persistent)
└── task-manager.lock    # Lock file (temporary)
```

## 🔒 Safety Mechanisms

### 1. VIP Lane Protection
- **Main Session:** Uses Claude Sonnet (expensive, powerful)
- **Background Tasks:** FORCED to use Gemini Flash or Haiku (cheap)
- **No Quota Drain:** Background work never touches Sonnet quota

### 2. Concurrency Limit
- **Max 1 Background Task:** Prevents system overload
- **Active Session Check:** Counts running sub-agents
- **Defers When Busy:** Protects main session responsiveness

### 3. Lock File
- **Single Instance:** Only one task manager runs at a time
- **Stale Lock Detection:** Auto-removes locks older than 1 minute
- **Race Condition Prevention:** Safe for concurrent heartbeats

### 4. Load Check
- **System Load Threshold:** 80% (currently mocked)
- **Defers High Load:** Waits for system to be idle
- **Future Extension:** Can integrate real CPU/memory metrics

## 🔄 Workflow

### Normal Operation (Task Ready)
1. **Heartbeat** triggers task manager
2. **Manager** checks queue → finds task
3. **Manager** checks load → OK
4. **Manager** checks sessions → 0 active
5. **Manager** outputs `READY` with `google-gemini-flash`
6. **Main Agent** spawns sub-agent with cheap model
7. **Main Agent** removes task from queue
8. **Sub-agent** runs in background (Economy Lane)

### Protected Operation (System Busy)
1. **Heartbeat** triggers task manager
2. **Manager** checks queue → finds task
3. **Manager** checks sessions → 1 already active
4. **Manager** outputs `DEFERRED` (concurrency_limit)
5. **Main Agent** does nothing (VIP Lane protected)
6. **Task** remains in queue for next heartbeat

## 📊 Status Outputs

### READY ✅
```json
{
  "status": "READY",
  "recommendation": {
    "model": "google-gemini-flash",
    "prompt": "Task description...",
    "priority": 1
  },
  "pending_count": 2,
  "message": "Ready to spawn task with google-gemini-flash"
}
```

### DEFERRED ⏸️
```json
{
  "status": "DEFERRED",
  "reason": "concurrency_limit",
  "pending_count": 3,
  "active_sessions": 1
}
```

### NO_TASKS ℹ️
```
[INFO] No pending tasks to process
```

## 🎮 Usage

### Add Task (Manual)
```bash
./skills/task-manager/add-task.sh "Research latest AI papers"
```

### Add Task (Programmatic)
```javascript
const fs = require('fs');
const tasks = JSON.parse(fs.readFileSync('memory/pending_tasks.json'));
tasks.push({
  prompt: "Analyze stock market trends",
  priority: 1,
  added_at: new Date().toISOString()
});
fs.writeFileSync('memory/pending_tasks.json', JSON.stringify(tasks, null, 2));
```

### Check Queue
```bash
cat memory/pending_tasks.json | jq
```

### Run Manager (Manual Test)
```bash
node skills/task-manager/index.js
```

## 🔗 Heartbeat Integration

Added to `HEARTBEAT.md`:
```javascript
// During heartbeat
const output = execSync('node skills/task-manager/index.js 2>&1');
const status = JSON.parse(output.match(/\{.*\}/)[0]);

if (status.status === 'READY') {
  await sessions_spawn({
    message: status.recommendation.prompt,
    model: status.recommendation.model  // Cheap model enforced
  });
  execSync('node skills/task-manager/process-task.js');
}
```

## ✅ Guarantees

| What | How | Verified |
|------|-----|----------|
| **VIP Lane Protected** | Main session never spawns expensive models for background work | ✅ Model forced in recommendation |
| **Quota Saved** | All background tasks use Gemini Flash or Haiku | ✅ CONFIG.PREFERRED_MODEL |
| **No Overload** | Max 1 concurrent background task | ✅ Concurrency check |
| **No Race Conditions** | Lock file prevents multiple managers | ✅ Lock acquisition |
| **Persistent Queue** | Tasks survive restarts | ✅ JSON file on disk |
| **Main Session Responsive** | Background work doesn't block main agent | ✅ Separate sub-agents |

## 🚀 Next Steps

1. **Real Load Metrics:** Replace mock with actual CPU/memory check
2. **Priority Queue:** Process high-priority tasks first
3. **Retry Logic:** Auto-retry failed tasks with backoff
4. **Task Timeout:** Kill stuck tasks after N minutes
5. **Metrics Dashboard:** Track task completion rates

## 📝 Notes

- Task manager is **passive**: it recommends, main agent decides
- Tasks are **FIFO** by default (can add priority sorting)
- Lock file lives in `memory/` (temporary, safe to delete if stale)
- Queue file is **persistent** (keep in git for visibility)
- Cheap models: Gemini Flash (preferred) > Haiku (fallback)

---

**Status:** ✅ ACTIVE  
**VIP Lane:** 🟢 PROTECTED  
**Last Updated:** 2026-02-02
