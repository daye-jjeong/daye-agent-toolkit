import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from inventory import parse_inventory_form
from store import Store

VALID = {9283, 9421, 9279}


def test_parses_quantities_by_kind_id():
    owned, rejected = parse_inventory_form(
        {"qty_9283": ["80"], "qty_9421": ["12"]}, VALID)
    assert owned == {9283: 80, 9421: 12}
    assert rejected == []


def test_blank_and_zero_mean_not_held():
    owned, rejected = parse_inventory_form(
        {"qty_9283": [""], "qty_9421": ["0"]}, VALID)
    assert owned == {}
    assert rejected == []


def test_comma_grouped_number_is_accepted():
    owned, _ = parse_inventory_form({"qty_9283": ["1,200"]}, VALID)
    assert owned == {9283: 1200}


def test_non_numeric_is_reported_not_swallowed():
    owned, rejected = parse_inventory_form(
        {"qty_9283": ["여든개"], "qty_9421": ["5"]}, VALID)
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
        {"echo": ["10"], "sort": ["market"], "qty_9283": ["7"]}, VALID)
    assert owned == {9283: 7}
    assert rejected == []


# --- 저장소 -------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    s = Store(str(tmp_path / "i.db"))
    s.init()
    return s


def test_inventory_roundtrip(db):
    db.save_inventory({9283: 80, 9421: 12})
    assert db.inventory() == {9283: 80, 9421: 12}


def test_saving_replaces_the_whole_list(db):
    """화면에서 지운 줄은 사라져야 한다. 병합하면 지울 방법이 없다."""
    db.save_inventory({9283: 80, 9421: 12})
    db.save_inventory({9283: 5})
    assert db.inventory() == {9283: 5}


def test_empty_inventory_is_empty_dict(db):
    assert db.inventory() == {}


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
