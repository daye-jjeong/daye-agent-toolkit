"""Tests for forecast.py subcommands."""
import json
import sqlite3
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from forecast_db import get_connection, init_db
from forecast import extract_signals, list_pending_verifications, update_prediction_status, save_predictions, compute_analysis, format_report


def _seed_articles(conn: sqlite3.Connection):
    """Seed 2 weeks of test data."""
    this_week = [
        ("2026-03-23", "Anthropic Claude 신모델 발표", "https://a.com/1", "AI·테크", "Models", 8.0, 3),
        ("2026-03-24", "Claude MCP 업데이트", "https://a.com/2", "AI·테크", "Models", 7.5, 2),
        ("2026-03-25", "Claude Code 새 기능", "https://a.com/3", "AI·테크", "Tools", 6.0, 1),
        ("2026-03-26", "OpenAI GPT-5 루머", "https://a.com/4", "AI·테크", "Models", 5.0, 1),
        ("2026-03-27", "EU AI 규제 강화", "https://a.com/5", "국제", "국제", 4.0, 2),
    ]
    last_week = [
        ("2026-03-16", "Google Gemma 오픈소스", "https://b.com/1", "AI·테크", "Models", 7.0, 2),
        ("2026-03-17", "Meta LLaMA 업데이트", "https://b.com/2", "AI·테크", "Models", 6.0, 1),
    ]

    for row in this_week + last_week:
        cursor = conn.execute(
            "INSERT INTO articles (date, title, headline, url, section, tag, score, coverage) VALUES (?,?,?,?,?,?,?,?)",
            (row[0], row[1], row[1], row[2], row[3], row[4], row[5], row[6]),
        )
        aid = cursor.lastrowid
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
    assert "claude" in surges


def test_signals_new_entities(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    new_ents = set(signals["new_entities"])
    assert "mcp" in new_ents


def test_signals_high_coverage(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    conn.close()

    signals = extract_signals(str(db_path), reference_date="2026-03-28")

    coverage_urls = [s["url"] for s in signals["high_coverage"]]
    assert "https://a.com/1" in coverage_urls


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
    assert top[0]["score"] >= top[-1]["score"]


def _seed_predictions(conn):
    """Create a forecast with predictions for testing."""
    conn.execute(
        "INSERT INTO forecasts (id, week, created_at, signal_json) VALUES (1, '2026-W12', '2026-03-22 00:00:00', '{}')"
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


def test_verify_lists_past_deadline(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    _seed_predictions(conn)
    conn.close()

    result = list_pending_verifications(str(db_path), today="2026-03-28")

    assert len(result) == 1
    assert result[0]["prediction"]["id"] == 1
    assert len(result[0]["related_articles"]) > 0


def test_verify_excludes_future_deadline(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_articles(conn)
    _seed_predictions(conn)
    conn.close()

    result = list_pending_verifications(str(db_path), today="2026-03-28")

    pred_ids = [r["prediction"]["id"] for r in result]
    assert 2 not in pred_ids


def test_update_status(tmp_path):
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


def test_save_predictions(tmp_path):
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


def _seed_verified_predictions(conn):
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


def test_analyze_overall_accuracy(tmp_path):
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


def test_analyze_confidence_buckets(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _seed_verified_predictions(conn)
    conn.close()

    analysis = compute_analysis(str(db_path))

    buckets = analysis["by_confidence"]
    assert len(buckets) > 0
    high = [b for b in buckets if b["bucket"] == "0.7-1.0"]
    assert len(high) == 1
    assert high[0]["total"] >= 2


def test_analyze_writes_improvement_log(tmp_path):
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
    assert "62" in report  # 62.5% accuracy
    assert "claude" in report
    assert "New prediction" in report
