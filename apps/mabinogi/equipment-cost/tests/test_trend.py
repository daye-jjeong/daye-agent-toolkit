import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from trend import (
    CHART_DAYS,
    SPARK_DAYS,
    candle_day,
    material_chart,
    material_trend,
)

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


# --- 30일 범위 띠 차트 ---------------------------------------------------------
#
# 망령의 영혼석 실측 35일(2026-07-14T21:00Z ~ 08-18T21:00Z). 마지막 30개가
# 차트에 들어간다 — KST 7/20 ~ 8/19. 8/12 버킷(KST)은 원본에 아예 없다.

REAL30 = [
    {"time": "2026-07-14T21:00:00Z", "open": 91, "high": 101, "low": 70, "close": 83},
    {"time": "2026-07-15T21:00:00Z", "open": 81, "high": 93, "low": 72, "close": 74},
    {"time": "2026-07-16T21:00:00Z", "open": 74, "high": 122, "low": 70, "close": 87},
    {"time": "2026-07-17T21:00:00Z", "open": 96, "high": 102, "low": 71, "close": 89},
    {"time": "2026-07-18T21:00:00Z", "open": 85, "high": 107, "low": 71, "close": 89},
    {"time": "2026-07-19T21:00:00Z", "open": 85, "high": 134, "low": 71, "close": 92},
    {"time": "2026-07-20T21:00:00Z", "open": 87, "high": 102, "low": 77, "close": 96},
    {"time": "2026-07-21T21:00:00Z", "open": 86, "high": 99, "low": 75, "close": 85},
    {"time": "2026-07-22T21:00:00Z", "open": 85, "high": 102, "low": 74, "close": 88},
    {"time": "2026-07-23T21:00:00Z", "open": 88, "high": 100, "low": 73, "close": 91},
    {"time": "2026-07-24T21:00:00Z", "open": 91, "high": 95, "low": 72, "close": 86},
    {"time": "2026-07-25T21:00:00Z", "open": 86, "high": 93, "low": 70, "close": 79},
    {"time": "2026-07-26T21:00:00Z", "open": 79, "high": 96, "low": 70, "close": 83},
    {"time": "2026-07-27T21:00:00Z", "open": 83, "high": 87, "low": 68, "close": 81},
    {"time": "2026-07-28T21:00:00Z", "open": 77, "high": 81, "low": 65, "close": 69},
    {"time": "2026-07-29T21:00:00Z", "open": 73, "high": 75, "low": 60, "close": 60},
    {"time": "2026-07-30T21:00:00Z", "open": 60, "high": 75, "low": 55, "close": 66},
    {"time": "2026-07-31T21:00:00Z", "open": 66, "high": 78, "low": 54, "close": 74},
    {"time": "2026-08-01T21:00:00Z", "open": 67, "high": 74, "low": 54, "close": 68},
    {"time": "2026-08-02T21:00:00Z", "open": 65, "high": 81, "low": 54, "close": 74},
    {"time": "2026-08-03T21:00:00Z", "open": 67, "high": 77, "low": 55, "close": 72},
    {"time": "2026-08-04T21:00:00Z", "open": 72, "high": 72, "low": 55, "close": 66},
    {"time": "2026-08-05T21:00:00Z", "open": 69, "high": 71, "low": 54, "close": 61},
    {"time": "2026-08-06T21:00:00Z", "open": 68, "high": 68, "low": 53, "close": 63},
    {"time": "2026-08-07T21:00:00Z", "open": 63, "high": 70, "low": 51, "close": 64},
    {"time": "2026-08-08T21:00:00Z", "open": 58, "high": 72, "low": 50, "close": 60},
    {"time": "2026-08-09T21:00:00Z", "open": 57, "high": 72, "low": 51, "close": 64},
    {"time": "2026-08-10T21:00:00Z", "open": 67, "high": 67, "low": 52, "close": 67},
    {"time": "2026-08-12T21:00:00Z", "open": 91, "high": 100, "low": 59, "close": 96},
    {"time": "2026-08-13T21:00:00Z", "open": 96, "high": 108, "low": 69, "close": 82},
    {"time": "2026-08-14T21:00:00Z", "open": 90, "high": 104, "low": 74, "close": 92},
    {"time": "2026-08-15T21:00:00Z", "open": 101, "high": 106, "low": 77, "close": 96},
    {"time": "2026-08-16T21:00:00Z", "open": 96, "high": 139, "low": 89, "close": 112},
    {"time": "2026-08-17T21:00:00Z", "open": 118, "high": 123, "low": 89, "close": 117},
    {"time": "2026-08-18T21:00:00Z", "open": 117, "high": 117, "low": 89, "close": 111},
]

NOW = "2026-08-19T07:17:00Z"   # KST 8/19 16:17 — 마지막 캔들이 오늘 장중 캔들이다


def test_only_the_last_thirty_days_are_charted():
    c = material_chart(REAL30, now_price=105, now=NOW)
    assert c["days"] == CHART_DAYS
    assert c["points"][0]["date"] == "2026-07-20"    # 7/14T21Z(=7/15)가 아니다
    assert c["points"][-1]["date"] == "2026-08-19"


def test_a_candle_bucket_belongs_to_the_korean_day_it_covers():
    """버킷은 21:00Z에 시작한다 — KST 06:00. 그 하루가 이 캔들의 날짜다."""
    assert candle_day("2026-08-18T21:00:00Z") == "2026-08-19"


def test_the_low_point_is_the_day_it_actually_happened():
    """실측 30일 최저는 50원, 2026-08-08T21:00Z 버킷 = KST 8/9."""
    c = material_chart(REAL30, now_price=105, now=NOW)
    assert c["low"]["value"] == 50
    assert c["low"]["date"] == "2026-08-09"


def test_the_high_point_is_the_day_it_actually_happened():
    """실측 30일 최고는 139원, 2026-08-16T21:00Z 버킷 = KST 8/17."""
    c = material_chart(REAL30, now_price=105, now=NOW)
    assert c["high"]["value"] == 139
    assert c["high"]["date"] == "2026-08-17"


def test_the_window_spans_low_to_high_when_the_price_sits_inside():
    c = material_chart(REAL30, now_price=105, now=NOW)
    assert (c["y_min"], c["y_max"]) == (50, 139)


def test_the_window_stretches_up_to_a_price_above_the_range():
    """급등해서 삐져나간 것 자체가 지금 가장 중요한 정보다 — 잘라내지 않는다."""
    c = material_chart(REAL30, now_price=200, now=NOW)
    assert c["y_max"] == 200
    assert c["now_y"] == 0            # 맨 위에 붙는다
    assert c["y_min"] == 50


def test_the_window_stretches_down_to_a_price_below_the_range():
    c = material_chart(REAL30, now_price=20, now=NOW)
    assert c["y_min"] == 20
    assert c["y_max"] == 139


def test_coordinates_run_top_down_and_left_to_right():
    c = material_chart(REAL30, now_price=105, now=NOW, width=290, height=100)
    assert c["points"][0]["x"] == 0
    assert round(c["points"][-1]["x"]) == 290
    assert c["low"]["y"] == 100        # 최저가 바닥
    assert c["high"]["y"] == 0         # 최고가 천장
    for p in c["points"]:
        assert p["y_high"] <= p["y_close"] <= p["y_low"]


def test_a_fresh_chart_says_nothing_about_its_age():
    c = material_chart(REAL30, now_price=105, now=NOW)
    assert c["as_of"] == "2026-08-19"
    assert c["stale_days"] == 0


def test_a_stale_chart_carries_the_day_it_stopped_at():
    """일봉 수집이 이틀 멈추면 차트가 그 사실을 적는다."""
    c = material_chart(REAL30, now_price=105, now="2026-08-21T07:00:00Z")
    assert c["as_of"] == "2026-08-19"
    assert c["stale_days"] == 2


def test_no_candles_means_no_chart():
    assert material_chart([], now_price=105, now=NOW) is None


def test_one_candle_is_not_a_trend():
    """선을 그으려면 점이 둘은 있어야 한다."""
    assert material_chart(REAL30[-1:], now_price=105, now=NOW) is None


def test_two_candles_are_not_a_trend_either():
    """직선 하나가 나올 뿐이다. 빈 차트 대신 "시세 이력 없음"으로 간다."""
    assert material_chart(REAL30[-2:], now_price=105, now=NOW) is None


def test_three_candles_are_enough():
    c = material_chart(REAL30[-3:], now_price=105, now=NOW)
    assert c["days"] == 3


def test_a_flat_material_still_gets_a_readable_window():
    """특급 목재는 30일 내내 146이다 — 0으로 나누면 안 되고 선이 가운데 와야 한다."""
    flat = [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 146, "high": 146, "close": 146}
            for d in range(1, 19)]
    c = material_chart(flat, now_price=146, now=NOW, height=100)
    assert c["y_min"] < 146 < c["y_max"]
    assert c["points"][0]["y_close"] == 50
    assert c["low"]["value"] == 146 and c["high"]["value"] == 146


def test_a_missing_low_falls_back_to_the_close():
    """원본이 필드 이름을 바꿔도 남은 값으로 그린다 — 띠가 납작해질 뿐이다."""
    broken = [{"time": f"2026-08-{d:02d}T21:00:00Z", "close": 60 + d} for d in range(1, 6)]
    c = material_chart(broken, now_price=63, now=NOW)
    assert c["days"] == 5
    assert c["points"][0]["low"] == c["points"][0]["high"] == 61


def test_a_candle_without_a_close_is_dropped():
    """선을 이을 자리가 없다. 남은 점으로만 그린다."""
    mixed = REAL30[-5:-1] + [{"time": "2026-08-18T21:00:00Z", "low": 89, "high": 117}]
    c = material_chart(mixed, now_price=105, now=NOW)
    assert c["days"] == 4
    assert c["as_of"] == "2026-08-18"


def test_nothing_usable_means_no_chart():
    junk = [{"time": "2026-08-17T21:00:00Z"}, {"time": "2026-08-18T21:00:00Z"}]
    assert material_chart(junk, now_price=105, now=NOW) is None


def test_axis_ticks_do_not_repeat_a_number():
    """값이 좁게 붙으면 최저·중간·최고가 같은 숫자로 겹친다 — 그때는 줄인다."""
    tight = [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 100, "high": 101, "close": 100}
             for d in range(1, 19)]
    c = material_chart(tight, now_price=100, now=NOW)
    vals = [t["value"] for t in c["ticks"]]
    assert len(vals) == len(set(vals))
    wide = material_chart(REAL30, now_price=105, now=NOW)
    assert [t["value"] for t in wide["ticks"]] == [139, 94, 50]


def test_a_flat_material_gets_one_tick_not_three():
    """눈금 셋을 그으면 ±1만큼 움직인 것처럼 보인다."""
    flat = [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 132, "high": 132, "close": 132}
            for d in range(1, 19)]
    c = material_chart(flat, now_price=132, now=NOW)
    assert c["flat"] is True
    assert c["ticks"] == [{"value": 132, "y": 75.0}]


def test_a_flat_history_with_a_moved_price_is_not_flat():
    """30일 내내 132였는데 지금 200이면 그 차이가 볼거리다."""
    flat = [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 132, "high": 132, "close": 132}
            for d in range(1, 19)]
    c = material_chart(flat, now_price=200, now=NOW)
    assert c["flat"] is False
    assert (c["y_min"], c["y_max"]) == (132, 200)


def test_now_may_arrive_as_a_datetime():
    """`build_report(now=...)`가 문자열도 datetime도 받아 그대로 넘긴다."""
    from datetime import datetime, timezone

    c = material_chart(REAL30, now_price=105,
                       now=datetime(2026, 8, 19, 7, 17, tzinfo=timezone.utc))
    assert c["stale_days"] == 0


# --- 날짜 비례 배치 + 빠진 날 끊기 ------------------------------------------
#
# 원본에 8/12(KST)가 없다 — 18종 전부. 순서대로 놓으면 8/11과 8/13이 붙어
# 그날이 있었던 것처럼 보인다.


def test_points_sit_where_their_date_falls_not_where_their_turn_is():
    c = material_chart(REAL30, now_price=105, now=NOW, width=300)
    by_date = {p["date"]: p["x"] for p in c["points"]}
    # 7/20이 0, 8/19가 300. 그 사이 30일을 균등하게 나눠 하루가 10픽셀.
    assert by_date["2026-07-20"] == 0
    assert by_date["2026-08-19"] == 300
    assert round(by_date["2026-07-21"], 6) == 10
    # 8/12이 없으므로 8/11과 8/13 사이가 하루가 아니라 이틀만큼 벌어진다.
    assert round(by_date["2026-08-13"] - by_date["2026-08-11"], 6) == 20


def test_a_missing_day_splits_the_run_in_two():
    c = material_chart(REAL30, now_price=105, now=NOW)
    assert len(c["segments"]) == 2
    first, second = c["segments"]
    assert first[0]["date"] == "2026-07-20" and first[-1]["date"] == "2026-08-11"
    assert second[0]["date"] == "2026-08-13" and second[-1]["date"] == "2026-08-19"


def test_an_unbroken_run_stays_one_segment():
    whole = [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 50, "high": 60, "close": 55}
             for d in range(1, 11)]
    c = material_chart(whole, now_price=55, now=NOW)
    assert len(c["segments"]) == 1
    assert len(c["segments"][0]) == 10


def test_every_point_belongs_to_exactly_one_segment():
    c = material_chart(REAL30, now_price=105, now=NOW)
    flat = [p for seg in c["segments"] for p in seg]
    assert [p["date"] for p in flat] == [p["date"] for p in c["points"]]


def test_a_lone_day_between_two_gaps_is_its_own_segment():
    """앞뒤가 다 비면 혼자 남는다 — 그려도 면이 안 나오니 렌더가 알아야 한다."""
    sparse = [
        {"time": "2026-08-01T21:00:00Z", "low": 50, "high": 60, "close": 55},
        {"time": "2026-08-02T21:00:00Z", "low": 50, "high": 60, "close": 55},
        {"time": "2026-08-06T21:00:00Z", "low": 70, "high": 80, "close": 75},
        {"time": "2026-08-10T21:00:00Z", "low": 50, "high": 60, "close": 55},
        {"time": "2026-08-11T21:00:00Z", "low": 50, "high": 60, "close": 55},
    ]
    c = material_chart(sparse, now_price=55, now=NOW)
    assert [len(s) for s in c["segments"]] == [2, 1, 2]


# --- 툴팁이 읽을 값 ------------------------------------------------------------


def test_each_point_carries_its_open():
    """툴팁이 시가·고가·저가·종가 넷을 다 보여준다 — 시가도 점에 실려야 한다."""
    c = material_chart(REAL30, now_price=105, now=NOW)
    last = c["points"][-1]
    assert (last["open"], last["high"], last["low"], last["close"]) == (117, 117, 89, 111)


def test_a_missing_open_falls_back_to_the_close():
    """`low`·`high`와 같은 규칙이다 — 없는 값은 종가로 대신하고 그림은 나온다."""
    broken = [{"time": f"2026-08-{d:02d}T21:00:00Z", "close": 60 + d} for d in range(1, 6)]
    c = material_chart(broken, now_price=63, now=NOW)
    assert c["points"][0]["open"] == 61
