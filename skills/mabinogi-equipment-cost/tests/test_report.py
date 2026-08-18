import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from report import build_report
from store import Store

AS_OF = "2026-08-14T16:17:00Z"


@pytest.fixture
def db(tmp_path):
    s = Store(str(tmp_path / "r.db"))
    s.init()
    s.save_items(
        [
            {
                "id": 1,
                "name": "해연의 커브드 하프ZZ",
                "kind_id": 1,
                "tier": "해연",
                "base_name": "커브드 하프ZZ",
                "category": "Weapon",
                "can_trade": True,
            },
            {
                "id": 2,
                "name": "잔영의 커브드 하프ZZ",
                "kind_id": 2,
                "tier": "잔영",
                "base_name": "커브드 하프ZZ",
                "category": "Weapon",
                "can_trade": True,
            },
            {
                "id": 9,
                "name": "레시피: 해연의 커브드 하프ZZ",
                "kind_id": 9,
                "tier": "레시피",
                "base_name": "커브드 하프ZZ",
                "can_trade": False,
            },
        ]
    )
    s.save_recipe(
        1,
        "normal",
        [{"kind_id": 100, "name": "망령의 영혼석", "qty": 80, "can_trade": True}],
    )
    s.save_recipe(
        1,
        "recipe",
        [
            {
                "kind_id": 9,
                "name": "레시피: 해연의 커브드 하프ZZ",
                "qty": 1,
                "can_trade": False,
            },
            {"kind_id": 100, "name": "망령의 영혼석", "qty": 40, "can_trade": True},
        ],
    )
    s.save_recipe(
        2,
        "normal",
        [{"kind_id": 100, "name": "망령의 영혼석", "qty": 10, "can_trade": True}],
    )
    s.save_prices(
        [
            {
                "kind_id": 1,
                "name": "해연의 커브드 하프ZZ",
                "min_price": 23174,
                "total_count": 6,
            },
            {
                "kind_id": 2,
                "name": "잔영의 커브드 하프ZZ",
                "min_price": 1270,
                "total_count": 6,
            },
            {
                "kind_id": 100,
                "name": "망령의 영혼석",
                "min_price": 103,
                "total_count": 1548,
            },
        ],
        as_of=AS_OF,
    )
    return s


def test_groups_follow_a_fixed_category_order(db):
    """부위별로 묶어서 본다. 순서는 무기 → 방어구 → 장신구로 고정한다."""
    db.save_items(
        [
            {
                "id": 4,
                "name": "해연의 페리도트 링ZZ",
                "kind_id": 4,
                "tier": "해연",
                "base_name": "페리도트 링ZZ",
                "category": "Ring",
                "can_trade": True,
            },
            {
                "id": 5,
                "name": "해연의 비늘 갑옷 투구ZZ",
                "kind_id": 5,
                "tier": "해연",
                "base_name": "비늘 갑옷 투구ZZ",
                "category": "Hat",
                "can_trade": True,
            },
        ]
    )
    groups = build_report(db, now="2026-08-14T16:20:00Z")["groups"]
    assert [g["label"] for g in groups] == ["무기", "투구", "반지"]


def test_every_row_lands_in_exactly_one_group(db):
    rep = build_report(db, now="2026-08-14T16:20:00Z")
    grouped = [r["item_id"] for g in rep["groups"] for r in g["rows"]]
    assert sorted(grouped) == sorted(r["item_id"] for r in rep["rows"])
    assert len(grouped) == len(set(grouped))


def test_unknown_category_gets_its_own_bucket(db):
    """패치로 새 부위가 생겨도 행을 잃지 않는다."""
    db.save_items(
        [
            {
                "id": 7,
                "name": "해연의 무언가ZZ",
                "kind_id": 7,
                "tier": "해연",
                "base_name": "무언가ZZ",
                "category": "Wings",
                "can_trade": True,
            }
        ]
    )
    groups = build_report(db, now="2026-08-14T16:20:00Z")["groups"]
    assert 7 in [r["item_id"] for g in groups for r in g["rows"]]


def test_report_carries_freshness(db):
    rep = build_report(db, now="2026-08-14T16:20:00Z", threshold_sec=1800)
    assert rep["freshness"]["as_of"] == AS_OF
    assert rep["freshness"]["stale"] is False

    stale = build_report(db, now="2026-08-14T18:00:00Z", threshold_sec=1800)
    assert stale["freshness"]["stale"] is True


def test_haeyeon_row_has_both_craft_paths(db):
    row = build_report(db, now="2026-08-14T16:20:00Z")["rows"][0]
    assert row["normal"]["total"] == 103 * 80
    assert row["recipe"]["total"] == 103 * 40  # 거래 불가 레시피는 빠진다


def test_uncollected_recipe_row_is_marked(db, tmp_path):
    """레시피를 아직 못 받은 아이템도 행은 나온다 — 거래소 값은 이미 있다."""
    db.save_items(
        [
            {
                "id": 3,
                "name": "해연의 외톨이 검ZZ",
                "kind_id": 3,
                "tier": "해연",
                "base_name": "외톨이 검ZZ",
                "can_trade": True,
            }
        ]
    )
    db.save_prices(
        [
            {
                "kind_id": 3,
                "name": "해연의 외톨이 검ZZ",
                "min_price": 500,
                "total_count": 2,
            }
        ],
        as_of=AS_OF,
    )
    row = next(
        r
        for r in build_report(db, now="2026-08-14T16:20:00Z")["rows"]
        if r["item_id"] == 3
    )
    assert row["market"]["price"] == 500
    assert row["normal"]["status"] == "not_collected"
    assert row["normal"]["total"] is None


def test_only_haeyeon_becomes_a_row(db):
    """행은 해연만. 잔영은 '잔영을 N개 사거나 만드는 길'로 들어온다."""
    rep = build_report(db, now="2026-08-14T16:20:00Z")
    assert [r["name"] for r in rep["rows"]] == ["해연의 커브드 하프ZZ"]
    assert all(r["tier"] == "해연" for r in rep["rows"])


def test_row_carries_both_echo_paths(db):
    row = build_report(db, now="2026-08-14T16:20:00Z", echo_multiplier=10)["rows"][0]
    assert row["echo_buy"]["total"] == 1270 * 10  # 잔영 시세 × 10
    assert row["echo_craft"]["total"] == 103 * 10 * 10  # 잔영 제작비(1,030) × 10
    assert row["echo_name"] == "잔영의 커브드 하프ZZ"


def test_both_echo_paths_follow_the_multiplier(db):
    def totals(m):
        r = build_report(db, now="2026-08-14T16:20:00Z", echo_multiplier=m)["rows"][0]
        return r["echo_buy"]["total"], r["echo_craft"]["total"]

    assert totals(10) == (12700, 10300)
    assert totals(11) == (13970, 11330)


def test_verdict_weighs_all_four(db):
    row = build_report(db, now="2026-08-14T16:20:00Z", echo_multiplier=10)["rows"][0]
    # 해연 구매 23,174 / 해연 제작 8,240 / 잔영 구매 12,700 / 잔영 제작 10,300
    assert row["verdict"] == "craft"
    assert row["cheapest"]["price"] == 8240


def test_inventory_comes_from_the_caller_not_the_store(db):
    """재고는 방문자마다 다르다. 저장소에서 읽으면 전원이 한 재고를 공유한다."""
    plain = build_report(db, now="2026-08-14T16:20:00Z")
    assert plain["has_inventory"] is False
    assert plain["rows"][0]["normal"]["out_of_pocket"] == 103 * 80

    mine = build_report(db, now="2026-08-14T16:20:00Z", owned={100: 30})
    assert mine["has_inventory"] is True
    assert mine["rows"][0]["normal"]["out_of_pocket"] == 103 * 50
    assert mine["rows"][0]["normal"]["total"] == 103 * 80  # 판정은 전체 시세 그대로


def test_one_visitors_inventory_does_not_leak_into_anothers(db):
    a = build_report(db, now="2026-08-14T16:20:00Z", owned={100: 80})
    b = build_report(db, now="2026-08-14T16:20:00Z", owned={})
    assert a["rows"][0]["normal"]["out_of_pocket"] == 0
    assert b["rows"][0]["normal"]["out_of_pocket"] == 103 * 80


def test_partnerless_haeyeon_still_gets_a_row(db):
    """짝이 되는 잔영이 없으면 잔영 두 길만 빈다 — 행과 나머지 값은 살아 있다."""
    db.save_items(
        [
            {
                "id": 8,
                "name": "해연의 짝없는 검ZZ",
                "kind_id": 8,
                "tier": "해연",
                "base_name": "짝없는 검ZZ",
                "category": "Weapon",
                "can_trade": True,
            }
        ]
    )
    db.save_prices(
        [
            {
                "kind_id": 8,
                "name": "해연의 짝없는 검ZZ",
                "min_price": 500,
                "total_count": 3,
            }
        ],
        as_of=AS_OF,
    )
    row = next(
        r
        for r in build_report(db, now="2026-08-14T16:20:00Z")["rows"]
        if r["item_id"] == 8
    )
    assert row["market"]["price"] == 500
    assert row["echo_buy"]["status"] == "no_counterpart"
    assert row["echo_craft"]["status"] == "no_counterpart"
    assert row["echo_name"] is None


# --- 재료 단가표 ---------------------------------------------------------------


def test_material_prices_ride_along_with_the_report(db):
    """재고 입력칸 옆에 세울 단가표. 재료마다 현재가와 추세가 붙는다."""
    db.save_candles(
        555, "day",
        [{"time": f"2026-08-{d:02d}T21:00:00Z", "low": 90, "high": 120, "close": 100}
         for d in range(1, 15)],
    )
    db.save_prices(
        [{"kind_id": 100, "market_kind_id": 555, "name": "망령의 영혼석",
          "min_price": 118, "total_count": 1548}],
        as_of="2026-08-14T16:18:00Z",   # fixture보다 뒤 — 같은 시각이면 무시된다
    )
    rep = build_report(db, now="2026-08-14T16:20:00Z", owned={100: 30})
    mat = next(m for m in rep["materials"] if m["kind_id"] == 100)

    assert mat["name"] == "망령의 영혼석"
    assert mat["price"] == 118
    assert mat["owned"] == 30
    assert mat["value"] == 118 * 30              # 내 재고가 얼마어치인가
    assert mat["trend"]["verdict"] == "expensive"  # 90~120에서 118이면 비싼 편


def test_materials_without_candles_still_list(db):
    """캔들을 아직 안 받았어도 단가는 보여야 한다."""
    rep = build_report(db, now="2026-08-14T16:20:00Z")
    mat = next(m for m in rep["materials"] if m["kind_id"] == 100)
    assert mat["price"] == 103
    assert mat["trend"] is None


def test_inventory_value_is_summed(db):
    rep = build_report(db, now="2026-08-14T16:20:00Z", owned={100: 30})
    assert rep["inventory_value"] == 103 * 30


def test_no_inventory_means_no_value(db):
    assert build_report(db, now="2026-08-14T16:20:00Z")["inventory_value"] == 0
