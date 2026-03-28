#!/usr/bin/env python3
"""Archive enriched newspaper JSON into forecast SQLite DB.

Usage:
    python3 archive.py --input /tmp/enriched.json [--db ~/.local/share/news-brief/forecast.db]

Reads compose+enrich output (newspaper schema) and inserts articles + entities.
Duplicate URLs are silently skipped (INSERT OR IGNORE).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forecast_db import get_connection, init_db

_KO_PARTICLES = re.compile(r"(은|는|이|가|을|를|의|에|와|과|로|으로|도|만|까지|부터|에서)$")


def extract_entities(text: str) -> set[str]:
    """Extract entity candidates from headline/title.

    Korean: 2+ character words after stripping trailing particles.
    English: 3+ character words (lowercased).
    """
    entities: set[str] = set()
    t = re.sub(r"[\[\]()\"\"''·…「」『』〈〉《》%↑↓]", " ", text)

    for m in re.findall(r"[가-힣]{2,}", t):
        if len(m) >= 3:
            cleaned = _KO_PARTICLES.sub("", m)
            if len(cleaned) >= 2:
                entities.add(cleaned)
        else:
            entities.add(m)

    for m in re.findall(r"[a-zA-Z]{3,}", t):
        entities.add(m.lower())

    return entities


def archive_newspaper(input_path: str, db_path: str | None = None) -> int:
    """Archive enriched newspaper JSON into DB. Returns count of new articles."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = get_connection(db_path)
    init_db(conn)

    date = data.get("date", "")
    inserted = 0

    for section in data.get("sections", []):
        section_title = section.get("title", "")
        for item in section.get("items", []):
            url = item.get("url", "")
            if not url:
                continue

            headline = item.get("headline", "")
            title = item.get("title", headline)

            try:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO articles
                       (date, title, headline, url, source, section, tag, score, coverage, summary)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        date,
                        title,
                        headline,
                        url,
                        item.get("source", ""),
                        section_title,
                        item.get("tag", ""),
                        item.get("score"),
                        item.get("coverage", 1),
                        item.get("summary", ""),
                    ),
                )
            except sqlite3.IntegrityError:
                continue

            if cursor.rowcount == 0:
                continue

            article_id = cursor.lastrowid
            inserted += 1

            entity_text = headline or title
            for entity in extract_entities(entity_text):
                conn.execute(
                    "INSERT OR IGNORE INTO article_entities (article_id, entity) VALUES (?, ?)",
                    (article_id, entity),
                )

    conn.commit()
    conn.close()
    return inserted


def main():
    ap = argparse.ArgumentParser(description="Archive enriched newspaper JSON to SQLite")
    ap.add_argument("--input", required=True, help="Path to enriched newspaper JSON")
    ap.add_argument("--db", default=None, help="SQLite DB path (default: ~/.local/share/news-brief/forecast.db)")
    args = ap.parse_args()

    count = archive_newspaper(args.input, args.db)
    print(f"Archived {count} new articles")


if __name__ == "__main__":
    main()
