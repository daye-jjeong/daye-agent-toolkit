"""life-coach 스크립트 공유 헬퍼."""

from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def find_project_memory(repo_name: str) -> Path | None:
    """레포 이름에 매칭되는 프로젝트 memory 디렉토리 탐색."""
    try:
        for entry in PROJECTS_DIR.iterdir():
            if entry.is_dir() and entry.name.endswith(repo_name):
                return entry / "memory"
    except FileNotFoundError:
        pass
    return None
