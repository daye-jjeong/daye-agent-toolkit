# Task Policy Operating Rules
**Last Updated:** 2026-02-04

## Language Policy (CRITICAL)
**Default Language:** Korean (한국어)

**Rule:** ALL deliverables (reports, guides, documentation, analysis, etc.) MUST be in Korean unless user explicitly requests English.

**Rationale:**
- User is Korean (Daye Jeong)
- Primary workspace is Korean-language environment
- Default to user's native language for best UX

**Exceptions (English allowed):**
- User explicitly says "in English" or "write in English"
- Technical documentation where English is standard (API docs, code comments if team is international)
- Content for English-speaking audience (if user specifies)

**Implementation:**
- Subagents default to Korean output
- Prompts/templates use Korean
- Task body template is in Korean (already implemented)

**Enforcement:** Add to pre-work checklist in AGENTS.md § 2.4

## Task Property Rules

### Start Date
- **Definition:** The date/time when work actually begins on the task (first action taken)
- **Setting:** Set automatically when first action begins
- **Default:** `null` until work starts
- **Format:** ISO 8601 with timezone (e.g., `2026-02-03T12:37:00+09:00`)
- **Example:** When subagent starts work, set Start Date to current datetime

### Due Date
- **Definition:** The deadline or target completion date for the task
- **Setting:** **MUST ASK user** at task creation - NEVER guess or auto-set
- **Default:** `null` (explicitly ask before setting)
- **When to ask:** At task creation or when user requests work
- **Exception:** Only set automatically if user explicitly provides date in request
- **Rationale:** Guessing deadlines creates false expectations and planning issues

## Task Creation Workflow

### 0. User Confirmation (Opt-In) - MANDATORY
**Rule:** Tasks are created ONLY after user confirmation.

**When to Create WITHOUT asking:**
- ✅ User explicitly says: "태스크로 넣어줘", "등록해줘", "create task for...", "add to tasks"
- ✅ User uses imperative form with clear deliverable: "X 만들어줘", "Y 분석해줘"

**When to ASK before creating:**
- 🤔 Agent identifies work that *could* be tracked as Task
- 🤔 User mentions idea/concept without explicit task request
- 🤔 Ambiguous request (could be Q&A or could be Task)

**Confirmation format:**
```
"[Work title] 작업을 projects/tasks.yml에 추가할까요?"
(Wait for: "응", "넣어줘", "추가", 👍)
```

**Someday/Maybe candidates:**
- Ideas, references, "나중에 해볼 것" → Suggest as Someday entry
- Still requires confirmation before creation

**Rationale:** Prevents unwanted Task accumulation and respects user control over their Task Policy.

### Policy Change Opt-In (NEW - 2026-02-04)
**Rule:** When new operational rules or guardrails emerge during conversation, agent MUST ask user confirmation before documenting them.

**Trigger conditions:**
- ✅ New guardrail pattern discovered during work
- ✅ User says "make this a rule" or "let's formalize this"
- ✅ Repeated pattern that could become policy
- ✅ Decision that affects future operations

**Do NOT trigger for:**
- ❌ One-time exceptions or workarounds
- ❌ Clarifications of existing policy
- ❌ Temporary solutions

**Confirmation format:**
```
"새로운 정책이 생겼습니다: [1-line rule summary]

정책 문서에 반영할까요?

A) 대화로만 유지 (문서화 안 함)
B) 문서에 반영 (POLICY.md / AGENTS.md)
C) 가드레일 자동화 (cron/watchdog 추가)

선택: [A/B/C]"
```

**Implementation:**
- Option A: Note in session memory only (ephemeral)
- Option B: Add to appropriate policy file (surgical edit, preserve tone)
- Option C: Create automation (cron job, pre-commit hook, watchdog alert)

**Rationale:** Prevents policy drift, ensures user controls system evolution, maintains explicit governance over operational rules.

**Example:**
```
User encounters issue: "Subagent created 5 duplicate tasks"
Agent identifies pattern: "Need deduplication check before task creation"

Agent asks:
"새로운 정책이 생겼습니다: Task 생성 전 중복 체크 필수

정책 문서에 반영할까요?

A) 대화로만 유지
B) 문서에 반영 (Pre-Work Checklist에 추가)
C) 가드레일 자동화 (Task creation hook)

선택: [A/B/C]"
```

### 1. User Request Analysis
```
User says: "Create a guide for X"
Agent checks:
- Is deliverable expected? → YES → Check opt-in (§0)
- Is it one-time Q&A? → NO
- Will it take 5+ min? → YES → Check opt-in (§0)
```

### 2. Task Property Collection
```
REQUIRED at creation:
- Name: Extract from request
- Status: "Not Started" (default) or "In Progress" if starting immediately
- Priority: Ask if not clear from context

CONDITIONAL:
- Due: ASK USER (never guess!)
  "When do you need this completed?"
  
- Start Date: Set automatically when work begins
  (DO NOT set at creation unless work starts immediately)

- Project: Link if part of existing Project/Epic
```

### 3. Task Body Template
```markdown
## 작업 내용
[Description of what needs to be done]

## 🔍 Progress Log (Internal)
*Chronological checkpoints during execution. NOT user-facing.*

**Format:** Each entry includes timestamp (YYYY-MM-DD HH:MM), AI model used (full model string), and agent type.

### [YYYY-MM-DD HH:MM] 작업 시작
**Model:** openai-codex/gpt-5.2 | **Agent:** [main / subagent]
- [Initial actions taken]

### [YYYY-MM-DD HH:MM] 중간 체크포인트 (optional)
**Model:** anthropic/claude-sonnet-4-5 | **Agent:** [main / subagent]
- [Progress updates, issues encountered]

### [YYYY-MM-DD HH:MM] 완료/산출물 생성
**Model:** anthropic/claude-opus-4-5 | **Agent:** [main / subagent]
- [Final deliverable details]

## 의사결정 포인트
[Key decisions made, rationale]

## 산출물
[Deliverables - links to local files, etc.]

## 참고
[References, related tasks, context]
```

## Auto-Classification Rules

### When to Create Task
- ✅ Deliverable expected (page/file/code/analysis)
- ✅ Multi-step work requiring tracking
- ✅ Work takes 5+ minutes
- ✅ User explicitly requests "create task for..."

### When NOT to Create Task
- ❌ Simple Q&A ("What's the weather?")
- ❌ Status checks ("How many sessions?")
- ❌ Immediate responses (<1 min work)

### Project vs Task vs Subtask
See `policy_project_task_classification.md` for full criteria.

## Integration with Workflows

### Subagent Spawn (Agent OS Orchestration)
Execution is delegated to **Agent OS Orchestrator** (`skills/orchestrator`) which enforces the **Agent OS Protocol**.

**Key Protocols (Refer to AGENTS.md for full policy):**
1.  **Confirmation Gates:** Mandatory Gate 1 (Plan) and Gate 2 (Budget) per `AGENTS.md § 2.5`.
2.  **Task Linkage:** No subagent spawn without a Task URL per `AGENTS.md § 7.3`.
3.  **Depth Limit:** Max depth 2.

**Implementation:**
- `skills/orchestrator` implements these gates via `skills.orchestrator.lib.gates.ask_approval`.

### Task Completion
1. Set Status to "Done"
2. Set "Completed on" date
3. Ensure all deliverables are accessible (no local-only paths)
4. Archive after 7 days (automatic)

## Automation: Task Triage Skill

**Skill:** `skills/task-triage/` (NEW - 2026-02-03)

Auto-handles Task creation with proper property management:
- **Start Date:** Auto-set to today when creating Task
- **Due Date:** Prompts user interactively (never guesses)
- **Project Linking:** Auto-detects if Task belongs to existing Project
- **YAML Storage:** Writes to `projects/{folder}/tasks.yml`

**Usage in agent workflows:**
```python
# Replace manual Task creation with:
from skills.task_triage.triage import handle_user_request
result = handle_user_request(user_message, auto_approve=False)
task_path = result["yaml_entry"]["path"]
```

**See:** `skills/task-triage/README.md` for full documentation

## Historical Context
- **2026-02-03:** Added explicit rules for Start Date (auto-set on work start) and Due (must ask, never guess)
- **2026-02-03:** Task Triage skill implemented to automate Task creation with proper property handling
- **Rationale:** Previous behavior auto-set dates incorrectly, causing planning issues and false deadline expectations
