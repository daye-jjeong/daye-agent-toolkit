---
name: task-policy-guardrails
description: Hard gate + auto-enforcement for deliverable accessibility (Notion upload) in Task Policy workflow
version: 1.0.0
status: Implemented
---

# Task Policy Guardrails Skill

**Status:** ✅ Implemented (2026-02-04)  
**Version:** 1.0.0  
**Purpose:** Enforce Notion Task linkage + deliverable upload for all work operations

---

## Quick Start

### Pre-Work Gate (Before Spawning Subagent)

```python
from skills.task_policy_guardrails.lib.gates import pre_work_gate, GuardrailsViolation

try:
    result = pre_work_gate(
        task_description="AI 트렌드 분석 리포트 작성. Task URL: https://notion.so/...",
        session_id=session_id
    )
    # Proceed with spawn
    spawn_subagent(...)
except GuardrailsViolation as e:
    # Work blocked - create Task or handle error
    print(f"Blocked: {e}")
```

### Post-Work Gate (After Subagent Completion)

```python
from skills.task_policy_guardrails.lib.gates import post_work_gate

result = post_work_gate(
    session_id=session_id,
    final_output=subagent_report,
    auto_upload=True  # Auto-upload local files to Notion
)

if result["passed"]:
    archive_session(session_id)
else:
    # Warn user to upload deliverables
    notify_user(result["message"])
```

---

## Features

### Gate 1: Pre-Work Enforcement (BLOCKING)
- ✅ **Work classification** - Auto-detect trivial vs deliverable work
- ✅ **Task URL validation** - Verify Task exists and is accessible
- ✅ **Auto-triage integration** - Create Task if missing (with approval)
- ✅ **Bypass mechanism** - Emergency override with audit log
- ✅ **State tracking** - Record decision trail in state files

### Gate 2: Post-Work Validation (WARNING → BLOCKING)
- ✅ **Deliverable detection** - Extract URLs from work output
- ✅ **Accessibility check** - Reject local-only paths
- ✅ **Auto-upload** - Convert local files to Notion child pages
- ✅ **Task update** - Add deliverable links to Task '산출물' section
- ✅ **Korean-by-default** - All uploads in Korean with proper footer

### Monitoring & Audit
- ✅ **Violations log** - JSONL append-only audit trail
- ✅ **Daily reports** - Violation summary and trends
- ✅ **State files** - Per-session tracking in `~/.clawdbot/guardrails/state/`

---

## Implementation

### Library Structure

```
skills/task-policy-guardrails/lib/
├── __init__.py              # Package exports
├── classifier.py            # Work type classification
├── validator.py             # Task URL + deliverable validation
├── state.py                 # State file CRUD
├── deliverable_checker.py   # Extract & check deliverables
├── notion_uploader.py       # Auto-upload to Notion
├── logger.py                # Violations logging
└── gates.py                 # Main enforcement gates
```

### State Files

**Location:** `~/.clawdbot/guardrails/state/guardrails-{session_id}.json`

**Schema:**
```json
{
  "session_id": "agent:main:subagent:xxx",
  "task_url": "https://notion.so/...",
  "task_id": "8e0e8902...",
  "work_type": "deliverable|trivial|bypassed",
  "gate_status": "passed|warned|blocked",
  "checkpoints": [
    {"stage": "pre-work", "timestamp": "...", "result": "passed"}
  ],
  "deliverables": [
    {"type": "notion_page", "url": "https://...", "verified": true}
  ],
  "bypass": {
    "used": false,
    "reason": null,
    "approver": null
  }
}
```

### Violations Log

**Location:** `~/.clawdbot/guardrails/violations.jsonl`

**Format:**
```jsonl
{"timestamp":"2026-02-04T10:00:00Z","session_id":"...","violation":"missing_task","blocked":true,"user_response":"declined"}
```

---

## Usage Examples

### Example 1: Normal Flow (Task Exists)

```python
# User: "Analyze calendar conflicts and write report"
# Agent adds Task URL to spawn request

result = pre_work_gate(
    task_description="Analyze calendar conflicts. Task URL: https://notion.so/task-123",
    session_id="agent:main:subagent:calendar-analysis"
)
# → ✅ Pre-work gate passed - Task validated

# Subagent completes work...

result = post_work_gate(
    session_id="agent:main:subagent:calendar-analysis",
    final_output="""
    ## 산출물
    - Report: https://notion.so/calendar-conflicts-report
    """
)
# → ✅ All deliverables accessible - can archive
```

### Example 2: Auto-Upload Flow (Local Files)

```python
# Subagent creates local markdown file
final_output = """
## 산출물
- Guide: ./docs/complete_guide.md
"""

result = post_work_gate(
    session_id="...",
    final_output=final_output,
    created_files=["./docs/complete_guide.md"],
    auto_upload=True  # Enable auto-upload
)
# → 📤 Auto-uploaded 1 deliverables to Notion
# → ✅ Task updated with deliverable link
```

### Example 3: Bypass Flow (Emergency)

```python
result = pre_work_gate(
    task_description="Emergency: Restart crashed service",
    session_id="...",
    bypass=True,
    bypass_reason="Production outage - time critical"
)
# → ⚠️ Guardrails bypassed (logged to violations.jsonl)
```

---

## Configuration

### Environment Variables

- `GUARDRAILS_ENABLED=true` (default: true)
- `NOTION_API_KEY_PATH=~/.config/notion/api_key_daye_personal`

### Tunable Parameters

Edit values in `lib/classifier.py`:
- `TRIVIAL_TIME_THRESHOLD = 5` (minutes)
- `TRIVIAL_KEYWORDS` (list of keywords)
- `DELIVERABLE_KEYWORDS` (list of keywords)

Edit values in `lib/gates.py`:
- `auto_upload` (default: True)
- `language` (default: "ko" for Korean)

---

## Testing

### Run Unit Tests

```bash
# All tests
python3 -m pytest skills/task-policy-guardrails/tests/ -v

# Specific test file
python3 -m pytest skills/task-policy-guardrails/tests/test_classifier.py -v
python3 -m pytest skills/task-policy-guardrails/tests/test_gates.py -v
```

### Run Verification Script

```bash
./skills/task-policy-guardrails/tests/verify_implementation.sh
```

**Expected output:**
```
=== Task Policy Guardrails - Implementation Verification ===
1️⃣  Checking directory structure...
  ✓ skills/task-policy-guardrails/lib
  ...
✅ Implementation verification complete!
```

### Manual Testing

```bash
# Test work classifier
python3 skills/task-policy-guardrails/lib/classifier.py

# Test state management
python3 skills/task-policy-guardrails/lib/state.py

# Test gates
python3 skills/task-policy-guardrails/lib/gates.py

# Test example wrappers
python3 skills/task-policy-guardrails/examples/spawn_with_guardrails.py
python3 skills/task-policy-guardrails/examples/completion_with_guardrails.py
```

---

## Integration

### Workflow Integration Points

| Component | Hook Point | Implementation |
|-----------|-----------|---------------|
| **sessions_spawn()** | Before spawn | Call `pre_work_gate()` |
| **Session completion** | After done | Call `post_work_gate()` |
| **task-triage** | Auto-create | Call when Task missing |
| **Heartbeat** | Every 5 min | Update state file |
| **Cron** | Daily 01:00 | Generate audit report |

### Example Integration (sessions_spawn wrapper)

```python
# In agents/main/spawn.py (or equivalent)

from skills.task_policy_guardrails.lib.gates import pre_work_gate, GuardrailsViolation

def spawn_subagent(task, model, label, **kwargs):
    """Spawn subagent with guardrails"""
    
    # Generate session ID
    session_id = generate_session_id()
    
    # Check guardrails
    if not kwargs.get("bypass_guardrails"):
        try:
            gate_result = pre_work_gate(
                task_description=task,
                session_id=session_id
            )
        except GuardrailsViolation as e:
            # Auto-create Task if missing
            if "Task required" in str(e):
                task_url = auto_create_task_via_triage(task)
                task = f"{task}\nTask URL: {task_url}"
                gate_result = pre_work_gate(task, session_id)
            else:
                raise
    
    # Proceed with original spawn logic
    return original_spawn(task, model, label, session_id=session_id, **kwargs)
```

---

## Troubleshooting

### "GuardrailsViolation: Task required for deliverable work"

**Cause:** Work classified as deliverable, but no Task URL provided  
**Fix:** Either:
1. Create Task manually and add URL to request
2. Approve auto-create when prompted
3. Use bypass flag if truly urgent (emergency only)

### "Task URL validation failed (404)"

**Cause:** Task URL not accessible  
**Fix:** 
- Verify Task exists in NEW HOME Notion workspace
- Check integration permissions
- Ensure Task is not archived

### "Deliverable validation failed: local path not accessible"

**Cause:** Subagent returned local file path instead of accessible URL  
**Fix:**
- Enable `auto_upload=True` in `post_work_gate()`
- Or manually upload file to Notion and update Task

### Auto-upload fails

**Cause:** File too large (>20MB) or invalid format  
**Fix:**
- Use external hosting for large files
- Check file format is supported (.md, .pdf, .csv, etc.)

---

## Language Policy (Korean-by-Default)

**ALL deliverables MUST be in Korean unless user explicitly requests English.**

**Enforcement:**
- Notion uploader defaults to Korean footer (`FOOTER_TEMPLATE_KO`)
- Task bodies use Korean template (from `skills/task-policy/POLICY.md`)
- Auto-generated reports in Korean

**Override:**
```python
upload_deliverable_to_notion(
    ...,
    language="en"  # Force English
)
```

---

## Files Created

### Core Library (8 files)
- `lib/__init__.py` - Package exports
- `lib/classifier.py` - Work classification (172 lines)
- `lib/validator.py` - Validation logic (157 lines)
- `lib/state.py` - State file management (230 lines)
- `lib/deliverable_checker.py` - Deliverable extraction (207 lines)
- `lib/notion_uploader.py` - Notion upload automation (201 lines)
- `lib/logger.py` - Violations logging (153 lines)
- `lib/gates.py` - Main enforcement gates (373 lines)

### Tests (2 files)
- `tests/test_classifier.py` - Unit tests for classifier (82 lines)
- `tests/test_gates.py` - Integration tests for gates (188 lines)

### Examples (2 files)
- `examples/spawn_with_guardrails.py` - Spawn wrapper example (186 lines)
- `examples/completion_with_guardrails.py` - Completion handler example (138 lines)

### Verification (1 file)
- `tests/verify_implementation.sh` - Implementation verification script (163 lines)

**Total:** 13 files, ~2,450 lines of code

---

## Related Documentation

- **SPEC.md** - Complete technical design specification
- **README.md** - Skill overview and quick reference
- **IMPLEMENTATION_CHECKLIST.md** - Build checklist (for reference)
- **AGENTS.md §7** - Task-Centric Policy (why this skill exists)
- **skills/task-policy/POLICY.md** - Task Policy operating rules

---

## Roadmap

- [x] **2026-02-04:** Core implementation complete
- [ ] **2026-W06:** Production integration (spawn wrapper)
- [ ] **2026-W06:** Cron job for daily audit reports
- [ ] **2026-W07:** 30-day ramp-up + tuning
- [ ] **2026-W10:** First quarterly review

---

**Questions?** See examples in `examples/` or run verification script.
