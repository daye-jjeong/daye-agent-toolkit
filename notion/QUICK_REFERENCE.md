# Notion Client Quick Reference

**Version:** 0.4.0  
**New Features:** Automatic Endpoint Routing, Data Sources, Users API, Database Schema

## 🚀 Quick Start

```python
from skills.notion.client import NotionClient

# Initialize
notion = NotionClient(workspace="personal")  # or "ronik"
```

## ⚡ Automatic Routing (NEW in v0.4.0)

**No code changes required!** The client automatically detects 2025-09-03 data sources.

```python
# Works for both legacy DBs and multi-source DBs
results = notion.query_database("db_id", filter={...})
# → Auto-routes to /v1/data_sources/{id}/query (if available)
# → Falls back to /v1/databases/{id}/query (if legacy)

# Multi-source databases (specify which source)
results = notion.query_database("db_id", filter={...}, data_source_index=1)
```

**Migration status:** ✅ 100% backward compatible. See `ENDPOINT_MIGRATION_AUDIT.md` for details.

## 🔍 Data Source Queries (v0.3.0)

```python
# Query data source (2025-09-03 API)
results = notion.query_data_source(
    "ds_id",
    filter={"property": "Status", "status": {"equals": "Active"}},
    page_size=50
)

# Convenience wrapper (auto-fetches data source ID)
results = notion.query_database_v2(
    "db_id",
    filter={...},
    data_source_index=0  # First data source (default)
)
```

## 👥 Users API (NEW in v0.3.0)

```python
# Get user
user = notion.get_user("user_id")

# List users
users = notion.list_users(page_size=50)

# Get bot info
bot = notion.get_bot_info()
```

## 🗄️ Database Schema (NEW in v0.3.0)

```python
# Create database
db = notion.create_database(
    parent_page_id="page_id",
    title="Tasks",
    properties={
        "Name": {"title": {}},
        "Status": {"status": {"options": [{"name": "Done", "color": "green"}]}}
    },
    icon={"type": "emoji", "emoji": "✅"}
)

# Update database
notion.update_database(
    "db_id",
    title="New Title",
    properties={"Priority": {"select": {"options": []}}}
)
```

## 📋 Page Properties (NEW in v0.3.0)

```python
# Get specific property
status = notion.get_page_property("page_id", "Status")

# Paginated property
rollup = notion.get_page_property("page_id", "prop_id", page_size=50)
```

## 📤 File Upload

```python
# Upload and attach file to page
notion.upload_and_attach_file(
    page_id="xxx",
    file_path="~/report.pdf",
    block_type="pdf",        # file|pdf|image|video
    caption="Optional caption"
)
```

**Supported:**
- ✅ Files ≤20MB (single-part)
- ✅ Auto-detect MIME type
- ✅ PDF, images, videos, archives, any file

**Not supported yet:**
- ❌ Files >20MB (raises clear error)

## 🗄️ Archive/Restore (NEW in v0.2.0)

```python
# Archive (soft delete)
notion.archive_page("page_id")
notion.archive_block("block_id")

# Restore
notion.restore_page("page_id")
notion.restore_block("block_id")
```

## 📄 Pages

```python
# Create page
page = notion.create_page(
    parent={"database_id": "db_id"},
    properties={"Name": {"title": [{"text": {"content": "Task"}}]}}
)

# Update page
notion.update_page("page_id", {
    "Status": {"status": {"name": "Done"}}
})

# Get page
page = notion.get("/v1/pages/page_id")
```

## 📝 Blocks

```python
# Append blocks
notion.append_blocks("page_id", [
    {
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "Title"}}]}
    },
    {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": "Content"}}]}
    }
])

# Batch append (>100 blocks)
notion.append_blocks_batch("page_id", large_block_list)
```

## 🗃️ Databases

```python
# Query database
results = notion.query_database(
    "db_id",
    filter={"property": "Status", "status": {"equals": "Active"}},
    sorts=[{"property": "Created", "direction": "descending"}]
)

# Get database
db = notion.get_database("db_id")
```

## 🔍 Search

```python
# Search all
results = notion.search(query="project")

# Search pages only
results = notion.search(
    query="",
    filter={"property": "object", "value": "page"}
)
```

## ⚙️ Configuration

```python
# Custom settings
notion = NotionClient(
    workspace="personal",
    max_retries=5,       # Default: 3
    timeout=15,          # Default: 10 seconds
    version="2025-09-03" # Default: latest
)
```

## 🧪 Testing

```bash
# Run all tests
python3 -m unittest skills.notion.test_client -v

# Run specific test
python3 -m unittest skills.notion.test_client.TestNotionClientFileUpload -v
```

## 🛠️ Error Handling

```python
try:
    notion.upload_and_attach_file(page_id, "large_file.zip")
except ValueError as e:
    if "File too large" in str(e):
        print("File >20MB not supported yet")
except FileNotFoundError:
    print("File not found")
```

## 📚 Full Documentation

- **User Guide:** `skills/notion/SKILL.md`
- **API Audit:** `skills/notion/API_AUDIT.md`
- **Tests:** `skills/notion/test_client.py`
- **Changelog:** `skills/notion/CHANGELOG.md`

## 🔗 Common Patterns

### Upload report to task
```python
task = notion.create_page(parent={"database_id": "tasks"}, ...)
notion.upload_and_attach_file(task["id"], "report.pdf", "pdf")
notion.update_page(task["id"], {"Status": {"status": {"name": "Done"}}})
```

### Bulk archive old tasks
```python
old_tasks = notion.query_database("tasks", filter={...})
for task in old_tasks["results"]:
    notion.archive_page(task["id"])
```

### Add formatted content
```python
notion.append_blocks(page_id, [
    {"type": "heading_1", "heading_1": {"rich_text": [{"text": {"content": "H1"}}]}},
    {"type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Text"}}]}},
    {"type": "code", "code": {"rich_text": [{"text": {"content": "code"}}], "language": "python"}}
])
```
