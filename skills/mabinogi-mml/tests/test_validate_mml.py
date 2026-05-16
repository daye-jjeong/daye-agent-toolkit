import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from validate_mml import parse_tracks

def test_parse_tracks_splits_on_comma_strips_wrapper():
    assert parse_tracks("MML@cde,fga,bb;") == ["cde", "fga", "bb"]

def test_parse_tracks_single_track_no_wrapper():
    assert parse_tracks("cdefg") == ["cdefg"]

def test_parse_tracks_trailing_empty_tracks_kept():
    assert parse_tracks("MML@cde,,;") == ["cde", "", ""]

from validate_mml import check_limits

def test_check_limits_ok():
    assert check_limits(["abc", "def"], 6, 1200) == []

def test_check_limits_too_many_tracks():
    assert any("트랙" in m and "7" in m for m in check_limits(["a"]*7, 6, 1200))

def test_check_limits_char_overflow_reports_index():
    v = check_limits(["x"*1201, "ok"], 6, 1200)
    assert any("트랙 1" in m and "1201" in m for m in v)
    assert not any("트랙 2" in m for m in v)

from validate_mml import track_tick_length, check_desync

def test_tick_length_quarter_default_l4():
    assert track_tick_length("cdef", 480) == 4*480

def test_tick_length_explicit_and_rest():
    assert track_tick_length("c8r4e2", 480) == 240+480+960

def test_tick_length_dotted():
    assert track_tick_length("c4.", 480) == 720

def test_tick_length_N_command_counts_as_default_length_note():
    assert track_tick_length("n60n62", 480) == 2*480

def test_tick_length_N_command_respects_l_default():
    assert track_tick_length("l8n60n62", 480) == 2*240

def test_check_desync_returns_warning_on_mismatch():
    w = check_desync(["cdef", "cde"], 480)
    assert w and ("디싱크" in w[0] or "길이" in w[0])

def test_check_desync_empty_when_equal():
    assert check_desync(["cdef", "cdef"], 480) == []

from validate_mml import check_tempo_placement, suggest_compression

def test_tempo_mid_track_warns():
    assert any("트랙 2" in m and "템포" in m
               for m in check_tempo_placement(["t120cdef", "cdt140ef"]))

def test_tempo_at_start_ok():
    assert check_tempo_placement(["t120cdef", "t120cdef"]) == []

def test_suggest_compression_repeated_length():
    assert any("l8" in x for x in suggest_compression("c8d8e8f8g8a8"))

def test_suggest_compression_clean_no_suggestion():
    assert suggest_compression("l4cdef") == []
