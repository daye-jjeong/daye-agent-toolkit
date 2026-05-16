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


def parse_header(data: bytes) -> tuple[int, int, int]:
    """MThd 검증·파싱 → (format, ntrks, division). 비표준은 ValueError."""
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("MThd 청크 없음 — 유효한 SMF 아님")
    length, fmt, ntrks, division = struct.unpack(">IHHH", data[4:14])
    if length != 6:
        raise ValueError(f"MThd 길이 {length} ≠ 6 — 손상 의심")
    if fmt not in (0, 1, 2):
        raise ValueError(f"미지원 SMF format {fmt}")
    if division & 0x8000:
        raise ValueError("SMPTE division 미지원 (PPQ 형식만)")
    return fmt, ntrks, division


def split_tracks(data: bytes) -> list[bytes]:
    """MTrk 본문 리스트. 선언 ntrks와 불일치하거나 절단되면 ValueError."""
    _, ntrks, _ = parse_header(data)
    chunks: list[bytes] = []
    pos = 14
    while pos < len(data):
        if data[pos:pos + 4] != b"MTrk":
            raise ValueError(f"오프셋 {pos}: MTrk 아닌 청크 — 손상/미지원")
        (length,) = struct.unpack(">I", data[pos + 4:pos + 8])
        end = pos + 8 + length
        if end > len(data):
            raise ValueError("MTrk 본문 절단 — 손상 파일")
        chunks.append(data[pos + 8:end])
        pos = end
    if len(chunks) != ntrks:
        raise ValueError(f"MTrk 수 {len(chunks)} ≠ 헤더 선언 {ntrks}")
    return chunks


def extract_notes(chunk: bytes) -> tuple[list[tuple[int, int, int]], dict]:
    """트랙 청크 → ([(start,dur,pitch)], stats). 손실 통계 명시."""
    pos = abs_tick = status = 0
    pending: dict[int, list[int]] = {}
    notes: list[tuple[int, int, int]] = []
    stats = {"unmatched_on": 0, "unmatched_off": 0, "skipped_events": 0}
    n = len(chunk)
    while pos < n:
        delta, pos = read_vlq(chunk, pos)
        abs_tick += delta
        b = chunk[pos]
        if b & 0x80:
            status = b
            pos += 1
        ev = status & 0xF0
        if ev in (0x80, 0x90):
            pitch, vel = chunk[pos], chunk[pos + 1]
            pos += 2
            if ev == 0x90 and vel > 0:
                pending.setdefault(pitch, []).append(abs_tick)
            else:
                if pending.get(pitch):
                    start = pending[pitch].pop(0)
                    notes.append((start, abs_tick - start, pitch))
                else:
                    stats["unmatched_off"] += 1
        elif ev in (0xA0, 0xB0, 0xE0):
            pos += 2
            stats["skipped_events"] += 1
        elif ev in (0xC0, 0xD0):
            pos += 1
            stats["skipped_events"] += 1
        elif status == 0xFF:
            mtype = chunk[pos]
            pos += 1
            mlen, pos = read_vlq(chunk, pos)
            pos += mlen
            if mtype == 0x2F:
                break  # EOT는 구조 마커 — 변환 손실 아니므로 skipped 제외
            stats["skipped_events"] += 1
        elif status in (0xF0, 0xF7):
            slen, pos = read_vlq(chunk, pos)
            pos += slen
            stats["skipped_events"] += 1
        else:
            raise ValueError(f"미지원 상태 바이트 {status:#x} @ {pos}")
    stats["unmatched_on"] = sum(len(v) for v in pending.values())
    return notes, stats
