"""Tests for archive.py — enriched newspaper JSON → SQLite."""
import json
import sqlite3
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from forecast_db import get_connection, init_db
from archive import archive_newspaper


SAMPLE_ENRICHED = {
    "date": "2026-03-28",
    "highlight": "테스트 하이라이트",
    "sections": [
        {
            "title": "🤖 AI·테크",
            "items": [
                {
                    "headline": "Anthropic Claude 4 발표",
                    "url": "https://example.com/claude4",
                    "source": "anthropic.com",
                    "tag": "Models",
                    "published": "2026-03-28 10:00 KST",
                    "summary": "새로운 모델이 출시되었다.",
                    "why": "성능이 크게 향상되었기 때문",
                },
                {
                    "headline": "OpenAI GPT-5 루머",
                    "url": "https://example.com/gpt5",
                    "source": "techcrunch.com",
                    "tag": "Models",
                    "published": "2026-03-28 11:00 KST",
                    "summary": "GPT-5 출시 루머가 돌고 있다.",
                },
            ],
        },
        {
            "title": "🌏 국제",
            "items": [
                {
                    "headline": "EU AI 규제 강화",
                    "url": "https://example.com/eu-ai",
                    "source": "reuters.com",
                    "tag": "국제",
                    "published": "2026-03-28 09:00 KST",
                    "summary": "EU가 AI 규제를 강화한다.",
                },
            ],
        },
    ],
}


def _setup_db(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    return conn, db_path


def test_archive_inserts_articles(tmp_path: Path):
    conn, db_path = _setup_db(tmp_path)
    json_path = tmp_path / "enriched.json"
    json_path.write_text(json.dumps(SAMPLE_ENRICHED, ensure_ascii=False))

    count = archive_newspaper(str(json_path), str(db_path))

    assert count == 3
    rows = conn.execute("SELECT * FROM articles ORDER BY id").fetchall()
    assert len(rows) == 3
    assert rows[0]["headline"] == "Anthropic Claude 4 발표"
    assert rows[0]["section"] == "🤖 AI·테크"
    assert rows[0]["date"] == "2026-03-28"
    conn.close()


def test_archive_extracts_entities(tmp_path: Path):
    conn, db_path = _setup_db(tmp_path)
    json_path = tmp_path / "enriched.json"
    json_path.write_text(json.dumps(SAMPLE_ENRICHED, ensure_ascii=False))

    archive_newspaper(str(json_path), str(db_path))

    entities = conn.execute(
        "SELECT entity FROM article_entities WHERE article_id = 1"
    ).fetchall()
    entity_set = {row["entity"] for row in entities}
    assert "anthropic" in entity_set
    assert "claude" in entity_set
    conn.close()


def test_archive_ignores_duplicates(tmp_path: Path):
    conn, db_path = _setup_db(tmp_path)
    json_path = tmp_path / "enriched.json"
    json_path.write_text(json.dumps(SAMPLE_ENRICHED, ensure_ascii=False))

    archive_newspaper(str(json_path), str(db_path))
    count = archive_newspaper(str(json_path), str(db_path))

    assert count == 0  # all duplicates skipped
    rows = conn.execute("SELECT count(*) as cnt FROM articles").fetchone()
    assert rows["cnt"] == 3
    conn.close()
