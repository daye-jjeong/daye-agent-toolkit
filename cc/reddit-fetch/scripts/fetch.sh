#!/usr/bin/env bash
set -euo pipefail

URL=""
MAX_COMMENTS=20
MAX_DEPTH=3
RAW=false

while [[ $# -gt 0 ]]; do
	case "$1" in
		--comments) MAX_COMMENTS="$2"; shift 2 ;;
		--depth)    MAX_DEPTH="$2"; shift 2 ;;
		--raw)      RAW=true; shift ;;
		*)          URL="$1"; shift ;;
	esac
done

if [[ -z "$URL" ]]; then
	echo "Usage: fetch.sh <reddit-url> [--comments N] [--depth N] [--raw]" >&2
	exit 1
fi

# Normalize URL → JSON endpoint
URL="${URL%/}"
URL="${URL%.json}"
JSON_URL="${URL}.json"

RESPONSE=$(curl -s -f \
	-H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
	"$JSON_URL" 2>&1) || {
	echo "Error: Failed to fetch $JSON_URL" >&2
	exit 1
}

if $RAW; then
	echo "$RESPONSE"
	exit 0
fi

echo "$RESPONSE" | python3 -c "
import json, sys, textwrap, html

data = json.load(sys.stdin)
MAX_COMMENTS = int(sys.argv[1])
MAX_DEPTH = int(sys.argv[2])

def unescape(text):
    return html.unescape(text) if text else ''

# === Post ===
post = data[0]['data']['children'][0]['data']
print(f\"# {unescape(post['title'])}\")
print(f\"**u/{post['author']}** | score: {post['score']} | r/{post['subreddit']}\")
print(f\"URL: {post['url']}\")
print()
body = unescape(post.get('selftext', ''))
if body:
    print(body)
    print()

# === Comments ===
def print_comment(c, depth=0):
    if c['kind'] == 'more':
        return
    cd = c['data']
    indent = '  ' * depth
    marker = '└─ ' if depth > 0 else ''
    author = cd.get('author', '[deleted]')
    score = cd.get('score', 0)
    body = unescape(cd.get('body', ''))
    print(f\"{indent}{marker}**u/{author}** (score: {score}):\")
    for line in body.split('\n'):
        print(f\"{indent}   {line}\")
    print()
    if depth < MAX_DEPTH and cd.get('replies') and isinstance(cd['replies'], dict):
        for r in cd['replies']['data']['children']:
            print_comment(r, depth + 1)

print('---')
print(f'## Comments ({len([c for c in data[1][\"data\"][\"children\"] if c[\"kind\"] != \"more\"])} top-level)')
print()
for c in data[1]['data']['children'][:MAX_COMMENTS]:
    print_comment(c)
" "$MAX_COMMENTS" "$MAX_DEPTH"
