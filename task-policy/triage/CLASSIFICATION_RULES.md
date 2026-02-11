# Auto-Classification Rules for Task Policy
**Last Updated:** 2026-02-09
**Parent:** Task Policy v1 (Local YAML)
**Policy Docs:** AGENTS.md § 2.4, § 7.3, § 2.5

---

## Overview

This page documents the **automatic classification rules** for Epic/Project/Task creation in the local YAML-based Task Policy. These rules are implemented in the `task-triage` skill and enforced in agent workflows.

---

## Classification Criteria

### ✅ Task (일 단위, 개별 행동)

**Duration:** 수 시간 ~ 1일  
**Scope:** 단일 행동, 명확한 산출물  
**Size:** Single deliverable

**Keywords:**
- 리뷰, 작성, 확인, 수정, 테스트
- 분석, 조회, 실행, 검증

**Examples:**
- "API 문서 리뷰"
- "PT 숙제 30분"
- "회의록 작성"
- "Clawdbot 가이드 초안 작성"

**When to Create:**
- ✅ Deliverable expected (page/file/code)
- ✅ Work takes 5+ minutes
- ✅ Single, focused action

**YAML Properties:**
```yaml
title: [task title]
status: todo | in_progress | done
start_date: [ISO 8601 datetime, auto-set]
due_date: [prompt user, never guess]
priority: [high | medium | low]
owner: [assignee name]
```

---

### 📁 Project (주 단위, 구체적 결과물)

**Duration:** 1-2주  
**Scope:** 3-10개 Task 포함  
**Size:** Multiple related deliverables

**Keywords:**
- 구현, 연동, 자동화, 시스템
- 파이프라인, 아키텍처, 가이드, 문서화

**Examples:**
- "토스 API 연동"
- "PT 숙제 자동화"
- "Clawdbot Complete Guide"
- "Notion Task Policy 개선"

**When to Create:**
- ✅ Multi-task initiative with clear goal
- ✅ Work spans multiple days
- ✅ 3+ related tasks expected

**YAML Properties:**
```yaml
title: [project title]
type: Project
status: todo | in_progress | done
due_date: [project deadline]
parent: [Epic ID if applicable]
tasks: [list of task IDs]
```

---

### 🎯 Epic (월 단위, 큰 목표)

**Duration:** 1개월+  
**Scope:** 여러 Project 포함  
**Size:** 10+ tasks, strategic initiative

**Keywords:**
- 플랫폼, 생태계, 전략, 이니셔티브
- 프로그램, 캠페인, 전환

**Examples:**
- "로닉 키오스크 연동" (entire integration)
- "건강 루틴 정착" (lifestyle transformation)
- "밍밍이 프로젝트" (AI evolution)

**When to Create:**
- ✅ User explicitly requests Epic
- ✅ Scope clearly spans multiple projects
- ⚠️ **Default: Do NOT create unless requested**

**YAML Properties:**
```yaml
title: [epic title]
type: Epic
status: in_progress | done
parent: null
sub_projects: [list of project IDs]
tasks: [rollup of all related task IDs]
```

---

## Follow-Up Work Consolidation (CRITICAL)

### Rule: Related follow-up work MUST be added to existing Task, NOT created as separate Task

**When to Consolidate (Add to Existing Task):**
- ✅ Audits, reviews, or validation of previous work
- ✅ Iterations based on feedback (v2, v3, etc.)
- ✅ Follow-up improvements or bug fixes
- ✅ Additional documentation/analysis for same project
- ✅ Any work that references "based on [existing task]"

**When to Create New Task:**
- ❌ Distinct project with different goal/scope
- ❌ Unrelated functionality or feature
- ❌ Different Epic/Project context
- ❌ Work that stands alone

**Follow-Up Keywords:**
- v2, 개선, 수정, 추가, 리팩토링
- based on, 이어서, 버전, 업데이트

---

## Task Property Rules

### Start Date
- **Set to:** Today (when work begins)
- **Auto-set:** By task-triage skill or subagent
- **Format:** YYYY-MM-DD
- **Never:** Leave null if work starts immediately

### Due Date
- **MUST ASK user** at task creation
- **NEVER guess** or auto-set
- **Prompt:** "언제까지 완료해야 하나요?"
- **Accept formats:**
  - YYYY-MM-DD
  - "내일" (tomorrow)
  - "이번 주 금요일"
  - Empty (set later in Notion)

---

## Automation: Task Triage Skill

**Location:** `skills/task-triage/`  
**Implementation:** Rule-based (zero tokens)

### Features
1. **Auto-Classification:** Analyzes keywords and scope
2. **Dry-Run Mode:** Preview before creating (default)
3. **Approval Gate:** User confirms before Notion writes
4. **Auto-Approve:** When user says "진행해" / "do it"
5. **Due Date Prompt:** Interactive prompt, never guesses
6. **Child Page Scaffold:** Creates deliverable template
7. **Duplicate Detection:** Checks for existing similar Tasks

### Usage (CLI)
```bash
# Dry-run (preview only)
python3 skills/task-triage/triage.py "토스 API 문서 리뷰"

# Execute with approval prompt
python3 skills/task-triage/triage.py "토스 API 문서 리뷰" --execute

# Auto-approve
python3 skills/task-triage/triage.py "토스 API 문서 리뷰" --auto-approve
```

### Usage (Python)
```python
from skills.task_triage.triage import handle_user_request

result = handle_user_request(
    user_message="토스 API 문서 리뷰",
    auto_approve=False  # User confirms
)

# Returns:
# {
#   "classification": {
#     "type": "Task",
#     "confidence": 0.9,
#     "is_followup": False,
#     "reasoning": "..."
#   },
#   "notion_entry": {
#     "url": "https://notion.so/...",
#     "id": "page-id",
#     "created": True
#   },
#   "approved": True
# }
```

---

## Decision Tree

```
User Request
    │
    ├─ One-time Q&A? → NO TASK (immediate response)
    │
    ├─ Deliverable expected?
    │   │
    │   ├─ Single action, <1 day
    │   │   └─ CREATE TASK
    │   │       └─ Link to Project if applicable
    │   │
    │   └─ Multiple related tasks, 1-2 weeks
    │       └─ CREATE PROJECT
    │           └─ CREATE FIRST TASK under Project
    │
    └─ User says "Epic" or 1+ month scope?
        └─ CREATE EPIC (only if explicit)
```

---

## Safety Features

### 1. Dry-Run Mode (Default)
- Preview classification without writes
- Shows: Type, Title, Start Date, Due prompt
- User must confirm to proceed

### 2. Approval Gate
- Required unless user says "진행해"
- Prompt: "Proceed with Notion creation? (y/N)"
- Prevents accidental Task spam

### 3. Validation
- Check Notion API access before writes
- Validate DB IDs exist
- Check for duplicate titles (similarity > 80%)
- Rollback on error

### 4. Logging
All operations logged to:
`~/.clawdbot/agents/main/logs/task-triage.log`

---

## Integration with Agent Workflows

### Pre-Work Checklist (AGENTS.md § 2.4)

```python
# In main agent session (before subagent spawn)

# 1. Check if Task creation needed
if user_requests_deliverable_work:
    # 2. Auto-classify
    result = handle_user_request(
        user_message=message,
        auto_approve=("진행해" in message)
    )

    # 3. Spawn subagent with Task path
    spawn_subagent(
        task=f"Task Path: {result['yaml_entry']['path']}\n{message}",
        model="anthropic/claude-sonnet-4-5"
    )

    # 4. Subagent delivers to Task file
```

---

## Examples

### Example 1: Simple Task
**Input:** "토스 API 문서 리뷰해줘"
**Classification:** Task (95% confidence)
**Result:**
- Created in projects/default/tasks.yml
- Title: "토스 API 문서 리뷰"
- Start Date: [will be set when work begins]
- Due: [prompted user]
- Status: todo

### Example 2: Project
**Input:** "토스 API 연동 설계부터 구현까지"
**Classification:** Project (85% confidence)
**Result:**
- Created in projects/toss-api-연동/tasks.yml
- Type: Project
- First Task auto-created: "토스 API 설계 문서 작성"

### Example 3: Follow-Up (Consolidation)
**Input:** "Clawdbot 가이드 v2 개선 작업"
**Classification:** Task, is_followup=True
**Result:**
- Found existing: "Clawdbot Complete Guide"
- Added to same YAML file with parent reference
- Updated parent Task deliverables section

### Example 4: Epic (Explicit)
**Input:** "로닉 키오스크 에픽 만들어줘"
**Classification:** Epic (user explicit)
**Result:**
- Created in projects/로닉-키오스크-에픽/tasks.yml
- Type: Epic
- Parent: null
- Ready for sub-Projects

---

## Monitoring & Maintenance

### Weekly Review (Fridays)
- [ ] Check for duplicate Tasks (consolidate if found)
- [ ] Audit classification accuracy
- [ ] Update criteria based on edge cases

### Monthly Review (1st of month)
- [ ] Review Epic/Project structure
- [ ] Check if Projects should be promoted to Epics (10+ tasks)
- [ ] Update this page with new patterns

---

## Edge Cases

### Q: User says "Project" but scope is 1 day
**A:** Create Task, not Project (classify by actual scope, not wording)

### Q: User says "Task" but scope is multi-week
**A:** Clarify: "This looks like a Project (3-10 tasks). Should I create a Project instead?"

### Q: Unclear if follow-up work
**A:** Ask: "Is this related to [existing task URL]? Should I add it there or create new Task?"

### Q: Epic requested but unclear scope
**A:** Default to Project unless user insists

---

## See Also

- **AGENTS.md § 2.4:** Pre-Work Checklist
- **AGENTS.md § 7.3:** Task-Centric Policy
- **AGENTS.md § 2.5:** Confirmation Gates
- **Policy:** `POLICY.md` (Task Policy Operating Rules)
- **Skill README:** `skills/task-triage/README.md`
- **Skill Docs:** `skills/task-triage/SKILL.md`

---

**Last Reviewed:** 2026-02-09
**Next Review:** 2026-03-09 (monthly)
