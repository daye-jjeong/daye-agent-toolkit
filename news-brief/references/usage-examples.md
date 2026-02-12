# News Brief Usage Examples

## Basic invocation

```bash
/Users/dayejeong/openclaw/.venv/bin/python \
  /Users/dayejeong/openclaw/skills/news-brief/scripts/news_brief.py \
  --feeds /Users/dayejeong/openclaw/skills/news-brief/references/rss_feeds.txt \
  --keywords /Users/dayejeong/openclaw/skills/news-brief/references/keywords.txt \
  --max-items 15 \
| /Users/dayejeong/openclaw/skills/news-brief/scripts/analyzer.py
```

## With Telegram send (for cron)

```bash
... | clawdbot message send -t -1003242721592 --thread-id 171
```

## Full cron command

```bash
0 9 * * * cd ~/openclaw && \
  /Users/dayejeong/openclaw/.venv/bin/python \
    /Users/dayejeong/openclaw/skills/news-brief/scripts/news_brief.py \
    --feeds /Users/dayejeong/openclaw/skills/news-brief/references/rss_feeds.txt \
    --keywords /Users/dayejeong/openclaw/skills/news-brief/references/keywords.txt \
    --max-items 15 \
  | /Users/dayejeong/openclaw/skills/news-brief/scripts/analyzer.py \
  | /opt/homebrew/bin/clawdbot message send -t -1003242721592 --thread-id 171 \
  >> /tmp/news_brief.log 2>&1
```

## Testing

```bash
# Test RSS fetch + dedup
python /Users/dayejeong/openclaw/skills/news-brief/scripts/news_brief.py \
  --feeds /Users/dayejeong/openclaw/skills/news-brief/references/rss_feeds.txt \
  --keywords /Users/dayejeong/openclaw/skills/news-brief/references/keywords.txt \
  --max-items 5 > /tmp/test_news.json

# Verify JSON structure
cat /tmp/test_news.json | jq '.'

# Test analyzer (stub mode)
cat /tmp/test_news.json | python /Users/dayejeong/openclaw/skills/news-brief/scripts/analyzer.py

# Test full pipeline
python /Users/dayejeong/openclaw/skills/news-brief/scripts/news_brief.py \
  --feeds /Users/dayejeong/openclaw/skills/news-brief/references/rss_feeds.txt \
  --keywords /Users/dayejeong/openclaw/skills/news-brief/references/keywords.txt \
  --max-items 5 \
| python /Users/dayejeong/openclaw/skills/news-brief/scripts/analyzer.py
```
