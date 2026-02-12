# Task Triage Skill - Full Documentation


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

## Purpose

Automate the classification and creation of work items in Obsidian vault, implementing the policy defined in AGENTS.md § 7 and § 8.

## Architecture

### Three-Tier Classification

```
┌─────────────────────────────────────────────┐
│         User Request                        │
│   "토스 API 연동 설계 문서 작성"            │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     Classification Engine                   │
│  • Keyword analysis                         │
│  • Duration detection                       │
│  • Follow-up check                          │
│  • Context matching                         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     Decision: Task                          │
│  Confidence: 75%                            │
│  Reasoning: "작성" keyword + 1-day scope    │
│  Parent: "토스 API 연동" Project            │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     Approval Gate                           │
│  • Dry-run preview (default)                │
│  • User confirmation                        │
│  • Auto-approve if "진행해"                 │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     Vault Creation                           │
│  • Create task .md in projects/              │
│  • Set Start Date = today                   │
│  • Prompt for Due Date                      │
│  • Link to Project                          │
│  • YAML frontmatter + body scaffold         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     Return Result                           │
│  Path: vault/projects/.../t-xxx-NNN.md     │
│  ID: t-xxx-NNN                              │
│  Status: Created                            │
└─────────────────────────────────────────────┘
```

## Classification Algorithm

### Step 1: Keyword Analysis

**Epic Indicators:**
- 플랫폼, 생태계, 전략, 이니셔티브, 프로그램, 캠페인
- Multi-month scope
- Multiple sub-projects expected

**Project Indicators:**
- 구현, 연동, 자동화, 시스템, 파이프라인, 아키텍처
- 1-2 week scope
- 3-10 tasks expected

**Task Indicators:**
- 리뷰, 작성, 확인, 수정, 테스트, 분석, 조회
- Hours to 1-day scope
- Single deliverable

### Step 2: Duration Detection

```python
duration_patterns = {
    "Task": r"(\d+분|\d+시간|오늘|내일|today|tomorrow)",
    "Project": r"(\d+주|이번 주|다음 주|week)",
    "Epic": r"(\d+개?월|quarter|분기)"
}
```

### Step 3: Follow-Up Detection

**Follow-up Keywords:**
- v2, 개선, 수정, 추가, 리팩토링
- based on, 이어서, 버전, 업데이트

**Action:**
- Search for parent Task/Project by title similarity
- Add as child page or new version
- DO NOT create separate Task

### Step 4: Context Matching

- Check recent Tasks for similar titles
- Check active Projects for related work
- Use similarity threshold (default: 0.8)

## Safety Features

### 1. Dry-Run Mode (Default)

```python
# Default behavior
classification = classify_request("user request")
# Shows preview, NO writes

# Explicit execution
result = create_vault_entry(classification, dry_run=False)
```

### 2. Approval Gate

```python
if not auto_approve:
    approve = input("Proceed with task creation? (y/N): ")
    if approve not in ['y', 'yes', '진행', '진행해']:
        return {"approved": False}
```

### 3. Validation

- Validate vault directory accessible
- Check for duplicate task IDs
- Check for duplicate titles
- Rollback on error

### 4. Logging

All operations logged to `~/.clawdbot/agents/main/logs/task-triage.log`:
```
2026-02-03 12:00:00 | CLASSIFY | "토스 API 문서 리뷰" → Task (90%)
2026-02-03 12:00:05 | APPROVE  | User confirmed
2026-02-03 12:00:10 | CREATE   | Task created: t-proj-001
```

## Integration Points

### With AGENTS.md § 2.6 Pre-Work Checklist

```python
# In main agent session
def handle_user_work_request(message):
    # 1. Check if task creation needed
    if requires_task_creation(message):
        # 2. Auto-classify
        from skills.task_triage.triage import handle_user_request
        result = handle_user_request(message, auto_approve=user_said_approve)
        
        # 3. Spawn sub-agent with Task URL
        spawn_subagent(
            task=f"Task ID: {result['task_id']}\n{message}",
            model="anthropic/claude-sonnet-4-5"
        )
```

### With Follow-Up Consolidation Policy

```python
# Detect follow-up
classification = classify_request("개선 작업")
if classification["is_followup"]:
    # Find parent Task
    parent = find_similar_task(classification["suggested_title"])
    if parent:
        # Add as child page instead of new Task
        add_child_page(parent["id"], classification)
```

## Configuration Options

Edit `config.json`:

```json
{
  "vault_path": "~/openclaw/vault",
  "dry_run_default": true,
  "auto_approve_keywords": ["진행해", "do it", "approve"],
  "similarity_threshold": 0.8,
  "classification_rules": {
    "epic_keywords": [...],
    "project_keywords": [...],
    "task_keywords": [...]
  }
}
```

## Error Handling

### Vault I/O Errors

```python
try:
    task_path = write_task(project_dir, task_data)
except PermissionError:
    log_error("Vault directory not writable")
except FileExistsError:
    log_error("Duplicate task ID detected")
```

### Classification Confidence < 50%

```python
if classification["confidence"] < 0.5:
    # Prompt user for manual classification
    print(f"⚠️  Low confidence ({classification['confidence']:.0%})")
    print(f"   Suggested: {classification['type']}")
    override = input("   Override? (Epic/Project/Task or Enter to accept): ")
    if override:
        classification["type"] = override
```

## Testing

### Unit Tests

```bash
# Test classification logic
python3 -m pytest skills/task-triage/tests/test_classifier.py

# Test cases:
# - Epic: "로닉 플랫폼 구축 전략" → Epic (90%)
# - Project: "토스 API 연동" → Project (85%)
# - Task: "API 문서 리뷰" → Task (95%)
# - Follow-up: "v2 개선 작업" → Task, is_followup=True
```

### Integration Tests

```bash
# Test vault integration (dry-run)
python3 skills/task-triage/tests/test_vault_dry_run.py

# Test full pipeline
python3 skills/task-triage/tests/test_end_to_end.py
```

### Manual Testing

```bash
# Test classification only
python3 skills/task-triage/triage.py "토스 API 문서 리뷰"

# Test with execution (requires approval)
python3 skills/task-triage/triage.py "토스 API 문서 리뷰" --execute

# Test auto-approve
python3 skills/task-triage/triage.py "토스 API 문서 리뷰" --auto-approve

# Test override
python3 skills/task-triage/triage.py "애매한 요청" --override-classification Task
```

## Performance

- **Classification**: < 100ms (no LLM calls, rule-based)
- **Vault write**: < 10ms (local I/O)
- **Total**: < 200ms for full pipeline

## Token Cost

**Zero tokens** - Pure Python logic, no LLM calls.

This is a Tier 1 (Script) implementation per AGENTS.md § 6.

## Future Enhancements

1. **ML-based classification** (if rule-based accuracy < 80%)
2. **Similarity search** using embeddings for parent detection
3. **Auto-populate Task body** with template based on type
4. **Integration with calendar** for Due date suggestions
5. **Batch processing** for multiple requests

## Rollback

If skill causes issues:

```bash
# Disable auto-triage
mv skills/task-triage skills/task-triage.disabled

# Manual Task creation
python3 skills/task-manager/task_manager.py create --name "manual task"
```

## See Also

- **Policy**: AGENTS.md § 7 (Task-Centric Policy)
- **Hierarchy**: AGENTS.md § 8 (Epic-Project-Task Structure)
- **Rules**: `triage/CLASSIFICATION_RULES.md`
- **Integration Check**: scripts/check_integrations.py
