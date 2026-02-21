#!/usr/bin/env python3
"""Compose multiple pipeline JSONs into render_newspaper.py input schema.

Merges General, AI Trends, and Ronik pipeline outputs into a single
JSON document that render_newspaper.py can render as an HTML newspaper.

Supports two modes:
  1. Raw mode: news_brief.py JSON → auto-map (description→summary, tag→section)
  2. Enriched mode: pre-analyzed JSON with headline_ko, summary, tag, why fields

Usage:
  python3 compose-newspaper.py \
    --general /tmp/general.json \
    --ai-trends /tmp/ai_trends.json \
    --ronik /tmp/ronik.json \
    --highlight "오늘의 핵심 한줄" \
    --output /tmp/newspaper_data.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kst_utils import format_pub_kst

# General news category order
_GENERAL_SECTION_ORDER = ["국제", "국내", "경제", "기타"]
_GENERAL_SECTION_TITLES = {
    "국제": "🌏 국제",
    "국내": "🇰🇷 국내",
    "경제": "💰 경제",
    "기타": "📌 기타",
}


def load_json(path: str) -> list | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── General pipeline ─────────────────────────────────────────────────

def map_general_items(items: list[dict]) -> dict[str, list[dict]]:
    """Map news_brief.py JSON items, grouped by tag (국내/국제/경제).

    Returns {category: [items]} for section splitting.
    Supports both raw items (title/description) and enriched items
    (headline/headline_ko/summary/why).
    """
    groups: dict[str, list[dict]] = {}
    for it in items:
        # Enriched items have headline_ko; raw items have title
        headline = it.get("headline") or it.get("headline_ko") or it.get("title", "")
        summary = it.get("summary") or it.get("description", "")
        tag = it.get("tag") or "기타"
        mapped = {
            "headline": headline,
            "url": it.get("url") or it.get("link", ""),
            "source": it.get("source", ""),
            "tag": tag,
            "published": it.get("published", ""),
        }
        if summary:
            mapped["summary"] = summary
        if it.get("why"):
            mapped["why"] = it["why"]
        groups.setdefault(tag, []).append(mapped)
    return groups


def map_ronik_items(items: list[dict]) -> list[dict]:
    """Map Ronik items — same structure as general but tagged for Ronik."""
    out = []
    for it in items:
        headline = it.get("headline") or it.get("headline_ko") or it.get("title", "")
        mapped = {
            "headline": headline,
            "url": it.get("url") or it.get("link", ""),
            "source": it.get("source", ""),
            "tag": "Ronik",
            "published": it.get("published", ""),
        }
        summary = it.get("summary") or it.get("description", "")
        if summary:
            mapped["summary"] = summary
        if it.get("why"):
            mapped["why"] = it["why"]
        # Ronik enriched fields
        for field in ("opportunity", "risk", "action"):
            if it.get(field):
                mapped[field] = it[field]
        out.append(mapped)
    return out


# ── AI Trends pipeline ───────────────────────────────────────────────

def _is_reddit_community(item: dict) -> bool:
    cat = (item.get("category") or "").lower()
    source = (item.get("source") or "").lower()
    return cat == "community" or "reddit" in source


def map_ai_trends_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map AI Trends items → (main_items, reddit_items)."""
    main, reddit = [], []
    for it in items:
        mapped = {
            "headline": it.get("name", ""),
            "url": it.get("source", ""),
            "source": _extract_domain(it.get("source", "")),
            "tag": it.get("category", ""),
            "published": format_pub_kst(it.get("published")),
            "summary": it.get("summary", ""),
            "why": it.get("why", ""),
        }
        if _is_reddit_community(it):
            reddit.append(mapped)
        else:
            main.append(mapped)
    return main, reddit


def _extract_domain(url: str) -> str:
    if not url or not url.startswith("http"):
        return url
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


# ── Compose ──────────────────────────────────────────────────────────

def compose(
    general: list[dict] | None,
    ai_trends: dict | None,
    ronik: list[dict] | None,
    highlight: str = "",
) -> dict:
    """Compose pipeline outputs into render_newspaper.py input schema."""
    today = datetime.now().strftime("%Y-%m-%d")
    sections: list[dict] = []

    # General News — split by category (국제/국내/경제)
    if general:
        groups = map_general_items(general)
        for cat in _GENERAL_SECTION_ORDER:
            items = groups.get(cat)
            if items:
                sections.append({
                    "title": _GENERAL_SECTION_TITLES.get(cat, cat),
                    "items": items,
                })
        # Any remaining categories not in order
        for cat, items in groups.items():
            if cat not in _GENERAL_SECTION_ORDER and items:
                sections.append({"title": cat, "items": items})

    # AI & Tech Trends (without Reddit/Community)
    reddit_items: list[dict] = []
    if ai_trends:
        ai_items = ai_trends.get("items") or []
        main_items, reddit_items = map_ai_trends_items(ai_items)
        if main_items:
            sections.append({
                "title": "AI & Tech Trends",
                "items": main_items,
                "insight": (ai_trends.get("briefing") or "")[:200],
            })

    # Reddit & Community
    if reddit_items:
        sections.append({
            "title": "Reddit & Community",
            "items": reddit_items,
        })

    # Ronik Industry
    if ronik:
        items = map_ronik_items(ronik)
        if items:
            sections.append({
                "title": "Ronik Industry",
                "items": items,
            })

    result: dict = {
        "date": ai_trends.get("date", today) if ai_trends else today,
        "sections": sections,
    }
    if highlight:
        result["highlight"] = highlight

    return result


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compose pipeline JSONs into newspaper schema"
    )
    ap.add_argument("--general", help="General pipeline JSON")
    ap.add_argument("--ai-trends", help="AI Trends pipeline JSON")
    ap.add_argument("--ronik", help="Ronik pipeline JSON")
    ap.add_argument("--highlight", default="", help="오늘의 핵심 한줄")
    ap.add_argument("--output", help="Output JSON file (default: stdout)")
    args = ap.parse_args()

    if not any([args.general, args.ai_trends, args.ronik]):
        print("Error: at least one pipeline input required", file=sys.stderr)
        sys.exit(1)

    general = load_json(args.general) if args.general else None
    ai_trends = load_json(args.ai_trends) if args.ai_trends else None
    ronik = load_json(args.ronik) if args.ronik else None

    result = compose(general, ai_trends, ronik, highlight=args.highlight)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ {args.output} ({len(result['sections'])} sections)", file=sys.stderr)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()


if __name__ == "__main__":
    main()
