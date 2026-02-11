---
name: notion
description: Notion API 클라이언트 — retry, 엔드포인트 라우팅
---

# Notion Skill

Unified Notion API client with automatic retry, connection reuse (40-60% latency reduction), and 2025-09-03 API support including multi-source databases.

## Quick Start

```python
from skills.notion.client import NotionClient

notion = NotionClient(workspace="personal")  # or "ronik"

# Search
results = notion.search(query="", filter={"property": "object", "value": "database"})

# Create page
page = notion.create_page(
    parent={"database_id": "xxx"},
    properties={
        "Name": {"title": [{"text": {"content": "My Task"}}]},
        "Status": {"status": {"name": "Not Started"}}
    }
)

# Append blocks (auto-batches if >100)
notion.append_blocks(page["id"], blocks)

# File upload (<20MB)
notion.upload_and_attach_file(page["id"], "~/report.pdf", block_type="pdf")

# Archive / Restore
notion.archive_page(page["id"])
notion.restore_page(page["id"])
```

**상세**: {baseDir}/references/usage-examples.md 참고

## Core Methods

| Category | Methods |
|----------|---------|
| Generic | `get()`, `post()`, `patch()`, `delete()` |
| Database | `get_database()`, `query_database()`, `create_database()`, `update_database()` |
| Data Source | `query_data_source()`, `query_database_v2()` (2025-09-03 API) |
| Page | `create_page()`, `update_page()`, `get_page_property()` |
| Block | `append_blocks()`, `append_blocks_batch()` |
| User | `get_user()`, `list_users()`, `get_bot_info()` |
| File | `upload_and_attach_file()` (single-part, <=20MB) |
| Lifecycle | `archive_page()`, `restore_page()`, `archive_block()`, `restore_block()` |
| Search | `search(query, filter, sort)` |

**상세**: {baseDir}/references/api-coverage.md 참고

## Automatic Endpoint Routing (v0.4.0)

`query_database()` auto-detects 2025-09-03 data sources vs legacy databases. Existing code works unchanged -- no migration needed.

**상세**: {baseDir}/references/api-features.md 참고

## Markdown Converter

`markdown_to_blocks(md_string)` converts markdown to Notion block objects. Supports headings, lists, code blocks, bold/italic, links, callouts, dividers.

```python
from skills.notion.markdown_converter import markdown_to_blocks
blocks = markdown_to_blocks(markdown_text)
notion.append_blocks(page_id, blocks)
```

**상세**: {baseDir}/references/markdown-converter.md 참고

## Error Handling & Retry

- **Retriable**: 429, 5xx, timeouts, connection errors (exponential backoff: 1s, 2s, 4s)
- **Non-retriable**: 400, 401, 404 (immediate exception)
- Max 3 retries (configurable via `max_retries`)

## Workspace Configuration

| Workspace | Init |
|-----------|------|
| Personal (NEW HOME) | `NotionClient(workspace="personal")` |
| Work (RONIK PROJECT) | `NotionClient(workspace="ronik")` |

API keys: `~/.config/notion/api_key_daye_personal` (auto-loaded)

## Compatibility

- **API Version:** 2025-09-03 (latest)
- **Python:** 3.8+
- **Dependencies:** `requests` (standard)
- **Tests:** 32 unit tests, 100% pass rate

**상세**: {baseDir}/references/testing.md 참고

## Troubleshooting

Common issues: API key not found, rate limiting (429), request timeouts.

**상세**: {baseDir}/references/troubleshooting.md 참고

## Related

- API audit: `API_AUDIT.md`
- Endpoint migration: `ENDPOINT_MIGRATION_AUDIT.md`
- Migration guide: `docs/notion_integration_audit_2026-02-03.md`
