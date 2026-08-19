import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from serve import render_html


def _rep(**over):
    rep = _base()
    rep.update(over)
    rep.setdefault(
        "groups", [{"category": "Weapon", "label": "무기", "rows": rep["rows"]}]
    )
    return rep


def _base():
    rep = {
        "as_of": "2026-08-14T16:17:00Z",
        "freshness": {
            "as_of": "2026-08-14T16:17:00Z",
            "age_sec": 300,
            "stale": False,
            "threshold_sec": 1800,
        },
        "echo_multiplier": 10,
        "sort": "saving",
        "desc": True,
        "has_inventory": False,
        "materials": [],
        "inventory_value": 0,
        "counts": {"total": 1, "recipe_pending": 0},
        "rows": [
            {
                "item_id": 1,
                "name": "해연의 커브드 하프ZZ",
                "tier": "해연",
                "base_name": "커브드 하프ZZ",
                "category": "Weapon",
                "market": {"status": "ok", "price": 23174, "count": 6},
                "normal": {
                    "status": "ok",
                    "total": 15165,
                    "materials": [],
                    "is_lower_bound": True,
                    "excluded_untradable": [],
                    "missing_price": [],
                    "shortage_warnings": [],
                },
                "recipe": None,
                "echo_buy": {
                    "status": "ok",
                    "total": 12700,
                    "multiplier": 10,
                    "unit": 1270,
                },
                "echo_craft": {
                    "status": "ok",
                    "total": 25930,
                    "multiplier": 10,
                    "unit": 2593,
                },
                "cheapest": {"option": "craft", "price": 15165, "label": "해연 제작"},
                "verdict": "craft",
            }
        ],
    }
    return rep


def _two_groups():
    rep = _base()
    hat = {
        **rep["rows"][0],
        "item_id": 2,
        "base_name": "비늘 갑옷 투구ZZ",
        "category": "Hat",
    }
    rep["rows"] = rep["rows"] + [hat]
    rep["groups"] = [
        {"category": "Weapon", "label": "무기", "rows": [rep["rows"][0]]},
        {"category": "Hat", "label": "투구", "rows": [hat]},
    ]
    return rep


def test_categories_get_their_own_heading():
    body = _body(_two_groups())
    assert "무기" in body and "투구" in body
    assert body.index("무기") < body.index("투구")  # 무기가 먼저다


def _thead(rep, **kw):
    return render_html(rep, **kw).split("<thead>")[1].split("</thead>")[0]


def test_recipe_column_can_be_hidden():
    assert ">레시피 제작" in _thead(_rep(), show_recipe=True)
    assert ">레시피 제작" not in _thead(_rep())
    assert "커브드 하프ZZ" in render_html(_rep())  # 행 자체는 남는다


def test_column_toggles_are_checkboxes_above_the_table():
    body = _body(_rep())
    assert 'class="toggles"' in body
    assert body.index('class="toggles"') < body.index("<tbody>")
    assert body.count('type="checkbox"') == 2


def test_optional_columns_are_off_by_default():
    assert ">레시피 제작" not in _thead(_rep())
    assert ">잔영×10 제작" not in _thead(_rep())
    assert ">레시피 제작" in _thead(_rep(), show_recipe=True)


def test_hiding_recipe_keeps_columns_aligned():
    """헤더와 본문 셀 수가 어긋나면 표가 밀린다."""
    for show in (True, False):
        html_ = render_html(_rep(), show_recipe=show)
        head = html_.split("<thead>")[1].split("</thead>")[0].count("<th")
        first = html_.split("<tbody>")[1].split("</tr>")[1]  # 그룹 헤더 다음 첫 행
        assert first.count("<td") == head


def test_verdict_names_the_cheapest_of_four():
    rep = _rep()
    rep["rows"][0]["cheapest"] = {"option": "echo_buy", "price": 12700,
                                  "label": "잔영 구매"}
    rep["rows"][0]["verdict"] = "echo_buy"
    body = _body(rep)
    assert "잔영×10 구매" in body
    assert "10,474" in body  # 해연을 그냥 살 때(23,174) 대비 아끼는 금액


def test_echo_buy_is_always_shown():
    body = _body(_rep())
    assert ">잔영×10 구매" in body
    assert "12,700" in body


def test_echo_craft_column_can_be_switched_on():
    assert ">잔영×10 제작" in _thead(_rep(), show_echo_craft=True)
    assert "25,930" in render_html(_rep(), show_echo_craft=True)


def test_detail_always_shows_every_path():
    """체크박스는 열만 끈다 — 상세의 재료표는 그대로 나온다."""
    rep = _rep()
    rep["rows"][0]["recipe"] = _path((("특급 목재", 5, 146, 0),))
    rep["rows"][0]["echo_craft"] = {**rep["rows"][0]["echo_craft"],
                                    "path": _path((("운철괴", 3, 74, 0),))}
    body = _body(rep)          # 두 열 모두 꺼진 기본 상태
    assert "레시피 제작</h5>" in body
    assert "잔영 1개 제작</h5>" in body


def test_echo_columns_show_the_unit_price():
    """N개 값만 보면 배수 감각을 잃는다 — 1개 단가를 붙인다."""
    assert "@1,270" in _body(_rep())


def test_verdict_says_buy_when_market_wins():
    rep = _rep()
    rep["rows"][0]["cheapest"] = {"option": "buy", "price": 23174,
                                  "label": "해연 구매"}
    rep["rows"][0]["verdict"] = "buy"
    assert "해연 구매" in _body(rep)


def test_page_states_cost_is_a_lower_bound():
    assert "하한선" in render_html(_rep())


def test_page_always_shows_snapshot_time():
    assert "2026-08-14T16:17:00Z" in render_html(_rep())


def _body(rep):
    """<style> 블록을 뺀 본문. CSS에도 stale이 들어 있어 통째로 검사하면 늘 걸린다."""
    return render_html(rep).split("</style>", 1)[1]


def test_fresh_snapshot_has_no_warning():
    assert "bar stale" not in _body(_rep())


def test_stale_snapshot_renders_warning():
    body = _body(
        _rep(
            freshness={
                "as_of": "2026-08-14T16:17:00Z",
                "age_sec": 7200,
                "stale": True,
                "threshold_sec": 1800,
            }
        )
    )
    assert "bar stale" in body
    assert "수집기가 멈췄는지" in body


def test_never_collected_prices_is_flagged():
    body = render_html(_rep(freshness=None, as_of=None)).split("</style>")[1]
    assert "한 번도 받지 못했다" in body


def test_multiplier_appears_in_header_and_form():
    body = render_html(_rep(echo_multiplier=7)).split("</style>")[1]
    assert "잔영×7 구매" in body
    assert 'value="7"' in body


def test_pending_recipes_are_announced():
    body = render_html(_rep(counts={"total": 76, "recipe_pending": 37})).split(
        "</style>"
    )[1]
    assert "37종을 아직 못 받았다" in body


def test_absent_recipe_path_renders_dash_not_zero():
    body = render_html(_rep()).split("</style>")[1]
    assert "<td>0</td>" not in body


def test_uncomputable_path_says_so():
    rep = _rep()
    rep["rows"][0]["normal"] = {
        "status": "uncomputable",
        "total": None,
        "materials": [],
        "excluded_untradable": [],
        "missing_price": ["희귀 재료"],
        "shortage_warnings": [],
        "is_lower_bound": True,
    }
    assert "계산 불가" in render_html(rep)


def test_no_listing_gives_no_verdict():
    rep = _rep()
    rep["rows"][0]["market"] = {"status": "no_listing", "price": None, "count": 0}
    body = render_html(rep).split("</style>")[1]
    assert "매물 없음" in body


# --- 가진 재료 입력칸 ----------------------------------------------------------

MATS = [("망령의 영혼석", 9283), ("특급 목재", 9421)]


def test_inventory_inputs_appear_per_material():
    body = _body(_rep())
    html_ = render_html(_rep(), materials=MATS)
    assert 'name="qty_9283"' in html_
    assert 'name="qty_12345"' not in html_
    assert "망령의 영혼석" in html_
    assert "가진 재료" in body


def test_inventory_form_sits_above_the_table():
    """입력칸이 표 아래 있으면 스크롤해야 보인다."""
    html_ = render_html(_rep(), materials=MATS)
    assert html_.index('class="inv"') < html_.index("<tbody>")


def test_saved_quantities_are_filled_back_in():
    html_ = render_html(_rep(), materials=MATS, owned={9283: 80})
    assert 'name="qty_9283" min="0" step="1" value="80"' in html_


def test_unheld_material_defaults_to_zero():
    """빈 칸보다 0이 낫다 — 안 가졌다는 걸 눈으로 확인할 수 있다."""
    html_ = render_html(_rep(), materials=MATS, owned={9283: 80})
    assert 'name="qty_9421" min="0" step="1" value="0"' in html_


def test_inputs_are_grouped_by_material_kind():
    html_ = render_html(_rep(), materials=MATS)
    assert "영혼석</h4>" in html_
    assert "그 밖의 재료</h4>" in html_
    assert html_.index("영혼석</h4>") < html_.index("그 밖의 재료</h4>")


def test_unsaved_edits_survive_a_reload():
    """저장을 누르기 전에 페이지가 바뀌어도 입력이 날아가지 않는다."""
    html_ = render_html(_rep(), materials=MATS)
    assert "localStorage" in html_


def test_form_stays_folded_even_with_holdings():
    """열 체크박스를 눌러 갱신될 때마다 펼쳐지면 표가 아래로 밀린다."""
    assert 'class="inv" open' not in render_html(_rep(), materials=MATS, owned={9283: 80})
    assert 'class="inv" open' not in render_html(_rep(), materials=MATS)


def test_rejected_inputs_are_reported():
    html_ = render_html(_rep(), materials=MATS, rejected=2)
    assert "2칸을 알아듣지 못해" in html_


def test_out_of_pocket_is_its_own_sortable_column():
    """한 칸에 두 값이 붙어 있으면 각각 정렬할 수 없다."""
    rep = _rep()
    rep["has_inventory"] = True
    rep["rows"][0]["normal"]["out_of_pocket"] = 4200
    body = _body(rep)
    assert "15,165" in body                 # 전체 시세
    assert "4,200" in body                  # 실지출
    assert ">실 제작" in body               # 헤더가 따로 있다
    assert "sort=craft_oop" in body         # 그 열로 정렬된다


def test_no_out_of_pocket_column_without_holdings():
    body = _body(_rep())
    assert ">실 제작" not in body
    assert "sort=craft&" in body            # 제작 열 정렬은 그대로


# --- 새로고침 버튼 -------------------------------------------------------------

def test_reload_button_and_progress_bar_are_present():
    body = _body(_rep())
    assert 'id="reload"' in body
    assert 'id="fill"' in body       # 진행바
    assert 'id="ptext"' in body      # 몇 건 받았는지


def test_reload_script_is_inlined():
    """외부 파일 없이 페이지 하나로 돈다."""
    html_ = render_html(_rep())
    assert "/refresh/status" in html_
    assert "<script>" in html_


def test_no_reload_button_before_the_first_collection():
    """받은 게 없으면 신선도 줄 자체가 없다 — 버튼도 거기 붙어 있다."""
    body = _body(_rep(freshness=None, as_of=None))
    assert "한 번도 받지 못했다" in body


# --- 재료 상세 표 -------------------------------------------------------------

def _path(owned_pairs=()):
    """(이름, 필요, 단가, 보유) → craft_path 모양."""
    mats = [
        {"name": n, "qty": q, "owned": o, "need": q - o, "unit_price": u,
         "subtotal": u * q, "listing_count": 9999, "shortage": False}
        for n, q, u, o in owned_pairs
    ]
    return {
        "status": "ok",
        "total": sum(m["subtotal"] for m in mats),
        "out_of_pocket": sum(m["unit_price"] * m["need"] for m in mats),
        "materials": mats, "excluded_untradable": [], "missing_price": [],
        "shortage_warnings": [], "is_lower_bound": True,
    }


THREE = (("망령의 영혼석", 80, 100, 30), ("특급 목재", 5, 146, 0),
         ("야생의 영혼석", 75, 34, 75))


def _detail(show_owned=True):
    rep = _rep()
    rep["rows"][0]["normal"] = _path(THREE)
    rep["has_inventory"] = show_owned
    return _body(rep)


def test_materials_are_ordered_by_cost_share():
    """원가를 지배하는 재료가 맨 위로 — 그게 보려는 이유다."""
    body = _detail()
    order = [body.index(n) for n in ("망령의 영혼석", "야생의 영혼석", "특급 목재")]
    assert order == sorted(order)   # 8,000 > 2,550 > 730


def test_held_quantity_shows_in_the_detail():
    body = _detail()
    assert ">보유<" in body
    assert ">살 것<" in body


def test_fully_stocked_material_needs_nothing():
    body = _detail()
    assert "야생의 영혼석" in body
    assert ">75<" in body  # 필요 75 = 보유 75


def test_detail_has_a_total_row():
    """재료를 다 더하면 얼마인지 표 안에서 끝나야 한다."""
    body = _detail()
    assert "합계" in body
    assert "11,280" in body  # 8,000 + 730 + 2,550


def test_total_row_carries_out_of_pocket_too():
    body = _detail()
    assert "5,730" in body  # 8,000-3,000 + 730 + 0


def test_owned_columns_hidden_without_inventory():
    body = _detail(show_owned=False)
    assert ">보유<" not in body
    assert "합계" in body  # 합계는 늘 나온다


# --- 상세는 아래에 펼쳐지는 별도 행 --------------------------------------------

def test_detail_is_its_own_row_not_a_swollen_cell():
    """값 칸은 한 줄로 유지되고, 상세는 그 아래 행으로 열린다."""
    body = _detail()
    assert 'class="detail"' in body
    assert "<details>" not in body      # 셀 안에서 부풀지 않는다


def test_detail_row_spans_the_whole_table():
    import re
    body = _detail()
    m = re.search(r'<tr class="detail"[^>]*><td colspan="(\d+)"', body)
    assert m, "상세 행이 없다"
    head = body.split("<thead>")[1].split("</thead>")[0].count("<th")
    assert int(m.group(1)) == head


def test_row_is_clickable_to_open_its_detail():
    body = _detail()
    assert 'class="row"' in body
    assert "data-detail=" in body


def test_detail_starts_hidden():
    body = _detail()
    assert 'class="detail" hidden' in body


def test_material_row_shows_both_subtotals():
    """소계 옆에 실 소계 — 가진 걸 빼면 실제로 얼마 나가는지."""
    body = _detail()
    assert ">소계<" in body
    assert ">실 소계<" in body
    assert ">5,000<" in body   # 망령 (80-30) × 100


def test_no_real_subtotal_column_without_inventory():
    body = _detail(show_owned=False)
    assert ">실 소계<" not in body
    assert ">소계<" in body


# --- 무엇이 빠졌는지 라벨이 정확히 말한다 --------------------------------------

from serve import excluded_label


def test_recipe_path_says_recipe():
    assert excluded_label(["레시피: 해연의 숏소드ZZ"]) == "레시피 제외"


def test_ordinary_untradable_material_is_named():
    """페리도트 계열에서 빠지는 건 레시피가 아니라 재료다."""
    assert excluded_label(["세공된 페리도트ZZ"]) == "세공된 페리도트ZZ 제외"


def test_several_exclusions_are_counted():
    label = excluded_label(["세공된 페리도트ZZ", "레시피: x"])
    assert label == "거래 불가 2종 제외"


def test_nothing_excluded_means_no_label():
    assert excluded_label([]) == ""


# --- 맨 위 안내 ---------------------------------------------------------------

def test_intro_states_the_equivalence():
    assert "잔영 11개" in _body(_rep())


def test_intro_states_the_weapon_mix():
    assert "다른 잔영 10개 + 내 무기 1개" in _body(_rep())


def test_intro_states_the_lower_bound():
    assert "하한선" in _body(_rep())


def test_old_footnotes_are_gone():
    body = _body(_rep())
    assert body.count("하한선") == 1          # 위에 한 번만
    assert "커뮤니티에서 통용되는" not in body


# --- 줄마다 최저 칸 표시 -------------------------------------------------------

def _win(option):
    rep = _rep()
    rep["rows"][0]["cheapest"] = {"option": option, "price": 1, "label": "x"}
    rep["rows"][0]["verdict"] = option
    return _body(rep)


def test_winning_cell_is_marked():
    assert 'class="win"' in _win("craft")


def test_only_one_cell_wins_per_row():
    assert _win("craft").count('class="win"') == 1


def test_the_mark_follows_the_cheapest_option():
    import re
    for opt, col in (("buy", 1), ("craft", 3), ("echo_buy", 4)):
        row = re.search(r'<tr class="row".*?</tr>', _win(opt), re.S).group()
        cells = re.findall(r"<td[^>]*>", row)
        assert 'class="win"' in cells[col], f"{opt} → {col}번째 칸이어야 한다"


def test_no_mark_without_a_verdict():
    rep = _rep()
    rep["rows"][0]["cheapest"] = None
    rep["rows"][0]["verdict"] = None
    assert 'class="win"' not in _body(rep)


def test_out_of_pocket_cell_can_win():
    """실 제작이 최저면 그 칸에 표시가 붙어야 한다."""
    rep = _rep()
    rep["has_inventory"] = True
    rep["rows"][0]["normal"]["out_of_pocket"] = 4200
    rep["rows"][0]["cheapest"] = {"option": "craft_oop", "price": 4200,
                                  "label": "실 제작"}
    rep["rows"][0]["verdict"] = "craft_oop"
    body = _body(rep)
    import re
    row = re.search(r'<tr class="row".*?</tr>', body, re.S).group()
    cells = re.findall(r"<td[^>]*>", row)
    assert 'class="win"' in cells[4]      # 아이템·구매·매물·제작 다음이 실 제작
    assert body.count('class="win"') == 1


def test_clear_button_sits_next_to_save():
    html_ = render_html(_rep(), materials=MATS, owned={9283: 80})
    assert 'id="clear-inv"' in html_
    assert "모두 비우기" in html_


def test_clearing_does_not_submit_on_its_own():
    """실수로 눌러도 저장 전이면 되돌릴 수 있어야 한다."""
    import re
    html_ = render_html(_rep(), materials=MATS)
    btn = re.search(r'<button id="clear-inv"[^>]*>', html_).group()
    assert 'type="button"' in btn      # submit이 아니다
    assert "clear-inv" in html_.split("<script>")[1]   # JS가 칸만 채운다


# --- 수집 실패는 화면까지 올라온다 ----------------------------------------------
#
# 공개판 방문자는 서버 콘솔을 못 본다. 신선도 띠는 임계(15분)를 넘어야 뜨고,
# 떠도 "낡았다"만 말한다 — 왜인지가 빠지면 고칠 수가 없다.


def test_collector_failure_shows_the_reason():
    html_ = render_html(
        _rep(), public=True, collector={"error": "URLError: timed out", "failures": 3}
    )
    assert "URLError: timed out" in html_
    assert "3번" in html_


def test_healthy_collector_says_nothing():
    html_ = render_html(_rep(), public=True, collector={"error": None, "failures": 0})
    assert "수집 실패" not in html_


def test_no_collector_status_says_nothing():
    """로컬판에는 주기 수집기가 없다."""
    assert "수집 실패" not in render_html(_rep())


# --- 원본이 늦는 것과 우리가 멈춘 것을 화면에서 가른다 --------------------------


def _fresh(**over):
    f = {
        "as_of": "2026-08-15T07:35:00Z",
        "age_sec": 180,
        "fetched_at": "2026-08-15T07:36:00Z",
        "fetch_age_sec": 120,
        "stale": False,
        "source_lagging": False,
        "threshold_sec": 900,
    }
    f.update(over)
    return _rep(freshness=f)


def test_normal_bar_shows_when_we_fetched_it():
    html_ = render_html(_fresh())
    assert "07:36 UTC</time>에 받음" in html_
    assert "stale" not in html_.split("<body>")[1].split("</div>")[0]


def test_lagging_source_is_stated_not_warned():
    """원본이 새 값을 안 주는 건 우리 잘못이 아니다 — 노란 경고를 띄우지 않는다."""
    html_ = render_html(
        _fresh(as_of="2026-08-15T07:14:00Z", age_sec=1440, source_lagging=True)
    )
    assert "원본이 그 뒤로 새 값을 안 준다" in html_
    assert "07:36 UTC</time>에 받음" in html_
    bar = html_.split('<div class="bar')[1]
    assert not bar.startswith(" stale")


def test_a_stopped_collector_warns_with_the_fetch_time():
    """경고는 받은 시각을 말한다 — 원본 시각은 여기서 답이 아니다."""
    html_ = render_html(
        _fresh(fetched_at="2026-08-15T07:10:00Z", fetch_age_sec=1680, stale=True)
    )
    assert "마지막 수집" in html_
    assert "07:10" in html_
    assert "수집기가 멈췄는지 확인할 것" in html_
    assert 'class="bar stale"' in html_


def test_old_databases_without_a_fetch_time_still_render():
    """수집 시각을 기록하기 전에 쌓인 DB."""
    html_ = render_html(
        _fresh(fetched_at=None, fetch_age_sec=None, age_sec=4380, stale=True)
    )
    assert "에 받음" not in html_
    assert 'class="bar stale"' in html_


def test_intro_explains_what_the_minus_number_is_measured_against():
    """"−6,861"만 있으면 뭐 대비인지 알 수 없다 — 실제로 그 질문이 나왔다."""
    html_ = render_html(_rep())
    intro = html_.split('<ul class="intro">')[1].split("</ul>")[0]
    assert "해연 구매가" in intro


# --- 재료 단가표 ---------------------------------------------------------------
#
# 실측: 망령의 영혼석이 하루에 69~108로 움직인다. 표에 뜬 단가가 그 범위의
# 어디쯤인지 모르면 비싼 때 산다.


def _mat(**over):
    m = {
        "name": "망령의 영혼석", "kind_id": 9283, "price": 100, "count": 5210,
        "owned": 76, "value": 7600,
        "trend": {"days": 14, "closes": [68, 74, 72, 66, 61, 63, 64, 60, 64, 67, 96, 82, 92, 95],
                  "low": 50, "high": 108, "today_low": 80, "today_high": 104,
                  "verdict": "expensive"},
    }
    m.update(over)
    return m


def _inv(mats, value=7600, owned=None):
    return render_html(
        _rep(materials=mats, inventory_value=value), materials=MATS,
        owned=owned if owned is not None else {9283: 76},
    ).split('<details class="inv"')[1].split("</details>")[0]


def test_the_price_sits_next_to_its_input():
    body = _inv([_mat()])
    assert "100" in body
    assert 'name="qty_9283"' in body


def test_a_sparkline_is_drawn_from_the_closes():
    body = _inv([_mat()])
    assert "<svg" in body and "polyline" in body


def test_the_two_week_range_brackets_the_sparkline():
    """선만 있으면 오르는 중인지만 알고 "2주 전엔 얼마였나"에 답하지 못한다."""
    body = _inv([_mat()])
    line = body.split('<span class="mtrend">')[1].split("</span></label>")[0]
    assert "50" in line and "108" in line          # 2주 최저·최고
    assert line.index("50") < line.index("<svg") < line.index("108")


def test_todays_range_moved_into_the_chart():
    """좁은 칸에 다 못 넣는다. 오늘 폭은 펼침 차트의 마지막 띠가 준다."""
    assert "오늘" not in _inv([_mat()])


def test_an_expensive_material_is_called_out():
    assert "비싼 편" in _inv([_mat()])


def test_a_cheap_material_is_called_out():
    body = _inv([_mat(price=52, trend={**_mat()["trend"], "verdict": "cheap"})])
    assert "싼 편" in body


def test_a_flat_material_says_fixed_not_expensive():
    """특급 목재는 14일 내내 146이다."""
    body = _inv([_mat(name="특급 목재", price=146,
                      trend={**_mat()["trend"], "verdict": "flat", "low": 146,
                             "high": 146, "today_low": 146, "today_high": 146})])
    assert "고정" in body
    assert "비싼 편" not in body and "싼 편" not in body


def test_a_material_without_candles_still_shows_its_price():
    body = _inv([_mat(trend=None)])
    assert "100" in body
    assert "<svg" not in body


def test_inventory_value_is_shown():
    assert "7,600" in _inv([_mat()])


def test_no_value_line_without_inventory():
    body = _inv([_mat(owned=0, value=0)], value=0, owned={})
    assert "재고 가치" not in body


# --- 30일 범위 띠 차트 ---------------------------------------------------------
#
# 실측 30일: 최저 50(8/9), 최고 139(8/17), 현재가 105.

CHART = {
    "days": 30,
    "points": [
        {"date": "2026-07-20", "low": 71, "high": 134, "close": 92,
         "x": 0.0, "y_low": 76.4, "y_high": 5.6, "y_close": 52.8},
        {"date": "2026-08-09", "low": 50, "high": 72, "close": 60,
         "x": 280.0, "y_low": 150.0, "y_high": 75.3, "y_close": 88.8},
        {"date": "2026-08-17", "low": 89, "high": 139, "close": 117,
         "x": 480.0, "y_low": 56.2, "y_high": 0.0, "y_close": 24.7},
        {"date": "2026-08-19", "low": 89, "high": 117, "close": 111,
         "x": 560.0, "y_low": 56.2, "y_high": 24.7, "y_close": 31.5},
    ],
    "low": {"date": "2026-08-09", "value": 50, "x": 280.0, "y": 150.0},
    "high": {"date": "2026-08-17", "value": 139, "x": 480.0, "y": 0.0},
    "y_min": 50, "y_max": 139, "flat": False,
    "now_price": 105, "now_y": 57.3,
    "ticks": [{"value": 139, "y": 0.0}, {"value": 94, "y": 75.0},
              {"value": 50, "y": 150.0}],
    "width": 560, "height": 150,
    "as_of": "2026-08-19", "stale_days": 0,
}
# 8/9와 8/17 사이가 비어 있다 — 이어 그리면 없는 값을 직선으로 메우게 된다.
CHART["segments"] = [CHART["points"][:2], CHART["points"][2:]]


def _chart_box(mat):
    return _inv([mat]).split('<div class="mchart"')[1].split("</div>")[0]


def test_the_name_and_the_sparkline_open_the_chart():
    body = _inv([_mat(chart=CHART)])
    assert 'class="mname" data-chart="mc9283"' in body
    assert '<svg data-chart="mc9283"' in body
    assert 'id="mc9283"' in body


def test_the_quantity_box_does_not_open_the_chart():
    """값을 넣으려다 차트가 열리면 방해다."""
    body = _inv([_mat(chart=CHART)])
    box = body.split('<input type="number"')[1].split(">")[0]
    assert "data-chart" not in box


def test_the_chart_starts_folded():
    assert 'class="mchart" id="mc9283" hidden' in _inv([_mat(chart=CHART)])


def test_the_band_is_one_filled_area_not_a_row_of_bars():
    """둘 다 그려 비교했다. 막대는 30개를 하나씩 읽게 하고 종가선을 가린다."""
    box = _chart_box(_mat(chart=CHART))
    assert "<polygon" in box
    assert "<rect" not in box


def test_the_band_breaks_where_a_day_is_missing():
    """없는 데이터를 직선으로 메우면 그 구간에 값이 있었다고 말하는 것이다."""
    box = _chart_box(_mat(chart=CHART))
    assert box.count("<polygon") == 2      # 구간 2개
    assert box.count("<polyline") == 2     # 종가선도 같이 끊긴다


def test_an_unbroken_history_draws_one_band():
    whole = dict(CHART, segments=[CHART["points"]])
    box = _chart_box(_mat(chart=whole))
    assert box.count("<polygon") == 1 and box.count("<polyline") == 1


def test_a_lone_day_is_marked_even_though_it_makes_no_area():
    """앞뒤가 다 빈 하루는 면도 선도 안 나온다 — 점이라도 남겨야 사라지지 않는다."""
    lone = dict(CHART, segments=[CHART["points"][:2], CHART["points"][2:3],
                                 CHART["points"][3:]])
    box = _chart_box(_mat(chart=lone))
    assert box.count("<polygon") == 1      # 2점짜리 구간 하나만 면이 된다
    assert "<circle" in box


def test_the_low_and_high_days_are_labelled():
    box = _chart_box(_mat(chart=CHART))
    assert "8/9 최저 50" in box
    assert "8/17 최고 139" in box


def test_the_current_price_crosses_the_chart():
    box = _chart_box(_mat(chart=CHART))
    assert "지금 105" in box
    assert 'class="nowline"' in box


def test_a_material_without_history_says_so_instead_of_drawing_zero():
    """빈 차트를 그리면 데이터가 있는데 값이 0인 줄 안다."""
    box = _chart_box(_mat(chart=None))
    assert "시세 이력 없음" in box
    assert "<polyline" not in box


def test_a_fresh_chart_does_not_nag_about_its_date():
    assert "기준" not in _chart_box(_mat(chart=CHART))


def test_a_stale_chart_carries_its_date_without_the_yellow_bar():
    """곁다리 실패로 전체를 경고 상태로 만들지 않는다."""
    stale = dict(CHART, as_of="2026-08-17", stale_days=2)
    html_ = render_html(_rep(materials=[_mat(chart=stale)]), materials=MATS,
                        owned={9283: 76})
    assert "8/17 기준" in html_
    assert 'class="bar stale"' not in html_


def test_a_material_stuck_at_one_price_does_not_repeat_it_three_times():
    """백금강괴는 30일 내내 132다. `132 132 132`는 읽을 게 없다."""
    fixed = {**_mat()["trend"], "verdict": "flat", "low": 132, "high": 132,
             "closes": [132] * 14}
    line = _inv([_mat(name="백금강괴", price=132, trend=fixed)])
    line = line.split('<span class="mtrend">')[1].split("</span></label>")[0]
    assert line.count("132") == 1
    assert "고정" in line


def test_a_flat_chart_drops_the_high_and_low_markers():
    """같은 점에 "최고 132"와 "최저 132"가 겹쳐 봐야 읽을 게 없다."""
    flat = dict(
        CHART, flat=True, y_min=131.5, y_max=132.5, now_price=132, now_y=75.0,
        segments=[CHART["points"]],
        ticks=[{"value": 132, "y": 75.0}],
        low={"date": "2026-07-20", "value": 132, "x": 0.0, "y": 75.0},
        high={"date": "2026-07-20", "value": 132, "x": 0.0, "y": 75.0},
    )
    box = _chart_box(_mat(name="백금강괴", price=132, chart=flat))
    assert "최고" not in box and "최저" not in box
    assert "붙박여 움직이지 않았다" in box
    assert box.count("132") == 3      # 눈금 1 · 지금 1 · 안내문 1
