#!/usr/bin/env python3
"""Shared SQLite connection and schema for news-brief forecast module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "news-brief" / "forecast.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY,
    date        TEXT NOT NULL,
    title       TEXT NOT NULL,
    headline    TEXT,
    url         TEXT UNIQUE NOT NULL,
    source      TEXT,
    section     TEXT,
    tag         TEXT,
    score       REAL,
    coverage    INTEGER DEFAULT 1,
    summary     TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
CREATE INDEX IF NOT EXISTS idx_articles_section ON articles(section);

CREATE TABLE IF NOT EXISTS article_entities (
    article_id  INTEGER REFERENCES articles(id),
    entity      TEXT NOT NULL,
    PRIMARY KEY (article_id, entity)
);

CREATE INDEX IF NOT EXISTS idx_entities_entity ON article_entities(entity);

CREATE TABLE IF NOT EXISTS forecasts (
    id            INTEGER PRIMARY KEY,
    week          TEXT NOT NULL UNIQUE,
    created_at    TEXT DEFAULT (datetime('now')),
    signal_json   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY,
    forecast_id   INTEGER REFERENCES forecasts(id),
    claim         TEXT NOT NULL,
    confidence    REAL NOT NULL,
    reasoning     TEXT NOT NULL,
    deadline      TEXT NOT NULL,
    status        TEXT DEFAULT 'open',
    verified_at   TEXT,
    verification  TEXT
);

CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_deadline ON predictions(deadline);

CREATE TABLE IF NOT EXISTS improvement_log (
    id            INTEGER PRIMARY KEY,
    week          TEXT NOT NULL,
    accuracy      REAL,
    bias_analysis TEXT,
    lesson        TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open SQLite connection. Creates parent directories if needed."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.executescript(SCHEMA_SQL)
