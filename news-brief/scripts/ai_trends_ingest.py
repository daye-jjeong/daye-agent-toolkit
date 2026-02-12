#!/usr/bin/env python3
"""Ingest Daily AI Trends into Notion DB + create a one-page briefing.

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

Not financial/legal/medical advice.

Updated 2026-02-03: Uses unified NotionClient with connection reuse & retry logic
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from skills.notion.client import NotionClient

# Config (created on 2026-01-30)
AI_TRENDS_DB_ID = "b2e30103-ff77-4440-a496-770580ef8203"
PARENT_PAGE_ID = "2f768ba6-9421-80b9-865d-c402d89bc6cf"  # DAYE HQ

# Initialize NotionClient
notion = NotionClient(workspace="personal")


def rt(text: str):
    return [{"type": "text", "text": {"content": text}}]


def paragraph(text: str):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rt(text)},
    }


def heading(text: str, level: int = 2):
    t = f"heading_{level}"
    return {"object": "block", "type": t, t: {"rich_text": rt(text)}}


def bulleted_link(label: str, url: str):
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {"type": "text", "text": {"content": label, "link": {"url": url}}}
            ]
        },
    }


def create_briefing_page(title: str, date_iso: str, briefing: str, links: list[dict]) -> str:
    props = {
        "title": {"title": rt(title)},
    }
    page = notion.create_page(
        parent={"page_id": PARENT_PAGE_ID},
        properties=props
    )

    blocks = [
        paragraph(f"Date: {date_iso}"),
        heading("Briefing", 2),
    ]

    for line in (briefing or "").splitlines():
        line = line.strip()
        if not line:
            continue
        blocks.append(paragraph(line))

    if links:
        blocks.append(heading("Links", 2))
        for l in links[:10]:
            if l.get("url"):
                blocks.append(bulleted_link(l.get("label") or l["url"], l["url"]))

    # append blocks (using batch-safe method)
    notion.append_blocks_batch(page['id'], blocks)

    return page.get("url")


def create_db_item(it: dict, date_iso: str, briefing_url: str | None):
    props = {
        "Name": {"title": rt(it.get("name", "(untitled)"))},
        "Date": {"date": {"start": date_iso}},
        "Category": {"select": {"name": it.get("category", "Other")}},
        "Summary": {"rich_text": rt(it.get("summary", ""))},
        "Why it matters": {"rich_text": rt(it.get("why", ""))},
        "Source": {"url": it.get("source")},
        "Tags": {"multi_select": [{"name": t} for t in (it.get("tags") or [])][:10]},
    }
    if briefing_url:
        props["Briefing Page"] = {"url": briefing_url}

    notion.create_page(
        parent={"database_id": AI_TRENDS_DB_ID},
        properties=props
    )


def main():
    payload = json.loads(sys.stdin.read() or "{}")
    date_iso = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
    title = payload.get("title") or f"AI Trends Briefing — {date_iso}"

    briefing_url = create_briefing_page(
        title=title,
        date_iso=date_iso,
        briefing=payload.get("briefing") or "",
        links=payload.get("links") or [],
    )

    for it in payload.get("items") or []:
        create_db_item(it, date_iso=date_iso, briefing_url=briefing_url)

    print(json.dumps({"ok": True, "briefing_url": briefing_url, "count": len(payload.get('items') or [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
