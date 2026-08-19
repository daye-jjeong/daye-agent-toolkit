import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from trend import SPARK_DAYS, material_trend

# 망령의 영혼석 실측(2026-08-02 ~ 08-15). 8/12에 급등했다.
REAL = [
    {"time": "2026-08-01T21:00:00Z", "low": 54, "high": 74, "close": 68},
    {"time": "2026-08-02T21:00:00Z", "low": 54, "high": 81, "close": 74},
    {"time": "2026-08-03T21:00:00Z", "low": 55, "high": 77, "close": 72},
    {"time": "2026-08-04T21:00:00Z", "low": 55, "high": 72, "close": 66},
    {"time": "2026-08-05T21:00:00Z", "low": 54, "high": 71, "close": 61},
    {"time": "2026-08-06T21:00:00Z", "low": 53, "high": 68, "close": 63},
    {"time": "2026-08-07T21:00:00Z", "low": 51, "high": 70, "close": 64},
    {"time": "2026-08-08T21:00:00Z", "low": 50, "high": 72, "close": 60},
    {"time": "2026-08-09T21:00:00Z", "low": 51, "high": 72, "close": 64},
    {"time": "2026-08-10T21:00:00Z", "low": 52, "high": 67, "close": 67},
    {"time": "2026-08-12T21:00:00Z", "low": 59, "high": 100, "close": 96},
    {"time": "2026-08-13T21:00:00Z", "low": 69, "high": 108, "close": 82},
    {"time": "2026-08-14T21:00:00Z", "low": 74, "high": 104, "close": 92},
    {"time": "2026-08-15T21:00:00Z", "low": 80, "high": 104, "close": 95},
]


def test_today_range_comes_from_the_last_candle():
    t = material_trend(REAL, now_price=100)
    assert t["today_low"] == 80 and t["today_high"] == 104


def test_current_price_is_placed_in_the_window():
    """지금 100원은 14일 범위(50~108)의 위쪽이다 — 사도 되는지가 여기서 갈린다."""
    t = material_trend(REAL, now_price=100)
    assert t["low"] == 50 and t["high"] == 108
    assert t["verdict"] == "expensive"


def test_a_price_near_the_bottom_reads_cheap():
    t = material_trend(REAL, now_price=52)
    assert t["verdict"] == "cheap"


def test_a_middling_price_says_nothing():
    """종가 정렬: 60 61 63 64 64 66 67 68 72 74 82 92 95 96 — 68은 딱 가운데."""
    t = material_trend(REAL, now_price=68)
    assert t["verdict"] == "middle"


def test_the_verdict_uses_closes_not_the_low_high_span():
    """저가~고가로 재면 50~139이라 111이 '가운데'가 된다. 종가로는 최고가다."""
    t = material_trend(REAL, now_price=111)
    assert t["low"] == 50 and t["high"] == 108   # 표시용 범위는 그대로
    assert t["verdict"] == "expensive"


def test_a_flat_material_is_called_out():
    """특급 목재는 14일 내내 146이다 — 여기서 '비싼 편'이 뜨면 거짓말이다."""
    flat = [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 146, "high": 146, "close": 146}
            for d in range(1, 15)]
    t = material_trend(flat, now_price=146)
    assert t["verdict"] == "flat"


def test_only_the_last_two_weeks_are_used():
    old = [{"time": f"2026-06-{d:02d}T21:00:00Z", "low": 1, "high": 2, "close": 1}
           for d in range(1, 20)]
    t = material_trend(old + REAL, now_price=100)
    assert len(t["closes"]) == SPARK_DAYS
    assert t["low"] == 50  # 6월의 1원이 범위를 오염시키지 않는다


def test_no_candles_yet():
    t = material_trend([], now_price=100)
    assert t is None


def test_a_single_candle_still_renders():
    t = material_trend(REAL[-1:], now_price=100)
    assert t["closes"] == [95]
    assert t["verdict"] in ("cheap", "middle", "expensive", "flat")
