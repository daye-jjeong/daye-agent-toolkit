"""life-coach 스크립트 공유 헬퍼."""

import re
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"

# ── 공유 상수 ─────────────────────────────────────

WEEKDAY = "월화수목금토일"

TAG_COLORS = {
    "리팩토링": "#4A90D9", "디버깅": "#E07B5A", "코딩": "#7ABD7E",
    "설계": "#9B7BC8", "ops": "#F0C040", "문서": "#5AC8D9",
    "리뷰": "#D9A85A", "리서치": "#5AC8D9", "설정": "#D9A85A",
    "기타": "#707070",
}

# ── 공유 유틸리티 ─────────────────────────────────

def esc_html(s: str) -> str:
    """HTML 특수문자 이스케이프."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_tokens(n: int) -> str:
    """토큰 수 포맷: 1234 → '1.2K', 1234567 → '1.2M'."""
    if n >= 1_000_000: return f"{n / 1_000_000:.1f}M"
    if n >= 1_000: return f"{n / 1_000:.1f}K"
    return str(n)


def to_h(t: str) -> float:
    """'HH:MM' 또는 ISO datetime → 시간(float). '13:30' → 13.5"""
    if "T" in t: t = t[11:16]
    h, m = map(int, t.split(":"))
    return h + m / 60


def dedup_sessions(sessions: list) -> list:
    """(start_at, repo, tag) 기준 중복 세션 제거."""
    seen, out = set(), []
    for s in sessions:
        k = (s.get("start_at"), s.get("repo"), s.get("tag"))
        if k not in seen:
            seen.add(k); out.append(s)
    return out


def md_to_html(md: str) -> str:
    """Minimal markdown → HTML (headings, bold, lists, paragraphs)."""
    lines = md.strip().split("\n")
    out = []
    in_ul = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h4 class="coaching-h">{esc_html(stripped[3:])}</h4>')
        elif stripped.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h5 class="coaching-h sub">{esc_html(stripped[4:])}</h5>')
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul: out.append('<ul class="coaching-list">'); in_ul = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[2:])
            out.append(f"<li>{content}</li>")
        elif stripped == "":
            if in_ul: out.append("</ul>"); in_ul = False
        else:
            if in_ul: out.append("</ul>"); in_ul = False
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            out.append(f"<p>{content}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)


def group_sessions_by_repo_branch(
    sessions: list[dict],
    short_repo: bool = False,
) -> list[tuple[str, int, int, dict[str | None, list[dict]]]]:
    """세션을 레포 > 브랜치로 그룹핑.

    Returns: [(repo, total_dur, total_tok, {branch: [sessions]}), ...]
             세션 수 내림차순 정렬.
    short_repo: True이면 repo 경로의 마지막 부분만 사용.
    """
    repo_groups: dict[str, list[dict]] = {}
    for s in sessions:
        repo = (s.get("repo") or "unknown")
        if short_repo:
            repo = repo.split("/")[-1]
        repo_groups.setdefault(repo, []).append(s)

    result = []
    for repo, sess in sorted(repo_groups.items(), key=lambda x: len(x[1]), reverse=True):
        total_dur = sum(s.get("duration_min", 0) for s in sess)
        total_tok = sum(s.get("token_total", 0) or 0 for s in sess)
        branch_groups: dict[str | None, list[dict]] = {}
        for s in sess:
            branch_groups.setdefault(s.get("branch"), []).append(s)
        result.append((repo, total_dur, total_tok, branch_groups))
    return result


def has_meaningful_branches(branch_groups: dict[str | None, list[dict]]) -> bool:
    """branch가 있는 세션이 하나라도 있으면 True."""
    return len(branch_groups) > 1 or (None not in branch_groups)


def find_project_memory(repo_name: str) -> Path | None:
    """레포 이름에 매칭되는 프로젝트 memory 디렉토리 탐색."""
    try:
        for entry in PROJECTS_DIR.iterdir():
            if entry.is_dir() and entry.name.endswith(repo_name):
                return entry / "memory"
    except FileNotFoundError:
        pass
    return None
