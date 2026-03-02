#!/usr/bin/env python3
"""HTML blog scraper for sources without RSS feeds.

Shared by breaking-alert.py and news_brief.py.
stdlib only — no external packages.

Usage:
    from html_source import fetch_entries

    cfg = {"link_pattern": "/news/", "base_url": "https://www.anthropic.com"}
    entries = fetch_entries("https://www.anthropic.com/news", cfg, since_hours=24)
    # Returns: [{title, link, published, summary}, ...]
"""

from __future__ import annotations

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

# Date pattern: "Feb 27, 2026" or "February 27, 2026"
_DATE_RE = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}"
)
# Category labels commonly found in blog listing pages
_CATEGORY_RE = re.compile(
    r"\b(?:Announcements?|Products?|Policy|Research|Company|Engineering|Safety)\b",
    re.IGNORECASE,
)


def _clean_title(raw: str) -> str:
    """Clean extracted title by stripping dates, categories, and descriptions."""
    t = raw.strip()
    # Remove HTML entities
    t = t.replace("&#x27;", "'").replace("&amp;", "&").replace("&quot;", '"')
    # Strip date patterns
    t = _DATE_RE.sub("", t)
    # Collapse whitespace before checking categories
    t = re.sub(r"\s+", " ", t).strip()
    # Strip category label only at the START (not mid-title)
    m = _CATEGORY_RE.match(t)
    if m:
        t = t[m.end():].strip()
    # If too long, likely has description appended — truncate at sentence boundary
    if len(t) > 100:
        # Look for sentence break: period+space, or common continuation signals
        for sep in [". ", " We ", " This ", " The "]:
            idx = t.find(sep, 40)
            if 40 < idx < 120:
                t = t[:idx]
                break
        else:
            t = t[:100].rsplit(" ", 1)[0]
    return t


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

    Handles both raw JSON and escaped JSON (\\\" in Next.js script tags).
    Returns {slug: iso_date_string} mapping.
    """
    dates: dict[str, str] = {}
    # Pattern covers both raw ("key":"val") and escaped (\"key\":\"val\") JSON
    date_re = re.compile(
        r'\\?"(?:publishedOn|publishedAt|published_at|datePublished)\\?"'
        r'\s*:\s*\\?"(\d{4}-\d{2}-\d{2}T[^"\\]+)\\?"'
    )
    slug_re = re.compile(r'\\?"current\\?"\s*:\s*\\?"([^"\\]+)\\?"')

    for m in date_re.finditer(html):
        date_str = m.group(1)
        # Anthropic: publishedOn comes BEFORE slug — look forward
        after = html[m.end() : m.end() + 300]
        slug_match = slug_re.search(after)
        if slug_match:
            dates[slug_match.group(1)] = date_str
            continue
        # Fallback: look backward for slug
        before = html[max(0, m.start() - 500) : m.start()]
        slug_match = slug_re.search(before)
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
        scrape_config: {"link_pattern": str, "base_url": str}
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
        print(
            f"[html_source] no links matched '{link_pattern}' in {url}",
            file=sys.stderr,
        )
        return []

    # Try to extract dates from embedded JSON
    date_map = _extract_dates_from_json(html)

    # Build entries
    now = datetime.now(timezone.utc)
    entries: list[dict] = []

    # Deduplicate: prefer shorter (cleaner) title for duplicate hrefs
    best_titles: dict[str, str] = {}
    for href, raw_title in parser.links:
        title = _clean_title(raw_title)
        if not title:
            continue
        if href not in best_titles or len(title) < len(best_titles[href]):
            best_titles[href] = title

    for href, title in best_titles.items():

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
        if raw_date:
            # Strip milliseconds (.000Z → Z) for parse_pub_date compatibility
            raw_date = re.sub(r"\.\d+Z$", "Z", raw_date)
        dt = parse_pub_date(raw_date) if raw_date else None

        # Time filter
        if dt and since_hours > 0:
            age_hours = (now - dt).total_seconds() / 3600
            if age_hours > since_hours:
                continue

        entries.append(
            {
                "title": title,
                "link": full_url,
                "published": raw_date or "",
                "summary": "",
            }
        )

    return entries
