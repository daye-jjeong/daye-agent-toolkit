# Session Manager Skill

## Purpose
Provides automatic fallback/retry logic for spawning subagent sessions with robust model selection when encountering rate limits, timeouts, or model unavailability.

## Problem Solved
- **Rate Limits (429):** Automatic retry with backoff, then fallback to alternative models
- **Timeouts:** Intelligent retry strategy with model substitution
- **Model Unavailable:** Immediate fallback to next available model in chain
- **Task Continuity:** Ensures Orchestrator workflows don't fail due to transient model issues

## Core Features

### 1. Automatic Model Fallback
**Default Chain:**
```
gpt-5.2 → claude-sonnet-4-5 → gemini-3-pro → claude-haiku-4-5
```

**Custom Override:** Plans can specify custom fallback order per subtask

### 2. Partial Substitution
- Only failing workers use fallback
- Successful workers continue with original model
- Optimizes for cost and quality

### 3. Comprehensive Logging
**Log Location:** `~/.clawdbot/agents/main/logs/fallback_decisions.jsonl`

**What's Logged:**
- Original and fallback models
- Error type (rate_limit, timeout, model_unavailable)
- Attempt number and max attempts
- Timestamp and task label
- Reason for fallback

### 4. Retry Strategies
| Error Type | Strategy |
|------------|----------|
| **Rate Limit (429)** | Retry same model 3x with 5s delay, then fallback |
| **Timeout** | Retry once, then fallback |
| **Model Unavailable** | Immediate fallback (no retry) |
| **Unknown** | Retry 2x with exponential backoff, then fallback |

## API Reference

### `spawn_subagent_with_retry()`
```python
from skills.session_manager import spawn_subagent_with_retry

result = spawn_subagent_with_retry(
    task="데이터 수집 및 분석",
    model="openai-codex/gpt-5.2",
    label="data-worker",
    fallback_order=None,  # Use DEFAULT_FALLBACK_ORDER
    max_retries=3,
    retry_delay=5
)

# Returns:
# {
#   "success": bool,
#   "session_id": str | None,
#   "model_used": str,
#   "attempts": int,
#   "fallback_chain": List[str],
#   "error": str | None
# }
```

**Parameters:**
- `task` (str): Task description for the subagent
- `model` (str): Initial model to attempt
- `label` (str): Session label for tracking
- `fallback_order` (List[str], optional): Custom fallback chain
- `max_retries` (int): Max retries per model (default: 3)
- `retry_delay` (int): Seconds between retries (default: 5)

### `spawn_parallel_workers_with_fallback()`
```python
from skills.session_manager import spawn_parallel_workers_with_fallback

tasks = [
    {"task": "데이터 수집", "model": "gpt-5.2", "label": "worker-1"},
    {"task": "분석", "model": "claude-sonnet-4-5", "label": "worker-2"}
]

result = spawn_parallel_workers_with_fallback(
    tasks,
    fallback_order=None,
    partial_substitution=True
)

# Returns:
# {
#   "success": bool,
#   "workers": List[Dict],  # Result from each spawn
#   "failed": List[str],    # Labels of failed workers
#   "fallback_applied": int # Count of workers using fallback
# }
```

**Parameters:**
- `tasks` (List[Dict]): List of task specs with "task", "model", "label" keys
- `fallback_order` (List[str], optional): Custom fallback chain
- `partial_substitution` (bool): If True, only retry failing workers

## Usage Examples

### Example 1: Single Worker with Fallback
```python
result = spawn_subagent_with_retry(
    task="AI 트렌드 분석 리포트 작성",
    model="openai-codex/gpt-5.2",
    label="ai-trends-analysis"
)

if result["success"]:
    print(f"✅ Worker spawned: {result['session_id']}")
    print(f"   Model used: {result['model_used']}")
    print(f"   Total attempts: {result['attempts']}")
else:
    print(f"❌ All models failed: {result['error']}")
```

### Example 2: Orchestrator Parallel Workers
```python
# Define subtasks with initial models
tasks = [
    {
        "task": "데이터 수집 (2025 Q4 AI news)",
        "model": "google-gemini-flash",
        "label": "data-fetch"
    },
    {
        "task": "기업 동향 분석",
        "model": "anthropic/claude-sonnet-4-5",
        "label": "company-analysis"
    },
    {
        "task": "기술 트렌드 분석",
        "model": "anthropic/claude-opus-4",
        "label": "tech-analysis"
    }
]

# Spawn all workers with automatic fallback
result = spawn_parallel_workers_with_fallback(tasks)

print(f"Success: {result['success']}")
print(f"Workers spawned: {len(result['workers'])}")
print(f"Fallbacks applied: {result['fallback_applied']}")

for worker in result["workers"]:
    print(f"  - {worker['session_id']}: {worker['model_used']}")
```

### Example 3: Custom Fallback Order
```python
# For simple tasks, prioritize cheaper models
cheap_fallback = [
    "google-gemini-flash",
    "google-gemini-3-pro",
    "anthropic/claude-haiku-4-5"
]

result = spawn_subagent_with_retry(
    task="간단한 데이터 변환",
    model="google-gemini-flash",
    label="data-transform",
    fallback_order=cheap_fallback
)
```

## Integration Points

### With Orchestrator
The Orchestrator uses this skill when spawning subtask workers:

```python
# In Orchestrator Phase 2: Execution
from skills.session_manager import spawn_parallel_workers_with_fallback

# Build task list from execution plan
tasks = []
for subtask in execution_plan:
    tasks.append({
        "task": subtask["description"],
        "model": subtask["agent_model"],
        "label": subtask["label"]
    })

# Spawn all workers with fallback
result = spawn_parallel_workers_with_fallback(
    tasks,
    fallback_order=execution_plan.get("fallback_order"),  # From plan
    partial_substitution=True
)

# Log fallback decisions
for worker in result["workers"]:
    if worker["model_used"] != worker["original_model"]:
        log_execution(f"Fallback applied: {worker['model_used']}")
```

### With Task OS Guardrails
Works seamlessly with the existing guardrails system:

```python
from skills.task_policy_guardrails.examples.spawn_with_guardrails import spawn_with_guardrails
from skills.session_manager import spawn_subagent_with_retry

def spawn_with_guardrails_and_fallback(task, model, label, **kwargs):
    # Run guardrails first
    gate_result = pre_work_gate(task, session_id)
    
    if gate_result["blocked"]:
        # Handle task creation, etc.
        pass
    
    # Then spawn with fallback
    return spawn_subagent_with_retry(task, model, label, **kwargs)
```

## Monitoring

### View Fallback Log
```bash
# Last 20 fallback decisions
tail -n 20 ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | jq

# Count fallbacks by error type
cat ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | \
  jq -r '.error_type' | sort | uniq -c

# Fallback rate for specific model
cat ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | \
  jq -r 'select(.original_model == "openai-codex/gpt-5.2")' | wc -l
```

### Alert Conditions
Consider alerting when:
- Fallback rate > 30% for any model in 1 hour window
- All models in chain fail (critical failure)
- Specific model consistently unavailable (>5 consecutive failures)

## Testing

Run the test suite:
```bash
cd /Users/dayejeong/clawd
python3 tests/test_session_fallback.py
```

**Test Coverage:**
- Error classification (429, timeout, unavailable)
- Single worker fallback logic
- Parallel workers with partial substitution
- Custom fallback order override
- Fallback decision logging
- All models fail scenario

## Configuration

### Default Fallback Order
Edit `DEFAULT_FALLBACK_ORDER` in `spawn_with_fallback.py`:
```python
DEFAULT_FALLBACK_ORDER = [
    "openai-codex/gpt-5.2",
    "anthropic/claude-sonnet-4-5",
    "google-gemini-3-pro",
    "anthropic/claude-haiku-4-5"
]
```

### Retry Parameters
Adjust defaults in function calls:
- `max_retries`: Number of retries per model (default: 3)
- `retry_delay`: Seconds between retries (default: 5)
- `timeout`: Command timeout in seconds (default: 30)

## Known Limitations

1. **Session ID Extraction:** Relies on parsing `clawdbot sessions spawn` output format
   - May break if output format changes
   - Consider using structured JSON output if available

2. **Log File Growth:** `fallback_decisions.jsonl` grows unbounded
   - Consider adding log rotation (e.g., weekly cleanup)
   - Add to session cleanup scripts

3. **Parallel Spawn:** Workers spawn sequentially, not truly in parallel
   - Could be optimized with async/concurrent execution
   - Current approach ensures ordered logging

## Future Enhancements

- [ ] Async/concurrent worker spawning
- [ ] Log rotation and archival
- [ ] Real-time fallback rate monitoring dashboard
- [ ] Auto-adjust fallback order based on historical success rates
- [ ] Integration with cost tracking (model usage analytics)
- [ ] Webhook notifications for critical fallback events

---

**Version:** 1.0  
**Created:** 2026-02-04  
**Last Updated:** 2026-02-04 16:37:46 KST  
**Author:** Orchestrator Update Subagent
