#!/usr/bin/env python3
"""KST (Korea Standard Time, UTC+9) date utilities for news-brief.

Shared by news_brief.py, compose-newspaper.py, breaking-alert.py.
stdlib only — no external packages.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

KST = timezone(timedelta(hours=9))
KST_FMT = "%Y-%m-%d %H:%M KST"


def parse_pub_date(raw: str | None) -> datetime | None:
    """Parse RSS published/updated date string.

    Handles RFC 2822 (most RSS), ISO 8601 (Atom), and plain date.
    Always returns a timezone-aware datetime (defaults to UTC if no tz info).
    """
    if not raw:
        return None
    # RFC 2822 (most RSS feeds)
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        pass
    # ISO 8601 variants
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def to_kst(dt: datetime) -> datetime:
    """Convert a timezone-aware datetime to KST."""
    return dt.astimezone(KST)


def format_kst(dt: datetime) -> str:
    """Format a timezone-aware datetime as '2026-02-21 18:30 KST'."""
    return to_kst(dt).strftime(KST_FMT)


def format_pub_kst(raw: str | None) -> str:
    """Parse a raw date string and return KST-formatted string.

    Returns the original string (or empty) if parsing fails.
    """
    dt = parse_pub_date(raw)
    if dt is None:
        return raw or ""
    return format_kst(dt)


def extract_domain(url: str) -> str:
    """Extract domain from URL, stripping 'www.' prefix.

    Returns the input as-is if not a valid HTTP(S) URL.
    """
    if not url or not url.startswith("http"):
        return url
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url
