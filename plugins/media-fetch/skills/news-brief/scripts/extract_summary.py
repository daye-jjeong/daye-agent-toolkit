#!/usr/bin/env python3
"""
extract_summary.py — 최종 enriched composed JSON에서 실제 헤드라인을 추출해
thread 멘션용 요약 메시지를 생성한다.

LLM 환각 방지: JSON에서 직접 읽은 헤드라인만 사용. 임의 생성 금지.

Usage:
    python3 extract_summary.py --input /tmp/composed_enriched.json

Output:
    stdout으로 요약 메시지 출력 (minions thread add --content 에 사용)
"""
from __future__ import annotations
import argparse
import json
import sys


def generate_summary(data: dict, max_per_section: int = 2) -> str:
    """enriched composed JSON → 요약 메시지 문자열."""
    highlight = data.get("highlight", "")
    sections = data.get("sections", [])
    date_str = data.get("date", "")

    lines = []

    if date_str:
        lines.append(f"☀️ 오늘의 신문 ({date_str})")
    else:
        lines.append("☀️ 오늘의 신문")

    lines.append("")

    if highlight:
        lines.append(f"📌 오늘의 핵심: {highlight}")
        lines.append("")

    lines.append("주요 헤드라인:")

    for sec in sections:
        title = sec.get("title", "")
        items = sec.get("items", [])
        if not items:
            continue
        top_items = items[:max_per_section]
        headlines = [
            item.get("headline", "").strip()
            for item in top_items
            if item.get("headline", "").strip()
        ]
        if not headlines:
            continue
        lines.append(f"\n{title}")
        for h in headlines:
            lines.append(f"• {h}")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extract summary from enriched composed JSON (no hallucination)"
    )
    ap.add_argument(
        "--input", required=True,
        help="Path to enriched composed JSON (after enrich.py apply)"
    )
    ap.add_argument(
        "--max-per-section", type=int, default=2,
        help="Max headlines per section (default: 2)"
    )
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = generate_summary(data, args.max_per_section)
    print(summary)


if __name__ == "__main__":
    main()
