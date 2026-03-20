#!/usr/bin/env python3
"""Reddit CC/OpenClaw showcase — usage examples and workflows.

Searches Reddit for Claude Code and OpenClaw usage showcases,
filters by upvotes and content quality, fetches top comments,
and outputs a rich digest for LLM summarization.

Uses Reddit search API with multiple configurable queries.

Usage:
  python3 reddit-cc-showcase.py --queries references/cc-showcase-queries.txt
  python3 reddit-cc-showcase.py --queries references/cc-showcase-queries.txt --time week --dry-run
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seen_cache import CACHE_DIR, load_seen, save_seen, prune_seen

SEEN_FILE = CACHE_DIR / "cc-showcase-seen.json"
DEFAULT_MIN_UPS = 50
MAX_TOTAL = 10
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


def load_queries(path: str) -> list[dict]:
    """Load search queries from text file.

    Format: query | subreddit (subreddit optional)
    """
    queries: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            q: dict = {"query": parts[0]}
            if len(parts) > 1 and parts[1]:
                q["subreddit"] = parts[1]
            queries.append(q)
    return queries


def search_reddit(query: str, subreddit: str | None = None,
                  sort: str = "top", time_filter: str = "week",
                  limit: int = 10) -> list[dict]:
    """Search Reddit via JSON API."""
    encoded = urllib.parse.quote(query)
    if subreddit:
        url = (f"https://www.reddit.com/r/{subreddit}/search.json"
               f"?q={encoded}&restrict_sr=on&sort={sort}"
               f"&t={time_filter}&limit={limit}")
    else:
        url = (f"https://www.reddit.com/search.json"
               f"?q={encoded}&sort={sort}"
               f"&t={time_filter}&limit={limit}")

    data = _curl(url)
    if not data:
        print(f"  skip query: {query}", file=sys.stderr)
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
            "sub": d.get("subreddit", ""),
            "selftext": selftext,
            "is_self": d.get("is_self", False),
            "link_url": d.get("url", ""),
        })
    return posts


def fetch_top_comments(post: dict) -> list[dict]:
    """Fetch top N comments for a post."""
    permalink = post["url"].replace("https://reddit.com", "")
    url = (f"https://www.reddit.com{permalink}.json"
           f"?limit={TOP_COMMENTS}&sort=top")
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
    ap = argparse.ArgumentParser(
        description="Reddit CC/OpenClaw showcase search")
    ap.add_argument("--queries", required=True,
                    help="Queries text file")
    ap.add_argument("--min-ups", type=int, default=DEFAULT_MIN_UPS,
                    help=f"Minimum upvotes (default: {DEFAULT_MIN_UPS})")
    ap.add_argument("--max-total", type=int, default=MAX_TOTAL,
                    help=f"Max total results (default: {MAX_TOTAL})")
    ap.add_argument("--time", default="week",
                    choices=["hour", "day", "week", "month", "year", "all"],
                    help="Time range (default: week)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print results but don't update seen cache")
    args = ap.parse_args()

    queries = load_queries(args.queries)
    if not queries:
        print("Error: no queries loaded", file=sys.stderr)
        sys.exit(1)

    seen = prune_seen(load_seen(SEEN_FILE), prune_hours=168)  # 7 days

    # Phase 1: Search all queries in parallel
    def do_search(q: dict) -> list[dict]:
        time.sleep(0.5)  # rate limit courtesy
        return search_reddit(
            q["query"], q.get("subreddit"),
            sort="top", time_filter=args.time, limit=10,
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(do_search, queries))

    # Deduplicate by URL, filter by upvotes
    url_seen: set[str] = set()
    all_posts: list[dict] = []
    for posts in results:
        for p in posts:
            if p["url"] in url_seen or p["url"] in seen:
                continue
            if p["ups"] < args.min_ups:
                continue
            url_seen.add(p["url"])
            all_posts.append(p)

    all_posts.sort(key=lambda x: x["ups"], reverse=True)
    all_posts = all_posts[:args.max_total]

    if not all_posts:
        if args.dry_run:
            print("(dry-run) No showcase posts above threshold",
                  file=sys.stderr)
        return

    # Phase 2: Fetch top comments in parallel
    with ThreadPoolExecutor(max_workers=min(len(all_posts), 5)) as pool:
        comment_results = list(pool.map(fetch_top_comments, all_posts))
    for post, comments in zip(all_posts, comment_results):
        post["top_comments"] = comments

    # Output
    print(f"# CC/OpenClaw Showcase ({len(all_posts)}개 포스트)\n")
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
