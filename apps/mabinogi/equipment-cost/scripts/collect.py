#!/usr/bin/env python3
"""수집기.

    python3 collect.py items      아이템 목록 (1회면 충분)
    python3 collect.py prices     시세 1회
    python3 collect.py recipes    레시피 — 쿼터에 걸리면 멈추고 받은 만큼 유지
    python3 collect.py loop       시세를 주기(기본 180초)로 갱신
    python3 collect.py seed       배포용 씨앗 DB (레시피·아이템만)
    python3 collect.py candles    재료 일봉 (하루 1회면 충분)

시세 API는 쿼터가 없고 상세 API에만 걸린다. 그래서 둘의 주기가 다르다.
"""

import json
import os
import sys
import time

import api
import classify
import normalize
from store import DEFAULT_DB, Store

TIERS = ("해연", "잔영")
# 3분. 실측에서 원본 기준 시각이 1분 만에도 바뀌었다 — 10분이면 그 사이를 흘린다.
# 시세 API는 쿼터가 없고 1,226건에 1.7초라 이 정도는 부담이 아니다.
DEFAULT_INTERVAL = 180


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


def tracked_kind_ids(store):
    """이력을 쌓을 종목 — 화면에 실제로 뜨는 것들.

    원본은 시세를 1,199종 통째로 준다. 그중 우리가 읽는 건 재료 18종과
    잔영·해연 76종뿐이고, 나머지 92%는 가구·요리·데코다(실측). 전부 쌓았더니
    하루 71MB씩 늘어 닷새 만에 329MB가 됐고 조회가 4.3초로 늘어졌다.

    비어 있으면(아이템 목록을 아직 안 받은 첫 실행) 걸러낼 근거가 없으므로
    전부 쌓는다.
    """
    return {i["kind_id"] for i in store.items() if i["tier"] in TIERS} | set(
        store.material_index().values()
    )


def collect_prices(store, on_page=None):
    rows = api.fetch_prices(on_page=on_page)
    prices = normalize.normalize_prices(rows)
    # 원본이 준 건 다 세되(진행바·건수), 쌓는 건 화면에 쓰는 종목만.
    tracked = tracked_kind_ids(store)
    if tracked:
        prices = {k: v for k, v in prices.items() if k in tracked}
    as_of = max((p["as_of"] for p in prices.values() if p["as_of"]), default=None)
    stamp = as_of or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store.save_prices([{"kind_id": k, **v} for k, v in prices.items()], as_of=stamp)
    # 받아온 사실을 따로 남긴다. 원본이 같은 스냅샷을 계속 줘도 이건 갱신된다 —
    # 그래야 "수집기가 멈췄나"와 "원본이 늦나"를 화면에서 가를 수 있다.
    store.mark_collected(as_of=stamp, count=len(prices))
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


def collect_candles(store, interval="day", sleep=0.2):
    """재료의 일봉을 받는다. 하루 한 번이면 충분하다 — 일봉이라 더 자주 받아도 같다.

    거래 가능한 재료만 본다(실측 18종). 해연 38종까지 받으면 요청이 세 배로
    늘지만, 화면에서 추세를 보는 건 재료 단가뿐이다.

    시세를 아직 못 받아 진짜 kind_id를 모르는 재료는 건너뛴다 — 그 상태로
    부르면 404다.
    """
    prices = store.latest_prices()
    done = 0
    for _, codex_id in sorted(store.material_index().items()):
        market_kind_id = (prices.get(codex_id) or {}).get("market_kind_id")
        if market_kind_id is None:
            continue
        store.save_candles(
            market_kind_id, interval, api.fetch_candles(market_kind_id, interval)
        )
        done += 1
        time.sleep(sleep)
    return done


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


def write_heartbeat(db, ok, count, as_of, error):
    """수집기 상태를 <db 폴더>/collector-status.json에 남긴다.
    m-agent 메뉴 '플랫폼 상태'가 읽어 🟢/🔴로 보인다. 계약: apps/mabinogi/README.md."""
    path = os.path.join(os.path.dirname(os.path.abspath(db)), "collector-status.json")
    payload = {
        "last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": ok,
        "count": count,
        "as_of": as_of,
        "error": error,
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    except OSError:
        pass


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
    elif cmd == "candles":
        print(f"재료 {collect_candles(store)}종의 일봉을 받았다")
    elif cmd == "seed":
        target = argv[3] if len(argv) > 3 else "seed.db"
        store.export_seed(target)
        kb = os.path.getsize(target) // 1024
        print(f"씨앗 {target} ({kb}KB) — 레시피·아이템만. 시세는 배포처가 직접 받는다")
    elif cmd == "loop":
        interval = int(argv[3]) if len(argv) > 3 else DEFAULT_INTERVAL
        # 실패해도 루프를 죽이지 않는다 — 다음 주기에 다시 시도하고, 상태는
        # heartbeat로 남겨 m-agent 메뉴가 멈춤/오류를 보이게 한다.
        while True:
            try:
                n, as_of = collect_prices(store)
                write_heartbeat(db, ok=True, count=n, as_of=as_of, error=None)
                print(
                    f"[{time.strftime('%H:%M:%S')}] 시세 {n}건 (기준 {as_of})",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001 — 어떤 실패든 살아남아 기록
                write_heartbeat(db, ok=False, count=0, as_of=None, error=str(exc))
                print(f"[{time.strftime('%H:%M:%S')}] 실패: {exc}", flush=True)
            time.sleep(interval)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
