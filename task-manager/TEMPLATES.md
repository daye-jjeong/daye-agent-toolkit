# Task Manager - Task Template Reference
**Last Updated:** 2026-02-09
**Status:** Legacy Notion Templates (Migrated to YAML/JSON)

## Purpose
Standardized templates for Projects and Tasks to ensure consistent tracking, progress logging, and deliverable management.

---

## 📁 Project Template

### Properties
```json
{
  "Name": "Project Name",
  "Type": "📁 Project",
  "Parent": "[Epic ID or null]",
  "Status": "Not Started | In Progress | Completed | Archived",
  "Priority": "High | Medium | Low",
  "Due": "YYYY-MM-DD",
  "Owner": "Daye",
  "Tasks": "[Relation to Tasks DB]",
  "Deliverables": "[List of deliverable URLs]"
}
```

### Page Structure

```markdown
# [Project Name]

## 📋 Overview
**Goal:** [Clear 1-2 sentence project goal]
**Scope:** [What's in/out of scope]
**Success Criteria:** [Measurable outcomes]

---

## 🎯 Objectives
- [ ] Objective 1
- [ ] Objective 2
- [ ] Objective 3

---

## 📊 Tasks
[Linked view from Tasks DB filtered by Project]

---

## 🚀 Key Milestones
| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Milestone 1 | YYYY-MM-DD | ⏳ |
| Milestone 2 | YYYY-MM-DD | ⏳ |

---

## 🔗 Resources
- [Link 1]
- [Link 2]

---

## 📝 Decisions & Notes
*Record key decisions, trade-offs, and context here.*

---

## 📦 Deliverables
*Final outputs will be linked here upon completion.*
```

---

## ✅ Task Template

### Properties
```json
{
  "Name": "Task Name",
  "Status": "Not Started | In Progress | Done | Blocked",
  "Priority": "High | Medium | Low",
  "Due": "YYYY-MM-DD (ASK USER)",
  "Start Date": "[Auto-set when work begins]",
  "Project": "[Relation to Project]",
  "Area": "[Work area/domain]",
  "Tags": "[Relevant tags]",
  "Assignee": "Daye"
}
```

### Page Structure (Full Body)

```markdown
# [Task Name]

## 📋 Context
**Purpose:** [Why this task exists]
**Part of:** [Project URL]
**Requested by:** [User or system]
**Created:** [YYYY-MM-DD HH:MM KST]

---

## 🎯 Goals & Acceptance Criteria
**Goal:** [What success looks like]

**Acceptance Criteria:**
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

---

## 🗂️ Task Breakdown
*High-level steps (not subtasks):*
1. Step 1
2. Step 2
3. Step 3

---

## 🔍 Progress Log (Internal)
*Chronological checkpoints during execution. NOT user-facing.*

**Format:** Each entry includes timestamp (YYYY-MM-DD HH:MM), AI model used, and agent type.

### [YYYY-MM-DD HH:MM] 작업 시작
**Model:** [gpt-5.2 / claude-sonnet-4-5 / etc.] | **Agent:** [main / subagent]
- Initial setup complete
- Analyzed requirements

### [YYYY-MM-DD HH:MM] 중간 체크포인트 (optional)
**Model:** [model name] | **Agent:** [main / subagent]
- Completed phase 1
- Encountered issue: [description]
- Resolution: [how fixed]

### [YYYY-MM-DD HH:MM] 완료/산출물 생성
**Model:** [model name] | **Agent:** [main / subagent]
- Deliverable v1 completed
- Final deliverable: [URL or description]

---

## 🎨 Deliverables
*All outputs from this task. MUST be accessible (no local-only paths).*

### Version History
- **v1** ([YYYY-MM-DD]): [Child page URL or embedded content]
  - Summary: [Brief description]
  - Format: [Notion page / PDF / Code]
  
- **v2** ([YYYY-MM-DD]): [URL if iterated]
  - Changes: [What was updated]

---

## 💡 Decisions & Trade-offs
*Key decisions made during execution.*

| Decision | Rationale | Date |
|----------|-----------|------|
| Decision 1 | Why chosen | YYYY-MM-DD |
| Decision 2 | Why chosen | YYYY-MM-DD |

---

## 🔗 Related Links
- [Related Task/Project]
- [External resource]

---

## ✅ Completion Summary
*Filled when Status → Done*

**Completed:** [YYYY-MM-DD HH:MM KST]
**Final deliverables:** [List of URLs]
**Lessons learned:** [Quick notes]
```

---

## Child Page Structure (Large Deliverables)

**When to use:** Reports, guides, or documents >10KB

**Template:**
```markdown
# [Deliverable Name] (v1)

**Task:** [Parent Task URL]
**Created:** [YYYY-MM-DD]
**Status:** Draft | Final

---

[Main content goes here]

---

## Change Log
- **v1** (YYYY-MM-DD): Initial version
```

---

## Update Locations Summary

| **What** | **Where** | **When** |
|----------|-----------|----------|
| Status | Task properties | Start, progress, completion |
| Start Date | Task properties | When work begins |
| Progress checkpoints | Task body → Progress Log | During execution (internal, with timestamp HH:MM + model + agent type) |
| Deliverable v1 | Task body → Deliverables | First version complete |
| Deliverable v2+ | Task body → Deliverables (versioned) | Iterations/updates |
| Decisions | Task body → Decisions & Trade-offs | As decisions made |
| Completion summary | Task body → Completion Summary | When Status → Done |
| Child pages | As child of Task | Large reports (>10KB) |
| External links | Task body → Related Links | Reference materials |

---

## Policy Enforcement

### ✅ Required (MANDATORY)
- **Every deliverable work** → Task in Notion
- **Progress updates** → Progress Log section (internal only)
- **Deliverables** → Accessible URLs (Notion pages/child pages, NOT local paths)
- **Follow-up work** → Add to existing Task (v2, v3), NOT new Task
- **Status updates** → Task properties (In Progress → Done)

### ❌ Forbidden
- Local-only file paths as deliverables
- Progress updates sent to user (internal only)
- Creating duplicate Tasks for iterations
- Leaving Tasks without completion summary

### 🔄 Workflow
1. **Pre-work:** Check if Task needed (deliverable? 5+ min?)
2. **Create Task:** Use template, link to Project
3. **Start work:** Set Start Date, Status → In Progress
4. **During execution:** Append to Progress Log (silent)
5. **Deliverable ready:** Add as child page or embed in Deliverables section
6. **Complete:** Status → Done, fill Completion Summary

---

## Examples

### Example 1: Simple Task (Small Content)
**Task:** "Write morning briefing script"
- **Deliverable:** Full script embedded in Task body (3KB)
- **Structure:** No child page needed

### Example 2: Complex Task (Large Report)
**Task:** "Research AI trends 2026"
- **Deliverable v1:** Child page "AI Trends Report 2026 (v1)" (50KB)
- **Summary in Task body:** Link + 3-sentence summary
- **v2 (after feedback):** New child page "AI Trends Report 2026 (v2)"

### Example 3: Follow-up Work
**Original Task:** "Clawdbot Complete Guide"
- **v1:** Initial guide (2026-02-01)
- **Follow-up request:** "Audit guide for policy compliance"
  - ❌ WRONG: Create new Task "Audit Clawdbot Guide"
  - ✅ RIGHT: Add child page "Guide Audit v2" under existing Task

---

## Current Implementation

The task manager now uses **YAML/JSON-based task storage** instead of Notion.

### Task Queue Format
```json
{
  "prompt": "Task description or prompt",
  "complexity": "simple|moderate|complex",
  "priority": 1,
  "metadata": {
    "source": "heartbeat",
    "retry_count": 0
  },
  "attempts": 0,
  "maxAttempts": 3
}
```

### Usage from Code
```javascript
const tasks = require('./skills/task-manager');
const pending = tasks.loadPendingTasks();

pending.push({
  prompt: 'Analyze error logs',
  complexity: 'moderate',
  priority: 1
});

tasks.savePendingTasks(pending);
```

**See:** `README.md` for detailed usage examples
