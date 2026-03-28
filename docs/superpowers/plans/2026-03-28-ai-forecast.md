# AI 산업 주간 예측 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** news-brief에 일일 뉴스 아카이브 + 주간 AI 예측 자가개선 루프를 추가한다.

**Architecture:** 기존 뉴스페이퍼 파이프라인 끝에 archive.py가 enriched JSON을 SQLite에 적재. forecast.py가 시그널 추출, 검증 데이터 준비, 분석, 리포트 포맷팅을 서브커맨드로 제공. LLM 판단(예측 생성, 검증 판정)은 크론 에이전트가 수행.

**Tech Stack:** Python 3, sqlite3 (stdlib), argparse, json, re, pathlib

**Spec:** `docs/superpowers/specs/2026-03-28-ai-forecast-design.md`

---

### Task 1: DB 초기화 모듈

archive.py와 forecast.py가 공유하는 DB 연결 + 스키마 초기화.

**Files:**
- Create: `shared/news-brief/scripts/forecast_db.py`
- Create: `shared/news-brief/tests/test_forecast_db.py`

- [ ] **Step 1: Write failing test — DB 초기화**

```python
# shared/news-brief/tests/test_forecast_db.py
"""Tests for forecast_db module."""
import sqlite3
from pathlib import Path
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forecast_db'`

- [ ] **Step 3: Implement forecast_db.py**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast_db.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/scripts/forecast_db.py shared/news-brief/tests/test_forecast_db.py
git commit -m "feat(forecast): add shared DB module with schema initialization"
```

---

### Task 2: archive.py — enriched JSON → DB 적재

**Files:**
- Create: `shared/news-brief/scripts/archive.py`
- Create: `shared/news-brief/tests/test_archive.py`

- [ ] **Step 1: Write failing tests**

```python
# shared/news-brief/tests/test_archive.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_archive.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'archive'`

- [ ] **Step 3: Implement archive.py**

```python
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

# Korean particles to strip (same pattern as news_brief.py)
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
                continue  # duplicate URL

            article_id = cursor.lastrowid
            inserted += 1

            # Extract and insert entities
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_archive.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/scripts/archive.py shared/news-brief/tests/test_archive.py
git commit -m "feat(forecast): add archive.py for daily newspaper → DB ingestion"
```

---

### Task 3: forecast.py signals — 시그널 추출

**Files:**
- Create: `shared/news-brief/scripts/forecast.py`
- Create: `shared/news-brief/tests/test_forecast.py`

- [ ] **Step 1: Write failing tests**

```python
# shared/news-brief/tests/test_forecast.py
"""Tests for forecast.py subcommands."""
import json
import sqlite3
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from forecast_db import get_connection, init_db
from forecast import extract_signals


def _seed_articles(conn: sqlite3.Connection):
    """Seed 2 weeks of test data."""
    # This week (2026-W13: Mar 23-28)
    this_week = [
        ("2026-03-23", "Anthropic Claude 신모델 발표", "https://a.com/1", "AI·테크", "Models", 8.0, 3),
        ("2026-03-24", "Claude MCP 업데이트", "https://a.com/2", "AI·테크", "Models", 7.5, 2),
        ("2026-03-25", "Claude Code 새 기능", "https://a.com/3", "AI·테크", "Tools", 6.0, 1),
        ("2026-03-26", "OpenAI GPT-5 루머", "https://a.com/4", "AI·테크", "Models", 5.0, 1),
        ("2026-03-27", "EU AI 규제 강화", "https://a.com/5", "국제", "국제", 4.0, 2),
    ]
    # Last week (2026-W12: Mar 16-22)
    last_week = [
        ("2026-03-16", "Google Gemma 오픈소스", "https://b.com/1", "AI·테크", "Models", 7.0, 2),
        ("2026-03-17", "Meta LLaMA 업데이트", "https://b.com/2", "AI·테크", "Models", 6.0, 1),
    ]

    for row in this_week + last_week:
        cursor = conn.execute(
            "INSERT INTO articles (date, headline, url, section, tag, score, coverage) VALUES (?,?,?,?,?,?,?)",
            row,
        )
        aid = cursor.lastrowid
        # Extract simple entities from headline
        for word in row[1].split():
            if len(word) >= 2:
                conn.execute(
                    "INSERT OR IGNORE INTO article_entities (article_id, entity) VALUES (?, ?)",
                    (aid, word.lower()),
                )
    conn.commit()


def test_signals_keyword_surge(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    surges = {s["entity"]: s["ratio"] for s in signals["keyword_surges"]}
    # "claude" appears 3 times this week, 0 last week → should be in surges
    assert "claude" in surges


def test_signals_new_entities(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    new_ents = set(signals["new_entities"])
    # "mcp" only appears this week
    assert "mcp" in new_ents


def test_signals_high_coverage(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    coverage_urls = [s["url"] for s in signals["high_coverage"]]
    assert "https://a.com/1" in coverage_urls  # coverage=3


def test_signals_section_distribution(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    dist = signals["section_distribution"]
    assert "this_week" in dist
    assert "last_week" in dist


def test_signals_top_articles(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    top = signals["top_articles"]
    assert len(top) <= 10
    assert top[0]["score"] >= top[-1]["score"]  # sorted descending
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forecast'`

- [ ] **Step 3: Implement forecast.py (signals subcommand)**

```python
#!/usr/bin/env python3
"""Weekly AI forecast pipeline — signal extraction, verification, analysis, reporting.

Subcommands:
    signals       Extract weekly signals from archived articles
    verify        List predictions past deadline with related articles
    update-status Update prediction status (hit/miss/expired)
    analyze       Compute accuracy and bias patterns
    report        Format Telegram message from all data

Usage:
    python3 forecast.py signals [--db path] [--date 2026-03-28]
    python3 forecast.py verify [--db path]
    python3 forecast.py update-status --id 1 --status hit --verification "근거"
    python3 forecast.py analyze [--db path]
    python3 forecast.py report --signals s.json --verify v.json --analyze a.json
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forecast_db import get_connection, init_db


def _week_range(reference_date: str, weeks_ago: int = 0) -> tuple[str, str]:
    """Return (start, end) date strings for a week ending on reference_date - weeks_ago*7."""
    ref = datetime.strptime(reference_date, "%Y-%m-%d")
    end = ref - timedelta(days=7 * weeks_ago)
    start = end - timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def extract_signals(db_path: str | None = None, reference_date: str | None = None) -> dict:
    """Extract weekly signals from archived articles."""
    conn = get_connection(db_path)
    init_db(conn)

    if not reference_date:
        reference_date = datetime.now().strftime("%Y-%m-%d")

    this_start, this_end = _week_range(reference_date, 0)
    last_start, last_end = _week_range(reference_date, 1)

    # 1. Keyword surges: this week vs last week entity frequency, 2x+ increase
    this_entities = dict(conn.execute(
        """SELECT entity, COUNT(*) as cnt FROM article_entities ae
           JOIN articles a ON ae.article_id = a.id
           WHERE a.date BETWEEN ? AND ?
           GROUP BY entity""",
        (this_start, this_end),
    ).fetchall())

    last_entities = dict(conn.execute(
        """SELECT entity, COUNT(*) as cnt FROM article_entities ae
           JOIN articles a ON ae.article_id = a.id
           WHERE a.date BETWEEN ? AND ?
           GROUP BY entity""",
        (last_start, last_end),
    ).fetchall())

    keyword_surges = []
    for entity, cnt in this_entities.items():
        prev = last_entities.get(entity, 0)
        if prev == 0 and cnt >= 2:
            keyword_surges.append({"entity": entity, "this_week": cnt, "last_week": 0, "ratio": float("inf")})
        elif prev > 0 and cnt / prev >= 2.0:
            keyword_surges.append({"entity": entity, "this_week": cnt, "last_week": prev, "ratio": round(cnt / prev, 1)})
    keyword_surges.sort(key=lambda x: x["this_week"], reverse=True)

    # 2. New entities: not seen in past 4 weeks
    four_weeks_ago = (datetime.strptime(reference_date, "%Y-%m-%d") - timedelta(days=28)).strftime("%Y-%m-%d")
    old_entities = set(row[0] for row in conn.execute(
        """SELECT DISTINCT entity FROM article_entities ae
           JOIN articles a ON ae.article_id = a.id
           WHERE a.date BETWEEN ? AND ?""",
        (four_weeks_ago, last_end),
    ).fetchall())

    new_entities = sorted(set(this_entities.keys()) - old_entities)

    # 3. High coverage stories (coverage 3+)
    high_coverage = [dict(row) for row in conn.execute(
        """SELECT headline, url, source, coverage, score
           FROM articles WHERE date BETWEEN ? AND ? AND coverage >= 3
           ORDER BY coverage DESC, score DESC""",
        (this_start, this_end),
    ).fetchall()]

    # 4. Section distribution: this week vs last week
    this_sections = dict(conn.execute(
        "SELECT section, COUNT(*) FROM articles WHERE date BETWEEN ? AND ? GROUP BY section",
        (this_start, this_end),
    ).fetchall())

    last_sections = dict(conn.execute(
        "SELECT section, COUNT(*) FROM articles WHERE date BETWEEN ? AND ? GROUP BY section",
        (last_start, last_end),
    ).fetchall())

    # 5. Top articles by score
    top_articles = [dict(row) for row in conn.execute(
        """SELECT headline, url, source, section, tag, score, coverage, date
           FROM articles WHERE date BETWEEN ? AND ?
           ORDER BY score DESC LIMIT 10""",
        (this_start, this_end),
    ).fetchall()]

    conn.close()

    return {
        "reference_date": reference_date,
        "period": {"this_week": [this_start, this_end], "last_week": [last_start, last_end]},
        "keyword_surges": keyword_surges[:20],
        "new_entities": new_entities[:20],
        "high_coverage": high_coverage,
        "section_distribution": {"this_week": this_sections, "last_week": last_sections},
        "top_articles": top_articles,
    }


def main():
    ap = argparse.ArgumentParser(description="Weekly AI forecast pipeline")
    sub = ap.add_subparsers(dest="command", required=True)

    # signals
    p_sig = sub.add_parser("signals", help="Extract weekly signals")
    p_sig.add_argument("--db", default=None)
    p_sig.add_argument("--date", default=None, help="Reference date (YYYY-MM-DD, default: today)")

    args = ap.parse_args()

    if args.command == "signals":
        result = extract_signals(args.db, args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/scripts/forecast.py shared/news-brief/tests/test_forecast.py
git commit -m "feat(forecast): add signals subcommand for weekly signal extraction"
```

---

### Task 4: forecast.py verify + update-status — 예측 검증

**Files:**
- Modify: `shared/news-brief/scripts/forecast.py`
- Modify: `shared/news-brief/tests/test_forecast.py`

- [ ] **Step 1: Write failing tests**

Append to `shared/news-brief/tests/test_forecast.py`:

```python
from forecast import list_pending_verifications, update_prediction_status, save_predictions


def _seed_predictions(conn: sqlite3.Connection):
    """Create a forecast with predictions for testing."""
    conn.execute(
        "INSERT INTO forecasts (id, week, signal_json) VALUES (1, '2026-W12', '{}')"
    )
    conn.execute(
        """INSERT INTO predictions (id, forecast_id, claim, confidence, reasoning, deadline, status)
           VALUES (1, 1, 'Anthropic releases new model', 0.8, 'Claude mentions surging', '2026-03-25', 'open')"""
    )
    conn.execute(
        """INSERT INTO predictions (id, forecast_id, claim, confidence, reasoning, deadline, status)
           VALUES (2, 1, 'Google open-sources Gemini', 0.5, 'Gemma trend', '2026-04-01', 'open')"""
    )
    conn.commit()


def test_verify_lists_past_deadline(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    _seed_predictions(conn)
    conn.close()

    result = list_pending_verifications(str(db_path), today="2026-03-28")

    assert len(result) == 1  # only prediction 1 (deadline 2026-03-25)
    assert result[0]["prediction"]["id"] == 1
    assert len(result[0]["related_articles"]) > 0


def test_verify_excludes_future_deadline(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    _seed_predictions(conn)
    conn.close()

    result = list_pending_verifications(str(db_path), today="2026-03-28")

    pred_ids = [r["prediction"]["id"] for r in result]
    assert 2 not in pred_ids  # deadline 2026-04-01 is future


def test_update_status(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_predictions(conn)
    conn.close()

    update_prediction_status(str(db_path), pred_id=1, status="hit", verification="Model released on 2026-03-24")

    conn = get_connection(str(db_path))
    row = conn.execute("SELECT status, verification, verified_at FROM predictions WHERE id=1").fetchone()
    assert row["status"] == "hit"
    assert row["verification"] == "Model released on 2026-03-24"
    assert row["verified_at"] is not None
    conn.close()


def test_save_predictions(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    conn.close()

    preds = [
        {"claim": "Test claim", "confidence": 0.7, "reasoning": "Because", "deadline": "2026-04-07"},
    ]
    save_predictions(str(db_path), week="2026-W14", signal_json="{}", predictions=preds)

    conn = get_connection(str(db_path))
    row = conn.execute("SELECT * FROM predictions WHERE claim='Test claim'").fetchone()
    assert row is not None
    assert row["confidence"] == 0.7
    assert row["status"] == "open"
    forecast = conn.execute("SELECT * FROM forecasts WHERE week='2026-W14'").fetchone()
    assert forecast is not None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py::test_verify_lists_past_deadline -v`
Expected: FAIL — `ImportError: cannot import name 'list_pending_verifications'`

- [ ] **Step 3: Add verify, update-status, save_predictions to forecast.py**

Add these functions to `forecast.py` after `extract_signals`:

```python
def list_pending_verifications(db_path: str | None = None, today: str | None = None) -> list[dict]:
    """List open predictions past deadline with related articles."""
    conn = get_connection(db_path)
    init_db(conn)

    if not today:
        today = datetime.now().strftime("%Y-%m-%d")

    pending = conn.execute(
        """SELECT p.id, p.forecast_id, p.claim, p.confidence, p.reasoning,
                  p.deadline, p.status, f.created_at as forecast_created
           FROM predictions p
           JOIN forecasts f ON p.forecast_id = f.id
           WHERE p.status = 'open' AND p.deadline <= ?
           ORDER BY p.deadline""",
        (today,),
    ).fetchall()

    result = []
    for pred in pending:
        pred_dict = dict(pred)
        # Get articles from prediction creation to deadline
        created_date = pred_dict["forecast_created"][:10]  # extract date part
        articles = conn.execute(
            """SELECT headline, url, source, section, tag, score, date
               FROM articles WHERE date BETWEEN ? AND ?
               ORDER BY score DESC LIMIT 20""",
            (created_date, pred_dict["deadline"]),
        ).fetchall()
        result.append({
            "prediction": pred_dict,
            "related_articles": [dict(a) for a in articles],
        })

    conn.close()
    return result


def update_prediction_status(
    db_path: str | None, pred_id: int, status: str, verification: str
) -> None:
    """Update prediction status after LLM verification."""
    conn = get_connection(db_path)
    conn.execute(
        """UPDATE predictions
           SET status = ?, verification = ?, verified_at = datetime('now')
           WHERE id = ?""",
        (status, verification, pred_id),
    )
    conn.commit()
    conn.close()


def save_predictions(
    db_path: str | None, week: str, signal_json: str, predictions: list[dict]
) -> None:
    """Save a new forecast with its predictions."""
    conn = get_connection(db_path)
    init_db(conn)

    cursor = conn.execute(
        "INSERT INTO forecasts (week, signal_json) VALUES (?, ?)",
        (week, signal_json),
    )
    forecast_id = cursor.lastrowid

    for pred in predictions:
        conn.execute(
            """INSERT INTO predictions (forecast_id, claim, confidence, reasoning, deadline)
               VALUES (?, ?, ?, ?, ?)""",
            (forecast_id, pred["claim"], pred["confidence"], pred["reasoning"], pred["deadline"]),
        )

    conn.commit()
    conn.close()
```

Add subcommand parsers in `main()`:

```python
    # verify
    p_ver = sub.add_parser("verify", help="List predictions past deadline")
    p_ver.add_argument("--db", default=None)
    p_ver.add_argument("--date", default=None, help="Today's date override")

    # update-status
    p_upd = sub.add_parser("update-status", help="Update prediction status")
    p_upd.add_argument("--db", default=None)
    p_upd.add_argument("--id", type=int, required=True)
    p_upd.add_argument("--status", required=True, choices=["hit", "miss", "expired"])
    p_upd.add_argument("--verification", required=True)

    # ... (keep existing args parsing)

    if args.command == "signals":
        result = extract_signals(args.db, args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "verify":
        result = list_pending_verifications(args.db, args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "update-status":
        update_prediction_status(args.db, args.id, args.status, args.verification)
        print(f"Updated prediction {args.id} → {args.status}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/scripts/forecast.py shared/news-brief/tests/test_forecast.py
git commit -m "feat(forecast): add verify, update-status, save_predictions subcommands"
```

---

### Task 5: forecast.py analyze — 적중률 + 편향 분석

**Files:**
- Modify: `shared/news-brief/scripts/forecast.py`
- Modify: `shared/news-brief/tests/test_forecast.py`

- [ ] **Step 1: Write failing tests**

Append to `shared/news-brief/tests/test_forecast.py`:

```python
from forecast import compute_analysis


def _seed_verified_predictions(conn: sqlite3.Connection):
    """Create forecasts with verified predictions for analysis testing."""
    conn.execute("INSERT INTO forecasts (id, week, signal_json) VALUES (1, '2026-W10', '{}')")
    conn.execute("INSERT INTO forecasts (id, week, signal_json) VALUES (2, '2026-W11', '{}')")
    conn.execute("INSERT INTO forecasts (id, week, signal_json) VALUES (3, '2026-W12', '{}')")

    verified = [
        (1, 1, "Model release A", 0.8, "reason", "2026-03-10", "hit", "Confirmed"),
        (2, 1, "Acquisition B", 0.6, "reason", "2026-03-10", "miss", "Did not happen"),
        (3, 1, "Policy change C", 0.9, "reason", "2026-03-10", "hit", "Confirmed"),
        (4, 2, "Launch D", 0.7, "reason", "2026-03-17", "miss", "Delayed"),
        (5, 2, "Open source E", 0.5, "reason", "2026-03-17", "hit", "Confirmed"),
        (6, 3, "Partnership F", 0.4, "reason", "2026-03-24", "miss", "Nope"),
        (7, 3, "Feature G", 0.8, "reason", "2026-03-24", "hit", "Confirmed"),
        (8, 3, "Funding H", 0.6, "reason", "2026-03-24", "expired", None),
    ]
    for row in verified:
        conn.execute(
            """INSERT INTO predictions (id, forecast_id, claim, confidence, reasoning, deadline, status, verification)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
    conn.commit()


def test_analyze_overall_accuracy(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_verified_predictions(conn)
    conn.close()

    analysis = compute_analysis(str(db_path))

    # 4 hits, 3 misses, 1 expired → accuracy = 4/7 ≈ 0.571
    assert analysis["overall"]["total_judged"] == 7
    assert analysis["overall"]["hits"] == 4
    assert analysis["overall"]["misses"] == 3
    assert 0.5 < analysis["overall"]["accuracy"] < 0.6


def test_analyze_confidence_buckets(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_verified_predictions(conn)
    conn.close()

    analysis = compute_analysis(str(db_path))

    buckets = analysis["by_confidence"]
    assert len(buckets) > 0
    # High confidence (0.7-1.0) should have data
    high = [b for b in buckets if b["bucket"] == "0.7-1.0"]
    assert len(high) == 1
    assert high[0]["total"] >= 2


def test_analyze_writes_improvement_log(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_verified_predictions(conn)
    conn.close()

    compute_analysis(str(db_path), week="2026-W13")

    conn = get_connection(str(db_path))
    log = conn.execute("SELECT * FROM improvement_log WHERE week='2026-W13'").fetchone()
    assert log is not None
    assert log["accuracy"] is not None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py::test_analyze_overall_accuracy -v`
Expected: FAIL — `ImportError: cannot import name 'compute_analysis'`

- [ ] **Step 3: Add compute_analysis to forecast.py**

```python
def compute_analysis(db_path: str | None = None, week: str | None = None) -> dict:
    """Compute accuracy stats and bias patterns from verified predictions."""
    conn = get_connection(db_path)
    init_db(conn)

    if not week:
        ref = datetime.now()
        week = f"{ref.year}-W{ref.isocalendar()[1]:02d}"

    # Overall accuracy (hit + miss only, exclude expired)
    rows = conn.execute(
        "SELECT status, confidence FROM predictions WHERE status IN ('hit', 'miss')"
    ).fetchall()

    hits = sum(1 for r in rows if r["status"] == "hit")
    misses = sum(1 for r in rows if r["status"] == "miss")
    total = hits + misses
    accuracy = hits / total if total > 0 else 0.0

    # By confidence bucket
    buckets_def = [("0.0-0.3", 0.0, 0.3), ("0.3-0.5", 0.3, 0.5), ("0.5-0.7", 0.5, 0.7), ("0.7-1.0", 0.7, 1.01)]
    by_confidence = []
    for label, lo, hi in buckets_def:
        bucket_rows = [r for r in rows if lo <= r["confidence"] < hi]
        if not bucket_rows:
            continue
        bucket_hits = sum(1 for r in bucket_rows if r["status"] == "hit")
        by_confidence.append({
            "bucket": label,
            "total": len(bucket_rows),
            "hits": bucket_hits,
            "accuracy": round(bucket_hits / len(bucket_rows), 3),
        })

    # Per-week trend
    weekly = conn.execute(
        """SELECT f.week,
                  SUM(CASE WHEN p.status = 'hit' THEN 1 ELSE 0 END) as hits,
                  SUM(CASE WHEN p.status = 'miss' THEN 1 ELSE 0 END) as misses
           FROM predictions p
           JOIN forecasts f ON p.forecast_id = f.id
           WHERE p.status IN ('hit', 'miss')
           GROUP BY f.week ORDER BY f.week""",
    ).fetchall()
    weekly_trend = [dict(w) for w in weekly]

    # Calibration note: are high-confidence predictions actually more accurate?
    bias_notes = []
    if len(by_confidence) >= 2:
        high_bucket = [b for b in by_confidence if b["bucket"] == "0.7-1.0"]
        low_bucket = [b for b in by_confidence if b["bucket"] in ("0.3-0.5", "0.0-0.3")]
        if high_bucket and low_bucket:
            h_acc = high_bucket[0]["accuracy"]
            l_acc = max(b["accuracy"] for b in low_bucket)
            if h_acc <= l_acc:
                bias_notes.append("고확신 예측이 저확신보다 정확도가 낮음 — 과신 경향")

    analysis = {
        "week": week,
        "overall": {"hits": hits, "misses": misses, "total_judged": total, "accuracy": round(accuracy, 3)},
        "by_confidence": by_confidence,
        "weekly_trend": weekly_trend,
        "bias_notes": bias_notes,
    }

    # Write to improvement_log
    conn.execute(
        """INSERT INTO improvement_log (week, accuracy, bias_analysis, lesson)
           VALUES (?, ?, ?, ?)""",
        (week, round(accuracy, 3), json.dumps(bias_notes, ensure_ascii=False), ""),
    )
    conn.commit()
    conn.close()

    return analysis
```

Add `analyze` subcommand in `main()`:

```python
    # analyze
    p_ana = sub.add_parser("analyze", help="Compute accuracy and bias analysis")
    p_ana.add_argument("--db", default=None)
    p_ana.add_argument("--week", default=None)

    # ... in dispatch:
    elif args.command == "analyze":
        result = compute_analysis(args.db, args.week)
        print(json.dumps(result, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/scripts/forecast.py shared/news-brief/tests/test_forecast.py
git commit -m "feat(forecast): add analyze subcommand for accuracy and bias tracking"
```

---

### Task 6: forecast.py report — 텔레그램 포맷

**Files:**
- Modify: `shared/news-brief/scripts/forecast.py`
- Modify: `shared/news-brief/tests/test_forecast.py`

- [ ] **Step 1: Write failing test**

Append to `shared/news-brief/tests/test_forecast.py`:

```python
from forecast import format_report


def test_report_format():
    verify_data = [
        {
            "prediction": {"claim": "Model release", "confidence": 0.8, "status": "hit"},
        },
        {
            "prediction": {"claim": "Acquisition X", "confidence": 0.6, "status": "miss"},
        },
    ]
    analyze_data = {
        "overall": {"hits": 5, "misses": 3, "total_judged": 8, "accuracy": 0.625},
        "bias_notes": ["고확신 예측이 저확신보다 정확도가 낮음"],
    }
    signals_data = {
        "keyword_surges": [{"entity": "claude", "this_week": 10, "last_week": 3, "ratio": 3.3}],
        "new_entities": ["mcp", "channel"],
        "section_distribution": {
            "this_week": {"AI·테크": 15, "국제": 5},
            "last_week": {"AI·테크": 10, "국제": 7},
        },
    }
    new_predictions = [
        {"claim": "New prediction", "confidence": 0.7, "deadline": "2026-04-07", "reasoning": "Because signals"},
    ]

    report = format_report(
        week="2026-W14",
        verify_results=verify_data,
        analysis=analyze_data,
        signals=signals_data,
        new_predictions=new_predictions,
    )

    assert "2026-W14" in report
    assert "HIT" in report
    assert "MISS" in report
    assert "62.5%" in report or "62%" in report
    assert "claude" in report
    assert "New prediction" in report
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py::test_report_format -v`
Expected: FAIL — `ImportError: cannot import name 'format_report'`

- [ ] **Step 3: Add format_report to forecast.py**

```python
def format_report(
    week: str,
    verify_results: list[dict],
    analysis: dict,
    signals: dict,
    new_predictions: list[dict],
) -> str:
    """Format Telegram message for weekly forecast report."""
    lines = [f"📊 AI 주간 예측 — {week}", ""]

    # Verification section
    if verify_results:
        lines.append("── 지난 예측 검증 ──")
        status_icons = {"hit": "✅ HIT", "miss": "❌ MISS", "expired": "⏰ EXPIRED"}
        for v in verify_results:
            p = v["prediction"]
            icon = status_icons.get(p.get("status", ""), "❓")
            lines.append(f"{icon}: {p['claim']} (confidence: {p['confidence']})")
        lines.append("")

    # Overall accuracy
    overall = analysis.get("overall", {})
    if overall.get("total_judged", 0) > 0:
        pct = round(overall["accuracy"] * 100, 1)
        lines.append(f"누적 적중률: {pct}% ({overall['hits']}/{overall['total_judged']})")
        lines.append("")

    # Bias analysis
    bias_notes = analysis.get("bias_notes", [])
    if bias_notes:
        lines.append("── 자가분석 ──")
        for note in bias_notes:
            lines.append(f"편향: {note}")
        lines.append("")

    # Signals
    lines.append("── 이번 주 시그널 ──")
    for surge in signals.get("keyword_surges", [])[:5]:
        ratio_str = f"{surge['ratio']}배" if surge["ratio"] != float("inf") else "신규"
        lines.append(f"• \"{surge['entity']}\" 언급 {ratio_str} 급증 (전주 대비)")

    new_ents = signals.get("new_entities", [])[:5]
    if new_ents:
        lines.append(f"• 신규 엔티티: {', '.join(new_ents)}")

    dist = signals.get("section_distribution", {})
    this_w = dist.get("this_week", {})
    last_w = dist.get("last_week", {})
    total_this = sum(this_w.values()) or 1
    total_last = sum(last_w.values()) or 1
    for section in this_w:
        pct_this = round(this_w[section] / total_this * 100)
        pct_last = round(last_w.get(section, 0) / total_last * 100)
        if abs(pct_this - pct_last) >= 5:
            lines.append(f"• {section} 섹션 비중 {pct_last}% → {pct_this}%")
    lines.append("")

    # New predictions
    if new_predictions:
        lines.append("── 새 예측 ──")
        for i, pred in enumerate(new_predictions, 1):
            lines.append(f"{i}. [{pred['confidence']}] {pred['claim']}")
            lines.append(f"   → 근거: {pred['reasoning']}")
            lines.append(f"   → 판정 시한: {pred['deadline']}")
        lines.append("")

    return "\n".join(lines).strip()
```

Add `report` subcommand in `main()`:

```python
    # report
    p_rep = sub.add_parser("report", help="Format Telegram report")
    p_rep.add_argument("--signals", required=True, help="Signals JSON file")
    p_rep.add_argument("--verify", default=None, help="Verify results JSON file")
    p_rep.add_argument("--analyze", default=None, help="Analysis JSON file")
    p_rep.add_argument("--predictions", default=None, help="New predictions JSON file")
    p_rep.add_argument("--week", required=True)

    # ... in dispatch:
    elif args.command == "report":
        def _load_json(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        signals = _load_json(args.signals)
        verify = _load_json(args.verify) if args.verify else []
        analyze = _load_json(args.analyze) if args.analyze else {}
        preds = _load_json(args.predictions) if args.predictions else []
        report = format_report(args.week, verify, analyze, signals, preds)
        print(report)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/scripts/forecast.py shared/news-brief/tests/test_forecast.py
git commit -m "feat(forecast): add report subcommand for Telegram formatting"
```

---

### Task 7: cron.json + SKILL.md 업데이트

**Files:**
- Modify: `shared/news-brief/cron.json`
- Modify: `shared/news-brief/SKILL.md`

- [ ] **Step 1: Update cron.json — weekly-forecast 크론 추가**

`cron.json`에 추가:

```json
{
    "name": "weekly-forecast",
    "schedule": "0 9 * * 1",
    "target": "weekly-forecast",
    "reason": "cron: weekly-forecast",
    "instructions": "news-brief 스킬의 '주간 AI 예측' 섹션을 따르세요.",
    "recipients": ["daye"]
}
```

- [ ] **Step 2: Update daily-newspaper instructions — archive 단계 추가**

`cron.json`의 `daily-newspaper` 항목 instructions를 수정:

```
"instructions": "news-brief 스킬의 'Quick Usage' 절차를 따르세요. enrich 단계를 절대 생략하지 마세요 — 영어 헤드라인이 남으면 안 됩니다. 완성된 HTML을 thread에 첨부하세요. 마지막에 python3 {baseDir}/scripts/archive.py --input /tmp/enriched.json 을 실행하여 DB에 아카이브하세요."
```

- [ ] **Step 3: Update SKILL.md — forecast 섹션 추가**

SKILL.md 끝에 추가:

```markdown
### 주간 AI 예측

뉴스페이퍼 아카이브 데이터 기반 AI 산업 주간 예측. 자가개선 루프 포함.

- DB: `~/.local/share/news-brief/forecast.db`
- 크론: 매주 월요일 09:00 KST

#### 아카이브 (매일 자동)

뉴스페이퍼 생성 후 enriched JSON을 DB에 적재:

```bash
python3 {baseDir}/scripts/archive.py --input /tmp/enriched.json
```

#### 주간 예측 절차 (크론 에이전트용)

1. 검증 데이터 추출:
   ```bash
   python3 {baseDir}/scripts/forecast.py verify > /tmp/forecast_verify.json
   ```
2. 각 prediction을 검토하고 판정:
   ```bash
   python3 {baseDir}/scripts/forecast.py update-status --id <id> --status hit|miss|expired --verification "판정 근거"
   ```
3. 분석:
   ```bash
   python3 {baseDir}/scripts/forecast.py analyze --week <YYYY-Wnn> > /tmp/forecast_analyze.json
   ```
4. 시그널 추출:
   ```bash
   python3 {baseDir}/scripts/forecast.py signals > /tmp/forecast_signals.json
   ```
5. improvement_log 최근 3건 확인:
   ```bash
   python3 {baseDir}/scripts/forecast.py analyze --db ~/.local/share/news-brief/forecast.db
   ```
   출력의 `bias_notes`와 `weekly_trend`를 참고하여 과거 편향을 인지
6. 시그널 + 과거 교훈을 기반으로 예측 3~5개 생성 (claim, confidence 0.0-1.0, reasoning, deadline)
7. 예측 저장 (LLM이 forecast.py에 직접 저장하거나, save_predictions 함수 사용)
8. 리포트 포맷팅:
   ```bash
   python3 {baseDir}/scripts/forecast.py report \
     --week <YYYY-Wnn> \
     --signals /tmp/forecast_signals.json \
     --verify /tmp/forecast_verify.json \
     --analyze /tmp/forecast_analyze.json \
     --predictions /tmp/forecast_predictions.json
   ```
9. 결과를 텔레그램으로 전송
```

- [ ] **Step 4: Verify cron.json is valid JSON**

Run: `python3 -c "import json; json.load(open('shared/news-brief/cron.json'))"`
Expected: No error

- [ ] **Step 5: Commit**

```bash
git add shared/news-brief/cron.json shared/news-brief/SKILL.md
git commit -m "feat(forecast): add weekly-forecast cron + SKILL.md forecast section"
```

---

### Task 8: 통합 테스트 + 전체 검증

**Files:**
- Modify: `shared/news-brief/tests/test_forecast.py`

- [ ] **Step 1: Write integration test — full pipeline flow**

Append to `shared/news-brief/tests/test_forecast.py`:

```python
def test_full_pipeline_flow(tmp_path: Path):
    """Integration test: archive → signals → save predictions → verify → update → analyze → report."""
    db_path = str(tmp_path / "test.db")

    # 1. Archive: simulate enriched newspaper
    json_path = tmp_path / "enriched.json"
    json_path.write_text(json.dumps(SAMPLE_ENRICHED, ensure_ascii=False))
    from archive import archive_newspaper
    count = archive_newspaper(str(json_path), db_path)
    assert count == 3

    # 2. Signals
    signals = extract_signals(db_path, reference_date="2026-03-28")
    assert "keyword_surges" in signals
    assert "top_articles" in signals

    # 3. Save predictions
    preds = [
        {"claim": "Test prediction A", "confidence": 0.7, "reasoning": "Signal based", "deadline": "2026-03-27"},
        {"claim": "Test prediction B", "confidence": 0.5, "reasoning": "Weak signal", "deadline": "2026-04-05"},
    ]
    save_predictions(db_path, week="2026-W13", signal_json=json.dumps(signals), predictions=preds)

    # 4. Verify (only A should appear — deadline passed)
    pending = list_pending_verifications(db_path, today="2026-03-28")
    assert len(pending) == 1
    assert pending[0]["prediction"]["claim"] == "Test prediction A"

    # 5. Update status
    pred_id = pending[0]["prediction"]["id"]
    update_prediction_status(db_path, pred_id, "hit", "Confirmed by articles")

    # 6. Analyze
    analysis = compute_analysis(db_path, week="2026-W13")
    assert analysis["overall"]["hits"] == 1
    assert analysis["overall"]["total_judged"] == 1

    # 7. Report
    report = format_report(
        week="2026-W13",
        verify_results=[{"prediction": {"claim": "Test A", "confidence": 0.7, "status": "hit"}}],
        analysis=analysis,
        signals=signals,
        new_predictions=[preds[1]],
    )
    assert "2026-W13" in report
    assert "HIT" in report
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m pytest shared/news-brief/tests/test_forecast.py shared/news-brief/tests/test_forecast_db.py shared/news-brief/tests/test_archive.py -v`
Expected: PASS (all 14+ tests)

- [ ] **Step 3: Run tsc/lint if applicable**

Run: `cd /Users/dayejeong/git_workplace/daye-agent-toolkit && python3 -m py_compile shared/news-brief/scripts/forecast_db.py && python3 -m py_compile shared/news-brief/scripts/archive.py && python3 -m py_compile shared/news-brief/scripts/forecast.py && echo "All OK"`
Expected: `All OK`

- [ ] **Step 4: Commit integration test**

```bash
git add shared/news-brief/tests/test_forecast.py
git commit -m "test(forecast): add integration test for full pipeline flow"
```
