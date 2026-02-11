---
name: notion
description: Unified Notion API client with retry logic, connection reuse, and modern API features (workspace version).
---

# Notion Skill

**Version:** 0.4.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Stable

**Purpose:** Unified Notion API client with retry logic, connection reuse, and modern API features.

## Features

- ✅ **Automatic endpoint routing** - Smart detection of 2025-09-03 data sources with legacy fallback
- ✅ **Automatic retry** with exponential backoff on rate limits (429) and server errors (5xx)
- ✅ **Connection reuse** via `requests.Session` (40-60% latency reduction)
- ✅ **Latest API version** (2025-09-03) with multi-source database support
- ✅ **Data source queries** - Query multi-source databases (2025-09-03 API)
- ✅ **Users API** - Get user info, list workspace users, bot details
- ✅ **Database schema management** - Create and update database structures
- ✅ **Page property retrieval** - Paginated access to large properties
- ✅ **File upload** - Upload and attach files to pages (<20MB single-part)
- ✅ **Archive/Restore** - Soft delete and restore pages and blocks
- ✅ **Configurable** timeout, retries, workspace selection
- ✅ **Type-safe** error handling (no silent failures)
- ✅ **Fully tested** - 38 unit tests with 100% pass rate
- ✅ **100% backward compatible** - Existing code works unchanged

## Installation

No additional dependencies required (uses `requests`, included in standard environment).

## Usage

### Basic Example

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

### Advanced: Workspace Selection

```python
# Personal workspace (NEW HOME)
notion_personal = NotionClient(workspace="personal")

# Work workspace (RONIK PROJECT)
notion_work = NotionClient(workspace="ronik")
```

### Advanced: Custom Configuration

```python
# Custom retry/timeout settings
notion = NotionClient(
    workspace="personal",
    max_retries=5,      # More retries for flaky networks
    timeout=15,         # Longer timeout for slow connections
    version="2022-06-28"  # Use older API version if needed
)
```

## Markdown Support

The skill includes a markdown-to-Notion-blocks converter for easy content creation from markdown files.

**Why needed:** Notion's API requires structured block objects (JSON). Writing these manually is verbose and error-prone, especially for formatted content.

### Usage

```python
from skills.notion.markdown_converter import markdown_to_blocks
from skills.notion.client import NotionClient

# Convert markdown to Notion blocks
markdown = """
# Main Title

This is a **bold** paragraph with *italic* text.

## Section 1

- Bullet point 1
- Bullet point 2

```python
def hello():
    print("Hello!")
```
"""

blocks = markdown_to_blocks(markdown)

# Append to Notion page
notion = NotionClient()
notion.append_blocks(page_id, blocks)
```

### Supported Markdown Elements

| Markdown | Notion Block | Notes |
|----------|--------------|-------|
| `# H1`, `## H2`, `### H3` | `heading_1`, `heading_2`, `heading_3` | H4-H6 map to heading_3 |
| `- item` or `* item` | `bulleted_list_item` | |
| `1. item`, `2. item` | `numbered_list_item` | |
| ` ```language` | `code` block | Syntax highlighting |
| `**bold**`, `*italic*` | Inline annotations | |
| `` `code` `` | Inline code | |
| `[text](url)` | Link | |
| `> quote` | `callout` | Rendered with 💡 icon |
| `---` | `divider` | |

### Batch Processing for Large Documents

Notion limits block operations to 100 blocks per request. For longer documents, use batching:

```python
blocks = markdown_to_blocks(long_markdown)

# Append in batches of 100
for i in range(0, len(blocks), 100):
    batch = blocks[i:i+100]
    notion.append_blocks(page_id, batch)
    print(f"Appended blocks {i+1}-{min(i+100, len(blocks))}")
```

### When to Use

✅ **Use markdown converter when:**
- Creating documentation pages from markdown files
- Importing blog posts or READMEs to Notion
- Automating content creation with formatted text

❌ **Don't use when:**
- Content is already in Notion's block format
- You need advanced block types (tables, embeds, databases)
- Real-time collaboration/editing is needed (use Notion UI)

### Limitations & Future Improvements

**Current limitations:**
- No table support (Notion tables are complex)
- Nested lists are flattened (no indentation)
- No image parsing (`![alt](url)`)
- No strikethrough (`~~text~~`) or underline

**Planned features:**
- Image block support
- Nested list indentation
- Table parsing
- More inline styles

## Automatic Endpoint Routing (v0.4.0)

### What's New

The client now **automatically detects** whether to use the new 2025-09-03 data source endpoint or legacy database endpoint. **No code changes required** - existing code works unchanged!

### How It Works

```python
# Same code works for both legacy DBs and 2025-09-03 multi-source DBs
results = notion.query_database("database_id", filter={...})

# Behind the scenes:
# 1. Fetches database metadata to check for data_sources
# 2. If data_sources present → Uses /v1/data_sources/{id}/query
# 3. If no data_sources → Falls back to /v1/databases/{id}/query
# 4. If metadata fetch fails → Falls back to legacy endpoint (backward compatible)
```

### Multi-Source Database Support

For databases with multiple data sources, specify which one to query:

```python
# Query first data source (default)
results = notion.query_database("db_id", filter={...})

# Query second data source
results = notion.query_database("db_id", filter={...}, data_source_index=1)

# Or use query_data_source() directly for full control
db = notion.get_database("db_id")
data_source_id = db["data_sources"][1]["id"]
results = notion.query_data_source(data_source_id, filter={...})
```

### Backward Compatibility

✅ **Legacy databases** (pre-2025-09-03) continue to work  
✅ **Existing code** requires no changes  
✅ **Network errors** gracefully fall back to legacy endpoint  
✅ **Permissions** issues handled transparently  

See `ENDPOINT_MIGRATION_AUDIT.md` for complete migration analysis.

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

## Rate Limit Handling

The client automatically handles Notion's 3 req/sec rate limit:

- **On 429 error:** Waits 1s, 2s, 4s (exponential backoff) before retry
- **Max retries:** 3 attempts (configurable)
- **Fallback:** Raises exception after retries exhausted

Example output when rate limited:

```
⚠️  Rate limited (429). Retrying in 1s... (attempt 1/3)
⚠️  Rate limited (429). Retrying in 2s... (attempt 2/3)
✅ Success on attempt 3
```

## New Features (v0.3.0)

### Data Source Queries (2025-09-03 API)

The 2025-09-03 API introduces data sources for multi-source databases. Use these methods to query databases with multiple data sources.

**When to use:**
- Databases with multiple data sources (check `database["data_sources"]`)
- Need pagination control (start_cursor, page_size)
- Working with 2025-09-03 API version

**Example:**

```python
from skills.notion.client import NotionClient

notion = NotionClient(workspace="personal")

# Method 1: Direct data source query (if you know the data source ID)
db = notion.get_database("db_id")
data_source_id = db["data_sources"][0]["id"]

results = notion.query_data_source(
    data_source_id,
    filter={"property": "Status", "status": {"equals": "Active"}},
    sorts=[{"property": "Created", "direction": "descending"}],
    page_size=50
)

# Method 2: Convenience wrapper (auto-fetches data source ID)
results = notion.query_database_v2(
    "db_id",
    filter={"property": "Status", "status": {"equals": "Active"}},
    data_source_index=0  # Use first data source (default)
)

# Pagination example
cursor = None
all_pages = []
while True:
    response = notion.query_data_source("ds_id", start_cursor=cursor, page_size=100)
    all_pages.extend(response["results"])
    if not response["has_more"]:
        break
    cursor = response["next_cursor"]
```

**Key differences from `query_database()`:**
- `query_database()` - Old endpoint, works with single-source databases
- `query_data_source()` - New endpoint, works with data source ID
- `query_database_v2()` - Wrapper that fetches data source ID automatically

### Users API

Retrieve user information, list workspace members, and get bot details.

**Use cases:**
- Find user IDs for assigning tasks
- Audit workspace members
- Get integration bot information
- Resolve user mentions

**Example:**

```python
# Get specific user by ID
user = notion.get_user("user_uuid")
print(f"Name: {user['name']}")
print(f"Type: {user['type']}")  # person or bot
print(f"Avatar: {user.get('avatar_url')}")

# List all workspace users
users = notion.list_users()
for user in users["results"]:
    print(f"{user['name']} - {user['type']}")

# Paginate through large user lists
cursor = None
all_users = []
while True:
    response = notion.list_users(start_cursor=cursor, page_size=50)
    all_users.extend(response["results"])
    if not response["has_more"]:
        break
    cursor = response["next_cursor"]

# Get bot/integration info
bot = notion.get_bot_info()
print(f"Integration: {bot['name']} (ID: {bot['id']})")
```

**Common patterns:**

```python
# Find user ID by name (for task assignment)
users = notion.list_users()
user_map = {u["name"]: u["id"] for u in users["results"]}

# Assign task to user
notion.update_page(
    "task_page_id",
    {"Assignee": {"people": [{"id": user_map["Alice"]}]}}
)

# Get all bot users
users = notion.list_users()
bots = [u for u in users["results"] if u["type"] == "bot"]
print(f"Found {len(bots)} bot integrations")
```

### Database Schema Management

Create new databases and update existing database schemas programmatically.

**Use cases:**
- Automate database creation for new projects
- Add properties to existing databases
- Update property options (status, select)
- Change database metadata (title, icon, description)

**Example:**

```python
# Create a new task database
db = notion.create_database(
    parent_page_id="page_id",
    title="Project Tasks",
    properties={
        "Name": {"title": {}},  # Required title property
        "Status": {
            "status": {
                "options": [
                    {"name": "Not Started", "color": "gray"},
                    {"name": "In Progress", "color": "blue"},
                    {"name": "Done", "color": "green"}
                ]
            }
        },
        "Due Date": {"date": {}},
        "Priority": {
            "select": {
                "options": [
                    {"name": "High", "color": "red"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "Low", "color": "gray"}
                ]
            }
        },
        "Assignee": {"people": {}},
        "Tags": {"multi_select": {"options": []}}
    },
    description="Track project tasks and deliverables",
    icon={"type": "emoji", "emoji": "✅"},
    is_inline=False  # Full-page database
)

print(f"Created database: {db['id']}")

# Update existing database - add new property
notion.update_database(
    db["id"],
    properties={
        "Estimated Hours": {"number": {"format": "number"}}
    }
)

# Update database title and icon
notion.update_database(
    "db_id",
    title="Renamed Tasks Database",
    icon={"type": "emoji", "emoji": "🎯"}
)

# Update select/status property options
notion.update_database(
    "db_id",
    properties={
        "Status": {
            "status": {
                "options": [
                    {"name": "Blocked", "color": "red"},  # Add new status
                    {"name": "Done", "color": "green"}
                ]
            }
        }
    }
)
```

**Property types supported:**

```python
properties = {
    "Title": {"title": {}},
    "Rich Text": {"rich_text": {}},
    "Number": {"number": {"format": "number"}},  # or "dollar", "percent", etc.
    "Select": {"select": {"options": [{"name": "Option", "color": "blue"}]}},
    "Multi-select": {"multi_select": {"options": []}},
    "Status": {"status": {"options": [{"name": "Done", "color": "green"}]}},
    "Date": {"date": {}},
    "People": {"people": {}},
    "Files": {"files": {}},
    "Checkbox": {"checkbox": {}},
    "URL": {"url": {}},
    "Email": {"email": {}},
    "Phone": {"phone_number": {}},
    "Formula": {"formula": {"expression": "prop(\"Number\") * 2"}},
    "Relation": {"relation": {"database_id": "related_db_id"}},
    "Rollup": {
        "rollup": {
            "relation_property_name": "Related",
            "rollup_property_name": "Count",
            "function": "count"
        }
    },
    "Created time": {"created_time": {}},
    "Created by": {"created_by": {}},
    "Last edited time": {"last_edited_time": {}},
    "Last edited by": {"last_edited_by": {}}
}
```

### Page Property Retrieval

Retrieve individual page properties with pagination support. Useful for large properties like relations or rollups.

**When to use:**
- Need to fetch a single property without loading entire page
- Property has large values (relation with many linked pages)
- Paginated properties (rollup results)

**Example:**

```python
# Get a simple property
status = notion.get_page_property("page_id", "Status")
print(f"Status: {status['status']['name']}")

# Get a relation property (may be paginated)
relations = notion.get_page_property("page_id", "Related Tasks")
print(f"Found {len(relations.get('results', []))} related tasks")

# Paginate through large property
cursor = None
all_items = []
while True:
    result = notion.get_page_property(
        "page_id",
        "Large Relation",
        start_cursor=cursor,
        page_size=50
    )
    all_items.extend(result.get("results", []))
    if not result.get("has_more"):
        break
    cursor = result["next_cursor"]

print(f"Total items: {len(all_items)}")

# Get rollup property
rollup = notion.get_page_property("page_id", "Total Count")
if rollup["type"] == "rollup":
    print(f"Rollup value: {rollup['rollup']['number']}")
```

**Common patterns:**

```python
# Fetch only specific properties to reduce payload size
page = notion.get(f"/v1/pages/{page_id}")  # Gets full page
status = notion.get_page_property(page_id, "Status")  # Gets only Status

# Check if property is paginated before fetching all
first_page = notion.get_page_property(page_id, "prop_id", page_size=1)
if first_page.get("has_more"):
    print("Property has multiple pages, fetching all...")
    # Paginate through all results

# Get property by property ID (more efficient than name)
page = notion.get(f"/v1/pages/{page_id}")
property_id = page["properties"]["Status"]["id"]
status = notion.get_page_property(page_id, property_id)
```

## New Features (v0.2.0)

### File Upload

Upload files and attach them to Notion pages. Supports single-part uploads up to 20MB.

**Supported file types:**
- Documents: PDF, DOCX, TXT
- Images: JPG, PNG, GIF, SVG
- Data: CSV, JSON, XML
- Archives: ZIP, TAR, GZ
- Any file type (auto-detected MIME type)

**Example:**

```python
from skills.notion.client import NotionClient

notion = NotionClient(workspace="personal")

# Upload PDF and attach to task page
result = notion.upload_and_attach_file(
    page_id="xxx",
    file_path="~/Documents/report.pdf",
    block_type="pdf",
    caption="Q4 Financial Report"
)

# Upload image
notion.upload_and_attach_file(
    page_id="xxx",
    file_path="~/Pictures/screenshot.png",
    block_type="image",
    caption="Bug screenshot"
)

# Upload generic file (CSV, logs, etc.)
notion.upload_and_attach_file(
    page_id="xxx",
    file_path="~/data.csv",
    block_type="file"
)
```

**Block types:**
- `"file"` - Generic file attachment
- `"pdf"` - PDF document (renders in Notion)
- `"image"` - Image (displays inline)
- `"video"` - Video file

**Limitations:**
- Single-part upload only (<=20MB)
- Files >20MB will raise `ValueError` with clear message
- Multipart upload (>20MB) planned for future release

**Error handling:**

```python
try:
    notion.upload_and_attach_file(page_id, "large_file.zip")
except ValueError as e:
    if "File too large" in str(e):
        print("File exceeds 20MB limit. Use external hosting or split file.")
except FileNotFoundError:
    print("File not found. Check path.")
```

### Archive & Restore

Soft delete (archive) and restore pages and blocks.

**Why archive instead of delete?**
- Archived pages can be restored
- Preserves relationships and history
- Safer than permanent deletion

**Example:**

```python
# Archive a task page (soft delete)
notion.archive_page("page_id")

# Restore it later
notion.restore_page("page_id")

# Archive a specific block
notion.archive_block("block_id")

# Restore the block
notion.restore_block("block_id")
```

**Common patterns:**

```python
# Archive completed tasks older than 30 days
from datetime import datetime, timedelta

cutoff = datetime.now() - timedelta(days=30)

tasks = notion.query_database(
    database_id="tasks_db",
    filter={
        "and": [
            {"property": "Status", "status": {"equals": "Done"}},
            {"property": "Completed", "date": {"before": cutoff.isoformat()}}
        ]
    }
)

for task in tasks["results"]:
    notion.archive_page(task["id"])
    print(f"Archived: {task['properties']['Name']['title'][0]['text']['content']}")
```

**Bulk restore:**

```python
# Search for archived pages
archived = notion.search(
    query="",
    filter={
        "property": "object",
        "value": "page"
    }
)

# Restore specific pages
for page in archived["results"]:
    if page.get("archived") and "Report" in page["properties"].get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", ""):
        notion.restore_page(page["id"])
        print(f"Restored: {page['id']}")
```

## API Coverage

### Implemented Methods

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get(path)` | Any GET | Generic GET request |
| `post(path, json)` | Any POST | Generic POST request |
| `patch(path, json)` | Any PATCH | Generic PATCH request |
| `delete(path)` | Any DELETE | Generic DELETE request |
| `get_database(db_id)` | `/v1/databases/:id` | Retrieve database metadata |
| `query_database(db_id, filter, sorts)` | `/v1/databases/:id/query` | Query database (legacy) |
| **`query_data_source(ds_id, ...)`** 🆕 | `/v1/data_sources/:id/query` | **Query data source (2025-09-03)** |
| **`query_database_v2(db_id, ...)`** 🆕 | `/v1/data_sources/:id/query` | **Query database via data sources** |
| **`create_database(...)`** 🆕 | `/v1/databases` | **Create new database** |
| **`update_database(db_id, ...)`** 🆕 | `/v1/databases/:id` | **Update database schema** |
| `create_page(parent, properties, children)` | `/v1/pages` | Create new page |
| `update_page(page_id, properties)` | `/v1/pages/:id` | Update page properties |
| **`get_page_property(page_id, prop_id, ...)`** 🆕 | `/v1/pages/:id/properties/:property_id` | **Get specific page property** |
| `append_blocks(block_id, children)` | `/v1/blocks/:id/children` | Append blocks (max 100) |
| `append_blocks_batch(block_id, children)` | `/v1/blocks/:id/children` | Append blocks in batches |
| `search(query, filter, sort)` | `/v1/search` | Search pages/databases |
| **`get_user(user_id)`** 🆕 | `/v1/users/:id` | **Get user by ID** |
| **`list_users(...)`** 🆕 | `/v1/users` | **List workspace users** |
| **`get_bot_info()`** 🆕 | `/v1/users/me` | **Get bot/integration info** |
| `upload_and_attach_file(...)` ⭐ | `/v1/file_uploads` | Upload file and attach to page |
| `archive_page(page_id)` ⭐ | `/v1/pages/:id` | Archive (soft delete) a page |
| `restore_page(page_id)` ⭐ | `/v1/pages/:id` | Restore archived page |
| `archive_block(block_id)` ⭐ | `/v1/blocks/:id` | Archive a block |
| `restore_block(block_id)` ⭐ | `/v1/blocks/:id` | Restore archived block |

⭐ = New in v0.2.0  
🆕 = New in v0.3.0

### Not Yet Implemented

- Multipart file upload (>20MB) - see `API_AUDIT.md`
- Data source operations (2025-09-03 multi-source DBs)
- User management (`get_user()`, `list_users()`)
- Comments (`create_comment()`, `get_comments()`)
- Webhook subscriptions

**Full gap analysis:** See `skills/notion/API_AUDIT.md` for detailed audit and implementation roadmap.

## Error Handling

The client distinguishes between retriable and non-retriable errors:

**Retriable (with backoff):**
- 429 (rate limited)
- 500-503 (server errors)
- Network timeouts
- Connection errors

**Non-retriable (immediate exception):**
- 400 (bad request)
- 401 (unauthorized/invalid API key)
- 404 (not found)

## Compatibility

- **API Version:** 2025-09-03 (latest)
- **Python:** 3.8+
- **Dependencies:** `requests` (standard)
- **Workspaces:** NEW HOME (personal), RONIK PROJECT (work)

## Testing

### Run Tests

```bash
# Run all tests
python3 -m unittest skills.notion.test_client -v

# Run specific test class
python3 -m unittest skills.notion.test_client.TestNotionClientFileUpload -v

# Run specific test
python3 -m unittest skills.notion.test_client.TestNotionClientFileUpload.test_upload_file_single_part -v
```

### Test Coverage

**Current: 32 tests, 100% pass rate**

**v0.3.0 features (10 tests):**
- ✅ Data source queries (single/multi-source, pagination)
- ✅ Database v2 queries (auto data source lookup)
- ✅ Users API (get_user, list_users, bot_info, pagination)
- ✅ Database create (schema, properties, icon, inline)
- ✅ Database update (title, properties, validation)
- ✅ Page property retrieval (simple, paginated)

**v0.2.0 features (10 tests):**
- ✅ File upload (single-part <20MB)
- ✅ File size validation (>20MB error)
- ✅ File not found handling
- ✅ Content type auto-detection (PDF, JPG, PNG, TXT)
- ✅ Upload and attach to page
- ✅ Archive/restore pages
- ✅ Archive/restore blocks

**Core features (12 tests):**
- ✅ Retry logic (429 rate limit, 5xx server errors)
- ✅ No retry on 4xx client errors
- ✅ Workspace selection (personal/ronik)
- ✅ API key loading

### Manual Testing

```bash
# Test connection
python3 skills/notion/client.py

# Expected output:
# Testing Notion API connection...
# ✅ Connection successful!
#    Found X databases
```

### Writing New Tests

```python
import unittest
from unittest.mock import Mock, patch
from skills.notion.client import NotionClient

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        """Set up test client with mocked API key"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    def test_my_feature(self):
        """Test description"""
        # Mock API responses
        self.client.get = Mock(return_value={"id": "test"})
        
        # Execute
        result = self.client.get("/v1/pages/test")
        
        # Assert
        self.assertEqual(result["id"], "test")
```

## Troubleshooting

### "Notion API key not found"

**Cause:** API key file missing or wrong workspace.

**Fix:**
```bash
# Check key exists
ls -la ~/.config/notion/api_key_daye_personal

# If missing, create it
mkdir -p ~/.config/notion
echo "ntn_YOUR_API_KEY_HERE" > ~/.config/notion/api_key_daye_personal
chmod 600 ~/.config/notion/api_key_daye_personal
```

### "Rate limited (429)"

**Cause:** Exceeded 3 requests/second.

**Fix:** Client automatically retries. If persistent, reduce request rate or batch operations.

### "Request timed out"

**Cause:** Network issue or Notion API slow.

**Fix:** Increase timeout:
```python
notion = NotionClient(workspace="personal", timeout=30)
```

## Migration Guide

See `docs/notion_integration_audit_2026-02-03.md` for detailed migration plan for all existing scripts.

## Related

- Audit report: `docs/notion_integration_audit_2026-02-03.md`
- Integration checker: `scripts/check_integrations.py`
- Example usage: `scripts/notion/ai_trends_ingest.py` (to be migrated)
