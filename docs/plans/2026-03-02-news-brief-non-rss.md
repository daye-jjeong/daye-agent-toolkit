# news-brief non-RSS 소스 지원 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Anthropic 블로그처럼 RSS가 없는 소스를 news-brief 파이프라인(breaking + daily)에서 수집 가능하게 한다.

**Architecture:** `html_source.py` 공유 모듈이 HTML 블로그를 스크래핑하여 feedparser entry와 동일한 형태를 반환. `rss_sources.json`의 `scrape` 필드로 소스별 설정. `breaking-alert.py`와 `news_brief.py` 양쪽에서 사용.

**Tech Stack:** Python 3 stdlib only (urllib.request, re, json, html.parser)

**Design:** `docs/plans/2026-03-02-news-brief-non-rss-design.md`

---

### Task 1: html_source.py — 공유 HTML 스크래핑 모듈

**Files:**
- Create: `shared/news-brief/scripts/html_source.py`

**Step 1: 모듈 작성**

`fetch_entries(url, scrape_config, since_hours)` 함수:
- `urllib.request.urlopen(url, timeout=10)`으로 HTML fetch
- `<a href="...">` 에서 `scrape_config["link_pattern"]` 매칭하는 링크 추출
- `scrape_config["base_url"]` + 상대경로 → 절대 URL 변환
- 제목: `<a>` 태그 텍스트에서 추출
- 날짜: HTML 내 ISO 8601 날짜 패턴(`"publishedOn"` 또는 일반 `\d{4}-\d{2}-\d{2}T`) 추출 시도
- `since_hours` 필터 적용 (날짜 있는 항목만)
- 실패 시 빈 리스트 반환, stderr에 경고 출력
- feedparser entry와 동일한 키: `{title, link, published, summary}`

```python
#!/usr/bin/env python3
"""HTML blog scraper for sources without RSS feeds.

Shared by breaking-alert.py and news_brief.py.
stdlib only — no external packages.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kst_utils import parse_pub_date

_TIMEOUT = 10
_UA = "Mozilla/5.0 (compatible; news-brief/1.0)"


class _LinkExtractor(HTMLParser):
    """Extract <a href="...">title</a> pairs matching a link pattern."""

    def __init__(self, link_pattern: str):
        super().__init__()
        self.link_pattern = link_pattern
        self.links: list[tuple[str, str]] = []  # (href, title_text)
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href and self.link_pattern in href:
                self._current_href = href
                self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            title = " ".join(t for t in self._current_text if t)
            if title:
                self.links.append((self._current_href, title))
            self._current_href = None
            self._current_text = []


def _extract_dates_from_json(html: str) -> dict[str, str]:
    """Try to extract publishedOn dates from embedded JSON (Next.js etc).

    Returns {slug: iso_date_string} mapping.
    """
    dates: dict[str, str] = {}
    # Match ISO 8601 dates near slug-like strings
    for m in re.finditer(
        r'"(?:publishedOn|publishedAt|published_at|datePublished)"'
        r'\s*:\s*"(\d{4}-\d{2}-\d{2}T[^"]+)"',
        html,
    ):
        date_str = m.group(1)
        # Look backward for a slug
        context = html[max(0, m.start() - 500):m.start()]
        slug_match = re.search(r'"(?:slug|current|url)"[^"]*"([^"]+)"', context)
        if slug_match:
            dates[slug_match.group(1)] = date_str
    return dates


def _slug_from_path(path: str) -> str:
    """Extract the last path segment as slug."""
    return path.rstrip("/").rsplit("/", 1)[-1]


def fetch_entries(
    url: str, scrape_config: dict, since_hours: float = 24
) -> list[dict]:
    """Fetch article entries from an HTML blog page.

    Args:
        url: Blog listing page URL
        scrape_config: {link_pattern: str, base_url: str}
        since_hours: Only return items newer than this (0=no filter)

    Returns:
        List of dicts with keys: title, link, published, summary
        (same keys as feedparser entries)
    """
    link_pattern = scrape_config.get("link_pattern", "/")
    base_url = scrape_config.get("base_url", "").rstrip("/")

    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[html_source] fetch failed: {url} — {exc}", file=sys.stderr)
        return []

    # Extract links
    parser = _LinkExtractor(link_pattern)
    parser.feed(html)

    if not parser.links:
        print(f"[html_source] no links matched '{link_pattern}' in {url}", file=sys.stderr)
        return []

    # Try to extract dates from embedded JSON
    date_map = _extract_dates_from_json(html)

    # Build entries
    now = datetime.now(timezone.utc)
    entries: list[dict] = []
    seen_hrefs: set[str] = set()

    for href, title in parser.links:
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Resolve relative URL
        if href.startswith("/"):
            full_url = f"{base_url}{href}"
        elif href.startswith("http"):
            full_url = href
        else:
            full_url = f"{base_url}/{href}"

        # Try to find date
        slug = _slug_from_path(href)
        raw_date = date_map.get(slug)
        dt = parse_pub_date(raw_date) if raw_date else None

        # Time filter
        if dt and since_hours > 0:
            age_hours = (now - dt).total_seconds() / 3600
            if age_hours > since_hours:
                continue

        entries.append({
            "title": title,
            "link": full_url,
            "published": raw_date or "",
            "summary": "",
        })

    return entries
```

**Step 2: 단독 테스트**

```bash
cd shared/news-brief/scripts
python3 -c "
from html_source import fetch_entries
cfg = {'link_pattern': '/news/', 'base_url': 'https://www.anthropic.com'}
entries = fetch_entries('https://www.anthropic.com/news', cfg, since_hours=0)
for e in entries[:5]:
    print(f'{e[\"title\"][:60]}  →  {e[\"link\"][:60]}')
print(f'Total: {len(entries)} entries')
"
```

Expected: Anthropic 블로그 기사 목록 출력 (5개+).

**Step 3: 커밋**

```bash
git add shared/news-brief/scripts/html_source.py
git commit -m "feat(news-brief): add html_source.py for non-RSS blog scraping"
```

---

### Task 2: rss_sources.json — Anthropic 엔트리에 scrape 설정 추가

**Files:**
- Modify: `shared/news-brief/references/ai_trends_team/rss_sources.json` (line 11-16)

**Step 1: Anthropic 엔트리 수정**

기존:
```json
{
  "name": "Anthropic Blog",
  "url": "https://www.anthropic.com/news",
  "category": "Models",
  "priority": "high",
  "note": "No RSS feed, use web_fetch"
}
```

변경:
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

**Step 2: 커밋**

```bash
git add shared/news-brief/references/ai_trends_team/rss_sources.json
git commit -m "feat(news-brief): add scrape config for Anthropic blog in rss_sources.json"
```

---

### Task 3: breaking-alert.py — scrape 소스 지원

**Files:**
- Modify: `shared/news-brief/scripts/breaking-alert.py`

**Step 1: import 추가**

파일 상단 imports 영역 (line 42 `from kst_utils import ...` 이후):

```python
from html_source import fetch_entries as fetch_html_entries
```

**Step 2: fetch_and_score() 수정**

`fetch_and_score()` 함수 (line 165-219)에서, 각 source를 처리하는 for loop 내부를 수정.

기존 (line 183-188):
```python
        try:
            d = feedparser.parse(url)
        except Exception:
            continue

        for e in d.entries[:20]:
```

변경:
```python
        # Use HTML scraper for non-RSS sources
        scrape_cfg = src.get("scrape")
        if scrape_cfg:
            raw_entries = fetch_html_entries(url, scrape_cfg, since_hours)
            entries = []
            for he in raw_entries:
                entries.append(type("E", (), {
                    "get": lambda self, k, d="": getattr(self, k, d),
                    "title": he.get("title", ""),
                    "link": he.get("link", ""),
                    "published": he.get("published"),
                    "updated": None,
                })())
        else:
            try:
                d = feedparser.parse(url)
            except Exception:
                continue
            entries = d.entries[:20]

        for e in entries:
```

NOTE: html_source가 이미 `since_hours` 필터를 적용하지만, breaking-alert의 기존 시간 필터 로직도 그대로 유지 (날짜가 빈 항목에 대해 benefit of doubt).

**Step 3: 테스트 (dry-run)**

```bash
cd shared/news-brief/scripts
python3 breaking-alert.py \
  --sources ../references/ai_trends_team/rss_sources.json \
  --keywords ../references/breaking-keywords.txt \
  --since 168 --threshold 4 --dry-run
```

`--since 168` (7일)과 `--threshold 4`로 낮춰서 Anthropic 블로그 기사가 결과에 포함되는지 확인.
Expected: Anthropic 블로그 기사가 score와 함께 출력됨.

**Step 4: 커밋**

```bash
git add shared/news-brief/scripts/breaking-alert.py
git commit -m "feat(news-brief): breaking-alert supports non-RSS sources via html_source"
```

---

### Task 4: news_brief.py — --web-sources 플래그 추가

**Files:**
- Modify: `shared/news-brief/scripts/news_brief.py`

**Step 1: import 추가**

파일 상단 imports 영역 (line 24 `from kst_utils import ...` 이후):

```python
from html_source import fetch_entries as fetch_html_entries
```

**Step 2: argparse에 --web-sources 추가**

`main()` 함수의 argparse 섹션 (line 453 뒤):

```python
    ap.add_argument("--web-sources",
                    help="rss_sources.json path — non-RSS sources with 'scrape' config")
```

**Step 3: web sources fetch 함수 추가**

`main()` 함수 바로 위에:

```python
def fetch_web_items(sources_path: str, keywords: list[str], since_hours: float) -> list[Item]:
    """Fetch items from non-RSS sources in rss_sources.json."""
    import json as _json
    with open(sources_path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    sources = data.get("sources", data) if isinstance(data, dict) else data

    items: list[Item] = []
    for src in sources:
        scrape_cfg = src.get("scrape")
        if not scrape_cfg:
            continue  # skip RSS sources
        url = src.get("url", "")
        if not url:
            continue

        entries = fetch_html_entries(url, scrape_cfg, since_hours)
        tier = detect_source_tier(url)
        src_domain = domain(url) or src.get("name", url)

        for e in entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            if not title or not link:
                continue
            items.append(Item(
                title=title,
                link=link,
                source=src_domain,
                published=e.get("published"),
                description=e.get("summary", ""),
                tag="",
                source_tier=tier,
            ))

    # Apply keyword filter (same as RSS items)
    if keywords:
        items = filter_by_keywords(items, keywords)
    return items
```

**Step 4: main()에서 web sources 합류**

`main()` 함수에서 `items = fetch_items(feeds)` (line 459) 이후에 추가:

```python
    # Merge non-RSS web sources
    if args.web_sources:
        since = args.since if args.since > 0 else 24
        web_items = fetch_web_items(args.web_sources, keywords, since)
        items.extend(web_items)
```

**Step 5: 테스트**

```bash
cd shared/news-brief/scripts
python3 news_brief.py \
  --feeds ../references/ai_trends_feeds.txt \
  --keywords ../references/ai_trends_keywords.txt \
  --web-sources ../references/ai_trends_team/rss_sources.json \
  --max-items 10 --since 168 --output-format json | python3 -m json.tool | head -40
```

Expected: RSS 기사들과 함께 Anthropic 블로그 기사가 JSON 출력에 포함됨.

**Step 6: 커밋**

```bash
git add shared/news-brief/scripts/news_brief.py
git commit -m "feat(news-brief): add --web-sources flag for non-RSS sources"
```

---

### Task 5: 키워드 파일 보강

**Files:**
- Modify: `shared/news-brief/references/breaking-keywords.txt`
- Modify: `shared/news-brief/references/ai_trends_keywords.txt`

**Step 1: breaking-keywords.txt에 "Claude Code" 추가**

tier:normal 섹션의 AI 모델/브랜드 영역 (line 40 `Claude` 뒤):

```
Claude Code
```

**Step 2: ai_trends_keywords.txt에 "Claude Code" 추가**

Models & Labs 섹션 (line 7 `Claude` 뒤):

```
Claude Code
```

**Step 3: dry-run 테스트**

```bash
cd shared/news-brief/scripts
python3 breaking-alert.py \
  --sources ../references/ai_trends_team/rss_sources.json \
  --keywords ../references/breaking-keywords.txt \
  --since 1 --dry-run
```

**Step 4: 커밋**

```bash
git add shared/news-brief/references/breaking-keywords.txt \
        shared/news-brief/references/ai_trends_keywords.txt
git commit -m "feat(news-brief): add 'Claude Code' to keyword lists"
```

---

### Task 6: SKILL.md 사용법 업데이트

**Files:**
- Modify: `shared/news-brief/SKILL.md`

**Step 1: AI Trends 수집 커맨드에 --web-sources 추가**

SKILL.md Quick Usage 섹션의 Pipeline 2 — AI Trends 커맨드 (line 123-124):

```bash
python3 news_brief.py --feeds ../references/ai_trends_feeds.txt \
  --keywords ../references/ai_trends_keywords.txt \
  --web-sources ../references/ai_trends_team/rss_sources.json \
  --max-items 10 --since 24 --output-format json > /tmp/ai_trends.json
```

**Step 2: usage-examples.md도 동기화**

해당 테스트 커맨드에도 `--web-sources` 추가.

**Step 3: 커밋**

```bash
git add shared/news-brief/SKILL.md shared/news-brief/references/usage-examples.md
git commit -m "docs(news-brief): update usage with --web-sources flag"
```

---

### Task 7: 통합 테스트

**Step 1: Breaking alert 전체 테스트**

```bash
cd shared/news-brief/scripts
python3 breaking-alert.py \
  --sources ../references/ai_trends_team/rss_sources.json \
  --feeds ../references/general_feeds.txt \
  --keywords ../references/breaking-keywords.txt \
  --since 168 --threshold 4 --dry-run 2>&1
```

확인: Anthropic 블로그 기사가 결과에 포함되는지.

**Step 2: AI Trends 파이프라인 테스트**

```bash
python3 news_brief.py --feeds ../references/ai_trends_feeds.txt \
  --keywords ../references/ai_trends_keywords.txt \
  --web-sources ../references/ai_trends_team/rss_sources.json \
  --max-items 5 --since 168 --output-format json | python3 -m json.tool
```

확인: Anthropic 소스 기사가 JSON에 포함되는지.

**Step 3: 기존 파이프라인 regression 확인**

```bash
# --web-sources 없이 기존대로 동작하는지
python3 news_brief.py --feeds ../references/general_feeds.txt \
  --keywords ../references/general_keywords.txt \
  --max-items 3 --since 24 --output-format json | python3 -m json.tool

# Breaking alert 기존 모드
python3 breaking-alert.py \
  --feeds ../references/general_feeds.txt \
  --keywords ../references/breaking-keywords.txt \
  --since 1 --dry-run
```

확인: 에러 없이 기존과 동일하게 동작.
