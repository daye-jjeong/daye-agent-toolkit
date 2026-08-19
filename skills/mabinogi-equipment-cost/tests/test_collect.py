import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import api
import collect
import pytest
from store import Store

DETAIL = {
    "id": 1,
    "attributes": {
        "crafting": {
            "made_by": [
                {"ingredients": [{"name": "특급 목재", "count": 5, "itemId": 9421}]},
                {
                    "ingredients": [
                        {"name": "레시피: x", "count": 1, "itemId": 900},
                        {"name": "특급 목재", "count": 3, "itemId": 9421},
                    ]
                },
            ]
        }
    },
}


@pytest.fixture
def db(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    s.init()
    s.save_items(
        [
            {
                "id": i,
                "name": f"해연의 무기{i}ZZ",
                "kind_id": i,
                "tier": "해연",
                "base_name": f"무기{i}ZZ",
                "can_trade": True,
            }
            for i in (1, 2, 3)
        ]
        + [
            {
                "id": 900,
                "name": "레시피: x",
                "kind_id": 900,
                "tier": "레시피",
                "base_name": "x",
                "can_trade": False,
            }
        ]
    )
    return s


def test_quota_stops_collection_and_keeps_what_arrived(db, monkeypatch):
    """5행: 상세 API가 쿼터를 반환 — 멈추되 이미 받은 레시피는 유지한다."""
    calls = []

    def fake(item_id):
        calls.append(item_id)
        if len(calls) > 2:
            raise api.Throttled(retry_after=578)
        return {**DETAIL, "id": item_id}

    monkeypatch.setattr(collect.api, "fetch_item_detail", fake)
    done, left, retry = collect.collect_recipes(db, sleep=0)

    assert (done, left, retry) == (2, 1, 578)
    assert db.recipe(1) is not None  # 받은 건 살아 있다
    assert db.recipe(3) is None


def test_next_run_resumes_from_what_is_missing(db, monkeypatch):
    seen = []

    def fake(item_id):
        seen.append(item_id)
        return {**DETAIL, "id": item_id}

    monkeypatch.setattr(collect.api, "fetch_item_detail", fake)
    db.save_recipe(
        1,
        "normal",
        [{"kind_id": 9421, "name": "특급 목재", "qty": 5, "can_trade": True}],
    )
    collect.collect_recipes(db, sleep=0)
    assert seen == [2, 3]  # 이미 받은 1은 다시 조회하지 않는다


def test_recipe_items_are_never_fetched(db, monkeypatch):
    """레시피 아이템 38종은 상세를 받을 이유가 없다 — 쿼터를 아낀다."""
    seen = []
    monkeypatch.setattr(
        collect.api,
        "fetch_item_detail",
        lambda i: (seen.append(i), {**DETAIL, "id": i})[1],
    )
    collect.collect_recipes(db, sleep=0)
    assert 900 not in seen


def test_untradable_material_flag_survives_collection(db, monkeypatch):
    monkeypatch.setattr(collect.api, "fetch_item_detail", lambda i: {**DETAIL, "id": i})
    collect.collect_recipes(db, sleep=0)
    recipe_path = db.recipe(1)["recipe"]
    assert next(m for m in recipe_path if m["kind_id"] == 900)["can_trade"] is False


def test_item_without_crafting_is_marked_fetched(db, monkeypatch):
    """제작 불가 아이템도 '받았다'고 남긴다. 안 그러면 매번 다시 조회한다."""
    monkeypatch.setattr(
        collect.api, "fetch_item_detail", lambda i: {"id": i, "attributes": {}}
    )
    collect.collect_recipes(db, sleep=0)
    assert db.pending_recipe_ids(tiers=("해연", "잔영")) == []


def test_materials_get_their_trade_flag_filled(db, monkeypatch):
    """재료 중에도 거래 불가가 있다 — 레시피 아이템만이 아니다.

    '세공된 페리도트ZZ'가 그렇다. items 테이블에 없으면 거래 가능으로 오인해
    경로 전체가 '계산 불가'로 죽는다. 실제로는 그 재료만 빼고 계산해야 한다.
    """
    monkeypatch.setattr(
        collect.api,
        "fetch_item_detail",
        lambda i: {
            "id": i,
            "attributes": {
                "crafting": {
                    "made_by": [
                        {
                            "ingredients": [
                                {
                                    "name": "세공된 페리도트ZZ",
                                    "count": 2,
                                    "itemId": 9369,
                                }
                            ]
                        },
                    ]
                }
            },
        },
    )
    collect.collect_recipes(db, sleep=0)

    monkeypatch.setattr(
        collect.api,
        "fetch_items",
        lambda name: [
            {
                "id": 9369,
                "name": "세공된 페리도트ZZ",
                "category": "Ingredient",
                "can_trade": False,
            },
            {
                "id": 593,
                "name": "세공된 페리도트",
                "category": "Ingredient",
                "can_trade": False,
            },  # 이름 검색은 여러 건을 준다 — id로 골라야 한다
        ],
    )
    filled = collect.collect_materials(db)

    assert filled == 1
    assert {i["id"]: i["can_trade"] for i in db.items()}[9369] is False


def test_material_fill_skips_what_is_already_known(db, monkeypatch):
    calls = []
    monkeypatch.setattr(
        collect.api,
        "fetch_item_detail",
        lambda i: {
            "id": i,
            "attributes": {
                "crafting": {
                    "made_by": [
                        {
                            "ingredients": [
                                {"name": "레시피: x", "count": 1, "itemId": 900}
                            ]
                        },
                    ]
                }
            },
        },
    )
    collect.collect_recipes(db, sleep=0)
    monkeypatch.setattr(
        collect.api, "fetch_items", lambda name: calls.append(name) or []
    )
    collect.collect_materials(db)
    assert calls == []  # 900은 이미 items 테이블에 있다


def test_retry_after_is_parsed_from_throttle_body():
    body = '{"detail": "Request was throttled. Expected available in 578 seconds."}'
    assert api.parse_retry_after(body) == 578
    assert api.parse_retry_after({"detail": "Expected available in 5 seconds."}) == 5
    assert api.parse_retry_after("nope") is None


# --- 캔들 수집 -----------------------------------------------------------------


def test_candles_are_collected_for_tradable_materials(monkeypatch, tmp_path):
    """재료 18종만 받는다. 해연 38종까지 받으면 요청이 세 배가 된다."""
    s = Store(str(tmp_path / "c.db"))
    s.init()
    s.save_recipe(
        1, "normal",
        [{"kind_id": 9283, "name": "망령의 영혼석", "qty": 80, "can_trade": True}],
    )
    s.save_prices(
        [{"kind_id": 9283, "market_kind_id": 281479538461834, "name": "망령의 영혼석",
          "min_price": 100, "total_count": 5210}],
        as_of="2026-08-16T04:56:00Z",
    )

    asked = []

    def fake(market_kind_id, interval="day"):
        asked.append((market_kind_id, interval))
        return [{"time": "2026-08-15T21:00:00Z", "open": 92, "high": 104,
                 "low": 80, "close": 95, "count_close": 5265}]

    monkeypatch.setattr(collect.api, "fetch_candles", fake)
    n = collect.collect_candles(s, sleep=0)

    assert asked == [(281479538461834, "day")]
    assert n == 1
    assert s.candles(281479538461834, "day")[-1]["close"] == 95


def test_a_material_without_a_market_kind_id_is_skipped(monkeypatch, tmp_path):
    """시세를 아직 못 받았거나 옛 스키마로 쌓인 재료 — 404를 부르지 않는다."""
    s = Store(str(tmp_path / "c2.db"))
    s.init()
    s.save_recipe(
        1, "normal",
        [{"kind_id": 9283, "name": "망령의 영혼석", "qty": 80, "can_trade": True}],
    )
    s.save_prices(
        [{"kind_id": 9283, "name": "망령의 영혼석", "min_price": 100, "total_count": 5}],
        as_of="2026-08-16T04:56:00Z",
    )
    monkeypatch.setattr(
        collect.api, "fetch_candles",
        lambda *a, **k: pytest.fail("market_kind_id가 없으면 부르면 안 된다"))
    assert collect.collect_candles(s, sleep=0) == 0


# --- 이력은 화면에 쓰는 종목만 -------------------------------------------------


def _prices_api(monkeypatch, rows):
    monkeypatch.setattr(collect.api, "fetch_prices", lambda on_page=None: rows)


ROWS = [
    {"codex_item_id": 100, "kind_id": 900, "name": "망령의 영혼석",
     "min_price": 103, "total_count": 5, "last_version": "2026-08-19T06:00:00Z"},
    {"codex_item_id": 1, "kind_id": 901, "name": "해연의 검ZZ",
     "min_price": 500, "total_count": 2, "last_version": "2026-08-19T06:00:00Z"},
    {"codex_item_id": 777, "kind_id": 902, "name": "훌륭한 탁상 램프 데코 상자",
     "min_price": 9, "total_count": 3, "last_version": "2026-08-19T06:00:00Z"},
]


def _seeded(tmp_path, name):
    s = Store(str(tmp_path / name))
    s.init()
    s.save_items([{"id": 1, "name": "해연의 검ZZ", "kind_id": 1, "tier": "해연",
                   "base_name": "검ZZ", "can_trade": True}])
    s.save_recipe(1, "normal",
                  [{"kind_id": 100, "name": "망령의 영혼석", "qty": 80, "can_trade": True}])
    return s


def test_only_tracked_items_are_stored(monkeypatch, tmp_path):
    """가구·요리 시세가 92%를 차지했다 — 화면에 한 번도 안 나오는 것들이다."""
    s = _seeded(tmp_path, "t.db")
    _prices_api(monkeypatch, ROWS)
    collect.collect_prices(s)

    stored = set(s.latest_prices())
    assert stored == {100, 1}          # 재료 + 해연
    assert 777 not in stored           # 데코 상자는 안 쌓는다


def test_an_empty_filter_stores_everything(monkeypatch, tmp_path):
    """첫 실행 — 아이템 목록을 아직 안 받았으면 걸러낼 근거가 없다."""
    s = Store(str(tmp_path / "e.db"))
    s.init()
    _prices_api(monkeypatch, ROWS)
    collect.collect_prices(s)
    assert set(s.latest_prices()) == {100, 1, 777}


def test_the_report_still_sees_what_it_needs(monkeypatch, tmp_path):
    """걸러낸 뒤에도 화면이 쓰는 값은 전부 남아야 한다."""
    from report import build_report

    s = _seeded(tmp_path, "r.db")
    _prices_api(monkeypatch, ROWS)
    collect.collect_prices(s)

    rep = build_report(s, now="2026-08-19T06:05:00Z")
    assert rep["rows"][0]["market"]["price"] == 500
    assert rep["rows"][0]["normal"]["total"] == 103 * 80
    assert [m["price"] for m in rep["materials"]] == [103]
