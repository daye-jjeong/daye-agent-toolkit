#!/usr/bin/env python3
"""Reddit hot posts alert — AI subreddits.

Fetches hot posts from configured AI subreddits via Reddit JSON API,
filters by upvote threshold, deduplicates, and outputs Telegram alerts.

Uses Reddit's hot ranking algorithm (time decay + engagement) as the
primary signal, with a minimum upvote floor to filter noise.

Designed for 2-hour cron: 0 */2 * * *

Usage:
  python3 reddit-hot.py --subs references/reddit-hot-subs.txt --dry-run
  python3 reddit-hot.py --subs references/reddit-hot-subs.txt --min-ups 100
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import subprocess
from pathlib import Path

CACHE_DIR = Path(os.path.expanduser("~/.cache/news-brief"))
SEEN_FILE = CACHE_DIR / "reddit-hot-seen.json"
PRUNE_HOURS = 48
DEFAULT_MIN_UPS = 50
MAX_PER_SUB = 3
MAX_TOTAL = 10
FETCH_LIMIT = 15
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36")


def load_subs(path: str) -> list[str]:
    """Load subreddit names from text file."""
    subs: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # normalize: strip leading r/ if present
            sub = line[2:] if line.startswith("r/") else line
            subs.append(sub)
    return subs


def load_seen() -> dict[str, float]:
    if not SEEN_FILE.exists():
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict[str, float]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2)


def prune_seen(seen: dict[str, float]) -> dict[str, float]:
    cutoff = time.time() - (PRUNE_HOURS * 3600)
    return {url: ts for url, ts in seen.items() if ts > cutoff}


def fetch_hot(sub: str) -> list[dict]:
    """Fetch hot posts from a subreddit via Reddit JSON API (curl)."""
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={FETCH_LIMIT}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", "-H", f"User-Agent: {USER_AGENT}", url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            print(f"  skip r/{sub}: curl exit {result.returncode}", file=sys.stderr)
            return []
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        print(f"  skip r/{sub}: {e}", file=sys.stderr)
        return []

    posts: list[dict] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        if d.get("stickied"):
            continue
        posts.append({
            "title": d.get("title", ""),
            "url": f"https://reddit.com{d.get('permalink', '')}",
            "ups": d.get("ups", 0),
            "comments": d.get("num_comments", 0),
            "sub": sub,
            "created": d.get("created_utc", 0),
        })
    return posts


def format_telegram(post: dict) -> str:
    ups = post["ups"]
    comments = post["comments"]
    title = post["title"]
    sub = post["sub"]
    url = post["url"]
    return f"🔥 r/{sub} | ⬆{ups} 💬{comments}\n{title}\n{url}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Reddit hot posts alert")
    ap.add_argument("--subs", required=True, help="Subreddits text file")
    ap.add_argument("--min-ups", type=int, default=DEFAULT_MIN_UPS,
                    help=f"Minimum upvotes (default: {DEFAULT_MIN_UPS})")
    ap.add_argument("--max-per-sub", type=int, default=MAX_PER_SUB,
                    help=f"Max alerts per subreddit (default: {MAX_PER_SUB})")
    ap.add_argument("--max-total", type=int, default=MAX_TOTAL,
                    help=f"Max total alerts (default: {MAX_TOTAL})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print alerts but don't update seen cache")
    args = ap.parse_args()

    subs = load_subs(args.subs)
    if not subs:
        print("Error: no subreddits loaded", file=sys.stderr)
        sys.exit(1)

    seen = prune_seen(load_seen())
    all_posts: list[dict] = []

    for sub in subs:
        posts = fetch_hot(sub)
        sub_count = 0
        for p in posts:
            if p["url"] in seen:
                continue
            if p["ups"] < args.min_ups:
                continue
            all_posts.append(p)
            sub_count += 1
            if sub_count >= args.max_per_sub:
                break

    # Sort by upvotes desc, cap total
    all_posts.sort(key=lambda x: x["ups"], reverse=True)
    all_posts = all_posts[:args.max_total]

    if not all_posts:
        if args.dry_run:
            print("(dry-run) No hot posts above threshold", file=sys.stderr)
        return

    for post in all_posts:
        print(format_telegram(post))
        print()

    if not args.dry_run:
        now = time.time()
        for post in all_posts:
            seen[post["url"]] = now
        save_seen(seen)
        print(f"({len(all_posts)} alerts sent, cache updated)", file=sys.stderr)
    else:
        print(f"(dry-run) {len(all_posts)} alerts would be sent", file=sys.stderr)


if __name__ == "__main__":
    main()
