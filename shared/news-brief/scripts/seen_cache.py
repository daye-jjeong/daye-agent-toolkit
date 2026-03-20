"""Shared seen-cache for news-brief alert scripts (dedup)."""

from __future__ import annotations

import json
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "news-brief"
DEFAULT_PRUNE_HOURS = 48


def load_seen(seen_file: Path) -> dict[str, float]:
    if not seen_file.exists():
        return {}
    try:
        with open(seen_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict[str, float], seen_file: Path) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(seen_file, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2)


def prune_seen(
    seen: dict[str, float], prune_hours: int = DEFAULT_PRUNE_HOURS
) -> dict[str, float]:
    cutoff = time.time() - (prune_hours * 3600)
    return {url: ts for url, ts in seen.items() if ts > cutoff}
