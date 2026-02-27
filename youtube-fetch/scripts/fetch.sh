#!/usr/bin/env bash
set -euo pipefail

URL=""
LANG_PREF="ko,en"
NO_TRANSCRIPT=false
RAW=false

while [[ $# -gt 0 ]]; do
	case "$1" in
		--no-transcript) NO_TRANSCRIPT=true; shift ;;
		--lang)          LANG_PREF="$2"; shift 2 ;;
		--raw)           RAW=true; shift ;;
		*)               URL="$1"; shift ;;
	esac
done

if [[ -z "$URL" ]]; then
	echo "Usage: fetch.sh <youtube-url> [--no-transcript] [--lang ko,en] [--raw]" >&2
	exit 1
fi

# Check yt-dlp is installed
if ! command -v yt-dlp &>/dev/null; then
	echo "Error: yt-dlp is not installed." >&2
	echo "Install with: brew install yt-dlp" >&2
	exit 1
fi

# Extract video ID from URL for temp file naming
VIDEO_ID=$(echo "$URL" | sed -E 's/.*[?&]v=([a-zA-Z0-9_-]{11}).*/\1/; s/.*youtu\.be\/([a-zA-Z0-9_-]{11}).*/\1/; s/.*\/shorts\/([a-zA-Z0-9_-]{11}).*/\1/' | head -1)
if [[ -z "$VIDEO_ID" || ${#VIDEO_ID} -ne 11 ]]; then
	VIDEO_ID="unknown"
fi

WORK_DIR="/tmp/yt-fetch-${VIDEO_ID}-$$"
mkdir -p "$WORK_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

# Fetch metadata JSON
META=$(yt-dlp -j --skip-download "$URL" 2>/dev/null) || {
	echo "Error: Failed to fetch video metadata. Check the URL." >&2
	exit 1
}

if $RAW; then
	echo "$META"
	exit 0
fi

# Fetch transcript if requested
TRANSCRIPT=""
if ! $NO_TRANSCRIPT; then
	# Try manual subs first, then auto-generated
	yt-dlp --write-sub --sub-lang "$LANG_PREF" --skip-download \
		-o "${WORK_DIR}/subs" "$URL" &>/dev/null || true

	# If no subtitle files found, try auto-generated
	SUB_FILE=$(find "$WORK_DIR" -name "subs.*" -type f 2>/dev/null | head -1)
	if [[ -z "$SUB_FILE" ]]; then
		yt-dlp --write-auto-sub --sub-lang "$LANG_PREF" --skip-download \
			-o "${WORK_DIR}/subs" "$URL" &>/dev/null || true
		SUB_FILE=$(find "$WORK_DIR" -name "subs.*" -type f 2>/dev/null | head -1)
	fi

	if [[ -n "$SUB_FILE" ]]; then
		TRANSCRIPT=$(cat "$SUB_FILE")
	fi
fi

# Format output as markdown
echo "$META" | python3 -c "
import json, sys, re

meta = json.load(sys.stdin)
transcript_text = sys.argv[1] if len(sys.argv) > 1 else ''

# Duration formatting
duration = meta.get('duration') or 0
if duration:
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    seconds = duration % 60
    if hours > 0:
        dur_str = f'{hours}:{minutes:02d}:{seconds:02d}'
    else:
        dur_str = f'{minutes}:{seconds:02d}'
else:
    dur_str = 'N/A'

# View count formatting
views = meta.get('view_count') or 0
if views >= 1_000_000:
    view_str = f'{views/1_000_000:.1f}M'
elif views >= 1_000:
    view_str = f'{views/1_000:.1f}K'
else:
    view_str = str(views)

# Upload date formatting
upload = meta.get('upload_date', '')
if upload and len(upload) == 8:
    upload = f'{upload[:4]}-{upload[4:6]}-{upload[6:]}'

print(f\"# {meta.get('title', 'Unknown')}\")
print()
print(f\"**Channel:** {meta.get('channel', meta.get('uploader', 'Unknown'))}\")
print(f\"**Uploaded:** {upload}\")
print(f\"**Duration:** {dur_str}\")
print(f\"**Views:** {view_str} | **Likes:** {meta.get('like_count', 'N/A')}\")
print(f\"**URL:** {meta.get('webpage_url', '')}\")
print()

# Tags
tags = meta.get('tags') or []
if tags:
    print(f\"**Tags:** {', '.join(tags[:10])}\")
    print()

# Description
desc = meta.get('description', '') or ''
if desc:
    lines = desc.split('\n')
    if len(lines) > 20:
        desc = '\n'.join(lines[:20]) + '\n\n... (truncated)'
    print('## Description')
    print()
    print(desc)
    print()

# Chapters
chapters = meta.get('chapters') or []
if chapters:
    print('## Chapters')
    print()
    for ch in chapters:
        start = int(ch.get('start_time', 0))
        m, s = divmod(start, 60)
        h, m = divmod(m, 60)
        if h > 0:
            ts = f'{h}:{m:02d}:{s:02d}'
        else:
            ts = f'{m}:{s:02d}'
        print(f'- **{ts}** {ch.get(\"title\", \"\")}')
    print()

# Transcript
if transcript_text.strip():
    # Parse VTT/SRT format -> plain text
    lines = transcript_text.strip().split('\n')
    text_lines = []
    for line in lines:
        line = line.strip()
        # Skip VTT header, sequence numbers, timestamps, empty lines, style blocks
        if not line:
            continue
        if line == 'WEBVTT' or line.startswith('Kind:') or line.startswith('Language:'):
            continue
        if line.isdigit():
            continue
        if re.match(r'\d{2}:\d{2}[:\.]', line):
            continue
        if line.startswith('NOTE') or line.startswith('STYLE'):
            continue
        # Remove HTML tags from auto-generated subs
        line = re.sub(r'<[^>]+>', '', line)
        line = line.strip()
        if line and line not in text_lines[-1:]:
            text_lines.append(line)
    if text_lines:
        print('## Transcript')
        print()
        print(' '.join(text_lines))
        print()
    else:
        print('## Transcript')
        print()
        print('(No transcript/subtitles available)')
        print()
else:
    print('## Transcript')
    print()
    print('(No transcript/subtitles available)')
    print()
" "$TRANSCRIPT"
