#!/usr/bin/env python3
"""Enrich composed newspaper JSON — extract items for LLM translation/summary.

Two modes:
  extract: Read composed JSON, output items needing enrichment as structured JSON.
           Agent uses this to generate translations and summaries.
  apply:   Merge enrichment data back into composed JSON.

Usage:
  # 1. Extract items needing enrichment
  python3 enrich.py extract --input /tmp/composed.json > /tmp/to_enrich.json

  # 2. Agent processes to_enrich.json, generates /tmp/enrichments.json
  #    (translations + summaries for each item)

  # 3. Apply enrichments back
  python3 enrich.py apply --input /tmp/composed.json \
    --enrichments /tmp/enrichments.json --output /tmp/enriched.json

Enrichment JSON format (agent generates this):
{
  "highlight": "전체 기사를 종합한 오늘의 핵심 2-3문장",
  "0.0": {"headline": "한국어 제목", "summary": "한국어 요약", "why": "왜 중요한가"},
  "0.1": {"headline": "...", "summary": "...", "why": "..."},
  ...
}

Keys are "section_index.item_index" (e.g., "0.0" = first section, first item).
"""

from __future__ import annotations

import argparse
import json
import re
import sys


def _is_english(text: str) -> bool:
    """Check if text is primarily English (>60% ASCII letters)."""
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_letters = sum(1 for c in letters if ord(c) < 128)
    return ascii_letters / len(letters) > 0.6


def _is_raw_rss(text: str) -> bool:
    """Check if text looks like raw RSS description (byline, HTML entities, etc.)."""
    if not text:
        return True
    # Korean wire service byline pattern
    if re.match(r"^\(.*=연합뉴스\)", text):
        return True
    # HTML entities
    if "&quot;" in text or "&amp;" in text or "&apos;" in text:
        return True
    # Very short or truncated
    if len(text) < 15 or text.endswith("..."):
        return True
    return False


def extract(data: dict) -> dict:
    """Extract items needing enrichment from composed JSON."""
    items_to_enrich: dict[str, dict] = {}

    for si, sec in enumerate(data.get("sections", [])):
        for ii, item in enumerate(sec.get("items", [])):
            key = f"{si}.{ii}"
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            why = item.get("why", "")

            needs: list[str] = []

            if _is_english(headline):
                needs.append("translate_headline")
            if _is_english(summary) or _is_raw_rss(summary):
                needs.append("rewrite_summary")
            if not why:
                needs.append("add_why")

            if needs:
                items_to_enrich[key] = {
                    "headline": headline,
                    "summary": summary[:200] if summary else "",
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "tag": item.get("tag", ""),
                    "origin_source": item.get("origin_source", ""),
                    "needs": needs,
                }

    section_titles = [
        sec.get("title", "") for sec in data.get("sections", [])
    ]

    # Collect all headlines for highlight generation context
    all_headlines: list[str] = []
    for sec in data.get("sections", []):
        for item in sec.get("items", []):
            all_headlines.append(item.get("headline", ""))

    return {
        "total_items": sum(
            len(sec.get("items", [])) for sec in data.get("sections", [])
        ),
        "items_needing_enrichment": len(items_to_enrich),
        "section_titles": section_titles,
        "all_headlines": all_headlines,
        "items": items_to_enrich,
        "instructions": (
            "## 1. 각 항목 enrichment\n"
            "- translate_headline: 영어 제목을 자연스러운 한국어로 번역\n"
            "- rewrite_summary: 영어 요약은 한국어로 번역. "
            "RSS 원문 붙여넣기 금지, 기사 핵심을 한국어 1-2문장으로 새로 작성\n"
            "- add_why: '왜 중요한가' 1문장 (비즈니스/기술/사회 관점, '→' 접두사 붙이지 말 것). "
            "summary 복사 금지 — 반드시 다른 관점의 문장\n"
            "- 최종 HTML에 영어 텍스트가 하나도 남으면 안 됨 (headline, summary, why 모두 한국어)\n\n"
            "## 2. highlight (필수)\n"
            "전체 기사를 종합해서 '오늘의 핵심' 2-3문장을 작성하세요.\n"
            "- 섹션 카테고리 나열 금지 ('AI·테크 트렌드와 글로벌 뉴스 종합' 같은 건 의미 없음)\n"
            "- 오늘 가장 중요한 흐름 2-3개를 구체적으로, 서로 연결해서 서술\n"
            "- 예: '이란 전쟁 여파로 환율 1,480원·코스피 1%↓ — 금융시장 불안 지속. "
            "OpenAI GPT-5.4 공개로 AI 경쟁 격화.'\n\n"
            "## 출력 형식 (JSON)\n"
            '{"highlight": "오늘의 핵심 2-3문장", '
            '"0.0": {"headline": "...", "summary": "...", "why": "..."}, ...}'
        ),
    }


def apply(data: dict, enrichments: dict) -> tuple[dict, int]:
    """Apply enrichment data back into composed JSON."""
    applied = 0

    # Apply highlight if provided (overrides compose --highlight)
    if "highlight" in enrichments and enrichments["highlight"]:
        data["highlight"] = enrichments["highlight"]

    for key, values in enrichments.items():
        if key == "highlight":
            continue
        parts = key.split(".")
        if len(parts) != 2:
            continue
        si, ii = int(parts[0]), int(parts[1])
        sections = data.get("sections", [])
        if si >= len(sections):
            continue
        items = sections[si].get("items", [])
        if ii >= len(items):
            continue

        item = items[ii]
        if "headline" in values:
            item["headline"] = values["headline"]
        if "summary" in values:
            item["summary"] = values["summary"]
        if "why" in values:
            item["why"] = values["why"]
        applied += 1

    return data, applied


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Enrich composed newspaper JSON"
    )
    sub = ap.add_subparsers(dest="mode", required=True)

    # extract mode
    ext = sub.add_parser("extract", help="Extract items needing enrichment")
    ext.add_argument("--input", required=True, help="Composed JSON file")

    # apply mode
    app = sub.add_parser("apply", help="Apply enrichments back")
    app.add_argument("--input", required=True, help="Composed JSON file")
    app.add_argument(
        "--enrichments", required=True, help="Enrichments JSON file"
    )
    app.add_argument("--output", help="Output file (default: overwrite input)")

    args = ap.parse_args()

    if args.mode == "extract":
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = extract(data)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
        print(
            f"({result['items_needing_enrichment']}/{result['total_items']}"
            " items need enrichment)",
            file=sys.stderr,
        )

    elif args.mode == "apply":
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(args.enrichments, "r", encoding="utf-8") as f:
            enrichments = json.load(f)
        data, applied = apply(data, enrichments)
        out_path = args.output or args.input
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ {out_path} ({applied} items enriched)", file=sys.stderr)


if __name__ == "__main__":
    main()
