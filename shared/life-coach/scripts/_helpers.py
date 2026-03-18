"""life-coach 스크립트 공유 헬퍼."""

import re
import subprocess
import sys
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


def group_topics_by_repo(topics: list[dict]) -> dict[str, list[dict]]:
    """토픽을 repo 단축명 기준으로 그룹핑."""
    groups: dict[str, list[dict]] = {}
    for t in topics:
        repo = (t.get("repo") or "unknown").split("/")[-1]
        groups.setdefault(repo, []).append(t)
    return groups


def dedup_sessions(sessions: list) -> list:
    """session_id prefix 기준 중복 제거. full UUID가 short prefix를 포함하면 full 우선."""
    seen = {}
    for s in sessions:
        sid = s.get("session_id", "")
        key = sid[:8] if len(sid) > 8 else sid
        if key not in seen or len(sid) > len(seen[key].get("session_id", "")):
            seen[key] = s
    return list(seen.values())


def _parse_md_table(lines: list[str], start: int) -> tuple[str, int]:
    """마크다운 테이블을 HTML <table>로 변환. (html, 소비한 줄 수) 반환."""
    header = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    # separator 행 건너뛰기
    consumed = 2
    rows = []
    for i in range(start + 2, len(lines)):
        stripped = lines[i].strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        rows.append(cells)
        consumed += 1
    # HTML 생성
    hdr = "".join(f"<th>{esc_html(h)}</th>" for h in header)
    body = ""
    for row in rows:
        cells_html = []
        for c in row:
            # bold 치환 먼저, 나머지를 escape
            parts = re.split(r'\*\*(.+?)\*\*', c)
            escaped = ""
            for j, part in enumerate(parts):
                if j % 2 == 0:
                    escaped += esc_html(part)
                else:
                    escaped += f"<strong>{esc_html(part)}</strong>"
            cells_html.append(f"<td>{escaped}</td>")
        body += f"<tr>{''.join(cells_html)}</tr>"
    html = f'<table class="coaching-table"><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>'
    return html, consumed


def md_to_html(md: str) -> str:
    """Minimal markdown → HTML (headings, bold, lists, paragraphs, tables)."""
    lines = md.strip().split("\n")
    out = []
    in_ul = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # 테이블 감지: 현재 행이 |로 시작하고 다음 행이 |---|
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"\|[\s\-:|]+\|", lines[i + 1].strip()):
            if in_ul: out.append("</ul>"); in_ul = False
            html, consumed = _parse_md_table(lines, i)
            out.append(html)
            i += consumed
            continue
        elif stripped.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h5 class="coaching-h sub">{esc_html(stripped[4:])}</h5>')
        elif stripped.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h4 class="coaching-h">{esc_html(stripped[3:])}</h4>')
        elif stripped.startswith("# "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h3 class="coaching-h" style="font-size:16px;margin:18px 0 8px">{esc_html(stripped[2:])}</h3>')
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul: out.append('<ul class="coaching-list">'); in_ul = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[2:])
            out.append(f"<li>{content}</li>")
        elif stripped.startswith("```"):
            if in_ul: out.append("</ul>"); in_ul = False
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(esc_html(lines[i]))
                i += 1
            out.append(f'<pre style="background:#1a1a1a;padding:10px;border-radius:6px;font-size:12px;overflow-x:auto;color:#C0C0C0">{chr(10).join(code_lines)}</pre>')
        elif stripped == "" or stripped == "---":
            if in_ul: out.append("</ul>"); in_ul = False
        else:
            if in_ul: out.append("</ul>"); in_ul = False
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            out.append(f"<p>{content}</p>")
        i += 1
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


def get_pending_work() -> list[dict]:
    """main/master가 아닌 활성 worktree 목록 반환."""
    pending = []
    home = Path.home()
    git_dirs = [home / "git_workplace"]
    for git_dir in git_dirs:
        if not git_dir.exists():
            continue
        for repo_dir in git_dir.iterdir():
            if not (repo_dir / ".git").exists():
                continue
            try:
                result = subprocess.run(
                    ["git", "worktree", "list", "--porcelain"],
                    capture_output=True, text=True, cwd=str(repo_dir),
                    timeout=5,
                )
                if result.returncode != 0:
                    continue
                worktrees = []
                current: dict = {}
                for line in result.stdout.strip().split("\n"):
                    if line.startswith("worktree "):
                        if current and current.get("branch"):
                            worktrees.append(current)
                        current = {"path": line[9:], "repo": repo_dir.name}
                    elif line.startswith("branch "):
                        branch = line[7:].split("/")[-1]
                        if branch not in ("main", "master"):
                            current["branch"] = branch
                if current and current.get("branch"):
                    worktrees.append(current)
                pending.extend(worktrees)
            except Exception as e:
                print(f"[get_pending_work] {repo_dir.name}: {e}", file=sys.stderr)
                continue
    return pending
