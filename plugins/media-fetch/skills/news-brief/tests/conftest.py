"""Pytest configuration for news-brief tests."""

import sys
from pathlib import Path

# Add scripts directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
