import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from midi_to_mml import read_vlq


def _vlq(n: int) -> bytes:
    o = bytearray([n & 0x7F]); n >>= 7
    while n:
        o.insert(0, (n & 0x7F) | 0x80); n >>= 7
    return bytes(o)


def make_smf(ppq: int, events: list[tuple[int, bytes]], fmt: int = 0,
             ntrks: int = 1) -> bytes:
    """최소 SMF. events=[(delta, raw_event_bytes)]. EOT 자동 append."""
    trk = bytearray()
    for delta, ev in events:
        trk += _vlq(delta) + ev
    trk += _vlq(0) + b"\xFF\x2F\x00"
    head = b"MThd" + struct.pack(">IHHH", 6, fmt, ntrks, ppq)
    track = b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
    return head + track


def test_read_vlq_single_byte():
    assert read_vlq(b"\x40", 0) == (0x40, 1)

def test_read_vlq_multi_byte():
    assert read_vlq(b"\x81\x00", 0) == (128, 2)

def test_read_vlq_offset():
    assert read_vlq(b"\xFF\x81\x00", 1) == (128, 3)

from midi_to_mml import parse_header, split_tracks
import pytest

def test_parse_header_ok():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    assert parse_header(smf) == (0, 1, 480)

def test_parse_header_rejects_non_mthd():
    with pytest.raises(ValueError):
        parse_header(b"XXXX" + b"\x00"*10)

def test_parse_header_rejects_smpte_division():
    bad = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 0x8000) + b"MTrk\x00\x00\x00\x00"
    with pytest.raises(ValueError):
        parse_header(bad)

def test_parse_header_rejects_zero_division():
    bad = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 0) + b"MTrk\x00\x00\x00\x00"
    with pytest.raises(ValueError):
        parse_header(bad)

def test_split_tracks_one_chunk():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    chunks = split_tracks(smf)
    assert len(chunks) == 1 and chunks[0].endswith(b"\xFF\x2F\x00")

def test_split_tracks_raises_on_truncation():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    with pytest.raises(ValueError):
        split_tracks(smf[:-3])

def test_split_tracks_raises_on_ntrks_mismatch():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")],
                   ntrks=2)
    with pytest.raises(ValueError):
        split_tracks(smf)

from midi_to_mml import extract_notes

def test_extract_single_note_and_clean_stats():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    notes, stats = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 480, 60)]
    assert stats == {"unmatched_on": 0, "unmatched_off": 0,
                     "skipped_events": 0}

def test_vel0_noteon_is_off():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (240, b"\x90\x3C\x00")])
    notes, _ = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 240, 60)]

def test_running_status():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (0, b"\x3E\x40"),
                         (480, b"\x80\x3C\x40"), (0, b"\x3E\x40")])
    notes, _ = extract_notes(split_tracks(smf)[0])
    assert sorted(notes) == [(0, 480, 60), (0, 480, 62)]

def test_meta_and_sysex_skipped_counted():
    smf = make_smf(480, [
        (0, b"\xFF\x51\x03\x07\xA1\x20"),
        (0, b"\xF0\x02\x11\xF7"),
        (0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    notes, stats = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 480, 60)]
    assert stats["skipped_events"] >= 2

def test_unmatched_note_on_counted():
    smf = make_smf(480, [(0, b"\x90\x3C\x40")])
    notes, stats = extract_notes(split_tracks(smf)[0])
    assert notes == [] and stats["unmatched_on"] == 1

def test_extract_notes_raises_on_internally_truncated_chunk():
    # delta=0, note-on status+pitch but velocity byte missing (chunk ends)
    with pytest.raises(ValueError):
        extract_notes(b"\x00\x90\x3C")


from midi_to_mml import ticks_to_length

def test_quarter_zero_error():
    assert ticks_to_length(480, 480) == ("4", 0)

def test_eighth_zero_error():
    assert ticks_to_length(240, 480) == ("8", 0)

def test_dotted_quarter():
    assert ticks_to_length(720, 480) == ("4.", 0)

def test_near_value_snaps_with_error():
    s, err = ticks_to_length(470, 480)
    assert s == "4" and err == 10

def test_triplet_eighth_reports_error():
    s, err = ticks_to_length(160, 480)
    assert err > 0


from midi_to_mml import midi_note_to_token

def test_c4_no_shift():
    assert midi_note_to_token(60, 4) == ("c", 4)

def test_sharp():
    assert midi_note_to_token(61, 4) == ("c+", 4)

def test_octave_up():
    assert midi_note_to_token(72, 4) == ("<c", 5)

def test_octave_down_two():
    assert midi_note_to_token(36, 4) == (">>c", 2)


from midi_to_mml import quantization_error

def test_quantization_error_zero_for_aligned():
    assert quantization_error([(0,480,60),(480,240,62)], 480) == 0

def test_quantization_error_positive_for_triplet():
    assert quantization_error([(0,160,60)], 480) > 0


from midi_to_mml import reduce_polyphony

def _monophonic(notes):
    s = sorted(notes)
    return all(s[i][0] + s[i][1] <= s[i+1][0] for i in range(len(s)-1))

def test_highest_at_same_start():
    out = reduce_polyphony([(0,480,60),(0,480,64),(0,480,67),(480,240,62)])
    assert out == [(0,480,67),(480,240,62)]

def test_monophonic_unchanged():
    n = [(0,240,60),(240,240,62)]
    assert reduce_polyphony(n) == n

def test_invariant_output_is_monophonic():
    n = [(0,480,60),(120,480,64),(300,200,67),(900,480,62)]
    assert _monophonic(reduce_polyphony(n))

def test_invariant_no_zero_or_negative_duration():
    out = reduce_polyphony([(0,480,60),(240,480,64)])
    assert all(d > 0 for _, d, _ in out)


from midi_to_mml import notes_to_mml
from validate_mml import track_tick_length

def test_basic_sequence():
    out = notes_to_mml([(0,480,60),(480,480,62),(960,480,64)], 480)
    assert "c" in out and "d" in out and "e" in out and "," not in out

def test_rest_for_gap():
    assert "r" in notes_to_mml([(0,480,60),(960,480,62)], 480)

def test_empty():
    assert notes_to_mml([], 480) == ""

def test_invariant_round_trip_tick_length():
    notes = [(0,480,60),(480,240,62),(960,480,64)]
    span = 960 + 480
    assert track_tick_length(notes_to_mml(notes, 480), 480) == span


from midi_to_mml import convert, midi_to_mml

def test_convert_returns_mml_and_report(tmp_path):
    smf = make_smf(480, [(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")])
    p = tmp_path/"a.mid"; p.write_bytes(smf)
    r = convert(str(p))
    assert r["mml"].startswith("MML@") and r["mml"].endswith(";")
    assert set(r["report"]) >= {"skipped_chunks","unmatched","quant_error",
                                "tracks_used","tracks_dropped"}

def test_convert_caps_and_reports_dropped_tracks(tmp_path):
    body = _vlq(0)+b"\x90\x3C\x40"+_vlq(480)+b"\x80\x3C\x40"+_vlq(0)+b"\xFF\x2F\x00"
    chunk = b"MTrk"+struct.pack(">I",len(body))+body
    smf = b"MThd"+struct.pack(">IHHH",6,1,8,480)+chunk*8
    p = tmp_path/"m.mid"; p.write_bytes(smf)
    r = convert(str(p), max_tracks=6)
    assert r["mml"].count(",") == 5
    assert r["report"]["tracks_used"] == 6
    assert r["report"]["tracks_dropped"] == 2

def test_midi_to_mml_returns_only_mml(tmp_path):
    smf = make_smf(480, [(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")])
    p = tmp_path/"b.mid"; p.write_bytes(smf)
    assert midi_to_mml(str(p)).startswith("MML@")

def test_cli_prints_mml_stdout(tmp_path):
    smf = make_smf(480, [(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")])
    p = tmp_path/"c.mid"; p.write_bytes(smf)
    import subprocess
    out = subprocess.run(["python3","scripts/midi_to_mml.py",str(p)],
        cwd=os.path.join(os.path.dirname(__file__),".."),
        capture_output=True,text=True)
    assert out.returncode == 0 and out.stdout.strip().startswith("MML@")


def test_convert_reports_polyphony_dropped(tmp_path):
    # 한 트랙에 동시 3음(60,64,67) → reduce_polyphony가 2음 버림
    body = (_vlq(0)+b"\x90\x3C\x40" + _vlq(0)+b"\x90\x40\x40" + _vlq(0)+b"\x90\x43\x40"
            + _vlq(480)+b"\x80\x3C\x40" + _vlq(0)+b"\x80\x40\x40" + _vlq(0)+b"\x80\x43\x40"
            + _vlq(0)+b"\xFF\x2F\x00")
    chunk = b"MTrk"+struct.pack(">I",len(body))+body
    smf = b"MThd"+struct.pack(">IHHH",6,0,1,480)+chunk
    p = tmp_path/"poly.mid"; p.write_bytes(smf)
    r = convert(str(p))
    assert r["report"]["notes_dropped_polyphony"] == 2


def test_cli_corrupt_midi_clean_error(tmp_path):
    bad = tmp_path/"bad.mid"; bad.write_bytes(b"NOT A MIDI FILE")
    import subprocess
    out = subprocess.run(["python3","scripts/midi_to_mml.py",str(bad)],
        cwd=os.path.join(os.path.dirname(__file__),".."),
        capture_output=True, text=True)
    assert out.returncode == 2
    assert "Traceback" not in out.stderr


def test_convert_format1_multitrack_with_meta(tmp_path):
    def mk(track_bytes):
        return b"MTrk"+struct.pack(">I",len(track_bytes))+track_bytes
    t1 = (_vlq(0)+b"\xFF\x51\x03\x07\xA1\x20"            # tempo meta
          + _vlq(0)+b"\x90\x3C\x40" + _vlq(480)+b"\x80\x3C\x40"
          + _vlq(0)+b"\xFF\x2F\x00")
    t2 = (_vlq(0)+b"\x90\x40\x40" + _vlq(480)+b"\x80\x40\x40"
          + _vlq(0)+b"\xFF\x2F\x00")
    smf = b"MThd"+struct.pack(">IHHH",6,1,2,480)+mk(t1)+mk(t2)
    p = tmp_path/"f1.mid"; p.write_bytes(smf)
    r = convert(str(p))
    assert r["mml"].startswith("MML@") and r["mml"].count(",") == 1  # 2 tracks
    assert r["report"]["tracks_used"] == 2
    assert r["report"]["skipped_chunks"] == 0
    assert r["report"]["unmatched"] == {"unmatched_on":0,"unmatched_off":0,"skipped_events":1}
