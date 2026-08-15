import os
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
