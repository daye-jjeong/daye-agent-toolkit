---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석. 뉴스 요약, 데일리 브리핑, 밍밍 데일리, 속보 알림, RSS, AI 트렌드 분석이 필요할 때 사용.
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

**Version:** 0.5.0 | **Updated:** 2026-02-26 | **Status:** Experimental

Four-pipeline news briefing system:
1. **General:** Korean/international general news + daily summary
2. **AI Trends:** AI/tech RSS + community (HN, Reddit, PH, GitHub)
3. **Ronik:** Robotics/kitchen automation RSS + Ronik impact analysis
4. **Breaking:** 15분 간격 속보 알림 (keyword scoring, LLM 0 tokens)

## Architecture

```
Pipeline 1 (General):  news_brief.py --output-format json  ─┐
Pipeline 2 (AI):       news_brief.py --output-format json  ─┤→ compose-newspaper.py → enrich.py → render_newspaper.py → HTML
Pipeline 3 (Ronik):    news_brief.py --output-format json  ─┤
Community  (Reddit):   news_brief.py --output-format json  ─┘
Pipeline 4 (Breaking): breaking-alert.py (*/15 cron)
```

**시간 표시**: 모든 파이프라인 KST (kst_utils.py). 포맷: `2026-02-21 18:30 KST`

## Trigger

- Pipeline 1-3: Daily cron 09:00 or manual
- Pipeline 4: `*/15 * * * *` (15분 간격)

## Core Workflow

1. `news_brief.py` fetches RSS feeds, filters by keywords, clusters by story (title similarity + entity overlap), scores by coverage/source tier/recency/entity density, ranks by score
2. `--output-format json` outputs: `[{title, link, source, published (KST), domain, score, coverage}, ...]`
3. `compose-newspaper.py` merges General + AI Trends + Ronik → newspaper schema
4. `enrich.py extract` → agent가 한국어 번역 + 요약(why) 생성 → `enrich.py apply`
5. `render_newspaper.py` renders enriched JSON → HTML newspaper

## Input Files

### Pipeline 1 — General

| File | Purpose |
|------|---------|
| `{baseDir}/references/general_feeds.txt` | General RSS feeds (연합뉴스, BBC Korean, Reuters, NYT 등) |
| `{baseDir}/references/general_keywords.txt` | Broad keywords (경제, 정치, 국제, 과학 등) |

### Community — Reddit

| File | Purpose |
|------|---------|
| `{baseDir}/references/community_feeds.txt` | Reddit RSS feeds (r/artificial, r/MachineLearning) |
| `{baseDir}/references/community_keywords.txt` | AI/ML 키워드 필터 |

### Pipeline 2 — AI Trends

| File | Purpose |
|------|---------|
| `{baseDir}/references/ai_trends_feeds.txt` | AI RSS feeds — plain text URL 목록 (news_brief.py용) |
| `{baseDir}/references/ai_trends_keywords.txt` | AI 키워드 필터 (GPT, Claude, LLM, transformer 등) |

### Pipeline 3 — Ronik

| File | Purpose |
|------|---------|
| `{baseDir}/references/rss_feeds.txt` | Ronik RSS feeds (robotics, QSR, Reuters tech) |
| `{baseDir}/references/keywords.txt` | Ronik keywords (robot, kitchen automation, etc.) |

### Pipeline 4 — Breaking

| File | Purpose |
|------|---------|
| `{baseDir}/references/breaking-keywords.txt` | 고신호 키워드 (launch, breaking 등) |
| `{baseDir}/references/ai_trends_team/rss_sources.json` | RSS sources (Pipeline 2와 공유) |

## Output

| 산출물 | 경로 | 설명 |
|--------|------|------|
| HTML 신문 | `/tmp/mingming_daily.html` | 4개 파이프라인 종합 신문 |
| 속보 텍스트 | stdout | breaking-alert.py 감지 결과 |

`render_newspaper.py`가 JSON → 신문 스타일 HTML 파일 생성.

**Input JSON schema**: `{baseDir}/references/newspaper-schema.md` 참고
**상세**: `{baseDir}/references/output-example.md` 참고

## Quick Usage

모든 스크립트는 `{baseDir}/scripts/` 디렉토리에서 실행.

### 1. 데이터 수집 (4개 파이프라인)

```bash
# 날씨
python3 fetch_weather.py --location Seoul --output /tmp/weather.json

# Pipeline 1 — General
python3 news_brief.py --feeds ../references/general_feeds.txt \
  --keywords ../references/general_keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/general.json

# Pipeline 2 — AI Trends (자동 수집)
python3 news_brief.py --feeds ../references/ai_trends_feeds.txt \
  --keywords ../references/ai_trends_keywords.txt \
  --web-sources ../references/ai_trends_team/rss_sources.json \
  --max-items 10 --since 24 --output-format json > /tmp/ai_trends.json

# Pipeline 3 — Ronik
python3 news_brief.py --feeds ../references/rss_feeds.txt \
  --keywords ../references/keywords.txt \
  --max-items 10 --since 24 --output-format json > /tmp/ronik.json

# Community — Reddit
python3 news_brief.py --feeds ../references/community_feeds.txt \
  --keywords ../references/community_keywords.txt \
  --max-items 10 --since 24 --output-format json > /tmp/community.json
```

### 2. 조합 + 보강 + 렌더링

```bash
# Compose (4개 파이프라인 합치기, --highlight 필수)
python3 compose-newspaper.py --general /tmp/general.json \
  --ai-trends /tmp/ai_trends.json --ronik /tmp/ronik.json \
  --community /tmp/community.json \
  --highlight "오늘의 핵심 한줄 요약" --output /tmp/composed.json

# Enrich (영어 헤드라인 한국어 번역 + 요약 why 추가)
python3 enrich.py extract --input /tmp/composed.json > /tmp/to_enrich.json
# → 에이전트가 to_enrich.json의 모든 항목에 대해 enrichments.json 생성
#    품질 기준:
#    - highlight: 전체 기사를 종합한 '오늘의 핵심' 2-3문장 (카테고리 나열 금지, 구체적 흐름 서술)
#    - headline: 영어 → 자연스러운 한국어 번역
#    - summary: 영어 요약은 한국어로 번역. RSS 원문 붙여넣기 금지, 기사 핵심을 한국어 1-2문장으로 요약
#    - why: 왜 중요한가 1문장 (비즈니스/기술/사회 관점)
#    - 최종 HTML에 영어 텍스트(headline, summary, why)가 하나도 남으면 안 됨
#    - 모든 항목 빠짐없이 처리할 것. 일부만 하고 넘어가면 영어가 섞인 신문이 됨
python3 enrich.py apply --input /tmp/composed.json \
  --enrichments /tmp/enrichments.json --output /tmp/composed.json

# Render HTML
python3 render_newspaper.py --input /tmp/composed.json \
  --weather /tmp/weather.json --output /tmp/mingming_daily.html
```

### Pipeline 4 — Breaking Alert (별도 cron)

```bash
# 속보 감지 (stdout으로 출력)
python3 breaking-alert.py --sources ../references/ai_trends_team/rss_sources.json \
  --feeds ../references/general_feeds.txt \
  --keywords ../references/breaking-keywords.txt --since 1
```


**상세 (cron, testing 등)**: `{baseDir}/references/usage-examples.md` 참고

## Scripts

| Script | Purpose | Key Args |
|--------|---------|----------|
| `news_brief.py` | RSS fetch + cluster + score + rank | `--feeds`, `--keywords`, `--web-sources`, `--output-format json`, `--no-rank` |
| `html_source.py` | Non-RSS 블로그 HTML 스크래핑 | (library, import only) |
| `kst_utils.py` | KST 시간 변환 유틸 | (library, import only) |
| `compose-newspaper.py` | 4-input 파이프라인 조합 | `--general`, `--ai-trends`, `--ronik`, `--community`, `--output` |
| `enrich.py` | 영어→한국어 번역 + 요약(why) 추가 | `extract --input`, `apply --input --enrichments` |
| `breaking-alert.py` | 속보 알림 (tiered keyword + word boundary) | `--sources`, `--keywords`, `--since`, `--dry-run` |
| `fetch_weather.py` | 날씨 + 옷차림 (Open-Meteo, 0 tokens) | `--location`, `--output` |
| `render_newspaper.py` | JSON → 신문 스타일 HTML | `--input`, `--weather`, `--output` |
**상세**: `{baseDir}/references/scripts-detail.md` 참고

## Token Usage

- RSS Fetch + Breaking Alert: ~0 tokens (no LLM)
- Weather + Outfit: ~0 tokens (Open-Meteo + rule-based)
- Analysis: ~200-400 tokens (3 sentences x 5 items + daily bet)
- Total: ~200-400 tokens/day

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. RSS + Dedup | Complete | news_brief.py |
| 2. Compose + KST | Complete | compose-newspaper.py, kst_utils.py |
| 3. AI Trends | Complete | news_brief.py + ai_trends_feeds.txt |
| 4. Enrich + Render | Complete | enrich.py, render_newspaper.py |
| 5. Breaking Alert | Complete | breaking-alert.py |
| 6. Community (Reddit) | Complete | news_brief.py + community feeds |
| 7. Cron Deployment | Pending | Validation needed |

**상세 (로드맵, 병합 이력)**: `{baseDir}/references/roadmap-history.md` 참고
