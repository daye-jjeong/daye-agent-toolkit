---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

**Version:** 0.4.0 | **Updated:** 2026-02-21 | **Status:** Experimental

Four-pipeline news briefing system:
1. **General:** Korean/international general news + daily summary
2. **AI Trends:** AI/tech RSS + community (HN, Reddit, PH, GitHub) + multi-agent analysis
3. **Ronik:** Robotics/kitchen automation RSS + Ronik impact analysis
4. **Breaking:** 15분 간격 속보 알림 (keyword scoring, LLM 0 tokens)

## Architecture

```
Pipeline 1 (General):  news_brief.py --output-format json  ─┐
Pipeline 2 (AI):       AI Trends Team (3-agent)              ├→ compose-newspaper.py → render_newspaper.py → HTML
Pipeline 3 (Ronik):    news_brief.py --output-format json  ─┘                        save_to_vault.py    → Vault
Pipeline 4 (Breaking): breaking-alert.py (*/15 cron)                                                     → Telegram
```

**시간 표시**: 모든 파이프라인 KST (kst_utils.py). 포맷: `2026-02-21 18:30 KST`

## Trigger

- Pipeline 1-3: Daily cron 09:00 or manual
- Pipeline 4: `*/15 * * * *` (15분 간격)

## Core Workflow

1. `news_brief.py` fetches RSS feeds, filters by keywords, deduplicates
2. `--output-format json` outputs: `[{title, link, source, published (KST), domain}, ...]`
3. `compose-newspaper.py` merges General + AI Trends + Ronik → newspaper schema
4. `render_newspaper.py` renders combined JSON → HTML newspaper
5. `save_to_vault.py` saves to vault as structured markdown

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
| `{baseDir}/references/ai_trends_team/executor.md` | Executor agent prompt (compose flow) |

### Pipeline 3 — Ronik

| File | Purpose |
|------|---------|
| `{baseDir}/references/rss_feeds.txt` | Ronik RSS feeds (robotics, QSR, Reuters tech) |
| `{baseDir}/references/keywords.txt` | Ronik keywords (robot, kitchen automation, etc.) |
| `{baseDir}/references/impact_prompt.txt` | LLM prompt: Ronik impact (기회/리스크/액션) |

### Pipeline 4 — Breaking

| File | Purpose |
|------|---------|
| `{baseDir}/references/breaking-keywords.txt` | 고신호 키워드 (launch, breaking 등) |
| `{baseDir}/references/ai_trends_team/rss_sources.json` | RSS sources (Pipeline 2와 공유) |

## Output

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
# Pipeline 1 — General (JSON output for compose)
python3 news_brief.py --feeds general_feeds.txt --keywords general_keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/general.json

# Pipeline 3 — Ronik (JSON output for compose)
python3 news_brief.py --feeds rss_feeds.txt --keywords keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/ronik.json

# Compose + Render
python3 compose-newspaper.py --general /tmp/general.json --ai-trends /tmp/ai_trends.json \
  --ronik /tmp/ronik.json --output /tmp/composed.json
python3 render_newspaper.py --input /tmp/composed.json --weather /tmp/weather.json \
  --output /tmp/mingming_daily.html

# Pipeline 4 — Breaking Alert (dry run)
python3 breaking-alert.py --sources references/ai_trends_team/rss_sources.json \
  --keywords references/breaking-keywords.txt --since 1 --dry-run
```

Pipeline 2 (AI Trends)는 multi-agent team으로 실행 — `references/ai_trends_team/` 참고.

**상세 (cron, testing 등)**: `{baseDir}/references/usage-examples.md` 참고

## Scripts

| Script | Purpose | Key Args |
|--------|---------|----------|
| `news_brief.py` | RSS fetch + dedup + filter | `--feeds`, `--keywords`, `--output-format json` |
| `kst_utils.py` | KST 시간 변환 유틸 | (library, import only) |
| `compose-newspaper.py` | 3-pipeline JSON 조합 | `--general`, `--ai-trends`, `--ronik`, `--output` |
| `breaking-alert.py` | 속보 알림 (keyword scoring) | `--sources`, `--keywords`, `--since`, `--dry-run` |
| `analyzer.py` | LLM impact analysis + formatting | stdin JSON |
| `fetch_weather.py` | 날씨 + 옷차림 (Open-Meteo, 0 tokens) | `--location`, `--output` |
| `render_newspaper.py` | JSON → 신문 스타일 HTML | `--input`, `--weather`, `--output` |
| `save_to_vault.py` | 기사 vault 저장 | `--input`, `--vault-dir` |
| `ai_trends_ingest.py` | AI 트렌드 vault 적재 | stdin JSON, `--vault-dir` |

## References (AI Trends Team)

| 파일 | 용도 |
|------|------|
| `references/ai_trends_team/executor.md` | AI Trends 실행자 프롬프트 |
| `references/ai_trends_team/researcher.md` | AI Trends 리서처 프롬프트 |
| `references/ai_trends_team/writer.md` | AI Trends 작성자 프롬프트 |
| `references/ai_trends_team/rss_sources.json` | AI Trends RSS 소스 목록 (13개: 공식 블로그 + HN/Reddit/PH/GitHub) |

**상세**: `{baseDir}/references/scripts-detail.md` 참고

## Token Usage

- RSS Fetch + Breaking Alert: ~0 tokens (no LLM)
- Weather + Outfit: ~0 tokens (Open-Meteo + rule-based)
- Analysis: ~200-400 tokens (3 sentences x 5 items + daily bet)
- Total: ~200-400 tokens/day

## Vault Storage

| 저장 위치 | 내용 |
|-----------|------|
| `{vault-dir}/reports/news-brief/YYYY-MM-DD.md` | 일일 뉴스 브리핑 (전체) |
| `{vault-dir}/reports/ai-trends/YYYY-MM-DD.md` | AI 트렌드 상세 |

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. RSS + Dedup | Complete | news_brief.py |
| 2. LLM Scaffold | Complete | analyzer.py |
| 3. Compose + KST | Complete | compose-newspaper.py, kst_utils.py |
| 4. Breaking Alert | Complete | breaking-alert.py |
| 5. LLM Integration | Pending | Full Claude API |
| 6. Cron Deployment | Pending | Validation needed |

**상세 (로드맵, 병합 이력)**: `{baseDir}/references/roadmap-history.md` 참고
