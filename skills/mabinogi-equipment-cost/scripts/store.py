"""SQLite 저장소. 표준 라이브러리만 쓴다.

시세는 갱신할 때마다 이력이 남는다(같은 스냅샷은 한 번만).
레시피는 1회 수집 후 고정한다 — 상세 API에만 쿼터가 걸려 있고,
레시피는 게임 패치 전까지 바뀌지 않으므로 반복 조회할 이유가 없다.
"""

import os
import sqlite3

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

-- 내가 이미 가진 재료. 화면에서 통째로 갈아끼운다.
CREATE TABLE IF NOT EXISTS inventory (
    kind_id     INTEGER PRIMARY KEY,
    qty         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    kind_id     INTEGER NOT NULL,
    name        TEXT,
    min_price   INTEGER,
    total_count INTEGER,
    as_of       TEXT NOT NULL,
    PRIMARY KEY (kind_id, as_of)
);
CREATE INDEX IF NOT EXISTS ix_price_asof ON price_history(as_of);
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

    def init(self):
        with self._conn() as c:
            c.executescript(SCHEMA)

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

    def save_inventory(self, owned):
        """통째로 갈아끼운다. 병합하면 화면에서 지운 줄을 지울 방법이 없다."""
        with self._conn() as c:
            c.execute("DELETE FROM inventory")
            c.executemany(
                "INSERT INTO inventory (kind_id, qty) VALUES (?,?)", list(owned.items())
            )

    def inventory(self):
        with self._conn() as c:
            return {
                r["kind_id"]: r["qty"]
                for r in c.execute("SELECT kind_id, qty FROM inventory")
            }

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
                " (kind_id, name, min_price, total_count, as_of) VALUES (?,?,?,?,?)",
                [
                    (
                        r["kind_id"],
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
                }
                for r in rows
            }

    def latest_as_of(self):
        with self._conn() as c:
            return c.execute("SELECT MAX(as_of) FROM price_history").fetchone()[0]

    def price_history_count(self, kind_id):
        with self._conn() as c:
            return c.execute(
                "SELECT COUNT(*) FROM price_history WHERE kind_id=?", (kind_id,)
            ).fetchone()[0]
