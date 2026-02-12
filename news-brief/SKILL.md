---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

**Version:** 0.3.0 | **Updated:** 2026-02-12 | **Status:** Experimental

Three-pipeline news briefing system (표시 순서):
1. **General:** Korean/international general news + daily summary
2. **AI Trends:** AI/tech RSS + community (HN, Reddit, PH, GitHub) + multi-agent analysis
3. **Ronik:** Robotics/kitchen automation RSS + Ronik impact analysis

## Architecture

```
Pipeline 1 (General):  news_brief.py --feeds general_feeds.txt  -> analyzer.py (general prompt)  -> Telegram 171
Pipeline 2 (AI):       AI Trends Team (Researcher → Writer → Executor)                           -> Telegram 171 + Vault
Pipeline 3 (Ronik):    news_brief.py --feeds rss_feeds.txt      -> analyzer.py (Ronik prompt)    -> Telegram 171
```

**섹션 순서**: General News → AI & Tech Trends → Ronik Industry (JSON sections 배열 순서로 제어)

## Trigger

Run manually or via daily cron at 09:00.

## Core Workflow

1. `news_brief.py` fetches RSS feeds, filters by keywords, deduplicates
2. Outputs JSON array: `[{title, link, source, published, domain}, ...]`
3. `analyzer.py` receives JSON, scores Ronik impact per item
4. Formats Telegram-ready markdown with prioritized headlines

## Input Files

### Pipeline 1 — General

| File | Purpose |
|------|---------|
| `{baseDir}/references/general_feeds.txt` | General RSS feeds (연합뉴스, BBC Korean, Reuters, NYT 등) |
| `{baseDir}/references/general_keywords.txt` | Broad keywords (경제, 정치, 국제, 과학 등) |
| `{baseDir}/references/general_prompt.txt` | LLM prompt: 카테고리별 요약 + 오늘의 핵심 |

### Pipeline 2 — AI Trends

| File | Purpose |
|------|---------|
| `{baseDir}/references/ai_trends_team/rss_sources.json` | AI RSS + community sources (13개) |
| `{baseDir}/references/ai_trends_team/researcher.md` | Researcher agent prompt |
| `{baseDir}/references/ai_trends_team/writer.md` | Writer agent prompt |
| `{baseDir}/references/ai_trends_team/executor.md` | Executor agent prompt |

### Pipeline 3 — Ronik

| File | Purpose |
|------|---------|
| `{baseDir}/references/rss_feeds.txt` | Ronik RSS feeds (robotics, QSR, Reuters tech) |
| `{baseDir}/references/keywords.txt` | Ronik keywords (robot, kitchen automation, etc.) |
| `{baseDir}/references/impact_prompt.txt` | LLM prompt: Ronik impact (기회/리스크/액션) |

## Output Format

### Telegram (text)

Each headline includes: link, Opportunity, Risk, Action. Ends with a daily bet recommendation.

### HTML 신문 (file attachment)

`render_newspaper.py`가 JSON → 신문 스타일 HTML 파일 생성. 텔레그램에 파일 첨부로 전송.

```bash
# 날씨 수집 (Tier 1, 0 tokens)
python3 fetch_weather.py --output /tmp/weather.json

# HTML 렌더링 (날씨 포함)
python3 render_newspaper.py --input data.json --weather /tmp/weather.json --output /tmp/mingming_daily.html
```

**Input JSON schema**: `{baseDir}/references/newspaper-schema.md` 참고
**상세**: `{baseDir}/references/output-example.md` 참고

## Quick Usage

```bash
# Pipeline 1 — General (24시간 이내 기사만)
python3 news_brief.py --feeds general_feeds.txt --keywords general_keywords.txt --max-items 15 --since 24 \
  | python3 analyzer.py --prompt general_prompt.txt

# Pipeline 3 — Ronik (24시간 이내 기사만)
python3 news_brief.py --feeds rss_feeds.txt --keywords keywords.txt --max-items 15 --since 24 \
  | python3 analyzer.py --prompt impact_prompt.txt
```

Pipeline 2 (AI Trends)는 multi-agent team으로 실행 — `references/ai_trends_team/` 참고.

**상세 (cron, testing 등)**: `{baseDir}/references/usage-examples.md` 참고

## Scripts

| Script | Purpose | Key Args |
|--------|---------|----------|
| `news_brief.py` | RSS fetch + dedup + filter | `--feeds`, `--keywords`, `--max-items`, `--dedupe-threshold` |
| `analyzer.py` | LLM impact analysis + formatting | stdin JSON |
| `fetch_weather.py` | 날씨 + 옷차림 추천 (Open-Meteo, Tier 1) | `--location`, `--output` |
| `render_newspaper.py` | JSON → 신문 스타일 HTML 렌더링 | `--input`, `--weather`, `--output` |
| `save_to_vault.py` | 중요 기사 vault 저장 (`vault/reports/news-brief/`) | `--input`, `--vault-dir` |
| `ai_trends_ingest.py` | AI 트렌드 vault 적재 (`vault/reports/ai-trends/`) | stdin JSON |

## References (AI Trends Team)

| 파일 | 용도 |
|------|------|
| `references/ai_trends_team/executor.md` | AI Trends 실행자 프롬프트 |
| `references/ai_trends_team/researcher.md` | AI Trends 리서처 프롬프트 |
| `references/ai_trends_team/writer.md` | AI Trends 작성자 프롬프트 |
| `references/ai_trends_team/rss_sources.json` | AI Trends RSS 소스 목록 (13개: 공식 블로그 + HN/Reddit/PH/GitHub) |

**상세**: `{baseDir}/references/scripts-detail.md` 참고

## Token Usage

- RSS Fetch: ~0 tokens (no LLM)
- Weather + Outfit: ~0 tokens (Open-Meteo API + rule-based)
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

## Vault Storage

중요 기사는 vault에 마크다운으로 저장:

```bash
# 전체 브리핑 저장
echo '...' | python3 save_to_vault.py --vault-dir ~/openclaw/vault

# 특정 파이프라인만
python3 save_to_vault.py --input ai_trends.json --vault-dir ~/openclaw/vault
```

| 저장 위치 | 내용 |
|-----------|------|
| `vault/reports/news-brief/YYYY-MM-DD.md` | 일일 뉴스 브리핑 (전체) |
| `vault/reports/ai-trends/` | AI 트렌드 상세 (ai_trends_ingest.py) |

각 파일에 YAML frontmatter 포함: `type`, `date`, `articles`, `sections`, `tags`.

## References

- Feeds config: `{baseDir}/references/rss_feeds.txt`
- Keywords: `{baseDir}/references/keywords.txt`
- Prompt: `{baseDir}/references/impact_prompt.txt`
- Telegram topic: 171 in JARVIS HQ group
- Changelog: `{baseDir}/CHANGELOG.md`
