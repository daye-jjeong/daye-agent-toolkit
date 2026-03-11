#!/usr/bin/env python3
"""Daily HTML Report — 일일 코칭 리포트를 HTML로 생성.

Usage:
    # 데이터만 (코칭 placeholder)
    python3 daily_coach.py --json | python3 daily_report.py

    # LLM 코칭 텍스트 포함
    python3 daily_coach.py --json | python3 daily_report.py --coaching coaching.md

    # 옵션
    python3 daily_report.py --input data.json --coaching coaching.md --output /tmp/daily_report.html

--coaching: LLM이 생성한 마크다운 파일. 섹션 헤더(## 오늘의 정리, ## 코칭 등)로 구분.
없으면 placeholder 표시.
"""
import argparse, json, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timeline_html import build, timeline_section_html
from _helpers import (
    WEEKDAY, TAG_COLORS, esc_html as _esc, fmt_tokens as _fmt_tokens, md_to_html,
    group_sessions_by_repo_branch, has_meaningful_branches,
)

# ── Section builders ──────────────────────────────────────────────────────────

def _build_stats_card(data: dict) -> str:
    sc = data.get("session_count", 0)
    wh = data.get("work_hours", 0)
    tok = data.get("token_total", 0)
    first = data.get("first_session", "")
    last = data.get("last_session_end", "")

    items = [
        ("세션", str(sc)),
        ("작업시간", f"{wh}h"),
        ("토큰", f"{_fmt_tokens(tok)}"),
    ]
    if first and last:
        items.append(("활동 시간대", f"{first} ~ {last}"))

    cards = "\n".join(
        f'<div class="stat-item"><div class="stat-val">{v}</div><div class="stat-lbl">{k}</div></div>'
        for k, v in items
    )
    return f'<div class="stats-row">{cards}</div>'


def _build_tag_breakdown(data: dict) -> str:
    tags = data.get("tag_breakdown", {})
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


def _build_nudges(data: dict) -> str:
    nudges = []
    wh = data.get("work_hours", 0)
    if wh >= 8:
        nudges.append(f'<div class="nudge warn">{wh}시간 작업 — 과작업 주의</div>')
    first = data.get("first_session", "")
    if first and first < "06:00":
        nudges.append('<div class="nudge warn">새벽 작업 감지 — 수면 패턴 주의</div>')
    if not nudges:
        return ""
    return f'<div class="nudge-row">{"".join(nudges)}</div>'


def _build_session_row(s: dict) -> str:
    start = (s.get("start_at") or "")[11:16] or "?"
    tag = s.get("tag") or "기타"
    summary = _esc(s.get("summary") or "")
    tag_color = TAG_COLORS.get(tag, "#707070")
    return (
        f'<div class="sess-row">'
        f'<span class="sess-time">{start}</span>'
        f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span>'
        f'<span class="sess-summary">{summary}</span>'
        f'</div>'
    )


def _build_repos_detail(data: dict) -> str:
    sessions = data.get("sessions", [])
    if not sessions:
        return ""

    rows = []
    for repo, total_dur, total_tok, branch_groups in group_sessions_by_repo_branch(sessions, short_repo=True):
        sess_count = sum(len(bs) for bs in branch_groups.values())
        h, m = divmod(total_dur, 60)
        dur_str = f"{h}h {m}m" if h else f"{m}m"
        meta = f'{sess_count}세션 · {dur_str}'
        if total_tok > 0:
            meta += f' · {_fmt_tokens(total_tok)} tokens'

        inner_html = ""
        if has_meaningful_branches(branch_groups):
            for branch, bsess in branch_groups.items():
                if branch:
                    inner_html += (
                        f'<div class="branch-group">'
                        f'<div class="branch-name">{_esc(branch)}</div>'
                    )
                    inner_html += "".join(_build_session_row(s) for s in bsess)
                    inner_html += '</div>'
                else:
                    inner_html += "".join(_build_session_row(s) for s in bsess)
        else:
            all_sess = list(branch_groups.values())[0] if branch_groups else []
            inner_html = "".join(_build_session_row(s) for s in all_sess)

        rows.append(
            f'<div class="repo-group">'
            f'<div class="repo-name">{_esc(repo)} <span class="repo-meta">{meta}</span></div>'
            f'{inner_html}'
            f'</div>'
        )
    return f'<div class="section"><h3>레포별 세션</h3>{"".join(rows)}</div>'


def _build_coaching_section(coaching_md: str | None) -> str:
    if not coaching_md:
        return """<div class="section coaching-placeholder" id="coaching-section">
<h3>코칭</h3>
<div class="coaching-empty">--coaching 파일을 전달하면 LLM 코칭 분석이 여기에 표시됩니다.</div>
</div>"""
    return f'<div class="section coaching" id="coaching-section">{md_to_html(coaching_md)}</div>'


def _build_raw_signals(data: dict) -> str:
    """행동 신호 원시 데이터 — 접힌 상태로 하단에."""
    signals = data.get("behavioral_signals", [])
    repeated = data.get("repeated_patterns", [])
    if not signals and not repeated:
        return ""

    by_type: dict[str, list[str]] = {}
    for s in signals:
        by_type.setdefault(s["type"], []).append(s["content"])

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
            f'<div class="raw-item raw-repeat-item">'
            f'"{_esc(r["content"])}" ({r["count"]}회)</div>'
            for r in repeated
        )
        cards.append(
            f'<div class="raw-card sig-repeat">'
            f'<div class="raw-hdr">반복 패턴 <span class="raw-sublabel">최근 7일</span></div>'
            f'{li}</div>'
        )

    inner = "".join(cards)
    return f"""<details class="raw-details">
<summary class="raw-summary">행동 신호 원시 데이터 ({len(signals)}건)</summary>
<div class="raw-grid">{inner}</div>
</details>"""


def _build_health_section(data: dict) -> str:
    parts = []
    ci = data.get("check_in")
    if ci:
        metrics = []
        if ci.get("sleep_hours"): metrics.append(f'수면 {ci["sleep_hours"]}h')
        if ci.get("steps"): metrics.append(f'걸음 {ci["steps"]}')
        if ci.get("stress"): metrics.append(f'스트레스 {ci["stress"]}/10')
        if ci.get("water_ml"): metrics.append(f'수분 {ci["water_ml"]}ml')
        if metrics:
            parts.append(f'<div class="health-metrics">{" · ".join(metrics)}</div>')

    exercises = data.get("exercises", [])
    if exercises:
        ex = ", ".join(f'{e["type"]} {e["duration_min"]}분' for e in exercises)
        parts.append(f'<div class="health-line">운동: {ex}</div>')

    meals = data.get("meals", [])
    if meals:
        eaten = [m for m in meals if not m.get("skipped")]
        total_cal = sum(m.get("calories", 0) or 0 for m in eaten)
        total_protein = sum(m.get("protein_g", 0) or 0 for m in eaten)
        parts.append(f'<div class="health-line">식사: {len(eaten)}끼 ({total_cal}kcal, 단백질 {total_protein:.0f}g)</div>')

    symptoms = data.get("symptoms", [])
    if symptoms:
        sym = ", ".join(f'{s["type"]}({s["severity"]})' for s in symptoms)
        parts.append(f'<div class="health-line symptom">증상: {sym}</div>')

    if not parts:
        return ""
    return f'<div class="section"><h3>건강</h3>{"".join(parts)}</div>'


def _build_pantry_section(data: dict) -> str:
    pantry = data.get("pantry_expiry", {})
    expired = pantry.get("expired", [])
    expiring = pantry.get("expiring", [])
    if not expired and not expiring:
        return ""
    lines = []
    if expired:
        names = ", ".join(i["name"] for i in expired)
        lines.append(f'<div class="health-line symptom">만료: {names}</div>')
    if expiring:
        names = ", ".join(i["name"] for i in expiring)
        lines.append(f'<div class="health-line">임박: {names}</div>')
    return f'<div class="section"><h3>유통기한</h3>{"".join(lines)}</div>'


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
.tag-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.tag-pill{border:1px solid;border-radius:12px;padding:3px 10px;font-size:11px;font-weight:600}
.section{background:var(--bg2);border-radius:10px;padding:16px 20px;margin-bottom:16px}
.section h3{font-size:14px;font-weight:600;color:#CCC;margin-bottom:10px}
.nudge-row{margin-bottom:16px}
.nudge{padding:8px 14px;border-radius:8px;font-size:12px;font-weight:600;margin-bottom:6px}
.nudge.warn{background:#3A2A1A;color:#F0C040;border-left:3px solid #F0C040}
.repo-group{margin-bottom:12px}
.repo-group:last-child{margin-bottom:0}
.repo-name{font-size:13px;font-weight:600;color:#D0D0D0;margin-bottom:4px}
.repo-meta{font-size:11px;font-weight:400;color:var(--mu)}
.sess-row{display:flex;gap:8px;font-size:12px;padding:2px 0;color:#B0B0B0}
.sess-time{color:var(--mu);flex-shrink:0;width:40px}
.sess-tag{flex-shrink:0;font-weight:600;font-size:11px}
.sess-summary{line-height:1.5}
.branch-group{margin:6px 0 8px 12px;padding-left:10px;border-left:2px solid #444}
.branch-name{font-size:11px;color:#9B7BC8;font-weight:600;margin-bottom:2px}
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
.health-metrics{font-size:13px;color:var(--tx);margin-bottom:6px}
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
.raw-sublabel{font-size:10px;color:#888;font-weight:400}
.raw-item{font-size:11px;color:#999;padding:2px 0;line-height:1.5}
.raw-repeat-item{color:#D9A85A}
#timeline-section{margin-bottom:20px}
.footer{font-size:10px;color:#444;text-align:center;margin-top:32px;padding-top:16px;border-top:1px solid #282828}
"""


def build_daily_report(data: dict, coaching_md: str | None = None) -> str:
    if not data.get("has_data"):
        return _build_empty_page(data.get("date", ""))

    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAY[dt.weekday()]
    title = f"{dt.month}/{dt.day}({weekday}) 데일리 리포트"

    # Timeline section
    _, days = build(data, weekly=False)
    timeline = timeline_section_html(days, f"{dt.month}/{dt.day}({weekday}) 타임라인")

    # Assemble sections
    sections = [
        _build_stats_card(data),
        _build_tag_breakdown(data),
        _build_nudges(data),
        timeline,
        _build_repos_detail(data),
        _build_coaching_section(coaching_md),
        _build_health_section(data),
        _build_pantry_section(data),
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
<div class="subtitle">{data.get('session_count', 0)}세션 · {data.get('work_hours', 0)}시간 · {_fmt_tokens(data.get('token_total', 0))} tokens</div>
{body}
<div class="footer">generated by life-coach/daily_report.py</div>
</body></html>"""


def _build_empty_page(date_str: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"><title>데일리 리포트</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>{date_str} 데일리 리포트</h1>
<div class="section"><p style="color:var(--mu)">오늘 기록된 세션이 없습니다.</p></div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Daily HTML report")
    parser.add_argument("--input", help="JSON file (default: stdin)")
    parser.add_argument("--coaching", help="LLM coaching markdown file")
    parser.add_argument("--output", default="/tmp/daily_report.html")
    args = parser.parse_args()

    raw = json.load(open(args.input) if args.input else sys.stdin)

    coaching_md = None
    if args.coaching:
        coaching_md = Path(args.coaching).read_text(encoding="utf-8")

    html = build_daily_report(raw, coaching_md)

    Path(args.output).write_text(html, encoding="utf-8")
    print(f"[daily_report] saved: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
