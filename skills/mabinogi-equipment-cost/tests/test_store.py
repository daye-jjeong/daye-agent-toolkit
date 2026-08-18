import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from store import Store


@pytest.fixture
def db(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.init()
    return s


def test_price_snapshot_roundtrip(db):
    db.save_prices(
        [
            {
                "kind_id": 1,
                "name": "특급 목재",
                "min_price": 146,
                "total_count": 162952,
            },
        ],
        as_of="2026-08-14T16:17:00Z",
    )
    got = db.latest_prices()
    assert got[1]["min_price"] == 146
    assert got[1]["total_count"] == 162952


def test_same_snapshot_is_not_stored_twice(db):
    rows = [{"kind_id": 1, "name": "특급 목재", "min_price": 146, "total_count": 10}]
    db.save_prices(rows, as_of="2026-08-14T16:17:00Z")
    db.save_prices(rows, as_of="2026-08-14T16:17:00Z")
    assert db.price_history_count(1) == 1


def test_history_accumulates_across_snapshots(db):
    db.save_prices(
        [{"kind_id": 1, "name": "특급 목재", "min_price": 146, "total_count": 10}],
        as_of="2026-08-14T16:17:00Z",
    )
    db.save_prices(
        [{"kind_id": 1, "name": "특급 목재", "min_price": 150, "total_count": 9}],
        as_of="2026-08-14T16:27:00Z",
    )
    assert db.price_history_count(1) == 2
    assert db.latest_prices()[1]["min_price"] == 150  # 최신 스냅샷이 이긴다


def test_collection_time_is_recorded_separately_from_the_snapshot(db):
    """`price_history`로는 "언제 받았나"를 알 수 없다.

    같은 스냅샷은 중복 저장을 건너뛰므로, 원본이 새 값을 안 주는 동안에는
    아무리 받아도 흔적이 안 남는다.
    """
    rows = [{"kind_id": 1, "name": "특급 목재", "min_price": 146, "total_count": 10}]
    db.save_prices(rows, as_of="2026-08-15T07:14:00Z")
    db.mark_collected(as_of="2026-08-15T07:14:00Z", count=1, at="2026-08-15T07:15:00Z")

    # 3분 뒤 다시 받았지만 원본은 같은 스냅샷을 줬다
    db.save_prices(rows, as_of="2026-08-15T07:14:00Z")
    db.mark_collected(as_of="2026-08-15T07:14:00Z", count=1, at="2026-08-15T07:18:00Z")

    assert db.price_history_count(1) == 1  # 이력은 그대로
    assert db.last_collected()["fetched_at"] == "2026-08-15T07:18:00Z"  # 받은 건 사실


def test_no_collection_yet_is_none(db):
    assert db.last_collected() is None


def test_latest_as_of_drives_freshness(db):
    assert db.latest_as_of() is None
    db.save_prices(
        [{"kind_id": 1, "name": "x", "min_price": 1, "total_count": 1}],
        as_of="2026-08-14T16:17:00Z",
    )
    assert db.latest_as_of() == "2026-08-14T16:17:00Z"


# --- 5행: 상세 API가 쿼터를 반환 — 부분 수집분을 버리지 않고 이어받는다 ------


def test_pending_recipe_ids_excludes_collected(db):
    db.save_items(
        [
            {"id": 10, "name": "A", "kind_id": 100},
            {"id": 11, "name": "B", "kind_id": 101},
            {"id": 12, "name": "C", "kind_id": 102},
        ]
    )
    db.save_recipe(
        10, "normal", [{"kind_id": 1, "name": "m", "qty": 2, "can_trade": True}]
    )
    assert db.pending_recipe_ids() == [11, 12]


def test_quota_stop_keeps_partial_and_resumes(db):
    db.save_items(
        [{"id": i, "name": f"i{i}", "kind_id": 100 + i} for i in (10, 11, 12)]
    )
    db.save_recipe(
        10, "normal", [{"kind_id": 1, "name": "m", "qty": 2, "can_trade": True}]
    )
    # 쿼터로 중단됐다가 다음 주기에 이어받는다
    assert db.pending_recipe_ids() == [11, 12]
    db.save_recipe(
        11, "normal", [{"kind_id": 1, "name": "m", "qty": 3, "can_trade": True}]
    )
    assert db.pending_recipe_ids() == [12]
    # 먼저 받은 건 그대로 살아 있다
    assert db.recipe(10)["normal"][0]["qty"] == 2


def test_recipe_returns_none_when_uncollected(db):
    db.save_items([{"id": 10, "name": "A", "kind_id": 100}])
    assert db.recipe(10) is None


# --- 배포용 씨앗 ---------------------------------------------------------------


def test_seed_carries_recipes_but_not_price_history(db, tmp_path):
    """배포 이미지에 넣을 DB. 레시피는 쿼터 때문에 새 환경에서 다시 못 받는다.

    시세는 쿼터가 없어 뜨자마자 채워지므로 이력을 통째로 들고 갈 이유가 없다.
    """
    db.save_items([{"id": 10, "name": "A", "kind_id": 100, "can_trade": True}])
    db.save_recipe(
        10,
        "normal",
        [{"kind_id": 1, "name": "망령의 영혼석", "qty": 2, "can_trade": True}],
    )
    db.save_prices(
        [{"kind_id": 1, "name": "망령의 영혼석", "min_price": 103, "total_count": 5}],
        as_of="2026-08-14T16:17:00Z",
    )

    seed_path = str(tmp_path / "seed.db")
    db.export_seed(seed_path)

    seed = Store(seed_path)
    assert seed.items()[0]["name"] == "A"
    assert seed.recipe(10)["normal"][0]["qty"] == 2
    assert seed.material_index() == {"망령의 영혼석": 1}
    assert seed.latest_as_of() is None  # 시세는 배포처에서 새로 받는다


def test_seed_does_not_carry_a_leftover_inventory(db, tmp_path):
    """재고는 브라우저에 산다. 씨앗에 실리면 방문자 전원이 물려받는다."""
    with sqlite3.connect(db.path) as c:
        c.execute("CREATE TABLE inventory (kind_id INTEGER PRIMARY KEY, qty INTEGER)")
        c.execute("INSERT INTO inventory VALUES (100, 30)")

    seed_path = str(tmp_path / "seed.db")
    db.export_seed(seed_path)

    with sqlite3.connect(seed_path) as c:
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master")}
    assert "inventory" not in names


def test_recipe_keeps_untradable_flag(db):
    db.save_items([{"id": 10, "name": "A", "kind_id": 100}])
    db.save_recipe(
        10,
        "recipe",
        [
            {"kind_id": 5, "name": "레시피: A", "qty": 1, "can_trade": False},
        ],
    )
    assert db.recipe(10)["recipe"][0]["can_trade"] is False


# --- 캔들 (원본이 주는 일봉) ----------------------------------------------------


def test_prices_carry_the_market_kind_id(db):
    db.save_prices(
        [{"kind_id": 9283, "market_kind_id": 281479538461834, "name": "망령의 영혼석",
          "min_price": 100, "total_count": 5210}],
        as_of="2026-08-16T04:56:00Z",
    )
    assert db.latest_prices()[9283]["market_kind_id"] == 281479538461834


def test_old_rows_without_a_market_kind_id_still_read(db):
    """이 컬럼이 생기기 전에 쌓인 이력."""
    db.save_prices(
        [{"kind_id": 1, "name": "x", "min_price": 5, "total_count": 1}],
        as_of="2026-08-16T04:56:00Z",
    )
    assert db.latest_prices()[1]["market_kind_id"] is None


CANDLES = [
    {"time": "2026-08-14T21:00:00Z", "open": 74, "high": 104, "low": 74, "close": 92,
     "count_close": 3403},
    {"time": "2026-08-15T21:00:00Z", "open": 92, "high": 104, "low": 80, "close": 95,
     "count_close": 5265},
]


def test_candle_roundtrip(db):
    db.save_candles(281479538461834, "day", CANDLES)
    got = db.candles(281479538461834, "day")
    assert [c["close"] for c in got] == [92, 95]
    assert got[-1]["low"] == 80 and got[-1]["high"] == 104


def test_refetching_the_same_day_updates_it(db):
    """장중에 다시 받으면 그날 캔들이 갱신돼야 한다 — 두 줄로 늘면 안 된다."""
    db.save_candles(281479538461834, "day", CANDLES)
    db.save_candles(281479538461834, "day", [{**CANDLES[-1], "close": 99, "high": 110}])
    got = db.candles(281479538461834, "day")
    assert len(got) == 2
    assert got[-1]["close"] == 99 and got[-1]["high"] == 110


def test_candles_are_kept_apart_by_interval_and_item(db):
    db.save_candles(1, "day", CANDLES)
    db.save_candles(1, "week", CANDLES[:1])
    db.save_candles(2, "day", CANDLES[:1])
    assert len(db.candles(1, "day")) == 2
    assert len(db.candles(1, "week")) == 1
    assert db.candles(999, "day") == []


def test_candles_come_back_in_time_order(db):
    db.save_candles(1, "day", list(reversed(CANDLES)))
    assert [c["time"] for c in db.candles(1, "day")] == [c["time"] for c in CANDLES]


def test_an_old_database_gains_the_new_column(tmp_path):
    """CREATE TABLE IF NOT EXISTS는 이미 있는 테이블을 바꾸지 않는다.

    실제로 돌고 있는 DB가 이 컬럼 없이 만들어져 있다.
    """
    path = str(tmp_path / "old.db")
    with sqlite3.connect(path) as c:
        c.execute(
            "CREATE TABLE price_history (kind_id INTEGER NOT NULL, name TEXT,"
            " min_price INTEGER, total_count INTEGER, as_of TEXT NOT NULL,"
            " PRIMARY KEY (kind_id, as_of))"
        )
        c.execute("INSERT INTO price_history VALUES (1, '특급 목재', 146, 10, 'x')")

    s = Store(path)
    s.init()
    s.save_prices(
        [{"kind_id": 2, "market_kind_id": 999, "name": "새 재료",
          "min_price": 5, "total_count": 1}],
        as_of="2026-08-16T04:56:00Z",
    )
    assert s.latest_prices()[2]["market_kind_id"] == 999
    assert s.latest_prices()[1]["market_kind_id"] is None  # 옛 행은 비어 있다
