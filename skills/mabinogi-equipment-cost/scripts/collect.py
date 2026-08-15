#!/usr/bin/env python3
"""수집기.

    python3 collect.py items      아이템 목록 (1회면 충분)
    python3 collect.py prices     시세 1회
    python3 collect.py recipes    레시피 — 쿼터에 걸리면 멈추고 받은 만큼 유지
    python3 collect.py loop       시세를 주기(기본 600초)로 갱신

시세 API는 쿼터가 없고 상세 API에만 걸린다. 그래서 둘의 주기가 다르다.
"""

import sys
import time

import api
import classify
import normalize
from store import DEFAULT_DB, Store

TIERS = ("해연", "잔영")
DEFAULT_INTERVAL = 600


def collect_items(store):
    raw = {}
    for kw in TIERS:
        for it in api.fetch_items(kw):
            raw[it["id"]] = it

    rows = []
    for it in raw.values():
        tier, base = classify.classify_item(it["name"])
        rows.append(normalize.normalize_item(it, tier=tier, base_name=base))
    store.save_items(rows)
    return len(rows)


def collect_prices(store, on_page=None):
    rows = api.fetch_prices(on_page=on_page)
    prices = normalize.normalize_prices(rows)
    as_of = max((p["as_of"] for p in prices.values() if p["as_of"]), default=None)
    store.save_prices(
        [{"kind_id": k, **v} for k, v in prices.items()],
        as_of=as_of or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    return len(prices), as_of


def collect_recipes(store, limit=None, sleep=0.4):
    """못 받은 것부터 이어받는다.

    쿼터를 만나면 그 자리에서 멈춘다. 이미 받은 레시피는 그대로 두고,
    다음 주기에 남은 것부터 다시 잇는다 — 부분 수집분을 버리지 않는다.
    """
    untradable = {i["id"] for i in store.items() if not i["can_trade"]}
    pending = store.pending_recipe_ids(tiers=TIERS)
    if limit:
        pending = pending[:limit]

    done = 0
    for item_id in pending:
        try:
            detail = api.fetch_item_detail(item_id)
        except api.Throttled as e:
            return done, len(pending) - done, e.retry_after
        r = normalize.normalize_recipe(detail, untradable_ids=untradable)
        if r is None:
            store.save_recipe(item_id, "normal", [])  # 제작 불가도 받은 사실은 남긴다
        else:
            store.save_recipe(item_id, "normal", r["normal"])
            if r["recipe"] is not None:
                store.save_recipe(item_id, "recipe", r["recipe"])
        done += 1
        time.sleep(sleep)
    return done, 0, None


def collect_materials(store):
    """레시피에 등장하는 재료의 거래 가능 여부를 채운다.

    재료 중에도 거래 불가가 있다 — '세공된 페리도트ZZ'가 그렇다. 모르고 두면
    시세가 없다는 이유로 경로 전체가 계산 불가로 죽는다. 실제로는 그 재료만
    빼고 나머지로 원가를 세워야 맞다.

    상세 API는 쿼터가 걸리므로 이름 검색(쿼터 없음)으로 받아 id로 골라낸다.
    """
    known = {i["id"] for i in store.items()}
    wanted = {}
    for it in store.items():
        for path in (store.recipe(it["id"]) or {}).values():
            for m in path:
                if m["kind_id"] is not None and m["kind_id"] not in known:
                    wanted[m["kind_id"]] = m["name"]

    filled = []
    for item_id, name in wanted.items():
        for found in api.fetch_items(name):
            if found["id"] == item_id:
                tier, base = classify.classify_item(found["name"])
                filled.append(
                    normalize.normalize_item(found, tier=tier, base_name=base)
                )
                break
    if filled:
        store.save_items(filled)
    return len(filled)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "loop"
    db = argv[2] if len(argv) > 2 else DEFAULT_DB
    store = Store(db)
    store.init()

    if cmd == "items":
        print(f"아이템 {collect_items(store)}종 저장")
    elif cmd == "prices":
        n, as_of = collect_prices(store)
        print(f"시세 {n}건 저장 (기준 {as_of})")
    elif cmd == "recipes":
        done, left, retry = collect_recipes(store)
        msg = f"레시피 {done}종 수집, {left}종 남음"
        if retry:
            msg += (
                f" — 쿼터. 서버는 {retry}초 뒤라지만 실측은 더 걸렸다."
                " 한참 뒤에 다시 실행할 것"
            )
        print(msg)
        filled = collect_materials(store)
        if filled:
            print(f"재료 {filled}종의 거래 가능 여부를 채웠다")
    elif cmd == "loop":
        interval = int(argv[3]) if len(argv) > 3 else DEFAULT_INTERVAL
        while True:
            n, as_of = collect_prices(store)
            print(
                f"[{time.strftime('%H:%M:%S')}] 시세 {n}건 (기준 {as_of})", flush=True
            )
            time.sleep(interval)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
