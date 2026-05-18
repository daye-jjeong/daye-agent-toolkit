"""record_sessions → sessions.cost_usd 영속화 회귀 테스트.

검증 경로: tokens.by_model → _prepare_fields(cost 계산) → upsert_session → DB.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from activity_writer import record_sessions  # noqa: E402
from pricing import estimate_cost  # noqa: E402


def _by_date_with_models(by_model: dict) -> dict:
    """parse_transcript_by_date 출력과 동일 구조의 단일 날짜 데이터."""
    return {
        "2026-05-15": {
            "files": ["a.py"],
            "commands": ["git status"],
            "errors": [],
            "topic": "cost tracker 테스트",
            "user_messages": [],
            "agent_messages": [],
            "duration_min": 10,
            "end_time": "14:30",
            "start_kst": None,
            "has_commits": False,
            "tokens": {
                "input": sum(t["input"] for t in by_model.values()),
                "output": sum(t["output"] for t in by_model.values()),
                "cache_read": sum(t["cache_read"] for t in by_model.values()),
                "cache_create": sum(t["cache_create"] for t in by_model.values()),
                "api_calls": 3,
                "by_model": by_model,
            },
        }
    }


def test_cost_usd_persisted_for_opus_session(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFE_DASHBOARD_DB", str(tmp_path / "test.db"))
    by_model = {
        "claude-opus-4-7": {
            "input": 50_000, "output": 8_000,
            "cache_read": 400_000, "cache_create": 30_000,
        }
    }
    record_sessions("cc", "sess-opus", _by_date_with_models(by_model), "myrepo", "main")

    from db import get_conn
    conn = get_conn()
    row = conn.execute(
        "SELECT cost_usd, token_total FROM sessions WHERE session_id='sess-opus'"
    ).fetchone()
    assert row is not None
    expected = estimate_cost("claude-opus-4-7", 50_000, 8_000, 400_000, 30_000)
    assert expected > 0
    assert abs(row["cost_usd"] - expected) < 1e-9
    assert row["token_total"] == 488_000  # 50k+8k+400k+30k


def test_cost_usd_sums_mixed_models(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFE_DASHBOARD_DB", str(tmp_path / "test.db"))
    by_model = {
        "claude-opus-4-7": {"input": 10_000, "output": 2_000, "cache_read": 0, "cache_create": 0},
        "claude-haiku-4-5-20251001": {"input": 100_000, "output": 5_000, "cache_read": 0, "cache_create": 0},
    }
    record_sessions("cc", "sess-mixed", _by_date_with_models(by_model), "myrepo", "main")

    from db import get_conn
    conn = get_conn()
    row = conn.execute(
        "SELECT cost_usd FROM sessions WHERE session_id='sess-mixed'"
    ).fetchone()
    expected = (
        estimate_cost("claude-opus-4-7", 10_000, 2_000)
        + estimate_cost("claude-haiku-4-5-20251001", 100_000, 5_000)
    )
    assert abs(row["cost_usd"] - expected) < 1e-9


def test_cost_usd_updated_on_re_record(tmp_path, monkeypatch):
    """PreCompact→SessionEnd 재기록 시 누적된 최신 비용으로 갱신 (ON CONFLICT)."""
    monkeypatch.setenv("LIFE_DASHBOARD_DB", str(tmp_path / "test.db"))
    first = {"claude-haiku-4-5-20251001": {"input": 10_000, "output": 1_000, "cache_read": 0, "cache_create": 0}}
    record_sessions("cc", "sess-re", _by_date_with_models(first), "repo", "main")

    second = {"claude-haiku-4-5-20251001": {"input": 90_000, "output": 9_000, "cache_read": 0, "cache_create": 0}}
    record_sessions("cc", "sess-re", _by_date_with_models(second), "repo", "main")

    from db import get_conn
    row = get_conn().execute(
        "SELECT cost_usd FROM sessions WHERE session_id='sess-re'"
    ).fetchone()
    expected = estimate_cost("claude-haiku-4-5-20251001", 90_000, 9_000)
    assert abs(row["cost_usd"] - expected) < 1e-9


def test_cost_usd_zero_when_no_by_model(tmp_path, monkeypatch):
    """구 데이터(by_model 없음) → cost_usd 0, 크래시 없음."""
    monkeypatch.setenv("LIFE_DASHBOARD_DB", str(tmp_path / "test.db"))
    data = _by_date_with_models({})
    data["2026-05-15"]["tokens"]["input"] = 1234  # token_total은 살아있어야
    record_sessions("cc", "sess-legacy", data, "myrepo", "main")

    from db import get_conn
    conn = get_conn()
    row = conn.execute(
        "SELECT cost_usd, token_total FROM sessions WHERE session_id='sess-legacy'"
    ).fetchone()
    assert row["cost_usd"] == 0
    assert row["token_total"] == 1234
