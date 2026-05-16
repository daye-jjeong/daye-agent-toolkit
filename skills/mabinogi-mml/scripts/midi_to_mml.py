"""MIDI(SMF) → 마비노기 모바일 MML (+변환 손실 리포트). stdlib only.
손상/비표준 입력은 조용히 통과시키지 않고 ValueError 또는 리포트로 노출한다."""
import struct

MAX_TRACKS = 6
MIDI_C4 = 60
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}
OCTAVE_UP, OCTAVE_DOWN = "<", ">"

_LEN_TABLE: list[tuple[float, str]] = []
for _b in (1, 2, 4, 8, 16, 32, 64):
    _LEN_TABLE.append((4.0 / _b, str(_b)))
    _LEN_TABLE.append((4.0 / _b * 1.5, f"{_b}."))


_PITCH = {0:"c",1:"c+",2:"d",3:"d+",4:"e",5:"f",
          6:"f+",7:"g",8:"g+",9:"a",10:"a+",11:"b"}


def midi_note_to_token(pitch: int, cur_oct: int) -> tuple[str, int]:
    """MIDI 음 → (MML 토큰, 새 옥타브). MIDI60=o4 c. OCTAVE_UP/DOWN 사용."""
    octave = (pitch - MIDI_C4) // 12 + 4
    name = _PITCH[(pitch - MIDI_C4) % 12]
    diff = octave - cur_oct
    shift = OCTAVE_UP*diff if diff > 0 else OCTAVE_DOWN*(-diff) if diff < 0 else ""
    return shift + name, octave


def ticks_to_length(ticks: int, ppq: int = 480) -> tuple[str, int]:
    """tick → (가장 가까운 MML 길이, 양자화 오차 tick절댓값)."""
    quarters = ticks / ppq
    val, label = min(_LEN_TABLE, key=lambda c: abs(c[0] - quarters))
    err = abs(round(val * ppq) - ticks)
    return label, err


def reduce_polyphony(
    notes: list[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    """겹치는 음을 단선율로 축약 (마비노기 트랙은 모노포닉).
    in/out: [(start_tick,dur_tick,midi_pitch)].
    불변식(테스트 강제): 출력은 구간 비겹침, dur>0.
    정책 결정 — 기본 권장: 동시/겹침 시 최고음, 가린 앞음은 절단, 0길이 제거.
    """
    if not notes:
        return []
    notes = sorted(notes)
    result: list[tuple[int, int, int]] = []
    i, n = 0, len(notes)
    while i < n:
        start = notes[i][0]
        j = i
        best = notes[i]
        while j < n and notes[j][0] == start:
            if notes[j][2] > best[2]:
                best = notes[j]
            j += 1
        _, dur, pitch = best
        next_start = notes[j][0] if j < n else None
        if next_start is not None and start + dur > next_start:
            dur = next_start - start
        if dur > 0:
            result.append((start, dur, pitch))
        i = j
    return result


def notes_to_mml(notes: list[tuple[int, int, int]], ppq: int = 480) -> str:
    """단선율 → MML 트랙. 공백은 rest로 채움.
    불변식(테스트 강제): track_tick_length(반환) == 음표+gap 총 tick.
    옥타브/기본길이 전략 = 사용자 기여. 기본 권장: 상대 <> + 최빈 l.
    helper: midi_note_to_token, ticks_to_length(라벨만 사용).
    """
    if not notes:
        return ""
    notes = sorted(notes)
    out: list[str] = []
    cur_oct = MABI_DEFAULTS["o"]
    cursor = 0
    for start, dur, pitch in notes:
        gap = start - cursor
        if gap > 0:
            out.append("r" + ticks_to_length(gap, ppq)[0])
        token, cur_oct = midi_note_to_token(pitch, cur_oct)
        out.append(token + ticks_to_length(dur, ppq)[0])
        cursor = start + dur
    return "".join(out)


def quantization_error(notes: list[tuple[int, int, int]],
                       ppq: int = 480) -> int:
    """각 음표 duration 양자화 오차 합(tick). 변환 손실 리포트용."""
    return sum(ticks_to_length(d, ppq)[1] for _, d, _ in notes)


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
    if division == 0:
        raise ValueError("division 0 — 손상 헤더")
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
    """트랙 청크 → ([(start,dur,pitch)], stats). 손실 통계 명시.
    이벤트 도중 절단(범위 초과)은 fail-closed ValueError로 노출."""
    try:
        return _extract_notes(chunk)
    except IndexError:
        raise ValueError("트랙 청크가 이벤트 도중 절단됨 — 손상 파일")


def _extract_notes(chunk: bytes) -> tuple[list[tuple[int, int, int]], dict]:
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
