#!/usr/bin/env python3
"""Compose multiple pipeline JSONs into render_newspaper.py input schema.

Merges General, AI Trends, and Ronik pipeline outputs into a single
JSON document that render_newspaper.py can render as an HTML newspaper.

Usage:
  python3 compose-newspaper.py \
    --general /tmp/general.json \
    --ai-trends /tmp/ai_trends.json \
    --ronik /tmp/ronik.json \
    --output /tmp/newspaper_data.json

All inputs are optional — only provided pipelines are included.
Output defaults to stdout if --output is not specified.
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


def load_json(path: str) -> list | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── General / Ronik pipeline (news_brief.py --output-format json) ─────

def map_general_items(items: list[dict]) -> list[dict]:
    """Map news_brief.py JSON items to render_newspaper.py item schema."""
    out = []
    for it in items:
        out.append({
            "headline": it.get("title", ""),
            "url": it.get("link", ""),
            "source": it.get("source", ""),
            "tag": "",
            "published": it.get("published", ""),
        })
    return out


def map_ronik_items(items: list[dict]) -> list[dict]:
    """Map Ronik items — same structure as general but tagged for Ronik."""
    out = []
    for it in items:
        out.append({
            "headline": it.get("title", ""),
            "url": it.get("link", ""),
            "source": it.get("source", ""),
            "tag": "Ronik",
            "published": it.get("published", ""),
        })
    return out


# ── AI Trends pipeline (ai_trends_ingest.py input format) ────────────

def _is_reddit_community(item: dict) -> bool:
    """Check if an AI Trends item belongs to Reddit/Community."""
    cat = (item.get("category") or "").lower()
    source = (item.get("source") or "").lower()
    return cat == "community" or "reddit" in source


def map_ai_trends_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map AI Trends items → (main_items, reddit_items).

    Splits Community/Reddit items into a separate list for their own section.
    """
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
    """Extract readable domain from URL."""
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
) -> dict:
    """Compose pipeline outputs into render_newspaper.py input schema."""
    today = datetime.now().strftime("%Y-%m-%d")
    sections: list[dict] = []

    # Section 1: General News
    if general:
        items = map_general_items(general)
        if items:
            sections.append({
                "title": "General News",
                "items": items,
            })

    # Section 2: AI & Tech Trends (without Reddit/Community)
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

    # Section 3: Reddit & Community (split from AI Trends)
    if reddit_items:
        sections.append({
            "title": "Reddit & Community",
            "items": reddit_items,
        })

    # Section 4: Ronik Industry
    if ronik:
        items = map_ronik_items(ronik)
        if items:
            sections.append({
                "title": "Ronik Industry",
                "items": items,
            })

    return {
        "date": ai_trends.get("date", today) if ai_trends else today,
        "sections": sections,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compose pipeline JSONs into newspaper schema"
    )
    ap.add_argument("--general", help="General pipeline JSON (news_brief.py --output-format json)")
    ap.add_argument("--ai-trends", help="AI Trends pipeline JSON (ai_trends_ingest.py input)")
    ap.add_argument("--ronik", help="Ronik pipeline JSON (news_brief.py --output-format json)")
    ap.add_argument("--output", help="Output JSON file (default: stdout)")
    args = ap.parse_args()

    if not any([args.general, args.ai_trends, args.ronik]):
        print("Error: at least one pipeline input required", file=sys.stderr)
        sys.exit(1)

    general = load_json(args.general) if args.general else None
    ai_trends = load_json(args.ai_trends) if args.ai_trends else None
    ronik = load_json(args.ronik) if args.ronik else None

    result = compose(general, ai_trends, ronik)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ {args.output} ({len(result['sections'])} sections)", file=sys.stderr)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()


if __name__ == "__main__":
    main()
