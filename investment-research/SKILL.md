---
name: investment-research
description: Personal investing research workflow for Daye (Jarvis). Use when asked to evaluate a stock/ETF, turn a long “investment analysis prompt” into a reusable operating template, run a safe Deep Research process (scope then deep) to gather evidence/links, and store results into Daye’s personal Notion (NEW HOME) in a consistent page/DB format.
---

# Jarvis Investment Research


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

## Workflow (use in order)

### 0) Safety gates (always)
- Do **not** request or accept API keys/tokens in chat.
- Prefer local secrets via **file** or environment variables.
- If output is meant to be sent externally (message/email/post), **ask for confirmation**.

### 1) Clarify the user’s intent (ask ≤3 questions)
Pick only what’s missing:
- Target: ticker/name + market (US/KR) + time horizon
- Decision type: 신규/보유/매도검토
- What matters today: 1–3 questions (e.g., valuation vs catalysts vs risk)

### 2) Choose mode: “Fast screen” vs “Deep research”
- **Fast screen** (default): user provides key numbers or short notes; respond with conditional conclusion + checklist.
- **Deep research**: only when the decision needs external evidence (SEC/IR, guidance, consensus, rates).

### 3) Produce the “Operating Template” (prompt v2)
Convert any long prompt into a stable template that is:
- Source-aware (every number has `as_of` + `source`)
- Anti-hallucination (unknown → N/A; no invented quarterly forecasts)
- Output stable (fixed headings; small tables; bullet-first)

**Deliverables**
1) Input block (what user fills)
2) Output block (exact headings)
3) Rules (sources, N/A policy, scenarios)

### 4) Deep Research protocol (token-saving)
#### Stage A — Scope only (cheap)
Ask for:
- Key questions (≤3)
- Required sources (official first)
Output:
- A research plan: 8–12 checks + best source per check + what evidence to capture

#### Stage B — Evidence collection (deep)
Output constraints:
- Per source: 3–5 lines summary + 1 quote + link
- Deduplicate; mark conflicts
- Keep “interpretation” to a short final section

### 5) Notion write-back (personal workspace only)
Use personal Notion (NEW HOME), and store under **DAYE HQ**.

**Canonical location (do not improvise):**
- DAYE HQ: https://www.notion.so/dayejjeong/DAYE-HQ-2f768ba6942180b9865dc402d89bc6cf
- DB (Runs): https://www.notion.so/83f20fcdfb2e4b3ca52465c458c2ff8f
- DB (Claims): https://www.notion.so/b017443a47b7467c92ae62aeee8d6296

Store results as either:
- Database row (preferred) with properties + structured body, or
- A single page using the template below.

**Page template (body)**
1) Questions (Q1–Q3)
2) TL;DR (5 lines)
3) Evidence log
   - Source | Claim | Quote/Evidence | Link | Confidence
4) Risks / Counterpoints
5) Next checks (events / data)
6) Suggested action (conditional)

## Quick templates

### A) Operating prompt v2 (copy/paste)
**INPUT**
- Ticker/Name:
- Market:
- Horizon:
- Position status (new/hold/sell-check):
- My 1–3 questions:
- Known numbers/notes (≤10 lines):

**OUTPUT (fixed)**
1) One-line conditional stance
2) Bull case (3 bullets)
3) Bear case (3 bullets)
4) Key numbers table (as_of + source per row; unknown=N/A)
5) Evidence checklist (next 5 items)
6) Risk management (entry/exit/invalidations)

**RULES**
- Every number must include `as_of` + `source`.
- If a value is unknown: write `N/A (needs verification)`.
- Quarterly forecasts: only if a credible consensus table exists; otherwise scenario (bear/base/bull).

### B) Deep Research plan prompt (Stage A)
“Do not conclude yet. Create a research plan: 10 checks, each with (what to verify, best primary source, what evidence to capture).”

### C) Deep Research evidence prompt (Stage B)
“Collect evidence with citations. Per source: 3–5 lines summary + 1 quote + link. Deduplicate, flag conflicts, then give a 5-line conclusion and 5 next checks.”
