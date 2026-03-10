#!/usr/bin/env python3
"""Work session timeline chart generator.

Usage:
    # 일일 차트
    python3 daily_coach.py --json | python3 timeline_chart.py
    python3 timeline_chart.py --input data.json

    # 주간 차트 (요일별)
    python3 weekly_coach.py --json | python3 timeline_chart.py --weekly
    python3 timeline_chart.py --weekly --input weekly.json

    # 저장 경로 지정
    python3 timeline_chart.py --output /tmp/my_chart.png
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import TAG_COLORS, dedup_sessions as dedup, to_h as to_hours

COLORS = ["#4A90D9", "#E07B5A", "#7ABD7E", "#9B7BC8", "#F0C040", "#5AC8D9", "#D95A90", "#D9A85A"]
BG = "#1C1C1E"
FONT = "Apple SD Gothic Neo"


def bar_color(session: dict, idx: int) -> str:
    tag = session.get("tag", "")
    return TAG_COLORS.get(tag, COLORS[idx % len(COLORS)])


def session_label(session: dict) -> str:
    repo = (session.get("repo") or "?").split("/")[-1][:18]
    tag = session.get("tag", "")
    return f"{repo} [{tag}]" if tag else repo




def daily_chart(data: dict, output_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = FONT

    sessions = dedup(data.get("sessions", []))
    date_str = data.get("date", "")

    if not sessions:
        print("[timeline_chart] no sessions to chart", file=sys.stderr)
        return

    fig, ax = plt.subplots(figsize=(14, max(3, len(sessions) * 0.75)))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    for i, s in enumerate(sessions):
        start = to_hours(s["start_at"])
        dur = s.get("duration_min") or 30
        end = start + dur / 60
        color = bar_color(s, i)
        ax.barh(i, end - start, left=start, height=0.55, color=color, alpha=0.88, edgecolor="none")
        if dur >= 20:
            time_str = f'{s["start_at"][11:16]}–{int(dur // 60):02d}:{int(dur % 60):02d}'
            ax.text(start + (end - start) / 2, i, time_str,
                    va="center", ha="center", fontsize=8, color="white", fontweight="bold")

    import matplotlib.patches as mpatches
    ax.set_yticks(range(len(sessions)))
    ax.set_yticklabels([session_label(s) for s in sessions], color="#E0E0E0", fontsize=10)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)], color="#A0A0A0", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444")
    ax.spines["bottom"].set_color("#444")
    ax.grid(axis="x", color="#333", linestyle="--", linewidth=0.5)
    ax.invert_yaxis()
    legend_items = [mpatches.Patch(color=c, label=t, alpha=0.85) for t, c in TAG_COLORS.items()]
    ax.legend(handles=legend_items, loc="lower right", fontsize=8,
              facecolor="#2A2A2A", edgecolor="#555", labelcolor="#CCC",
              ncol=len(TAG_COLORS), title="색상 = 태그", title_fontsize=8)
    ax.set_title(f"{date_str} 작업 타임라인", color="#E0E0E0", fontsize=13, pad=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=BG)
    print(f"[timeline_chart] saved: {output_path}", file=sys.stderr)


def assign_lanes(sessions: list[dict]) -> list[list[dict]]:
    """겹치는 세션을 서로 다른 레인에 배치."""
    lanes: list[list[dict]] = []
    for s in sessions:
        s_start = to_hours(s["start_at"])
        s_end = s_start + (s.get("duration_min") or 30) / 60
        placed = False
        for lane in lanes:
            fits = all(
                s_end <= to_hours(e["start_at"]) or
                s_start >= to_hours(e["start_at"]) + (e.get("duration_min") or 30) / 60
                for e in lane
            )
            if fits:
                lane.append(s)
                placed = True
                break
        if not placed:
            lanes.append([s])
    return lanes


def weekly_chart(data: dict, output_path: str):
    """주간 차트 — 요일별 subplot, 각 subplot은 일일 차트와 동일한 방식."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = FONT

    from collections import defaultdict

    active_days = [d for d in data.get("daily", [])
                   if d.get("activities") or d.get("work_hours", 0) > 0]
    if not active_days:
        print("[timeline_chart] no weekly session data to chart", file=sys.stderr)
        return

    WEEKDAY = "월화수목금토일"

    def repos_for_day(sessions):
        """레포별로 세션 묶기. 총 작업시간 내림차순."""
        by_repo = defaultdict(list)
        for s in dedup(sessions):
            by_repo[s.get("repo") or "?"].append(s)
        return sorted(by_repo.items(), key=lambda kv: -sum(s.get("duration_min") or 30 for s in kv[1]))

    day_repos = [(day, repos_for_day(day.get("activities", []))) for day in active_days]

    heights = [max(1.0, len(repos) * 0.55) for _, repos in day_repos]
    fig, axes = plt.subplots(
        len(day_repos), 1,
        figsize=(15, max(5, sum(heights) + len(heights) * 0.3)),
        gridspec_kw={"height_ratios": heights},
        sharex=True
    )
    if len(day_repos) == 1:
        axes = [axes]
    fig.patch.set_facecolor(BG)

    for ax, (day, repos) in zip(axes, day_repos):
        ax.set_facecolor(BG)

        for row_idx, (repo, sessions) in enumerate(repos):
            # 같은 레포의 세션을 색으로 구분 (태그별)
            for s in sessions:
                start = to_hours(s["start_at"])
                dur = s.get("duration_min") or 30
                end = start + dur / 60
                color = bar_color(s, row_idx)
                ax.barh(row_idx, end - start, left=start, height=0.6,
                        color=color, alpha=0.85, edgecolor="none")

            # 레포 전체 범위에서 라벨 한 번만
            all_starts = [to_hours(s["start_at"]) for s in sessions]
            all_ends = [to_hours(s["start_at"]) + (s.get("duration_min") or 30) / 60 for s in sessions]
            total_min = sum(s.get("duration_min") or 30 for s in sessions)
            mid = (min(all_starts) + max(all_ends)) / 2
            tag = (sessions[0].get("tag") or "기타") if sessions else "기타"
            lbl = f'{repo.split("/")[-1]} [{tag}]  {total_min//60}h{total_min%60:02d}m' if total_min >= 60 \
                  else f'{repo.split("/")[-1]} [{tag}]  {total_min}m'
            ax.text(mid, row_idx, lbl, va="center", ha="center",
                    fontsize=7.5, color="white", fontweight="bold", clip_on=True)

        ax.set_yticks([])
        ax.set_xlim(0, 24)
        ax.invert_yaxis()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#333")
        ax.grid(axis="x", color="#333", linestyle="--", linewidth=0.5)

        dt = datetime.strptime(day["date"], "%Y-%m-%d")
        hours = day.get("work_hours", 0)
        ax.set_ylabel(f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})\n{hours}h',
                      color="#C0C0C0", fontsize=9, rotation=0, labelpad=55, va="center")

    axes[-1].set_xticks(range(0, 25, 2))
    axes[-1].set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)], color="#A0A0A0", fontsize=9)

    # 범례 — 태그별 색상
    import matplotlib.patches as mpatches
    legend_items = [mpatches.Patch(color=c, label=t, alpha=0.85) for t, c in TAG_COLORS.items()]
    axes[-1].legend(
        handles=legend_items, loc="lower right", fontsize=8,
        facecolor="#2A2A2A", edgecolor="#555", labelcolor="#CCC",
        ncol=len(TAG_COLORS), title="색상 = 태그",
        title_fontsize=8,
    )

    dates = data.get("dates", [])
    if dates:
        mon = datetime.strptime(dates[0], "%Y-%m-%d")
        sun = datetime.strptime(dates[6], "%Y-%m-%d")
        title = f'{mon.month}/{mon.day} ~ {sun.month}/{sun.day} 주간 타임라인'
    else:
        title = "주간 타임라인"
    fig.suptitle(title, color="#E0E0E0", fontsize=13)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=BG)
    print(f"[timeline_chart] saved: {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Work session timeline chart")
    parser.add_argument("--weekly", action="store_true", help="Weekly mode (day-by-day)")
    parser.add_argument("--input", help="JSON file (default: stdin)")
    parser.add_argument("--output", default="/tmp/work_timeline.png")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    if args.weekly:
        weekly_chart(data, args.output)
    else:
        daily_chart(data, args.output)


if __name__ == "__main__":
    main()
