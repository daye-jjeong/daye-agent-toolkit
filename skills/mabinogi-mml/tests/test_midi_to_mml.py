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
