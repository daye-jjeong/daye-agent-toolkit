#!/usr/bin/env python3
"""Reddit hot posts alert — AI subreddits.

Fetches hot posts from configured AI subreddits via Reddit JSON API,
filters by upvote threshold, deduplicates, and outputs rich digest
including post body and top comments for LLM summarization.

Uses Reddit's hot ranking algorithm (time decay + engagement) as the
primary signal, with a minimum upvote floor to filter noise.

Designed for daily cron: 0 18 * * *

Usage:
  python3 reddit-hot.py --subs references/reddit-hot-subs.txt --dry-run
  python3 reddit-hot.py --subs references/reddit-hot-subs.txt --min-ups 100
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seen_cache import CACHE_DIR, load_seen, save_seen, prune_seen

SEEN_FILE = CACHE_DIR / "reddit-hot-seen.json"
DEFAULT_MIN_UPS = 50
MAX_PER_SUB = 3
MAX_TOTAL = 10
FETCH_LIMIT = 15
TOP_COMMENTS = 3
SELFTEXT_MAX = 500
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36")


def _curl(url: str, timeout: int = 15) -> dict | None:
    """Fetch JSON from URL via curl. Returns parsed dict or None."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", "-H", f"User-Agent: {USER_AGENT}", url],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def load_subs(path: str) -> list[str]:
    """Load subreddit names from text file."""
    subs: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sub = line[2:] if line.startswith("r/") else line
            subs.append(sub)
    return subs


def fetch_hot(sub: str) -> list[dict]:
    """Fetch hot posts from a subreddit. Includes selftext."""
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={FETCH_LIMIT}"
    data = _curl(url)
    if not data:
        print(f"  skip r/{sub}", file=sys.stderr)
        return []

    posts: list[dict] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        if d.get("stickied"):
            continue
        selftext = html.unescape(d.get("selftext", "") or "").strip()
        if len(selftext) > SELFTEXT_MAX:
            selftext = selftext[:SELFTEXT_MAX] + "…"
        posts.append({
            "title": d.get("title", ""),
            "url": f"https://reddit.com{d.get('permalink', '')}",
            "ups": d.get("ups", 0),
            "num_comments": d.get("num_comments", 0),
            "sub": sub,
            "selftext": selftext,
            "is_self": d.get("is_self", False),
            "link_url": d.get("url", ""),
        })
    return posts


def fetch_top_comments(post: dict) -> list[dict]:
    """Fetch top N comments for a post."""
    permalink = post["url"].replace("https://reddit.com", "")
    url = f"https://www.reddit.com{permalink}.json?limit={TOP_COMMENTS}&sort=top"
    data = _curl(url)
    if not data or not isinstance(data, list) or len(data) < 2:
        return []

    comments: list[dict] = []
    for child in data[1].get("data", {}).get("children", []):
        if child.get("kind") == "more":
            continue
        cd = child.get("data", {})
        body = html.unescape(cd.get("body", "") or "").strip()
        if len(body) > 300:
            body = body[:300] + "…"
        comments.append({
            "author": cd.get("author", "[deleted]"),
            "score": cd.get("score", 0),
            "body": body,
        })
        if len(comments) >= TOP_COMMENTS:
            break
    return comments


def format_post(post: dict) -> str:
    """Format a post with body and comments for LLM digest."""
    lines = [
        f"## r/{post['sub']} | ⬆{post['ups']} 💬{post['num_comments']}",
        f"**{post['title']}**",
        post["url"],
    ]

    if post["selftext"]:
        lines.append(f"\n{post['selftext']}")
    elif not post["is_self"] and post["link_url"]:
        lines.append(f"(링크: {post['link_url']})")

    if post.get("top_comments"):
        lines.append("\n**Top comments:**")
        for c in post["top_comments"]:
            lines.append(f"- u/{c['author']} (⬆{c['score']}): {c['body']}")

    return "\n".join(lines)


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

    seen = prune_seen(load_seen(SEEN_FILE))

    # Phase 1: Fetch hot posts from all subreddits in parallel
    with ThreadPoolExecutor(max_workers=len(subs)) as pool:
        results = list(pool.map(fetch_hot, subs))

    all_posts: list[dict] = []
    for posts in results:
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

    all_posts.sort(key=lambda x: x["ups"], reverse=True)
    all_posts = all_posts[:args.max_total]

    if not all_posts:
        if args.dry_run:
            print("(dry-run) No hot posts above threshold", file=sys.stderr)
        return

    # Phase 2: Fetch top comments for selected posts in parallel
    with ThreadPoolExecutor(max_workers=len(all_posts)) as pool:
        comment_results = list(pool.map(fetch_top_comments, all_posts))
    for post, comments in zip(all_posts, comment_results):
        post["top_comments"] = comments

    # Output
    print(f"# Reddit Hot — AI 서브레딧 ({len(all_posts)}개 포스트)\n")
    for post in all_posts:
        print(format_post(post))
        print("\n---\n")

    if not args.dry_run:
        now = time.time()
        for post in all_posts:
            seen[post["url"]] = now
        save_seen(seen, SEEN_FILE)
        print(f"({len(all_posts)} posts, cache updated)", file=sys.stderr)
    else:
        print(f"(dry-run) {len(all_posts)} posts", file=sys.stderr)


if __name__ == "__main__":
    main()
