#!/usr/bin/env python3
"""
MingMing Dashboard v3 — Vault Edition

Reads MD+frontmatter from ~/clawd/memory/projects/ and generates
an HTML dashboard with:
  - 오늘 목표 (daily goals)
  - 내가 할 일 (todo)
  - 진행 중 (in-progress with updated_by icons)
  - 이번 주 (weekly progress)
  - 최근 완료 (done in last 7 days)
  - 전체 태스크 테이블

Usage:
    python3 scripts/generate_dashboard_v3.py
    open docs/dashboard/index.html
"""

import re
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

VAULT_DIR = Path.home() / "clawd" / "memory"
PROJECTS_DIR = VAULT_DIR / "projects"
OUTPUT_DIR = Path.home() / "clawd" / "docs" / "dashboard"

OWNER_ICONS = {
    "claude-code": ("🤖", "CC"),
    "openclaw": ("🦊", "OC"),
    "daye": ("👤", "daye"),
    "mingming": ("🤖", "밍밍"),
    "unassigned": ("—", "미정"),
}

# Project color palette: (accent, light background)
PROJECT_COLORS = {
    "ronik":       ("#e74c3c", "#fdf2f2"),  # red
    "mingming":    ("#8e44ad", "#f9f3fc"),  # purple
    "mingming-ai": ("#8e44ad", "#f9f3fc"),  # purple (alias)
    "career":      ("#2980b9", "#edf5fc"),  # blue
    "saju":        ("#e67e22", "#fef6ee"),  # orange
    "health":      ("#27ae60", "#f0faf4"),  # green
    "investment":  ("#f1c40f", "#fefce8"),  # yellow
    "asset":       ("#1abc9c", "#edfaf7"),  # teal
}
DEFAULT_PROJECT_COLOR = ("#95a5a6", "#f4f5f5")  # gray fallback


def parse_frontmatter(filepath: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from an MD file. Returns (metadata, body)."""
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    import yaml
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    body = parts[2].strip()
    return meta, body


def get_last_log_entry(body: str) -> str:
    """Extract the most recent progress log entry from body text."""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("- ") and ("(" in line):
            # e.g. "- 2026-02-11 14:30 (claude-code): 코드 수정 완료"
            # Strip the leading "- " and date prefix for display
            content = line[2:]
            # Try to extract just the action part after the colon
            if "):" in content:
                return content.split("):", 1)[1].strip()
            return content
    return ""


def scan_tasks() -> list[dict]:
    """Scan all t-*.md files in vault projects."""
    tasks = []
    for md_file in PROJECTS_DIR.rglob("t-*.md"):
        meta, body = parse_frontmatter(md_file)
        if not meta.get("id"):
            continue

        # Determine project from path
        # e.g., projects/work/ronik/t-ronik-001.md → work/ronik
        rel = md_file.parent.relative_to(PROJECTS_DIR)
        project_path = str(rel)
        project_name = rel.parts[-1] if rel.parts else "unknown"
        project_type = rel.parts[0] if rel.parts else "unknown"

        meta["_project_path"] = project_path
        meta["_project_name"] = project_name
        meta["_project_type"] = project_type
        meta["_last_activity"] = get_last_log_entry(body)
        meta["_file"] = str(md_file)
        tasks.append(meta)

    return tasks


def _load_yaml(filepath: Path) -> dict | None:
    """Load a plain YAML file."""
    import yaml
    try:
        text = filepath.read_text(encoding="utf-8")
        return yaml.safe_load(text) or {}
    except Exception:
        return None


def _extract_project_keyword(project: str) -> str:
    """Extract last segment of 'work/mingming-ai' → 'mingming-ai'."""
    return project.rsplit("/", 1)[-1].strip().lower() if project else ""


def _yaml_monthly_to_body(data: dict) -> str:
    """Convert monthly YAML to pseudo-markdown body for legacy parsers."""
    lines = []
    for goal in data.get("goals", []):
        title = goal.get("title", "")
        proj = goal.get("project", "")
        priority = goal.get("priority", "")
        lines.append(f"### {title}" + (f" `{priority}`" if priority else ""))
        if proj:
            lines.append(f"프로젝트: {proj}")
        for kr in goal.get("key_results", []):
            if isinstance(kr, str):
                lines.append(f"- {kr}")
            elif isinstance(kr, dict):
                desc = kr.get("description", "")
                lines.append(f"- {desc}")
        lines.append("")
    return "\n".join(lines)


def _yaml_weekly_to_body(data: dict) -> str:
    """Convert weekly YAML to pseudo-markdown body for legacy parsers."""
    lines = ["## 목표"]
    for goal in data.get("goals", []):
        title = goal.get("title", "")
        proj = _extract_project_keyword(goal.get("project", ""))
        status = goal.get("status", "").lower()
        check = "x" if status == "done" else " "
        tag = f" ({proj})" if proj else ""
        lines.append(f"- [{check}] {title}{tag}")
    return "\n".join(lines)


def _yaml_daily_to_body(data: dict) -> str:
    """Convert daily YAML to pseudo-markdown body for legacy parsers."""
    lines = ["## 오늘 목표"]
    for item in data.get("top3", []):
        if isinstance(item, str):
            lines.append(f"- [ ] {item}")
        else:
            title = item.get("title", "")
            proj = _extract_project_keyword(item.get("project", ""))
            status = item.get("status", "").lower()
            check = "x" if status == "done" else " "
            tag = f" ({proj})" if proj else ""
            lines.append(f"- [{check}] {title}{tag}")
    for item in data.get("checklist", []):
        if isinstance(item, dict):
            task = item.get("task", "")
            done = item.get("done", False)
            check = "x" if done else " "
            lines.append(f"- [{check}] {task}")
    # Also handle classic 'goals' key
    for goal in data.get("goals", []):
        if isinstance(goal, str):
            lines.append(f"- [ ] {goal}")
        elif isinstance(goal, dict):
            title = goal.get("title", "")
            proj = _extract_project_keyword(goal.get("project", ""))
            status = goal.get("status", "").lower()
            check = "x" if status == "done" else " "
            tag = f" ({proj})" if proj else ""
            lines.append(f"- [{check}] {title}{tag}")
    return "\n".join(lines)


def scan_goals() -> dict:
    """Read today's daily goal, this week's weekly goal, this month's monthly goal."""
    goals = {}
    now = datetime.now()
    goals_dir = VAULT_DIR / "goals"

    # Monthly
    monthly_file = goals_dir / "monthly" / f"{now.strftime('%Y-%m')}.yml"
    data = _load_yaml(monthly_file) if monthly_file.exists() else None
    if data:
        goals["monthly"] = {
            "meta": {"theme": data.get("theme", "")},
            "body": _yaml_monthly_to_body(data),
        }

    # Weekly
    iso_year, iso_week, _ = now.isocalendar()
    weekly_file = goals_dir / "weekly" / f"{iso_year}-W{iso_week:02d}.yml"
    data = _load_yaml(weekly_file) if weekly_file.exists() else None
    if data:
        goals["weekly"] = {
            "meta": {},
            "body": _yaml_weekly_to_body(data),
        }

    # Daily
    daily_file = goals_dir / "daily" / f"{now.strftime('%Y-%m-%d')}.yml"
    data = _load_yaml(daily_file) if daily_file.exists() else None
    if data:
        goals["daily"] = {
            "meta": {},
            "body": _yaml_daily_to_body(data),
        }

    return goals


def extract_project_tag(text: str) -> str:
    """Extract project tag from parentheses: '태스크 제목 (ronik)' → 'ronik'."""
    m = re.search(r'\(([^)]+)\)\s*$', text)
    return m.group(1).strip().lower() if m else ""


def build_goal_chains(goals: dict) -> list[dict]:
    """Build goal hierarchy chains: daily → weekly → monthly by project keyword matching."""
    # Parse monthly goals by project keyword
    monthly_by_project = {}
    if "monthly" in goals:
        for line in goals["monthly"]["body"].split("\n"):
            stripped = line.strip()
            if stripped.startswith("### "):
                # e.g., "### clawd 시스템 완성 `high`"
                title = re.sub(r'`[^`]*`', '', stripped[4:]).strip()
                monthly_by_project["_current"] = title
            elif stripped.startswith("프로젝트:"):
                proj = stripped.replace("프로젝트:", "").strip().lower()
                # Extract project name from various formats
                proj = re.sub(r'[\[\]]', '', proj)  # strip wiki links
                for keyword in proj.replace("-", " ").replace("_", " ").split():
                    if keyword not in ("work", "personal"):
                        monthly_by_project[keyword] = monthly_by_project.get("_current", "")

    # Parse weekly goals by project keyword
    weekly_by_project = {}
    if "weekly" in goals:
        items = parse_checklist_items(goals["weekly"]["body"], "목표")
        for item in items:
            tag = extract_project_tag(item["text"])
            if tag:
                clean_text = re.sub(r'\s*\([^)]+\)\s*$', '', item["text"])
                weekly_by_project[tag] = {"text": clean_text, "done": item["done"]}

    # Build chains for daily items
    chains = []
    if "daily" in goals:
        items = parse_checklist_items(goals["daily"]["body"], "오늘 목표")
        if not items:
            items = parse_checklist_items(goals["daily"]["body"])
        for item in items:
            tag = extract_project_tag(item["text"])
            clean_text = re.sub(r'\s*\([^)]+\)\s*$', '', item["text"])
            chain = {
                "daily": clean_text,
                "daily_done": item["done"],
                "weekly": "",
                "weekly_done": False,
                "monthly": "",
                "project": tag,
            }
            if tag:
                # Match weekly
                if tag in weekly_by_project:
                    chain["weekly"] = weekly_by_project[tag]["text"]
                    chain["weekly_done"] = weekly_by_project[tag]["done"]
                # Match monthly
                for key, title in monthly_by_project.items():
                    if key != "_current" and tag in key or key in tag:
                        chain["monthly"] = title
                        break
            chains.append(chain)

    return chains


def strip_wiki_links(text: str) -> str:
    """Convert [[target|display]] → display, [[target]] → target."""
    text = re.sub(r'\[\[([^|\]]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    return text


def parse_checklist_items(body: str, section: str = None) -> list[dict]:
    """Parse markdown checklist items from body. Optionally filter by section heading."""
    items = []
    in_section = section is None
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            if section:
                in_section = section.lower() in stripped.lower()
            continue
        if in_section and stripped.startswith("- ["):
            done = stripped[3] == "x"
            text = stripped[6:].strip() if len(stripped) > 6 else ""
            text = strip_wiki_links(text)
            items.append({"text": text, "done": done})
    return items


def project_color(tag: str) -> tuple[str, str]:
    """Return (accent, bg) for a project tag."""
    tag = tag.lower().strip()
    if tag in PROJECT_COLORS:
        return PROJECT_COLORS[tag]
    # Try partial match
    for key, val in PROJECT_COLORS.items():
        if key in tag or tag in key:
            return val
    return DEFAULT_PROJECT_COLOR


def project_dot_html(tag: str) -> str:
    """Small colored dot for project identification."""
    accent, _ = project_color(tag)
    return f'<span class="project-dot" style="background:{accent}"></span>'


def owner_badge_html(updated_by: str) -> str:
    icon, label = OWNER_ICONS.get(updated_by, ("?", updated_by or "?"))
    cls = (updated_by or "unknown").replace("-", "")
    return f'<span class="owner-badge {cls}">{icon} {label}</span>'


def priority_badge_html(priority: str) -> str:
    labels = {"high": "높음", "medium": "중간", "low": "낮음"}
    return f'<span class="priority-badge {priority}">{labels.get(priority, priority)}</span>'


def status_badge_html(status: str) -> str:
    labels = {"todo": "시작 전", "in_progress": "진행 중", "done": "완료", "blocked": "차단"}
    cls = status.replace("_", "-")
    return f'<span class="status-badge {cls}">{labels.get(status, status)}</span>'


def format_date(d) -> str:
    if not d:
        return "—"
    s = str(d)
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return f"{dt.month}/{dt.day}"
    except Exception:
        return s


def generate_html(tasks: list[dict], goals: dict) -> str:
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    todo_tasks = [t for t in tasks if t.get("status") == "todo"]
    todo_tasks.sort(key=lambda t: ({"high": 0, "medium": 1, "low": 2}.get(t.get("priority", "low"), 2)))

    ip_tasks = [t for t in tasks if t.get("status") == "in_progress"]
    ip_tasks.sort(key=lambda t: t.get("updated_at", ""))
    ip_tasks.reverse()

    seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    done_tasks = [t for t in tasks if t.get("status") == "done"]
    # Filter recent (if completed date available, otherwise include all)
    recent_done = []
    for t in done_tasks:
        completed = str(t.get("completed", t.get("updated_at", "")))[:10]
        if completed >= seven_days_ago or not completed:
            recent_done.append(t)
    recent_done.sort(key=lambda t: str(t.get("completed", t.get("updated_at", ""))), reverse=True)

    blocked_tasks = [t for t in tasks if t.get("status") == "blocked"]

    # --- Goal hierarchy flow (monthly → weekly → daily) ---
    chains = build_goal_chains(goals)
    daily_html = ""

    if chains or "daily" in goals:
        done_count = sum(1 for c in chains if c["daily_done"]) if chains else 0
        total_count = len(chains) if chains else 0
        pct = round(done_count / total_count * 100) if total_count > 0 else 0

        # Group chains by monthly goal for cleaner display
        # Collect unique monthly goals
        monthly_goals = []
        seen_monthly = set()
        if "monthly" in goals:
            for line in goals["monthly"]["body"].split("\n"):
                stripped = line.strip()
                if stripped.startswith("### "):
                    title = re.sub(r'`[^`]*`', '', stripped[4:]).strip()
                    if title not in seen_monthly:
                        monthly_goals.append(title)
                        seen_monthly.add(title)

        # Collect unique weekly goals
        weekly_items = []
        if "weekly" in goals:
            weekly_items = parse_checklist_items(goals["weekly"]["body"], "목표")

        # Build monthly column — map each goal to project keywords
        monthly_html = ""
        monthly_project_map = {}  # project_keyword → monthly_title
        current_monthly = ""
        if "monthly" in goals:
            for line in goals["monthly"]["body"].split("\n"):
                stripped = line.strip()
                if stripped.startswith("### "):
                    current_monthly = re.sub(r'`[^`]*`', '', stripped[4:]).strip()
                elif stripped.startswith("프로젝트:") and current_monthly:
                    proj = stripped.replace("프로젝트:", "").strip().lower()
                    proj = re.sub(r'[\[\]]', '', proj)
                    for kw in proj.replace("-", " ").replace("_", " ").split():
                        if kw not in ("work", "personal"):
                            monthly_project_map[kw] = current_monthly

        for mg in monthly_goals:
            # Find project keyword for this monthly goal
            proj_kw = ""
            for kw, title in monthly_project_map.items():
                if title == mg:
                    proj_kw = kw
                    break
            accent, bg = project_color(proj_kw)
            monthly_html += f'<div class="flow-item" data-project="{proj_kw}" style="background:{bg};border-left:3px solid {accent}">{mg}</div>'
        if not monthly_html:
            monthly_html = '<div class="flow-item monthly" style="opacity:0.4">미설정</div>'

        # Build weekly column
        weekly_html_items = ""
        for wi in weekly_items:
            text = strip_wiki_links(wi["text"])
            proj_tag = extract_project_tag(text)
            text = re.sub(r'\s*\([^)]+\)\s*$', '', text)
            cls = "done" if wi["done"] else ""
            check = "checked" if wi["done"] else ""
            mark = "✓" if wi["done"] else ""
            accent, bg = project_color(proj_tag)
            weekly_html_items += f'''<div class="flow-item {cls}" data-project="{proj_tag}" style="background:{bg};border-left:3px solid {accent}">
                <span class="check-box {check}" style="width:12px;height:12px;font-size:8px">{mark}</span> {text}
            </div>'''
        if not weekly_html_items:
            weekly_html_items = '<div class="flow-item weekly" style="opacity:0.4">미설정</div>'

        # Build daily column
        daily_items_html = ""
        if chains:
            for c in chains:
                cls = "done" if c["daily_done"] else ""
                check = "checked" if c["daily_done"] else ""
                mark = "✓" if c["daily_done"] else ""
                accent, bg = project_color(c["project"])
                daily_items_html += f'''<div class="flow-item {cls}" data-project="{c["project"]}" style="background:{bg};border-left:3px solid {accent}">
                    <span class="check-box {check}" style="width:12px;height:12px;font-size:8px">{mark}</span> {c["daily"]}
                </div>'''
        else:
            items = parse_checklist_items(goals["daily"]["body"], "오늘 목표")
            if not items:
                items = parse_checklist_items(goals["daily"]["body"])
            for item in items:
                text = strip_wiki_links(item["text"])
                proj_tag = extract_project_tag(text)
                text = re.sub(r'\s*\([^)]+\)\s*$', '', text)
                cls = "done" if item["done"] else ""
                check = "checked" if item["done"] else ""
                mark = "✓" if item["done"] else ""
                accent, bg = project_color(proj_tag)
                daily_items_html += f'''<div class="flow-item {cls}" data-project="{proj_tag}" style="background:{bg};border-left:3px solid {accent}">
                    <span class="check-box {check}" style="width:12px;height:12px;font-size:8px">{mark}</span> {text}
                </div>'''

        theme = ""
        if "monthly" in goals:
            theme = goals["monthly"]["meta"].get("theme", "")

        daily_html = f"""
        <div class="section-card" style="border-left-color: var(--green)">
            <div class="section-header">
                <span class="section-label">🎯 목표 흐름</span>
                <span class="section-pct" style="color: var(--green)">{done_count}/{total_count}</span>
            </div>
            {"<div style='font-size:0.85em;color:var(--text2);margin-bottom:12px'>테마: " + theme + "</div>" if theme else ""}
            <div class="goal-flow-wrap" id="goalFlowWrap">
                <svg class="goal-flow-svg" id="goalFlowSvg"></svg>
                <div class="goal-flow" id="goalFlow">
                    <div class="goal-flow-col" id="colDaily">
                        <div class="goal-flow-header daily">오늘</div>
                        {daily_items_html}
                    </div>
                    <div class="goal-flow-col" id="colWeekly">
                        <div class="goal-flow-header weekly">이번 주</div>
                        {weekly_html_items}
                    </div>
                    <div class="goal-flow-col" id="colMonthly">
                        <div class="goal-flow-header monthly">이번 달</div>
                        {monthly_html}
                    </div>
                </div>
            </div>
        </div>"""

    # --- Weekly goal ---
    weekly_html = ""
    if "weekly" in goals:
        w = goals["weekly"]
        items = parse_checklist_items(w["body"], "목표")
        if not items:
            items = parse_checklist_items(w["body"])
        done_count = sum(1 for i in items if i["done"])
        total_count = len(items)
        pct = round(done_count / total_count * 100) if total_count > 0 else 0
        period = w["meta"].get("period", "")
        theme = w["meta"].get("theme", "")

        items_html = ""
        for item in items:
            check = "checked" if item["done"] else ""
            mark = "✓" if item["done"] else ""
            cls = "done" if item["done"] else ""
            items_html += f'<li class="{cls}"><span class="check-box {check}">{mark}</span>{item["text"]}</li>'

        weekly_html = f"""
        <div class="section-card weekly">
            <div class="section-header">
                <span class="section-label">📊 이번 주 ({period})</span>
                <span class="section-pct">{pct}%</span>
            </div>
            {"<div class='section-theme'>" + theme + "</div>" if theme else ""}
            <div class="progress-bar"><div class="progress-fill weekly" style="width:{pct}%"></div></div>
            <ul class="checklist">{items_html}</ul>
        </div>"""

    # --- Todo list ---
    todo_rows = ""
    for t in todo_tasks:
        pname = t.get('_project_name', '')
        todo_rows += f"""<tr>
            <td><code>{t.get('id','')}</code></td>
            <td>{t.get('title','')}</td>
            <td>{priority_badge_html(t.get('priority','medium'))}</td>
            <td>{format_date(t.get('deadline',''))}</td>
            <td class="project-cell">{project_dot_html(pname)} {pname}</td>
        </tr>"""

    todo_html = f"""
    <div class="section-card">
        <div class="section-header">
            <span class="section-label">🔥 내가 할 일</span>
            <span class="section-count">{len(todo_tasks)}</span>
        </div>
        <table class="task-table">
            <thead><tr><th>ID</th><th>제목</th><th>우선순위</th><th>마감</th><th>프로젝트</th></tr></thead>
            <tbody>{todo_rows}</tbody>
        </table>
    </div>""" if todo_tasks else ""

    # --- In-progress ---
    ip_rows = ""
    for t in ip_tasks:
        updated_by = t.get("updated_by", t.get("owner", "unassigned"))
        activity = t.get("_last_activity", "")
        if len(activity) > 30:
            activity = activity[:30] + "…"
        pname = t.get('_project_name', '')
        ip_rows += f"""<tr>
            <td><code>{t.get('id','')}</code></td>
            <td>{project_dot_html(pname)} {t.get('title','')}</td>
            <td>{owner_badge_html(updated_by)}</td>
            <td class="activity-cell">{activity}</td>
        </tr>"""

    ip_html = f"""
    <div class="section-card">
        <div class="section-header">
            <span class="section-label">⚡ 진행 중</span>
            <span class="section-count">{len(ip_tasks)}</span>
        </div>
        <table class="task-table">
            <thead><tr><th>ID</th><th>제목</th><th>담당</th><th>최근 활동</th></tr></thead>
            <tbody>{ip_rows}</tbody>
        </table>
    </div>""" if ip_tasks else ""

    # --- Recent done ---
    done_rows = ""
    for t in recent_done[:10]:
        updated_by = t.get("updated_by", t.get("owner", ""))
        pname = t.get('_project_name', '')
        done_rows += f"""<tr>
            <td><code>{t.get('id','')}</code></td>
            <td>{project_dot_html(pname)} {t.get('title','')}</td>
            <td>{owner_badge_html(updated_by)}</td>
            <td>{format_date(t.get('completed', t.get('updated_at','')))}</td>
        </tr>"""

    done_html = f"""
    <div class="section-card">
        <div class="section-header">
            <span class="section-label">✅ 최근 완료</span>
            <span class="section-count">{len(recent_done)}</span>
        </div>
        <table class="task-table">
            <thead><tr><th>ID</th><th>제목</th><th>담당</th><th>완료일</th></tr></thead>
            <tbody>{done_rows}</tbody>
        </table>
    </div>""" if recent_done else ""

    # --- Blocked ---
    blocked_html = ""
    if blocked_tasks:
        blocked_rows = ""
        for t in blocked_tasks:
            pname = t.get('_project_name', '')
            blocked_rows += f"""<tr>
                <td><code>{t.get('id','')}</code></td>
                <td>{t.get('title','')}</td>
                <td class="project-cell">{project_dot_html(pname)} {pname}</td>
            </tr>"""
        blocked_html = f"""
        <div class="section-card blocked">
            <div class="section-header">
                <span class="section-label">🚫 차단됨</span>
                <span class="section-count">{len(blocked_tasks)}</span>
            </div>
            <table class="task-table">
                <thead><tr><th>ID</th><th>제목</th><th>프로젝트</th></tr></thead>
                <tbody>{blocked_rows}</tbody>
            </table>
        </div>"""

    # --- Stats ---
    stats_html = f"""
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-label">전체</div><div class="stat-number">{len(tasks)}</div></div>
        <div class="stat-card"><div class="stat-label">할 일</div><div class="stat-number todo">{len(todo_tasks)}</div></div>
        <div class="stat-card"><div class="stat-label">진행 중</div><div class="stat-number ip">{len(ip_tasks)}</div></div>
        <div class="stat-card"><div class="stat-label">완료</div><div class="stat-number done">{len(done_tasks)}</div></div>
        <div class="stat-card"><div class="stat-label">차단</div><div class="stat-number blocked">{len(blocked_tasks)}</div></div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MingMing Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --bg: #f8f9fa; --surface: #ffffff; --text: #1a1a2e; --text2: #6c757d;
            --border: #e9ecef; --primary: #2c3e50;
            --green: #27ae60; --blue: #2980b9; --purple: #8e44ad;
            --red: #e74c3c; --orange: #f39c12; --gray: #adb5bd;
            --radius: 10px;
            --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg); color: var(--text); line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}

        .header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid var(--border);
        }}
        .header h1 {{ font-size: 1.5em; color: var(--primary); }}
        .header-meta {{ font-size: 0.85em; color: var(--text2); }}

        .stats-grid {{
            display: grid; grid-template-columns: repeat(5, 1fr);
            gap: 12px; margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--surface); padding: 16px; border-radius: var(--radius);
            box-shadow: var(--shadow); text-align: center;
        }}
        .stat-label {{ font-size: 0.75em; color: var(--text2); text-transform: uppercase; font-weight: 600; }}
        .stat-number {{ font-size: 2em; font-weight: 800; color: var(--primary); }}
        .stat-number.todo {{ color: var(--gray); }}
        .stat-number.ip {{ color: var(--blue); }}
        .stat-number.done {{ color: var(--green); }}
        .stat-number.blocked {{ color: var(--red); }}

        .dashboard-grid {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;
        }}
        .dashboard-grid.full {{ grid-template-columns: 1fr; }}

        .section-card {{
            background: var(--surface); border-radius: var(--radius);
            padding: 20px; box-shadow: var(--shadow);
            border-left: 4px solid var(--primary);
        }}
        .section-card.daily {{ border-left-color: var(--green); }}
        .section-card.weekly {{ border-left-color: var(--blue); }}
        .section-card.blocked {{ border-left-color: var(--red); }}

        .section-header {{
            display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
        }}
        .section-label {{ font-size: 1.05em; font-weight: 700; color: var(--primary); }}
        .section-pct {{ font-size: 1.3em; font-weight: 800; }}
        .section-card.daily .section-pct {{ color: var(--green); }}
        .section-card.weekly .section-pct {{ color: var(--blue); }}
        .section-count {{
            font-size: 0.85em; font-weight: 600; color: var(--text2);
            background: var(--bg); padding: 2px 10px; border-radius: 12px;
        }}
        .section-theme {{ font-size: 0.9em; color: var(--text2); margin-bottom: 8px; }}

        .progress-bar {{
            width: 100%; height: 6px; background: var(--border);
            border-radius: 3px; overflow: hidden; margin-bottom: 12px;
        }}
        .progress-fill {{ height: 100%; border-radius: 3px; transition: width 0.8s ease; }}
        .progress-fill.daily {{ background: linear-gradient(90deg, #27ae60, #2ecc71); }}
        .progress-fill.weekly {{ background: linear-gradient(90deg, #2980b9, #3498db); }}

        .checklist {{ list-style: none; }}
        .checklist li {{
            display: flex; align-items: center; gap: 8px;
            padding: 6px 0; font-size: 0.9em; color: var(--text);
            border-bottom: 1px solid var(--border);
        }}
        .checklist li:last-child {{ border-bottom: none; }}
        .checklist li.done {{ color: var(--text2); text-decoration: line-through; opacity: 0.6; }}
        .check-box {{
            width: 16px; height: 16px; border-radius: 3px;
            border: 2px solid var(--border); flex-shrink: 0;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 10px;
        }}
        .check-box.checked {{ background: var(--green); border-color: var(--green); color: white; }}

        .goal-flow-wrap {{ position: relative; }}
        .goal-flow {{
            display: grid; grid-template-columns: 1.5fr 1fr 1fr;
            gap: 32px; position: relative;
        }}
        .goal-flow-svg {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 1;
        }}
        .goal-flow-col {{ position: relative; z-index: 2; }}
        .goal-flow-header {{
            font-size: 0.7em; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.5px; color: var(--text2); margin-bottom: 10px;
            padding-bottom: 6px; border-bottom: 1px solid var(--border);
        }}
        .goal-flow-header.monthly {{ color: var(--purple); border-bottom-color: var(--purple); }}
        .goal-flow-header.weekly {{ color: var(--blue); border-bottom-color: var(--blue); }}
        .goal-flow-header.daily {{ color: var(--green); border-bottom-color: var(--green); }}

        .flow-item {{
            position: relative; padding: 8px 10px; margin-bottom: 8px;
            border-radius: 6px; font-size: 0.85em; line-height: 1.4;
        }}
        /* flow-item colors set inline per project */
        .flow-item.done {{ opacity: 0.5; text-decoration: line-through; }}
        .flow-item .check-box {{ vertical-align: middle; display: inline-flex; margin-right: 4px; }}

        @media (max-width: 768px) {{
            .goal-flow {{ grid-template-columns: 1fr; gap: 16px; }}
            .goal-flow-svg {{ display: none; }}
        }}

        .task-table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
        .task-table thead {{ background: var(--bg); }}
        .task-table th {{
            padding: 8px 10px; text-align: left; font-weight: 600; font-size: 0.8em;
            color: var(--text2); text-transform: uppercase; letter-spacing: 0.3px;
            border-bottom: 2px solid var(--border);
        }}
        .task-table td {{ padding: 10px; border-bottom: 1px solid var(--border); }}
        .task-table tbody tr:hover {{ background: var(--bg); }}
        .task-table code {{ font-size: 0.85em; color: var(--blue); }}
        .activity-cell {{ color: var(--text2); font-size: 0.9em; }}
        .project-cell {{ color: var(--text2); }}
        .project-dot {{
            display: inline-block; width: 8px; height: 8px; border-radius: 50%;
            vertical-align: middle; margin-right: 4px;
        }}

        .owner-badge {{
            display: inline-flex; align-items: center; gap: 4px;
            padding: 2px 8px; border-radius: 10px; font-size: 0.85em; font-weight: 500;
        }}
        .owner-badge.claudecode {{ background: #e8f5e9; color: #2e7d32; }}
        .owner-badge.openclaw {{ background: #fff3e0; color: #e65100; }}
        .owner-badge.daye {{ background: #e3f2fd; color: #1565c0; }}
        .owner-badge.mingming {{ background: #f3e5f5; color: #7b1fa2; }}
        .owner-badge.unassigned {{ background: var(--bg); color: var(--text2); }}

        .priority-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 0.8em; font-weight: 600;
        }}
        .priority-badge.high {{ background: #ffcdd2; color: #c62828; }}
        .priority-badge.medium {{ background: #fff3e0; color: #e65100; }}
        .priority-badge.low {{ background: #e0f2f1; color: #004d40; }}

        .status-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.8em; font-weight: 600;
        }}
        .status-badge.todo {{ background: #e9ecef; color: #6c757d; }}
        .status-badge.in-progress {{ background: #d6eaf8; color: #2471a3; }}
        .status-badge.done {{ background: #d5f5e3; color: #1e8449; }}
        .status-badge.blocked {{ background: #fadbd8; color: #c0392b; }}

        .footer {{
            margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--border);
            text-align: center; color: var(--text2); font-size: 0.8em;
        }}

        @media (max-width: 768px) {{
            .container {{ padding: 16px; }}
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
            .dashboard-grid {{ grid-template-columns: 1fr; }}
            .header {{ flex-direction: column; gap: 8px; align-items: flex-start; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>MingMing Dashboard</h1>
            <span class="header-meta">{timestamp}</span>
        </div>

        {stats_html}

        <div class="dashboard-grid full">
            {daily_html}
        </div>

        <div class="dashboard-grid full">
            {ip_html}
        </div>

        <div class="dashboard-grid full">
            {todo_html}
        </div>

        <div class="dashboard-grid full">
            {done_html}
        </div>

        <div class="dashboard-grid full">
            {blocked_html}
        </div>

        <div class="footer">
            <p>Last updated: {timestamp} | Source: ~/clawd/memory/projects/</p>
        </div>
    </div>
    <script>
    const PROJECT_COLORS = {json.dumps({k: v[0] for k, v in PROJECT_COLORS.items()})};
    const DEFAULT_COLOR = '{DEFAULT_PROJECT_COLOR[0]}';

    function getProjectColor(tag) {{
        if (!tag) return DEFAULT_COLOR;
        tag = tag.toLowerCase();
        if (PROJECT_COLORS[tag]) return PROJECT_COLORS[tag];
        for (const [k, v] of Object.entries(PROJECT_COLORS)) {{
            if (k.includes(tag) || tag.includes(k)) return v;
        }}
        return DEFAULT_COLOR;
    }}

    function drawGoalConnections() {{
        const wrap = document.getElementById('goalFlowWrap');
        const svg = document.getElementById('goalFlowSvg');
        if (!wrap || !svg) return;

        const wrapRect = wrap.getBoundingClientRect();
        svg.setAttribute('width', wrapRect.width);
        svg.setAttribute('height', wrapRect.height);
        svg.innerHTML = '';

        function getCenter(el, side) {{
            const r = el.getBoundingClientRect();
            const x = side === 'right' ? r.right - wrapRect.left : r.left - wrapRect.left;
            const y = r.top + r.height / 2 - wrapRect.top;
            return {{ x, y }};
        }}

        function drawLine(from, to, color) {{
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const dx = (to.x - from.x) * 0.4;
            const d = `M${{from.x}},${{from.y}} C${{from.x + dx}},${{from.y}} ${{to.x - dx}},${{to.y}} ${{to.x}},${{to.y}}`;
            path.setAttribute('d', d);
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke', color);
            path.setAttribute('stroke-width', '2');
            path.setAttribute('stroke-opacity', '0.5');
            svg.appendChild(path);

            [from, to].forEach(pt => {{
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', pt.x);
                circle.setAttribute('cy', pt.y);
                circle.setAttribute('r', '3');
                circle.setAttribute('fill', color);
                circle.setAttribute('opacity', '0.6');
                svg.appendChild(circle);
            }});
        }}

        const dailyItems = document.querySelectorAll('#colDaily .flow-item');
        const weeklyItems = document.querySelectorAll('#colWeekly .flow-item');
        const monthlyItems = document.querySelectorAll('#colMonthly .flow-item');

        // Daily → Weekly (use daily item's project color)
        dailyItems.forEach(di => {{
            const dp = (di.dataset.project || '').toLowerCase();
            if (!dp) return;
            const color = getProjectColor(dp);
            weeklyItems.forEach(wi => {{
                const wp = (wi.dataset.project || '').toLowerCase();
                if (wp && (dp.includes(wp) || wp.includes(dp))) {{
                    drawLine(getCenter(di, 'right'), getCenter(wi, 'left'), color);
                }}
            }});
        }});

        // Weekly → Monthly (use weekly item's project color)
        weeklyItems.forEach(wi => {{
            const wp = (wi.dataset.project || '').toLowerCase();
            if (!wp) return;
            const color = getProjectColor(wp);
            monthlyItems.forEach(mi => {{
                const mp = (mi.dataset.project || '').toLowerCase();
                if (mp && (wp.includes(mp) || mp.includes(wp))) {{
                    drawLine(getCenter(wi, 'right'), getCenter(mi, 'left'), color);
                }}
            }});
        }});
    }}

    window.addEventListener('DOMContentLoaded', () => {{
        setTimeout(drawGoalConnections, 100);
    }});
    window.addEventListener('resize', drawGoalConnections);
    </script>
</body>
</html>"""

    return html


def main():
    print("Scanning vault...")
    tasks = scan_tasks()
    goals = scan_goals()
    print(f"  Tasks: {len(tasks)}, Goals: {len(goals)} periods")

    html = generate_html(tasks, goals)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  Dashboard written to: {output_path}")


if __name__ == "__main__":
    main()
