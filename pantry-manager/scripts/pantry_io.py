"""
pantry_io.py -- Obsidian vault 기반 식재료 데이터 I/O 모듈.

~/clawd/memory/pantry/items/ 아래에 Dataview-queryable markdown 파일을 읽고 쓴다.
Notion API 의존성 없음. stdlib만 사용.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

VAULT_DIR = Path(os.environ.get("PANTRY_VAULT", "~/clawd/memory")).expanduser()
PANTRY_DIR = VAULT_DIR / "pantry"
ITEMS_DIR = PANTRY_DIR / "items"


# -- 유틸 --------------------------------------------------
def sanitize(name, max_len=60):
    """파일시스템 안전한 이름."""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "", name)
    name = name.replace(" ", "_").strip("._")
    return name[:max_len] if name else "unknown"


def today():
    return datetime.now().strftime("%Y-%m-%d")


def _write_frontmatter(filepath, fm, body=""):
    """frontmatter dict + body를 .md 파일로 작성."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif v is None or v == "":
            continue
        else:
            sv = str(v)
            if any(c in sv for c in ":#{}[]|>&*!?,"):
                lines.append(f'{k}: "{sv}"')
            else:
                lines.append(f"{k}: {sv}")
    lines.append("---")

    content = "\n".join(lines)
    if body:
        content += f"\n\n{body}\n"
    else:
        content += "\n"

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _parse_frontmatter(text):
    """마크다운 텍스트에서 frontmatter dict + body를 분리."""
    fm = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    val = val.strip().strip('"')
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    else:
                        try:
                            val = int(val)
                        except ValueError:
                            try:
                                val = float(val)
                            except ValueError:
                                pass
                    fm[key.strip()] = val
    return fm, body


# -- 쓰기 --------------------------------------------------
def add_item(name, category, quantity, unit, location,
             expiry_date=None, purchase_date=None, notes=""):
    """식재료 추가. 동명 아이템이 있으면 수량 업데이트."""
    if purchase_date is None:
        purchase_date = today()

    fm = {
        "type": "pantry-item",
        "name": name,
        "category": category,
        "quantity": quantity,
        "unit": unit,
        "location": location,
        "purchase_date": purchase_date,
        "status": "재고 있음",
        "updated": today(),
    }
    if expiry_date:
        fm["expiry_date"] = expiry_date
    if notes:
        fm["notes"] = notes

    filename = f"{sanitize(name)}.md"
    fpath = ITEMS_DIR / filename

    _write_frontmatter(fpath, fm)
    return {"success": True, "path": str(fpath)}


def update_item_status(name, status):
    """아이템 상태 업데이트 (재고 있음/부족/만료)."""
    filename = f"{sanitize(name)}.md"
    fpath = ITEMS_DIR / filename
    if not fpath.exists():
        return False

    text = fpath.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    fm["status"] = status
    fm["updated"] = today()
    _write_frontmatter(fpath, fm, body)
    return True


def remove_item(name):
    """아이템 파일 삭제."""
    filename = f"{sanitize(name)}.md"
    fpath = ITEMS_DIR / filename
    if fpath.exists():
        fpath.unlink()
        return True
    return False


# -- 읽기 --------------------------------------------------
def query_items(filter_fn=None):
    """모든 아이템 조회. filter_fn(frontmatter) -> bool 으로 필터링."""
    if not ITEMS_DIR.exists():
        return []

    results = []
    for f in sorted(ITEMS_DIR.glob("*.md")):
        fm, _ = _parse_frontmatter(f.read_text(encoding="utf-8"))
        if not fm or fm.get("type") != "pantry-item":
            continue
        if filter_fn and not filter_fn(fm):
            continue
        fm["_path"] = str(f)
        results.append(fm)

    return results


def get_all_items_by_location(location=None):
    """위치별 식재료 목록."""
    def loc_filter(fm):
        if location:
            return fm.get("location") == location
        return True

    return query_items(loc_filter)


def check_expiring_items(days_ahead=3):
    """유통기한 임박/만료 항목 체크."""
    all_items = query_items()

    today_date = datetime.now().date()
    threshold = today_date + timedelta(days=days_ahead)

    expiring = []
    expired = []

    for fm in all_items:
        expiry_str = fm.get("expiry_date")
        if not expiry_str:
            continue

        try:
            expiry_date = datetime.strptime(str(expiry_str), "%Y-%m-%d").date()
        except ValueError:
            continue

        days_left = (expiry_date - today_date).days

        item_info = {
            "name": fm.get("name", "Unknown"),
            "expiry_date": str(expiry_str),
            "category": fm.get("category", ""),
            "location": fm.get("location", ""),
        }

        if days_left < 0:
            item_info["days_ago"] = abs(days_left)
            expired.append(item_info)
        elif days_left <= days_ahead:
            item_info["days_left"] = days_left
            expiring.append(item_info)

    return {"expiring": expiring, "expired": expired}


def get_shopping_list():
    """'부족' 상태인 아이템 목록."""
    return query_items(lambda fm: fm.get("status") == "부족")


def get_available_items():
    """'재고 있음' 상태인 아이템 목록."""
    return query_items(lambda fm: fm.get("status") == "재고 있음")
