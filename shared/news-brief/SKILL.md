---
name: news-brief
description: 키워드 기반 뉴스 브리핑 + 로닉 임팩트 분석
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# News Brief Skill

뉴스 수집 · 요약 · 알림 스킬.

## 기능

### 데일리 신문

General, AI Trends, Ronik, Community(Reddit) 4개 소스에서 RSS를 수집하고, 클러스터링 · 스코어링 · 한국어 번역 · 요약을 거쳐 HTML 신문을 생성한다.

```
news_brief.py (4개 소스) → compose-newspaper.py → enrich.py → render_newspaper.py → HTML
```

- 매일 09:00 자동 실행 또는 수동
- LLM 사용: enrich 단계에서 번역 + 요약 (~200-400 tokens)

### 속보 알림

AI/테크 RSS 소스를 키워드 스코어링으로 감시하여 고신호 기사를 즉시 알린다.

- `breaking-alert.py`: tiered keyword scoring + word boundary 매칭
- 매시간 자동 실행, LLM 0 tokens

### Reddit 핫 포스트

AI 관련 서브레딧(r/ClaudeAI, r/MachineLearning, r/LocalLLaMA 등 8개)의 핫 포스트를 upvote 기반으로 필터링하여 알린다.

- `reddit-hot.py`: upvote 50+ 필터, 서브레딧당 최대 3개
- 2시간 간격 자동 실행, LLM 0 tokens

## Output

| 산출물 | 경로 | 설명 |
|--------|------|------|
| HTML 신문 | `/tmp/mingming_daily.html` | 4개 소스 종합 신문 |
| 속보 텍스트 | stdout | breaking-alert.py 감지 결과 |
| Reddit 핫 | stdout | reddit-hot.py 알림 결과 |

## 시간 표시

모든 출력은 KST (kst_utils.py). 포맷: `2026-02-21 18:30 KST`

## Token Usage

- 데일리 신문 enrich: ~200-400 tokens
- 속보 + Reddit 핫: 0 tokens
- 날씨 + 옷차림: 0 tokens (Open-Meteo + rule-based)

## Scripts

| Script | Purpose |
|--------|---------|
| `news_brief.py` | RSS fetch + cluster + score + rank |
| `compose-newspaper.py` | 4-input 소스 조합 |
| `enrich.py` | 영어→한국어 번역 + 요약(why) 추가 |
| `breaking-alert.py` | 속보 알림 (tiered keyword + word boundary) |
| `reddit-hot.py` | Reddit 핫 포스트 알림 (AI 서브레딧, upvote 필터) |
| `fetch_weather.py` | 날씨 + 옷차림 (Open-Meteo) |
| `render_newspaper.py` | JSON → 신문 스타일 HTML |
| `seen_cache.py` | 알림 dedup 캐시 (library) |
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
| `references/*_feeds.txt` | 소스별 RSS 피드 목록 |
| `references/*_keywords.txt` | 소스별 키워드 필터 |
