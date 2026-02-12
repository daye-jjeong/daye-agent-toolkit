"""
task_io.py -- Obsidian vault 기반 태스크 I/O 모듈.

task-policy 스킬의 guardrails / triage 공통 사용.
~/openclaw/vault/projects/ 아래에 Dataview-queryable markdown 파일을 읽고 쓴다.

기존 vault 컨벤션 준수:
  - 프로젝트: projects/{type}/{project-name}/_project.md
  - 태스크:   projects/{type}/{project-name}/t-{prefix}-{NNN}.md
  - frontmatter: id, title, status, priority, owner, created, deadline, start ...
  - statuses: todo, in_progress, done, blocked
  - priorities: high, medium, low

stdlib만 사용. 외부 패키지 없음.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

VAULT_DIR = Path(os.environ.get("TASK_VAULT", "~/openclaw/vault")).expanduser()
PROJECTS_DIR = VAULT_DIR / "projects"
GUARDRAILS_DIR = Path.home() / ".clawdbot" / "guardrails"

# Valid statuses and priorities (aligned with structure.yml)
TASK_STATUSES = ["todo", "in_progress", "done", "blocked"]
TASK_PRIORITIES = ["high", "medium", "low"]


# ── frontmatter 파싱 ──────────────────────────────
def parse_frontmatter(text: str) -> Tuple[Dict, str]:
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
                    val = val.strip().strip("'\"")
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


def format_frontmatter(fm: Dict) -> str:
    """frontmatter dict를 YAML frontmatter 문자열로 변환."""
    lines = ["---"]
    for k, v in fm.items():
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"- {item}")
        else:
            sv = str(v)
            if any(c in sv for c in ":#{}[]|>&*!?,") or sv != sv.strip():
                lines.append(f"{k}: '{sv}'")
            else:
                lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines)


# ── 태스크 파일 I/O ──────────────────────────────
def write_task(project_path: str, task_data: Dict, body: str = "") -> Dict:
    """
    프로젝트 디렉토리에 태스크 .md 파일 생성.

    Args:
        project_path: 프로젝트 폴더 경로 (e.g., "work/ronik" 또는 절대 경로)
        task_data: frontmatter 데이터 (id, title, status, priority, owner, ...)
        body: 마크다운 본문 (선택)

    Returns:
        {"success": bool, "path": str|None, "task_id": str|None, "error": str|None}
    """
    try:
        if os.path.isabs(project_path):
            proj_dir = Path(project_path)
        else:
            proj_dir = PROJECTS_DIR / project_path

        proj_dir.mkdir(parents=True, exist_ok=True)

        task_id = task_data.get("id")
        if not task_id:
            # Auto-generate ID based on project prefix
            prefix = _extract_prefix(proj_dir)
            next_num = _next_task_number(proj_dir, prefix)
            task_id = f"t-{prefix}-{next_num:03d}"
            task_data["id"] = task_id

        # Ensure defaults
        task_data.setdefault("status", "todo")
        task_data.setdefault("priority", "medium")
        task_data.setdefault("owner", "daye")
        task_data.setdefault("created", today())

        filename = f"{task_id}.md"
        filepath = proj_dir / filename

        content = format_frontmatter(task_data)
        if body:
            content += f"\n\n{body}\n"
        else:
            content += "\n"

        filepath.write_text(content, encoding="utf-8")

        return {
            "success": True,
            "path": str(filepath),
            "task_id": task_id,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "path": None,
            "task_id": None,
            "error": str(e)
        }


def read_task(filepath: str) -> Dict:
    """
    태스크 파일 읽기.

    Returns:
        {"success": bool, "frontmatter": dict, "body": str, "error": str|None}
    """
    try:
        fp = Path(filepath)
        if not fp.exists():
            return {"success": False, "frontmatter": {}, "body": "", "error": f"File not found: {filepath}"}

        text = fp.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)

        return {"success": True, "frontmatter": fm, "body": body, "error": None}

    except Exception as e:
        return {"success": False, "frontmatter": {}, "body": "", "error": str(e)}


def update_task(filepath: str, updates: Dict) -> Dict:
    """
    태스크 frontmatter 필드 업데이트.

    Args:
        filepath: 태스크 파일 경로
        updates: 업데이트할 필드 dict

    Returns:
        {"success": bool, "updated_at": str|None, "error": str|None}
    """
    try:
        fp = Path(filepath)
        if not fp.exists():
            return {"success": False, "updated_at": None, "error": f"File not found: {filepath}"}

        text = fp.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)

        fm.update(updates)
        fm["updated_at"] = now()

        content = format_frontmatter(fm)
        if body:
            content += f"\n\n{body}\n"
        else:
            content += "\n"

        fp.write_text(content, encoding="utf-8")

        return {"success": True, "updated_at": fm["updated_at"], "error": None}

    except Exception as e:
        return {"success": False, "updated_at": None, "error": str(e)}


def update_task_status(filepath: str, new_status: str) -> Dict:
    """태스크 상태 업데이트. done이면 completed 날짜도 설정."""
    updates = {"status": new_status}
    if new_status == "done":
        updates["completed"] = today()
    return update_task(filepath, updates)


def add_deliverable_link(filepath: str, deliverable_path: str) -> Dict:
    """태스크 본문의 산출물 섹션에 링크 추가."""
    try:
        fp = Path(filepath)
        if not fp.exists():
            return {"success": False, "error": f"File not found: {filepath}"}

        text = fp.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)

        deliverable_line = f"- [[{deliverable_path}]]"

        if "## 산출물" in body:
            body = body.replace("## 산출물", f"## 산출물\n{deliverable_line}", 1)
        else:
            body += f"\n\n## 산출물\n{deliverable_line}\n"

        content = format_frontmatter(fm)
        content += f"\n\n{body}\n"
        fp.write_text(content, encoding="utf-8")

        return {"success": True, "error": None}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 검색 / 조회 ──────────────────────────────
def find_task_by_id(task_id: str) -> Optional[str]:
    """
    vault 전체에서 task_id로 태스크 파일 경로 찾기.
    파일명이 {task_id}.md 인 파일 검색.

    Returns:
        파일 경로 (str) or None
    """
    if not PROJECTS_DIR.exists():
        return None

    for f in PROJECTS_DIR.rglob(f"{task_id}.md"):
        return str(f)
    return None


def find_task_by_title(title: str, threshold: float = 0.6) -> Optional[str]:
    """
    제목 유사도로 태스크 검색. 단순 부분 일치 사용.

    Returns:
        가장 유사한 태스크 파일 경로 or None
    """
    if not PROJECTS_DIR.exists():
        return None

    title_lower = title.lower()
    best_match = None
    best_score = 0.0

    for f in PROJECTS_DIR.rglob("t-*.md"):
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        task_title = str(fm.get("title", "")).lower()
        if not task_title:
            continue

        score = _simple_similarity(title_lower, task_title)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = str(f)

    return best_match


def read_tasks(project_path: str, status: str = None) -> Dict:
    """
    프로젝트 내 모든 태스크 읽기.

    Args:
        project_path: 프로젝트 폴더 경로 (상대 또는 절대)
        status: 특정 상태 필터 (선택)

    Returns:
        {"success": bool, "tasks": list[dict], "count": int, "error": str|None}
    """
    try:
        if os.path.isabs(project_path):
            proj_dir = Path(project_path)
        else:
            proj_dir = PROJECTS_DIR / project_path

        if not proj_dir.exists():
            return {"success": True, "tasks": [], "count": 0, "error": None}

        tasks = []
        for f in sorted(proj_dir.glob("t-*.md")):
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            if status and fm.get("status") != status:
                continue
            fm["_path"] = str(f)
            tasks.append(fm)

        return {"success": True, "tasks": tasks, "count": len(tasks), "error": None}

    except Exception as e:
        return {"success": False, "tasks": [], "count": 0, "error": str(e)}


def search_all_tasks(status: str = None, priority: str = None,
                     owner: str = None, days: int = None) -> List[Dict]:
    """
    vault 전체에서 태스크 검색.

    Args:
        status: 상태 필터
        priority: 우선순위 필터
        owner: 소유자 필터
        days: 최근 N일 이내 생성 필터

    Returns:
        list of frontmatter dicts (with _path key)
    """
    if not PROJECTS_DIR.exists():
        return []

    cutoff = None
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    results = []
    for f in sorted(PROJECTS_DIR.rglob("t-*.md")):
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        if not fm:
            continue

        if status and fm.get("status") != status:
            continue
        if priority and fm.get("priority") != priority:
            continue
        if owner and fm.get("owner") != owner:
            continue
        if cutoff and str(fm.get("created", "")) < cutoff:
            continue

        fm["_path"] = str(f)
        results.append(fm)

    return results


# ── 산출물 저장 (Notion uploader 대체) ──────────────
def save_deliverable(
    file_path: str,
    task_filepath: str,
    session_id: str = "",
    model: str = "unknown",
    language: str = "ko"
) -> Dict:
    """
    산출물 파일을 vault에 저장하고 태스크에 링크 추가.
    Notion 업로더 대체.

    파일을 태스크와 같은 디렉토리의 deliverables/ 하위에 복사하고,
    태스크 본문에 wiki-link 추가.

    Args:
        file_path: 원본 파일 경로
        task_filepath: 연결할 태스크 파일 경로
        session_id: 세션 식별자
        model: AI 모델명
        language: "ko" (기본) or "en"

    Returns:
        {"success": bool, "vault_path": str|None, "error": str|None}
    """
    try:
        src = Path(file_path)
        if not src.exists():
            return {"success": False, "vault_path": None, "error": f"File not found: {file_path}"}

        task_fp = Path(task_filepath)
        if not task_fp.exists():
            return {"success": False, "vault_path": None, "error": f"Task not found: {task_filepath}"}

        # 산출물 디렉토리
        deliverables_dir = task_fp.parent / "deliverables"
        deliverables_dir.mkdir(parents=True, exist_ok=True)

        # 파일 복사 (+ footer 추가)
        dest = deliverables_dir / src.name

        content = src.read_text(encoding="utf-8")

        # footer 추가
        footer = _make_footer(session_id, model, task_filepath, language)
        full_content = content + "\n" + footer

        dest.write_text(full_content, encoding="utf-8")

        # 태스크에 링크 추가
        rel_path = dest.name  # Obsidian wiki-link는 파일명만으로도 작동
        add_deliverable_link(task_filepath, rel_path)

        return {
            "success": True,
            "vault_path": str(dest),
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "vault_path": None,
            "error": str(e)
        }


# ── 태스크 URL / 경로 검증 ──────────────────────────
def validate_task_path(task_ref: str) -> Dict:
    """
    태스크 참조(경로 또는 ID)가 유효한지 검증.
    Notion URL 검증 대체.

    Args:
        task_ref: 태스크 파일 경로 또는 태스크 ID

    Returns:
        {"valid": bool, "accessible": bool, "task_id": str|None,
         "title": str|None, "path": str|None, "error": str|None}
    """
    # 경로로 직접 접근 시도
    fp = Path(task_ref)
    if fp.exists() and fp.suffix == ".md":
        fm, _ = parse_frontmatter(fp.read_text(encoding="utf-8"))
        return {
            "valid": True,
            "accessible": True,
            "task_id": fm.get("id"),
            "title": fm.get("title"),
            "path": str(fp),
            "error": None
        }

    # ID로 검색
    found = find_task_by_id(task_ref)
    if found:
        fm, _ = parse_frontmatter(Path(found).read_text(encoding="utf-8"))
        return {
            "valid": True,
            "accessible": True,
            "task_id": fm.get("id"),
            "title": fm.get("title"),
            "path": found,
            "error": None
        }

    return {
        "valid": False,
        "accessible": False,
        "task_id": None,
        "title": None,
        "path": None,
        "error": f"Task not found: {task_ref}"
    }


def extract_task_ref(text: str) -> Optional[str]:
    """
    텍스트에서 태스크 참조 추출.
    패턴: "Task: t-xxx-NNN", "Task ID: t-xxx-NNN",
          "Task: /path/to/t-xxx-NNN.md"

    Returns:
        태스크 참조 (ID 또는 경로) or None
    """
    # Pattern 1: "Task: <path>" or "Task ID: <id>"
    p1 = re.search(r"Task(?:\s+(?:URL|ID|Path))?:\s*(\S+)", text, re.IGNORECASE)
    if p1:
        ref = p1.group(1).rstrip(")")
        return ref

    # Pattern 2: bare task ID (t-xxx-NNN)
    p2 = re.search(r"(t-[a-z]+-\d{3})", text)
    if p2:
        return p2.group(1)

    # Pattern 3: vault path
    p3 = re.search(r"((?:/[^\s]+)?/t-[a-z]+-\d{3}\.md)", text)
    if p3:
        return p3.group(1)

    return None


def is_accessible_path(path: str) -> bool:
    """
    경로가 접근 가능한지(vault 내부 또는 URL) 확인.
    로컬 전용 경로는 False.
    """
    # vault 내 경로
    try:
        p = Path(path)
        if p.exists():
            return True
        if str(VAULT_DIR) in path:
            return True
    except (OSError, ValueError):
        pass

    # URL
    if path.startswith("http://") or path.startswith("https://"):
        return True

    # wiki-link (Obsidian)
    if path.startswith("[[") and path.endswith("]]"):
        return True

    return False


# ── 프로젝트 유틸 ──────────────────────────────
def list_projects(project_type: str = None) -> List[Dict]:
    """
    vault의 프로젝트 목록 반환.

    Args:
        project_type: "work" or "personal" (None이면 전체)

    Returns:
        list of {"name": str, "path": str, "type": str, "status": str}
    """
    results = []
    if not PROJECTS_DIR.exists():
        return results

    search_dirs = []
    if project_type:
        d = PROJECTS_DIR / project_type
        if d.exists():
            search_dirs.append(d)
    else:
        for d in PROJECTS_DIR.iterdir():
            if d.is_dir() and d.name not in ("config", "goals", "_archive"):
                search_dirs.append(d)

    for type_dir in search_dirs:
        for proj_dir in sorted(type_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            project_md = proj_dir / "_project.md"
            if project_md.exists():
                fm, _ = parse_frontmatter(project_md.read_text(encoding="utf-8"))
                results.append({
                    "name": fm.get("name", proj_dir.name),
                    "path": str(proj_dir),
                    "type": fm.get("type", type_dir.name),
                    "status": fm.get("status", "active"),
                })
            else:
                results.append({
                    "name": proj_dir.name,
                    "path": str(proj_dir),
                    "type": type_dir.name,
                    "status": "active",
                })

    return results


# ── 내부 헬퍼 ──────────────────────────────
def _extract_prefix(proj_dir: Path) -> str:
    """프로젝트 디렉토리에서 태스크 ID prefix 추출."""
    name = proj_dir.name
    # 기존 태스크에서 prefix 추출
    existing = list(proj_dir.glob("t-*.md"))
    if existing:
        m = re.match(r"t-([a-z]+)-\d+", existing[0].stem)
        if m:
            return m.group(1)
    # 디렉토리 이름에서 생성
    clean = re.sub(r"[^a-z]", "", name.lower())
    return clean[:6] if clean else "task"


def _next_task_number(proj_dir: Path, prefix: str) -> int:
    """프로젝트 내 다음 태스크 번호 계산."""
    max_num = 0
    for f in proj_dir.glob(f"t-{prefix}-*.md"):
        m = re.search(r"-(\d{3})\.md$", f.name)
        if m:
            num = int(m.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1


def _simple_similarity(a: str, b: str) -> float:
    """두 문자열의 단순 유사도 (set 기반 Jaccard)."""
    if not a or not b:
        return 0.0
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _make_footer(session_id: str, model: str, task_path: str, language: str = "ko") -> str:
    """산출물 footer 생성."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_name = Path(task_path).stem

    if language == "ko":
        return f"""
---

**생성 정보**
- 생성일: {timestamp}
- AI 모델: {model}
- 세션: {session_id}
- 원본 Task: [[{task_name}]]
"""
    else:
        return f"""
---

**Generation Info**
- Created: {timestamp}
- AI Model: {model}
- Session: {session_id}
- Source Task: [[{task_name}]]
"""


# ── 유틸 ──────────────────────────────
def sanitize(name: str, max_len: int = 50) -> str:
    """파일시스템 안전한 이름."""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "", name)
    name = name.replace(" ", "_").strip("._")
    return name[:max_len] if name else "unknown"


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


if __name__ == "__main__":
    print("=== task_io.py Test ===\n")
    print(f"Vault: {VAULT_DIR}")
    print(f"Projects: {PROJECTS_DIR}")

    projects = list_projects()
    print(f"\nProjects ({len(projects)}):")
    for p in projects:
        print(f"  - {p['name']} ({p['type']}, {p['status']})")

    tasks = search_all_tasks(status="todo")
    print(f"\nTodo tasks ({len(tasks)}):")
    for t in tasks[:5]:
        print(f"  - [{t.get('id')}] {t.get('title')} ({t.get('priority')})")
