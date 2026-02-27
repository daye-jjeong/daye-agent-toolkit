# Notion API Features (Detailed)

## Automatic Endpoint Routing (v0.4.0)

The client automatically detects whether to use the new 2025-09-03 data source endpoint or legacy database endpoint. No code changes required - existing code works unchanged.

### How It Works

```python
# Same code works for both legacy DBs and 2025-09-03 multi-source DBs
results = notion.query_database("database_id", filter={...})

# Behind the scenes:
# 1. Fetches database metadata to check for data_sources
# 2. If data_sources present -> Uses /v1/data_sources/{id}/query
# 3. If no data_sources -> Falls back to /v1/databases/{id}/query
# 4. If metadata fetch fails -> Falls back to legacy endpoint (backward compatible)
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

- Legacy databases (pre-2025-09-03) continue to work
- Existing code requires no changes
- Network errors gracefully fall back to legacy endpoint
- Permissions issues handled transparently

See `ENDPOINT_MIGRATION_AUDIT.md` for complete migration analysis.

---

## Data Source Queries (v0.3.0, 2025-09-03 API)

The 2025-09-03 API introduces data sources for multi-source databases.

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

---

## Users API (v0.3.0)

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

---

## Database Schema Management (v0.3.0)

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
    icon={"type": "emoji", "emoji": "checkmark"},
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
    icon={"type": "emoji", "emoji": "target"}
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

### Property Types Supported

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

---

## Page Property Retrieval (v0.3.0)

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

---

## File Upload (v0.2.0)

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

---

## Archive & Restore (v0.2.0)

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
