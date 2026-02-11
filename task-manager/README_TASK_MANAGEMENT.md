# Task Manager - Notion Task Management Skill

## Purpose
Python skill for managing Notion Tasks with standardized templates, progress tracking, and deliverable management. Enforces task-centric workflow policies.

## Features
- ✅ Create Tasks with standardized template body
- ✅ Update progress logs (internal, not user-facing)
- ✅ Add deliverables with versioning (v1, v2, etc.)
- ✅ Close Tasks with completion summary
- ✅ Dry-run mode for previewing changes
- ✅ No external dependencies (stdlib only)

## Commands

### 1. Create Task
```bash
./task_manager.py create \
  --name "Task Name" \
  --purpose "Why this task exists" \
  --goal "What success looks like" \
  --acceptance-criteria "Criterion 1|Criterion 2|Criterion 3" \
  --task-breakdown "Step 1|Step 2|Step 3" \
  --project-id "PROJECT_NOTION_ID" \
  --project-url "https://notion.so/..." \
  --priority "High" \
  --area "Development" \
  --tags "ai,automation" \
  --related-links "https://example.com/ref" \
  --dry-run  # Optional: preview without creating
```

**Output:**
```json
{
  "status": "success",
  "task_id": "12345...",
  "url": "https://www.notion.so/..."
}
```

### 2. Update Progress
```bash
./task_manager.py update-progress \
  --task-id "TASK_NOTION_ID" \
  --entry "Completed phase 1. Encountered issue with API rate limits. Resolved by adding exponential backoff." \
  --status "In Progress" \
  --dry-run  # Optional
```

**Output:**
```json
{
  "status": "success",
  "message": "Progress log updated"
}
```

### 3. Add Deliverable
```bash
./task_manager.py add-deliverable \
  --task-id "TASK_NOTION_ID" \
  --version "v1" \
  --url "https://notion.so/deliverable-page" \
  --summary "Initial implementation with core features" \
  --format "Notion page" \
  --dry-run  # Optional
```

**Output:**
```json
{
  "status": "success",
  "message": "Deliverable added"
}
```

### 4. Close Task
```bash
./task_manager.py close \
  --task-id "TASK_NOTION_ID" \
  --summary "Completed all acceptance criteria. Deliverables: [v1 URL]. Lessons learned: Start with simple model for data fetching." \
  --dry-run  # Optional
```

**Output:**
```json
{
  "status": "success",
  "message": "Task closed"
}
```

## Usage Examples

### Example 1: Simple Task Lifecycle
```bash
# 1. Create Task
RESULT=$(./task_manager.py create \
  --name "Create morning briefing skill" \
  --purpose "Automate morning briefing for Daye" \
  --goal "Script that fetches weather, calendar, news" \
  --acceptance-criteria "Weather API integrated|Calendar events fetched|News summarized" \
  --task-breakdown "Research APIs|Write script|Test output" \
  --priority "High")

TASK_ID=$(echo $RESULT | jq -r '.task_id')
TASK_URL=$(echo $RESULT | jq -r '.url')

# 2. Update progress during work
./task_manager.py update-progress \
  --task-id "$TASK_ID" \
  --entry "Weather API integrated successfully. Using OpenWeatherMap." \
  --status "In Progress"

# 3. Add deliverable when complete
./task_manager.py add-deliverable \
  --task-id "$TASK_ID" \
  --version "v1" \
  --url "https://notion.so/morning-briefing-v1" \
  --summary "Working script with all three data sources" \
  --format "Python script (Notion page)"

# 4. Close Task
./task_manager.py close \
  --task-id "$TASK_ID" \
  --summary "All features working. Deliverable at $TASK_URL. Next: add cron scheduling."
```

### Example 2: Follow-up Work (v2 Iteration)
```bash
# Instead of creating new Task, add v2 to existing Task
TASK_ID="existing-task-id-here"

# Add new deliverable version
./task_manager.py add-deliverable \
  --task-id "$TASK_ID" \
  --version "v2" \
  --url "https://notion.so/morning-briefing-v2" \
  --summary "Added error handling and retry logic based on feedback" \
  --format "Python script (Notion page)"

# Update progress
./task_manager.py update-progress \
  --task-id "$TASK_ID" \
  --entry "v2 improvements: added exponential backoff for API failures, improved logging" \
  --status "In Progress"
```

### Example 3: Dry-Run Preview
```bash
# Preview Task creation before executing
./task_manager.py create \
  --name "Test Task" \
  --purpose "Testing template" \
  --goal "See how template looks" \
  --dry-run

# Output shows properties and body preview without creating page
```

## Integration with Sub-Agents

### Pattern 1: Sub-agent creates Task at start
```python
# In sub-agent initialization
import subprocess
import json

def create_work_task(name, purpose, goal):
    cmd = [
        "./skills/task-manager/task_manager.py", "create",
        "--name", name,
        "--purpose", purpose,
        "--goal", goal,
        "--acceptance-criteria", "TBD",
        "--task-breakdown", "TBD"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    
    return data['task_id'], data['url']

# Usage
task_id, task_url = create_work_task(
    name="Research AI trends 2026",
    purpose="Provide insights for strategic planning",
    goal="Comprehensive report on AI trends"
)

print(f"Task created: {task_url}")
```

### Pattern 2: Sub-agent updates progress silently
```python
def log_progress(task_id, entry, status="In Progress"):
    """Log progress without user-facing messages"""
    cmd = [
        "./skills/task-manager/task_manager.py", "update-progress",
        "--task-id", task_id,
        "--entry", entry,
        "--status", status
    ]
    
    subprocess.run(cmd, capture_output=True, text=True)
    # No output to user - internal log only

# Usage during work
log_progress(task_id, "Analyzed 50 research papers. Key themes emerging.")
log_progress(task_id, "Encountered rate limit on API. Implemented backoff.")
log_progress(task_id, "Draft report complete. Starting review.")
```

### Pattern 3: Sub-agent adds deliverable at completion
```python
def add_final_deliverable(task_id, version, url, summary):
    cmd = [
        "./skills/task-manager/task_manager.py", "add-deliverable",
        "--task-id", task_id,
        "--version", version,
        "--url", url,
        "--summary", summary,
        "--format", "Notion page"
    ]
    
    subprocess.run(cmd, capture_output=True, text=True)

# Usage
add_final_deliverable(
    task_id=task_id,
    version="v1",
    url=deliverable_page_url,
    summary="AI Trends 2026 report with 10 key insights and recommendations"
)
```

### Pattern 4: Sub-agent closes Task when done
```python
def complete_task(task_id, summary):
    cmd = [
        "./skills/task-manager/task_manager.py", "close",
        "--task-id", task_id,
        "--summary", summary
    ]
    
    subprocess.run(cmd, capture_output=True, text=True)

# Usage
complete_task(
    task_id=task_id,
    summary=f"Completed successfully. Deliverable: {deliverable_url}. Insights shared with main agent."
)
```

## Policy Enforcement

### ✅ Required Workflow
1. **Before work:** Create Task (if deliverable expected)
2. **During work:** Update progress log (internal, silent)
3. **When deliverable ready:** Add to Task (not local path)
4. **At completion:** Close Task with summary

### ❌ Violations to Avoid
- Creating Tasks without using template
- Progress updates sent to user (should be internal only)
- Deliverables as local file paths
- Follow-up work as separate Tasks (should be v2 under original)
- Leaving Tasks without completion summary

### 🔄 Follow-Up Consolidation
**Rule:** Related work goes under same Task, NOT new Task.

**Check before creating Task:**
```bash
# Is this related to existing Task?
# If YES → Add as v2/v3 deliverable
# If NO → Create new Task
```

**Example:**
```bash
# Original Task: "Create AI trends report"
# Follow-up: "Add competitor analysis section"

# ❌ WRONG: Create new Task "Add competitor analysis"
# ✅ RIGHT: Add v2 deliverable to existing Task

./task_manager.py add-deliverable \
  --task-id "ORIGINAL_TASK_ID" \
  --version "v2" \
  --url "https://notion.so/ai-trends-v2" \
  --summary "Added competitor analysis section based on feedback"
```

## Configuration

### Notion API Key
- **Path:** `~/.config/notion/api_key_daye_personal`
- **Workspace:** NEW HOME (personal)

### Database IDs
- **Tasks DB:** `8e0e8902-0c60-4438-8bbf-abe10d474b9b`
- **Projects DB:** `92f50099-1567-4f34-9827-c197238971f6`

### Required Task Properties
- Name (title)
- Status (status): Not Started | In Progress | Done | Blocked
- Start Date (date): Auto-set when created
- Priority (select): High | Medium | Low
- Project (relation): Link to Project if applicable
- Area (select): Work domain
- Tags (multi_select): Relevant tags

## Error Handling

### Common Issues

**1. API Key Not Found**
```
ERROR: Notion API key not found at ~/.config/notion/api_key_daye_personal
```
**Fix:** Ensure API key file exists and is readable.

**2. Invalid Task ID**
```
ERROR: Notion API error: 404 - Object not found
```
**Fix:** Verify Task ID is correct (from Notion URL: `notion.so/...-TASK_ID`).

**3. Missing Required Arguments**
```
ERROR: the following arguments are required: --name
```
**Fix:** Provide all required arguments for the command.

**4. Rate Limit**
```
ERROR: Notion API error: 429 - Rate limit exceeded
```
**Fix:** Wait 1 minute and retry. Consider batching operations.

## Testing

### Dry-Run Mode
All commands support `--dry-run` flag to preview changes:
```bash
# Preview Task creation
./task_manager.py create --name "Test" --purpose "Test" --goal "Test" --dry-run

# Preview progress update
./task_manager.py update-progress --task-id "..." --entry "Test entry" --dry-run
```

### Manual Testing Checklist
- [ ] Create Task with all properties → Verify in Notion
- [ ] Update progress → Check Progress Log section updated
- [ ] Add deliverable → Check Deliverables section updated
- [ ] Close Task → Verify Status=Done and completion summary added
- [ ] Dry-run mode → Confirm no actual changes made

## Dependencies
**None** - Pure Python 3 stdlib:
- `urllib.request` (HTTP)
- `json` (JSON parsing)
- `argparse` (CLI)
- `datetime` (timestamps)
- `os` (file paths)

No external packages required. Fully self-contained.

## See Also
- **TEMPLATES.md:** Detailed template structure definitions
- **AGENTS.md § 7:** Task-Centric Policy
- **AGENTS.md § 7.5:** Follow-Up Consolidation Policy
- **policy_deliverable_accessibility.md:** Deliverable accessibility requirements
