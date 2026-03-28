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

    # 1. Keyword surges
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

    # 2. New entities (not seen in past 4 weeks)
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

    # 4. Section distribution
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


def list_pending_verifications(db_path=None, today=None):
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
        created_date = pred_dict["forecast_created"][:10]
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


def update_prediction_status(db_path, pred_id, status, verification):
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


def save_predictions(db_path, week, signal_json, predictions):
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


def compute_analysis(db_path=None, week=None):
    """Compute accuracy stats and bias patterns from verified predictions."""
    conn = get_connection(db_path)
    init_db(conn)

    if not week:
        ref = datetime.now()
        week = f"{ref.year}-W{ref.isocalendar()[1]:02d}"

    rows = conn.execute(
        "SELECT status, confidence FROM predictions WHERE status IN ('hit', 'miss')"
    ).fetchall()

    hits = sum(1 for r in rows if r["status"] == "hit")
    misses = sum(1 for r in rows if r["status"] == "miss")
    total = hits + misses
    accuracy = hits / total if total > 0 else 0.0

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

    conn.execute(
        """INSERT INTO improvement_log (week, accuracy, bias_analysis, lesson)
           VALUES (?, ?, ?, ?)""",
        (week, round(accuracy, 3), json.dumps(bias_notes, ensure_ascii=False), ""),
    )
    conn.commit()
    conn.close()

    return analysis


def format_report(week, verify_results, analysis, signals, new_predictions):
    """Format Telegram message for weekly forecast report."""
    lines = [f"📊 AI 주간 예측 — {week}", ""]

    if verify_results:
        lines.append("── 지난 예측 검증 ──")
        status_icons = {"hit": "✅ HIT", "miss": "❌ MISS", "expired": "⏰ EXPIRED"}
        for v in verify_results:
            p = v["prediction"]
            icon = status_icons.get(p.get("status", ""), "❓")
            lines.append(f"{icon}: {p['claim']} (confidence: {p['confidence']})")
        lines.append("")

    overall = analysis.get("overall", {})
    if overall.get("total_judged", 0) > 0:
        pct = round(overall["accuracy"] * 100, 1)
        lines.append(f"누적 적중률: {pct}% ({overall['hits']}/{overall['total_judged']})")
        lines.append("")

    bias_notes = analysis.get("bias_notes", [])
    if bias_notes:
        lines.append("── 자가분석 ──")
        for note in bias_notes:
            lines.append(f"편향: {note}")
        lines.append("")

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

    if new_predictions:
        lines.append("── 새 예측 ──")
        for i, pred in enumerate(new_predictions, 1):
            lines.append(f"{i}. [{pred['confidence']}] {pred['claim']}")
            lines.append(f"   → 근거: {pred['reasoning']}")
            lines.append(f"   → 판정 시한: {pred['deadline']}")
        lines.append("")

    return "\n".join(lines).strip()


def main():
    ap = argparse.ArgumentParser(description="Weekly AI forecast pipeline")
    sub = ap.add_subparsers(dest="command", required=True)

    p_sig = sub.add_parser("signals", help="Extract weekly signals")
    p_sig.add_argument("--db", default=None)
    p_sig.add_argument("--date", default=None, help="Reference date (YYYY-MM-DD)")

    p_ver = sub.add_parser("verify", help="List predictions past deadline")
    p_ver.add_argument("--db", default=None)
    p_ver.add_argument("--date", default=None, help="Today's date override")

    p_upd = sub.add_parser("update-status", help="Update prediction status")
    p_upd.add_argument("--db", default=None)
    p_upd.add_argument("--id", type=int, required=True)
    p_upd.add_argument("--status", required=True, choices=["hit", "miss", "expired"])
    p_upd.add_argument("--verification", required=True)

    p_ana = sub.add_parser("analyze", help="Compute accuracy and bias analysis")
    p_ana.add_argument("--db", default=None)
    p_ana.add_argument("--week", default=None)

    p_rep = sub.add_parser("report", help="Format Telegram report")
    p_rep.add_argument("--signals", required=True, help="Signals JSON file")
    p_rep.add_argument("--verify", default=None, help="Verify results JSON file")
    p_rep.add_argument("--analyze", default=None, help="Analysis JSON file")
    p_rep.add_argument("--predictions", default=None, help="New predictions JSON file")
    p_rep.add_argument("--week", required=True)

    args = ap.parse_args()

    if args.command == "signals":
        result = extract_signals(args.db, args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif args.command == "verify":
        result = list_pending_verifications(args.db, args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif args.command == "update-status":
        update_prediction_status(args.db, args.id, args.status, args.verification)
        print(f"Updated prediction {args.id} → {args.status}")
    elif args.command == "analyze":
        result = compute_analysis(args.db, args.week)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
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


if __name__ == "__main__":
    main()
