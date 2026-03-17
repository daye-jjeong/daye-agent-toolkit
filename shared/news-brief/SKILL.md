---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

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

## Core Workflow

1. `news_brief.py` fetches RSS feeds, filters by keywords, clusters by story, scores, ranks
2. `compose-newspaper.py` merges General + AI + Ronik + Community → newspaper schema
3. `enrich.py extract` → 에이전트가 한국어 번역 + 요약(why) 생성 → `enrich.py apply`
4. `render_newspaper.py` renders enriched JSON → HTML newspaper

## Output

| 산출물 | 경로 | 설명 |
|--------|------|------|
| HTML 신문 | `/tmp/mingming_daily.html` | 4개 파이프라인 종합 신문 |
| 속보 텍스트 | stdout | breaking-alert.py 감지 결과 |

## Trigger

- Pipeline 1-3: Daily cron 09:00 or manual
- Pipeline 4: `*/15 * * * *` (15분 간격)

## Token Usage

- RSS Fetch + Breaking Alert: ~0 tokens (no LLM)
- Weather + Outfit: ~0 tokens (Open-Meteo + rule-based)
- Analysis: ~200-400 tokens (3 sentences x 5 items)
- Total: ~200-400 tokens/day

## Scripts

| Script | Purpose |
|--------|---------|
| `news_brief.py` | RSS fetch + cluster + score + rank |
| `compose-newspaper.py` | 4-input 파이프라인 조합 |
| `enrich.py` | 영어→한국어 번역 + 요약(why) 추가 |
| `breaking-alert.py` | 속보 알림 (tiered keyword + word boundary) |
| `fetch_weather.py` | 날씨 + 옷차림 (Open-Meteo) |
| `render_newspaper.py` | JSON → 신문 스타일 HTML |
| `kst_utils.py` | KST 시간 변환 유틸 (library) |
| `html_source.py` | Non-RSS 블로그 HTML 스크래핑 (library) |

**상세 (플래그, 예시)**: `references/scripts-detail.md` 참고

## References

| File | 내용 |
|------|------|
| `references/usage-examples.md` | CLI 실행 예시 (데이터 수집 → 조합 → 렌더링) |
| `references/scripts-detail.md` | 스크립트별 상세 플래그 |
| `references/newspaper-schema.md` | 신문 JSON 스키마 |
| `references/output-example.md` | 산출물 예시 |
| `references/*_feeds.txt` | 파이프라인별 RSS 피드 목록 |
| `references/*_keywords.txt` | 파이프라인별 키워드 필터 |
