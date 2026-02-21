#!/usr/bin/env python3
"""Generate a deduplicated daily news/trends brief from RSS feeds.

- Prefers RSS (stable, low rate-limit) over web search.
- Dedupe by normalized title similarity + same URL.
- Produces compact text suitable for Slack/Telegram.

This script does NOT attempt to be a crawler. Keep feeds curated.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import feedparser

from kst_utils import format_pub_kst, parse_pub_date

# Low-signal patterns filtered from general news
NOISE_PATTERNS = re.compile(
    r"\[부고\]|\[인사\]|부고|부음|별세|발인|빈소|조문|부친상|모친상|"
    r"\[알림\]|\[공고\]|\[광고\]|\[스포츠\]|포토\]|사진\]",
    re.IGNORECASE,
)

# Feed URL → category tag mapping
_FEED_TAGS: list[tuple[str, str]] = [
    ("reuters.com/reuters/business", "경제"),
    ("yna.co.kr/rss/economy", "경제"),
    ("reuters.com", "국제"),
    ("nytimes.com", "국제"),
    ("bbc", "국제"),
    ("yna.co.kr", "국내"),
    ("donga.com", "국내"),
    ("hankyung.com", "국내"),
]


def _strip_html(s: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200] if s else ""


def detect_feed_tag(feed_url: str) -> str:
    """Detect category tag from feed URL."""
    for pattern, tag in _FEED_TAGS:
        if pattern in feed_url:
            return tag
    return ""


@dataclass
class Item:
    title: str
    link: str
    source: str
    published: str | None
    description: str = ""
    tag: str = ""


def norm_title(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    # strip common boilerplate
    s = re.sub(r"\b(update|live|breaking|exclusive|report)\b", "", s)
    s = re.sub(r"[^a-z0-9가-힣 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def load_list(path: str) -> list[str]:
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


def fetch_items(feeds: list[str]) -> list[Item]:
    items: list[Item] = []
    for u in feeds:
        d = feedparser.parse(u)
        src = domain(u) or (d.feed.get("title") if hasattr(d, "feed") else "")
        tag = detect_feed_tag(u)
        for e in d.entries[:30]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link:
                continue
            desc = _strip_html(e.get("summary") or e.get("description") or "")
            items.append(
                Item(
                    title=title,
                    link=link,
                    source=src or domain(link),
                    published=e.get("published") or e.get("updated"),
                    description=desc,
                    tag=tag,
                )
            )
    return items


def filter_by_time(items: list[Item], since_hours: float) -> list[Item]:
    """Keep only items published within the last `since_hours` hours."""
    if since_hours <= 0:
        return items
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for it in items:
        dt = parse_pub_date(it.published)
        if dt is None:
            # No date info — keep it (benefit of doubt)
            out.append(it)
            continue
        age_hours = (now - dt).total_seconds() / 3600
        if age_hours <= since_hours:
            out.append(it)
    return out


def filter_by_keywords(items: list[Item], keywords: list[str]) -> list[Item]:
    if not keywords:
        return items
    kws = [k.lower() for k in keywords]
    out: list[Item] = []
    for it in items:
        t = it.title.lower()
        if any(k in t for k in kws):
            out.append(it)
    return out


def dedupe(items: list[Item], threshold: float = 0.86) -> list[Item]:
    seen_links: set[str] = set()
    kept: list[Item] = []
    kept_norm: list[str] = []

    for it in items:
        if it.link in seen_links:
            continue
        nt = norm_title(it.title)
        if not nt:
            continue
        dup = False
        for knt in kept_norm:
            if similar(nt, knt) >= threshold:
                dup = True
                break
        if dup:
            continue
        kept.append(it)
        kept_norm.append(nt)
        seen_links.add(it.link)

    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", required=True, help="Path to rss_feeds.txt")
    ap.add_argument("--keywords", required=False, help="Path to keywords.txt")
    ap.add_argument("--max-items", type=int, default=5)
    ap.add_argument("--since", type=float, default=0,
                    help="Only include items published within this many hours (0=no filter)")
    ap.add_argument("--dedupe-threshold", type=float, default=0.86)
    ap.add_argument("--output-format", choices=["text", "json"], default="text",
                    help="Output format: text (Telegram) or json (for compose-newspaper.py)")
    args = ap.parse_args()

    feeds = load_list(args.feeds)
    keywords = load_list(args.keywords) if args.keywords else []

    items = fetch_items(feeds)
    # Filter noise (부고, 인사, 광고 등)
    items = [it for it in items if not NOISE_PATTERNS.search(it.title)]
    if args.since > 0:
        items = filter_by_time(items, args.since)
    items = filter_by_keywords(items, keywords)

    # naive sort: keep order as fetched (RSS order tends to be recent-first)
    items = dedupe(items, threshold=args.dedupe_threshold)[: args.max_items]

    # JSON output for compose-newspaper.py
    if args.output_format == "json":
        out = []
        for it in items:
            obj: dict = {
                "title": it.title,
                "link": it.link,
                "source": it.source,
                "published": format_pub_kst(it.published),
                "domain": domain(it.link),
                "tag": it.tag,
            }
            if it.description:
                obj["description"] = it.description
            out.append(obj)
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        print()  # trailing newline
        return

    # Default text output (Telegram)
    today = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append(f"[뉴스/트렌드] 로봇·조리자동화 데일리 브리프 — {today}")

    if not items:
        lines.append("- 오늘은 RSS에서 관련 뉴스를 못 찾았어(피드/키워드 확인 필요).")
        print("\n".join(lines))
        return

    lines.append("- Top headlines")
    for it in items:
        lines.append(f"  - {it.title} ({it.source})")
        lines.append(f"    {it.link}")

    # Keep impact section as placeholders; LLM can rewrite, but this stays deterministic
    lines.append("- Ronik impact (초안)")
    for it in items:
        lines.append(f"  - {it.title.split(' — ')[0][:60]}...")
        lines.append("    • 기회: (작성 필요)")
        lines.append("    • 리스크: (작성 필요)")
        lines.append("    • 액션: (작성 필요)")

    lines.append("- Today's bet: (작성 필요)")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
