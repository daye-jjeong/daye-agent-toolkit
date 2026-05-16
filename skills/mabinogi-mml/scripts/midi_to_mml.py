"""MIDI(SMF) → 마비노기 모바일 MML (+변환 손실 리포트). stdlib only.
손상/비표준 입력은 조용히 통과시키지 않고 ValueError 또는 리포트로 노출한다."""
import struct

MAX_TRACKS = 6
MIDI_C4 = 60
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}
OCTAVE_UP, OCTAVE_DOWN = "<", ">"


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    """가변길이 수량 → (value, next_pos)."""
    value = 0
    while True:
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            return value, pos
