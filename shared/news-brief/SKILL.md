---
name: news-brief
description: 뉴스 수집 · 요약 · 알림 — 데일리 신문(RSS 4개 소스 → HTML), AI 속보 알림(keyword scoring), Reddit AI 서브레딧 핫 포스트, CC/OpenClaw 활용 사례 검색. 뉴스 정리, 신문 만들어, breaking alert, 레딧 핫, 속보, RSS 피드, 밍밍 데일리, 뉴스 브리핑, reddit-hot, CC 활용 사례, claude code 사례, openclaw 사례 등의 요청에 사용.
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

- LLM 사용: enrich 단계에서 번역 + 요약 (~200-400 tokens)

### 속보 알림

AI/테크 RSS 소스를 키워드 스코어링으로 감시하여 고신호 기사를 즉시 알린다.

- `breaking-alert.py`: tiered keyword scoring + word boundary 매칭
- LLM 0 tokens

### Reddit 핫 포스트

AI 관련 서브레딧 8개(r/ClaudeAI, r/MachineLearning, r/LocalLLaMA, r/singularity, r/ChatGPT 등)의 핫 포스트를 수집하고 한국어 다이제스트로 요약한다.

- 구독 목록: `references/reddit-hot-subs.txt`

#### 절차

1. `reddit-hot.py --subs references/reddit-hot-subs.txt` 실행
   - upvote 50+ 필터, 서브레딧당 최대 3개, 전체 최대 10개
   - 포스트 본문 + 상위 댓글 3개를 함께 수집
   - 이미 본 URL은 seen_cache로 자동 스킵 (48시간 유지)
2. 출력이 없으면 아무것도 하지 않는다 (빈 확인 메시지 발송 금지)
3. 출력이 있으면 각 포스트를 한국어로 요약하여 recipients에게 전달:
   - 번호. **제목** — r/서브레딧 (⬆upvotes) + 링크
   - 포스트 내용 1-2문장 요약
   - 댓글 핵심 반응 1-2문장

### CC/OpenClaw 활용 사례

Claude Code, OpenClaw, Claude 스킬 등의 실전 활용 사례를 Reddit에서 검색하여 다이제스트로 요약한다.

- 검색 쿼리 목록: `references/cc-showcase-queries.txt`

#### 절차

1. `reddit-cc-showcase.py --queries references/cc-showcase-queries.txt` 실행
   - 기본 시간 범위: week (--time으로 변경 가능: day, month, year, all)
   - upvote 50+ 필터, 전체 최대 10개
   - 포스트 본문 + 상위 댓글 3개를 함께 수집
2. 출력이 없으면 아무것도 하지 않는다
3. 출력이 있으면 각 포스트를 한국어로 요약하여 recipients에게 전달:
   - 번호. **제목** — r/서브레딧 (⬆upvotes) + 링크
   - 포스트 내용 1-2문장 요약 (어떤 활용인지 구체적으로)
   - 댓글 핵심 반응/팁 1-2문장

## Output

| 산출물 | 경로 | 설명 |
|--------|------|------|
| HTML 신문 | `/tmp/mingming_daily.html` | 4개 소스 종합 신문 |
| 속보 텍스트 | stdout | breaking-alert.py 감지 결과 |
| Reddit 핫 | stdout | reddit-hot.py 알림 결과 |
| CC 활용 사례 | stdout | reddit-cc-showcase.py 검색 결과 |

## 시간 표시

모든 출력은 KST (kst_utils.py). 포맷: `2026-02-21 18:30 KST`

## Token Usage

- 데일리 신문 enrich: ~200-400 tokens
- 속보: 0 tokens
- Reddit 핫: 수집 0 tokens, 요약 ~100-200 tokens
- CC 활용 사례: 수집 0 tokens, 요약 ~200-400 tokens
- 날씨 + 옷차림: 0 tokens (Open-Meteo + rule-based)

## Scripts

| Script | Purpose |
|--------|---------|
| `news_brief.py` | RSS fetch + cluster + score + rank |
| `compose-newspaper.py` | 4-input 소스 조합 |
| `enrich.py` | 영어→한국어 번역 + 요약(why) 추가 |
| `breaking-alert.py` | 속보 알림 (tiered keyword + word boundary) |
| `reddit-hot.py` | Reddit 핫 포스트 알림 (AI 서브레딧, upvote 필터) |
| `reddit-cc-showcase.py` | CC/OpenClaw 활용 사례 검색 (Reddit search API) |
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
| `references/reddit-hot-subs.txt` | Reddit 핫 구독 서브레딧 목록 |
| `references/cc-showcase-queries.txt` | CC/OpenClaw 활용 사례 검색 쿼리 |
