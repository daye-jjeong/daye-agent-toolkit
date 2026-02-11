# Task Policy Guardrails Skill - Design Spec

**Version:** 1.1  
**Last Updated:** 2026-02-04  
**Purpose:** Enforce Notion Task linkage + deliverable upload for all work operations

## Language Policy (CRITICAL)
**Default Language:** Korean (한국어)

ALL deliverables MUST be in Korean unless user explicitly requests English.
- Applies to: Reports, guides, documentation, analysis, Task bodies
- Exceptions: User says "in English", or English-speaking audience specified
- Enforcement: Subagent prompts default to Korean, deliverable validation checks language

---

## 1. Requirements

### Functional Requirements
- **FR1:** Block subagent spawn if no Task exists for deliverable work (>5min, non-trivial)
- **FR2:** Validate Task URL accessibility before allowing work to proceed
- **FR3:** Enforce deliverable upload after subagent completion (no local-only paths)
- **FR4:** Auto-create Task via task-triage if missing (with user approval)
- **FR5:** Track Task→Subagent mapping in state file for audit trail
- **FR6:** Provide escape hatch for emergencies (manual override with reason logged)

### Non-Functional Requirements
- **NFR1:** <500ms latency on work classification check
- **NFR2:** Zero false positives on trivial work (status checks, Q&A)
- **NFR3:** Graceful degradation if Notion API unavailable (warn, log, allow)

---

## 2. UX Flow

### Pre-Work Gate (Before Subagent Spawn)
```
User Request → Classify Work → [Trivial?] → YES → Allow (bypass)
                                    ↓ NO
                              [Task Exists?] → YES → Validate URL → Allow
                                    ↓ NO
                              Auto-Triage Prompt → User Approves → Create Task → Allow
                                                        ↓ NO
                                                   Block + Notify User
```

### Post-Work Gate (After Subagent Completion)
```
Subagent Reports Done → [Deliverable Created?] → NO → Log Warning (pass)
                                    ↓ YES
                         [Accessible URL?] → YES → Update Task Body → Done
                                    ↓ NO
                         Block Archival → Prompt User → Attach/Upload → Done
```

---

## 3. Hard Gate Rules

### Gate 1: Pre-Work (BLOCKING)
**Trigger:** `sessions_spawn()` called with `task` parameter containing work request  
**Criteria for PASS:**
- Work classified as Trivial (Q&A, status check, <5min), OR
- Valid Task URL present in `task` parameter (format: `Task URL: https://notion.so/...`), OR
- User explicitly bypasses (`--bypass-guardrails` flag + reason)

**Criteria for BLOCK:**
- Deliverable work (>5min, file/report/analysis) AND no Task URL AND user declines auto-create

**Action on BLOCK:**
1. Return error: `GuardrailsViolation: Task required for deliverable work`
2. Log to `~/.clawdbot/guardrails/violations.jsonl`
3. Prompt user with auto-triage option

### Gate 2: Post-Work (WARNING → BLOCKING)
**Trigger:** Subagent session completion (status=done)  
**Criteria for WARN:**
- Subagent reports deliverable created BUT no accessible URL found in final output

**Criteria for BLOCK:**
- 24 hours elapsed since completion AND still no accessible URL in Task body

**Action on WARN:**
1. Notify user: "Upload deliverable to Task: [URL]"
2. Hold session archival (keep in `completed` state)
3. Retry check in 1 hour (max 3 retries)

**Action on BLOCK:**
1. Archive session with flag `deliverable_missing=true`
2. Create follow-up Task: "Upload deliverable for [original Task]"

---

## 4. Auto-Enforcement Pipeline

### Pipeline Stages
```
Stage 1: Intercept (pre-work)
  └─ Hook: sessions_spawn() wrapper in agents/main/spawn.py
  └─ Check: Work classification + Task URL validation
  └─ Output: ALLOW | BLOCK | PROMPT_USER

Stage 2: Track (during work)
  └─ Hook: Heartbeat monitor (every 5min)
  └─ Check: State file exists + Task updated
  └─ Output: Log progress to guardrails state

Stage 3: Validate (post-work)
  └─ Hook: Session completion handler in agents/main/completion.py
  └─ Check: Deliverable accessibility in Task body
  └─ Output: PASS | WARN | BLOCK_ARCHIVE

Stage 4: Audit (daily)
  └─ Hook: Cron job at 01:00 (cleanup-guardrails-audit.sh)
  └─ Check: Review violations.jsonl + missing deliverables
  └─ Output: Daily report to JARVIS HQ (Telegram)
```

---

## 5. Templates & Standardization

### State File Schema
**Location:** `.state/guardrails-[session-id].json`  
**Format:**
```json
{
  "sessionId": "agent:main:subagent:xxx",
  "taskUrl": "https://notion.so/...",
  "taskId": "8e0e8902-0c60-...",
  "workType": "deliverable|trivial",
  "gateStatus": "passed|warned|blocked",
  "checkpoints": [
    {"stage": "pre-work", "timestamp": "2026-02-03T14:00:00Z", "result": "passed"}
  ],
  "deliverables": [
    {"type": "notion_attachment", "url": "https://...", "verified": true}
  ],
  "bypass": {
    "used": false,
    "reason": null,
    "approver": null
  }
}
```

### Violation Log Schema
**Location:** `~/.clawdbot/guardrails/violations.jsonl`  
**Format:**
```jsonl
{"timestamp":"2026-02-03T14:00:00Z","sessionId":"...","violation":"missing_task","blocked":true,"userResponse":"declined"}
{"timestamp":"2026-02-03T15:00:00Z","sessionId":"...","violation":"missing_deliverable","blocked":false,"retryCount":1}
```

---

## 6. Integration Points

### A. `sessions_spawn()` Wrapper
**File:** `agents/main/spawn.py` (create if missing)  
**Hook Point:** Wrap existing spawn logic  
**Pseudocode:**
```python
def spawn_with_guardrails(task, model, label, **kwargs):
    # 1. Check bypass flag
    if kwargs.get('bypass_guardrails'):
        log_bypass(reason=kwargs['bypass_reason'])
        return original_spawn(task, model, label, **kwargs)
    
    # 2. Classify work
    work_type = classify_work(task)
    if work_type == 'trivial':
        return original_spawn(task, model, label, **kwargs)
    
    # 3. Check Task URL
    task_url = extract_task_url(task)
    if not task_url:
        # 4. Auto-triage prompt
        create_task = prompt_user_auto_triage(task)
        if create_task:
            task_url = auto_create_task_via_triage(task)
        else:
            raise GuardrailsViolation("Task required")
    
    # 5. Validate Task accessibility
    validate_notion_task(task_url)
    
    # 6. Create state file
    create_guardrails_state(session_id, task_url, work_type)
    
    # 7. Proceed
    return original_spawn(task, model, label, **kwargs)
```

### B. Task-Triage Skill Integration
**File:** `skills/task-triage/triage.py`  
**Hook Point:** Add `create_from_guardrails()` function  
**Purpose:** Called when Gate 1 blocks and user approves auto-create

### C. Session Completion Handler
**File:** `agents/main/completion.py` (create if missing)  
**Hook Point:** Wrap session archival logic  
**Purpose:** Validate deliverable upload before archival

### D. Cron Jobs
**New Jobs:**
1. **Daily Audit:** `scripts/cron/guardrails-daily-audit.sh` at 01:00
   - Read violations.jsonl (last 24h)
   - Check for pending deliverable uploads
   - Send summary to Telegram JARVIS HQ
2. **Weekly Cleanup:** `scripts/cron/guardrails-weekly-cleanup.sh` at 02:00 Sunday
   - Archive old state files (>30 days)
   - Rotate violations.jsonl (keep 90 days)

---

## 7. Data Model & State Files

### State File Lifecycle
1. **Create:** At pre-work gate pass (Stage 1)
2. **Update:** Every heartbeat if session active (Stage 2)
3. **Finalize:** At post-work gate (Stage 3)
4. **Archive:** After 30 days or when Task archived

### Storage Structure
```
~/.clawdbot/guardrails/
  ├── state/
  │   ├── guardrails-{session-id}.json  # Active tracking
  │   └── archive/                       # Completed (30+ days)
  ├── violations.jsonl                   # Append-only log
  └── audit/
      └── YYYY-MM-DD-report.md           # Daily summaries
```

---

## 8. Failure Modes & Rollback

### Failure Mode 1: Notion API Down
- **Symptom:** Task URL validation fails
- **Response:** Log warning, allow work to proceed, retry validation on completion
- **Rollback:** N/A (graceful degradation)

### Failure Mode 2: False Positive (Trivial Work Blocked)
- **Symptom:** User reports work blocked incorrectly
- **Response:** Use `--bypass-guardrails` flag + reason
- **Rollback:** Adjust classification heuristics in `classify_work()`

### Failure Mode 3: State File Corruption
- **Symptom:** State file unreadable/malformed
- **Response:** Recreate from session log + Notion Task query
- **Rollback:** Delete corrupted file, log incident

### Failure Mode 4: Deliverable Upload Forgotten
- **Symptom:** 24h elapsed, no URL in Task
- **Response:** Create follow-up Task, notify user
- **Rollback:** Manual intervention (user uploads, marks resolved)

### Emergency Escape Hatch
**Command:** `clawdbot guardrails disable --duration 1h --reason "emergency"`  
**Effect:** Temporarily disable all gates, log to violations.jsonl  
**Auto-Re-enable:** After specified duration or manual re-enable

---

## 9. Implementation Milestones

### P0 (Critical Path - Week 1)
- [ ] **M1:** Create `sessions_spawn()` wrapper with Gate 1 (pre-work blocking)
- [ ] **M2:** Implement work classification logic (trivial vs deliverable)
- [ ] **M3:** Add Task URL validation (Notion API check)
- [ ] **M4:** Create state file schema + CRUD functions
- [ ] **M5:** Integrate with existing `task-triage` skill for auto-create
- [ ] **M6:** Add bypass flag (`--bypass-guardrails`) to spawn command

### P1 (High Value - Week 2)
- [ ] **M7:** Implement Gate 2 (post-work deliverable validation)
- [ ] **M8:** Create session completion handler wrapper
- [ ] **M9:** Add heartbeat monitoring for state file updates
- [ ] **M10:** Implement violations.jsonl logging
- [ ] **M11:** Create daily audit cron job + Telegram reporting
- [ ] **M12:** Write comprehensive tests (unit + integration)

### P2 (Nice-to-Have - Week 3)
- [ ] **M13:** Add emergency disable command
- [ ] **M14:** Create Notion view for "Missing Deliverables"
- [ ] **M15:** Implement auto-retry logic for deliverable checks
- [ ] **M16:** Add metrics dashboard (violations over time, bypass frequency)
- [ ] **M17:** Weekly cleanup cron job for old state files
- [ ] **M18:** User documentation + troubleshooting guide

---

**End of Spec**
