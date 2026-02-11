# Task Policy Guardrails - Implementation Checklist

**Objective:** Enforce Notion Task linkage + deliverable upload for all work operations  
**Timeline:** 3 weeks (P0: Week 1, P1: Week 2, P2: Week 3)

---

## P0 - Critical Path (Week 1)

### Setup & Infrastructure
- [ ] Create skill directory structure:
  ```bash
  mkdir -p skills/task-policy-guardrails/{lib,tests}
  mkdir -p ~/.clawdbot/guardrails/{state,archive,audit}
  touch ~/.clawdbot/guardrails/violations.jsonl
  ```
- [ ] Create `skills/task-policy-guardrails/SKILL.md` (skill manifest)
- [ ] Add Notion API helper functions (`lib/notion_helper.py`)
  - [ ] `validate_task_url(url)` → bool
  - [ ] `extract_task_id(url)` → str
  - [ ] `get_task_properties(task_id)` → dict

### M1: sessions_spawn() Wrapper
- [ ] Create `agents/main/spawn.py`
- [ ] Import existing spawn logic from Clawdbot core
- [ ] Implement `spawn_with_guardrails()` wrapper function
- [ ] Add environment variable `GUARDRAILS_ENABLED=true` (default)
- [ ] Test: Spawn without Task URL → should block
- [ ] Test: Spawn with valid Task URL → should pass

### M2: Work Classification Logic
- [ ] Create `lib/classifier.py`
- [ ] Implement `classify_work(task_description)` → "trivial" | "deliverable"
- [ ] Heuristics:
  - [ ] Trivial: Q&A keywords ("what time", "how many", "status")
  - [ ] Trivial: Duration estimate <5min
  - [ ] Deliverable: Keywords ("create", "write", "analyze", "build")
  - [ ] Deliverable: Mentions file types (PDF, CSV, report, guide)
- [ ] Test with 20 example requests (10 trivial, 10 deliverable)
- [ ] Adjust thresholds based on false positive rate

### M3: Task URL Validation
- [ ] Add `lib/validator.py`
- [ ] Implement `extract_task_url(text)` using regex (https://notion.so/...)
- [ ] Implement `validate_notion_task(url)` → raises exception if 404/403
- [ ] Use NEW HOME API key: `~/.config/notion/api_key_daye_personal`
- [ ] Test with valid/invalid URLs
- [ ] Add graceful degradation if Notion API times out (>5s)

### M4: State File Schema
- [ ] Create `lib/state.py`
- [ ] Implement `create_state_file(session_id, task_url, work_type)`
- [ ] Implement `update_state_file(session_id, checkpoint_data)`
- [ ] Implement `read_state_file(session_id)` → dict
- [ ] Implement `archive_state_file(session_id)` (move to archive/)
- [ ] Test CRUD operations
- [ ] Add file locking for concurrent access

### M5: Task-Triage Integration
- [ ] Add function to `skills/task-triage/triage.py`:
  ```python
  def create_from_guardrails(task_description, auto_approve=False):
      """Called by guardrails when Task missing"""
      return handle_user_request(task_description, auto_approve)
  ```
- [ ] Update `spawn_with_guardrails()` to call triage on missing Task
- [ ] Test auto-create flow: User request → No Task → Prompt → Create → Spawn

### M6: Bypass Flag
- [ ] Add `--bypass-guardrails` flag to spawn command
- [ ] Add `--bypass-reason` parameter (required if bypassing)
- [ ] Log bypass events to violations.jsonl:
  ```jsonl
  {"type":"bypass","reason":"emergency fix","user":"main","timestamp":"..."}
  ```
- [ ] Test bypass: `sessions_spawn(task="...", bypass_guardrails=True, bypass_reason="...")`

---

## P1 - High Value (Week 2)

### M7: Post-Work Deliverable Validation
- [ ] Create `lib/deliverable_checker.py`
- [ ] Implement `extract_deliverables(subagent_output)` → list of URLs
- [ ] Check for patterns:
  - [ ] Notion URLs (child pages, attachments)
  - [ ] Cloud storage URLs (Google Drive, Dropbox, etc.)
  - [ ] Local paths (flag as invalid)
- [ ] Implement `is_accessible(url)` → bool (HTTP HEAD request)
- [ ] Test with sample subagent outputs

### M8: Session Completion Handler
- [ ] Create `agents/main/completion.py`
- [ ] Implement `handle_completion_with_guardrails(session_id, output)`
- [ ] Steps:
  1. Read state file
  2. Extract deliverables from output
  3. Validate accessibility
  4. Update Task body with deliverable URLs (if missing)
  5. Finalize state file
  6. Allow/block archival
- [ ] Hook into Clawdbot session lifecycle (research exact hook point)
- [ ] Test: Completion with valid deliverable → Pass
- [ ] Test: Completion without deliverable → Warn

### M9: Heartbeat Monitoring
- [ ] Add to `skills/heartbeat/main.py` (or create new heartbeat task):
  ```python
  def check_guardrails_state():
      for session in active_sessions:
          state_file = read_state_file(session.id)
          if session.duration > 10min and not state_file.last_updated:
              warn("Session stalled: no progress")
  ```
- [ ] Run every 5 minutes
- [ ] Update state file `last_heartbeat` timestamp

### M10: Violations Logging
- [ ] Implement `lib/logger.py`
- [ ] Function: `log_violation(type, session_id, details, blocked=True)`
- [ ] Violation types:
  - [ ] `missing_task` (no Task URL at spawn)
  - [ ] `missing_deliverable` (no accessible URL at completion)
  - [ ] `invalid_task_url` (404/403 from Notion)
  - [ ] `bypass` (emergency escape hatch used)
- [ ] Ensure JSONL append is atomic (file locking)
- [ ] Test with concurrent writes

### M11: Daily Audit Cron Job
- [ ] Create `scripts/cron/guardrails-daily-audit.sh`
- [ ] Parse violations.jsonl for last 24 hours
- [ ] Generate summary:
  - Total violations (by type)
  - Bypasses used (count + reasons)
  - Missing deliverables (>24h pending)
- [ ] Format as markdown report
- [ ] Send to Telegram JARVIS HQ (topic: 📰 뉴스/트렌드 or create new)
- [ ] Add to crontab: `0 1 * * * /path/to/guardrails-daily-audit.sh`
- [ ] Test manual run first

### M12: Comprehensive Tests
- [ ] Unit tests for each lib module (pytest):
  - [ ] `test_classifier.py` (20+ test cases)
  - [ ] `test_validator.py` (valid/invalid URLs, API failures)
  - [ ] `test_state.py` (CRUD operations, concurrency)
  - [ ] `test_deliverable_checker.py` (extraction, accessibility)
- [ ] Integration tests:
  - [ ] End-to-end: User request → Spawn → Work → Complete → Validate
  - [ ] Failure scenarios: Notion down, missing Task, no deliverable
- [ ] Test coverage goal: >80%
- [ ] Run: `pytest skills/task-policy-guardrails/tests/`

---

## P2 - Nice-to-Have (Week 3)

### M13: Emergency Disable Command
- [ ] Add CLI command: `clawdbot guardrails disable --duration 1h --reason "..."`
- [ ] Create lock file: `~/.clawdbot/guardrails/disabled.lock`
- [ ] Lock file content: `{"until": "2026-02-03T15:00:00Z", "reason": "emergency"}`
- [ ] Check lock file in `spawn_with_guardrails()` → bypass if active
- [ ] Auto-delete lock file after duration
- [ ] Add manual re-enable: `clawdbot guardrails enable`
- [ ] Log to violations.jsonl

### M14: Notion View for Missing Deliverables
- [ ] Create Notion database view in Tasks DB
- [ ] Filter: Tasks with no child pages/attachments + completed recently
- [ ] Sort by completion date (oldest first)
- [ ] Share view URL in daily audit report
- [ ] Optional: Auto-tag Tasks with "⚠️ Missing Deliverable" property

### M15: Auto-Retry Logic
- [ ] Update completion handler to retry deliverable check
- [ ] Retry schedule: 1h, 6h, 24h (max 3 attempts)
- [ ] Store retry count in state file
- [ ] After max retries → create follow-up Task
- [ ] Notify user on Telegram after each retry

### M16: Metrics Dashboard
- [ ] Create `~/.clawdbot/guardrails/metrics.json`
- [ ] Track daily:
  - [ ] Total spawns (with/without guardrails)
  - [ ] Violations by type
  - [ ] Bypass count + reasons
  - [ ] Average time to deliverable upload
- [ ] Generate weekly chart (matplotlib or ASCII chart)
- [ ] Include in weekly audit report

### M17: Weekly Cleanup Cron
- [ ] Create `scripts/cron/guardrails-weekly-cleanup.sh`
- [ ] Archive state files >30 days old
- [ ] Rotate violations.jsonl (keep last 90 days, compress older)
- [ ] Delete archived state files >1 year old
- [ ] Add to crontab: `0 2 * * 0 /path/to/guardrails-weekly-cleanup.sh`

### M18: User Documentation
- [ ] Write `skills/task-policy-guardrails/README.md`
- [ ] Cover:
  - [ ] What guardrails enforce
  - [ ] How to create Tasks properly
  - [ ] How to bypass (when appropriate)
  - [ ] Troubleshooting common errors
  - [ ] Metrics interpretation
- [ ] Add examples (good/bad patterns)
- [ ] Link from main AGENTS.md

---

## Validation Criteria (Done-Done Checklist)

Before marking P0/P1/P2 complete:

### P0 Complete When:
- [ ] All spawns with deliverable work require Task URL
- [ ] Trivial work bypasses guardrails correctly
- [ ] Auto-triage creates Tasks on user approval
- [ ] State files track all work sessions
- [ ] Tests pass (>80% coverage for P0 modules)

### P1 Complete When:
- [ ] Deliverable validation blocks archival if missing
- [ ] Daily audit report sent to Telegram (24h+ consecutive)
- [ ] Violations logged correctly (manual review confirms)
- [ ] Heartbeat detects stalled sessions
- [ ] Integration tests cover full lifecycle

### P2 Complete When:
- [ ] Emergency disable command tested (manual verify)
- [ ] Notion view shows real missing deliverables
- [ ] Auto-retry demonstrated (simulate 24h wait)
- [ ] Metrics dashboard generated (1 week data minimum)
- [ ] User docs peer-reviewed (by main agent)

---

## Rollback Plan

If guardrails cause significant disruption (>5 false blocks/day):

1. **Immediate:** Disable via emergency command
2. **Investigate:** Review violations.jsonl for patterns
3. **Adjust:** Tweak classification heuristics or thresholds
4. **Test:** Run against historical requests (last 30 days)
5. **Re-enable:** With updated logic + monitoring

**Rollback Trigger:** User explicitly requests disable due to productivity impact

---

**Estimated Effort:**
- P0: ~8-12 hours (core enforcement)
- P1: ~10-15 hours (validation + monitoring)
- P2: ~6-10 hours (polish + docs)
- **Total:** ~24-37 hours (3 weeks @ 8-12h/week)

**Success Metrics:**
- Zero deliverable work without Tasks (after 30-day ramp-up)
- <2% bypass rate (indicates good classification)
- >95% deliverables accessible within 24h of completion
