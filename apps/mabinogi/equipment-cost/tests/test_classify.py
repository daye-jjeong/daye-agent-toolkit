import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from classify import classify_item, echo_partners


def test_haeyeon_equipment():
    assert classify_item("해연의 커브드 하프ZZ") == ("해연", "커브드 하프ZZ")


def test_janyeong_equipment():
    assert classify_item("잔영의 커브드 하프ZZ") == ("잔영", "커브드 하프ZZ")


def test_recipe_item_is_its_own_tier():
    assert classify_item("레시피: 해연의 커브드 하프ZZ") == ("레시피", "커브드 하프ZZ")


def test_unrelated_item_has_no_tier():
    assert classify_item("망령의 영혼석") == (None, "망령의 영혼석")


PAIR = [
    {"id": 1, "name": "해연의 커브드 하프ZZ", "kind_id": 100},
    {"id": 2, "name": "잔영의 커브드 하프ZZ", "kind_id": 200},
]


def test_echo_source_is_always_the_janyeong_of_the_same_kind():
    """등가 칸의 기준은 늘 잔영이다 — '잔영 11개 = 해연 1개'라서다.

    해연 행은 짝이 되는 잔영을, 잔영 행은 자기 자신을 본다.
    상대 등급을 보면 잔영 행에 해연×11이라는 무의미한 값이 찍힌다.
    """
    echo = echo_partners(PAIR)
    assert echo[1]["kind_id"] == 200
    assert echo[2]["kind_id"] == 200


def test_echo_source_blank_when_no_janyeong_of_that_kind():
    """패치로 1:1이 깨지면 등가 비교 칸을 비운다."""
    echo = echo_partners(
        [
            {"id": 1, "name": "해연의 외톨이 검ZZ", "kind_id": 100},
            {"id": 2, "name": "잔영의 커브드 하프ZZ", "kind_id": 200},
        ]
    )
    assert echo[1] is None
    assert echo[2]["kind_id"] == 200


def test_echo_source_ignores_recipe_items():
    echo = echo_partners(
        PAIR
        + [
            {"id": 3, "name": "레시피: 해연의 커브드 하프ZZ", "kind_id": None},
        ]
    )
    assert 3 not in echo


# --- 재료 묶음 ---------------------------------------------------------------

from classify import group_materials

MATS = [
    ("망령의 영혼석", 9283), ("허상의 마력석", 9285), ("특급 목재", 9421),
    ("공명의 영혼석", 9281), ("심해의 마력석", 9287), ("백금강괴", 9395),
]


def test_materials_split_into_three_groups():
    """입력칸이 18개라 섞여 있으면 어디에 넣을지 헤맨다."""
    groups = group_materials(MATS)
    assert [g["label"] for g in groups] == ["영혼석", "마력석", "그 밖의 재료"]


def test_soul_stones_go_together():
    groups = group_materials(MATS)
    assert [n for n, _ in groups[0]["items"]] == ["공명의 영혼석", "망령의 영혼석"]


def test_mana_stones_go_together():
    groups = group_materials(MATS)
    assert [n for n, _ in groups[1]["items"]] == ["심해의 마력석", "허상의 마력석"]


def test_everything_else_lands_in_the_last_group():
    groups = group_materials(MATS)
    assert [n for n, _ in groups[2]["items"]] == ["백금강괴", "특급 목재"]


def test_empty_group_is_dropped():
    groups = group_materials([("특급 목재", 9421)])
    assert [g["label"] for g in groups] == ["그 밖의 재료"]


def test_no_material_is_lost():
    groups = group_materials(MATS)
    assert sum(len(g["items"]) for g in groups) == len(MATS)
