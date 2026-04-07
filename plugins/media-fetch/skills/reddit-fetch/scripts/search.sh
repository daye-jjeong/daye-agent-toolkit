#!/usr/bin/env bash
set -euo pipefail

QUERY=""
SUBREDDIT=""
SORT="relevance"
TIME="all"
LIMIT=10
RAW=false

while [[ $# -gt 0 ]]; do
	case "$1" in
		--subreddit) SUBREDDIT="$2"; shift 2 ;;
		--sort)      SORT="$2"; shift 2 ;;
		--time)      TIME="$2"; shift 2 ;;
		--limit)     LIMIT="$2"; shift 2 ;;
		--raw)       RAW=true; shift ;;
		*)           QUERY="$1"; shift ;;
	esac
done

if [[ -z "$QUERY" ]]; then
	echo "Usage: search.sh <query> [--subreddit NAME] [--sort relevance|new|top|comments] [--time hour|day|week|month|year|all] [--limit N] [--raw]" >&2
	exit 1
fi

# Strip r/ prefix if user provides it
SUBREDDIT="${SUBREDDIT#r/}"

# Build search URL
ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))")

if [[ -n "$SUBREDDIT" ]]; then
	SEARCH_URL="https://www.reddit.com/r/${SUBREDDIT}/search.json?q=${ENCODED_QUERY}&restrict_sr=on&sort=${SORT}&t=${TIME}&limit=${LIMIT}"
else
	SEARCH_URL="https://www.reddit.com/search.json?q=${ENCODED_QUERY}&sort=${SORT}&t=${TIME}&limit=${LIMIT}"
fi

RESPONSE=$(curl -s -f \
	-H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
	"$SEARCH_URL" 2>&1) || {
	echo "Error: Failed to search Reddit" >&2
	exit 1
}

if $RAW; then
	echo "$RESPONSE"
	exit 0
fi

echo "$RESPONSE" | python3 -c "
import json, sys, html
from datetime import datetime

data = json.load(sys.stdin)
children = data.get('data', {}).get('children', [])

if not children:
    print('No results found.')
    sys.exit(0)

print(f'# Reddit Search: {len(children)} results')
print()

for i, child in enumerate(children, 1):
    post = child['data']
    title = html.unescape(post.get('title', ''))
    author = post.get('author', '[deleted]')
    subreddit = post.get('subreddit_name_prefixed', '')
    score = post.get('score', 0)
    num_comments = post.get('num_comments', 0)
    created = datetime.fromtimestamp(post.get('created_utc', 0)).strftime('%Y-%m-%d')
    permalink = 'https://www.reddit.com' + post.get('permalink', '')
    selftext = html.unescape(post.get('selftext', ''))

    print(f'## {i}. {title}')
    print(f'**{subreddit}** | u/{author} | score: {score} | comments: {num_comments} | {created}')
    print(f'URL: {permalink}')
    if selftext:
        preview = selftext[:300].replace('\n', ' ')
        if len(selftext) > 300:
            preview += '...'
        print(f'Preview: {preview}')
    print()
"
