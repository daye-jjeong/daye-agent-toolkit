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
import argparse, json, re, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timeline_html import build, timeline_section_html
from _helpers import (
    WEEKDAY, TAG_COLORS, esc_html as _esc, fmt_tokens as _fmt_tokens, md_to_html,
    group_sessions_by_repo_branch, has_meaningful_branches, group_topics_by_repo,
)

# ── Section builders ──────────────────────────────────────────────────────────

def _calc_actual_work_hours(topics: list[dict], sessions: list[dict]) -> float:
    """토픽/세션의 시간 구간을 합쳐서 겹치지 않는 실제 작업 시간(h) 계산."""
    intervals = []
    for t in topics:
        sa, ea = t.get("start_at", ""), t.get("end_at", "")
        if sa and ea and len(sa) >= 16 and len(ea) >= 16:
            try:
                s = int(sa[11:13]) * 60 + int(sa[14:16])
                e = int(ea[11:13]) * 60 + int(ea[14:16])
                if e > s:
                    intervals.append((s, e))
            except (ValueError, IndexError):
                pass
    if not intervals:
        # 폴백: sessions 기반
        for s in sessions:
            sa, ea = s.get("start_at", ""), s.get("end_at", "")
            dur = s.get("duration_min", 0) or 0
            if sa and len(sa) >= 16 and dur > 0:
                try:
                    start = int(sa[11:13]) * 60 + int(sa[14:16])
                    intervals.append((start, start + dur))
                except (ValueError, IndexError):
                    pass
    if not intervals:
        return 0.0
    # 겹치는 구간 병합
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    total_min = sum(e - s for s, e in merged)
    return round(total_min / 60, 1)


def _build_stats_card(data: dict) -> str:
    sc = data.get("session_count", 0)
    tok = data.get("token_total", 0)
    first = data.get("first_session", "")
    last = data.get("last_session_end", "")
    topics = data.get("topics", [])
    sessions = data.get("sessions", [])

    actual_hours = _calc_actual_work_hours(topics, sessions)

    items = [
        ("세션", str(sc)),
        ("작업시간", f"{first}~{last}" if first and last else "—"),
        ("활동", f"{actual_hours}h"),
        ("토큰", f"{_fmt_tokens(tok)}"),
    ]

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
    actual = _calc_actual_work_hours(data.get("topics", []), data.get("sessions", []))
    if actual >= 8:
        nudges.append(f'<div class="nudge warn">{actual}h 활동 — 과작업 주의</div>')
    first = data.get("first_session", "")
    if first and first < "06:00":
        nudges.append('<div class="nudge warn">새벽 작업 감지 — 수면 패턴 주의</div>')
    if not nudges:
        return ""
    return f'<div class="nudge-row">{"".join(nudges)}</div>'


STATUS_STYLES = {
    "completed": ("✓", "#7ABD7E"),
    "in_progress": ("◦", "#888"),
    "blocked": ("✕", "#E07B5A"),
    "follow_up": ("→", "#F0C040"),
}

def _status_badge(status: str) -> str:
    icon, color = STATUS_STYLES.get(status, ("◦", "#888"))
    return f'<span class="status-badge" style="color:{color}" title="{status}">{icon}</span> '


_NOISE_PATTERNS = ("/clear", "세션 초기화")


def _is_noise_topic(t: dict) -> bool:
    """리포트에서 생략할 잡음 토픽."""
    dur = t.get("duration_estimate_min", 0) or 0
    summary = (t.get("summary") or "").lower()
    if dur <= 1 and any(p in summary for p in _NOISE_PATTERNS):
        return True
    return False


def _build_topic_items(topics: list[dict]) -> str:
    """session_topics 기준 작업 표시 — 같은 세션의 토픽은 한 줄로 합침."""
    # 세션별 그룹핑 (잡음 토픽 제외)
    by_session: dict[str, list[dict]] = {}
    for t in topics:
        if _is_noise_topic(t):
            continue
        sid = t.get("session_id", "?")
        by_session.setdefault(sid, []).append(t)

    items = []
    for sid, session_topics in by_session.items():
        if len(session_topics) == 1:
            t = session_topics[0]
            tag = t.get("tag") or "기타"
            tag_color = TAG_COLORS.get(tag, "#707070")
            summary = _esc(t.get("summary") or "(요약 없음)")
            status = t.get("status", "in_progress")
            status_badge = _status_badge(status)
            dur = t.get("duration_estimate_min")
            meta_parts = []
            if dur:
                meta_parts.append(f"{dur}m")
            if t.get("has_commits"):
                meta_parts.append("커밋")
            meta_str = f' <span class="work-meta">({", ".join(meta_parts)})</span>' if meta_parts else ""
            follow_up = t.get("follow_up", "")
            follow_html = f' <span class="follow-up">→ {_esc(follow_up)}</span>' if follow_up else ""
            items.append(
                f'<div class="work-item">'
                f'{status_badge}'
                f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span> '
                f'<span class="work-summary">{summary}{meta_str}{follow_html}</span>'
                f'</div>'
            )
        else:
            # 복수 토픽 → 태그 모아서 한 줄 + 서브 아이템
            total_dur = sum(t.get("duration_estimate_min", 0) or 0 for t in session_topics)
            tags = list(dict.fromkeys(t.get("tag", "기타") for t in session_topics))
            tag_html = " ".join(
                f'<span class="sess-tag" style="color:{TAG_COLORS.get(tg, "#707070")}">[{tg}]</span>'
                for tg in tags
            )
            # 가장 대표적인 status
            statuses = [t.get("status", "in_progress") for t in session_topics]
            status = "in_progress" if "in_progress" in statuses else statuses[0]
            status_badge = _status_badge(status)
            has_commits = any(t.get("has_commits") for t in session_topics)
            meta_parts = []
            if has_commits:
                meta_parts.append("커밋")
            commit_str = f' <span class="work-meta">({", ".join(meta_parts)})</span>' if meta_parts else ""
            total_str = f' <span class="work-meta" style="margin-left:4px;color:#888">— 총 {total_dur}m</span>'
            # 서브 아이템: 항목(시간) 순서
            sub_items = []
            for t in session_topics:
                s = _esc(t.get("summary") or "")
                short = s.split(" — ")[0] if " — " in s else s[:80]
                dur_t = t.get("duration_estimate_min", 0) or 0
                follow_up = t.get("follow_up", "")
                follow_html = f' <span class="follow-up">→ {_esc(follow_up)}</span>' if follow_up else ""
                sub_items.append(f"{short} ({dur_t}m){follow_html}")
            sub_html = " / ".join(sub_items)
            items.append(
                f'<div class="work-item">'
                f'{status_badge}'
                f'{tag_html} '
                f'<span class="work-summary">{sub_html}{commit_str}{total_str}</span>'
                f'</div>'
            )
    return "".join(items)


def _build_work_items(sessions: list[dict], topics: list[dict] | None = None) -> str:
    """토픽별(우선) 또는 세션별 작업 표시."""
    if topics:
        return _build_topic_items(topics)

    # 기존 세션별 로직 (폴백)
    tag_groups: dict[str, list[dict]] = {}
    for s in sessions:
        tag = s.get("tag") or "기타"
        tag_groups.setdefault(tag, []).append(s)

    items = []
    for tag, group in sorted(
        tag_groups.items(),
        key=lambda x: sum(s.get("duration_min", 0) for s in x[1]),
        reverse=True,
    ):
        best = max(group, key=lambda s: (s.get("duration_min") or 0))
        summary = _esc(best.get("summary") or "(요약 없음)")
        tag_color = TAG_COLORS.get(tag, "#707070")

        total_dur = sum(s.get("duration_min", 0) for s in group)
        has_commit = any(s.get("has_commits") for s in group)

        status = best.get("status", "in_progress")
        follow_up = best.get("follow_up", "")
        status_badge = _status_badge(status)

        # source tag (CC/Codex)
        sources: set[str] = {s["source"] for s in group if s.get("source")}
        src_html = ""
        for src in sorted(sources):
            src_color = SOURCE_COLORS.get(src, "#888")
            src_html += f'<span class="src-tag" style="color:{src_color}">[{src}]</span> '

        meta_parts = []
        if total_dur:
            meta_parts.append(f"{total_dur}m")
        if len(group) > 1:
            meta_parts.append(f"{len(group)}세션")
        if has_commit:
            meta_parts.append("커밋")
        meta_str = (
            f' <span class="work-meta">({", ".join(meta_parts)})</span>'
            if meta_parts else ""
        )

        follow_html = f' <span class="follow-up">→ {_esc(follow_up)}</span>' if follow_up else ""

        items.append(
            f'<div class="work-item">'
            f'{status_badge}'
            f'{src_html}'
            f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span> '
            f'<span class="work-summary">{summary}{meta_str}{follow_html}</span>'
            f'</div>'
        )
    return "".join(items)


_RE_TAGS = re.compile(r"^(\[(?:CC|Codex)\])\s*(\[[^\]]+\])\s*")

SOURCE_COLORS = {"CC": "#4A90D9", "Codex": "#E07B5A"}


def _render_summary_item(text: str) -> str:
    """Parse [CC] [태그] prefix into colored tags, render the rest as text."""
    m = _RE_TAGS.match(text)
    if m:
        source = m.group(1)[1:-1]  # "CC" or "Codex"
        tag = m.group(2)[1:-1]     # e.g. "코딩"
        rest = text[m.end():]
        src_color = SOURCE_COLORS.get(source, "#888")
        tag_color = TAG_COLORS.get(tag, "#707070")
        return (
            f'<div class="repo-summary-item">'
            f'<span class="src-tag" style="color:{src_color}">[{source}]</span> '
            f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span> '
            f'{_esc(rest)}'
            f'</div>'
        )
    return f'<div class="repo-summary-item">{_esc(text)}</div>'


def _match_repo_summary(repo: str, summaries: dict[str, str | list[str]]) -> str | list[str] | None:
    """repo 이름으로 summaries dict에서 매칭.

    정확한 매칭 우선, 이후 하이픈 구분 단어 기준으로 한쪽이 다른 쪽의 접두사/접미사인 경우만 허용.
    """
    if repo in summaries:
        return summaries[repo]
    repo_parts = set(repo.split("-"))
    for key, val in summaries.items():
        key_parts = set(key.split("-"))
        # 짧은 쪽의 모든 단어가 긴 쪽에 포함되면 매칭
        shorter, longer = (key_parts, repo_parts) if len(key_parts) <= len(repo_parts) else (repo_parts, key_parts)
        if len(shorter) >= 2 and shorter <= longer:
            return val
    return None


def validate_report(html: str, data: dict) -> list[dict]:
    """Gate C: HTML 리포트 프리뷰 검증. 이슈 목록 반환."""
    import re as _re
    issues = []
    date_str = data.get("date", "")

    # 1. 세션 수에 eval 포함
    m = _re.search(r'stat-val">(\d+)</div><div class="stat-lbl">세션', html)
    real_count = len([s for s in data.get("sessions", []) if s.get("tag") != "eval"])
    if m and int(m.group(1)) != real_count:
        issues.append({"type": "eval-leak", "detail": f"stats sessions {m.group(1)} != real {real_count}"})

    # 2. tag pill에 eval 표시
    if _re.search(r'tag-pill[^>]*>eval', html):
        issues.append({"type": "eval-leak", "detail": "eval tag in tag pills"})

    # 3. 토큰 수에 eval 포함
    eval_tokens = sum(s.get("token_total", 0) for s in data.get("sessions", []) if s.get("tag") == "eval")
    if eval_tokens > 0:
        m = _re.search(r'stat-val">([\d.]+)M</div><div class="stat-lbl">토큰', html)
        if m:
            total_tokens = sum(s.get("token_total", 0) for s in data.get("sessions", []))
            real_tokens = total_tokens - eval_tokens
            displayed = float(m.group(1)) * 1_000_000
            if abs(displayed - real_tokens) > real_tokens * 0.1:
                issues.append({"type": "eval-leak", "detail": f"tokens include eval: displayed={m.group(1)}M"})

    # 4. 레포명 unknown
    for m in _re.finditer(r'class="repo-name">([^<]+)<', html):
        name = m.group(1).strip()
        if name in ("unknown", "", "None"):
            issues.append({"type": "repo-null", "detail": f"repo name: '{name}'"})

    # 5. 건강 데이터: eval 시간대 겹침 (주 기준)
    try:
        _mcp = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
        sys.path.insert(0, str(_mcp))
        from db import get_conn as _get_conn
        conn = _get_conn()
        eval_exists = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE date = ? AND repo = '-claude'",
            (date_str,)
        ).fetchone()[0]
        if eval_exists:
            for table in ["health_exercises", "health_symptoms", "health_meals"]:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE date = ?", (date_str,)
                ).fetchone()[0]
                if count:
                    issues.append({"type": "fake-health", "detail": f"{table}: {count} records on eval day"})
        conn.close()
    except Exception:
        pass

    # 6. 가짜 키워드 (보조)
    for kw in ["테스트용", "스크립트 검증", "알수없는음식"]:
        if kw in html:
            issues.append({"type": "fake-health", "detail": f"keyword '{kw}'"})

    # 7. 제안 태스크 중복
    task_texts = _re.findall(r'work-summary[^>]*>([^<]{5,})', html)
    from collections import Counter
    prefix_counter = Counter(" ".join(t.split()[:3]) for t in task_texts if len(t.split()) >= 3)
    for prefix, cnt in prefix_counter.items():
        if cnt >= 3:
            issues.append({"type": "task-dup", "detail": f"'{prefix}' x{cnt}"})

    # 8. 타임라인에 eval 잔존
    if _re.search(r'data-tag="eval"', html) or _re.search(r'"-claude"', html):
        issues.append({"type": "eval-leak", "detail": "eval in timeline data"})

    # 9. 빈 섹션 (CSS 정의가 아닌 실제 사용 체크)
    body_html = html.split('</style>')[-1] if '</style>' in html else html
    if 'coaching-placeholder' in body_html or 'coaching-empty' in body_html:
        issues.append({"type": "empty-section", "detail": "coaching section empty"})

    # 10. 1-2분 단순 명령 독립 항목 (B-2 실패 감지)
    trivial_patterns = [r'/exit[^a-z]', r'/clear[^a-z]', r'/login[^a-z]', r'/reload']
    for pat in trivial_patterns:
        matches = _re.findall(pat, html)
        if len(matches) > 1:
            issues.append({"type": "trivial-topic", "detail": f"'{pat}' appears {len(matches)}x"})

    return issues


def _build_repos_detail(data: dict, repo_summaries: dict[str, str | list[str]] | None = None) -> str:
    """레포별 작업. topics 있으면 토픽 기준, 없으면 세션 원문."""
    sessions = data.get("sessions", [])
    topics = data.get("topics", [])
    if not sessions and not topics:
        return ""

    # 토픽이 있는 레포 + 토픽 없는 세션 모두 표시
    topic_repos = group_topics_by_repo(topics) if topics else {}
    # 토픽이 커버하는 session_id 집합
    topic_session_ids = {t.get("session_id") for t in topics} if topics else set()
    # 토픽이 없는 세션만 필터
    untopiced_sessions = [s for s in sessions if s.get("session_id") not in topic_session_ids]

    rows = []

    # 1) 토픽 기준 레포 표시
    for r, ts in sorted(topic_repos.items()):
        inner_html = _build_topic_items(ts)
        rows.append(
            f'<div class="repo-group">'
            f'<div class="repo-name">{_esc(r)}</div>'
            f'{inner_html}'
            f'</div>'
        )

    # 2) 토픽 없는 세션 — 기존 방식으로 표시
    if untopiced_sessions:
        for repo, total_dur, total_tok, branch_groups in group_sessions_by_repo_branch(untopiced_sessions, short_repo=True):
            if repo in topic_repos:
                continue  # 이미 토픽으로 표시된 레포는 skip
            sess_count = sum(len(bs) for bs in branch_groups.values())
            h, m = divmod(total_dur, 60)
            dur_str = f"{h}h {m}m" if h else f"{m}m"
            meta = f'{sess_count}세션 · {dur_str}'
            if total_tok > 0:
                meta += f' · {_fmt_tokens(total_tok)} tokens'
            summary = _match_repo_summary(repo, repo_summaries) if repo_summaries else None
            if summary is not None:
                if isinstance(summary, list):
                    items = "".join(_render_summary_item(s) for s in summary)
                    inner_html = f'<div class="repo-summary-list">{items}</div>'
                else:
                    inner_html = f'<div class="repo-summary">{_esc(summary)}</div>'
            elif has_meaningful_branches(branch_groups):
                inner_html = ""
                for branch, bsess in branch_groups.items():
                    if branch:
                        inner_html += (
                            f'<div class="branch-group">'
                            f'<div class="branch-name">{_esc(branch)}</div>'
                            f'{_build_work_items(bsess)}'
                            f'</div>'
                        )
                    else:
                        inner_html += _build_work_items(bsess)
            else:
                all_sess = [s for bs in branch_groups.values() for s in bs]
                inner_html = _build_work_items(all_sess)
            rows.append(
                f'<div class="repo-group">'
                f'<div class="repo-name">{_esc(repo)} <span class="repo-meta">{meta}</span></div>'
                f'{inner_html}'
                f'</div>'
            )

    if not rows:
        return ""

    legend = (
        '<div class="status-legend">'
        '<span style="color:#7ABD7E">✓</span> 완료 '
        '<span style="color:#888">◦</span> 진행중 '
        '<span style="color:#E07B5A">✕</span> 블로커 '
        '<span style="color:#F0C040">→</span> 후속필요'
        '</div>'
    )
    return f'<div class="section"><h3>레포별 작업</h3>{legend}{"".join(rows)}</div>'



def _build_followup_section(data: dict) -> str:
    """미해소 항목 — 진행중/후속작업/긴급 분류."""
    topics = data.get("topics", [])
    topic_followups = [t for t in topics if t.get("follow_up")]
    chain_followups = data.get("open_followups", [])
    pending_tasks = data.get("pending_tasks", [])

    if not topic_followups and not chain_followups and not pending_tasks:
        return ""

    def _render_topic_item(t):
        repo = _esc((t.get("repo") or "?").split("/")[-1])
        tag = t.get("tag") or "기타"
        tag_color = TAG_COLORS.get(tag, "#707070")
        follow = _esc(t.get("follow_up", ""))
        return (
            f'<div class="work-item">'
            f'<span class="sess-tag" style="color:{tag_color}">[{tag}]</span> '
            f'<span class="work-summary">{repo}: {follow}</span>'
            f'</div>'
        )

    # 분류: in_progress → 내일 이어할 작업, completed+follow_up → 후속 작업
    continuing = [t for t in topic_followups if t.get("status") == "in_progress"]
    action_needed = [t for t in topic_followups if t.get("status") != "in_progress"]

    sections = []

    if continuing:
        items = "".join(_render_topic_item(t) for t in continuing)
        sections.append(f'<div class="followup-group"><div class="followup-label">◦ 진행중 ({len(continuing)}건) — 내일 이어서</div>{items}</div>')

    if action_needed:
        items = "".join(_render_topic_item(t) for t in action_needed)
        sections.append(f'<div class="followup-group"><div class="followup-label">→ 후속 작업 ({len(action_needed)}건)</div>{items}</div>')

    if chain_followups:
        items = ""
        for f in chain_followups:
            desc = _esc(f.get("description", ""))
            days = f.get("days_open", 0)
            repo = _esc(f.get("origin_repo") or "?")
            items += f'<div class="work-item"><span class="work-summary">[{days}일] {repo} — {desc}</span></div>'
        sections.append(f'<div class="followup-group"><div class="followup-label">🔗 미해소 체인 ({len(chain_followups)}건)</div>{items}</div>')

    if pending_tasks:
        items = ""
        for t in pending_tasks:
            desc = _esc(t.get("description", ""))
            items += f'<div class="work-item"><span class="work-summary">{desc}</span></div>'
        sections.append(f'<div class="followup-group"><div class="followup-label">📋 제안 태스크 ({len(pending_tasks)}건)</div>{items}</div>')

    total = len(topic_followups) + len(chain_followups) + len(pending_tasks)
    return (
        f'<div class="section"><h3>미해소 항목 ({total}건)</h3>'
        f'{"".join(sections)}</div>'
    )


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
.work-item{display:flex;gap:6px;font-size:12px;padding:3px 0;color:#B0B0B0;line-height:1.5}
.work-summary{flex:1}
.status-badge{font-weight:700;font-size:13px;flex-shrink:0}
.status-legend{font-size:11px;color:#888;margin-bottom:8px;display:flex;gap:12px}
.follow-up{color:#F0C040;font-size:11px;font-style:italic}
.followup-group{margin-bottom:10px}
.followup-label{font-size:12px;font-weight:600;color:#AAA;margin-bottom:4px}
.work-meta{font-size:10px;color:var(--mu);font-weight:400}
.src-tag{flex-shrink:0;font-weight:600;font-size:10px;opacity:0.8}
.sess-tag{flex-shrink:0;font-weight:600;font-size:11px}
.branch-group{margin:6px 0 8px 12px;padding-left:10px;border-left:2px solid #444}
.repo-summary{font-size:12px;color:#C0C0C0;line-height:1.6;padding:2px 0}
.repo-summary-list{padding:2px 0}
.repo-summary-item{font-size:12px;color:#C0C0C0;line-height:1.6;padding:2px 0 2px 14px;position:relative}
.repo-summary-item::before{content:"•";position:absolute;left:0;color:var(--mu)}
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
.coaching-table{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}
.coaching-table th{text-align:left;padding:6px 10px;border-bottom:2px solid #444;color:#CCC;font-weight:600}
.coaching-table td{padding:5px 10px;border-bottom:1px solid #333;color:#B0B0B0}
.coaching-table tr:hover td{background:#2A2A2E}
.coaching pre{background:#1a1a1a;padding:10px;border-radius:6px;font-size:12px;overflow-x:auto;color:#C0C0C0;margin:8px 0}
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


def _build_week_trend_chart(data: dict) -> str:
    """최근 7일+당일의 활동시간·토큰 사용량 바 차트 (인라인 SVG)."""
    date_str = data.get("date", "")
    if not date_str:
        return ""

    # DB에서 최근 8일 sessions 직접 조회 (daily_stats는 부정확할 수 있음)
    try:
        _mcp = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
        import sys as _sys
        _sys.path.insert(0, str(_mcp))
        from db import get_conn
        conn = get_conn()
        end_dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=7)
        session_rows = conn.execute("""
            SELECT date, start_at, end_at, duration_min, token_total
            FROM sessions WHERE date >= ? AND date <= ?
            ORDER BY date, start_at
        """, (start_dt.strftime("%Y-%m-%d"), date_str)).fetchall()
        conn.close()
    except Exception:
        return ""

    # 날짜별 interval merge로 활동시간 계산
    days_data: dict[str, dict] = {}
    for i in range(8):
        d = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        days_data[d] = {"intervals": [], "sum_dur": 0, "tokens": 0, "sessions": 0}
    for r in session_rows:
        d = r["date"]
        if d not in days_data:
            continue
        days_data[d]["sessions"] += 1
        days_data[d]["sum_dur"] += r["duration_min"] or 0
        days_data[d]["tokens"] += r["token_total"] or 0
        s = r["start_at"] or ""
        e = r["end_at"] or s
        if len(s) >= 16 and len(e) >= 16:
            days_data[d]["intervals"].append((s, e))
    # interval merge → min(sum_dur, wall) per day
    for d, dd in days_data.items():
        intervals = dd["intervals"]
        if not intervals:
            dd["hours"] = 0.0
            continue
        parsed = []
        for s, e in intervals:
            try:
                st = int(s[11:13]) * 60 + int(s[14:16])
                et = int(e[11:13]) * 60 + int(e[14:16])
                if et > st:
                    parsed.append((st, et))
            except (ValueError, IndexError):
                pass
        if not parsed:
            dd["hours"] = round(dd["sum_dur"] / 60, 1)
            continue
        parsed.sort()
        merged = [parsed[0]]
        for s, e in parsed[1:]:
            if s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        wall_min = sum(e - s for s, e in merged)
        dd["hours"] = round(min(dd["sum_dur"], wall_min) / 60, 1)

    # 오늘은 topics 기반 활동시간으로 덮어쓰기 (더 정확)
    today_hours = _calc_actual_work_hours(data.get("topics", []), data.get("sessions", []))
    if date_str in days_data:
        days_data[date_str]["hours"] = today_hours
        days_data[date_str]["tokens"] = data.get("token_total", 0)
        days_data[date_str]["sessions"] = data.get("session_count", 0)

    dates = sorted(days_data.keys())
    if not dates:
        return ""

    # SVG 차트 생성
    W, H = 700, 180
    pad_l, pad_r, pad_b = 40, 20, 36
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_b - 10
    bar_w = chart_w / len(dates)
    max_hours = max((days_data[d]["hours"] for d in dates), default=1) or 1
    max_tokens = max((days_data[d]["tokens"] for d in dates), default=1) or 1

    bars_svg = ""
    labels_svg = ""
    for i, d in enumerate(dates):
        dd = days_data[d]
        x = pad_l + i * bar_w
        cx = x + bar_w / 2

        # 활동시간 바 (초록)
        h_pct = dd["hours"] / max_hours
        bh = h_pct * (chart_h * 0.85)
        by = 10 + chart_h - bh
        is_today = d == date_str
        fill = "#7ABD7E" if not is_today else "#5AE05A"
        opacity = "1" if is_today else "0.7"
        bars_svg += f'<rect x="{cx - bar_w*0.18}" y="{by}" width="{bar_w*0.36}" height="{bh}" rx="3" fill="{fill}" opacity="{opacity}"/>'

        # 토큰 라인 포인트 (파랑)
        t_pct = dd["tokens"] / max_tokens
        ty = 10 + chart_h - t_pct * (chart_h * 0.85)
        if i > 0:
            prev_d = dates[i - 1]
            prev_pct = days_data[prev_d]["tokens"] / max_tokens
            prev_ty = 10 + chart_h - prev_pct * (chart_h * 0.85)
            prev_cx = pad_l + (i - 1) * bar_w + bar_w / 2
            bars_svg += f'<line x1="{prev_cx}" y1="{prev_ty}" x2="{cx}" y2="{ty}" stroke="#4A90D9" stroke-width="1.5" opacity="0.6"/>'
        bars_svg += f'<circle cx="{cx}" cy="{ty}" r="3" fill="#4A90D9" opacity="0.8"/>'

        # 활동시간 값 (바 위)
        if dd["hours"] > 0:
            bars_svg += f'<text x="{cx}" y="{by - 4}" text-anchor="middle" font-size="9" fill="#AAA">{dd["hours"]}h</text>'

        # 날짜 + 요일 라벨
        d_dt = datetime.strptime(d, "%Y-%m-%d")
        weekday_short = ["월", "화", "수", "목", "금", "토", "일"][d_dt.weekday()]
        short_date = f"{d[8:10]}({weekday_short})"
        weight = "700" if is_today else "400"
        color = "#E0E0E0" if is_today else "#666"
        labels_svg += f'<text x="{cx}" y="{H - 12}" text-anchor="middle" font-size="10" fill="{color}" font-weight="{weight}">{short_date}</text>'

    # 범례
    legend = (
        f'<rect x="{pad_l}" y="{H - 6}" width="8" height="8" rx="2" fill="#7ABD7E" opacity="0.7"/>'
        f'<text x="{pad_l + 12}" y="{H}" font-size="9" fill="#888">활동시간</text>'
        f'<line x1="{pad_l + 70}" y1="{H - 2}" x2="{pad_l + 86}" y2="{H - 2}" stroke="#4A90D9" stroke-width="1.5" opacity="0.6"/>'
        f'<circle cx="{pad_l + 78}" cy="{H - 2}" r="2.5" fill="#4A90D9"/>'
        f'<text x="{pad_l + 90}" y="{H}" font-size="9" fill="#888">토큰</text>'
    )

    # 토큰 총량 (오른쪽 범례)
    today_tok = days_data.get(date_str, {}).get("tokens", 0)
    tok_str = _fmt_tokens(today_tok) if today_tok else "0"
    tok_legend = f'<text x="{W - pad_r}" y="{H}" text-anchor="end" font-size="9" fill="#4A90D9">오늘 {tok_str} tokens</text>'

    svg = (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="font-family:-apple-system,\'Apple SD Gothic Neo\',sans-serif">'
        f'{bars_svg}{labels_svg}{legend}{tok_legend}'
        f'</svg>'
    )

    return f'<div class="section"><h3>최근 8일 트렌드</h3>{svg}</div>'


def build_daily_report(data: dict, coaching_md: str | None = None,
                       repo_summaries: dict[str, str | list[str]] | None = None) -> str:
    # repo_summaries는 deprecated — DB summary를 직접 사용.
    # 하위 호환을 위해 파라미터는 유지하되 무시.
    if not data.get("has_data"):
        return _build_empty_page(data.get("date", ""))

    # eval 세션/토픽 제외 + 집계 값 재계산
    _fs = [s for s in data.get("sessions", []) if s.get("tag") != "eval"]
    _ft = [t for t in data.get("topics", []) if t.get("tag") != "eval"]
    _tag_bd = {}
    for _t in _ft:
        _k = _t.get("tag", "기타")
        _tag_bd[_k] = _tag_bd.get(_k, 0) + 1
    _repo_bd = {}
    for _s in _fs:
        _r = _s.get("repo", "unknown")
        _repo_bd[_r] = _repo_bd.get(_r, 0) + 1
    data = {**data,
            "sessions": _fs, "topics": _ft,
            "session_count": len(_fs),
            "token_total": sum(s.get("token_total", 0) for s in _fs),
            "tag_breakdown": _tag_bd, "repos": _repo_bd}

    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAY[dt.weekday()]
    title = f"{dt.month}/{dt.day}({weekday}) 데일리 리포트"

    # Timeline section
    _, days = build(data, weekly=False)
    timeline = timeline_section_html(days, f"{dt.month}/{dt.day}({weekday}) 타임라인")

    sections = [
        _build_week_trend_chart(data),
        _build_stats_card(data),
        _build_tag_breakdown(data),
        _build_nudges(data),
        timeline,
        _build_repos_detail(data),  # DB summary 직접 사용
        _build_followup_section(data),
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
<div class="subtitle">{data.get('session_count', 0)}세션 · {_calc_actual_work_hours(data.get('topics', []), data.get('sessions', []))}h 활동 · {_fmt_tokens(data.get('token_total', 0))} tokens</div>
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
    parser.add_argument("--repo-summaries", help="LLM repo summaries JSON file")
    parser.add_argument("--output", help="Output HTML path (default: date-based)")
    parser.add_argument("--validate", action="store_true", help="Gate C: validate report before saving")
    args = parser.parse_args()

    raw = json.load(open(args.input) if args.input else sys.stdin)

    coaching_md = None
    if args.coaching:
        coaching_md = Path(args.coaching).read_text(encoding="utf-8")

    repo_summaries = None
    if args.repo_summaries:
        repo_summaries = json.load(open(args.repo_summaries))

    # validate gate — 토픽 누락 시 경고
    date_str = raw.get("date", "unknown")
    try:
        import subprocess as _sp
        # shared/life-coach → repo root → cc/work-digest
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        validate_script = repo_root / "cc" / "work-digest" / "scripts" / "validate_topics.py"
        if validate_script.exists():
            vr = _sp.run([sys.executable, str(validate_script), "--fix", "--date", date_str],
                         capture_output=True, text=True, timeout=30)
            if vr.returncode != 0:
                print(f"[daily_report] ⚠ validate_topics warning:\n{vr.stdout.strip()}", file=sys.stderr)
    except Exception as e:
        print(f"[daily_report] validate skipped: {e}", file=sys.stderr)

    html = build_daily_report(raw, coaching_md, repo_summaries=repo_summaries)

    if args.validate:
        vi = validate_report(html, raw)
        if vi:
            # trivial-topic은 경고만 (Gate B-2 영역)
            warn_types = {"trivial-topic"}
            errors = [i for i in vi if i["type"] not in warn_types]
            warns = [i for i in vi if i["type"] in warn_types]
            if warns:
                print(f"[daily_report] ⚡ Gate C warnings: {len(warns)}", file=sys.stderr)
                for w in warns:
                    print(f"  ⚠ [{w['type']}] {w['detail']}", file=sys.stderr)
            if errors:
                print(f"[daily_report] ✗ Gate C: {len(errors)} blocking issues", file=sys.stderr)
                for iss in errors:
                    print(f"  ✗ [{iss['type']}] {iss['detail']}", file=sys.stderr)
                log_path = Path(__file__).resolve().parent.parent / "references" / "gate-c-issues.json"
                existing = json.loads(log_path.read_text()) if log_path.exists() else []
                for iss in vi:
                    existing.append({"date": date_str, **iss, "auto_fixed": False})
                log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
                print("[daily_report] Gate C failed. Fix issues and retry.", file=sys.stderr)
                sys.exit(1)

    output_path = args.output or f"/tmp/daily_report_{date_str}.html"
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"[daily_report] saved: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
