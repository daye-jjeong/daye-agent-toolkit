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
