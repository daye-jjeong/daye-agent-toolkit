# pantry-manager → life-dashboard SQLite 통합 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** pantry-manager의 저장소를 Obsidian vault에서 life-dashboard SQLite로 전환하고, 유통기한 알림을 life-coach로 이관한다.

**Architecture:** pantry-manager 스크립트들이 life-dashboard-mcp의 db.py를 직접 import하는 구조. 다른 스킬(life-coach, meal-tracker, health-tracker)과 동일한 패턴. pantry-manager는 온디맨드 CRUD만, life-coach가 일일 코칭에서 유통기한 섹션 포함.

**Tech Stack:** Python3, SQLite, life-dashboard-mcp db.py

---

## Task 1: schema.sql에 pantry_items 테이블 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/schema.sql`

**Step 1: 테이블 + 인덱스 추가**

`schema.sql` 끝에 추가:

```sql
-- ── Pantry ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS pantry_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    location TEXT NOT NULL,
    purchase_date TEXT,
    expiry_date TEXT,
    status TEXT DEFAULT '재고 있음',
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(name, location)
);

CREATE INDEX IF NOT EXISTS idx_pantry_expiry ON pantry_items(expiry_date);
CREATE INDEX IF NOT EXISTS idx_pantry_status ON pantry_items(status);
```

**Step 2: 커밋**

```bash
git add shared/life-dashboard-mcp/schema.sql
git commit -m "feat(schema): add pantry_items table"
```

---

## Task 2: db.py에 pantry CRUD 함수 추가

**Files:**
- Modify: `shared/life-dashboard-mcp/db.py`

**Step 1: pantry 함수 추가**

db.py 끝에 Pantry 섹션 추가:

```python
# ── Pantry ──────────────────────────────────


def upsert_pantry_item(conn: sqlite3.Connection, data: dict):
    conn.execute("""
        INSERT INTO pantry_items (name, category, quantity, unit, location,
            purchase_date, expiry_date, status, notes, updated_at)
        VALUES (:name, :category, :quantity, :unit, :location,
            :purchase_date, :expiry_date, :status, :notes, datetime('now','localtime'))
        ON CONFLICT(name, location) DO UPDATE SET
            category=excluded.category, quantity=excluded.quantity, unit=excluded.unit,
            purchase_date=excluded.purchase_date, expiry_date=excluded.expiry_date,
            status=excluded.status, notes=excluded.notes,
            updated_at=datetime('now','localtime')
    """, data)


def query_pantry_items(conn: sqlite3.Connection, category: str | None = None,
                       location: str | None = None, status: str | None = None) -> list[dict]:
    clauses = []
    params = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if location:
        clauses.append("location = ?")
        params.append(location)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    sql = "SELECT * FROM pantry_items"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY category, name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_pantry_status(conn: sqlite3.Connection, item_id: int, status: str) -> bool:
    cursor = conn.execute(
        "UPDATE pantry_items SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (status, item_id),
    )
    return cursor.rowcount > 0


def delete_pantry_item(conn: sqlite3.Connection, item_id: int) -> bool:
    cursor = conn.execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))
    return cursor.rowcount > 0


def query_expiring_pantry(conn: sqlite3.Connection, days_ahead: int = 3) -> dict:
    """유통기한 임박/만료 항목 조회."""
    rows = conn.execute("""
        SELECT * FROM pantry_items
        WHERE expiry_date IS NOT NULL AND status != '만료'
        ORDER BY expiry_date
    """).fetchall()
    today_str = datetime.now().strftime("%Y-%m-%d")
    threshold = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    expiring, expired = [], []
    for r in rows:
        r = dict(r)
        if r["expiry_date"] < today_str:
            expired.append(r)
        elif r["expiry_date"] <= threshold:
            expiring.append(r)
    return {"expiring": expiring, "expired": expired}
```

**Step 2: 검증**

```bash
cd shared/life-dashboard-mcp && python3 -c "from db import upsert_pantry_item, query_pantry_items, query_expiring_pantry; print('import OK')"
```

**Step 3: 커밋**

```bash
git add shared/life-dashboard-mcp/db.py
git commit -m "feat(db): add pantry CRUD functions"
```

---

## Task 3: pantry-manager 스크립트 전환

**Files:**
- Delete: `shared/pantry-manager/scripts/pantry_io.py`
- Delete: `shared/pantry-manager/scripts/check_expiry.py`
- Delete: `shared/pantry-manager/scripts/weekly_check.py`
- Modify: `shared/pantry-manager/scripts/add_item.py`
- Modify: `shared/pantry-manager/scripts/list_items.py`
- Modify: `shared/pantry-manager/scripts/shopping_list.py`
- Modify: `shared/pantry-manager/scripts/recipe_suggest.py`
- Modify: `shared/pantry-manager/scripts/parse_receipt.py`

**Step 1: 삭제 — pantry_io.py, check_expiry.py, weekly_check.py**

```bash
git rm shared/pantry-manager/scripts/pantry_io.py
git rm shared/pantry-manager/scripts/check_expiry.py
git rm shared/pantry-manager/scripts/weekly_check.py
```

**Step 2: add_item.py 전환**

vault import → db.py import + upsert_pantry_item 호출로 변경.

```python
#!/usr/bin/env python3
"""식재료 추가 스크립트"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, upsert_pantry_item


def main():
    parser = argparse.ArgumentParser(description="식재료 추가")
    parser.add_argument("--name", required=True, help="식재료명")
    parser.add_argument("--category", required=True,
                       choices=["채소", "과일", "육류", "가공식품", "조미료", "유제품", "기타"])
    parser.add_argument("--quantity", type=float, required=True)
    parser.add_argument("--unit", required=True,
                       choices=["개", "g", "ml", "봉지", "팩"])
    parser.add_argument("--location", required=True,
                       choices=["냉장", "냉동", "실온"])
    parser.add_argument("--expiry", help="유통기한 (YYYY-MM-DD)")
    parser.add_argument("--purchase", help="구매일 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--notes", default="")

    args = parser.parse_args()

    data = {
        "name": args.name,
        "category": args.category,
        "quantity": args.quantity,
        "unit": args.unit,
        "location": args.location,
        "purchase_date": args.purchase or datetime.now().strftime("%Y-%m-%d"),
        "expiry_date": args.expiry,
        "status": "재고 있음",
        "notes": args.notes or None,
    }

    with open_conn() as conn:
        upsert_pantry_item(conn, data)

    print(f"OK: {args.name} {args.quantity}{args.unit} / {args.location}")
    if args.expiry:
        print(f"   유통기한: {args.expiry}")


if __name__ == "__main__":
    main()
```

**Step 3: list_items.py 전환**

```python
#!/usr/bin/env python3
"""식재료 목록 조회 스크립트"""

import argparse
import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, query_pantry_items


def main():
    parser = argparse.ArgumentParser(description="식재료 목록 조회")
    parser.add_argument("--category", help="카테고리 필터")
    parser.add_argument("--location", choices=["냉장", "냉동", "실온"])
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    with open_conn(auto_commit=False) as conn:
        items = query_pantry_items(conn, category=args.category, location=args.location)

    if args.json:
        import json
        print(json.dumps(items, ensure_ascii=False, indent=2, default=str))
        return

    if not items:
        print("식재료가 없습니다.")
        return

    print(f"식재료 목록 (총 {len(items)}개)\n")

    by_category: dict[str, list] = {}
    for item in items:
        cat = item.get("category", "기타")
        by_category.setdefault(cat, []).append(item)

    for category, cat_items in sorted(by_category.items()):
        print(f"[{category}]")
        for item in cat_items:
            print(f"  {item['name']}: {item['quantity']}{item['unit']} ({item['location']})")
        print()


if __name__ == "__main__":
    main()
```

**Step 4: shopping_list.py 전환**

```python
#!/usr/bin/env python3
"""장보기 목록 생성 스크립트"""

import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, query_pantry_items


def main():
    with open_conn(auto_commit=False) as conn:
        items = query_pantry_items(conn, status="부족")

    if not items:
        print("부족한 식재료가 없습니다.")
        return

    print(f"장보기 목록\n")

    by_category: dict[str, list] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item["name"])

    for category, names in sorted(by_category.items()):
        print(f"[{category}]")
        for name in names:
            print(f"  - {name}")

    print(f"\n총 {len(items)}개 항목")


if __name__ == "__main__":
    main()
```

**Step 5: recipe_suggest.py 전환**

```python
#!/usr/bin/env python3
"""레시피 추천 스크립트 (저속노화 기준)"""

import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_MCP_DIR))
from db import open_conn, query_pantry_items


def main():
    with open_conn(auto_commit=False) as conn:
        items = query_pantry_items(conn, status="재고 있음")

    if not items:
        print("현재 사용 가능한 식재료가 없습니다.")
        return

    print("현재 보유 식재료:")
    for item in items:
        print(f"  {item['name']} ({item['quantity']}{item['unit']})")

    print("\n에이전트에게 '현재 재료로 저속노화 메뉴 추천해줘'라고 요청하세요.")

    ingredient_names = [item["name"] for item in items]

    longevity_recipes = {
        "채소 볶음": ["채소", "올리브유", "마늘"],
        "샐러드": ["채소", "과일", "견과류"],
        "생선 구이": ["생선", "레몬", "허브"],
        "두부 조림": ["두부", "간장", "마늘"],
        "콩 스튜": ["콩", "토마토", "채소"],
    }

    suggested = []
    for recipe, required in longevity_recipes.items():
        matches = sum(1 for req in required if any(req in ing for ing in ingredient_names))
        if matches >= 2:
            suggested.append(recipe)

    if suggested:
        print("\n기본 추천:")
        for recipe in suggested:
            print(f"  {recipe}")


if __name__ == "__main__":
    main()
```

**Step 6: parse_receipt.py — pantry_io import 제거**

변경 최소화: import 부분만 제거. OCR 로직/출력은 그대로.

수정 내용:
- `sys.path.insert(0, str(Path(__file__).parent))` 제거
- `import pantry_io` 제거
- 나머지 그대로 (OCR → 텍스트 출력 → 에이전트가 add_item.py 호출)

**Step 7: 검증**

```bash
# add_item 테스트
python3 shared/pantry-manager/scripts/add_item.py --name "테스트양파" --category "채소" --quantity 3 --unit "개" --location "실온"

# list_items 테스트
python3 shared/pantry-manager/scripts/list_items.py

# list_items --json
python3 shared/pantry-manager/scripts/list_items.py --json

# shopping_list (부족 항목 없으므로 빈 결과)
python3 shared/pantry-manager/scripts/shopping_list.py

# recipe_suggest
python3 shared/pantry-manager/scripts/recipe_suggest.py

# 정리: 테스트 데이터 삭제
python3 -c "
import sys; sys.path.insert(0, 'shared/life-dashboard-mcp')
from db import open_conn
with open_conn() as conn:
    conn.execute(\"DELETE FROM pantry_items WHERE name = '테스트양파'\")
print('cleanup OK')
"
```

**Step 8: 커밋**

```bash
git add -A shared/pantry-manager/scripts/
git commit -m "refactor(pantry): vault → SQLite, remove cron scripts"
```

---

## Task 4: life-coach daily_coach.py에 유통기한 섹션 추가

**Files:**
- Modify: `shared/life-coach/scripts/daily_coach.py`

**Step 1: import에 query_expiring_pantry 추가**

db.py import 라인에 `query_expiring_pantry` 추가.

**Step 2: get_today_data()에 pantry 데이터 추가**

health data 조회 블록 아래에:

```python
    try:
        pantry_expiry = query_expiring_pantry(conn, days_ahead=3)
    except Exception:
        pantry_expiry = {"expiring": [], "expired": []}
```

return dict에 `"pantry_expiry": pantry_expiry` 추가.

**Step 3: _build_pantry_section() 함수 추가**

`_build_health_section` 아래에:

```python
def _build_pantry_section(data: dict) -> str | None:
    pantry = data.get("pantry_expiry", {})
    expired = pantry.get("expired", [])
    expiring = pantry.get("expiring", [])
    if not expired and not expiring:
        return None
    lines = []
    if expired:
        lines.append(f"  만료: {', '.join(i['name'] for i in expired)}")
    if expiring:
        lines.append(f"  임박: {', '.join(i['name'] for i in expiring)}")
    return "🧊 유통기한:\n" + "\n".join(lines)
```

**Step 4: build_template_report()에 pantry 섹션 삽입**

health 섹션 뒤에:

```python
    pantry = _build_pantry_section(data)
    if pantry:
        sections.append(pantry)
```

**Step 5: 검증**

```bash
python3 shared/life-coach/scripts/daily_coach.py --dry-run
```

Expected: 기존 리포트 + pantry 항목이 있으면 유통기한 섹션 표시.

**Step 6: 커밋**

```bash
git add shared/life-coach/scripts/daily_coach.py
git commit -m "feat(coach): add pantry expiry section to daily report"
```

---

## Task 5: SKILL.md + 문서 업데이트

**Files:**
- Modify: `shared/pantry-manager/SKILL.md`
- Modify: `shared/pantry-manager/references/usage-examples.md`
- Modify: `shared/pantry-manager/.gitignore`
- Modify: `shared/life-coach/SKILL.md`

**Step 1: pantry-manager SKILL.md 업데이트**

주요 변경:
- vault 참조 → SQLite 참조로 변경
- Data Storage 섹션: `life-dashboard-mcp SQLite` → `pantry_items` 테이블
- Cron/자동화 섹션 제거 (life-coach로 이관됨 명시)
- Scripts 테이블에서 check_expiry, weekly_check 제거
- Frontmatter Schema, Dataview 쿼리 섹션 제거

**Step 2: usage-examples.md 업데이트**

- vault 경로 → 스킬 경로로 변경
- cron 섹션 제거
- 스크립트 명령어 업데이트 (--json 옵션 추가 등)

**Step 3: .gitignore 정리**

Notion DB ID 관련 줄 제거 (더 이상 사용 안 함).

**Step 4: life-coach SKILL.md에 유통기한 책임 명시**

건강 코칭 섹션 근처에 한 줄 추가: "일일 코칭에 유통기한 임박/만료 식재료 알림 포함 (pantry-manager 데이터 참조)"

**Step 5: 커밋**

```bash
git add shared/pantry-manager/SKILL.md shared/pantry-manager/references/usage-examples.md \
        shared/pantry-manager/.gitignore shared/life-coach/SKILL.md
git commit -m "docs: update SKILL.md for pantry SQLite migration"
```

---

## Checklist

- [ ] Task 1: schema.sql — pantry_items 테이블
- [ ] Task 2: db.py — pantry CRUD 함수
- [ ] Task 3: pantry-manager 스크립트 전환 + 삭제
- [ ] Task 4: life-coach daily_coach.py 유통기한 섹션
- [ ] Task 5: SKILL.md + 문서 업데이트
