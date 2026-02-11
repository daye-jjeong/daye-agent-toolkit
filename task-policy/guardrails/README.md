# Task Policy Guardrails Skill

**Status:** Design Phase  
**Version:** 1.0  
**Owner:** Main Agent  
**Last Updated:** 2026-02-03

---

## Quick Start

This skill enforces Notion Task linkage and deliverable upload for all work operations.

**Read in order:**
1. **[SUMMARY.md](./SUMMARY.md)** - Executive overview (5 min read)
2. **[SPEC.md](./SPEC.md)** - Complete design spec (15 min read)
3. **[IMPLEMENTATION_CHECKLIST.md](./IMPLEMENTATION_CHECKLIST.md)** - Build guide (reference)

---

## What This Skill Does

### Before Work Starts (Gate 1)
- ✅ Classifies work as trivial (bypass) or deliverable (require Task)
- ✅ Validates Notion Task URL exists and is accessible
- ✅ Auto-creates Task via task-triage if missing (with user approval)
- ❌ Blocks subagent spawn if no Task + user declines

### After Work Completes (Gate 2)
- ✅ Extracts deliverable URLs from subagent output
- ✅ Validates accessibility (no local-only paths)
- ⚠️ Warns if no accessible URL found
- ❌ Blocks session archival after 24h if still missing

### Continuous Monitoring
- 🔍 Heartbeat checks (every 5min) during work
- 📊 Daily audit reports (violations, bypasses, missing uploads)
- 🧹 Weekly cleanup (archive old state files, rotate logs)

---

## Key Files (After Implementation)

```
skills/task-policy-guardrails/
├── README.md                          # This file
├── SUMMARY.md                         # Executive overview
├── SPEC.md                            # Complete design spec
├── IMPLEMENTATION_CHECKLIST.md        # Build guide
├── SKILL.md                           # Skill manifest (TODO: P0)
├── lib/
│   ├── classifier.py                  # Work type classification (TODO: P0)
│   ├── validator.py                   # Task URL + deliverable validation (TODO: P0)
│   ├── state.py                       # State file CRUD (TODO: P0)
│   ├── notion_helper.py               # Notion API wrappers (TODO: P0)
│   ├── deliverable_checker.py         # Post-work validation (TODO: P1)
│   └── logger.py                      # Violations logging (TODO: P1)
└── tests/
    ├── test_classifier.py             # Unit tests (TODO: P1)
    ├── test_validator.py
    ├── test_state.py
    ├── test_deliverable_checker.py
    └── test_integration.py            # End-to-end tests (TODO: P1)
```

**State files (runtime):**
```
~/.clawdbot/guardrails/
├── state/
│   └── guardrails-{session-id}.json   # Active work tracking
├── archive/                            # Completed state files (30+ days)
├── violations.jsonl                    # Append-only violation log
└── audit/
    └── YYYY-MM-DD-report.md            # Daily audit summaries
```

---

## Integration Points

| System Component | Change Required | Priority |
|-----------------|----------------|----------|
| `sessions_spawn()` | Wrap with guardrails check | P0 |
| `task-triage` skill | Add `create_from_guardrails()` | P0 |
| Session completion | Wrap archival logic | P1 |
| Heartbeat monitor | Add guardrails state check | P1 |
| Cron jobs | Add daily audit + weekly cleanup | P1 |

---

## Usage Examples

### Normal Flow (Task Exists)
```python
# User: "Analyze calendar conflicts and write report"
# Agent internally:
sessions_spawn(
    task="Analyze calendar conflicts. Task URL: https://notion.so/xxx",
    model="anthropic/claude-sonnet-4-5",
    label="calendar-conflict-analysis"
)
# → Gate 1 validates Task URL → Proceeds
# → Subagent completes → Gate 2 checks report uploaded to Notion → Pass
```

### Auto-Create Flow (Task Missing)
```python
# User: "Build expense tracking automation"
# Agent internally:
sessions_spawn(
    task="Build expense tracking automation",  # No Task URL!
    model="anthropic/claude-sonnet-4-5"
)
# → Gate 1 detects missing Task
# → Prompts user: "Create Task for this work? (Epic/Project/Task)"
# → User approves → task-triage creates Task
# → Adds Task URL to spawn request → Proceeds
```

### Bypass Flow (Emergency)
```python
# User: "Emergency fix: restart crashed service NOW"
# Agent internally:
sessions_spawn(
    task="Restart crashed service (emergency)",
    bypass_guardrails=True,
    bypass_reason="Production outage - time critical"
)
# → Gate 1 logs bypass → Proceeds immediately
# → Violation logged to violations.jsonl for audit
```

---

## Configuration

**Environment Variables:**
- `GUARDRAILS_ENABLED=true` (default: true)
- `NOTION_API_KEY_PATH=~/.config/notion/api_key_daye_personal`
- `GUARDRAILS_STATE_DIR=~/.clawdbot/guardrails/state`

**Tunable Parameters (in SKILL.md):**
- `trivial_work_threshold_minutes=5` (work <5min bypasses gates)
- `deliverable_retry_hours=[1, 6, 24]` (retry schedule for missing uploads)
- `state_archive_days=30` (when to archive completed state files)

---

## Testing

**Run unit tests:**
```bash
pytest skills/task-policy-guardrails/tests/ -v
```

**Run integration tests:**
```bash
pytest skills/task-policy-guardrails/tests/test_integration.py -v
```

**Manual validation:**
```bash
# Test pre-work gate
clawdbot sessions spawn --task "Build report" --model sonnet  # Should block

# Test bypass
clawdbot sessions spawn --task "Quick fix" --bypass-guardrails \
  --bypass-reason "testing" --model sonnet  # Should pass

# Check violations log
cat ~/.clawdbot/guardrails/violations.jsonl | jq .
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
**Cause:** Task URL not accessible (deleted, wrong workspace, no permissions)  
**Fix:** Verify Task exists in NEW HOME Notion workspace, check sharing settings

### "Deliverable validation failed: local path not accessible"
**Cause:** Subagent returned local file path instead of accessible URL  
**Fix:** Upload file to Notion Task (attachment or child page), update Task body

### Too many false positives (trivial work blocked)
**Cause:** Classification heuristics too aggressive  
**Fix:** Adjust `trivial_work_threshold_minutes` or classifier keywords in `lib/classifier.py`

---

## Roadmap

- [x] **2026-02-03:** Design spec completed
- [ ] **2026-W06:** P0 implementation (core enforcement)
- [ ] **2026-W07:** P1 implementation (validation + monitoring)
- [ ] **2026-W08:** P2 implementation (polish + docs)
- [ ] **2026-W09:** Production deployment + 30-day ramp-up
- [ ] **2026-W13:** First quarterly review + tuning

---

## Related Documentation

- **AGENTS.md §7:** Task-Centric Policy (why this skill exists)
- **AGENTS.md §2:** Session Protection Policy (integration point)
- **skills/task-policy/POLICY.md:** Task Policy operating rules
- **memory/policy_project_task_classification.md:** Work classification logic
- **skills/task-triage/SKILL.md:** Auto-Task creation integration

---

**Questions?** See [SPEC.md](./SPEC.md) for detailed technical design or [IMPLEMENTATION_CHECKLIST.md](./IMPLEMENTATION_CHECKLIST.md) for build steps.
