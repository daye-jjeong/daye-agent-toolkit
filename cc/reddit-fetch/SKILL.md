---
name: reddit-fetch
description: Use when needing to read or search Reddit. Fetches posts/comments via Reddit JSON API, and searches Reddit by keyword with optional subreddit filtering. Use this instead of WebFetch for all Reddit access.
---

# Reddit Fetch & Search

Read Reddit posts and search Reddit — bypasses bot blocking via Reddit JSON API.

## 1. Fetch a Post

```bash
{baseDir}/scripts/fetch.sh "<reddit-url>"
```

**Options:**
- `--comments N` — max top-level comments (default: 20)
- `--depth N` — reply nesting depth (default: 3)
- `--raw` — output raw JSON instead of formatted text

## 2. Search Reddit

```bash
{baseDir}/scripts/search.sh "<query>"
{baseDir}/scripts/search.sh "<query>" --subreddit openclaw
```

**Options:**
- `--subreddit NAME` — limit to specific subreddit (with or without `r/` prefix)
- `--sort relevance|new|top|comments` — sort order (default: relevance)
- `--time hour|day|week|month|year|all` — time range (default: all)
- `--limit N` — max results (default: 10)
- `--raw` — output raw JSON instead of formatted text

## How It Works

Reddit blocks default bot User-Agents but serves JSON when you append `.json` to any URL and use a browser-like UA. Both scripts:
1. Build the appropriate Reddit JSON API URL
2. Fetch with `curl` + browser User-Agent
3. Parse with `python3` into readable format

## When to Use

- **Always use this for Reddit** — WebFetch cannot access reddit.com
- User shares a Reddit link → use `fetch.sh`
- User asks to find/search Reddit posts → use `search.sh`
- Need to research a topic on Reddit → use `search.sh` then `fetch.sh` on interesting results
