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
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

LOG_DIR = pathlib.Path.home() / "Library/Application Support/BackgroundAutomator"
KST = timezone(timedelta(hours=9))

# 전리품이 아닌 것: 결과 화면의 버튼·안내문·메타 텍스트.
NOT_LOOT = re.compile(
    r"순수 전투 시간|구역|다음 임무|상세 정보|퀘스트|계속하|도전해"
    r"|부족해|나가기|다시 하기|다시하기|하기$|사용할|사용|ESC|EsC|Space"
)
HANGUL = re.compile(r"[가-힣]")


# 수량 뱃지('255.3만', '1.3만', '1,382'). 단위 '만'이 한글이라
# 한글 필터를 그냥 통과한다.
QUANTITY = re.compile(r"[\d][\d,.\s]*[만천억]?")

# 오독·조각·제외 규칙은 코드 밖 편집 파일에 둔다. 미인식 배지를 보고 한 줄
# 고쳐 새로고침하는 사이클이 닫히도록. 이름 정규화·자리 비움 기준 등 검증된
# 규칙은 코드에 그대로 둔다(스펙: 다시 만들지 말고 쓴다).
CORRECTIONS_PATH = pathlib.Path(__file__).with_name("loot-corrections.json")


def load_corrections(path=None):
    """전리품 교정 사전을 읽는다. 없거나 깨지면 빈 스켈레톤.
    서버는 요청마다 다시 불러 편집을 즉시 반영한다."""
    empty = {
        "오독": {},
        "조각": {},
        "제외": [],
        "제외_접두": [],
        "분리": {},
        "영혼석": {},
        "재화_표식": [],
    }
    path = pathlib.Path(path) if path else CORRECTIONS_PATH
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty
    for key, default in empty.items():
        data.setdefault(key, default)
    return data


def classify_slot(raw, corrections):
    """전리품 원문 한 칸을 가른다.

      ("item", 이름)         — 아이템으로 센다
      ("excluded", None)     — 수량 뱃지·버튼·이벤트, 조용히 뺀다
      ("unrecognized", 원문) — 해석 못 한 문자열, 미인식으로 세어 화면에 띄운다

    조용한 누락이 이 도구의 유일한 실패 방식이라, 못 읽은 칸은 버리지 않고
    원문 그대로 돌려보낸다.
    """
    text = raw.strip()
    if QUANTITY.fullmatch(text):
        return ("excluded", None)  # 수량 뱃지
    for prefix in corrections.get("제외_접두", ()):
        if text.startswith(prefix):
            return ("excluded", None)  # 다이얼로그·버튼 (정리 전 원문 기준)
    name = re.sub(r"^[^가-힣]+", "", text)
    name = re.sub(r"[^가-힣 ]+$", "", name).strip()
    if not name or not HANGUL.search(name):
        return ("unrecognized", raw)  # 한글이 안 남음 = OCR 잡음
    if NOT_LOOT.search(name):
        return ("excluded", None)  # 버튼·UI 텍스트
    if name in {"만", "천", "억"}:  # 단위 한 글자만 남은 잔해
        return ("excluded", None)
    for wrong, right in corrections.get("오독", {}).items():
        name = name.replace(wrong, right)
    name = corrections.get("조각", {}).get(name, name)
    if name in corrections.get("제외", ()):
        return ("excluded", None)  # 이벤트·버프 표시
    return ("item", name)


def clean_item(raw, corrections=None):
    """원문에서 전리품 이름만 남긴다. 아이템이 아니면 None.
    기존 리포트가 쓰던 좁은 진입점 — 미인식/제외를 구분하지 않는다."""
    kind, value = classify_slot(raw, corrections or CORRECTIONS)
    return value if kind == "item" else None


# '마물 퇴치 증표'와 그 OCR 변종(마울/마을/미물/매물, 증표/종표/중표/층표, 붙어쓰기).
# 매 판 나오는 아이템이라 OCR이 옆 칸과 자주 붙여 읽는다.
TRIBUTE_RE = re.compile(r"[마미매][물울을]\s*퇴\s*치\s*[증종중층]표")
_JUNK = " .,•·{}()[]'\"~_|§:*<>?ㆍ"


def extract_tribute(text):
    """경계(앞끝·뒤끝)에 '마물 퇴치 증표'가 붙어 읽힌 조인을 가른다. 증표를 빼내고
    나머지를 따로 돌린다. 가운데 끼면(양쪽 다 내용) 분리 사전 몫이라 안 건드린다.
    증표 단독(변종)은 원문 그대로 둬 classify_slot의 오독 교정에 맡긴다."""
    mt = TRIBUTE_RE.search(text)
    if not mt:
        return [text]
    before = text[: mt.start()].strip(_JUNK)
    after = text[mt.end() :].strip(_JUNK)
    if before and after:
        return [text]  # 가운데 낀 조인 → 분리 사전이 정확 일치로 처리
    if before:
        return [before, "마물 퇴치 증표"]
    if after:
        return ["마물 퇴치 증표", after]
    return [text]  # 증표 단독(앞뒤 잡음뿐) → classify_slot이 정리


def split_gems(text):
    """OCR이 '조각난 X'(보석 조각) 여럿을 한 칸에 붙여 읽은 조인을 가른다.
    '조각난' 경계마다 자른다 — 앞에 다른 아이템(시즌 경험치 등)이 붙어도 갈린다.
    보석 하나뿐이면 원문 그대로."""
    if "조각난" not in text:
        return [text]
    parts = [p.strip(_JUNK) for p in re.split(r"(?=조각난)", text) if p.strip(_JUNK)]
    return parts if len(parts) > 1 else [text]


def split_slot(raw, split_map):
    """한 칸을 아이템 조각들로 편다. 분리 사전(정확 일치) → 경계 '마물 퇴치 증표'
    추출 → '조각난 보석' 조인 분리 순으로 적용한다."""
    out = []
    for part in split_map.get(raw.strip(), (raw,)):
        for piece in extract_tribute(part):
            out.extend(split_gems(piece))
    return out


def classify_cycle_items(items, corrections):
    """한 판의 원문 칸들 → (아이템 이름 목록, 미인식 원문 목록).
    붙어 읽힌 칸은 분리 사전·증표 추출로 먼저 편다. 같은 판 내 같은 이름은 한 번만."""
    names, unrecognized, seen = [], [], set()
    split_map = corrections.get("분리", {})
    for raw in items:
        for part in split_slot(raw, split_map):
            kind, value = classify_slot(part, corrections)
            if kind == "item":
                if value not in seen:
                    seen.add(value)
                    names.append(value)
            elif kind == "unrecognized":
                unrecognized.append(value)
    return names, unrecognized


def clean_items(items, corrections=None):
    names, _ = classify_cycle_items(items, corrections or CORRECTIONS)
    return names


# 리포트가 corrections 인자 없이 부를 때 쓰는 기본 사전. 서버는 요청마다
# load_corrections()를 다시 불러 편집을 반영하므로 이 전역에 기대지 않는다.
CORRECTIONS = load_corrections()


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
    print(
        f"  구간   {times[0]:%m/%d %H:%M} ~ {times[-1]:%m/%d %H:%M}"
        f"  ({span / 3600:.1f}시간)"
    )
    if per:
        print(f"  속도   판당 {per:.0f}초 = 시간당 {3600 / per:.1f}판")
    stalls = [(a, g) for a, g in zip(times, gaps) if g > 180]
    print(f"  끊김   {len(stalls)}회 (3분 이상)")
    for at, gap in stalls[:5]:
        print(f"         {at:%H:%M:%S} 이후 {gap / 60:.1f}분")

    combat = [c["combatSeconds"] for c in cycles if c.get("combatSeconds") is not None]
    if combat:
        print(
            f"  전투   평균 {sum(combat) / len(combat):.1f}초"
            f" (최소 {min(combat)} · 최대 {max(combat)})"
        )

    display = group_dungeons(cycles)
    dungeons = Counter(
        display[dungeon_key(c["dungeon"])] for c in cycles if c.get("dungeon")
    )
    print(f"  던전   {dict(dungeons.most_common(3))}")

    entries = Counter(c.get("entry") or "미기록" for c in cycles)
    labels = {"coin": "은동전 씀", "tribute": "공물 씀", "free": "임무 해제"}
    print(
        "  입장   "
        + " · ".join(f"{labels.get(k, k)} {v}판" for k, v in entries.most_common())
    )


def report_drops(cycles):
    total = len(cycles)
    if not total:
        return
    counts = Counter()
    # 수량은 뱃지가 붙는 아이템에만 있다. 뱃지 없는 아이템(갱신권·보물 상자)은
    # 등장만 세고 개수는 비운다 — '뱃지 없음 = 1개'로 지어내지 않는다.
    quantity_total, quantity_cycles = Counter(), Counter()
    for cycle in cycles:
        for name in clean_items(cycle.get("items", [])):
            counts[name] += 1
        # 한 판 안에서 같은 아이템이 여러 라벨로 갈리는 일이 있다(실측 23판 중
        # 4판: '마물 퇴치 증표'와 '(마물 퇴치 증표'에 각각 10이 붙었다).
        # 이름을 정리해 합치면서 수량까지 더하면 10개가 20개가 된다.
        # 판마다 이름당 하나만 남기되 큰 값을 쓴다 — 뱃지를 흘려 읽은 쪽이
        # 작게 나오므로(0 등) 제대로 읽은 값이 이긴다.
        per_cycle = {}
        for raw, value in (cycle.get("quantities") or {}).items():
            # 0은 뱃지를 흘려 읽은 것이다('10'을 '0'으로). 앱은 2026-07-29부터
            # 안 남기지만 그 전에 쌓인 로그에는 들어 있어, 평균을 끌어내린다.
            if value > 0 and (name := clean_item(raw)):
                per_cycle[name] = max(per_cycle.get(name, 0), value)
        for name, value in per_cycle.items():
            quantity_total[name] += value
            quantity_cycles[name] += 1
    print(f"\n■ 드랍률 ({total}판 기준)")
    print(f"  {'아이템':<20} {'등장':>5} {'비율':>8} {'개/판':>9} {'수량표본':>7}")
    print(f"  {'-' * 54}")
    for name, count in counts.most_common(20):
        seen = quantity_cycles[name]
        average = f"{quantity_total[name] / seen:,.1f}" if seen else "—"
        sample = f"{seen}판" if seen else "—"
        print(
            f"  {name:<20} {count:>5} {count / total * 100:>7.1f}%"
            f" {average:>9} {sample:>7}"
        )


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
            print(
                f"    {name:<18} {count:>4}판 {share * 100:>5.1f}%"
                f" ±{margin * 100:.1f}%p"
            )


# 규칙 이름이 바뀌면 옛 로그와 새 로그가 다른 줄로 갈린다. 실제로는 같은
# 동작이라 하나로 묶어 본다(2026-07-26: deselect_double_loot → deselect_coin,
# 임무 해제인데 더블 루팅을 끄는 것처럼 읽혀서 바꿨다).
RENAMED_SCENES = {"deselect_double_loot": "deselect_coin"}


def scene_name(event):
    scene = event.get("scene")
    return RENAMED_SCENES.get(scene, scene)


# 상위 구간 안에 이미 포함된 값이다. 합계에 또 더하면 두 번 세게 된다.
SUBPHASES = {"capture", "reobserveCapture"}


def phase_total(phases):
    return sum(
        v
        for k, v in phases.items()
        if k.endswith("Milliseconds")
        and k != "totalMilliseconds"
        and k.replace("Milliseconds", "") not in SUBPHASES
    )


def report_phases(events):
    clicks = [e for e in events if e.get("phases")]
    if not clicks:
        print(
            "\n■ 구간별 소요: 기록 없음"
            " (구간 타이밍이 들어간 버전으로 배포하면 채워진다)"
        )
        return
    buckets = defaultdict(list)
    for event in clicks:
        for key, value in event["phases"].items():
            if not key.endswith("Milliseconds") or key == "totalMilliseconds":
                continue
            if value is None:
                continue
            buckets[key.replace("Milliseconds", "")].append(value)

    print(f"\n■ 구간별 소요 (클릭 {len(clicks)}회, 중앙값)")
    labels = {
        "observe": "화면 읽기",
        "capture": "└ 창 잡기",
        "idleWait": "유휴 대기",
        "reobserve": "재확인",
        "reobserveCapture": "└ 창 잡기",
        "click": "클릭·복귀",
    }
    rows = []
    for key, values in buckets.items():
        values.sort()
        rows.append((values[len(values) // 2], key, values))
    for median, key, values in sorted(rows, reverse=True):
        p95 = values[int(len(values) * 0.95)]
        mark = " " if key in SUBPHASES else ""
        print(
            f"  {mark}{labels.get(key, key):<10} {median:>6.0f}ms"
            f"   (p95 {p95:.0f}ms, {len(values)}건)"
        )
    per_click = sum(row[0] for row in rows if row[1] not in SUBPHASES)
    print(
        f"  {'합계':<10} {per_click:>6.0f}ms  클릭 1회"
        "   (└ 항목은 상위 구간에 이미 포함)"
    )

    by_scene = defaultdict(list)
    for event in clicks:
        by_scene[scene_name(event)].append(phase_total(event["phases"]))
    print("\n  씬별 클릭 소요(중앙값):")
    for scene, values in sorted(
        by_scene.items(), key=lambda kv: -sorted(kv[1])[len(kv[1]) // 2]
    ):
        values.sort()
        print(f"    {scene:<20} {values[len(values) // 2]:>6.0f}ms  ({len(values)}회)")


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


ENTRY_LABELS = {"coin": "은동전 씀", "tribute": "공물 씀", "free": "임무 해제"}


def resolve_entry(cycle):
    """(입장 방식 라벨, 추정 여부).

    기록이 있으면 그대로. 없으면 전리품 칸 수로 메운다 —
    15칸 이상=재화, 6칸 이하=무료, 7~14칸=판정 불가(어느 쪽에도 안 섞음).
    기록이 약 천 판에 없어서 칸 수로 짐작하되, 짐작한 칸은 화면에서 구분한다.
    """
    entry = cycle.get("entry")
    if entry:
        return (ENTRY_LABELS.get(entry, entry), False)
    slots = len(cycle.get("items") or [])
    if slots >= 15:
        return ("재화(추정)", True)
    if slots <= 6:
        return ("무료(추정)", True)
    return ("판정 불가", True)


def cycle_durations(ordered):
    """시각순 다음 판까지의 간격(초). 자리 비움(>5분)·역행은 뺀다. 키는
    id(cycle). 판당 소요·시간당 판수를 이 한 곳에서만 재, 여러 집계가 갈리지
    않게 한다."""
    duration = {}
    for prev, nxt in zip(ordered, ordered[1:]):
        gap = (kst(nxt["at"]) - kst(prev["at"])).total_seconds()
        if 0 < gap <= MAX_CYCLE_GAP:
            duration[id(prev)] = gap
    return duration


def aggregate_farming(cycles, corrections=None):
    """던전 × 입장 방식 × 아이템 → 시간당 획득. 이 함수가 이음새다.

    반환:
      {
        "dungeons": {대표던전명: {입장방식: {
            "games": 판수, "games_per_hour": 시간당 판수, "estimated": 추정 여부,
            "items": {이름: {"total", "per_game", "per_hour"|None, "sample"}}}}},
        "unrecognized": {원문: 건수},   # 해석 못 한 문자열
        "period": {"start", "last", "total_games"},
      }

    규칙:
      - 입장 방식: resolve_entry (기록 우선, 없으면 칸 수)
      - 개수: 수량 뱃지가 있으면 그 값, 없으면 1개
      - 시간당 획득 = 판당 평균 획득 × 시간당 판수
        (시간당 판수 = 3600 / 판당 소요 중앙값. 5분 넘는 간격은 자리 비움이라 뺀다)
      - 표본이 MIN_SAMPLES 미만이면 per_hour를 비우고 sample로 대신한다
    """
    corrections = corrections or CORRECTIONS
    ordered = sorted(cycles, key=lambda c: c["at"])
    display = group_dungeons(ordered)
    duration = cycle_durations(ordered)

    groups = {}
    unrecognized = Counter()
    for cycle in ordered:
        dkey = dungeon_key(cycle.get("dungeon") or "")
        if not dkey:
            continue
        entry_label, estimated = resolve_entry(cycle)
        names, unrec = classify_cycle_items(cycle.get("items", []), corrections)
        for raw in unrec:
            unrecognized[raw] += 1

        # 수량 뱃지: 판마다 이름당 큰 값 하나. 같은 아이템이 여러 라벨로 갈려
        # 각각 뱃지가 붙으면 더해서 두 배가 되므로, 큰 값만 남긴다.
        badges = {}
        for raw, value in (cycle.get("quantities") or {}).items():
            if value > 0:
                kind, name = classify_slot(raw, corrections)
                if kind == "item":
                    badges[name] = max(badges.get(name, 0), value)

        group = groups.setdefault(
            (dkey, entry_label),
            {
                "games": 0,
                "durations": [],
                "estimated": estimated,
                "items": defaultdict(lambda: {"total": 0, "sample": 0}),
            },
        )
        group["games"] += 1
        group["estimated"] = group["estimated"] or estimated
        if id(cycle) in duration:
            group["durations"].append(duration[id(cycle)])
        for name in names:
            item = group["items"][name]
            item["total"] += badges.get(name, 1)  # 뱃지 없으면 1개
            item["sample"] += 1

    dungeons = {}
    for (dkey, entry_label), group in groups.items():
        gph = (
            3600 / statistics.median(group["durations"]) if group["durations"] else None
        )
        enough = group["games"] >= MIN_SAMPLES and gph is not None
        items = {}
        for name, item in group["items"].items():
            per_game = item["total"] / group["games"]
            items[name] = {
                "total": item["total"],
                "per_game": per_game,
                "per_hour": per_game * gph if enough else None,
                "sample": item["sample"],
            }
        dname = display.get(dkey, dkey)
        dungeons.setdefault(dname, {})[entry_label] = {
            "games": group["games"],
            "games_per_hour": gph,
            "estimated": group["estimated"],
            "items": items,
        }

    stamps = [c["at"] for c in ordered]
    return {
        "dungeons": dungeons,
        "unrecognized": dict(unrecognized.most_common()),
        "period": {
            "start": stamps[0] if stamps else None,
            "last": stamps[-1] if stamps else None,
            "total_games": len(ordered),
        },
    }


# ── 영혼석 전용 집계 (스펙: 2026-08-19-mabinogi-soul-stone-dashboard.md) ──
# 관심은 영혼석 5종뿐. 화이트리스트로 캐논을 정하고 나머지는 "기타"로 뭉친다.
# 주 지표는 시간당 데카(= 시간당 개수 × 거래소 시세). 골드 아님.

SOUL_KEY = "영혼석"
SOUL_UNKNOWN = "종류 불명"
# 비심층(룬다·피오드)의 더블 루팅 뱃지는 2. 그 이상은 조인 문자열에서 옆
# 아이템의 수량이 새어 붙은 오염이라 개수를 못 믿는다 → 1개로 센다. (실측:
# '마물 퇴치 증표 망령의 영혼석'에 증표 수량 10·180이 붙어 통계를 부풀렸다.)
SOUL_BADGE_MAX = 2
# 해연 원가 도구가 거래소 시세를 받아 두는 저장소. 읽기만 한다.
PRICE_DB = pathlib.Path.home() / ".mabi-equipment-cost/data.db"


# 5개 대상 던전의 area 루트 → 표준 표기. OCR 변종은 루트 2글자 근사로 잡는다
# (로다·름다→룬다, 페카고는·해카→페카 고분, 피오도·퍼오드→피오드).
DUNGEON_AREAS = {
    "룬다": "룬다",
    "페카": "페카 고분",
    "피오": "피오드",
    "마스": "마스",
    "북쪽": "북쪽 폐허",
}
# 심층 표기와 그 OCR 변종. '1층'이 '심층'에 편집거리 1이라 오탐하던 걸 막으려
# 명시 스펠링만 잡는다.
DEEP_DUNGEON = re.compile(r"심층|심증|실층|심충|실증|심중|삼중|삼한|심연|심총")


def is_deep_dungeon(name):
    """심층 던전인가(OCR 변종 심증·실층 포함). 심층은 '매우 어려움'급이라 더블
    루팅이 없다 — 영혼석이 무조건 1개. 여러 개는 비심층(룬다·피오드)에서만."""
    return bool(DEEP_DUNGEON.search(name or ""))


def canonical_dungeon(name):
    """OCR 변종 던전명을 표준 표기로. 던전 순위가 변종별로 쪼개지지 않게 한다.

    area(룬다·페카 고분·피오드·마스·북쪽 폐허)를 루트 2글자 근사로 매칭하고,
    심층 여부·층·구역을 붙여 "<area>[ 심층] N층 M구역"을 만든다. area를 못
    가리면(타 던전·잘린 이름) "기타 던전"으로 묶어 조용히 버리지 않는다.
    빈 이름은 None.
    """
    norm = normalize_dungeon(name or "")
    if not norm:
        return None
    tokens = norm.split()
    head = tokens[0][:2]
    area = None
    for root, full in DUNGEON_AREAS.items():
        if _within_one_edit(head, root) or norm.replace(" ", "").startswith(root):
            area = full
            break
    if not area:
        return "기타 던전"
    deep = " 심층" if DEEP_DUNGEON.search(norm) else ""
    fz = re.search(r"(\d+)\s*[층등총중충종]\s*(\d+)", norm)
    if fz:
        floor, zone = fz.group(1), fz.group(2)
    else:  # 층·구역이 깨끗이 안 잡히면 남은 숫자 둘로 근사
        nums = re.findall(r"\d+", norm)
        floor = nums[0] if nums else "?"
        zone = nums[1] if len(nums) > 1 else "?"
    return f"{area}{deep} {floor}층 {zone}구역"


def soul_count(badge, deep):
    """이 판에서 이 영혼석을 몇 개로 셀지. 심층은 더블 루팅이 없어 무조건 1개.
    비심층은 뱃지(더블=2)를 쓰되, 2 초과는 조인 오염이라 1개로 본다."""
    if deep:
        return 1
    return badge if badge <= SOUL_BADGE_MAX else 1


def load_soul_whitelist(corrections=None):
    """교정 사전의 영혼석 섹션 → {어간: 캐논 이름}. 없으면 빈 사전."""
    corrections = corrections or CORRECTIONS
    return dict(corrections.get("영혼석", {}))


def load_paid_markers(corrections=None):
    """교정 사전의 재화 표식 목록. 없으면 빈 목록."""
    corrections = corrections or CORRECTIONS
    return list(corrections.get("재화_표식", []))


def is_paid_run(cycle, markers):
    """이 판이 재화(은동전/공물) 판인가. 재화 표식 전리품이 한 칸이라도 있으면
    재화. base(영혼석·증표·화폐)만 있으면 무료. (실측: 재화 판만 파편·조각난
    보석·미스틱 다이스 등을 준다. 앱은 입장 방식을 99.5% 못 남겨 전리품으로
    가른다.)"""
    if not markers:
        return False
    return any(mk in slot for slot in (cycle.get("items") or []) for mk in markers)


def run_mode(cycle, markers):
    """이 판의 재화/무료 판정. 레코드에 "mode"("재화"/"무료") 수동 오버라이드가
    있으면 그걸 따른다(개별 판 수정에서 사람이 못박은 값). 없으면 전리품 표식으로
    가른다. 앱이 입장 방식을 거의 안 남겨 표식이 기본이되, 사람 판단이 우선."""
    forced = cycle.get("mode")
    if forced in ("재화", "무료"):
        return forced
    return "재화" if is_paid_run(cycle, markers) else "무료"


def _within_one_edit(a, b):
    """레벤슈타인 거리 ≤1. 어간(2글자)의 한 글자 오독(망경→망령)을 잡는다."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:  # 짧은 쪽을 a로
        a, b, la, lb = b, a, lb, la
    i = j = edits = 0
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if la == lb:
                i += 1  # 치환
            j += 1  # 삽입 또는 치환 진행
    return edits + (lb - j) + (la - i) <= 1


def match_soul_stone(text, whitelist):
    """전리품 원문 한 칸 → (kind, 어간):

      ("soul", 어간)   화이트리스트 캐논 (망령·야생·공명·원념·파동)
      ("unknown", None) 영혼석인데 어간을 못 가름 → "종류 불명"으로 센다
      (None, None)      영혼석 아님 → "기타(미집계)"로 센다

    매칭: 원문에 '영혼석'이 있고 어간이 근사하면 그 캐논. 조인 문자열
    ('마물 퇴치 증표 망령의 영혼석')·기호 접두('{ 야생의 영혼석')도 잡는다.
    """
    if SOUL_KEY not in text:
        return (None, None)
    for stem in whitelist:  # 어간이 그대로 박혀 있으면 바로 잡는다
        if stem in text:
            return ("soul", stem)
    before = text.split(SOUL_KEY, 1)[0]  # '영혼석' 바로 앞 낱말이 어간
    toks = re.findall(r"[0-9A-Za-z가-힣]+", before)
    cand = toks[-1].rstrip("의이") if toks else ""
    if len(cand) >= 2:  # 한 글자만 남으면(생) 못 가른다 → 종류 불명
        for stem in whitelist:
            if _within_one_edit(cand[-len(stem) :], stem):
                return ("soul", stem)
    return ("unknown", None)


def read_soul_prices(whitelist, db_path=None):
    """해연 원가 도구의 시세 저장소에서 최신 영혼석 시세를 읽는다(읽기 전용).

    반환: ({캐논이름: 데카(min_price)}, as_of ISO | None).
    DB가 없거나 비면 ({}, None) — 데카 열을 지어내지 않는다. 최신 as_of의
    행만, 화이트리스트에 있는 캐논 이름만 남긴다.
    """
    path = pathlib.Path(db_path) if db_path else PRICE_DB
    if not path.exists():
        return {}, None
    names = set(whitelist.values())
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}, None
    try:
        row = con.execute("SELECT MAX(as_of) FROM price_history").fetchone()
        as_of = row[0] if row else None
        if not as_of:
            return {}, None
        prices = {}
        for name, price in con.execute(
            "SELECT name, min_price FROM price_history WHERE as_of = ?", (as_of,)
        ):
            if name in names and price is not None:
                prices[name] = price
        return prices, as_of
    except sqlite3.Error:
        return {}, None
    finally:
        con.close()


def soul_dungeon_ranking(
    cycles, whitelist, prices, corrections=None, mode="all", markers=None
):
    """(로그, 화이트리스트, 시세) → 던전별 영혼석 순위. 이 함수가 이음새다.

    던전 하나당 영혼석 1종이라 행은 (던전, 어간)이고, 입장 방식은 합산한다.
    주 지표는 시간당 데카(내림차순). 시세 없는 어간은 데카를 비우고 개수만.

    mode: "all"(전체) | "paid"(재화 판만) | "free"(무료 판만). 재화/무료는
    재화 표식 전리품으로 가른다(is_paid_run). 판당 소요(gph)는 던전 전체 판
    기준으로 공유하고 — 재화 판은 띄엄띄엄이라 재화만의 시간당 판수가 무의미 —
    판당 개수·판수만 모드별로 센다. 기타·종류 불명은 전체 기준(진단용).

    반환:
      {
        "rows": [ {  # per_hour_deca 내림차순, 데카 없는 행은 뒤로
            "dungeon", "stem", "name", "price",
            "games", "games_per_hour", "estimated",
            "count_total", "count_per_game",
            "per_hour_count"|None, "per_hour_deca"|None,
        } ],
        "other_count":   기타(미집계) 건수 (영혼석 아닌 아이템 슬롯),
        "unknown_count": 종류 불명 건수 (어간 못 가른 영혼석),
        "period": {"start", "last", "total_games"},
      }

    개수: 심층은 무조건 1, 비심층은 뱃지(더블=2, 오염값은 1).
    시간당 개수 = 판당 개수 × 시간당 판수(5분 넘는 간격 제외, 표본 부족이면 비움).
    """
    corrections = corrections or CORRECTIONS
    if markers is None:
        markers = load_paid_markers(corrections)
    ordered = sorted(cycles, key=lambda c: c["at"])
    duration = cycle_durations(ordered)
    split_map = corrections.get("분리", {})

    groups = {}
    other_items = Counter()  # 기타(미집계): 영혼석 아닌 아이템 원문 → 건수
    unknown_items = Counter()  # 종류 불명: 어간 못 가른 영혼석 원문 → 건수
    for cycle in ordered:
        dkey = canonical_dungeon(cycle.get("dungeon"))  # OCR 변종 병합
        if not dkey:
            continue
        _, estimated = resolve_entry(cycle)
        deep = is_deep_dungeon(cycle.get("dungeon"))
        rmode = run_mode(cycle, markers)
        in_mode = (
            mode == "all"
            or (mode == "paid" and rmode == "재화")
            or (mode == "free" and rmode == "무료")
        )

        # 이 판의 뱃지: 어간별 최대값. 같은 영혼석이 여러 라벨로 갈려 각각
        # 뱃지가 붙으면 더해서 두 배가 되므로 큰 값만 남긴다.
        badges = {}
        for raw, value in (cycle.get("quantities") or {}).items():
            if value > 0:
                kind, stem = match_soul_stone(raw, whitelist)
                if kind == "soul":
                    badges[stem] = max(badges.get(stem, 0), value)

        # 슬롯 분류. 어간은 판당 한 번(더블 슬롯 중복 제거). 개수는 심층이면
        # 무조건 1, 비심층이면 뱃지(오염값은 1로). 기타·종류 불명은 모드와
        # 무관하게 전체 기준으로 센다(진단용 헤더).
        seen = set()
        soul_hits = {}
        for slot in cycle.get("items", []):
            for part in split_slot(slot, split_map):
                kind, stem = match_soul_stone(part, whitelist)
                if kind == "soul":
                    if stem not in seen:
                        seen.add(stem)
                        soul_hits[stem] = soul_count(badges.get(stem, 1), deep)
                elif kind == "unknown":
                    unknown_items[part.strip()] += 1
                else:  # 영혼석 아님: 아이템으로 읽히면 기타, UI 잡음은 무시
                    itemkind, name = classify_slot(part, corrections)
                    if itemkind == "item":
                        other_items[name] += 1

        group = groups.setdefault(
            dkey,
            {
                "games": 0,
                "durations": [],
                "estimated": False,
                "stems": defaultdict(int),
            },
        )
        # gph는 전체 판 기준(모드 무관). 판수·소울·추정은 모드 판만.
        if id(cycle) in duration:
            group["durations"].append(duration[id(cycle)])
        if not in_mode:
            continue
        group["games"] += 1
        group["estimated"] = group["estimated"] or estimated
        for stem, cnt in soul_hits.items():
            group["stems"][stem] += cnt

    rows = []
    for dkey, group in groups.items():
        gph = (
            3600 / statistics.median(group["durations"]) if group["durations"] else None
        )
        enough = group["games"] >= MIN_SAMPLES and gph is not None
        dname = dkey  # canonical 이름이 곧 표시명
        for stem, total in group["stems"].items():
            per_game = total / group["games"]
            per_hour_count = per_game * gph if enough else None
            name = whitelist.get(stem)
            price = prices.get(name) if name else None
            per_hour_deca = (
                per_hour_count * price
                if per_hour_count is not None and price is not None
                else None
            )
            rows.append(
                {
                    "dungeon": dname,
                    "stem": stem,
                    "name": name,
                    "price": price,
                    "games": group["games"],
                    "games_per_hour": gph,
                    "estimated": group["estimated"],
                    "count_total": total,
                    "count_per_game": per_game,
                    "per_hour_count": per_hour_count,
                    "per_hour_deca": per_hour_deca,
                }
            )

    # 데카 있는 행 먼저(내림차순), 그다음 개수 있는 행, 그다음 나머지.
    rows.sort(
        key=lambda r: (
            r["per_hour_deca"] is None,
            -(r["per_hour_deca"] or 0),
            r["per_hour_count"] is None,
            -(r["per_hour_count"] or 0),
            -r["count_total"],
        )
    )
    stamps = [c["at"] for c in ordered]
    return {
        "rows": rows,
        "other_count": sum(other_items.values()),
        "unknown_count": sum(unknown_items.values()),
        "other_items": dict(other_items.most_common()),  # 진단: 기타 원문 → 건수
        "unknown_items": dict(unknown_items.most_common()),  # 진단: 종류 불명 원문
        "period": {
            "start": stamps[0] if stamps else None,
            "last": stamps[-1] if stamps else None,
            "total_games": len(ordered),
        },
    }


def daily_soul_deca(cycles, whitelist, prices, markers=None):
    """날짜별 시간당 데카(전 던전 합산). 활동량 차트의 부가 추세선용.

    반환: [{"date", "deca_per_hour", "deca_total", "paid_deca", "free_deca"}]
    (날짜 오름차순). 총 데카는 재화 판/무료 판 몫으로도 갈라 낸다(stacked 막대용).
    가동 시간·개수 규칙은 다른 집계와 같다 — 5분 넘는 간격은 자리 비움이라
    빼고, 개수는 심층이면 1·비심층이면 뱃지. 시세 없거나 가동 0이면 비운다.
    """
    if markers is None:
        markers = load_paid_markers(CORRECTIONS)
    ordered = sorted(cycles, key=lambda c: c["at"])
    by_day = {}
    for c in ordered:
        at = kst(c["at"])
        day = at.date()
        deep = is_deep_dungeon(c.get("dungeon"))
        paid = run_mode(c, markers) == "재화"
        row = by_day.setdefault(
            day,
            {
                "active": 0.0,
                "prev": None,
                "deca": 0.0,
                "paid": 0.0,
                "free": 0.0,
                "priced": False,
            },
        )
        badges = {}
        for raw, value in (c.get("quantities") or {}).items():
            if value > 0:
                kind, stem = match_soul_stone(raw, whitelist)
                if kind == "soul":
                    badges[stem] = max(badges.get(stem, 0), value)
        seen = set()
        for slot in c.get("items", []):
            kind, stem = match_soul_stone(slot, whitelist)
            if kind == "soul" and stem not in seen:
                seen.add(stem)
                price = prices.get(whitelist.get(stem))
                if price is not None:
                    gain = soul_count(badges.get(stem, 1), deep) * price
                    row["deca"] += gain
                    row["paid" if paid else "free"] += gain
                    row["priced"] = True
        if row["prev"] is not None:
            gap = (at - row["prev"]).total_seconds()
            if 0 < gap <= MAX_CYCLE_GAP:
                row["active"] += gap
        row["prev"] = at

    out = []
    for day in sorted(by_day):
        r = by_day[day]
        hours = r["active"] / 3600
        dph = r["deca"] / hours if hours > 0 and r["priced"] else None
        out.append(
            {
                "date": f"{day:%m/%d}",
                "deca_per_hour": dph,  # 시간당 데카
                "deca_total": r["deca"] if r["priced"] else None,  # 그날 총 데카
                "paid_deca": r["paid"] if r["priced"] else None,  # 재화 판 몫
                "free_deca": r["free"] if r["priced"] else None,  # 무료 판 몫
            }
        )
    return out


def dungeon_detail(cycles, dungeon, whitelist, prices, corrections=None, markers=None):
    """한 던전의 상세 분석 데이터. 순위표 행을 눌렀을 때 여는 뷰용.

    던전(canonical 이름)에 속한 판만 모아 낸다:
      - 성과: 판수·판당/시간당 개수·시간당 데카·총 데카 누적·드랍률(N판당 1개)
      - daily: 날짜별 판수·가동·드랍률(개/판)·총 데카 → 패치로 확률이 바뀌었나
      - 재화/무료: paid/free 각각 판수·판당·시간당
      - hours: 시간대(KST) 판수 분포
      - other_items: 같이 나온 기타 아이템 빈도
    없는 던전이면 None.
    """
    corrections = corrections or CORRECTIONS
    if markers is None:
        markers = load_paid_markers(corrections)
    ordered = sorted(cycles, key=lambda c: c["at"])
    duration = cycle_durations(ordered)
    split_map = corrections.get("분리", {})
    sel = [c for c in ordered if canonical_dungeon(c.get("dungeon")) == dungeon]
    if not sel:
        return None

    deep = any(is_deep_dungeon(c.get("dungeon")) for c in sel)
    stem_total = Counter()
    other = Counter()
    other_paid = Counter()  # 재화 판에서 나온 기타 전리품
    other_free = Counter()  # 무료 판에서 나온 기타 전리품
    hours = Counter()
    hours_paid = Counter()  # 시간대별 재화 판수
    hours_free = Counter()  # 시간대별 무료 판수
    durations = []
    by_day = {}
    paid_g = free_g = paid_soul = free_soul = 0
    for c in sel:
        at = kst(c["at"])
        row = by_day.setdefault(
            at.date(),
            {
                "games": 0,
                "soul": 0,
                "active": 0.0,
                "prev": None,
                "paid_games": 0,
                "paid_soul": 0,
                "free_games": 0,
                "free_soul": 0,
            },
        )
        row["games"] += 1
        hours[at.hour] += 1
        paid = run_mode(c, markers) == "재화"
        (hours_paid if paid else hours_free)[at.hour] += 1

        badges = {}
        for raw, v in (c.get("quantities") or {}).items():
            if v > 0:
                k, st = match_soul_stone(raw, whitelist)
                if k == "soul":
                    badges[st] = max(badges.get(st, 0), v)
        seen = set()
        hit = 0
        for slot in c.get("items", []):
            for part in split_slot(slot, split_map):
                k, st = match_soul_stone(part, whitelist)
                if k == "soul":
                    if st not in seen:
                        seen.add(st)
                        cnt = soul_count(badges.get(st, 1), deep)
                        stem_total[st] += cnt
                        hit += cnt
                elif k != "unknown":
                    itemkind, name = classify_slot(part, corrections)
                    if itemkind == "item":
                        other[name] += 1
                        (other_paid if paid else other_free)[name] += 1
        row["soul"] += hit
        row["paid_games" if paid else "free_games"] += 1
        row["paid_soul" if paid else "free_soul"] += hit
        if paid:
            paid_g += 1
            paid_soul += hit
        else:
            free_g += 1
            free_soul += hit
        if id(c) in duration:
            durations.append(duration[id(c)])
        if row["prev"] is not None:
            gap = (at - row["prev"]).total_seconds()
            if 0 < gap <= MAX_CYCLE_GAP:
                row["active"] += gap
        row["prev"] = at

    games = len(sel)
    gph = 3600 / statistics.median(durations) if durations else None
    stem = stem_total.most_common(1)[0][0] if stem_total else None
    name = whitelist.get(stem) if stem else None
    price = prices.get(name) if name else None
    total_count = sum(stem_total.values())
    per_game = total_count / games if games else 0
    enough = games >= MIN_SAMPLES and gph is not None
    per_hour_count = per_game * gph if enough else None
    per_hour_deca = (
        per_hour_count * price
        if per_hour_count is not None and price is not None
        else None
    )

    def side(g, s):  # 재화/무료 한쪽
        pg = s / g if g else 0
        ok = g >= MIN_SAMPLES and gph is not None
        phc = pg * gph if ok else None
        return {
            "games": g,
            "per_game": pg,
            "per_hour_count": phc,
            "per_hour_deca": (
                phc * price if phc is not None and price is not None else None
            ),
        }

    daily = []
    for day in sorted(by_day):
        r = by_day[day]
        pg, fg = r["paid_games"], r["free_games"]
        daily.append(
            {
                "date": f"{day:%m/%d}",
                "games": r["games"],
                "active_hours": r["active"] / 3600,
                "soul": r["soul"],
                "per_game": r["soul"] / r["games"] if r["games"] else 0,  # 드랍률
                "deca": r["soul"] * price if price is not None else None,
                # 날짜별로도 재화/무료 갈라 낸다(패치+재화 효과 비교용).
                "paid_games": pg,
                "paid_per_game": r["paid_soul"] / pg if pg else None,
                "free_games": fg,
                "free_per_game": r["free_soul"] / fg if fg else None,
            }
        )

    # 돌린 구간(세션): 20분 이상 벌어지면 끊는다. 각 구간의 시작~종료·판수(재화/무료).
    sessions = []
    prev = cur = None
    for c in sel:
        at = kst(c["at"])
        if cur is None or (at - prev).total_seconds() > SESSION_GAP:
            cur = {"start": c["at"], "end": c["at"], "games": 0, "paid": 0, "free": 0}
            sessions.append(cur)
        cur["end"] = c["at"]
        cur["games"] += 1
        cur["paid" if run_mode(c, markers) == "재화" else "free"] += 1
        prev = at
    sessions.reverse()  # 최근 구간이 위로

    return {
        "dungeon": dungeon,
        "stem": stem,
        "name": name,
        "price": price,
        "deep": deep,
        "games": games,
        "first": sel[0]["at"],
        "last": sel[-1]["at"],
        "games_per_hour": gph,
        "per_game": per_game,
        "per_hour_count": per_hour_count,
        "per_hour_deca": per_hour_deca,
        "total_count": total_count,
        "total_deca": total_count * price if price is not None else None,
        "drop_rate": games / total_count if total_count else None,  # N판당 1개
        "daily": daily,
        "sessions": sessions,  # 돌린 구간별 시작~종료·판수
        "hours": {str(h): n for h, n in sorted(hours.items())},
        "hours_paid": {str(h): n for h, n in sorted(hours_paid.items())},
        "hours_free": {str(h): n for h, n in sorted(hours_free.items())},
        "paid": side(paid_g, paid_soul),
        "free": side(free_g, free_soul),
        "other_items": dict(other.most_common(30)),
        "other_paid": dict(other_paid.most_common(30)),
        "other_free": dict(other_free.most_common(30)),
    }


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


def daily_summary(cycles):
    """날짜별 판 수·가동 시간·판당 소요·전투·영혼석. 터미널과 웹이 같은
    숫자를 쓰도록 여기 한 곳에서만 계산한다.

    반환: [{"date": "MM/DD", "games", "active_hours", "per_game_sec",
            "combat_avg", "soul_games", "soul_rate"}] (날짜 오름차순)
    """
    by_day = {}
    for c in cycles:
        day = kst(c["at"]).date()
        row = by_day.setdefault(
            day, {"n": 0, "combat": [], "soul": 0, "active": 0.0, "prev": None}
        )
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

    out = []
    for day in sorted(by_day):
        r = by_day[day]
        out.append(
            {
                "date": f"{day:%m/%d}",
                "games": r["n"],
                "active_hours": r["active"] / 3600,
                "per_game_sec": r["active"] / (r["n"] - 1) if r["n"] > 1 else 0,
                "combat_avg": statistics.mean(r["combat"]) if r["combat"] else 0,
                "soul_games": r["soul"],
                "soul_rate": r["soul"] / r["n"] * 100 if r["n"] else 0,
            }
        )
    return out


def report_daily(cycles):
    """날짜별 판 수·전투 시간·영혼석. 파밍은 자정을 넘겨 이어지므로
    누적만 보면 '오늘 얼마나 돌았나'를 알 수 없다."""
    rows = daily_summary(cycles)
    if not rows:
        return
    print("\n■ 날짜별 기록")
    print("  날짜          판수   가동      판당    전투    영혼석")
    for r in rows:
        print(
            f"  {r['date']}  {r['games']:8d}  {r['active_hours']:5.1f}h"
            f"  {r['per_game_sec']:6.0f}초  {r['combat_avg']:5.1f}초"
            f"  {r['soul_games']:3d}판 {r['soul_rate']:4.1f}%"
        )


UNSTAMPED = "(스탬프 이전)"
# 이만큼은 쌓여야 판당 소요 중앙값을 믿는다. 배포 직후 두세 판으로 "빨라졌다"
# 를 말했다가 뒤집힌 적이 있다(2026-07-26).
MIN_SAMPLES = 20
# 이보다 벌어진 간격은 자리를 비운 것으로 본다. 앱의
# CycleTracker.maximumCycleGapSeconds와 같은 값이어야 두 곳의 "가동 시간"이
# 갈리지 않는다. 정상 판당 105~130초, 멈춤 감지 기준 150초.
MAX_CYCLE_GAP = 300
# 던전 상세의 '돌린 구간(세션)' 경계. 이보다 벌어지면 다른 판 사이(딴짓·휴식)로
# 보고 세션을 끊는다. 가동(5분)보다 넉넉히 잡아 한 번 앉아 돌린 걸 한 구간으로.
SESSION_GAP = 1200


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
        app_ms[event.get("build") or UNSTAMPED].append(phase_total(event["phases"]))

    print("\n■ 빌드별 비교")
    print(
        f"  {'빌드':<19} {'판수':>5} {'판당':>7} {'앱 구간':>9} {'보상읽기':>7}  변경"
    )
    print(f"  {'-' * 76}")
    thin = []
    for build, stamps in sorted(times.items(), key=lambda kv: max(kv[1]), reverse=True):
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
        print(
            f"  {build:<19} {len(stamps):>5}"
            f" {per:>6.0f}초{mark:<1}"
            f" {statistics.median(phases) if phases else 0:>7.0f}ms"
            f" {sum(hits) / len(hits) * 100:>6.0f}%"
            f"  {summaries.get(build) or '—'}"
        )
    if thin:
        print(f"  * 표본 {MIN_SAMPLES}판 미만 — 판당 소요를 비교에 쓰지 마라")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="cycle-log.jsonl의 전리품 목록을 정리해 다시 쓴다",
    )
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

    print(f"\n■ 정지 기록 {len(stalls)}건" + ("" if stalls else " (멈춘 적 없음)"))
    for stall in stalls[-3:]:
        content = stall.get("content", {})
        print(
            f"  {kst(stall['updatedAt']):%m/%d %H:%M:%S}"
            f"  {content.get('statusDescription')}"
        )

    if args.rewrite:
        if not cycles:
            print("정리할 사이클 기록이 없다", file=sys.stderr)
            return 1
        rewrite_cycles(cycle_path, cycles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
