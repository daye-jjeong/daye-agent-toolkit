import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fixtures as fx
from cost import build_row, freshness

BASE = dict(
    item_id=16055,
    name="해연의 커브드 하프ZZ",
    kind_id=281489250918530,
    normal=fx.HAEYEON_HARP_NORMAL,
)


# --- done 기준 1: 픽스처 재현 -------------------------------------------------


def test_market_price_from_fixture():
    row = build_row(**BASE, prices=fx.PRICES)
    assert row["market"]["status"] == "ok"
    assert row["market"]["price"] == fx.MARKET_PRICE
    assert row["market"]["count"] == 6


def test_normal_craft_total_from_fixture():
    row = build_row(**BASE, prices=fx.PRICES)
    assert row["normal"]["status"] == "ok"
    assert row["normal"]["total"] == fx.NORMAL_TOTAL


def test_normal_craft_material_breakdown():
    row = build_row(**BASE, prices=fx.PRICES)
    mats = row["normal"]["materials"]
    assert len(mats) == 6
    ghost = next(m for m in mats if m["name"] == "망령의 영혼석")
    assert (ghost["qty"], ghost["unit_price"], ghost["subtotal"]) == (80, 103, 8240)
    assert ghost["listing_count"] == 1548
    # 재료비의 54%를 한 종이 차지한다 — 스펙이 실측으로 든 예
    assert round(ghost["subtotal"] / row["normal"]["total"] * 100) == 54


def test_recipe_craft_total_from_fixture():
    row = build_row(**BASE, prices=fx.PRICES, recipe=fx.HAEYEON_HARP_WITH_RECIPE)
    assert row["recipe"]["status"] == "ok"
    assert row["recipe"]["total"] == fx.RECIPE_TOTAL
    # 레시피 자체는 거래 불가라 합계에서 빠지고 라벨만 남는다
    assert row["recipe"]["excluded_untradable"] == ["레시피: 해연의 커브드 하프ZZ"]


def test_recipe_path_is_absent_for_janyeong():
    """잔영은 레시피 아이템이 없다 — 0원이 아니라 빈 칸이다."""
    row = build_row(**BASE, prices=fx.PRICES, recipe=None)
    assert row["recipe"] is None


def test_three_fixture_values_reproduce_together():
    """done 기준 1 — 세 값이 한 행에서 같이 나온다."""
    row = build_row(**BASE, prices=fx.PRICES, recipe=fx.HAEYEON_HARP_WITH_RECIPE)
    assert (row["market"]["price"], row["normal"]["total"], row["recipe"]["total"]) == (
        23174,
        15165,
        8322,
    )


def test_craft_is_cheaper_than_market_for_fixture():
    row = build_row(**BASE, prices=fx.PRICES)
    assert row["normal"]["total"] < row["market"]["price"]


def test_cost_is_labelled_as_lower_bound():
    # 최저가 × 수량이라 실제 지출은 이보다 크다. 페이지가 이걸 숨기면 안 된다.
    row = build_row(**BASE, prices=fx.PRICES)
    assert row["normal"]["is_lower_bound"] is True


# --- done 기준 2: "범위 밖 입력을 만나면" 표 7행 ------------------------------


def test_untradable_material_is_excluded_and_labelled():
    """1행: 재료가 거래 불가(레시피 아이템) — 합계에서 빼고 라벨, 경로는 살린다."""
    mats = fx.HAEYEON_HARP_NORMAL + [
        {
            "kind_id": 999,
            "name": "레시피: 해연의 커브드 하프ZZ",
            "qty": 1,
            "can_trade": False,
        }
    ]
    row = build_row(**{**BASE, "normal": mats}, prices=fx.PRICES)
    assert row["normal"]["status"] == "ok"
    assert row["normal"]["total"] == fx.NORMAL_TOTAL  # 빠졌으므로 합계 불변
    assert "레시피: 해연의 커브드 하프ZZ" in row["normal"]["excluded_untradable"]


def test_missing_price_makes_whole_path_uncomputable():
    """2행: 재료 시세가 아예 없음 — 경로 전체를 계산 불가로. 0으로 메우지 않는다."""
    mats = fx.HAEYEON_HARP_NORMAL + [
        {"kind_id": 12345, "name": "시세없는재료", "qty": 3, "can_trade": True}
    ]
    row = build_row(**{**BASE, "normal": mats}, prices=fx.PRICES)
    assert row["normal"]["status"] == "uncomputable"
    assert row["normal"]["total"] is None
    assert "시세없는재료" in row["normal"]["missing_price"]


def test_sold_out_product_drops_market_from_the_options():
    """3행: 완제품 매물이 0 — 거래소만 선택지에서 빼고 나머지로 비교한다."""
    prices = {**fx.PRICES}
    prices[281489250918530] = {**prices[281489250918530], "total_count": 0}
    row = build_row(**BASE, prices=prices)
    assert row["market"]["status"] == "no_listing"
    assert row["market"]["price"] is None  # 직전 가격을 현재가로 쓰지 않는다
    assert row["verdict"] == "craft"  # 살 수 없으니 만드는 수밖에
    assert row["cheapest"]["price"] == fx.NORMAL_TOTAL


def test_listing_shortage_warns_but_still_computes():
    """4행: 매물 수량이 필요 수량보다 적음 — 계산은 하되 경고를 남긴다."""
    prices = {**fx.PRICES}
    prices[281479538461834] = {
        **prices[281479538461834],
        "total_count": 10,
    }  # 80개 필요
    row = build_row(**BASE, prices=prices)
    assert row["normal"]["status"] == "ok"
    assert row["normal"]["total"] == fx.NORMAL_TOTAL
    ghost = next(m for m in row["normal"]["materials"] if m["name"] == "망령의 영혼석")
    assert ghost["shortage"] is True
    assert "망령의 영혼석" in row["normal"]["shortage_warnings"]


def test_stale_snapshot_is_flagged():
    """6행: 수집기가 멈춤 — 임계를 넘으면 신선도가 경고로 바뀐다."""
    ok = freshness(
        "2026-08-14T16:17:00Z", now="2026-08-14T16:22:00Z", threshold_sec=1800
    )
    assert ok["stale"] is False
    assert ok["age_sec"] == 300

    bad = freshness(
        "2026-08-14T16:17:00Z", now="2026-08-14T17:30:00Z", threshold_sec=1800
    )
    assert bad["stale"] is True
    assert bad["age_sec"] == 4380


# --- 원본이 늦는 것과 우리가 멈춘 것은 다르다 ----------------------------------
#
# 실측: 원본 기준 시각이 07:14에서 07:35까지 21분간 안 바뀌었다. 그 사이
# 수집기는 3분마다 일곱 번 받았고 매번 원본이 "최신은 07:14"라고 답했다.


def test_lagging_source_is_not_our_failure():
    """받은 지 2분밖에 안 됐으면 경고하지 않는다 — 우리 쪽은 멀쩡하다."""
    f = freshness(
        "2026-08-15T07:14:00Z",
        fetched_at="2026-08-15T07:36:00Z",
        now="2026-08-15T07:38:00Z",
        threshold_sec=900,
    )
    assert f["stale"] is False  # 노란 경고를 띄우지 않는다
    assert f["source_lagging"] is True  # 대신 원본이 늦는다고 말한다
    assert f["age_sec"] == 1440  # 원본 스냅샷은 24분 전
    assert f["fetch_age_sec"] == 120  # 우리가 받은 건 2분 전


def test_a_stopped_collector_is_flagged():
    """받은 지 오래면 그게 경고다 — 원본 시각이 아니라."""
    f = freshness(
        "2026-08-15T07:14:00Z",
        fetched_at="2026-08-15T07:10:00Z",
        now="2026-08-15T07:38:00Z",
        threshold_sec=900,
    )
    assert f["stale"] is True
    assert f["source_lagging"] is False  # 경고와 겹쳐 두 번 말하지 않는다
    assert f["fetch_age_sec"] == 1680


def test_fresh_on_both_clocks_says_nothing():
    f = freshness(
        "2026-08-15T07:35:00Z",
        fetched_at="2026-08-15T07:36:00Z",
        now="2026-08-15T07:38:00Z",
        threshold_sec=900,
    )
    assert f["stale"] is False
    assert f["source_lagging"] is False


def test_without_a_collection_time_it_judges_by_the_source():
    """수집 시각을 기록하기 전에 쌓인 DB도 그대로 읽힌다."""
    f = freshness("2026-08-15T07:14:00Z", now="2026-08-15T07:38:00Z", threshold_sec=900)
    assert f["stale"] is True
    assert f["fetch_age_sec"] is None
    assert f["source_lagging"] is False


# --- 판정: 해연 1개를 얻는 네 가지 길 -----------------------------------------

ECHO = dict(echo_kind_id=fx.JANYEONG_KIND, echo_normal=fx.JANYEONG_HARP_NORMAL)


def test_four_paths_are_priced_side_by_side():
    row = build_row(
        **BASE,
        prices=fx.PRICES,
        recipe=fx.HAEYEON_HARP_WITH_RECIPE,
        echo_multiplier=10,
        **ECHO,
    )
    assert row["market"]["price"] == 23174  # 해연 구매
    assert row["normal"]["total"] == 15165  # 해연 제작
    assert row["echo_buy"]["total"] == 12700  # 잔영 10개 구매
    assert row["echo_craft"]["total"] == 25930  # 잔영 10개 제작
    assert row["recipe"]["total"] == 8322  # 레시피 제작(조건부, 후보 아님)


def test_cheapest_of_the_four_wins():
    row = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, **ECHO)
    assert row["verdict"] == "echo_buy"
    assert row["cheapest"]["price"] == 12700
    assert row["cheapest"]["label"] == "잔영 구매"


def test_janyeong_craft_is_dearer_than_buying_it():
    """잔영은 사는 게 싸다 — 1개 제작비 2,593 vs 시세 1,270(실측 구조)."""
    row = build_row(**BASE, prices=fx.PRICES, echo_multiplier=1, **ECHO)
    assert row["echo_craft"]["unit"] == fx.JANYEONG_CRAFT_UNIT
    assert row["echo_buy"]["unit"] == fx.JANYEONG_MARKET
    assert row["echo_craft"]["total"] > row["echo_buy"]["total"]


def test_recipe_path_never_wins_the_verdict():
    """레시피 제작은 조건부라 판정 후보가 아니다 — 가장 싼 값인데도."""
    row = build_row(
        **BASE,
        prices=fx.PRICES,
        recipe=fx.HAEYEON_HARP_WITH_RECIPE,
        echo_multiplier=10,
        **ECHO,
    )
    assert row["recipe"]["total"] < row["cheapest"]["price"]
    assert row["verdict"] != "recipe"


def test_multiplier_moves_both_echo_paths():
    def totals(m):
        r = build_row(**BASE, prices=fx.PRICES, echo_multiplier=m, **ECHO)
        return r["echo_buy"]["total"], r["echo_craft"]["total"]

    assert totals(10) == (12700, 25930)
    assert totals(11) == (13970, 28523)
    assert totals(1) == (1270, 2593)


def test_high_multiplier_flips_the_verdict_to_crafting_haeyeon():
    row = build_row(**BASE, prices=fx.PRICES, echo_multiplier=30, **ECHO)
    assert row["verdict"] == "craft"  # 잔영 30개는 38,100 — 해연 제작 15,165보다 비싸다


def test_missing_partner_drops_both_echo_paths():
    """7행: 짝이 되는 잔영이 없으면 그 두 길을 후보에서 뺀다."""
    row = build_row(**BASE, prices=fx.PRICES, echo_kind_id=None, echo_normal=None)
    assert row["echo_buy"]["status"] == "no_counterpart"
    assert row["echo_craft"]["status"] == "no_counterpart"
    assert row["verdict"] == "craft"


def test_sold_out_partner_drops_only_the_buy_path():
    """잔영 매물이 없어도 잔영을 만드는 길은 남는다."""
    prices = {**fx.PRICES}
    prices[fx.JANYEONG_KIND] = {**prices[fx.JANYEONG_KIND], "total_count": 0}
    row = build_row(**BASE, prices=prices, echo_multiplier=10, **ECHO)
    assert row["echo_buy"]["status"] == "no_listing"
    assert row["echo_craft"]["total"] == 25930


def test_no_verdict_when_nothing_is_computable():
    row = build_row(item_id=1, name="x", kind_id=999, normal=None, prices={})
    assert row["verdict"] is None
    assert row["cheapest"] is None


# --- 보유 재료: 전체 시세와 실지출을 나란히 ------------------------------------


def test_owning_material_lowers_out_of_pocket_only():
    """보유분은 실지출에서만 빠진다. 전체 시세는 그대로다 — 그 재료도 팔 수 있다."""
    owned = {281479538461834: 80}  # 망령의 영혼석 80개 = 필요량 전부
    row = build_row(**BASE, prices=fx.PRICES, owned=owned)
    assert row["normal"]["total"] == fx.NORMAL_TOTAL  # 15,165 불변
    assert row["normal"]["out_of_pocket"] == fx.NORMAL_TOTAL - 8240


def test_partial_holding_only_covers_what_it_covers():
    owned = {281479538461834: 30}  # 80개 중 30개만 있다
    row = build_row(**BASE, prices=fx.PRICES, owned=owned)
    assert row["normal"]["out_of_pocket"] == fx.NORMAL_TOTAL - 30 * 103


def test_surplus_holding_does_not_go_negative():
    owned = {281479538461834: 500}  # 필요보다 훨씬 많다
    row = build_row(**BASE, prices=fx.PRICES, owned=owned)
    assert row["normal"]["out_of_pocket"] == fx.NORMAL_TOTAL - 8240


def test_out_of_pocket_matches_total_when_nothing_is_owned():
    row = build_row(**BASE, prices=fx.PRICES)
    assert row["normal"]["out_of_pocket"] == row["normal"]["total"]


def test_holdings_open_a_cheaper_path():
    """재고를 넣으면 실지출이 후보로 들어와 판정이 바뀔 수 있다."""
    owned = {k: 9999 for k in fx.PRICES}
    plain = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, **ECHO)
    held = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, owned=owned, **ECHO)
    assert plain["verdict"] == "echo_buy"
    assert held["verdict"] == "craft_oop"  # 재료가 다 있으면 만드는 게 공짜에 가깝다
    assert held["cheapest"]["price"] == 0


def test_full_price_paths_are_unaffected_by_holdings():
    """전체 시세 값 자체는 재고와 무관하다 — 판정 후보가 하나 늘 뿐이다."""
    owned = {k: 9999 for k in fx.PRICES}
    held = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, owned=owned, **ECHO)
    assert held["normal"]["total"] == fx.NORMAL_TOTAL
    assert held["echo_buy"]["total"] == 12700


def test_margin_is_market_minus_craft():
    """만들어 팔면 남는 돈. 수수료는 반영하지 않는다."""
    row = build_row(**BASE, prices=fx.PRICES)
    assert row["normal"]["margin"] == 23174 - 15165


def test_margin_uses_out_of_pocket_when_materials_are_held():
    owned = {281479538461834: 80}
    row = build_row(**BASE, prices=fx.PRICES, owned=owned)
    assert row["normal"]["margin_out_of_pocket"] == 23174 - (fx.NORMAL_TOTAL - 8240)


def test_margin_is_none_without_a_market_price():
    prices = {**fx.PRICES}
    prices[281489250918530] = {**prices[281489250918530], "total_count": 0}
    row = build_row(**BASE, prices=prices)
    assert row["normal"]["margin"] is None


# --- 거래 불가 재료도 내역에는 남는다 -----------------------------------------

UNTRADABLE = fx.HAEYEON_HARP_NORMAL + [
    {"kind_id": 9369, "name": "세공된 페리도트ZZ", "qty": 2, "can_trade": False}
]


def test_untradable_material_appears_in_the_breakdown():
    """합계엔 안 넣어도 재료 목록에는 있어야 한다 — 필요한 재료인 건 사실이다."""
    row = build_row(**{**BASE, "normal": UNTRADABLE}, prices=fx.PRICES)
    names = [m["name"] for m in row["normal"]["materials"]]
    assert "세공된 페리도트ZZ" in names


def test_untradable_material_costs_nothing_and_has_no_listing():
    row = build_row(**{**BASE, "normal": UNTRADABLE}, prices=fx.PRICES)
    m = next(m for m in row["normal"]["materials"] if m["name"] == "세공된 페리도트ZZ")
    assert (m["unit_price"], m["subtotal"], m["listing_count"]) == (None, 0, 0)
    assert m["untradable"] is True
    assert m["qty"] == 2


def test_untradable_material_does_not_move_the_total():
    row = build_row(**{**BASE, "normal": UNTRADABLE}, prices=fx.PRICES)
    assert row["normal"]["total"] == fx.NORMAL_TOTAL
    assert row["normal"]["status"] == "ok"


def test_untradable_material_is_not_a_shortage_warning():
    """살 수 없는 것과 매물이 모자란 건 다르다."""
    row = build_row(**{**BASE, "normal": UNTRADABLE}, prices=fx.PRICES)
    assert row["normal"]["shortage_warnings"] == []


# --- 실 제작도 판정 후보 -------------------------------------------------------


def test_out_of_pocket_craft_can_win():
    """재고를 넣었으면 그 값으로도 겨룬다 — 실제로 나가는 돈이 그거다."""
    owned = {281479538461834: 80}  # 망령의 영혼석 전부 보유 → 실지출 6,925
    row = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, owned=owned, **ECHO)
    assert row["verdict"] == "craft_oop"
    assert row["cheapest"]["price"] == fx.NORMAL_TOTAL - 8240
    assert row["cheapest"]["label"] == "실 제작"


def test_echo_still_wins_when_it_is_cheaper_than_out_of_pocket():
    owned = {281479782081111: 5}  # 특급 목재만 조금 → 실지출 14,435
    row = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, owned=owned, **ECHO)
    assert row["verdict"] == "echo_buy"  # 12,700 < 14,435


def test_no_out_of_pocket_candidate_without_holdings():
    """가진 게 없으면 실지출은 전체 시세와 같다 — 같은 값을 두 번 세우지 않는다."""
    row = build_row(**BASE, prices=fx.PRICES, echo_multiplier=10, **ECHO)
    assert row["verdict"] != "craft_oop"
