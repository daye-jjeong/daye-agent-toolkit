import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from collect import _collect_from_conn


def _create_test_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema_path = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp" / "schema.sql"
    conn.executescript(schema_path.read_text())
    return conn


class _CollectHelper:
    def __init__(self):
        self.conn = _create_test_db()

    def __call__(self, dates=None, period_start=None, period_end=None):
        dates = dates or []
        start = period_start or (dates[0] if dates else "2026-03-01")
        end = period_end or (dates[-1] if dates else "2026-03-01")
        return _collect_from_conn(self.conn, start, end, project_roots=[])


@pytest.fixture
def collect_with_db():
    helper = _CollectHelper()
    yield helper
    helper.conn.close()
