#!/usr/bin/env python3
"""Ingest Daily AI Trends into vault markdown.

Input (stdin JSON):
{
  "date": "YYYY-MM-DD",
  "title": "AI Trends Briefing — YYYY-MM-DD",
  "items": [
     {"name":"...","category":"Models|Tools|Policy|Open-source|Business|Other",
      "summary":"...","why":"...","source":"https://...","tags":["agent",...]
     },
     ...
  ],
  "briefing": "markdown-ish text (used as paragraphs)",
  "links": [{"label":"...","url":"..."}]
}

Output: vault/reports/ai-trends/{date}.md

Migrated 2026-02-12: Notion → vault (vault/reports/ai-trends/)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kst_utils import KST, KST_FMT, format_pub_kst

DEFAULT_VAULT = os.path.expanduser("~/openclaw/vault")


def render_markdown(payload: dict) -> str:
    """Render AI trends payload as markdown."""
    date_iso = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
    title = payload.get("title") or f"AI Trends Briefing — {date_iso}"
    items = payload.get("items") or []
    briefing = payload.get("briefing") or ""
    links = payload.get("links") or []

    now_kst = datetime.now(KST).strftime(KST_FMT)
    lines = [
        f"# {title}",
        f"",
        f"**Date:** {date_iso} | **Generated:** {now_kst}  ",
        f"**Items:** {len(items)}",
        "",
    ]

    # Briefing section
    if briefing.strip():
        lines.append("## Briefing")
        lines.append("")
        for line in briefing.splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        lines.append("")

    # Items by category
    if items:
        lines.append("## Items")
        lines.append("")

        # Group by category
        categories: dict[str, list] = {}
        for it in items:
            cat = it.get("category", "Other")
            categories.setdefault(cat, []).append(it)

        for cat, cat_items in categories.items():
            lines.append(f"### {cat}")
            lines.append("")
            for it in cat_items:
                name = it.get("name", "(untitled)")
                summary = it.get("summary", "")
                why = it.get("why", "")
                source = it.get("source", "")
                tags = it.get("tags") or []

                lines.append(f"- **{name}**")
                if summary:
                    lines.append(f"  - {summary}")
                if why:
                    lines.append(f"  - Why: {why}")
                if source:
                    lines.append(f"  - Source: {source}")
                if tags:
                    lines.append(f"  - Tags: {', '.join(tags)}")
            lines.append("")

    # Links section
    if links:
        lines.append("## Links")
        lines.append("")
        for link in links[:10]:
            label = link.get("label") or link.get("url", "")
            url = link.get("url", "")
            if url:
                lines.append(f"- [{label}]({url})")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Ingest AI trends into vault")
    ap.add_argument("--vault-dir", default=DEFAULT_VAULT,
                    help=f"Vault root directory (default: {DEFAULT_VAULT})")
    args = ap.parse_args()

    payload = json.loads(sys.stdin.read() or "{}")
    date_iso = payload.get("date") or datetime.now().strftime("%Y-%m-%d")

    # Render markdown
    md_content = render_markdown(payload)

    # Write to {vault-dir}/reports/ai-trends/YYYY-MM-DD.md
    out_dir = Path(args.vault_dir) / "reports" / "ai-trends"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{date_iso}.md"
    output_path.write_text(md_content, encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "output_path": str(output_path),
        "count": len(payload.get("items") or []),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
