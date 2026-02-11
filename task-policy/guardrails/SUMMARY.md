# Task Policy Guardrails - Executive Summary

## Purpose
Systematically enforce the Task-Centric Policy (AGENTS.md §7) by blocking work without Notion Tasks and ensuring all deliverables are accessible (not local-only paths).

## Core Mechanism

```
┌─────────────────┐
│ User Request    │
└────────┬────────┘
         │
    ┌────▼─────┐
    │ Gate 1:  │ ◄── Pre-Work (BLOCKING)
    │ Task?    │     • Classify: Trivial vs Deliverable
    └────┬─────┘     • Validate: Task URL exists + accessible
         │           • Auto-Fix: Call task-triage if missing
    ┌────▼─────┐
    │ Spawn    │
    │ Subagent │
    └────┬─────┘
         │
    ┌────▼─────┐
    │ Gate 2:  │ ◄── Post-Work (WARNING→BLOCKING)
    │ Upload?  │     • Extract: Deliverable URLs from output
    └────┬─────┘     • Validate: Accessible (not local path)
         │           • Retry: 1h, 6h, 24h (max 3x)
    ┌────▼─────┐
    │ Archive  │
    └──────────┘
```

## Key Features

### 1. Pre-Work Gate (Blocking)
- **Trigger:** `sessions_spawn()` called with work request
- **Checks:**
  - Is this trivial work (<5min, Q&A)? → Bypass
  - Does Task URL exist in request? → Validate
  - User approves auto-create? → Triage → Proceed
- **Result:** Block spawn if no Task + no approval

### 2. Post-Work Gate (Warning → Blocking)
- **Trigger:** Subagent completes with deliverable
- **Checks:**
  - Accessible URL in output (Notion, cloud storage)?
  - Local-only path? → Warn
  - 24h elapsed without upload? → Block archival
- **Result:** Hold session until deliverable uploaded

### 3. Auto-Enforcement Pipeline
- **Stage 1 (Pre):** Intercept spawn → Classify → Validate
- **Stage 2 (During):** Heartbeat monitor (every 5min)
- **Stage 3 (Post):** Extract deliverables → Validate accessibility
- **Stage 4 (Audit):** Daily report (violations, bypasses, missing uploads)

### 4. Escape Hatches
- **Bypass Flag:** `--bypass-guardrails --bypass-reason "emergency"`
  - Logs to violations.jsonl
  - Use for: API outages, time-critical work, false positives
- **Emergency Disable:** `clawdbot guardrails disable --duration 1h`
  - Temporarily disables all gates
  - Auto-re-enables after duration

## Integration Points

| Component | Hook Point | Purpose |
|-----------|-----------|---------|
| `sessions_spawn()` | Wrap spawn logic | Pre-work gate (Gate 1) |
| `task-triage` | Add `create_from_guardrails()` | Auto-create Tasks when missing |
| Session completion | Wrap archival logic | Post-work gate (Gate 2) |
| Heartbeat | Add guardrails check | Monitor progress during work |
| Cron (daily 01:00) | New job | Audit violations + missing deliverables |
| Cron (weekly Sun 02:00) | New job | Cleanup old state files |

## Data Model

### State File (`.state/guardrails-[session-id].json`)
Tracks work lifecycle:
- Task URL + Notion ID
- Work type (trivial/deliverable)
- Gate status (passed/warned/blocked)
- Checkpoints (pre-work, heartbeats, post-work)
- Deliverables (URLs + accessibility)
- Bypass metadata (if used)

### Violations Log (`~/.clawdbot/guardrails/violations.jsonl`)
Append-only log:
- Timestamp + session ID
- Violation type (missing_task, missing_deliverable, invalid_url, bypass)
- Blocked (true/false)
- User response (declined, approved, etc.)

## Implementation Timeline

### Week 1 (P0 - Critical Path)
Focus: Core enforcement working
- Pre-work gate blocking spawns without Tasks
- Work classification (trivial vs deliverable)
- Task URL validation (Notion API)
- State file tracking
- Task-triage integration for auto-create
- Bypass flag for emergencies

**Success Criteria:** No deliverable work proceeds without Task

### Week 2 (P1 - High Value)
Focus: Post-work validation + monitoring
- Post-work gate checking deliverable upload
- Session completion handler
- Heartbeat monitoring for progress
- Violations logging (JSONL)
- Daily audit cron job (Telegram reports)
- Comprehensive test suite (80%+ coverage)

**Success Criteria:** All deliverables validated + daily reports working

### Week 3 (P2 - Nice-to-Have)
Focus: Polish + user experience
- Emergency disable command
- Notion view for missing deliverables
- Auto-retry logic (1h, 6h, 24h)
- Metrics dashboard (violations over time)
- Weekly cleanup cron job
- User documentation + troubleshooting guide

**Success Criteria:** System runs autonomously + user-friendly

## Failure Modes & Mitigations

| Failure | Symptom | Mitigation |
|---------|---------|-----------|
| Notion API down | Task validation fails | Graceful degradation (warn + allow) |
| False positive | Trivial work blocked | Use bypass flag + adjust classifier |
| State file corruption | Unreadable JSON | Recreate from session log + Notion query |
| Deliverable forgotten | 24h, no upload | Create follow-up Task + notify user |

## Success Metrics (After 30-Day Ramp-Up)

- **Zero** deliverable work without Tasks
- **<2%** bypass rate (indicates accurate classification)
- **>95%** deliverables accessible within 24h
- **<1** false positive per week (trivial work blocked)

## Maintenance

- **Daily:** Audit report (automated via cron)
- **Weekly:** Review bypass reasons + adjust if needed
- **Monthly:** Analyze metrics + tune classification thresholds
- **Quarterly:** User feedback survey + documentation updates

---

**Related Files:**
- Full spec: `skills/task-policy-guardrails/SPEC.md`
- Implementation checklist: `skills/task-policy-guardrails/IMPLEMENTATION_CHECKLIST.md`
- Policy context: `AGENTS.md` §7 (Task-Centric), §2 (Session Protection)
