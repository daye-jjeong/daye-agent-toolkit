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
import math
import pathlib
import re
import statistics
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
    # 수량 뱃지('255.3만', '1.3만', '1,382'). 단위 '만'이 한글이라
    # 한글 필터를 그냥 통과했다.
    if QUANTITY.fullmatch(raw.strip()):
        return None
    name = re.sub(r"^[^가-힣]+", "", raw)
    name = re.sub(r"[^가-힣 ]+$", "", name).strip()
    if not name or not HANGUL.search(name):
        return None
    if NOT_LOOT.search(name):
        return None
    # 단위 한 글자만 남은 잔해('만', '천').
    if name in {"만", "천", "억"}:
        return None
    # 자주 나오는 OCR 오독을 표준 이름으로 모은다.
    for wrong, right in (("마울", "마물"), ("종표", "증표"), ("퇴 치", "퇴치")):
        name = name.replace(wrong, right)
    return FRAGMENTS.get(name, name)


# 아이콘 하나 밑에 두 줄로 쌓인 이름이 따로 기록된 것들.
# 앱은 2026-07-26부터 좌표로 이어 붙이지만, 그 전 로그엔 조각으로 남아 있다.
FRAGMENTS = {
    "미지의": "미지의 소울 조각",
    "소울 조각": "미지의 소울 조각",
    "조각난": "조각난 다이아몬드",
    "다이아몬드": "조각난 다이아몬드",
    "세공된 블루": "세공된 블루 스피넬",
    "스피넬": "세공된 블루 스피넬",
    "타격의 블루": "타격의 블루 스피넬 펜던트",
    "스피넬 펜던트": "타격의 블루 스피넬 펜던트",
}

QUANTITY = re.compile(r"[\d][\d,.\s]*[만천억]?")


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

    display = group_dungeons(cycles)
    dungeons = Counter(
        display[dungeon_key(c["dungeon"])] for c in cycles if c.get("dungeon")
    )
    print(f"  던전   {dict(dungeons.most_common(3))}")

    entries = Counter(c.get("entry") or "미기록" for c in cycles)
    labels = {"coin": "은동전 씀", "tribute": "공물 씀", "free": "임무 해제"}
    print("  입장   " + " · ".join(
        f"{labels.get(k, k)} {v}판" for k, v in entries.most_common()
    ))


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


def report_drops_by_entry(cycles):
    """재화를 쓰고 들어간 판과 아닌 판을 갈라 본다.

    입장 방식이 기록되기 전에는 전리품 칸 수로 짐작해야 했다(재화를 쓰면
    3칸 → 24칸). 짐작은 기록이 아니라서, 판마다 어떤 규칙으로 들어갔는지를
    같이 남긴다. `미기록`은 앱이 입장 버튼을 누르지 않은 판이다.
    """
    groups = defaultdict(list)
    for cycle in cycles:
        groups[cycle.get("entry") or "미기록"].append(cycle)
    known = {k: v for k, v in groups.items() if k != "미기록"}
    if not known:
        return

    labels = {"coin": "은동전 씀", "tribute": "공물 씀", "free": "임무 해제"}
    print("\n■ 입장 방식별 드랍률")
    for key, sel in sorted(known.items(), key=lambda kv: -len(kv[1])):
        n = len(sel)
        counts = Counter()
        for cycle in sel:
            for name in clean_items(cycle.get("items", [])):
                counts[name] += 1
        print(f"\n  {labels.get(key, key)} — {n}판")
        if n < MIN_SAMPLES:
            print(f"    표본 {MIN_SAMPLES}판 미만 — 비율을 비교에 쓰지 마라")
        for name, count in counts.most_common(8):
            share = count / n
            margin = 1.96 * math.sqrt(share * (1 - share) / n)
            print(f"    {name:<18} {count:>4}판 {share * 100:>5.1f}%"
                  f" ±{margin * 100:.1f}%p")


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


def normalize_dungeon(name):
    """같은 던전이 '룬다 1층 2구역'·'룬다. 1층 2구역'·"룬다 '1층 2구역*"
    셋으로 쌓여 통계가 쪼개졌다. 앱과 같은 규칙으로 모은다."""
    # 파이썬 \w는 '_'를 포함하지만 앱의 normalizedName은 글자·숫자만
    # 남긴다. OCR이 밑줄을 뱉는 건 실제 사례가 있다('장면 넘기기_').
    # 어긋나면 --rewrite한 과거 로그와 앞으로 쌓일 이름이 갈린다.
    return " ".join(re.sub(r"[^0-9A-Za-z가-힣]+", " ", name).split())


def dungeon_key(name):
    """띄어쓰기를 지운 집계 키. OCR이 '페카고분 심층 1층 2구역'(27판)과
    '페카 고분 심층 1층 2구역'(8판)으로 갈라 읽어 같은 던전이 쪼개졌다."""
    return re.sub(r"\s+", "", normalize_dungeon(name or ""))


def group_dungeons(cycles):
    """집계 키 → 대표 표기(처음 읽은 것). 붙여 쓴 표기가 이기면 읽기 나쁘다."""
    display = {}
    for cycle in cycles:
        name = cycle.get("dungeon")
        if name:
            display.setdefault(dungeon_key(name), normalize_dungeon(name))
    return display


def rewrite_cycles(path, cycles):
    backup = path.with_suffix(".jsonl.bak")
    if not backup.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    lines = []
    for cycle in cycles:
        cycle = dict(cycle)
        cycle["items"] = clean_items(cycle.get("items", []))
        if cycle.get("dungeon"):
            cycle["dungeon"] = normalize_dungeon(cycle["dungeon"])
        lines.append(json.dumps(cycle, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n정리 완료: {path}")
    print(f"원본 백업: {backup}")


def report_daily(cycles):
    """날짜별 판 수·전투 시간·영혼석. 파밍은 자정을 넘겨 이어지므로
    누적만 보면 '오늘 얼마나 돌았나'를 알 수 없다."""
    if not cycles:
        return
    by_day = {}
    for c in cycles:
        day = kst(c["at"]).date()
        row = by_day.setdefault(day, {"n": 0, "combat": [], "soul": 0,
                                      "active": 0.0, "prev": None})
        row["n"] += 1
        if c.get("combatSeconds"):
            row["combat"].append(c["combatSeconds"])
        if any("영혼석" in i for i in c.get("items", [])):
            row["soul"] += 1
        at = kst(c["at"])
        # 앱의 CycleSummary.todayActiveSeconds와 같은 기준. 처음~끝 폭으로
        # 재면 자리를 비운 시간까지 '돌린 시간'에 들어가 판당 소요가 거짓이 된다.
        if row["prev"] is not None:
            gap = (at - row["prev"]).total_seconds()
            if 0 < gap <= MAX_CYCLE_GAP:
                row["active"] += gap
        row["prev"] = at

    print("\n■ 날짜별 기록")
    print("  날짜          판수   가동      판당    전투    영혼석")
    for day in sorted(by_day):
        r = by_day[day]
        span = r["active"]
        hours = span / 3600
        per = span / (r["n"] - 1) if r["n"] > 1 else 0
        combat = statistics.mean(r["combat"]) if r["combat"] else 0
        rate = r["soul"] / r["n"] * 100 if r["n"] else 0
        print(f"  {day:%m/%d}  {r['n']:8d}  {hours:5.1f}h"
              f"  {per:6.0f}초  {combat:5.1f}초  {r['soul']:3d}판 {rate:4.1f}%")


UNSTAMPED = "(스탬프 이전)"
# 이만큼은 쌓여야 판당 소요 중앙값을 믿는다. 배포 직후 두세 판으로 "빨라졌다"
# 를 말했다가 뒤집힌 적이 있다(2026-07-26).
MIN_SAMPLES = 20
# 이보다 벌어진 간격은 자리를 비운 것으로 본다. 앱의
# CycleTracker.maximumCycleGapSeconds와 같은 값이어야 두 곳의 "가동 시간"이
# 갈리지 않는다. 정상 판당 105~130초, 멈춤 감지 기준 150초.
MAX_CYCLE_GAP = 300


def report_builds(cycles, events, builds):
    """빌드별 성능 비교.

    시각으로 배포 전후를 가르면 두 군데서 어긋난다 — 빌드해도 앱을 다시
    켜지 않으면 옛 바이너리가 계속 돌고, 배포 시각이 로그에 없어 기억으로
    역산해야 한다. 그래서 기록에 박힌 빌드 아이디로 나눈다.
    """
    if not cycles:
        return
    summaries = {b["build"]: b.get("summary") for b in builds}

    times, app_ms, got_items = defaultdict(list), defaultdict(list), defaultdict(list)
    for cycle in cycles:
        build = cycle.get("build") or UNSTAMPED
        times[build].append(kst(cycle["at"]))
        got_items[build].append(bool(clean_items(cycle.get("items", []))))
    for event in events:
        if not event.get("phases"):
            continue
        app_ms[event.get("build") or UNSTAMPED].append(
            sum(v for k, v in event["phases"].items()
                if k.endswith("Milliseconds") and k != "totalMilliseconds")
        )

    print("\n■ 빌드별 비교")
    print(f"  {'빌드':<19} {'판수':>5} {'판당':>7} {'앱 구간':>9}"
          f" {'보상읽기':>7}  변경")
    print(f"  {'-' * 76}")
    thin = []
    for build, stamps in sorted(times.items(), key=lambda kv: max(kv[1]),
                                reverse=True):
        stamps.sort()
        # 같은 빌드 안에서만 이어 잰다. 재시작으로 벌어진 간격은 잘라낸다.
        gaps = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:])]
        gaps = [g for g in gaps if g < 300]
        per = statistics.median(gaps) if gaps else 0
        phases = app_ms.get(build) or []
        hits = got_items[build]
        mark = "" if len(gaps) >= MIN_SAMPLES else "*"
        if mark:
            thin.append(build)
        print(f"  {build:<19} {len(stamps):>5}"
              f" {per:>6.0f}초{mark:<1}"
              f" {statistics.median(phases) if phases else 0:>7.0f}ms"
              f" {sum(hits) / len(hits) * 100:>6.0f}%"
              f"  {summaries.get(build) or '—'}")
    if thin:
        print(f"  * 표본 {MIN_SAMPLES}판 미만 — 판당 소요를 비교에 쓰지 마라")


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
    builds = read_jsonl(directory / "builds.jsonl")

    report_cycles(cycles)
    report_builds(cycles, events, builds)
    report_daily(cycles)
    report_drops(cycles)
    report_drops_by_entry(cycles)
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
