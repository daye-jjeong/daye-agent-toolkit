"""
health_io.py — Obsidian vault 기반 건강 데이터 I/O 모듈.

health-tracker / health-coach 공통 사용.
~/openclaw/vault/health/ 아래에 Dataview-queryable markdown 파일을 읽고 쓴다.
stdlib만 사용.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

VAULT_DIR = Path(os.environ.get("HEALTH_VAULT", "~/openclaw/vault")).expanduser()
HEALTH_DIR = VAULT_DIR / "health"

CATEGORIES = {
    "symptoms": HEALTH_DIR / "symptoms",
    "exercises": HEALTH_DIR / "exercises",
    "pt-homework": HEALTH_DIR / "pt-homework",
    "check-ins": HEALTH_DIR / "check-ins",
}


# ── 쓰기 ──────────────────────────────────────
def write_entry(category, filename, frontmatter, body=""):
    """카테고리 디렉토리에 .md 파일 생성. 이미 존재하면 덮어쓰기."""
    cat_dir = CATEGORIES[category]
    cat_dir.mkdir(parents=True, exist_ok=True)
    fpath = cat_dir / filename

    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, bool):
            fm_lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            fm_lines.append(f"{k}: {v}")
        elif v is None or v == "":
            continue
        else:
            # quote strings that contain special chars
            sv = str(v)
            if any(c in sv for c in ":#{}[]|>&*!?,"):
                fm_lines.append(f'{k}: "{sv}"')
            else:
                fm_lines.append(f"{k}: {sv}")
    fm_lines.append("---")

    content = "\n".join(fm_lines)
    if body:
        content += f"\n\n{body}\n"
    else:
        content += "\n"

    fpath.write_text(content, encoding="utf-8")
    return fpath


def update_entry(filepath, updates):
    """기존 .md 파일의 frontmatter 필드를 업데이트."""
    filepath = Path(filepath)
    if not filepath.exists():
        return None

    text = filepath.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    fm.update(updates)

    return write_entry_raw(filepath, fm, body)


def write_entry_raw(filepath, frontmatter, body=""):
    """파일 경로에 직접 쓰기."""
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, bool):
            fm_lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            fm_lines.append(f"{k}: {v}")
        elif v is None or v == "":
            continue
        else:
            sv = str(v)
            if any(c in sv for c in ":#{}[]|>&*!?,"):
                fm_lines.append(f'{k}: "{sv}"')
            else:
                fm_lines.append(f"{k}: {sv}")
    fm_lines.append("---")

    content = "\n".join(fm_lines)
    if body:
        content += f"\n\n{body}\n"
    else:
        content += "\n"

    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 읽기 ──────────────────────────────────────
def parse_frontmatter(text):
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
                    # type coercion
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


def read_entries(category, days=None, filters=None):
    """카테고리의 모든 .md 파일을 읽어 frontmatter 리스트 반환.

    Args:
        category: "symptoms", "exercises", "pt-homework", "check-ins"
        days: 최근 N일 필터 (None이면 전체)
        filters: dict of {field: value} 추가 필터
    Returns:
        list of (filepath, frontmatter_dict)
    """
    cat_dir = CATEGORIES[category]
    if not cat_dir.exists():
        return []

    cutoff = None
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    results = []
    for f in sorted(cat_dir.glob("*.md")):
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        if not fm:
            continue

        # date filter
        if cutoff and "date" in fm:
            if str(fm["date"]) < cutoff:
                continue

        # custom filters
        if filters:
            match = all(fm.get(k) == v for k, v in filters.items())
            if not match:
                continue

        results.append((f, fm))

    return results


def list_entries(category, filters=None):
    """간단한 목록 반환 (경로 + frontmatter)."""
    return read_entries(category, filters=filters)


# ── 유틸 ──────────────────────────────────────
def sanitize(name, max_len=50):
    """파일시스템 안전한 이름."""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "", name)
    name = name.replace(" ", "_").strip("._")
    return name[:max_len] if name else "unknown"


def today():
    return datetime.now().strftime("%Y-%m-%d")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
