# Verify Before Done

Never claim "done" until all three pass. Why: without verification, confident-sounding completions hide broken tests, type errors, and cross-file inconsistencies — the model's brevity bias makes it skip checks that feel redundant but catch real bugs.

1. Run related tests + confirm passing
2. `tsc --noEmit` (TypeScript projects)
3. Cross-file consistency check (references, schedules, flag names)

Run verification once more even after you believe you're done.
