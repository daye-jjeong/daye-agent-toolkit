---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

**Version:** 0.5.0 | **Updated:** 2026-02-26 | **Status:** Experimental

Four-pipeline news briefing system:
1. **General:** Korean/international general news + daily summary
2. **AI Trends:** AI/tech RSS + community (HN, Reddit, PH, GitHub) + multi-agent analysis
3. **Ronik:** Robotics/kitchen automation RSS + Ronik impact analysis
4. **Breaking:** 15분 간격 속보 알림 (keyword scoring, LLM 0 tokens)

## Architecture

```
Pipeline 1 (General):  news_brief.py --output-format json  ─┐
Pipeline 2 (AI):       AI Trends Team (3-agent)              ├→ compose-newspaper.py → enrich.py → render_newspaper.py → HTML
Pipeline 3 (Ronik):    news_brief.py --output-format json  ─┤                                     save_to_vault.py    → Vault
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
6. `save_to_vault.py` saves to vault as structured markdown

## Input Files

### Pipeline 1 — General

| File | Purpose |
|------|---------|
| `{baseDir}/references/general_feeds.txt` | General RSS feeds (연합뉴스, BBC Korean, Reuters, NYT 등) |
| `{baseDir}/references/general_keywords.txt` | Broad keywords (경제, 정치, 국제, 과학 등) |
| `{baseDir}/references/general_prompt.txt` | LLM prompt: 카테고리별 요약 + 오늘의 핵심 |

### Community — Reddit

| File | Purpose |
|------|---------|
| `{baseDir}/references/community_feeds.txt` | Reddit RSS feeds (r/artificial, r/MachineLearning) |
| `{baseDir}/references/community_keywords.txt` | AI/ML 키워드 필터 |

### Pipeline 2 — AI Trends

**자동 수집 (cron/단일 에이전트):**

| File | Purpose |
|------|---------|
| `{baseDir}/references/ai_trends_feeds.txt` | AI RSS feeds — plain text URL 목록 (news_brief.py용) |
| `{baseDir}/references/ai_trends_keywords.txt` | AI 키워드 필터 (GPT, Claude, LLM, transformer 등) |

**멀티 에이전트 (수동/고품질):**

| File | Purpose |
|------|---------|
| `{baseDir}/references/ai_trends_team/rss_sources.json` | AI RSS + community sources (13개) — 에이전트가 직접 web_fetch |
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

| 산출물 | 경로 | 설명 |
|--------|------|------|
| HTML 신문 | `/tmp/mingming_daily.html` | 4개 파이프라인 종합 신문 |
| Vault 마크다운 | `{vault-dir}/reports/news-brief/YYYY-MM-DD.md` | 구조화된 일일 브리핑 |
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

Pipeline 2를 멀티 에이전트 팀으로 고품질 실행하려면 `references/ai_trends_team/` 참고.

### 2. 조합 + 보강 + 렌더링

```bash
# Compose (4개 파이프라인 합치기, --highlight 필수)
python3 compose-newspaper.py --general /tmp/general.json \
  --ai-trends /tmp/ai_trends.json --ronik /tmp/ronik.json \
  --community /tmp/community.json \
  --highlight "오늘의 핵심 한줄 요약" --output /tmp/composed.json

# Enrich (영어 헤드라인 한국어 번역 + 요약 why 추가)
python3 enrich.py extract --input /tmp/composed.json > /tmp/to_enrich.json
# → 에이전트가 to_enrich.json을 읽고 enrichments.json 생성 (한국어 번역 + why)
python3 enrich.py apply --input /tmp/composed.json \
  --enrichments /tmp/enrichments.json --output /tmp/composed.json

# Render HTML
python3 render_newspaper.py --input /tmp/composed.json \
  --weather /tmp/weather.json --output /tmp/mingming_daily.html
```

### 3. 저장

```bash
# Vault 저장
python3 save_to_vault.py --input /tmp/composed.json \
  --weather /tmp/weather.json --vault-dir ~/openclaw/vault
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
| `news_brief.py` | RSS fetch + cluster + score + rank | `--feeds`, `--keywords`, `--output-format json`, `--no-rank` |
| `kst_utils.py` | KST 시간 변환 유틸 | (library, import only) |
| `compose-newspaper.py` | 4-input 파이프라인 조합 | `--general`, `--ai-trends`, `--ronik`, `--community`, `--output` |
| `enrich.py` | 영어→한국어 번역 + 요약(why) 추가 | `extract --input`, `apply --input --enrichments` |
| `breaking-alert.py` | 속보 알림 (tiered keyword + word boundary) | `--sources`, `--keywords`, `--since`, `--dry-run` |
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
| 2. Compose + KST | Complete | compose-newspaper.py, kst_utils.py |
| 3. AI Trends Team | Complete | 3-agent (researcher/writer/executor) |
| 4. Enrich + Render | Complete | enrich.py, render_newspaper.py |
| 5. Breaking Alert | Complete | breaking-alert.py |
| 6. Community (Reddit) | Complete | news_brief.py + community feeds |
| 7. Cron Deployment | Pending | Validation needed |

**상세 (로드맵, 병합 이력)**: `{baseDir}/references/roadmap-history.md` 참고
