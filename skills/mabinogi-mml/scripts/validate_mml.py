"""마비노기 모바일 MML 제약 검증 + 압축 제안. stdlib only."""
import re

MAX_TRACKS = 6
MAX_CHARS_PER_PART = 1200  # 1200/2400 소스 상이. 보수적 기본. 게임 실측 후 조정.
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}


def parse_tracks(mml: str) -> list[str]:
    """`MML@t1,t2,...;` → 트랙 리스트. 래퍼 없으면 단일 트랙."""
    s = mml.strip()
    if s.upper().startswith("MML@"):
        s = s[4:]
    if s.endswith(";"):
        s = s[:-1]
    return s.split(",")


def check_limits(tracks: list[str], max_tracks: int = MAX_TRACKS,
                 max_chars: int = MAX_CHARS_PER_PART) -> list[str]:
    """제약 위반(violations). 빈 리스트면 통과."""
    v: list[str] = []
    if len(tracks) > max_tracks:
        v.append(f"트랙 수 {len(tracks)}개 — 최대 {max_tracks}개 초과")
    for i, t in enumerate(tracks, 1):
        if len(t) > max_chars:
            v.append(f"트랙 {i} 글자수 {len(t)} — 파트당 최대 {max_chars} 초과")
    return v


_TOKEN_RE = re.compile(
    r"(?P<note>[a-gA-G])(?P<acc>[+#-]?)(?P<len>\d*)(?P<dot>\.*)"
    r"|(?P<rest>[rR])(?P<rlen>\d*)(?P<rdot>\.*)"
    r"|[nN](?P<npitch>\d+)(?P<nlen>\d*)(?P<ndot>\.*)"
    r"|[lL](?P<ldef>\d+)"
    r"|[oO]\d+|[<>]|[tT]\d+|[vV]\d+"
)


def _len_to_ticks(length: int, dots: int, ppq: int) -> int:
    base = (4 * ppq) // length
    total = add = base
    for _ in range(dots):
        add //= 2
        total += add
    return total


def track_tick_length(track: str, ppq: int = 480) -> int:
    """총 연주 길이(tick). l 기본길이/점음표/쉼표/N명령 반영. o<>tv는 0."""
    cur_l = MABI_DEFAULTS["l"]
    total = 0
    for m in _TOKEN_RE.finditer(track):
        if m.group("ldef"):
            cur_l = int(m.group("ldef"))
        elif m.group("note"):
            ln = int(m.group("len")) if m.group("len") else cur_l
            total += _len_to_ticks(ln, len(m.group("dot")), ppq)
        elif m.group("rest"):
            ln = int(m.group("rlen")) if m.group("rlen") else cur_l
            total += _len_to_ticks(ln, len(m.group("rdot")), ppq)
        elif m.group("npitch"):
            ln = int(m.group("nlen")) if m.group("nlen") else cur_l
            total += _len_to_ticks(ln, len(m.group("ndot")), ppq)
    return total


def check_desync(tracks: list[str], ppq: int = 480) -> list[str]:
    """트랙 길이 불일치 = warning(곡 구조상 정상일 수 있음, hard-fail 아님)."""
    lengths = [track_tick_length(t, ppq) for t in tracks if t.strip()]
    if len(set(lengths)) > 1:
        return [f"트랙 길이 불일치(디싱크 가능, 인트로/아웃트로면 정상): "
                f"{lengths} tick — --strict 시 위반 처리"]
    return []


def check_tempo_placement(tracks: list[str]) -> list[str]:
    """t가 트랙 첫 음표 뒤면 warning(모바일 박자 어긋남 흔한 원인)."""
    w: list[str] = []
    for i, t in enumerate(tracks, 1):
        fn = re.search(r"[a-gA-Gr]", t)
        for tm in re.finditer(r"[tT]\d+", t):
            if fn and tm.start() > fn.start():
                w.append(f"트랙 {i}: 음표 뒤 템포({tm.group()}) — "
                         f"모바일 박자 어긋남 위험, 트랙 맨 앞 권장")
                break
    return w


def suggest_compression(track: str) -> list[str]:
    """글자수 절약 제안(텍스트만, 자동수정 안 함 — 위험)."""
    out: list[str] = []
    lengths = re.findall(r"[a-gA-G][+#-]?(\d+)", track)
    if lengths:
        from collections import Counter
        common, cnt = Counter(lengths).most_common(1)[0]
        if cnt >= 4:
            out.append(f"길이 {common} {cnt}회 — `l{common}` 기본길이로 절약")
    if "n" not in track.lower() and re.search(r"[oO]\d+|[<>]", track):
        out.append("`N` 명령으로 옥타브 명령 생략 가능 "
                    "(마비꼬 export 'N 명령 허용' 체크)")
    return out


def validate(mml: str, max_tracks: int = MAX_TRACKS,
             max_chars: int = MAX_CHARS_PER_PART, ppq: int = 480,
             strict: bool = False) -> dict:
    tracks = parse_tracks(mml)
    violations = check_limits(tracks, max_tracks, max_chars)
    warnings = check_desync(tracks, ppq) + check_tempo_placement(tracks)
    suggestions = [f"트랙 {i}: {s}"
                   for i, t in enumerate(tracks, 1)
                   for s in suggest_compression(t)]
    ok = not violations and (not warnings if strict else True)
    return {"ok": ok, "tracks": len(tracks), "violations": violations,
            "warnings": warnings, "suggestions": suggestions}


def _main(argv: list[str]) -> int:
    import argparse, json
    p = argparse.ArgumentParser(description="마비노기 모바일 MML 검증")
    p.add_argument("mml", help="MML 문자열 또는 @파일경로")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS_PER_PART)
    p.add_argument("--max-tracks", type=int, default=MAX_TRACKS)
    p.add_argument("--ppq", type=int, default=480)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    text = a.mml
    if text.startswith("@"):
        with open(text[1:], encoding="utf-8") as f:
            text = f.read().strip()
    rep = validate(text, a.max_tracks, a.max_chars, a.ppq, a.strict)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False))
    else:
        print("OK" if rep["ok"] else "FAIL")
        for x in rep["violations"]:
            print(f"  ✗ {x}")
        for x in rep["warnings"]:
            print(f"  ⚠ {x}")
        for x in rep["suggestions"]:
            print(f"  · {x}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
