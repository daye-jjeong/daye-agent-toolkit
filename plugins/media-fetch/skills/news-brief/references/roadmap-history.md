# News Brief Roadmap & History

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
- Single pipeline: RSS dedup -> LLM analysis -> Telegram send
- Unified testing and deployment
- Shared references (feeds, keywords, prompts)
- Single cron job instead of two
- Reduced cognitive overhead

## Deprecation

Old skills are superseded by this unified version:
- `jarvis-news-brief` -> deprecated, use `news-brief`
- `jarvis-news-analyzer` -> deprecated, use `news-brief`

To restore old behavior:
```bash
# Use old monolithic skill (if needed)
python /Users/dayejeong/openclaw/skills/jarvis-news-brief/scripts/news_brief.py \
  --feeds ... --keywords ... --max-items 5
```

## Implementation Roadmap

### Phase 1: Scaffold (Complete)
- [x] Directory structure created
- [x] RSS aggregation working (news_brief.py)
- [x] Deduplication working
- [x] Keyword filtering working
- [x] SKILL.md documented

### Phase 2: Merge (Complete)
- [x] Merged jarvis-news-brief + jarvis-news-analyzer
- [x] Unified SKILL.md
- [x] Removed "jarvis-" prefixes
- [x] Created VERSION (0.2.0) and CHANGELOG

### Phase 3: LLM Integration (Next)
- [ ] Full Claude API integration in analyzer.py
- [ ] Implement `analyze_ronik_impact()` with LLM
- [ ] Implement `prioritize_items()` with LLM
- [ ] Add caching for LLM calls (optional)
- [ ] Error handling + retry logic

### Phase 4: Validation (Week 2)
- [ ] Deploy cron job
- [ ] Monitor for 1 week
- [ ] Collect feedback
- [ ] Measure token usage
- [ ] Finalize for production
