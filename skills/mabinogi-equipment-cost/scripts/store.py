"""SQLite 저장소. 표준 라이브러리만 쓴다.

시세는 갱신할 때마다 이력이 남는다(같은 스냅샷은 한 번만).
레시피는 1회 수집 후 고정한다 — 상세 API에만 쿼터가 걸려 있고,
레시피는 게임 패치 전까지 바뀌지 않으므로 반복 조회할 이유가 없다.
"""

import os
import sqlite3
import time

DEFAULT_DB = os.path.expanduser("~/.mabi-equipment-cost/data.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    kind_id     INTEGER,
    category    TEXT,
    tier        TEXT,          -- 해연 / 잔영
    base_name   TEXT,          -- 등급을 뗀 이름. 해연↔잔영 짝짓기에 쓴다
    can_trade   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recipe_materials (
    item_id     INTEGER NOT NULL,
    path        TEXT NOT NULL,     -- normal | recipe
    kind_id     INTEGER,
    name        TEXT NOT NULL,
    qty         INTEGER NOT NULL,
    can_trade   INTEGER DEFAULT 1,
    ord         INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_recipe_item ON recipe_materials(item_id);

-- 레시피를 받아온 사실 자체를 따로 남긴다. 재료가 0개인 경로와
-- 아직 못 받은 경로를 구분해야 이어받기가 정확해진다.
CREATE TABLE IF NOT EXISTS recipe_fetched (
    item_id     INTEGER NOT NULL,
    path        TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (item_id, path)
);

-- 보유 재료는 여기 없다. 방문자의 브라우저 쿠키에 산다(inventory.py).
-- 서버에 두면 여러 사람이 한 서버를 쓸 때 전원이 한 재고를 공유한다.

-- 마지막으로 시세를 받아온 시각. 한 행만 유지한다.
-- price_history로는 알 수 없다 — 같은 스냅샷은 중복 저장을 건너뛰므로,
-- 원본이 새 값을 안 주는 동안에는 아무리 받아도 흔적이 안 남는다.
CREATE TABLE IF NOT EXISTS collect_log (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    fetched_at  TEXT NOT NULL,
    as_of       TEXT,
    count       INTEGER
);

-- 일봉을 마지막으로 받은 시각. 서버는 재시작마다 주기 번호가 0으로 돌아가서
-- "몇 번째 주기냐"로 판단하면 켤 때마다 다시 받는다 — 실측에서 하루 1번이
-- 의도인데 재시작이 잦은 날 7번 긁었다. 시각을 남겨야 재시작을 넘어 기억한다.
CREATE TABLE IF NOT EXISTS candle_log (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    kind_id     INTEGER NOT NULL,   -- 실제로는 codex_item_id (재료 매칭 키)
    -- 거래소가 쓰는 진짜 kind_id. 캔들 API가 이걸 요구한다 —
    -- codex_item_id를 넘기면 404다(실측).
    market_kind_id INTEGER,
    name        TEXT,
    min_price   INTEGER,
    total_count INTEGER,
    as_of       TEXT NOT NULL,
    PRIMARY KEY (kind_id, as_of)
);
CREATE INDEX IF NOT EXISTS ix_price_asof ON price_history(as_of);

-- 원본이 주는 일·주·월봉. 우리가 3분마다 쌓는 이력과 별개다 —
-- 이쪽은 두 달치가 이미 있고, 하루 한 번만 받으면 된다.
CREATE TABLE IF NOT EXISTS price_candles (
    market_kind_id INTEGER NOT NULL,
    interval       TEXT NOT NULL,      -- day | week | month
    time           TEXT NOT NULL,
    open  INTEGER, high INTEGER, low INTEGER, close INTEGER,
    count_close    INTEGER,
    PRIMARY KEY (market_kind_id, interval, time)
);
"""


class Store:
    def __init__(self, path=DEFAULT_DB):
        self.path = path

    def _conn(self):
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # 나중에 더한 칸들. CREATE TABLE IF NOT EXISTS는 이미 있는 테이블을
    # 건드리지 않으므로, 돌고 있던 DB에는 여기서 따로 붙인다.
    MIGRATIONS = [("price_history", "market_kind_id", "INTEGER")]

    def init(self):
        with self._conn() as c:
            c.executescript(SCHEMA)
            for table, column, kind in self.MIGRATIONS:
                have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
                if column not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")

    # --- 아이템 -------------------------------------------------------------

    def save_items(self, items):
        with self._conn() as c:
            c.executemany(
                "INSERT OR REPLACE INTO items"
                " (id, name, kind_id, category, tier, base_name, can_trade)"
                " VALUES (?,?,?,?,?,?,?)",
                [
                    (
                        i["id"],
                        i["name"],
                        i.get("kind_id"),
                        i.get("category"),
                        i.get("tier"),
                        i.get("base_name"),
                        int(i.get("can_trade", True)),
                    )
                    for i in items
                ],
            )

    def items(self, tier=None):
        q = "SELECT * FROM items"
        args = ()
        if tier:
            q += " WHERE tier = ?"
            args = (tier,)
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(q + " ORDER BY id", args)]
        for r in rows:  # sqlite는 0/1로 돌려준다. 경계에서 bool로 맞춘다
            r["can_trade"] = bool(r["can_trade"])
        return rows

    # --- 레시피 -------------------------------------------------------------

    def save_recipe(self, item_id, path, materials, fetched_at="now"):
        with self._conn() as c:
            c.execute(
                "DELETE FROM recipe_materials WHERE item_id=? AND path=?",
                (item_id, path),
            )
            c.executemany(
                "INSERT INTO recipe_materials"
                " (item_id, path, kind_id, name, qty, can_trade, ord)"
                " VALUES (?,?,?,?,?,?,?)",
                [
                    (
                        item_id,
                        path,
                        m.get("kind_id"),
                        m["name"],
                        m["qty"],
                        int(m.get("can_trade", True)),
                        n,
                    )
                    for n, m in enumerate(materials)
                ],
            )
            c.execute(
                "INSERT OR REPLACE INTO recipe_fetched (item_id, path, fetched_at)"
                " VALUES (?,?,datetime('now'))"
                if fetched_at == "now"
                else "INSERT OR REPLACE INTO recipe_fetched (item_id, path, fetched_at)"
                " VALUES (?,?,?)",
                (item_id, path) if fetched_at == "now" else (item_id, path, fetched_at),
            )

    def recipe(self, item_id):
        """경로별 재료. 한 번도 안 받았으면 None.

        거래 가능 여부는 items 테이블이 진실이다. 상세 응답의 재료 객체에는
        그 정보가 없어서, 레시피를 받을 때는 아는 만큼만 적어 둔다. 나중에
        `collect_materials`가 items를 채우면 여기서 조인으로 따라잡는다.
        """
        with self._conn() as c:
            paths = [
                r["path"]
                for r in c.execute(
                    "SELECT path FROM recipe_fetched WHERE item_id=?", (item_id,)
                )
            ]
            if not paths:
                return None
            out = {p: [] for p in paths}
            for r in c.execute(
                "SELECT rm.*, i.can_trade AS known_trade FROM recipe_materials rm"
                " LEFT JOIN items i ON i.id = rm.kind_id"
                " WHERE rm.item_id=? ORDER BY rm.path, rm.ord",
                (item_id,),
            ):
                known = r["known_trade"]
                out.setdefault(r["path"], []).append(
                    {
                        "kind_id": r["kind_id"],
                        "name": r["name"],
                        "qty": r["qty"],
                        "can_trade": bool(r["can_trade"] if known is None else known),
                    }
                )
            return out

    def pending_recipe_ids(self, tiers=None):
        """아직 레시피를 못 받은 아이템. 쿼터로 끊긴 다음 주기에 여기부터 잇는다.

        tiers를 주면 그 등급만 본다 — 레시피 아이템 38종은 상세를 받을 이유가 없다.
        """
        q = "SELECT id FROM items WHERE id NOT IN (SELECT item_id FROM recipe_fetched)"
        args = ()
        if tiers:
            q += " AND tier IN (%s)" % ",".join("?" * len(tiers))
            args = tuple(tiers)
        with self._conn() as c:
            return [r["id"] for r in c.execute(q + " ORDER BY id", args)]

    # --- 보유 재료 -----------------------------------------------------------
    #
    # 재고 자체는 저장하지 않는다 — 브라우저 쿠키에 산다(inventory.py).
    # 여기 있는 건 "무엇을 입력받을 수 있나"라는 목록뿐이고, 그건 모두에게 같다.

    def take_legacy_inventory(self):
        """재고를 서버에 두던 시절의 값을 꺼내고 테이블을 지운다.

        한 번만 넘기면 되므로 꺼내는 즉시 없앤다 — 남겨 두면 다음 방문자가
        남의 재고를 물려받는다.
        """
        with self._conn() as c:
            try:
                rows = list(c.execute("SELECT kind_id, qty FROM inventory"))
            except sqlite3.OperationalError:  # 이미 넘겼거나 처음부터 없었다
                return {}
            c.execute("DROP TABLE inventory")
        return {r["kind_id"]: r["qty"] for r in rows if r["qty"] > 0}

    def material_index(self):
        """재료 이름 -> kind_id. 거래 불가 재료는 뺀다 — 보유를 적을 이유가 없다.

        거래 가능 여부는 items가 진실이다. recipe_materials에 적힌 값은
        레시피를 받던 시점의 추정이라 나중에 뒤집힌다(세공된 페리도트ZZ).
        """
        with self._conn() as c:
            return {
                r["name"]: r["kind_id"]
                for r in c.execute(
                    "SELECT DISTINCT rm.name, rm.kind_id FROM recipe_materials rm"
                    " LEFT JOIN items i ON i.id = rm.kind_id"
                    " WHERE rm.kind_id IS NOT NULL"
                    " AND COALESCE(i.can_trade, rm.can_trade) = 1"
                    " ORDER BY rm.name"
                )
            }

    # --- 시세 ---------------------------------------------------------------

    def save_prices(self, rows, as_of):
        with self._conn() as c:
            c.executemany(
                "INSERT OR IGNORE INTO price_history"
                " (kind_id, market_kind_id, name, min_price, total_count, as_of)"
                " VALUES (?,?,?,?,?,?)",
                [
                    (
                        r["kind_id"],
                        r.get("market_kind_id"),
                        r.get("name"),
                        r.get("min_price"),
                        r.get("total_count"),
                        as_of,
                    )
                    for r in rows
                ],
            )

    def latest_prices(self):
        """kind_id -> 가장 최근 스냅샷의 시세."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT p.* FROM price_history p JOIN"
                " (SELECT kind_id, MAX(as_of) AS m FROM price_history GROUP BY kind_id) t"
                " ON p.kind_id = t.kind_id AND p.as_of = t.m"
            )
            return {
                r["kind_id"]: {
                    "name": r["name"],
                    "min_price": r["min_price"],
                    "total_count": r["total_count"],
                    "as_of": r["as_of"],
                    "market_kind_id": r["market_kind_id"],
                }
                for r in rows
            }

    # --- 배포 -----------------------------------------------------------------

    def export_seed(self, target):
        """레시피·아이템만 담은 DB를 만든다. 시세 이력은 뺀다.

        배포 이미지에 넣을 씨앗이다. 레시피는 상세 API 쿼터 때문에 새 환경에서
        다시 받기 어렵다 — 76종을 39 + 37로 나눠 받는 데 몇 시간이 걸렸다.
        시세는 쿼터가 없어 서버가 뜨고 3분 안에 채워지므로 들고 갈 이유가 없다.

        재고 테이블이 남아 있어도 따라가지 않는다 — 실리면 방문자 전원이
        그 재고를 물려받는다.
        """
        seed = Store(target)
        seed.init()
        c = seed._conn()
        try:
            c.execute("ATTACH DATABASE ? AS src", (self.path,))
            with c:  # 트랜잭션만 연다 — 열린 채로는 DETACH가 안 된다
                for table in ("items", "recipe_materials", "recipe_fetched"):
                    c.execute(f"DELETE FROM {table}")
                    c.execute(f"INSERT INTO {table} SELECT * FROM src.{table}")
            c.execute("DETACH DATABASE src")
        finally:
            c.close()
        return target

    def latest_as_of(self):
        with self._conn() as c:
            return c.execute("SELECT MAX(as_of) FROM price_history").fetchone()[0]

    def mark_collected(self, as_of=None, count=0, at=None):
        """시세를 받아온 사실을 남긴다. 마지막 한 번만 유지한다.

        원본이 같은 스냅샷을 계속 줘도 여기는 갱신된다 — 그래야 "수집기가
        멈췄나"와 "원본이 늦나"를 화면에서 가를 수 있다.
        """
        stamp = at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO collect_log (id, fetched_at, as_of, count)"
                " VALUES (1,?,?,?)",
                (stamp, as_of, count),
            )
        return stamp

    def last_collected(self):
        """{fetched_at, as_of, count} 또는 아직 한 번도 안 받았으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT fetched_at, as_of, count FROM collect_log WHERE id=1"
            ).fetchone()
        return dict(row) if row else None

    def mark_candles_collected(self, now=None):
        """일봉을 받은 사실을 남긴다. 다음 실행이 이걸 보고 건너뛴다."""
        stamp = now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO candle_log (id, fetched_at) VALUES (1,?)",
                (stamp,),
            )
        return stamp

    def last_candle_collection(self):
        """마지막으로 일봉을 받은 시각. 한 번도 안 받았으면 None."""
        with self._conn() as c:
            row = c.execute("SELECT fetched_at FROM candle_log WHERE id=1").fetchone()
        return row["fetched_at"] if row else None

    # --- 캔들 -----------------------------------------------------------------

    def save_candles(self, market_kind_id, interval, candles):
        """원본 일·주·월봉을 넣는다. 같은 시각은 덮어쓴다.

        오늘 캔들은 장중에 계속 움직이므로 REPLACE여야 한다 — IGNORE로 두면
        그날 첫 값에 붙박인다.
        """
        with self._conn() as c:
            c.executemany(
                "INSERT OR REPLACE INTO price_candles"
                " (market_kind_id, interval, time, open, high, low, close, count_close)"
                " VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        market_kind_id,
                        interval,
                        k["time"],
                        k.get("open"),
                        k.get("high"),
                        k.get("low"),
                        k.get("close"),
                        k.get("count_close"),
                    )
                    for k in candles
                ],
            )

    def candles(self, market_kind_id, interval="day", limit=None):
        """시각 오름차순. 최근 N개만 필요하면 limit."""
        q = (
            "SELECT time, open, high, low, close, count_close FROM price_candles"
            " WHERE market_kind_id=? AND interval=? ORDER BY time"
        )
        args = [market_kind_id, interval]
        with self._conn() as c:
            rows = [dict(r) for r in c.execute(q, args)]
        return rows[-limit:] if limit else rows

    def price_history_count(self, kind_id):
        with self._conn() as c:
            return c.execute(
                "SELECT COUNT(*) FROM price_history WHERE kind_id=?", (kind_id,)
            ).fetchone()[0]
