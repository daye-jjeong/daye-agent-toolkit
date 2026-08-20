import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fixtures as fx
from cost import build_row
from normalize import normalize_prices, normalize_recipe

DETAIL = json.load(open(os.path.join(os.path.dirname(__file__), "detail_16055.json")))
RECIPE_ITEM_ID = 10075  # 레시피: 해연의 커브드 하프ZZ — 거래 불가


def test_first_made_by_is_normal_craft():
    r = normalize_recipe(DETAIL)
    names = [m["name"] for m in r["normal"]]
    assert names[0] == "특급 목재"
    assert len(r["normal"]) == 6
    assert {m["name"]: m["qty"] for m in r["normal"]}["망령의 영혼석"] == 80


def test_second_made_by_is_recipe_craft():
    r = normalize_recipe(DETAIL)
    assert r["recipe"][0]["name"] == "레시피: 해연의 커브드 하프ZZ"
    assert {m["name"]: m["qty"] for m in r["recipe"]}["망령의 영혼석"] == 40


def test_material_key_is_item_id():
    """재료의 itemId가 시세의 codex_item_id와 맞물린다."""
    r = normalize_recipe(DETAIL)
    wood = next(m for m in r["normal"] if m["name"] == "특급 목재")
    assert wood["kind_id"] == 9421


def test_untradable_ids_mark_materials():
    r = normalize_recipe(DETAIL, untradable_ids={RECIPE_ITEM_ID})
    recipe_mat = next(m for m in r["recipe"] if m["kind_id"] == RECIPE_ITEM_ID)
    assert recipe_mat["can_trade"] is False
    assert all(m["can_trade"] for m in r["normal"])


def test_single_made_by_has_no_recipe_path():
    """잔영처럼 레시피 경로가 없는 아이템."""
    d = json.loads(json.dumps(DETAIL))
    d["attributes"]["crafting"]["made_by"] = d["attributes"]["crafting"]["made_by"][:1]
    r = normalize_recipe(d)
    assert r["recipe"] is None
    assert len(r["normal"]) == 6


def test_no_crafting_block_yields_none():
    d = {"id": 1, "name": "x", "attributes": {}}
    assert normalize_recipe(d) is None


# --- 시세 정규화 -------------------------------------------------------------

RAW_PRICES = [
    {
        "kind_id": 1,
        "codex_item_id": 9421,
        "name": "특급 목재",
        "min_price": 146,
        "total_count": 162952,
        "last_version": "2026-08-14T16:17:00Z",
    },
    {
        "kind_id": 2,
        "codex_item_id": None,
        "name": "",
        "min_price": 411,
        "total_count": 3,
        "last_version": "2026-08-14T16:17:00Z",
    },
]


def test_prices_keyed_by_codex_item_id():
    p = normalize_prices(RAW_PRICES)
    assert p[9421]["min_price"] == 146


def test_rows_without_codex_id_are_dropped():
    """codex_item_id가 없는 레코드가 134건 있다 — 매칭에 쓸 수 없다."""
    assert None not in normalize_prices(RAW_PRICES)
    assert len(normalize_prices(RAW_PRICES)) == 1


def test_duplicate_codex_id_keeps_lowest_price():
    """같은 codex_item_id가 여러 건이면 최저가를 택한다 — 원가 기준과 일치시킨다."""
    rows = RAW_PRICES + [
        {
            "kind_id": 3,
            "codex_item_id": 9421,
            "name": "특급 목재",
            "min_price": 140,
            "total_count": 5,
            "last_version": "2026-08-14T16:17:00Z",
        }
    ]
    assert normalize_prices(rows)[9421]["min_price"] == 140


def test_sold_out_row_does_not_beat_priced_row():
    """매물 0은 최저가로 볼 수 없다 — 살 수 없는 가격이다."""
    rows = RAW_PRICES + [
        {
            "kind_id": 3,
            "codex_item_id": 9421,
            "name": "특급 목재",
            "min_price": 1,
            "total_count": 0,
            "last_version": "2026-08-14T16:17:00Z",
        }
    ]
    assert normalize_prices(rows)[9421]["min_price"] == 146


# --- 정규화 → 계산까지 한 줄로 이어지는지 -----------------------------------


def test_normalized_recipe_feeds_cost_function():
    r = normalize_recipe(DETAIL, untradable_ids={RECIPE_ITEM_ID})
    prices = {
        m["kind_id"]: fx.PRICES[k]
        for m, k in zip(
            r["normal"],
            [
                281479782081111,
                281479763007481,
                281481363189525,
                281479538461834,
                281480675678393,
                281480597107872,
            ],
        )
    }
    prices[16055] = fx.PRICES[281489250918530]
    row = build_row(
        item_id=16055,
        name="해연의 커브드 하프ZZ",
        kind_id=16055,
        normal=r["normal"],
        recipe=r["recipe"],
        prices=prices,
    )
    assert row["normal"]["total"] == fx.NORMAL_TOTAL
    assert row["recipe"]["total"] == fx.RECIPE_TOTAL
    assert row["market"]["price"] == fx.MARKET_PRICE


def test_prices_keep_the_market_kind_id():
    """시세 캔들 API는 codex_item_id가 아니라 진짜 kind_id를 요구한다.

    둘을 헷갈리면 404가 난다(실측).
    """
    out = normalize_prices([
        {"codex_item_id": 9283, "kind_id": 281479538461834, "name": "망령의 영혼석",
         "min_price": 100, "total_count": 5210, "last_version": "2026-08-16T04:56:00Z"},
    ])
    assert out[9283]["market_kind_id"] == 281479538461834


def test_the_winning_row_brings_its_own_market_kind_id():
    """같은 codex_item_id에 여러 줄이 오면 이긴 줄의 kind_id를 써야 한다."""
    out = normalize_prices([
        {"codex_item_id": 1, "kind_id": 111, "min_price": 90, "total_count": 0},
        {"codex_item_id": 1, "kind_id": 222, "min_price": 100, "total_count": 5},
    ])
    assert out[1]["min_price"] == 100          # 매물 있는 줄이 이긴다
    assert out[1]["market_kind_id"] == 222
