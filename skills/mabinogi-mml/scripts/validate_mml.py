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
