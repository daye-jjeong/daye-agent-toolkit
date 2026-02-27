# Superpowers Workflow Gates (Auto-loaded every session)

These gates are NON-NEGOTIABLE. Skipping any gate is a workflow violation.

---

## Gate 0: Brainstorming Before Implementation Skills

**This gate overrides `using-superpowers` skill matching order.**

When `using-superpowers` says "invoke relevant skills BEFORE any response", the Skill Priority section applies:

> 1. **Process skills first** (brainstorming, debugging)
> 2. **Implementation skills second** (frontend-design, mcp-builder, **writing-skills**, etc.)

**The concrete rule:** If the user's request involves BUILDING, CREATING, or MODIFYING something (feature, skill, component, workflow), the FIRST skill invoked MUST be `superpowers:brainstorming`. NOT the implementation skill that "matches" the request.

**Implementation skills that REQUIRE brainstorming first:**
- `superpowers:writing-skills` — "스킬 만들자" → brainstorming FIRST
- `superpowers:writing-plans` — brainstorming must complete before planning
- `frontend-design` — brainstorming FIRST
- `interface-design` — brainstorming FIRST
- Any skill that produces code or artifacts

**The check:** Before invoking ANY implementation skill, ask yourself:
> "Has brainstorming been completed for this task in this session?"
> If NO → invoke `superpowers:brainstorming` first.
> If YES → proceed with the implementation skill.

**What is exempt (skip brainstorming):**
- Single-file typo/bug fixes
- Config changes
- User gave very specific, detailed instructions for a small change
- Debugging (use `systematic-debugging` instead)

**Rationalization prevention:**

| Excuse | Reality |
|--------|---------|
| "I know exactly how to do this" | Brainstorm anyway. You'll catch edge cases. |
| "The matching skill already guides the process" | Skills guide HOW, brainstorming decides WHAT. |
| "It's just a few changes" | "A few changes" across files = brainstorm first |
| "Planning is overhead for this" | Rework from no brainstorming is more overhead |
| "The skill name matches the request directly" | Direct match ≠ skip process. Process skills first, always. |

---

## Gate 0.5: Worktree Isolation for Concurrent Sessions

When working on implementation tasks, ALWAYS use a git worktree for isolation.

**The rule:**
- Start sessions with `claude --worktree <name>` when doing implementation work
- If already in a session without worktree, ask: "Should I create a worktree for this work?"
- Each session = separate worktree = separate branch = no conflicts
- Add `.claude/worktrees/` to `.gitignore` if not already present

**When worktree is REQUIRED:**
- Any implementation task (code changes + commits)
- When user is known to run multiple sessions on the same project

**When worktree is optional:**
- Read-only exploration / research
- Single quick fix the user wants on current branch

**After worktree work completes:**
- Use `finishing-a-development-branch` to merge/PR
- Clean up worktree

---

## Gate 1: Prefer Subagent-Driven Development

When executing an implementation plan, ALWAYS use `superpowers:subagent-driven-development` instead of `superpowers:executing-plans`.

**Why:** subagent-driven-development includes 2-stage review per task (spec compliance + code quality). executing-plans only does batch reporting without automated review dispatch.

**The rule:**
- `subagent-driven-development` = DEFAULT execution mode
- `executing-plans` = ONLY if user explicitly requests batch mode
- Never downgrade from subagent-driven to executing-plans without user consent

---

## Gate 2: Plan Review Before Execution

After `writing-plans` generates a plan, you MUST review it before executing. Never auto-execute.

**The 3-Example Rule:** For every file path, naming convention, or structural claim in the plan, find 3+ existing examples in the codebase that confirm it. If you can't find 3 examples, the plan item is suspect.

**Checklist — output these BEFORE starting execution:**

```
Plan Review Checklist:
- [ ] All file paths verified against actual codebase (3-Example Rule)
- [ ] Naming conventions match existing patterns
- [ ] Task dependencies are correct (no circular, no missing)
- [ ] Edge cases from brainstorming are covered in tasks
- [ ] No tasks reference non-existent functions/modules
- [ ] Test strategy covers actual requirements, not just code presence
```

**If any item fails:** Fix the plan first. Do not proceed with a flawed plan.

**Rationalization prevention:**

| Excuse | Reality |
|--------|---------|
| "The plan looks correct" | Did you run the 3-Example Rule? |
| "File paths are obvious" | Obvious paths are wrong 40% of the time |
| "I'll fix issues during execution" | Fixing during execution compounds errors |
| "This is a simple feature" | Simple features have wrong assumptions too |

---

## Gate 3: Fresh-Eyes Final Review

After ALL tasks are complete (before `finishing-a-development-branch`), dispatch a **full-implementation review** that examines the ENTIRE diff at once.

**Why:** Per-task reviews only see one task's changes. Cross-cutting issues (dead code, value mismatches, duplication, inconsistencies) only appear when viewing the whole implementation together.

**The process:**

1. Get the full diff: `git diff <base-branch>...HEAD`
2. Dispatch `superpowers:code-reviewer` subagent with:
   - `{WHAT_WAS_IMPLEMENTED}`: Full feature description
   - `{BASE_SHA}`: Commit before first task
   - `{HEAD_SHA}`: Current HEAD after all tasks
   - `{DESCRIPTION}`: "Fresh-eyes full-implementation review — check for cross-task issues"
3. Additionally check these cross-task concerns:
   - Dead code or unreachable branches
   - Value/constant inconsistencies between files
   - Duplicated logic across task boundaries
   - Missing integration between components built in separate tasks
   - Documentation gaps
4. Fix all Critical and Important issues before proceeding

**This review is MANDATORY. It is NOT the same as per-task reviews.**

**Rationalization prevention:**

| Excuse | Reality |
|--------|---------|
| "All per-task reviews passed" | Per-task reviews miss cross-task issues — this is proven |
| "It's a small feature" | Small features still have integration gaps |
| "Tests all pass" | Tests passing ≠ no dead code, no duplication |
| "I'm running low on context" | Context is not an excuse to skip quality |

---

## Gate 4: Structural Enforcement

Gates 0-3 are instructions. This gate makes them harder to skip.

### 4a. Explicit Gate Declarations

Before transitioning between workflow phases, you MUST output a gate declaration:

```
═══ GATE CHECK: [gate name] ═══
Status: PASS / FAIL / SKIPPED (with justification)
Evidence: [what you checked]
═══════════════════════════════
```

The phases and their required gates:

| Transition | Required Gate |
|------------|---------------|
| Task received → Implementation start | Gate 0 (Brainstorming First) |
| Implementation start → Code changes | Gate 0.5 (Worktree Isolation) |
| Plan written → Execution start | Gate 2 (Plan Review) |
| Task N complete → Task N+1 | Per-task review (subagent-driven handles this) |
| All tasks complete → Finishing branch | Gate 3 (Fresh-Eyes Final Review) |

### 4b. Anti-Skip Rules

- If you catch yourself about to skip a gate → STOP and execute the gate
- If context window is running low → `/compact` first, then execute the gate
- If a gate fails → fix the issue, re-run the gate, do not proceed
- "Quick skip" is not a thing. Every gate runs, every time.

### 4c. Post-Compact Recovery

After any context compaction (`/compact` or auto-compact), re-read this file and verify:
- Which workflow phase you are in
- Which gates have been passed
- What remains to be done

---

## Quick Reference

```
[Task received]
    ↓
══ GATE 0: Brainstorming first? (building/creating/modifying) ══
    ↓
══ GATE 0.5: Worktree Isolation ══
    ↓
brainstorming
    ↓
writing-plans
    ↓
══ GATE 2: Plan Review (3-Example Rule) ══
    ↓
subagent-driven-development (Gate 1)
  ├─ Task 1 → spec review → code review → ✓
  ├─ Task 2 → spec review → code review → ✓
  └─ Task N → spec review → code review → ✓
    ↓
══ GATE 3: Fresh-Eyes Final Review (full diff) ══
    ↓
finishing-a-development-branch (merge worktree)
```
