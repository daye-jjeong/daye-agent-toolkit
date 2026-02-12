#!/usr/bin/env python3
"""Save important news articles to vault as structured markdown.

Reads the same JSON schema as render_newspaper.py and produces a
markdown file in vault/reports/news-brief/YYYY-MM-DD.md.

Input JSON schema:
{
  "date": "2026-02-12",
  "sections": [...],
  "highlight": "오늘의 핵심"
}

Usage:
  echo '...' | python3 save_to_vault.py
  python3 save_to_vault.py --input data.json
  python3 save_to_vault.py --input data.json --vault-dir /path/to/vault
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# Default vault path — override with --vault-dir
DEFAULT_VAULT = os.path.expanduser("~/openclaw/vault")


def korean_date(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.year}년 {d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"


def render_item_md(item: dict) -> str:
    """Render a single item as markdown."""
    headline = item.get("headline", "")
    url = item.get("url", "")
    source = item.get("source", "")
    tag = item.get("tag", "")

    parts: list[str] = []

    # Headline with link
    if url:
        parts.append(f"### [{headline}]({url})")
    else:
        parts.append(f"### {headline}")

    # Meta line
    meta: list[str] = []
    if source:
        meta.append(source)
    if tag:
        meta.append(f"`{tag}`")
    if meta:
        parts.append(f"_{' · '.join(meta)}_")

    # Ronik format
    if "opportunity" in item:
        parts.append(f"- **기회**: {item['opportunity']}")
        if item.get("risk"):
            parts.append(f"- **리스크**: {item['risk']}")
        if item.get("action"):
            parts.append(f"- **액션**: {item['action']}")
    else:
        # Standard format
        summary = item.get("summary", "")
        if summary:
            parts.append(f"\n{summary}")
        why = item.get("why", "")
        if why:
            parts.append(f"\n> → {why}")

    return "\n".join(parts)


def render_section_md(section: dict) -> str:
    """Render a section as markdown."""
    title = section.get("title", "")
    items = section.get("items", [])
    insight = section.get("insight", "")

    if not items:
        return ""

    parts: list[str] = [f"## {title}", ""]

    for item in items:
        parts.append(render_item_md(item))
        parts.append("")

    if insight:
        parts.append(f"> 💡 **적용 아이디어** — {insight}")
        parts.append("")

    return "\n".join(parts)


def render_vault_md(data: dict) -> str:
    """Render full vault markdown with YAML frontmatter."""
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    kdate = korean_date(date_str)
    highlight = data.get("highlight", "")

    # Count total items
    total = sum(len(s.get("items", [])) for s in data.get("sections", []))
    section_names = [s.get("title", "") for s in data.get("sections", []) if s.get("items")]

    # YAML frontmatter
    lines: list[str] = [
        "---",
        "type: news-brief",
        f"date: {date_str}",
        "created_by: news-brief-skill",
        f"articles: {total}",
        f'sections: [{", ".join(section_names)}]',
        f'tags: [news, daily-brief, {date_str[:7]}]',
        "---",
        "",
        f"# 밍밍 데일리 — {kdate}",
        "",
    ]

    # Highlight at top
    if highlight:
        lines.append(f"> ★ **오늘의 핵심**: {highlight}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Sections
    for section in data.get("sections", []):
        section_md = render_section_md(section)
        if section_md:
            lines.append(section_md)

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Save news articles to vault")
    ap.add_argument("--input", help="JSON input file (default: stdin)")
    ap.add_argument(
        "--vault-dir",
        default=DEFAULT_VAULT,
        help=f"Vault root directory (default: {DEFAULT_VAULT})",
    )
    args = ap.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    md = render_vault_md(data)

    # Write to vault/reports/news-brief/YYYY-MM-DD.md
    out_dir = Path(args.vault_dir) / "reports" / "news-brief"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.md"

    out_path.write_text(md, encoding="utf-8")
    print(f"✅ {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
