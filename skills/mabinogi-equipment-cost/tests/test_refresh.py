import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from refresh import CollectorStatus, RefreshState


def test_starts_idle():
    st = RefreshState()
    assert st.snapshot()["state"] == "idle"
    assert st.snapshot()["fetched"] == 0


def test_running_reports_progress():
    st = RefreshState()
    st.start(expected=1000)
    st.progress(500)
    snap = st.snapshot()
    assert snap["state"] == "running"
    assert snap["fetched"] == 500
    assert snap["expected"] == 1000
    assert snap["percent"] == 50


def test_percent_is_capped_when_it_overshoots():
    """직전 건수는 추정치다. 넘어도 100%를 넘겨 그리지 않는다."""
    st = RefreshState()
    st.start(expected=100)
    st.progress(250)
    assert st.snapshot()["percent"] == 100


def test_percent_is_none_without_an_estimate():
    """추정할 근거가 없으면 비율을 지어내지 않는다."""
    st = RefreshState()
    st.start(expected=0)
    st.progress(300)
    snap = st.snapshot()
    assert snap["percent"] is None
    assert snap["fetched"] == 300


def test_done_carries_the_snapshot_time():
    st = RefreshState()
    st.start(expected=10)
    st.progress(10)
    st.done(as_of="2026-08-15T06:14:00Z", count=10)
    snap = st.snapshot()
    assert snap["state"] == "done"
    assert snap["as_of"] == "2026-08-15T06:14:00Z"
    assert snap["percent"] == 100


def test_failure_keeps_the_reason():
    """조용히 idle로 돌아가면 왜 값이 그대로인지 알 수 없다."""
    st = RefreshState()
    st.start(expected=10)
    st.fail("HTTP Error 403")
    snap = st.snapshot()
    assert snap["state"] == "error"
    assert "403" in snap["error"]


def test_starting_again_clears_the_previous_error():
    st = RefreshState()
    st.start(expected=10)
    st.fail("boom")
    st.start(expected=10)
    snap = st.snapshot()
    assert snap["state"] == "running"
    assert snap["error"] is None


def test_second_start_is_refused_while_running():
    """두 번 눌러도 수집은 하나만 돈다."""
    st = RefreshState()
    assert st.start(expected=10) is True
    assert st.start(expected=10) is False
    st.done(as_of="x", count=10)
    assert st.start(expected=10) is True


# --- 주기 수집기의 건강 상태 ----------------------------------------------------
#
# 공개판 방문자는 서버 콘솔을 못 본다. 실패가 화면까지 올라와야 한다.


def test_collector_starts_healthy():
    c = CollectorStatus()
    assert c.snapshot()["error"] is None
    assert c.snapshot()["failures"] == 0


def test_collector_keeps_the_reason_and_counts_the_streak():
    c = CollectorStatus()
    c.failed("URLError: timed out")
    c.failed("URLError: timed out")
    snap = c.snapshot()
    assert "timed out" in snap["error"]
    assert snap["failures"] == 2


def test_one_success_clears_the_streak():
    """한 번 성공하면 화면에서 경고가 사라져야 한다."""
    c = CollectorStatus()
    c.failed("boom")
    c.ok()
    snap = c.snapshot()
    assert snap["error"] is None
    assert snap["failures"] == 0
