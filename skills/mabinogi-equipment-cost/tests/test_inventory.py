import os
import sys
from http.cookies import SimpleCookie

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from inventory import (
    COOKIE_NAME,
    decode_inventory,
    encode_inventory,
    inventory_cookie_header,
    parse_inventory_form,
    read_inventory_cookie,
)
from store import Store

VALID = {9283, 9421, 9279}


def test_parses_quantities_by_kind_id():
    owned, rejected = parse_inventory_form(
        {"qty_9283": ["80"], "qty_9421": ["12"]}, VALID
    )
    assert owned == {9283: 80, 9421: 12}
    assert rejected == []


def test_blank_and_zero_mean_not_held():
    owned, rejected = parse_inventory_form({"qty_9283": [""], "qty_9421": ["0"]}, VALID)
    assert owned == {}
    assert rejected == []


def test_comma_grouped_number_is_accepted():
    owned, _ = parse_inventory_form({"qty_9283": ["1,200"]}, VALID)
    assert owned == {9283: 1200}


def test_non_numeric_is_reported_not_swallowed():
    owned, rejected = parse_inventory_form(
        {"qty_9283": ["여든개"], "qty_9421": ["5"]}, VALID
    )
    assert owned == {9421: 5}
    assert rejected == ["qty_9283"]


def test_negative_is_rejected():
    _, rejected = parse_inventory_form({"qty_9283": ["-3"]}, VALID)
    assert rejected == ["qty_9283"]


def test_unknown_material_id_is_rejected():
    _, rejected = parse_inventory_form({"qty_1234": ["5"]}, VALID)
    assert rejected == ["qty_1234"]


def test_other_form_fields_are_ignored():
    owned, rejected = parse_inventory_form(
        {"echo": ["10"], "sort": ["market"], "qty_9283": ["7"]}, VALID
    )
    assert owned == {9283: 7}
    assert rejected == []


# --- 쿠키 인코딩 ---------------------------------------------------------------
#
# 재고는 브라우저에 산다. 서버 DB에 두면 여러 사람이 한 서버를 쓸 때
# 재고가 전원 공유가 된다.


def test_encoding_is_readable():
    assert encode_inventory({9283: 80, 9421: 12}) == "9283:80.9421:12"


def test_encoding_is_stable_regardless_of_dict_order():
    """같은 재고면 같은 쿠키다 — 안 그러면 Set-Cookie가 매번 달라진다."""
    assert encode_inventory({9421: 12, 9283: 80}) == encode_inventory(
        {9283: 80, 9421: 12}
    )


def test_empty_inventory_encodes_to_empty_string():
    assert encode_inventory({}) == ""


def test_roundtrip():
    owned = {9283: 80, 9421: 12, 9279: 3}
    assert decode_inventory(encode_inventory(owned), VALID) == owned


def test_encoded_value_needs_no_cookie_quoting():
    """쉼표를 구분자로 쓰면 SimpleCookie가 값을 통째로 따옴표로 감싼다."""
    c = SimpleCookie()
    c[COOKIE_NAME] = encode_inventory({9283: 80, 9421: 12})
    assert '"' not in c.output()


def test_decoding_drops_unknown_material_but_keeps_the_rest():
    """패치로 재료가 바뀌면 여기서 조용히 정리된다."""
    assert decode_inventory("9283:80.1234:5", VALID) == {9283: 80}


def test_decoding_drops_broken_entries():
    assert decode_inventory("9283:80.깨짐.9421:x.:.9279", VALID) == {9283: 80}


def test_decoding_drops_non_positive():
    assert decode_inventory("9283:-3.9421:0.9279:5", VALID) == {9279: 5}


def test_decoding_nothing_is_an_empty_dict():
    assert decode_inventory("", VALID) == {}
    assert decode_inventory(None, VALID) == {}


# --- 쿠키 헤더 -----------------------------------------------------------------


def test_reads_our_cookie_from_among_others():
    header = "theme=dark; %s=9283:80; sid=abc" % COOKIE_NAME
    assert read_inventory_cookie(header, VALID) == {9283: 80}


def test_no_cookie_means_no_inventory():
    assert read_inventory_cookie("theme=dark", VALID) == {}
    assert read_inventory_cookie(None, VALID) == {}


def test_malformed_cookie_header_does_not_crash():
    assert read_inventory_cookie("=;;garbage", VALID) == {}


def test_set_cookie_survives_a_browser_restart():
    header = inventory_cookie_header({9283: 80})
    assert f"{COOKIE_NAME}=9283:80" in header
    assert "Max-Age=31536000" in header  # 1년
    assert "Path=/" in header
    assert "SameSite=Lax" in header
    assert "HttpOnly" in header  # 서버만 읽는다


def test_clearing_the_inventory_deletes_the_cookie():
    """빈 값을 남기면 다음 요청에도 계속 실린다. 지우는 게 맞다."""
    header = inventory_cookie_header({})
    assert "Max-Age=0" in header


# --- 저장소 -------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    s = Store(str(tmp_path / "i.db"))
    s.init()
    return s


def test_store_does_not_keep_inventory(db):
    """재고는 브라우저에 산다. 서버가 들고 있으면 방문자끼리 섞인다."""
    assert not hasattr(db, "inventory")
    assert not hasattr(db, "save_inventory")


def _legacy_table(db, rows):
    """재고를 서버에 두던 시절의 DB를 흉내낸다."""
    import sqlite3

    with sqlite3.connect(db.path) as c:
        c.execute("CREATE TABLE inventory (kind_id INTEGER PRIMARY KEY, qty INTEGER)")
        c.executemany("INSERT INTO inventory VALUES (?,?)", rows)


def test_legacy_inventory_moves_out_exactly_once(db):
    """예전 재고는 브라우저로 한 번 넘기고 서버에서 없앤다.

    남겨 두면 다음 방문자가 남의 재고를 물려받는다.
    """
    _legacy_table(db, [(9283, 76), (9421, 25)])
    assert db.take_legacy_inventory() == {9283: 76, 9421: 25}
    assert db.take_legacy_inventory() == {}


def test_no_legacy_table_is_not_an_error(db):
    assert db.take_legacy_inventory() == {}


def test_material_index_comes_from_collected_recipes(db):
    db.save_items(
        [
            {
                "id": 1,
                "name": "해연의 검ZZ",
                "kind_id": 1,
                "tier": "해연",
                "base_name": "검ZZ",
                "can_trade": True,
            }
        ]
    )
    db.save_recipe(
        1,
        "normal",
        [
            {"kind_id": 9283, "name": "망령의 영혼석", "qty": 80, "can_trade": True},
            {
                "kind_id": 900,
                "name": "레시피: 해연의 검ZZ",
                "qty": 1,
                "can_trade": False,
            },
        ],
    )
    idx = db.material_index()
    assert idx["망령의 영혼석"] == 9283
    assert "레시피: 해연의 검ZZ" not in idx  # 거래 불가는 보유 입력 대상이 아니다
