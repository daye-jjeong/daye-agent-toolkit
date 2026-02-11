---
name: news-brief
description: Unified news briefing skill. Fetches RSS feeds, deduplicates headlines, analyzes Ronik impact (robotics, commercial kitchen, retail automation), prioritizes by relevance, and formats for Telegram. Combines RSS aggregation with LLM-powered impact analysis.
tier: 3 (Full LLM)
status: Experimental
version: 0.2.0
input: RSS feeds list (rss_feeds.txt), keywords list (keywords.txt), impact analysis prompt (impact_prompt.txt)
output: Formatted Telegram message (markdown) with prioritized headlines and Ronik impact analysis
---

# News Brief Skill

**Version:** 0.2.0
**Updated:** 2026-02-09
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

Unified news briefing skill for robotics, commercial kitchen, and retail automation. Combines:
- **RSS aggregation:** Fetches and deduplicates headlines from curated feeds
- **Keyword filtering:** Filters for relevant topics (robot, automation, kitchen, etc.)
- **LLM analysis:** Scores Ronik impact (opportunity, risk, action) for each item
- **Prioritization:** Ranks by relevance and urgency
- **Telegram formatting:** Produces daily brief for Telegram topic 171 (📰 뉴스/트렌드)

**Implementation Status:**
- ✅ Phase 1 (RSS + Dedup): Complete (news_brief.py)
- ✅ Phase 2 (LLM Scaffold): Complete (analyzer.py)
- 🚧 Phase 3 (LLM Integration): Pending full implementation
- ⏸️ Phase 4 (Cron Deployment): Pending validation

## Architecture

Unified pipeline (Tier 1 + Tier 3):

```
news_brief.py (RSS dedup) → analyzer.py (LLM analysis) → Telegram topic 171
(0 tokens, RSS fetch)     (200-400 tokens, analysis)     (📰 뉴스/트렌드)
```

This skill integrates two previous skills:
- `jarvis-news-brief` (RSS aggregation + deduplication)
- `jarvis-news-analyzer` (Ronik impact analysis + formatting)

## Usage

**Basic invocation:**

```bash
/Users/dayejeong/clawd/.venv/bin/python \
  /Users/dayejeong/clawd/skills/news-brief/scripts/news_brief.py \
  --feeds /Users/dayejeong/clawd/skills/news-brief/references/rss_feeds.txt \
  --keywords /Users/dayejeong/clawd/skills/news-brief/references/keywords.txt \
  --max-items 15 \
| /Users/dayejeong/clawd/skills/news-brief/scripts/analyzer.py
```

**With Telegram send (for cron):**

```bash
... | clawdbot message send -t -1003242721592 --thread-id 171
```

**Full cron command:**

```bash
0 9 * * * cd ~/clawd && \
  /Users/dayejeong/clawd/.venv/bin/python \
    /Users/dayejeong/clawd/skills/news-brief/scripts/news_brief.py \
    --feeds /Users/dayejeong/clawd/skills/news-brief/references/rss_feeds.txt \
    --keywords /Users/dayejeong/clawd/skills/news-brief/references/keywords.txt \
    --max-items 15 \
  | /Users/dayejeong/clawd/skills/news-brief/scripts/analyzer.py \
  | /opt/homebrew/bin/clawdbot message send -t -1003242721592 --thread-id 171 \
  >> /tmp/news_brief.log 2>&1
```

## Input Format

**RSS Feeds** (`rss_feeds.txt`):
- One feed URL per line
- Comments start with `#`
- Categories: Robotics, Food/Restaurant/Retail, Tech/Business

**Keywords** (`keywords.txt`):
- One keyword per line
- Examples: `robot`, `kitchen automation`, `humanoid`, `POS`
- Headlines matching any keyword are included

**Impact Prompt** (`impact_prompt.txt`):
- LLM system prompt for analyzing Ronik relevance
- Constrains analysis to: opportunity, risk, action
- Tones: factual, no hype; mark uncertain items "확인 필요"

## Output Format

Telegram-ready markdown:

```
📰 오늘의 뉴스 (2026-02-09)

1. Figure raises $500M for humanoid robots
   🔗 techcrunch.com
   💡 Opportunity: Commercial kitchen humanoids becoming viable
   ⚠️ Risk: Competition in QSR automation space
   🎯 Action: Research Figure's sensor stack vs. ours

2. Miso Robotics expands kitchen automation partnership
   🔗 restaurantbusinessonline.com
   💡 Opportunity: Large QSR deployment potential
   ⚠️ Risk: Focus on burger chains, not ingredient dispensing
   🎯 Action: Monitor partnership expansion timeline

...

🎲 Today's Bet: Reach out to 1X for supply chain partnership
```

## Scripts

### `news_brief.py`

**Purpose:** RSS aggregation, filtering, deduplication

**Inputs:**
- `--feeds` (required): Path to rss_feeds.txt
- `--keywords` (optional): Path to keywords.txt
- `--max-items` (default: 5): Maximum headlines to keep
- `--dedupe-threshold` (default: 0.86): Title similarity threshold (0.0–1.0)

**Output:**
- JSON array to stdout: `[{title, link, source, published, domain}, ...]`

**Features:**
- Fetches up to 30 items per feed
- Normalizes titles (lowercase, remove boilerplate, strip special chars)
- Deduplicates by URL and normalized title similarity
- Filters by keywords (case-insensitive substring match)

### `analyzer.py`

**Purpose:** LLM-powered impact analysis and Telegram formatting

**Input:**
- JSON array from stdin (from news_brief.py)

**Output:**
- Formatted Telegram message to stdout

**Functions:**
- `analyze_ronik_impact(item)` → {opportunity, risk, action}
- `prioritize_items(items)` → sorted list by relevance/urgency
- `format_telegram_message(items)` → Telegram markdown

**Status:**
- Phase 2 (LLM Integration): Pending full Claude API integration
- Currently returns stub values for testing

## Token Usage (Estimated)

- **RSS Fetch:** ~0 tokens (no LLM)
- **Analysis:** ~200–400 tokens (3 sentences × 5 items + daily bet)
- **Total:** ~200–400 tokens/day

## Testing

```bash
# Test RSS fetch + dedup
python /Users/dayejeong/clawd/skills/news-brief/scripts/news_brief.py \
  --feeds /Users/dayejeong/clawd/skills/news-brief/references/rss_feeds.txt \
  --keywords /Users/dayejeong/clawd/skills/news-brief/references/keywords.txt \
  --max-items 5 > /tmp/test_news.json

# Verify JSON structure
cat /tmp/test_news.json | jq '.'

# Test analyzer (stub mode)
cat /tmp/test_news.json | python /Users/dayejeong/clawd/skills/news-brief/scripts/analyzer.py

# Test full pipeline
python /Users/dayejeong/clawd/skills/news-brief/scripts/news_brief.py \
  --feeds /Users/dayejeong/clawd/skills/news-brief/references/rss_feeds.txt \
  --keywords /Users/dayejeong/clawd/skills/news-brief/references/keywords.txt \
  --max-items 5 \
| python /Users/dayejeong/clawd/skills/news-brief/scripts/analyzer.py
```

## References

- **Related Tier 1 script:** `scripts/news/fetch_news.py` (if exists)
- **Telegram topic:** 📰 뉴스/트렌드 (171) in JARVIS HQ group
- **Feeds config:** `/Users/dayejeong/clawd/skills/news-brief/references/rss_feeds.txt`
- **Keywords:** `/Users/dayejeong/clawd/skills/news-brief/references/keywords.txt`
- **Prompt:** `/Users/dayejeong/clawd/skills/news-brief/references/impact_prompt.txt`

## Merged History

This skill unifies two predecessor skills:

1. **jarvis-news-brief** (v0.1.0, 2026-02-03)
   - RSS aggregation + deduplication
   - Keyword filtering
   - Deterministic impact placeholders

2. **jarvis-news-analyzer** (v0.1.0, 2026-02-03)
   - LLM-powered impact analysis scaffold
   - Telegram formatting template
   - Prioritization scaffolds

**Merge rationale:**
- Single pipeline: RSS dedup → LLM analysis → Telegram send
- Unified testing and deployment
- Shared references (feeds, keywords, prompts)
- Single cron job instead of two
- Reduced cognitive overhead

## Deprecation

Old skills are superseded by this unified version:
- `jarvis-news-brief` → deprecated, use `news-brief`
- `jarvis-news-analyzer` → deprecated, use `news-brief`

To restore old behavior:
```bash
# Use old monolithic skill (if needed)
python /Users/dayejeong/clawd/skills/jarvis-news-brief/scripts/news_brief.py \
  --feeds ... --keywords ... --max-items 5
```

## Implementation Roadmap

### ✅ Phase 1: Scaffold (Complete)
- [x] Directory structure created
- [x] RSS aggregation working (news_brief.py)
- [x] Deduplication working
- [x] Keyword filtering working
- [x] SKILL.md documented

### ✅ Phase 2: Merge (Complete)
- [x] Merged jarvis-news-brief + jarvis-news-analyzer
- [x] Unified SKILL.md
- [x] Removed "jarvis-" prefixes
- [x] Created VERSION (0.2.0) and CHANGELOG

### 🚧 Phase 3: LLM Integration (Next)
- [ ] Full Claude API integration in analyzer.py
- [ ] Implement `analyze_ronik_impact()` with LLM
- [ ] Implement `prioritize_items()` with LLM
- [ ] Add caching for LLM calls (optional)
- [ ] Error handling + retry logic

### ⏸️ Phase 4: Validation (Week 2)
- [ ] Deploy cron job
- [ ] Monitor for 1 week
- [ ] Collect feedback
- [ ] Measure token usage
- [ ] Finalize for production

## Related Files

- **Changelog:** `/Users/dayejeong/clawd/skills/news-brief/CHANGELOG.md`
- **Version:** `/Users/dayejeong/clawd/skills/news-brief/VERSION`
- **Ronik docs:** Reference internal project documentation for context
