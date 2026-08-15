"""이름으로 등급을 가르고 해연↔잔영을 짝짓는다.

API가 등급을 따로 주지 않는다(`rarity`는 장비에서 빈 문자열이다).
이름 말머리가 유일한 단서라 여기서 처리한다.
"""

import re

TIERS = ("해연", "잔영")
RECIPE_PREFIX = "레시피: "


def classify_item(name):
    """(등급, 등급을 뗀 이름). 해당 없으면 (None, 원래 이름)."""
    if name.startswith(RECIPE_PREFIX):
        _, base = classify_item(name[len(RECIPE_PREFIX) :])
        return "레시피", base

    m = re.match(r"^(%s)의\s+(.+)$" % "|".join(TIERS), name)
    if m:
        return m.group(1), m.group(2)
    return None, name


ECHO_TIER = "잔영"

# 재료 입력칸 묶음. 18칸이 한 줄로 늘어서면 어디에 넣을지 헤맨다.
MATERIAL_GROUPS = [("영혼석", "영혼석"), ("마력석", "마력석")]
OTHER_LABEL = "그 밖의 재료"


def group_materials(materials):
    """[(이름, kind_id)] → 묶음 목록. 빈 묶음은 내보내지 않는다."""
    buckets = {label: [] for _, label in MATERIAL_GROUPS}
    other = []
    for name, kind_id in sorted(materials):
        for suffix, label in MATERIAL_GROUPS:
            if name.endswith(suffix):
                buckets[label].append((name, kind_id))
                break
        else:
            other.append((name, kind_id))

    out = [
        {"label": label, "items": buckets[label]}
        for _, label in MATERIAL_GROUPS
        if buckets[label]
    ]
    if other:
        out.append({"label": OTHER_LABEL, "items": other})
    return out


def echo_partners(items):
    """item_id -> 같은 종류 **잔영** 아이템(없으면 None).

    등가는 "잔영 N개 = 해연 1개"라 기준이 늘 잔영 쪽이다. 잔영을 사는 값과
    만드는 값을 둘 다 세야 해서 kind_id만으로는 부족하다 — 잔영의 레시피를
    찾으려면 그쪽 item_id가 필요하다.

    지금은 38종이 1:1로 대응하지만 패치로 깨질 수 있다 — 짝이 없으면 None을
    넣어 그 두 길을 후보에서 뺀다.
    """
    janyeong = {}
    equipment = []
    for it in items:
        tier, base = classify_item(it["name"])
        if tier not in TIERS:
            continue
        equipment.append((it, base))
        if tier == ECHO_TIER:
            janyeong[base] = it

    return {it["id"]: janyeong.get(base) for it, base in equipment}
