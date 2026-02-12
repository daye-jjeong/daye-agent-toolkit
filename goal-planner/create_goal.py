#!/usr/bin/env python3
"""
Goal Planner — 월간/주간/일간 목표 YAML 자동 생성

Usage:
    python3 create_goal.py monthly [--dry-run]
    python3 create_goal.py weekly  [--dry-run] [--date 2026-02-10]
    python3 create_goal.py daily   [--dry-run] [--date 2026-02-10] [--energy high|medium|low]
    python3 create_goal.py retro   --type daily|weekly|monthly
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Error: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
CLAWD_ROOT = Path.home() / "clawd"
PROJECTS_ROOT = CLAWD_ROOT / "memory" / "projects"
GOALS_ROOT = CLAWD_ROOT / "memory" / "goals"
FETCH_SCHEDULE = CLAWD_ROOT / "skills" / "schedule-advisor" / "scripts" / "fetch_schedule.py"

TELEGRAM_GROUP = "-1003242721592"
TELEGRAM_THREAD = "167"

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

# 기본 시간 블록 템플릿 (에너지별)
TIME_BLOCKS_HIGH = [
    ("09:00-10:00", "아침 루틴 + 체크인", "personal"),
    ("10:00-12:00", "딥워크 (핵심 업무)", "work"),
    ("13:00-15:00", "딥워크 (핵심 업무 2)", "work"),
    ("15:00-16:30", "미팅/협업", "work"),
    ("16:30-17:30", "가벼운 작업/정리", "work"),
    ("19:00-20:00", "운동/PT", "personal"),
]

TIME_BLOCKS_MEDIUM = [
    ("09:00-10:00", "아침 루틴 + 체크인", "personal"),
    ("10:00-11:30", "집중 작업", "work"),
    ("11:30-12:00", "가벼운 작업", "work"),
    ("13:00-14:30", "집중 작업", "work"),
    ("14:30-15:30", "미팅/협업", "work"),
    ("15:30-16:30", "가벼운 작업/정리", "work"),
    ("19:00-20:00", "운동/PT", "personal"),
]

TIME_BLOCKS_LOW = [
    ("09:30-10:00", "아침 루틴 (천천히)", "personal"),
    ("10:00-11:00", "가벼운 작업", "work"),
    ("11:00-11:30", "휴식", "personal"),
    ("11:30-12:30", "집중 작업 (짧게)", "work"),
    ("13:30-14:30", "가벼운 작업", "work"),
    ("14:30-15:00", "휴식/산책", "personal"),
    ("15:00-16:00", "집중 작업 (짧게)", "work"),
    ("19:00-19:30", "가벼운 운동", "personal"),
]


# ──────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────
def load_yaml(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: YAML parse error {path}: {e}", file=sys.stderr)
        return None


def save_yaml(path: Path, data: Dict, dry_run: bool = False) -> bool:
    """YAML 저장. dry_run이면 stdout 출력만."""
    content = yaml.dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    if dry_run:
        print(f"\n{'='*50}")
        print(f"📄 {path.name} (dry-run)")
        print(f"{'='*50}")
        print(content)
        return True
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 저장됨: {path}")
        return True
    except Exception as e:
        print(f"❌ 저장 실패: {e}", file=sys.stderr)
        return False


def calc_kr_percent(kr: Any) -> Optional[int]:
    """KR 진행률 계산."""
    if isinstance(kr, str):
        return None
    if not isinstance(kr, dict):
        return None
    current = str(kr.get("current", "")).strip()
    target = str(kr.get("target", "")).strip()
    if not current or current == "0":
        return 0
    if current in ("완료", "done", "Done"):
        return 100
    if current in ("진행중", "진행 중", "in_progress"):
        return 50
    t_nums = re.findall(r"[\d.]+", target)
    c_nums = re.findall(r"[\d.]+", current)
    if t_nums and c_nums:
        try:
            t, c = float(t_nums[0]), float(c_nums[0])
            if t > 0:
                return min(100, round(c / t * 100))
        except (ValueError, IndexError):
            return 0
    return 0


def get_week_string(dt: datetime) -> str:
    """ISO 주차 문자열 (YYYY-Www)."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def get_week_period(dt: datetime) -> str:
    """주의 시작~끝 날짜 문자열."""
    iso = dt.isocalendar()
    # ISO 주의 월요일
    monday = datetime.strptime(f"{iso[0]}-W{iso[1]:02d}-1", "%G-W%V-%u")
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')}"


def fetch_calendar_events(date_str: str = "today") -> List[Dict]:
    """fetch_schedule.py로 캘린더 이벤트 조회."""
    if not FETCH_SCHEDULE.exists():
        print("⚠️ fetch_schedule.py 없음, 캘린더 건너뜀", file=sys.stderr)
        return []
    try:
        result = subprocess.run(
            ["python3", str(FETCH_SCHEDULE), "--time-filter", date_str, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("events", [])
    except Exception as e:
        print(f"⚠️ 캘린더 조회 실패: {e}", file=sys.stderr)
    return []


def fetch_pending_tasks() -> List[Dict]:
    """프로젝트별 대기 중 태스크 조회."""
    tasks = []
    for proj_dir in PROJECTS_ROOT.iterdir():
        if not proj_dir.is_dir() or proj_dir.name.startswith("_"):
            continue
        tasks_file = proj_dir / "tasks.yml"
        data = load_yaml(tasks_file)
        if not data:
            continue
        for task in data.get("tasks", []):
            if isinstance(task, dict) and task.get("status") in ("todo", "in_progress"):
                task["_project"] = proj_dir.name
                tasks.append(task)
    return tasks


def send_telegram(message: str) -> bool:
    """텔레그램 메시지 전송."""
    try:
        result = subprocess.run(
            [
                "clawdbot", "message", "send",
                "-t", TELEGRAM_GROUP,
                "--thread-id", TELEGRAM_THREAD,
                message,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"⚠️ 텔레그램 전송 실패: {e}", file=sys.stderr)
        return False


# ──────────────────────────────────────────────
# Monthly
# ──────────────────────────────────────────────
def draft_monthly(target_date: datetime, dry_run: bool = False) -> Dict:
    """월간 목표 템플릿 생성."""
    month_str = target_date.strftime("%Y-%m")
    file_path = GOALS_ROOT / "monthly" / f"{month_str}.yml"

    existing = load_yaml(file_path)
    if existing:
        print(f"ℹ️ 기존 월간 목표 존재: {file_path.name}")
        if not dry_run:
            print("   기존 파일을 덮어쓰지 않습니다. --dry-run으로 확인하세요.")
            return existing

    # 지난달 데이터 참조
    prev_month = target_date.replace(day=1) - timedelta(days=1)
    prev_data = load_yaml(GOALS_ROOT / "monthly" / f"{prev_month.strftime('%Y-%m')}.yml")

    # 프로젝트 목록 스캔
    projects = []
    for proj_dir in sorted(PROJECTS_ROOT.iterdir()):
        if proj_dir.is_dir() and not proj_dir.name.startswith("_"):
            projects.append(proj_dir.name)

    data = {
        "month": month_str,
        "status": "active",
        "theme": "",  # 사용자가 채울 것
        "goals": [],
        "retrospective": {
            "achievement_rate": None,
            "went_well": [],
            "to_improve": [],
            "next_month_focus": [],
        },
    }

    # 지난달 미완료 목표 이월
    if prev_data:
        for goal in prev_data.get("goals", []):
            krs = goal.get("key_results", [])
            # KR 중 미완료 항목 있으면 이월
            incomplete = []
            for kr in krs:
                pct = calc_kr_percent(kr)
                if pct is not None and pct < 100:
                    incomplete.append(kr)
            if incomplete:
                data["goals"].append({
                    "title": f"[이월] {goal.get('title', '')}",
                    "project": goal.get("project", ""),
                    "priority": goal.get("priority", "medium"),
                    "key_results": [
                        {"description": kr.get("description", str(kr)), "target": kr.get("target", ""), "current": ""}
                        for kr in incomplete
                    ],
                })

    # 빈 목표 슬롯 추가 (최소 3개)
    while len(data["goals"]) < 3:
        data["goals"].append({
            "title": "",
            "project": "",
            "priority": "medium",
            "key_results": [
                {"description": "", "target": "", "current": ""},
            ],
        })

    # 코멘트로 프로젝트 목록 안내
    print(f"\n📋 사용 가능한 프로젝트: {', '.join(projects)}")

    save_yaml(file_path, data, dry_run)
    return data


# ──────────────────────────────────────────────
# Weekly
# ──────────────────────────────────────────────
def draft_weekly(target_date: datetime, dry_run: bool = False) -> Dict:
    """주간 목표 자동 드래프트 (월간에서 파생)."""
    week_str = get_week_string(target_date)
    period_str = get_week_period(target_date)
    file_path = GOALS_ROOT / "weekly" / f"{week_str}.yml"

    existing = load_yaml(file_path)
    if existing and not dry_run:
        print(f"ℹ️ 기존 주간 목표 존재: {file_path.name}")
        print("   기존 파일을 덮어쓰지 않습니다.")
        return existing

    # 월간 목표 로드
    month_str = target_date.strftime("%Y-%m")
    monthly = load_yaml(GOALS_ROOT / "monthly" / f"{month_str}.yml")

    # 캘린더 이벤트 (이번주)
    events = fetch_calendar_events("week")

    data = {
        "week": week_str,
        "period": period_str,
        "status": "active",
        "goals": [],
        "retrospective": {
            "went_well": [],
            "to_improve": [],
            "lessons": [],
        },
    }

    if monthly:
        goals = monthly.get("goals", [])
        # priority: high 우선, 그 다음 진행률 낮은 순
        scored = []
        for g in goals:
            priority_score = {"high": 3, "medium": 2, "low": 1}.get(
                g.get("priority", "medium"), 2
            )
            # 평균 진행률 계산 (낮을수록 우선)
            krs = g.get("key_results", [])
            percents = [calc_kr_percent(kr) for kr in krs]
            valid = [p for p in percents if p is not None]
            avg_pct = sum(valid) / len(valid) if valid else 0
            # 완료된 건 제외
            if avg_pct >= 100:
                continue
            score = priority_score * 100 - avg_pct  # 높은 priority, 낮은 진행률 = 높은 점수
            scored.append((score, g))

        scored.sort(key=lambda x: -x[0])

        for _, g in scored[:5]:  # 최대 5개
            krs = g.get("key_results", [])
            # 미완료 KR만 추출
            weekly_krs = []
            for kr in krs:
                if isinstance(kr, str):
                    weekly_krs.append(kr)
                elif isinstance(kr, dict):
                    pct = calc_kr_percent(kr)
                    if pct is None or pct < 100:
                        weekly_krs.append(kr.get("description", str(kr)))

            if weekly_krs:
                data["goals"].append({
                    "title": g.get("title", "").replace("[이월] ", ""),
                    "project": g.get("project", ""),
                    "priority": g.get("priority", "medium"),
                    "status": "todo",
                    "key_results": weekly_krs,
                })
    else:
        print("⚠️ 월간 목표 없음 — 빈 템플릿 생성")
        for _ in range(3):
            data["goals"].append({
                "title": "",
                "project": "",
                "priority": "medium",
                "status": "todo",
                "key_results": [],
            })

    # 캘린더 기반 힌트
    if events:
        event_summary = [e.get("summary", "?") for e in events[:10]]
        print(f"\n📅 이번주 주요 일정: {', '.join(event_summary)}")

    save_yaml(file_path, data, dry_run)
    return data


# ──────────────────────────────────────────────
# Daily
# ──────────────────────────────────────────────
def draft_daily(
    target_date: datetime, energy: str = "medium", dry_run: bool = False
) -> Dict:
    """일간 목표 자동 드래프트 (주간 + 캘린더 기반)."""
    date_str = target_date.strftime("%Y-%m-%d")
    dow = WEEKDAY_KO[target_date.weekday()]
    file_path = GOALS_ROOT / "daily" / f"{date_str}.yml"

    existing = load_yaml(file_path)
    if existing and not dry_run:
        print(f"ℹ️ 기존 일간 목표 존재: {file_path.name}")
        return existing

    # 주간/월간 목표 로드
    week_str = get_week_string(target_date)
    weekly = load_yaml(GOALS_ROOT / "weekly" / f"{week_str}.yml")
    month_str = target_date.strftime("%Y-%m")
    monthly = load_yaml(GOALS_ROOT / "monthly" / f"{month_str}.yml")

    # 오늘 캘린더
    events = fetch_calendar_events("today")

    # 대기 중 태스크
    pending = fetch_pending_tasks()

    data = {
        "date": date_str,
        "day_of_week": dow,
        "energy_level": energy,
        "status": "active",
        "top3": [],
        "time_blocks": [],
        "checklist": [],
        "retrospective": {
            "completed_ratio": None,
            "mood": None,
            "notes": "",
        },
    }

    # ── top3 선정 ──
    candidates = []

    # 주간 목표에서 추출
    if weekly:
        for g in weekly.get("goals", []):
            if g.get("status") in ("todo", "in_progress"):
                candidates.append({
                    "title": g.get("title", ""),
                    "project": g.get("project", ""),
                    "source": "weekly",
                    "priority": g.get("priority", "medium"),
                })

    # 대기 태스크에서 추출 (마감일 기준)
    for task in pending:
        deadline = str(task.get("deadline", "")).strip()
        if deadline and deadline <= date_str:
            candidates.append({
                "title": task.get("title", ""),
                "project": task.get("_project", ""),
                "source": "task",
                "priority": task.get("priority", "medium"),
            })

    # priority 정렬 후 top3 선정
    priority_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1))

    seen_titles = set()
    for c in candidates:
        if c["title"] and c["title"] not in seen_titles:
            data["top3"].append({
                "title": c["title"],
                "project": c["project"],
                "status": "todo",
            })
            seen_titles.add(c["title"])
            if len(data["top3"]) >= 3:
                break

    # top3가 부족하면 빈 슬롯
    while len(data["top3"]) < 3:
        data["top3"].append({"title": "", "project": "", "status": "todo"})

    # ── time_blocks 생성 ──
    template = {
        "high": TIME_BLOCKS_HIGH,
        "medium": TIME_BLOCKS_MEDIUM,
        "low": TIME_BLOCKS_LOW,
    }.get(energy, TIME_BLOCKS_MEDIUM)

    # 캘린더 이벤트를 time_blocks에 먼저 삽입
    cal_blocks = []
    for ev in events:
        start = ev.get("start", {})
        start_dt = start.get("dateTime", "")
        if not start_dt:
            continue  # 종일 이벤트 건너뜀
        try:
            s_hour = int(start_dt[11:13])
            s_min = int(start_dt[14:16])
            end = ev.get("end", {})
            end_dt = end.get("dateTime", "")
            if end_dt:
                e_hour = int(end_dt[11:13])
                e_min = int(end_dt[14:16])
            else:
                e_hour, e_min = s_hour + 1, s_min
            cal_blocks.append({
                "time": f"{s_hour:02d}:{s_min:02d}-{e_hour:02d}:{e_min:02d}",
                "task": f"📅 {ev.get('summary', '일정')}",
                "category": "calendar",
            })
        except (ValueError, IndexError):
            continue

    # 템플릿 블록 중 캘린더와 겹치지 않는 것만 추가
    for time_range, task, category in template:
        t_start = int(time_range.split("-")[0].replace(":", ""))
        # 캘린더 이벤트와 시간 겹침 체크
        overlap = False
        for cb in cal_blocks:
            cb_start = int(cb["time"].split("-")[0].replace(":", ""))
            cb_end = int(cb["time"].split("-")[1].replace(":", ""))
            if cb_start <= t_start < cb_end:
                overlap = True
                break
        if not overlap:
            cal_blocks.append({
                "time": time_range,
                "task": task,
                "category": category,
            })

    # 시간순 정렬
    cal_blocks.sort(key=lambda x: x["time"])
    data["time_blocks"] = cal_blocks

    # ── checklist 생성 ──
    for t in data["top3"]:
        if t["title"]:
            data["checklist"].append({"task": t["title"], "done": False})

    # 주간 KR에서 오늘 할 수 있는 것 추가
    if weekly:
        for g in weekly.get("goals", []):
            if g.get("status") == "done":
                continue
            for kr in g.get("key_results", []):
                kr_text = kr if isinstance(kr, str) else kr.get("description", "")
                if kr_text and kr_text not in seen_titles:
                    data["checklist"].append({"task": kr_text, "done": False})
                    seen_titles.add(kr_text)

    save_yaml(file_path, data, dry_run)
    return data


# ──────────────────────────────────────────────
# Retrospective
# ──────────────────────────────────────────────
def show_retro(target_date: datetime, retro_type: str):
    """회고용 데이터 출력."""
    if retro_type == "daily":
        path = GOALS_ROOT / "daily" / f"{target_date.strftime('%Y-%m-%d')}.yml"
    elif retro_type == "weekly":
        path = GOALS_ROOT / "weekly" / f"{get_week_string(target_date)}.yml"
    elif retro_type == "monthly":
        path = GOALS_ROOT / "monthly" / f"{target_date.strftime('%Y-%m')}.yml"
    else:
        print(f"❌ 알 수 없는 타입: {retro_type}")
        return

    data = load_yaml(path)
    if not data:
        print(f"⚠️ 파일 없음: {path.name}")
        return

    print(f"\n{'='*50}")
    print(f"📝 회고: {path.name}")
    print(f"{'='*50}")

    # 목표별 상태 출력
    goals = data.get("goals", data.get("top3", []))
    for g in goals:
        if isinstance(g, str):
            print(f"  ⬜ {g}")
            continue
        title = g.get("title", "")
        status = g.get("status", "")
        icon = {"done": "✅", "in_progress": "🔄", "todo": "⬜"}.get(status, "⬜")
        print(f"  {icon} {title}")

        # KR 진행률
        for kr in g.get("key_results", []):
            if isinstance(kr, str):
                print(f"      - {kr}")
            elif isinstance(kr, dict):
                pct = calc_kr_percent(kr)
                desc = kr.get("description", "")
                pct_str = f" ({pct}%)" if pct is not None else ""
                print(f"      - {desc}{pct_str}")

    # 체크리스트 (일간)
    checklist = data.get("checklist", [])
    if checklist:
        done_count = sum(1 for c in checklist if c.get("done"))
        total = len(checklist)
        print(f"\n  체크리스트: {done_count}/{total} 완료")

    # 회고 필드
    retro = data.get("retrospective", {})
    if retro:
        print(f"\n  retrospective:")
        for k, v in retro.items():
            if v is not None and v != "" and v != []:
                print(f"    {k}: {v}")
            else:
                print(f"    {k}: (미작성)")

    print(f"\n💡 회고를 작성하려면 {path} 파일의 retrospective 필드를 편집하세요.")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Goal Planner — 목표 YAML 생성")
    parser.add_argument(
        "command",
        choices=["monthly", "weekly", "daily", "retro"],
        help="생성할 목표 단위",
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 생성 없이 출력만")
    parser.add_argument("--date", type=str, help="대상 날짜 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument(
        "--energy",
        choices=["high", "medium", "low"],
        default="medium",
        help="에너지 레벨 (daily용)",
    )
    parser.add_argument(
        "--type",
        choices=["daily", "weekly", "monthly"],
        help="회고 대상 (retro용)",
    )
    parser.add_argument("--auto", action="store_true", help="자동 모드 (생성 + 텔레그램)")

    args = parser.parse_args()

    # 날짜 파싱
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        target = datetime.now()

    print(f"🎯 Goal Planner — {args.command} ({target.strftime('%Y-%m-%d')})")

    if args.command == "monthly":
        data = draft_monthly(target, args.dry_run)
    elif args.command == "weekly":
        data = draft_weekly(target, args.dry_run)
    elif args.command == "daily":
        data = draft_daily(target, args.energy, args.dry_run)
    elif args.command == "retro":
        if not args.type:
            print("❌ --type 필수 (daily|weekly|monthly)")
            sys.exit(1)
        show_retro(target, args.type)
        return

    # --auto: 텔레그램으로 요약 전송
    if args.auto and not args.dry_run and data:
        msg = format_telegram_summary(args.command, data, target)
        if msg:
            send_telegram(msg)
            print("📨 텔레그램 전송 완료")


def format_telegram_summary(cmd: str, data: Dict, target: datetime) -> str:
    """텔레그램 요약 메시지 생성."""
    lines = []

    if cmd == "daily":
        dow = WEEKDAY_KO[target.weekday()]
        lines.append(f"📋 일간 계획 ({target.strftime('%m/%d')} {dow})")
        lines.append(f"에너지: {data.get('energy_level', '?')}")
        lines.append("")

        # top3
        lines.append("🎯 오늘의 핵심 3:")
        for i, t in enumerate(data.get("top3", []), 1):
            title = t.get("title", "(미정)")
            if title:
                lines.append(f"  {i}. {title}")

        # time_blocks 요약
        blocks = data.get("time_blocks", [])
        if blocks:
            lines.append("")
            lines.append("⏰ 시간 블록:")
            for b in blocks:
                lines.append(f"  {b['time']} {b['task']}")

    elif cmd == "weekly":
        lines.append(f"📋 주간 계획 ({data.get('week', '')})")
        lines.append(f"기간: {data.get('period', '')}")
        lines.append("")
        for g in data.get("goals", []):
            priority = g.get("priority", "")
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⬜")
            lines.append(f"{icon} {g.get('title', '')}")
            for kr in g.get("key_results", []):
                kr_text = kr if isinstance(kr, str) else kr.get("description", "")
                lines.append(f"   - {kr_text}")

    elif cmd == "monthly":
        lines.append(f"📋 월간 계획 ({data.get('month', '')})")
        theme = data.get("theme", "")
        if theme:
            lines.append(f"테마: {theme}")
        lines.append("")
        for g in data.get("goals", []):
            title = g.get("title", "")
            if title:
                lines.append(f"• {title}")

    return "\n".join(lines) if lines else ""


if __name__ == "__main__":
    main()
