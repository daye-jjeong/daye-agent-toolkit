# Session Manager API Details

## `spawn_subagent_with_retry()`

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

## `spawn_parallel_workers_with_fallback()`

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
