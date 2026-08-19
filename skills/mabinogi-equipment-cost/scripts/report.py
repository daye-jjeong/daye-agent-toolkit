"""저장소 → 비교표. 계산은 cost.py가, 저장은 store.py가 한다.

여기는 둘을 잇기만 한다.
"""

from classify import echo_partners
from cost import DEFAULT_ECHO_MULTIPLIER, DEFAULT_STALE_SEC, build_row, freshness
from trend import material_chart, material_trend

EQUIPMENT_TIERS = ("해연", "잔영")
TARGET_TIER = "해연"  # 표의 행. 잔영은 등가 경로로만 들어온다

# 부위 표시 순서. 무기 → 방어구 → 장신구.
CATEGORY_ORDER = [
    ("Weapon", "무기"),
    ("Hat", "투구"),
    ("Top", "상의"),
    ("Bottom", "하의"),
    ("Gloves", "장갑"),
    ("Shoes", "신발"),
    ("Accessory", "목걸이"),
    ("Ring", "반지"),
]
CATEGORY_LABELS = dict(CATEGORY_ORDER)


def _saving(row):
    """해연을 그냥 살 때보다 아끼는 금액."""
    c = row["cheapest"]
    if c is None or row["market"]["status"] != "ok":
        return None
    return row["market"]["price"] - c["price"]


def _path_total(row, key, field="total"):
    path = row[key]
    return path.get(field) if path else None


# 정렬할 수 있는 값. 없는 값(계산 불가·미수집)은 방향과 무관하게 뒤로 보낸다.
SORT_FIELDS = {
    "saving": _saving,
    "margin": lambda r: r["normal"].get("margin_out_of_pocket"),
    "market": lambda r: r["market"]["price"],
    "count": lambda r: r["market"]["count"],
    "craft": lambda r: _path_total(r, "normal"),
    "craft_oop": lambda r: _path_total(r, "normal", "out_of_pocket"),
    "recipe": lambda r: _path_total(r, "recipe"),
    "echo_buy": lambda r: _path_total(r, "echo_buy"),
    "echo_craft": lambda r: _path_total(r, "echo_craft"),
    "name": lambda r: None,
}
DEFAULT_SORT = "saving"
DESCENDING = ("saving", "margin", "count")  # 클수록 좋은 값은 큰 순이 기본


def sort_rows(rows, sort=DEFAULT_SORT, desc=None):
    field = SORT_FIELDS.get(sort, SORT_FIELDS[DEFAULT_SORT])
    if desc is None:
        desc = sort in DESCENDING

    def key(row):
        v = field(row)
        if v is None:
            return (1, 0, row["name"])  # 값 없는 행은 늘 뒤
        return (0, -v if desc else v, row["name"])

    return sorted(rows, key=key)


def group_rows(rows, sort=DEFAULT_SORT, desc=None):
    """부위별로 묶는다. 목록에 없는 부위는 뒤에 제 이름으로 붙인다."""
    buckets = {}
    for r in rows:
        buckets.setdefault(r["category"], []).append(r)

    known = [k for k, _ in CATEGORY_ORDER if k in buckets]
    unknown = sorted(k for k in buckets if k not in CATEGORY_LABELS)
    return [
        {
            "category": k,
            "label": CATEGORY_LABELS.get(k, k or "기타"),
            "rows": sort_rows(buckets[k], sort, desc),
        }
        for k in known + unknown
    ]


def material_prices(store, prices, owned, now=None):
    """재고 입력칸 옆에 세울 단가표.

    거래 가능한 재료만 나온다(실측 18종) — 입력칸과 같은 목록이라 나란히 선다.
    각 재료에 현재 최저가, 최근 14일 추세, 펼쳐 볼 30일 차트, 내 재고의
    값어치가 붙는다.

    값어치를 내는 이유는 "만들지 말고 재료를 그냥 팔까"가 실제 선택지라서다.
    """
    out = []
    for name, kind_id in sorted(store.material_index().items()):
        p = prices.get(kind_id) or {}
        price = p.get("min_price")
        have = owned.get(kind_id, 0)
        mk = p.get("market_kind_id")
        # 캔들은 한 번만 읽는다 — 작은 줄과 펼침 차트가 같은 목록을 본다.
        candles = (
            store.candles(mk, "day") if mk is not None and price is not None else []
        )
        out.append(
            {
                "name": name,
                "kind_id": kind_id,
                "price": price,
                "count": p.get("total_count"),
                "owned": have,
                "value": price * have if price is not None else None,
                "trend": material_trend(candles, price) if candles else None,
                "chart": material_chart(candles, price, now=now) if candles else None,
            }
        )
    return out


def build_report(
    store,
    now=None,
    echo_multiplier=DEFAULT_ECHO_MULTIPLIER,
    threshold_sec=DEFAULT_STALE_SEC,
    sort=DEFAULT_SORT,
    desc=None,
    owned=None,
):
    """저장소의 시세·레시피 + **호출자가 준 재고**로 표를 만든다.

    재고를 저장소에서 읽지 않는 이유는 방문자마다 다르기 때문이다.
    서버에 두면 여러 사람이 한 서버를 쓸 때 전원이 한 재고를 공유한다.
    """
    items = [i for i in store.items() if i["tier"] in EQUIPMENT_TIERS]
    prices = store.latest_prices()
    owned = owned or {}
    materials = material_prices(store, prices, owned, now=now)
    partners = echo_partners(items)

    # 행은 해연만이다. 잔영은 "잔영을 N개 사거나 만드는 길"로 이 표에 들어간다.
    rows = []
    for it in [i for i in items if i["tier"] == TARGET_TIER]:
        recipe = store.recipe(it["id"])
        # 각 해연은 같은 종류 잔영과 짝짓는다. 종류 간 비교는 열 정렬로 한다.
        mate = partners.get(it["id"])
        mate_recipe = store.recipe(mate["id"]) if mate else None
        rows.append(
            build_row(
                item_id=it["id"],
                name=it["name"],
                kind_id=it["kind_id"],
                # 아직 못 받았으면 None을 넘겨 "미수집"으로 남긴다. 0으로 메우지 않는다.
                normal=recipe.get("normal") if recipe else None,
                recipe=recipe.get("recipe") if recipe else None,
                prices=prices,
                echo_kind_id=mate["kind_id"] if mate else None,
                echo_normal=mate_recipe.get("normal") if mate_recipe else None,
                echo_multiplier=echo_multiplier,
                owned=owned,
            )
        )
        rows[-1]["tier"] = it["tier"]
        rows[-1]["base_name"] = it["base_name"]
        rows[-1]["category"] = it["category"]
        rows[-1]["echo_name"] = mate["name"] if mate else None

    as_of = store.latest_as_of()
    last = store.last_collected()
    return {
        "as_of": as_of,
        "freshness": (
            freshness(
                as_of,
                fetched_at=last["fetched_at"] if last else None,
                now=now,
                threshold_sec=threshold_sec,
            )
            if as_of
            else None
        ),
        "echo_multiplier": echo_multiplier,
        "sort": sort,
        "desc": desc if desc is not None else sort in DESCENDING,
        "has_inventory": bool(owned),
        "materials": materials,
        "inventory_value": sum(m["value"] or 0 for m in materials),
        "rows": rows,
        "groups": group_rows(rows, sort, desc),
        "counts": {
            "total": len(rows),
            "recipe_pending": sum(
                1 for r in rows if r["normal"]["status"] == "not_collected"
            ),
        },
    }
