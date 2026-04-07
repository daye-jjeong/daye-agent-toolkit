---
name: youtube-fetch
description: Use when needing to read YouTube videos. Fetches video metadata (title, channel, description, chapters) and transcript/subtitles via yt-dlp. Use this instead of WebFetch for all YouTube access.
---

# YouTube Fetch

Read YouTube videos — extracts metadata and transcripts via yt-dlp.

## Fetch a Video

```bash
{baseDir}/scripts/fetch.sh "<youtube-url>"
```

**Options:**
- `--no-transcript` — skip transcript extraction (faster, metadata only)
- `--lang ko,en` — preferred subtitle languages (default: ko,en)
- `--raw` — output raw yt-dlp JSON instead of formatted text

## Prerequisites

Requires `yt-dlp` installed:
```bash
brew install yt-dlp
```

## When to Use

- **Always use this for YouTube** — WebFetch cannot access youtube.com
- User shares a YouTube link → use `fetch.sh`
- User asks "what is this video about?" → use `fetch.sh`
- Need to summarize or analyze a video → use `fetch.sh`, then summarize the transcript
- Supports `youtube.com/watch?v=`, `youtu.be/`, and `youtube.com/shorts/` URLs
