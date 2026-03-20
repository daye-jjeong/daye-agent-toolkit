#!/usr/bin/env python3
"""Breaking news alert — tiered keyword scoring + word boundary + dedup.

Checks RSS sources, scores items by tiered keyword matches + source priority,
and outputs Telegram alerts for high-scoring items (score >= 7).

Keywords are tiered:
  - tier:high (+4) — standalone high-signal events (AGI, acquisition, etc.)
  - tier:normal (+2) — need combination to trigger (launch, Claude, etc.)

Word boundary matching prevents false positives (e.g. "ban" won't match "banned").

Designed for 15-minute cron: */15 * * * *

Usage:
  python3 breaking-alert.py \
    --sources references/ai_trends_team/rss_sources.json \
    --keywords references/breaking-keywords.txt \
    --since 1 --dry-run

  python3 breaking-alert.py \
    --feeds references/general_feeds.txt \
    --keywords references/breaking-keywords.txt \
    --since 1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import feedparser

from html_source import fetch_entries as fetch_html_entries
from kst_utils import format_kst, parse_pub_date
from seen_cache import CACHE_DIR, load_seen, save_seen, prune_seen

SEEN_FILE = CACHE_DIR / "seen.json"
ALERT_THRESHOLD = 7

PRIORITY_SCORES = {"high": 2, "medium": 1, "low": 0}
TIER_SCORES = {"high": 4, "normal": 2}


def load_keywords(path: str) -> list[tuple[str, str]]:
    """Load tiered keywords from file.

    Parses '# tier:high' / '# tier:normal' section markers.
    Returns list of (keyword, tier) tuples.
    """
    kws: list[tuple[str, str]] = []
    current_tier = "normal"
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("# tier:"):
                current_tier = line.split("# tier:", 1)[1].strip().split()[0]
                continue
            if line.startswith("#"):
                continue
            kws.append((line.lower(), current_tier))
    return kws


def _word_boundary_match(keyword: str, text: str) -> bool:
    """Match keyword with word boundaries to avoid substring false positives.

    Multi-word keywords (e.g. 'open source') use substring match.
    Single-word keywords use \\b word boundary regex.
    """
    if " " in keyword or "-" in keyword:
        return keyword in text
    return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))


def load_rss_sources(path: str) -> list[dict]:
    """Load RSS sources from rss_sources.json format."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("sources", data) if isinstance(data, dict) else data


def load_feeds_txt(path: str) -> list[dict]:
    """Load feeds from plain text file, one URL per line."""
    sources = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sources.append({"url": line, "priority": "medium", "name": line})
    return sources


# ── Scoring ──────────────────────────────────────────────────────────

def score_item(
    title: str, source_priority: str, keywords: list[tuple[str, str]]
) -> tuple[int, list[str]]:
    """Score an item by tiered keyword matches + source priority.

    - tier:high keyword match: +4
    - tier:normal keyword match: +2
    - Source priority bonus: high=2, medium=1, low=0
    - Urgency signals: ALL CAPS word (+1), exclamation (+1)

    Returns (score, matched_keywords).
    """
    score = PRIORITY_SCORES.get(source_priority, 0)
    title_lower = title.lower()
    matched: list[str] = []

    for kw, tier in keywords:
        if _word_boundary_match(kw, title_lower):
            score += TIER_SCORES.get(tier, 2)
            matched.append(kw)

    # Urgency signals
    words = title.split()
    caps_words = sum(1 for w in words if w.isupper() and len(w) > 2)
    if caps_words >= 2:
        score += 1
    if "!" in title:
        score += 1

    return score, matched


# ── Fetch + filter ───────────────────────────────────────────────────

def fetch_and_score(
    sources: list[dict],
    keywords: list[tuple[str, str]],
    since_hours: float,
    seen: dict[str, float],
    threshold: int = ALERT_THRESHOLD,
) -> list[dict]:
    """Fetch RSS items, score, filter by threshold and dedup."""
    now = datetime.now(timezone.utc)
    alerts: list[dict] = []

    for src in sources:
        url = src.get("url", "")
        if not url or not url.startswith("http"):
            continue
        priority = src.get("priority", "medium")
        source_name = src.get("name", url)

        # Fetch entries: HTML scraper for non-RSS, feedparser for RSS
        scrape_cfg = src.get("scrape")
        if scrape_cfg:
            raw_entries = fetch_html_entries(url, scrape_cfg, since_hours)
        else:
            try:
                d = feedparser.parse(url)
            except Exception:
                continue
            raw_entries = [
                {"title": (e.get("title") or "").strip(),
                 "link": (e.get("link") or "").strip(),
                 "published": e.get("published") or e.get("updated")}
                for e in d.entries[:20]
            ]

        for entry in raw_entries:
            title = entry["title"]
            link = entry["link"]
            if not title or not link:
                continue

            # Dedup
            if link in seen:
                continue

            # Time filter
            dt = parse_pub_date(entry["published"])
            if dt and since_hours > 0:
                age_hours = (now - dt).total_seconds() / 3600
                if age_hours > since_hours:
                    continue

            # Score
            sc, matched = score_item(title, priority, keywords)
            if sc >= threshold:
                alerts.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "score": sc,
                    "matched": matched,
                    "published": format_kst(dt) if dt else "",
                })

    # Sort by score descending
    alerts.sort(key=lambda x: x["score"], reverse=True)
    return alerts


# ── Output formatting ────────────────────────────────────────────────

def format_telegram(alert: dict) -> str:
    """Format a single alert as Telegram message."""
    title = alert["title"]
    source = alert["source"]
    pub = alert["published"]
    url = alert["link"]
    matched = alert.get("matched", [])
    time_str = f" | {pub}" if pub else ""
    keywords_str = f"\nKeywords: {', '.join(matched)}" if matched else ""
    return f"🚨 Breaking: {title}\nSource: {source}{time_str}{keywords_str}\n{url}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Breaking news alert (zero LLM)")
    ap.add_argument("--sources", help="RSS sources JSON (rss_sources.json format)")
    ap.add_argument("--feeds", help="RSS feeds text file (one URL per line)")
    ap.add_argument("--keywords", required=True, help="Breaking keywords file")
    ap.add_argument("--since", type=float, default=1,
                    help="Only check items from last N hours (default: 1)")
    ap.add_argument("--threshold", type=int, default=ALERT_THRESHOLD,
                    help=f"Alert score threshold (default: {ALERT_THRESHOLD})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print alerts but don't update seen cache")
    args = ap.parse_args()

    if not args.sources and not args.feeds:
        print("Error: --sources or --feeds required", file=sys.stderr)
        sys.exit(1)

    # Load sources
    sources: list[dict] = []
    if args.sources:
        sources.extend(load_rss_sources(args.sources))
    if args.feeds:
        sources.extend(load_feeds_txt(args.feeds))

    keywords = load_keywords(args.keywords)
    seen = prune_seen(load_seen(SEEN_FILE))

    alerts = fetch_and_score(sources, keywords, args.since, seen,
                             threshold=args.threshold)

    if not alerts:
        if args.dry_run:
            print("(dry-run) No breaking alerts", file=sys.stderr)
        return

    for alert in alerts:
        print(format_telegram(alert))
        print()

    # Update seen cache
    if not args.dry_run:
        now = time.time()
        for alert in alerts:
            seen[alert["link"]] = now
        save_seen(seen, SEEN_FILE)
        print(f"({len(alerts)} alerts sent, cache updated)", file=sys.stderr)
    else:
        print(f"(dry-run) {len(alerts)} alerts would be sent", file=sys.stderr)


if __name__ == "__main__":
    main()
