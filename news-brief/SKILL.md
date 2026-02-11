---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

**Version:** 0.2.0 | **Updated:** 2026-02-09 | **Status:** Experimental

Unified news briefing for robotics, commercial kitchen, and retail automation.
- **RSS aggregation:** Fetch and deduplicate headlines from curated feeds
- **Keyword filtering:** Filter by relevant topics (robot, automation, kitchen, etc.)
- **LLM analysis:** Score Ronik impact (opportunity, risk, action) per item
- **Telegram formatting:** Daily brief to Telegram topic 171

## Architecture

```
news_brief.py (RSS dedup, 0 tokens) -> analyzer.py (LLM, 200-400 tokens) -> Telegram topic 171
```

Merges two predecessor skills: `jarvis-news-brief` + `jarvis-news-analyzer`.

## Trigger

Run manually or via daily cron at 09:00.

## Core Workflow

1. `news_brief.py` fetches RSS feeds, filters by keywords, deduplicates
2. Outputs JSON array: `[{title, link, source, published, domain}, ...]`
3. `analyzer.py` receives JSON, scores Ronik impact per item
4. Formats Telegram-ready markdown with prioritized headlines

## Input Files

| File | Purpose |
|------|---------|
| `{baseDir}/references/rss_feeds.txt` | One feed URL per line, `#` for comments |
| `{baseDir}/references/keywords.txt` | One keyword per line (case-insensitive match) |
| `{baseDir}/references/impact_prompt.txt` | LLM system prompt for Ronik analysis |

## Output Format

Each headline includes: link, Opportunity, Risk, Action. Ends with a daily bet recommendation.

**상세**: `{baseDir}/references/output-example.md` 참고

## Quick Usage

```bash
python news_brief.py --feeds rss_feeds.txt --keywords keywords.txt --max-items 15 \
  | python analyzer.py
```

**상세 (cron, testing 등)**: `{baseDir}/references/usage-examples.md` 참고

## Scripts

| Script | Purpose | Key Args |
|--------|---------|----------|
| `news_brief.py` | RSS fetch + dedup + filter | `--feeds`, `--keywords`, `--max-items`, `--dedupe-threshold` |
| `analyzer.py` | LLM impact analysis + formatting | stdin JSON |

**상세**: `{baseDir}/references/scripts-detail.md` 참고

## Token Usage

- RSS Fetch: ~0 tokens (no LLM)
- Analysis: ~200-400 tokens (3 sentences x 5 items + daily bet)
- Total: ~200-400 tokens/day

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. RSS + Dedup | Complete | news_brief.py |
| 2. LLM Scaffold | Complete | analyzer.py |
| 3. LLM Integration | Pending | Full Claude API |
| 4. Cron Deployment | Pending | Validation needed |

**상세 (로드맵, 병합 이력, 폐기 안내)**: `{baseDir}/references/roadmap-history.md` 참고

## References

- Feeds config: `{baseDir}/references/rss_feeds.txt`
- Keywords: `{baseDir}/references/keywords.txt`
- Prompt: `{baseDir}/references/impact_prompt.txt`
- Telegram topic: 171 in JARVIS HQ group
- Changelog: `{baseDir}/CHANGELOG.md`
