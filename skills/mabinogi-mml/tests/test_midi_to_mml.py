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
