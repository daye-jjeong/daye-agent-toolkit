# News Brief Usage Examples

## 전체 파이프라인 (수동 실행)

```bash
BASE=/Users/dayejeong/git_workplace/daye-agent-toolkit/news-brief
cd $BASE/scripts

# 1. General
python3 news_brief.py --feeds ../references/general_feeds.txt \
  --keywords ../references/general_keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/general.json

# 2. Ronik
python3 news_brief.py --feeds ../references/rss_feeds.txt \
  --keywords ../references/keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/ronik.json

# 3. Community (Reddit)
python3 news_brief.py --feeds ../references/community_feeds.txt \
  --keywords ../references/community_keywords.txt \
  --max-items 10 --since 24 --output-format json > /tmp/community.json

# 4. Weather
python3 fetch_weather.py --output /tmp/weather.json

# 5. AI Trends — multi-agent team 실행 → /tmp/ai_trends_data.json

# 6. Compose
python3 compose-newspaper.py \
  --general /tmp/general.json \
  --ai-trends /tmp/ai_trends_data.json \
  --ronik /tmp/ronik.json \
  --community /tmp/community.json \
  --output /tmp/composed.json

# 7. Enrich (extract → agent 번역 → apply)
python3 enrich.py extract --input /tmp/composed.json > /tmp/to_enrich.json
# Agent generates /tmp/enrichments.json
python3 enrich.py apply --input /tmp/composed.json \
  --enrichments /tmp/enrichments.json --output /tmp/composed.json

# 8. Render
python3 render_newspaper.py --input /tmp/composed.json \
  --weather /tmp/weather.json \
  --output /tmp/mingming_daily_$(date +%Y-%m-%d).html
```

## 테스트

```bash
# RSS 수집 테스트 (General)
python3 news_brief.py --feeds ../references/general_feeds.txt \
  --keywords ../references/general_keywords.txt \
  --max-items 3 --since 24 --output-format json | python3 -m json.tool

# Community (Reddit) 수집 테스트
python3 news_brief.py --feeds ../references/community_feeds.txt \
  --keywords ../references/community_keywords.txt \
  --max-items 3 --since 24 --output-format json | python3 -m json.tool

# Compose 테스트 (AI Trends만)
python3 compose-newspaper.py --ai-trends /tmp/ai_trends_data.json --output /tmp/test.json

# Breaking Alert (dry run)
python3 breaking-alert.py \
  --sources ../references/ai_trends_team/rss_sources.json \
  --keywords ../references/breaking-keywords.txt \
  --since 1 --dry-run
```

## Cron 설정 (OpenClaw)

```bash
# 매일 09:00 — 전체 파이프라인
0 9 * * * cd ~/openclaw && python3 skills/news-brief/scripts/news_brief.py ...

# 매 15분 — 속보 알림
*/15 * * * * cd ~/openclaw && python3 skills/news-brief/scripts/breaking-alert.py ...
```

상세 cron 설정은 executor.md 참고.
