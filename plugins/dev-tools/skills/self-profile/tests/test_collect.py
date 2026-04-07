#!/usr/bin/env python3
"""Tests for self-profile collect.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _insert_session(conn, *, source="cc", session_id="s1", repo="test-repo",
                    tag="코딩", start_at="2026-03-01 10:00", end_at="2026-03-01 10:30",
                    date="2026-03-01", duration_min=30):
    conn.execute("""
        INSERT INTO sessions (source, session_id, date, repo, tag, start_at, end_at, duration_min)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (source, session_id, date, repo, tag, start_at, end_at, duration_min))
    conn.commit()


def _insert_signal(conn, *, session_id="s1", date="2026-03-01",
                   signal_type="mistake", content="test signal", repo="test-repo",
                   reasoning=None):
    conn.execute("""
        INSERT INTO signals (session_id, date, signal_type, content, reasoning, repo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, date, signal_type, content, reasoning, repo))
    conn.commit()


class TestJsonSchema:
    """출력 JSON이 설계 스키마를 따르는지 검증."""

    def test_top_level_keys(self, collect_with_db):
        result = collect_with_db()
        assert set(result.keys()) == {"period", "sessions", "behavioral_signals",
                                       "corrections", "daily_trend"}

    def test_sessions_has_dual_metrics(self, collect_with_db):
        """by_weekday, by_hour, by_tag은 count + total_min 둘 다 있어야 한다."""
        _insert_session(collect_with_db.conn, session_id="s1",
                        start_at="2026-03-01 10:00", duration_min=30)
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        # 2026-03-01 = Sunday
        sun = result["sessions"]["by_weekday"].get("Sun")
        assert sun is not None
        assert "count" in sun and "total_min" in sun

    def test_by_source_breakdown(self, collect_with_db):
        """source별 breakdown이 있어야 한다."""
        _insert_session(collect_with_db.conn, session_id="s1", source="cc")
        _insert_session(collect_with_db.conn, session_id="s2", source="codex",
                        date="2026-03-01")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        assert "cc" in result["sessions"]["by_source"]
        assert "codex" in result["sessions"]["by_source"]


class TestNullHandling:
    """NULL/빈 데이터 처리."""

    def test_empty_tag_becomes_기타(self, collect_with_db):
        _insert_session(collect_with_db.conn, session_id="s1", tag="")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        assert "기타" in result["sessions"]["by_tag"]

    def test_null_tag_becomes_기타(self, collect_with_db):
        _insert_session(collect_with_db.conn, session_id="s1", tag=None)
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        assert "기타" in result["sessions"]["by_tag"]


class TestDailyTrend:
    """daily_trend의 0-fill 검증."""

    def test_zero_fill_inactive_days(self, collect_with_db):
        """활동 없는 날도 daily_trend에 포함되어야 한다."""
        _insert_session(collect_with_db.conn, session_id="s1",
                        start_at="2026-03-01 10:00")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-03")
        dates = [d["date"] for d in result["daily_trend"]]
        assert "2026-03-02" in dates
        inactive = next(d for d in result["daily_trend"] if d["date"] == "2026-03-02")
        assert inactive["sessions"] == 0
        assert inactive["hours"] == 0.0


class TestBehavioralSignals:
    """행동 신호 상위 N개 제한."""

    def test_top_signals_limited_to_20(self, collect_with_db):
        """각 유형별 상위 20개만 반환."""
        for i in range(25):
            _insert_signal(collect_with_db.conn, session_id=f"s{i}",
                           signal_type="mistake", content=f"mistake {i}")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        assert len(result["behavioral_signals"]["top_mistakes"]) <= 20

    def test_repeat_signals_aggregated(self, collect_with_db):
        """반복 신호가 count와 함께 집계."""
        for i in range(3):
            _insert_signal(collect_with_db.conn, session_id=f"s{i}",
                           signal_type="mistake", content="같은 실수")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        repeats = result["behavioral_signals"]["repeat_signals"]
        assert any(r["content"] == "같은 실수" and r["count"] == 3 for r in repeats)

    def test_reasoning_field_included(self, collect_with_db):
        """v2 signals의 reasoning 필드가 포함되어야 한다."""
        _insert_signal(collect_with_db.conn, session_id="s1",
                       signal_type="decision",
                       content="A를 선택",
                       reasoning="B보다 간단해서")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        decisions = result["behavioral_signals"]["top_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["reasoning"] == "B보다 간단해서"


class TestDecisionProfile:
    """의사결정 성향 프로파일."""

    def test_decision_profile_exists(self, collect_with_db):
        """decision_profile이 behavioral_signals에 포함."""
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        dp = result["behavioral_signals"]["decision_profile"]
        assert "total" in dp
        assert "by_category" in dp
        assert "tradeoff_ratio" in dp

    def test_categorization(self, collect_with_db):
        """결정이 카테고리별로 분류."""
        _insert_signal(collect_with_db.conn, session_id="s1",
                       signal_type="decision",
                       content="SQLite를 선택 — PostgreSQL 대신 임베디드가 배포 간편해서")
        _insert_signal(collect_with_db.conn, session_id="s2",
                       signal_type="decision",
                       content="모듈을 분리 — 단일 파일이 커지면 테스트가 어려워서")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        dp = result["behavioral_signals"]["decision_profile"]
        assert dp["total"] == 2
        assert "기술 선택" in dp["by_category"]
        assert "아키텍처" in dp["by_category"]

    def test_tradeoff_detection(self, collect_with_db):
        """트레이드오프 비율 계산."""
        _insert_signal(collect_with_db.conn, session_id="s1",
                       signal_type="decision",
                       content="A 대신 B를 사용하기로 — 성능이 더 좋아서")
        _insert_signal(collect_with_db.conn, session_id="s2",
                       signal_type="decision",
                       content="새 기능을 추가")
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        dp = result["behavioral_signals"]["decision_profile"]
        assert dp["tradeoff_ratio"] == 0.5  # 1 out of 2

    def test_empty_decisions(self, collect_with_db):
        """결정 없을 때 빈 프로파일."""
        result = collect_with_db(period_start="2026-03-01", period_end="2026-03-01")
        dp = result["behavioral_signals"]["decision_profile"]
        assert dp["total"] == 0
        assert dp["tradeoff_ratio"] == 0.0
