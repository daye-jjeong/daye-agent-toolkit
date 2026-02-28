# Correction Protocol (Auto-loaded every session)

When a user corrects your behavior, AUTOMATICALLY apply this protocol.
Do NOT wait for `/correction-memory` invocation.

## Trigger Detection

You are corrected when the user:
- Says "always do X", "never do Y", "use X instead of Y"
- Says "remember this", "don't forget"
- Repeats the same instruction for the 2nd+ time
- Corrects a pattern, tool choice, convention, or architecture decision

## What to Do

### 1. Apply the correction immediately in current session

### 2. Save to Layer 1 — Rules (git-tracked, shared)
- Directory: `.claude/rules/` in the current project
- Create ONE file per correction: `correction-{YYYYMMDD}-{HHmm}-{slug}.md`
- Slug: lowercase, hyphens, 2-4 words describing the rule
- Timestamp prevents filename collision between concurrent sessions
- Example filename: `correction-20260227-1430-use-bun.md`
- Example content: `- ALWAYS use bun, NEVER use npm for package management`
- IMPORTANT: Each rule is a SEPARATE file to prevent concurrent session conflicts
- Before creating, check existing `correction-*.md` files for duplicates
- If 50+ correction files exist, suggest running `/correction-memory review`

### 3. Save to Layer 2 — Register (auto memory, local only)
- File: auto memory `corrections/{topic}.md`
- Topics: tooling, architecture, testing, style, integrations, general
- Format: `- [YYYY-MM-DD] {before} -> {after} (reason: {reason})`
- Mark superseded entries with `[superseded]`

### 4. Save to Layer 3 — Log (auto memory, local only)
- File: auto memory `corrections/log/YYYY-MM-DD.md`
- Format: `{HH:MM} | {topic} | {summary} | {trigger type}`

### 5. Report to user
```
Correction saved:
  Rule: "{rule content}"
  Topic: {topic}
  Scope: all sessions in this project
```

## Write Gate — Do NOT save if:
- One-time typo or trivial mistake
- Context-dependent judgment (only valid this session)
- Rule already exists in CLAUDE.md or .claude/rules/
- If unsure, ask: "Save this as a permanent rule?"

## CLAUDE.md Auto-Management
When a correction affects project-wide conventions (not just Claude behavior):
- Check if CLAUDE.md should be updated too
- Suggest the update to the user before writing
- Never modify CLAUDE.md without user confirmation

## Scope Decision
- Project-specific corrections -> `.claude/rules/correction-{slug}.md`
- Global corrections (apply to all projects) -> suggest adding to `~/.claude/CLAUDE.md`

## Concurrent Session Safety
- Each correction = separate file → no write conflicts between sessions
- `/correction-memory review` consolidates and cleans up files
