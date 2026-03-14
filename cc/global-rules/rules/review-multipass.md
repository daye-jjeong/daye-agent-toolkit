# Review Multipass

Always do at least 2 passes on code review. Why: single-pass reviews catch per-file issues but miss cross-file inconsistencies (mismatched references, schedule times, flag names) — these are the bugs that ship silently.

1. **Pass 1**: Per-file issues (logic errors, omissions, style)
2. **Pass 2**: Cross-file consistency — references, schedule times, flag names, distributed docs

NEVER merge a PR without explicit user approval.
