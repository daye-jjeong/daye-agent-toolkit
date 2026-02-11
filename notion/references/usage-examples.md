# Notion Client - Usage Examples

## Basic Example

```python
from skills.notion.client import NotionClient

# Initialize client (loads API key from ~/.config/notion/api_key_daye_personal)
notion = NotionClient(workspace="personal")

# Search databases
results = notion.search(query="", filter={"property": "object", "value": "database"})

# Create page
page = notion.create_page(
    parent={"database_id": "xxx"},
    properties={
        "Name": {"title": [{"text": {"content": "My Task"}}]},
        "Status": {"status": {"name": "Not Started"}}
    }
)

# Append blocks (batch mode for >100 blocks)
blocks = [
    {"type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Section 1"}}]}},
    {"type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Content..."}}]}}
]
notion.append_blocks(page["id"], blocks)

# Upload and attach file to page
notion.upload_and_attach_file(
    page_id=page["id"],
    file_path="~/Documents/report.pdf",
    block_type="pdf",
    caption="Monthly report"
)

# Archive (soft delete) a page
notion.archive_page(page["id"])

# Restore an archived page
notion.restore_page(page["id"])
```

## Workspace Selection

```python
# Personal workspace (NEW HOME)
notion_personal = NotionClient(workspace="personal")

# Work workspace (RONIK PROJECT)
notion_work = NotionClient(workspace="ronik")
```

## Custom Configuration

```python
# Custom retry/timeout settings
notion = NotionClient(
    workspace="personal",
    max_retries=5,      # More retries for flaky networks
    timeout=15,         # Longer timeout for slow connections
    version="2022-06-28"  # Use older API version if needed
)
```

## Migration from Old Patterns

### Before (No Retry, No Connection Reuse)

```python
import urllib.request
import json

def req(method, url, data=None):
    token = open("~/.config/notion/api_key", "r").read().strip()
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)

    with urllib.request.urlopen(r) as resp:
        return resp.status, json.loads(resp.read())

# Every call creates new connection, no retry on 429
status, data = req("POST", "https://api.notion.com/v1/pages", {...})
```

### After (With Retry, Connection Reuse)

```python
from skills.notion.client import NotionClient

notion = NotionClient(workspace="personal")

# Automatic retry, connection reuse, better error handling
data = notion.post("/v1/pages", json={...})
```
