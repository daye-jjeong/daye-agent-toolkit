# Session Manager Integration & Examples

## Example 1: Single Worker with Fallback

```python
result = spawn_subagent_with_retry(
    task="AI 트렌드 분석 리포트 작성",
    model="openai-codex/gpt-5.2",
    label="ai-trends-analysis"
)

if result["success"]:
    print(f"Worker spawned: {result['session_id']}")
    print(f"   Model used: {result['model_used']}")
    print(f"   Total attempts: {result['attempts']}")
else:
    print(f"All models failed: {result['error']}")
```

## Example 2: Orchestrator Parallel Workers

```python
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

result = spawn_parallel_workers_with_fallback(tasks)

print(f"Success: {result['success']}")
print(f"Workers spawned: {len(result['workers'])}")
print(f"Fallbacks applied: {result['fallback_applied']}")

for worker in result["workers"]:
    print(f"  - {worker['session_id']}: {worker['model_used']}")
```

## Example 3: Custom Fallback Order

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

## Orchestrator Integration

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

## Task OS Guardrails Integration

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
