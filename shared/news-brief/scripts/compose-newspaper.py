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
import re
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kst_utils import extract_domain, format_pub_kst

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

# Patterns that indicate raw RSS boilerplate (not real summaries)
_HN_BOILERPLATE = re.compile(
    r"Article URL:\s*https?://\S+\s*Comments URL:\s*https?://",
    re.IGNORECASE,
)
_REDDIT_BOILERPLATE = re.compile(
    r"(&#32;|&amp;#32;|\s)*submitted by\s+(&#32;|&amp;#32;|\s)*/u/\S+\s*\[link\]",
    re.IGNORECASE,
)


def _clean_community_summary(summary: str) -> str:
    """Strip HN/Reddit RSS boilerplate from summaries.

    Returns empty string if the summary is entirely boilerplate.
    """
    if not summary:
        return ""
    if _HN_BOILERPLATE.search(summary):
        return ""
    if _REDDIT_BOILERPLATE.search(summary):
        return ""
    return summary


# Community origin sources — Reddit만 커뮤니티 섹션 배치
# HN은 AI·테크, PH는 Tools, GitHub Trending은 Open-source로 분류
_COMMUNITY_ORIGINS = {
    "reddit", "reddit r/artificial", "reddit r/machinelearning",
}


def _is_community(item: dict) -> bool:
    """Check if item originates from a community source."""
    origin = (item.get("origin_source") or "").lower()
    if origin and origin in _COMMUNITY_ORIGINS:
        return True
    # Fallback: check category for backward compatibility
    cat = (item.get("category") or "").lower()
    return cat == "community"


def map_ai_trends_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map AI Trends items → (main_items, community_items).

    Supports three input formats:
      - Writer vault format: name, url/source (URL), source_name, origin_source
      - Researcher format: name/title, url, source_name, origin_source
      - news_brief.py format: title, link, source, tag, description
    """
    main, community = [], []
    for it in items:
        # URL: prefer explicit 'url', fallback to 'link' (news_brief.py), 'source' (writer)
        url = it.get("url") or it.get("link") or it.get("source", "")
        # Source name: prefer 'source_name', fallback to 'source' (news_brief.py), domain
        source_name = it.get("source_name") or it.get("source") or extract_domain(url)
        # Summary: prefer 'summary', fallback to 'description' (news_brief.py)
        summary = it.get("summary") or it.get("description", "")

        mapped = {
            "headline": it.get("name") or it.get("title", ""),
            "url": url,
            "source": source_name,
            "tag": it.get("category") or it.get("tag", ""),
            "published": format_pub_kst(it.get("published")),
            "summary": _clean_community_summary(summary),
            "why": it.get("why", ""),
            "origin_source": it.get("origin_source", ""),
        }
        if _is_community(it):
            community.append(mapped)
        else:
            main.append(mapped)
    return main, community



# ── Compose ──────────────────────────────────────────────────────────

def map_community_items(items: list[dict]) -> list[dict]:
    """Map news_brief.py JSON items from community feeds (Reddit etc.)."""
    out = []
    for it in items:
        headline = it.get("headline") or it.get("headline_ko") or it.get("title", "")
        summary = it.get("summary") or it.get("description", "")
        mapped = {
            "headline": headline,
            "url": it.get("url") or it.get("link", ""),
            "source": it.get("source", "") or extract_domain(it.get("url") or it.get("link", "")),
            "tag": "Community",
            "published": it.get("published", ""),
            "origin_source": it.get("origin_source", "Reddit"),
        }
        summary = _clean_community_summary(summary)
        if summary:
            mapped["summary"] = summary
        if it.get("why"):
            mapped["why"] = it["why"]
        out.append(mapped)
    return out


def compose(
    general: list[dict] | None,
    ai_trends: list[dict] | dict | None,
    ronik: list[dict] | None,
    community: list[dict] | None = None,
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

    # Normalize ai_trends: news_brief.py outputs list, researcher outputs dict
    if isinstance(ai_trends, list):
        ai_trends = {"items": ai_trends}

    # AI·테크 (커뮤니티 제외)
    ai_community_items: list[dict] = []
    if ai_trends:
        ai_items = ai_trends.get("items") or []
        main_items, ai_community_items = map_ai_trends_items(ai_items)
        if main_items:
            sections.append({
                "title": "🤖 AI·테크",
                "items": main_items,
                "insight": (ai_trends.get("briefing") or "")[:200],
            })

    # 커뮤니티: news_brief.py 경유 Reddit + AI Trends 내 커뮤니티 아이템 합산
    all_community = []
    if community:
        all_community.extend(map_community_items(community))
    all_community.extend(ai_community_items)
    if all_community:
        sections.append({
            "title": "💬 커뮤니티",
            "items": all_community,
        })

    # 로닉 산업
    if ronik:
        items = map_ronik_items(ronik)
        if items:
            sections.append({
                "title": "🏭 로닉 산업",
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
    ap.add_argument("--community", help="Community pipeline JSON (Reddit via news_brief.py)")
    ap.add_argument("--highlight", default="", help="오늘의 핵심 한줄")
    ap.add_argument("--output", help="Output JSON file (default: stdout)")
    args = ap.parse_args()

    if not any([args.general, args.ai_trends, args.ronik, args.community]):
        print("Error: at least one pipeline input required", file=sys.stderr)
        sys.exit(1)

    general = load_json(args.general) if args.general else None
    ai_trends = load_json(args.ai_trends) if args.ai_trends else None
    ronik = load_json(args.ronik) if args.ronik else None
    community = load_json(args.community) if args.community else None

    result = compose(general, ai_trends, ronik, community=community, highlight=args.highlight)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ {args.output} ({len(result['sections'])} sections)", file=sys.stderr)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()


if __name__ == "__main__":
    main()
