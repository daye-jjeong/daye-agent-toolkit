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

# 5. AI Trends (자동 수집 + non-RSS 소스 포함)
python3 news_brief.py --feeds ../references/ai_trends_feeds.txt \
  --keywords ../references/ai_trends_keywords.txt \
  --web-sources ../references/ai_trends_team/rss_sources.json \
  --max-items 10 --since 24 --output-format json > /tmp/ai_trends_data.json
# 또는 multi-agent team 실행 → /tmp/ai_trends_data.json

# 6. Compose
python3 compose-newspaper.py \
  --general /tmp/general.json \
  --ai-trends /tmp/ai_trends_data.json \
  --ronik /tmp/ronik.json \
  --community /tmp/community.json \
  --output /tmp/composed.json

# 7. Enrich (extract → agent 번역 → apply)
python3 enrich.py extract --input /tmp/composed.json > /tmp/to_enrich.json
# → 에이전트가 to_enrich.json의 모든 항목에 대해 enrichments.json 생성
#    품질 기준:
#    - highlight: 전체 기사를 종합한 '오늘의 핵심' 2-3문장 (카테고리 나열 금지, 구체적 흐름 서술)
#    - headline: 영어 → 자연스러운 한국어 번역
#    - summary: RSS 원문 붙여넣기 금지, 기사 핵심을 한국어 1-2문장으로 요약
#    - why: 왜 중요한가 1문장 (비즈니스/기술/사회 관점)
#    - 최종 HTML에 영어 텍스트가 하나도 남으면 안 됨
#    - 모든 항목 빠짐없이 처리할 것
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
