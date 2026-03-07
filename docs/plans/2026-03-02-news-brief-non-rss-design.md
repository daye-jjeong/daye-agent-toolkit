# news-brief non-RSS 소스 지원

**Date:** 2026-03-02 | **Status:** Approved | **Size:** M

## Problem

2/28 Claude Code batch 발표가 news-brief에서 누락됨.

원인:
1. Anthropic 블로그에 RSS 피드 없음 → feedparser가 HTML 파싱 실패
2. 간접 소스(TechCrunch 등)가 기능 업데이트를 항상 커버하지 않음
3. "Claude Code" 키워드 누락

## Design

### rss_sources.json 스키마 확장

`scrape` 필드 추가. 이 필드가 있는 소스는 feedparser 대신 HTML scraping 사용.

```json
{
  "name": "Anthropic Blog",
  "url": "https://www.anthropic.com/news",
  "category": "Models",
  "priority": "high",
  "note": "No RSS feed, use web_fetch",
  "scrape": {
    "link_pattern": "/news/",
    "base_url": "https://www.anthropic.com"
  }
}
```

### html_source.py (신규 공유 모듈)

```python
def fetch_entries(url: str, scrape_config: dict, since_hours: float = 24) -> list[dict]:
    """HTML 블로그에서 기사 목록 추출. feedparser entry와 동일한 키 반환."""
```

- urllib.request로 HTML fetch (stdlib만 사용)
- `<a href="...">` + link_pattern 매칭
- base_url로 상대→절대 URL 변환
- 제목: `<a>` 텍스트
- 날짜: HTML 내 JSON에서 추출 시도 → 실패 시 None
- since_hours 필터 적용
- urllib timeout 10초 설정 (cron 환경에서 hang 방지)
- 실패 시 빈 리스트 반환

### breaking-alert.py 변경

source에 `scrape` 필드 있으면 feedparser 대신 html_source.fetch_entries() 사용.
기존 scoring/dedup 로직은 그대로.

### news_brief.py 변경

`--web-sources` 플래그 추가. rss_sources.json에서 `scrape` 필드가 있는 소스를 읽어
html_source로 수집 후 기존 items에 합류.

### 키워드 보강

- breaking-keywords.txt: "Claude Code" (tier:normal)
- ai_trends_keywords.txt: "Claude Code"

## 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/html_source.py` | 신규 — HTML scraping 공유 모듈 |
| `scripts/breaking-alert.py` | scrape 소스 지원 |
| `scripts/news_brief.py` | --web-sources 플래그 |
| `references/ai_trends_team/rss_sources.json` | Anthropic에 scrape 추가 |
| `references/breaking-keywords.txt` | "Claude Code" 추가 |
| `references/ai_trends_keywords.txt` | "Claude Code" 추가 |
