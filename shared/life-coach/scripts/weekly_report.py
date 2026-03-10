#!/usr/bin/env python3
"""Weekly HTML Report — 주간 코칭 리포트를 HTML로 생성.

Usage:
    python3 weekly_coach.py --json | python3 weekly_report.py
    python3 weekly_report.py --input data.json --coaching coaching.md
    python3 weekly_report.py --output /tmp/weekly_report.html
"""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timeline_html import build, timeline_section_html

KST = timezone(timedelta(hours=9))
WEEKDAY = "월화수목금토일"
TAG_COLORS = {
    "리팩토링": "#4A90D9", "디버깅": "#E07B5A", "코딩": "#7ABD7E",
    "설계": "#9B7BC8", "ops": "#F0C040", "문서": "#5AC8D9",
    "리뷰": "#D9A85A", "기타": "#707070",
}

# ── Helper ────────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000: return f"{n / 1_000_000:.1f}M"
    if n >= 1_000: return f"{n / 1_000:.1f}K"
    return str(n)

def _md_to_html(md: str) -> str:
    lines = md.strip().split("\n")
    out = []
    in_ul = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h4 class="coaching-h">{_esc(stripped[3:])}</h4>')
        elif stripped.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f'<h5 class="coaching-h sub">{_esc(stripped[4:])}</h5>')
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

# ── Section builders ──────────────────────────────────────────────────────────

def _build_stats_card(data: dict) -> str:
    items = [
        ("세션", str(data.get("total_sessions", 0))),
        ("작업시간", f'{data.get("total_hours", 0)}h'),
        ("토큰", _fmt_tokens(data.get("total_tokens", 0))),
        ("활동일", f'{sum(1 for d in data.get("daily", []) if d.get("sessions", 0) > 0)}일'),
    ]
    cards = "\n".join(
        f'<div class="stat-item"><div class="stat-val">{v}</div><div class="stat-lbl">{k}</div></div>'
        for k, v in items
    )
    return f'<div class="stats-row">{cards}</div>'


def _build_daily_heatmap(data: dict) -> str:
    """요일별 작업시간 히트맵."""
    daily = data.get("daily", [])
    if not daily:
        return ""
    max_hours = max((d.get("work_hours", 0) for d in daily), default=1) or 1

    cells = []
    for d in daily:
        wh = d.get("work_hours", 0)
        sess = d.get("sessions", 0)
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        label = f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})'
        opacity = max(0.15, wh / max_hours) if wh > 0 else 0.05
        cells.append(
            f'<div class="hm-cell" style="opacity:{opacity:.2f}">'
            f'<div class="hm-day">{label}</div>'
            f'<div class="hm-val">{wh}h</div>'
            f'<div class="hm-sess">{sess}세션</div>'
            f'</div>'
        )
    return f'<div class="heatmap">{"".join(cells)}</div>'


def _build_tag_breakdown(data: dict) -> str:
    tags = data.get("tags", {})
    if not tags:
        return ""
    items = sorted(tags.items(), key=lambda x: x[1], reverse=True)
    pills = []
    for tag, count in items:
        color = TAG_COLORS.get(tag, "#707070")
        pills.append(
            f'<span class="tag-pill" style="border-color:{color};color:{color}">'
            f'{tag} {count}</span>'
        )
    return f'<div class="tag-row">{" ".join(pills)}</div>'


def _build_repos_summary(data: dict) -> str:
    repos = data.get("repos", {})
    if not repos:
        return ""
    items = sorted(repos.items(), key=lambda x: x[1], reverse=True)
    rows = []
    total = sum(v for v in repos.values())
    for repo, count in items:
        pct = count / total * 100 if total else 0
        rows.append(
            f'<div class="repo-bar-row">'
            f'<span class="repo-bar-name">{_esc(repo)}</span>'
            f'<div class="repo-bar-track"><div class="repo-bar-fill" style="width:{pct:.0f}%"></div></div>'
            f'<span class="repo-bar-count">{count}세션</span>'
            f'</div>'
        )
    return f'<div class="section"><h3>레포별</h3>{"".join(rows)}</div>'


def _build_coaching_section(coaching_md: str | None) -> str:
    if not coaching_md:
        return """<div class="section coaching-placeholder">
<h3>코칭</h3>
<div class="coaching-empty">--coaching 파일을 전달하면 LLM 주간 코칭이 여기에 표시됩니다.</div>
</div>"""
    return f'<div class="section coaching">{_md_to_html(coaching_md)}</div>'


def _build_health_section(data: dict) -> str:
    parts = []
    exercises = data.get("exercises", [])
    if exercises:
        by_type: dict[str, int] = {}
        for e in exercises:
            by_type[e["type"]] = by_type.get(e["type"], 0) + e.get("duration_min", 0)
        ex_parts = [f'{t} {m}분' for t, m in sorted(by_type.items(), key=lambda x: -x[1])]
        parts.append(f'<div class="health-line">운동: {", ".join(ex_parts)}</div>')

    meals = data.get("meals", [])
    if meals:
        eaten = [m for m in meals if not m.get("skipped")]
        total_cal = sum(m.get("calories", 0) or 0 for m in eaten)
        parts.append(f'<div class="health-line">식사: {len(eaten)}끼 총 {total_cal}kcal</div>')

    symptoms = data.get("symptoms", [])
    if symptoms:
        by_type_s: dict[str, int] = {}
        for s in symptoms:
            by_type_s[s["type"]] = by_type_s.get(s["type"], 0) + 1
        sym_parts = [f'{t}({c}회)' for t, c in sorted(by_type_s.items(), key=lambda x: -x[1])]
        parts.append(f'<div class="health-line symptom">증상: {", ".join(sym_parts)}</div>')

    if not parts:
        return ""
    return f'<div class="section"><h3>건강 요약</h3>{"".join(parts)}</div>'


def _build_raw_signals(data: dict) -> str:
    signals = data.get("weekly_signals", [])
    repeated = data.get("repeated_patterns", [])
    if not signals and not repeated:
        return ""

    by_type: dict[str, list[str]] = {}
    for s in signals:
        by_type.setdefault(s.get("type", "pattern"), []).append(s.get("content", ""))

    type_config = {
        "mistake":  {"label": "시행착오", "cls": "sig-mistake"},
        "decision": {"label": "결정", "cls": "sig-decision"},
        "pattern":  {"label": "패턴", "cls": "sig-pattern"},
    }

    cards = []
    for t, cfg in type_config.items():
        items = by_type.get(t, [])
        if not items:
            continue
        li = "".join(f'<div class="raw-item">{_esc(c)}</div>' for c in items)
        cards.append(
            f'<div class="raw-card {cfg["cls"]}">'
            f'<div class="raw-hdr">{cfg["label"]} <span class="raw-count">{len(items)}</span></div>'
            f'{li}</div>'
        )

    if repeated:
        li = "".join(
            f'<div class="raw-item raw-repeat-item">"{_esc(r["content"])}" ({r["count"]}회)</div>'
            for r in repeated
        )
        cards.append(
            f'<div class="raw-card sig-repeat">'
            f'<div class="raw-hdr">반복 패턴<span class="raw-sublabel">최근 7일</span></div>'
            f'{li}</div>'
        )

    inner = "".join(cards)
    return f"""<details class="raw-details">
<summary class="raw-summary">행동 신호 원시 데이터 ({len(signals)}건)</summary>
<div class="raw-grid">{inner}</div>
</details>"""


# ── Page assembly ─────────────────────────────────────────────────────────────

PAGE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#1C1C1E;--bg2:#242426;--bg3:#2C2C2E;--bd:#333;--tx:#E0E0E0;--mu:#888;--lw:170px}
body{background:var(--bg);color:var(--tx);font-family:-apple-system,"Apple SD Gothic Neo",sans-serif;font-size:13px;padding:28px 32px;max-width:1200px;margin:0 auto}
h1{font-size:20px;font-weight:700;color:#F0F0F0;margin-bottom:6px}
.subtitle{font-size:13px;color:var(--mu);margin-bottom:24px}
.stats-row{display:flex;gap:16px;margin-bottom:20px}
.stat-item{background:var(--bg2);border-radius:10px;padding:14px 20px;flex:1;text-align:center}
.stat-val{font-size:22px;font-weight:700;color:#F0F0F0}
.stat-lbl{font-size:11px;color:var(--mu);margin-top:2px}
.heatmap{display:flex;gap:6px;margin-bottom:20px}
.hm-cell{flex:1;background:#7ABD7E;border-radius:8px;padding:10px 8px;text-align:center}
.hm-day{font-size:11px;font-weight:600;color:#1C1C1E}
.hm-val{font-size:16px;font-weight:700;color:#1C1C1E}
.hm-sess{font-size:10px;color:#2A2A2A}
.tag-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.tag-pill{border:1px solid;border-radius:12px;padding:3px 10px;font-size:11px;font-weight:600}
.section{background:var(--bg2);border-radius:10px;padding:16px 20px;margin-bottom:16px}
.section h3{font-size:14px;font-weight:600;color:#CCC;margin-bottom:10px}
.repo-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.repo-bar-name{width:140px;font-size:12px;color:#CCC;text-align:right;flex-shrink:0}
.repo-bar-track{flex:1;height:18px;background:var(--bg3);border-radius:4px;overflow:hidden}
.repo-bar-fill{height:100%;background:#4A90D9;border-radius:4px;min-width:2px}
.repo-bar-count{width:60px;font-size:11px;color:var(--mu);flex-shrink:0}
.coaching{border-left:4px solid #7ABD7E}
.coaching-h{font-size:14px;font-weight:700;color:#E0E0E0;margin:14px 0 6px}
.coaching-h:first-child{margin-top:0}
.coaching-h.sub{font-size:12px;color:#CCC;margin:10px 0 4px}
.coaching p{font-size:13px;color:#C0C0C0;line-height:1.7;margin-bottom:6px}
.coaching strong{color:#E0E0E0}
.coaching-list{list-style:none;padding:0;margin:0 0 8px}
.coaching-list li{font-size:12px;color:#C0C0C0;padding:3px 0;padding-left:14px;position:relative;line-height:1.6}
.coaching-list li::before{content:"•";position:absolute;left:0;color:var(--mu)}
.coaching-placeholder{border:1px dashed #444;background:transparent}
.coaching-empty{color:#555;font-size:12px;font-style:italic}
.health-line{font-size:12px;color:#B0B0B0;margin-bottom:4px}
.health-line.symptom{color:#E07B5A}
.raw-details{margin-top:24px;margin-bottom:16px}
.raw-summary{font-size:12px;color:#666;cursor:pointer;padding:8px 0;user-select:none}
.raw-summary:hover{color:#999}
.raw-grid{display:flex;flex-direction:column;gap:10px;margin-top:10px}
.raw-card{border-radius:8px;padding:12px 14px;border-left:3px solid}
.raw-card.sig-mistake{background:#2A1A1A;border-color:#E07B5A}
.raw-card.sig-decision{background:#1A2233;border-color:#4A90D9}
.raw-card.sig-pattern{background:#221A2E;border-color:#9B7BC8}
.raw-card.sig-repeat{background:#2A2218;border-color:#F0C040}
.raw-hdr{font-size:12px;font-weight:700;color:#CCC;margin-bottom:6px}
.raw-count{background:rgba(255,255,255,.1);color:#AAA;font-size:10px;font-weight:600;padding:1px 7px;border-radius:10px}
.raw-sublabel{font-size:10px;color:#888;font-weight:400;margin-left:6px}
.raw-item{font-size:11px;color:#999;padding:2px 0;line-height:1.5}
.raw-repeat-item{color:#D9A85A}
#timeline-section{margin-bottom:20px}
.footer{font-size:10px;color:#444;text-align:center;margin-top:32px;padding-top:16px;border-top:1px solid #282828}
"""


def build_weekly_report(data: dict, coaching_md: str | None = None) -> str:
    dates = data.get("dates", [])
    if not dates:
        return "<html><body>No weekly data.</body></html>"

    mon = datetime.strptime(dates[0], "%Y-%m-%d")
    sun = datetime.strptime(dates[-1], "%Y-%m-%d")
    title = f"{mon.month}/{mon.day} ~ {sun.month}/{sun.day} 주간 리포트"

    # Timeline
    _, days = build(data, weekly=True)
    timeline = timeline_section_html(days, f"{mon.month}/{mon.day} ~ {sun.month}/{sun.day} 타임라인")

    sections = [
        _build_stats_card(data),
        _build_daily_heatmap(data),
        _build_tag_breakdown(data),
        timeline,
        _build_repos_summary(data),
        _build_coaching_section(coaching_md),
        _build_health_section(data),
        _build_raw_signals(data),
    ]

    body = "\n".join(s for s in sections if s)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"><title>{title}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>{title}</h1>
<div class="subtitle">{data.get('total_sessions', 0)}세션 · {data.get('total_hours', 0)}시간 · {_fmt_tokens(data.get('total_tokens', 0))} tokens</div>
{body}
<div class="footer">generated by life-coach/weekly_report.py</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Weekly HTML report")
    parser.add_argument("--input", help="JSON file (default: stdin)")
    parser.add_argument("--coaching", help="LLM coaching markdown file")
    parser.add_argument("--output", default="/tmp/weekly_report.html")
    args = parser.parse_args()

    raw = json.load(open(args.input) if args.input else sys.stdin)

    coaching_md = None
    if args.coaching:
        coaching_md = Path(args.coaching).read_text(encoding="utf-8")

    html = build_weekly_report(raw, coaching_md)

    Path(args.output).write_text(html, encoding="utf-8")
    print(f"[weekly_report] saved: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
