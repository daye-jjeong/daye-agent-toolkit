"""Tests for forecast_db module."""
import sqlite3
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from forecast_db import get_connection, init_db


def test_init_db_creates_tables(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "articles" in tables
    assert "article_entities" in tables
    assert "forecasts" in tables
    assert "predictions" in tables
    assert "improvement_log" in tables
    conn.close()


def test_init_db_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)  # second call should not raise
    cursor = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
    count = cursor.fetchone()[0]
    assert count >= 5
    conn.close()
