#!/usr/bin/env python3
"""파밍 로그를 읽어 사이클·드랍률·구간별 소요를 정리한다.

사용법:
    analyze-logs.py                 분석 결과만 출력
    analyze-logs.py --rewrite       cycle-log.jsonl의 전리품 목록을 정리해
                                    다시 쓴다(원본은 .bak으로 남긴다)

전리품 정리가 필요한 이유: 2026-07-25 이전 기록은 아이템 그리드 아래의
버튼·안내문까지 전리품으로 담았다. 앱은 이후 좌표로 걸러내지만, 이미
쌓인 로그에는 좌표가 없어 텍스트로 근사해 걸러낸다.
"""

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

LOG_DIR = (
    pathlib.Path.home()
    / "Library/Application Support/BackgroundAutomator"
)
KST = timezone(timedelta(hours=9))

# 전리품이 아닌 것: 결과 화면의 버튼·안내문·메타 텍스트.
NOT_LOOT = re.compile(
    r"순수 전투 시간|구역|다음 임무|상세 정보|퀘스트|계속하|도전해"
    r"|부족해|나가기|다시 하기|다시하기|하기$|사용할|사용|ESC|EsC|Space"
)
HANGUL = re.compile(r"[가-힣]")


def clean_item(raw):
    """OCR이 흘린 기호를 떼고 전리품 이름만 남긴다. 아니면 None."""
    name = re.sub(r"^[^가-힣]+", "", raw)
    name = re.sub(r"[^가-힣 ]+$", "", name).strip()
    if not name or not HANGUL.search(name):
        return None
    if NOT_LOOT.search(name):
        return None
    # 자주 나오는 OCR 오독을 표준 이름으로 모은다.
    name = name.replace("마울", "마물")
    # 두 줄로 끊겨 읽힌 이름을 합친다.
    return {
        "미지의": "미지의 소울 조각",
        "소울 조각": "미지의 소울 조각",
        "다이아몬드": "조각난 다이아몬드",
    }.get(name, name)


def clean_items(items):
    seen, out = set(), []
    for raw in items:
        name = clean_item(raw)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def read_jsonl(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def kst(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(KST)


def report_cycles(cycles):
    if not cycles:
        print("사이클 기록 없음")
        return
    times = [kst(c["at"]) for c in cycles]
    span = (times[-1] - times[0]).total_seconds()
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    per = sorted(gaps)[len(gaps) // 2] if gaps else 0

    print(f"■ 사이클 {len(cycles)}판")
    print(f"  구간   {times[0]:%m/%d %H:%M} ~ {times[-1]:%m/%d %H:%M}"
          f"  ({span / 3600:.1f}시간)")
    if per:
        print(f"  속도   판당 {per:.0f}초 = 시간당 {3600 / per:.1f}판")
    stalls = [(a, g) for a, g in zip(times, gaps) if g > 180]
    print(f"  끊김   {len(stalls)}회 (3분 이상)")
    for at, gap in stalls[:5]:
        print(f"         {at:%H:%M:%S} 이후 {gap / 60:.1f}분")

    combat = [c["combatSeconds"] for c in cycles
              if c.get("combatSeconds") is not None]
    if combat:
        print(f"  전투   평균 {sum(combat) / len(combat):.1f}초"
              f" (최소 {min(combat)} · 최대 {max(combat)})")

    dungeons = Counter(c.get("dungeon") for c in cycles if c.get("dungeon"))
    print(f"  던전   {dict(dungeons.most_common(3))}")


def report_drops(cycles):
    total = len(cycles)
    if not total:
        return
    counts = Counter()
    for cycle in cycles:
        for name in clean_items(cycle.get("items", [])):
            counts[name] += 1
    print(f"\n■ 드랍률 ({total}판 기준)")
    print(f"  {'아이템':<20} {'등장':>5} {'비율':>8}")
    print(f"  {'-' * 34}")
    for name, count in counts.most_common(20):
        print(f"  {name:<20} {count:>5} {count / total * 100:>7.1f}%")


def report_phases(events):
    clicks = [e for e in events if e.get("phases")]
    if not clicks:
        print("\n■ 구간별 소요: 기록 없음"
              " (구간 타이밍이 들어간 버전으로 배포하면 채워진다)")
        return
    buckets = defaultdict(list)
    for event in clicks:
        for key, value in event["phases"].items():
            if key.endswith("Milliseconds") and key != "totalMilliseconds":
                buckets[key.replace("Milliseconds", "")].append(value)

    print(f"\n■ 구간별 소요 (클릭 {len(clicks)}회, 중앙값)")
    labels = {
        "observe": "화면 읽기",
        "idleWait": "유휴 대기",
        "reobserve": "재확인",
        "click": "클릭·복귀",
    }
    rows = []
    for key, values in buckets.items():
        values.sort()
        rows.append((values[len(values) // 2], key, values))
    for median, key, values in sorted(rows, reverse=True):
        p95 = values[int(len(values) * 0.95)]
        print(f"  {labels.get(key, key):<10} {median:>6.0f}ms"
              f"   (p95 {p95:.0f}ms)")
    per_click = sum(row[0] for row in rows)
    print(f"  {'합계':<10} {per_click:>6.0f}ms  클릭 1회")

    by_scene = defaultdict(list)
    for event in clicks:
        by_scene[event.get("scene")].append(
            sum(v for k, v in event["phases"].items()
                if k.endswith("Milliseconds") and k != "totalMilliseconds")
        )
    print("\n  씬별 클릭 소요(중앙값):")
    for scene, values in sorted(
        by_scene.items(), key=lambda kv: -sorted(kv[1])[len(kv[1]) // 2]
    ):
        values.sort()
        print(f"    {scene:<20} {values[len(values) // 2]:>6.0f}ms"
              f"  ({len(values)}회)")


def rewrite_cycles(path, cycles):
    backup = path.with_suffix(".jsonl.bak")
    if not backup.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    lines = []
    for cycle in cycles:
        cycle = dict(cycle)
        cycle["items"] = clean_items(cycle.get("items", []))
        lines.append(json.dumps(cycle, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n정리 완료: {path}")
    print(f"원본 백업: {backup}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite", action="store_true",
                        help="cycle-log.jsonl의 전리품 목록을 정리해 다시 쓴다")
    parser.add_argument("--dir", default=str(LOG_DIR), help="로그 디렉터리")
    args = parser.parse_args()

    directory = pathlib.Path(args.dir).expanduser()
    cycle_path = directory / "cycle-log.jsonl"
    cycles = read_jsonl(cycle_path)
    events = read_jsonl(directory / "activity-log.jsonl")
    stalls = read_jsonl(directory / "stall-log.jsonl")

    report_cycles(cycles)
    report_drops(cycles)
    report_phases(events)

    print(f"\n■ 정지 기록 {len(stalls)}건"
          + ("" if stalls else " (멈춘 적 없음)"))
    for stall in stalls[-3:]:
        content = stall.get("content", {})
        print(f"  {kst(stall['updatedAt']):%m/%d %H:%M:%S}"
              f"  {content.get('statusDescription')}")

    if args.rewrite:
        if not cycles:
            print("정리할 사이클 기록이 없다", file=sys.stderr)
            return 1
        rewrite_cycles(cycle_path, cycles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
