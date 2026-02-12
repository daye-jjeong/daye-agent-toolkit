#!/usr/bin/env python3
"""건강 패턴 분석 -- 주간/월간 리포트 (Obsidian vault 기반)"""

import sys, argparse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_io import read_entries, today


def _count(entries, key):
    d = defaultdict(int)
    for _, fm in entries:
        d[fm.get(key, "기타")] += 1
    return dict(d)


def analyze(period):
    days = 7 if period == "week" else 30
    label = "주간" if period == "week" else "월간"
    print(f"분석 기간: 최근 {days}일\n")

    symptoms = read_entries("symptoms", days=days)
    exercises = read_entries("exercises", days=days)
    print(f"증상: {len(symptoms)}개 / 운동: {len(exercises)}개\n")

    # -- report --
    r = f"{label} 건강 리포트 ({today()})\n{'='*40}\n\n"

    r += "[증상 기록]\n"
    if not symptoms:
        r += "  기록된 증상 없음 (좋아요!)\n"
    else:
        r += f"  총 {len(symptoms)}회 기록\n"
        for k, v in _count(symptoms, "type").items():
            r += f"    - {k}: {v}회\n"
        for k, v in _count(symptoms, "severity").items():
            r += f"    - {k}: {v}회\n"

    r += "\n[운동 기록]\n"
    if not exercises:
        r += "  기록된 운동 없음\n"
    else:
        total_dur = sum(fm.get("duration_min", 0) for _, fm in exercises
                        if isinstance(fm.get("duration_min", 0), (int, float)))
        avg = total_dur / len(exercises)
        r += f"  총 {len(exercises)}회 운동 / {total_dur}분 / 평균 {avg:.1f}분\n"
        for k, v in _count(exercises, "type").items():
            r += f"    - {k}: {v}회\n"

    r += "\n[조언]\n"
    if len(exercises) < 3:
        r += "  - 운동 횟수가 적어요. 주 2-3회 이상 목표!\n"
    else:
        r += "  - 운동 잘하고 있어요!\n"
    if len(symptoms) > 5:
        r += "  - 증상이 자주 발생하고 있어요. 병원 방문 고려해보세요.\n"
    pt = _count(exercises, "type").get("PT", 0)
    if pt < 2:
        r += "  - PT 출석률이 낮아요. 주 2회 목표 유지하세요!\n"

    print(r)


def main():
    parser = argparse.ArgumentParser(description="건강 패턴 분석")
    parser.add_argument("--period", default="week", choices=["week", "month"])
    analyze(parser.parse_args().period)


if __name__ == "__main__":
    main()
