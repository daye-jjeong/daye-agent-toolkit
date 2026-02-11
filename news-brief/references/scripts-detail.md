# News Brief Scripts Detail

## `news_brief.py`

**Purpose:** RSS aggregation, filtering, deduplication

**Inputs:**
- `--feeds` (required): Path to rss_feeds.txt
- `--keywords` (optional): Path to keywords.txt
- `--max-items` (default: 5): Maximum headlines to keep
- `--dedupe-threshold` (default: 0.86): Title similarity threshold (0.0-1.0)

**Output:**
- JSON array to stdout: `[{title, link, source, published, domain}, ...]`

**Features:**
- Fetches up to 30 items per feed
- Normalizes titles (lowercase, remove boilerplate, strip special chars)
- Deduplicates by URL and normalized title similarity
- Filters by keywords (case-insensitive substring match)

## `analyzer.py`

**Purpose:** LLM-powered impact analysis and Telegram formatting

**Input:**
- JSON array from stdin (from news_brief.py)

**Output:**
- Formatted Telegram message to stdout

**Functions:**
- `analyze_ronik_impact(item)` -> {opportunity, risk, action}
- `prioritize_items(items)` -> sorted list by relevance/urgency
- `format_telegram_message(items)` -> Telegram markdown

**Status:**
- Phase 2 (LLM Integration): Pending full Claude API integration
- Currently returns stub values for testing
