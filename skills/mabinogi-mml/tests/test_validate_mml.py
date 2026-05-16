import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from validate_mml import parse_tracks

def test_parse_tracks_splits_on_comma_strips_wrapper():
    assert parse_tracks("MML@cde,fga,bb;") == ["cde", "fga", "bb"]

def test_parse_tracks_single_track_no_wrapper():
    assert parse_tracks("cdefg") == ["cdefg"]

def test_parse_tracks_trailing_empty_tracks_kept():
    assert parse_tracks("MML@cde,,;") == ["cde", "", ""]
