"""API 원형 → 계산이 쓰는 정규화 형태.

원가 계산(cost.py)은 API 스키마를 모른다. 변환은 전부 여기서 끝낸다.

매칭 키는 `재료.itemId` = `시세.codex_item_id` = `아이템 목록.id`다.
이름으로 맞추지 않는다 — 시세 1,226건에 동명 항목이 74건 있다.
"""


def normalize_recipe(detail, untradable_ids=frozenset()):
    """상세 응답 하나 → {"normal": [...], "recipe": [...] | None}.

    `crafting.made_by`는 배열이고 [0]이 일반 제작, [1]이 레시피 제작이다.
    레시피 경로가 없는 아이템(잔영 전체)은 recipe가 None이다.

    재료 객체에는 거래 가능 여부가 없다. 거래 불가 id를 밖에서 받아 표시한다.
    """
    made_by = (detail.get("attributes") or {}).get("crafting", {}).get("made_by")
    if not made_by:
        return None

    def path(entry):
        return [
            {
                "kind_id": g.get("itemId"),
                "name": g["name"],
                "qty": g["count"],
                "can_trade": g.get("itemId") not in untradable_ids,
            }
            for g in entry.get("ingredients", [])
        ]

    return {
        "normal": path(made_by[0]),
        "recipe": path(made_by[1]) if len(made_by) > 1 else None,
    }


def normalize_prices(rows):
    """시세 목록 → {codex_item_id: 시세}.

    codex_item_id가 없는 레코드는 버린다(실측 134건 — 이름도 비어 있다).
    같은 id가 여러 건이면 최저가를 택하되, 매물이 0인 줄은 이기지 못한다 —
    살 수 없는 가격을 최저가로 세우면 원가가 실제보다 낮게 나온다.
    """
    out = {}
    for r in rows:
        key = r.get("codex_item_id")
        if key is None:
            continue
        price, count = r.get("min_price"), r.get("total_count") or 0
        if price is None:
            continue
        cur = out.get(key)
        if cur is None:
            out[key] = {
                "name": r.get("name"),
                "min_price": price,
                "total_count": count,
                "as_of": r.get("last_version"),
            }
            continue
        # 매물이 있는 줄이 없는 줄을 이긴다. 둘 다 있으면 싼 쪽.
        if (count > 0) > (cur["total_count"] > 0) or (
            (count > 0) == (cur["total_count"] > 0) and price < cur["min_price"]
        ):
            out[key] = {
                "name": r.get("name"),
                "min_price": price,
                "total_count": count,
                "as_of": r.get("last_version"),
            }
    return out


def normalize_item(raw, tier=None, base_name=None):
    """아이템 목록 한 건 → items 테이블 행. kind_id 자리에 id를 그대로 쓴다."""
    return {
        "id": raw["id"],
        "name": raw["name"],
        "kind_id": raw["id"],
        "category": raw.get("category"),
        "tier": tier,
        "base_name": base_name,
        "can_trade": raw.get("can_trade", True),
    }
