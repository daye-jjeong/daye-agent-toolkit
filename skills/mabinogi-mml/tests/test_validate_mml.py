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
