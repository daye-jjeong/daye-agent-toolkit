"""원가 비교의 유일한 이음새 — 순수 함수.

레시피와 시세를 딕셔너리로 받아 비교행 하나를 돌려준다.
API 호출·저장소·렌더링은 이 파일 바깥에 얇게 둔다.

원가는 늘 `최저가 × 수량`이라 **하한선**이다. 실제로 80개를 사면
최저가부터 위로 훑어 올라가므로 지출은 이보다 크다.
"""

from datetime import datetime, timezone

DEFAULT_ECHO_MULTIPLIER = 10
DEFAULT_STALE_SEC = 1800


def _listing(prices, kind_id):
    """시세 한 건. 없거나 매물이 0이면 None — 직전 가격을 현재가로 쓰지 않는다."""
    p = prices.get(kind_id)
    if not p or p.get("total_count", 0) <= 0:
        return None
    return p


def _craft_path(materials, prices, owned=None):
    """재료 목록 하나를 원가 경로로 접는다.

    거래 불가 재료는 합계에서 빼고 라벨만 남긴다(경로 자체는 살린다).
    시세가 없는 재료가 하나라도 있으면 경로 전체를 계산 불가로 둔다 —
    0이나 추정치로 메우면 그 경로가 부당하게 싸 보인다.

    값은 둘로 낸다. `total`은 전체 시세고, `out_of_pocket`은 이미 가진 재료를
    뺀 실지출이다. 판정에는 `total`을 쓴다 — 가진 재료도 팔 수 있으므로,
    만들지 말지를 정할 때는 기회비용이 옳다.
    """
    owned = owned or {}
    rows = []
    excluded, missing, shortages = [], [], []
    total = 0
    out_of_pocket = 0

    for m in materials:
        qty = m["qty"]
        if not m.get("can_trade", True):
            # 합계엔 안 넣는다(값을 매길 수 없다). 다만 필요한 재료인 건 사실이므로
            # 내역에는 0원·매물 없음으로 남긴다.
            excluded.append(m["name"])
            rows.append(
                {
                    "name": m["name"],
                    "qty": qty,
                    "owned": 0,
                    "need": qty,
                    "unit_price": None,
                    "subtotal": 0,
                    "listing_count": 0,
                    "shortage": False,
                    "untradable": True,
                }
            )
            continue

        listing = _listing(prices, m["kind_id"])
        if listing is None:
            missing.append(m["name"])
            rows.append(
                {
                    "name": m["name"],
                    "qty": qty,
                    "unit_price": None,
                    "subtotal": None,
                    "listing_count": 0,
                    "shortage": True,
                    "untradable": False,
                }
            )
            continue

        unit = listing["min_price"]
        count = listing.get("total_count", 0)
        have = min(owned.get(m["kind_id"], 0), qty)  # 남는 보유분은 이 아이템과 무관
        need = qty - have
        short = count < need
        if short:
            shortages.append(m["name"])
        total += unit * qty
        out_of_pocket += unit * need
        rows.append(
            {
                "name": m["name"],
                "qty": qty,
                "owned": have,
                "need": need,
                "unit_price": unit,
                "subtotal": unit * qty,
                "listing_count": count,
                "shortage": short,
                "untradable": False,
            }
        )

    computable = not missing
    return {
        "status": "ok" if computable else "uncomputable",
        "total": total if computable else None,
        "out_of_pocket": out_of_pocket if computable else None,
        "materials": rows,
        "excluded_untradable": excluded,
        "missing_price": missing,
        "shortage_warnings": shortages,
        "is_lower_bound": True,
    }


def _not_collected():
    """레시피를 아직 못 받은 상태. 계산 불가와 구분한다 — 원인이 다르다.

    계산 불가는 시세가 없어서고, 이건 상세 API 쿼터로 아직 못 받아서다.
    다음 수집 주기에 채워진다.
    """
    return {
        "status": "not_collected",
        "total": None,
        "out_of_pocket": None,
        "materials": [],
        "excluded_untradable": [],
        "missing_price": [],
        "shortage_warnings": [],
        "is_lower_bound": True,
    }


def _market(prices, kind_id):
    listing = _listing(prices, kind_id)
    if listing is None:
        return {"status": "no_listing", "price": None, "count": 0}
    return {
        "status": "ok",
        "price": listing["min_price"],
        "count": listing.get("total_count", 0),
    }


def _blank_echo(status, multiplier):
    return {"status": status, "total": None, "multiplier": multiplier, "unit": None}


def _echo_buy(prices, echo_kind_id, multiplier):
    """잔영 N개를 거래소에서 사는 값.

    배수는 설정값이다. 부위별 마도저항 수치표를 확보하지 못했으므로
    페이지에서 바꿀 수 있어야 한다.
    """
    if echo_kind_id is None:
        return _blank_echo("no_counterpart", multiplier)
    listing = _listing(prices, echo_kind_id)
    if listing is None:
        return _blank_echo("no_listing", multiplier)
    unit = listing["min_price"]
    return {
        "status": "ok",
        "total": unit * multiplier,
        "multiplier": multiplier,
        "unit": unit,
    }


def _add_margin(path, market):
    """만들어 팔면 남는 돈. 거래소 수수료는 반영하지 않는다."""
    if path is None:
        return None
    price = market["price"] if market["status"] == "ok" else None
    ok = path["status"] == "ok" and price is not None
    path["margin"] = price - path["total"] if ok else None
    path["margin_out_of_pocket"] = price - path["out_of_pocket"] if ok else None
    return path


def _echo_craft(prices, echo_normal, multiplier, owned=None):
    """잔영 N개를 직접 만드는 값. 한 개 재료비 × N."""
    if echo_normal is None:
        return _blank_echo("no_counterpart", multiplier)
    path = _craft_path(echo_normal, prices, owned)
    if path["status"] != "ok":
        return {**_blank_echo(path["status"], multiplier), "path": path}
    return {
        "status": "ok",
        "total": path["total"] * multiplier,
        "multiplier": multiplier,
        "unit": path["total"],
        "path": path,
    }


OPTION_LABELS = {
    "buy": "해연 구매",
    "craft": "해연 제작",
    "echo_buy": "잔영 구매",
    "echo_craft": "잔영 제작",
    "craft_oop": "실 제작",
}


def _oop_candidate(path):
    if path["status"] != "ok":
        return None
    oop = path.get("out_of_pocket")
    return oop if oop is not None and oop != path["total"] else None


def _cheapest(candidates):
    """해연 1개를 얻는 길 중 가장 싼 것.

    길은 넷이다 — 해연을 사기, 해연을 만들기, 잔영을 배수만큼 사기,
    잔영을 배수만큼 만들기.

    못 세는 길은 후보에서 빠진다. 하나도 못 세면 결론을 내지 않는다 —
    빈 값을 0으로 보면 아무것도 아닌 게 늘 이긴다.
    """
    options = [(key, value) for key, value in candidates if value is not None]
    if not options:
        return None
    option, price = min(options, key=lambda o: o[1])
    return {"option": option, "price": price, "label": OPTION_LABELS[option]}


def build_row(
    *,
    item_id,
    name,
    kind_id,
    normal,
    prices,
    recipe=None,
    echo_kind_id=None,
    echo_normal=None,
    echo_multiplier=DEFAULT_ECHO_MULTIPLIER,
    owned=None,
):
    """해연 한 종을 얻는 네 가지 길을 한 줄로 세운다.

    recipe(레시피 보유 시 재료)는 없으면 None으로 둔다. 레시피 아이템은
    거래 불가라 시세가 없어서, 나머지와 같은 줄에 세워 비교하지 않는다.

    echo_kind_id / echo_normal은 같은 종류 잔영의 시세 키와 제작 재료다.
    짝이 없으면 그 두 길은 후보에서 빠진다.
    """
    market = _market(prices, kind_id)
    normal_path = _add_margin(
        _craft_path(normal, prices, owned) if normal is not None else _not_collected(),
        market,
    )
    recipe_path = _add_margin(
        _craft_path(recipe, prices, owned) if recipe is not None else None, market
    )
    echo_buy = _echo_buy(prices, echo_kind_id, echo_multiplier)
    echo_craft = _echo_craft(prices, echo_normal, echo_multiplier, owned)
    cheapest = _cheapest(
        [
            ("buy", market["price"] if market["status"] == "ok" else None),
            ("craft", normal_path["total"] if normal_path["status"] == "ok" else None),
            ("echo_buy", echo_buy["total"]),
            ("echo_craft", echo_craft["total"]),
            # 재고를 넣었으면 실지출로도 겨룬다. 가진 게 없으면 전체 시세와
            # 같은 값이라 후보에 넣지 않는다 — 같은 값을 두 번 세울 이유가 없다.
            ("craft_oop", _oop_candidate(normal_path)),
        ]
    )

    return {
        "item_id": item_id,
        "name": name,
        "kind_id": kind_id,
        "market": market,
        "normal": normal_path,
        "recipe": recipe_path,
        "echo_buy": echo_buy,
        "echo_craft": echo_craft,
        "cheapest": cheapest,
        "verdict": cheapest["option"] if cheapest else None,
    }


def _parse(ts):
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def freshness(as_of, now=None, threshold_sec=DEFAULT_STALE_SEC):
    """시세 기준 시각의 신선도.

    수집기가 죽어도 페이지는 멀쩡한 숫자를 계속 보여준다.
    보는 순간 낡았다는 게 눈에 들어와야 한다.
    """
    now_dt = datetime.now(timezone.utc) if now is None else _parse(now)
    age = int((now_dt - _parse(as_of)).total_seconds())
    return {
        "as_of": as_of,
        "age_sec": age,
        "stale": age > threshold_sec,
        "threshold_sec": threshold_sec,
    }
