# Notion API Audit (2025-09-03)

**Date:** 2026-02-03
**API Version:** 2025-09-03
**Client Version:** 0.2.0

## Executive Summary

This audit compares our NotionClient implementation against the official Notion API (version 2025-09-03) to identify gaps and prioritize implementation.

**Status:** ✅ Core features implemented, file upload added, archive/restore added

**Priority Legend:**
- **P0** (Critical): Essential functionality, immediate implementation required
- **P1** (High): Important features, implement within 1-2 weeks
- **P2** (Medium): Nice-to-have, implement as needed
- **P3** (Low): Edge cases, defer unless requested

## Implementation Status

### ✅ Implemented (Core)

| Feature | Endpoint | Status | Notes |
|---------|----------|--------|-------|
| Get page | `GET /v1/pages/{id}` | ✅ | Via `get()` |
| Update page | `PATCH /v1/pages/{id}` | ✅ | `update_page()` |
| Archive page | `PATCH /v1/pages/{id}` | ✅ NEW | `archive_page()` |
| Restore page | `PATCH /v1/pages/{id}` | ✅ NEW | `restore_page()` |
| Create page | `POST /v1/pages` | ✅ | `create_page()` |
| Get block | `GET /v1/blocks/{id}` | ✅ | Via `get()` |
| Update block | `PATCH /v1/blocks/{id}` | ✅ | Via `patch()` |
| Archive block | `PATCH /v1/blocks/{id}` | ✅ NEW | `archive_block()` |
| Restore block | `PATCH /v1/blocks/{id}` | ✅ NEW | `restore_block()` |
| Delete block | `DELETE /v1/blocks/{id}` | ✅ | Via `delete()` |
| Get block children | `GET /v1/blocks/{id}/children` | ✅ | Via `get()` |
| Append block children | `PATCH /v1/blocks/{id}/children` | ✅ | `append_blocks()`, `append_blocks_batch()` |
| Get database | `GET /v1/databases/{id}` | ✅ | `get_database()` |
| Query database | `POST /v1/databases/{id}/query` | ✅ | `query_database()` |
| Search | `POST /v1/search` | ✅ | `search()` |
| File upload | `POST /v1/file_uploads` | ✅ NEW | `upload_and_attach_file()` |
| File upload complete | `POST /v1/file_uploads/{id}/complete` | ✅ NEW | Internal to `_upload_file()` |

### 🚧 Partially Implemented

| Feature | Status | Gap | Priority | Notes |
|---------|--------|-----|----------|-------|
| File upload (multipart) | ⚠️ Partial | >20MB files not supported | P2 | Single-part works (<20MB), multipart stubbed with clear error |
| Data sources (2025-09-03) | ⚠️ Partial | Multi-source databases not supported | P1 | Old `query_database()` works for single-source DBs |

### ❌ Not Implemented

#### P0 (Critical) - None

All critical features implemented.

#### P1 (High Priority)

| Feature | Endpoint | Reason | Implementation Effort |
|---------|----------|--------|----------------------|
| **Data source query** | `POST /v1/data_sources/{id}/query` | 2025-09-03 introduces multi-source databases | Medium - requires new method + backward compat |
| **Get user** | `GET /v1/users/{id}` | Needed for @mention resolution, ownership checks | Low - simple GET wrapper |
| **List users** | `GET /v1/users` | Needed for team/permission management | Low - simple GET with pagination |
| **Get comment** | `GET /v1/comments/{id}` | Useful for collaboration features | Low - simple GET |
| **Create comment** | `POST /v1/comments` | Useful for collaboration features | Low - simple POST |

#### P2 (Medium Priority)

| Feature | Endpoint | Reason | Implementation Effort |
|---------|----------|--------|----------------------|
| **Multipart file upload** | `POST /v1/file_uploads/{id}/send` | Support >20MB files | Medium - chunking + progress tracking |
| **Create database** | `POST /v1/databases` | Rarely needed (usually done via UI) | Low - POST with schema |
| **Update database** | `PATCH /v1/databases/{id}` | Schema changes usually manual | Low - PATCH with schema |
| **Get page property** | `GET /v1/pages/{id}/properties/{property_id}` | Useful for paginated properties | Low - GET wrapper |
| **Webhook subscriptions** | `POST /v1/webhooks` | Real-time updates | High - requires server infrastructure |

#### P3 (Low Priority)

| Feature | Endpoint | Reason | Implementation Effort |
|---------|----------|--------|----------------------|
| **Bot info** | `GET /v1/users/me` | Informational only | Low - simple GET |
| **Rich text parsing** | N/A (client-side) | Helper for complex formatting | Medium - parser implementation |

## Detailed Analysis

### 1. Data Sources (2025-09-03 Breaking Change)

**What changed:**
- Notion now supports **multiple data sources per database** (e.g., synced from external APIs)
- Old endpoint: `POST /v1/databases/{database_id}/query`
- New endpoint: `POST /v1/data_sources/{data_source_id}/query`

**Current state:**
- `query_database()` still works for **single-source databases** (backward compatible)
- `get_database()` now returns `data_sources[]` array instead of single source

**Recommendation (P1):**
```python
def query_data_source(self, data_source_id: str, filter=None, sorts=None):
    """Query a specific data source (2025-09-03)"""
    payload = {}
    if filter:
        payload["filter"] = filter
    if sorts:
        payload["sorts"] = sorts
    return self.post(f"/v1/data_sources/{data_source_id}/query", json=payload)

def query_database_v2(self, database_id: str, filter=None, sorts=None):
    """
    Query database (2025-09-03 compatible)
    
    Automatically fetches data sources and queries first source.
    For multi-source databases, use query_data_source() directly.
    """
    # Get database metadata
    db = self.get_database(database_id)
    
    # Get first data source
    if not db.get("data_sources"):
        raise ValueError(f"Database {database_id} has no data sources")
    
    data_source_id = db["data_sources"][0]["id"]
    return self.query_data_source(data_source_id, filter, sorts)
```

### 2. File Upload (Multipart)

**Current state:**
- ✅ Single-part upload works (<20MB)
- ❌ Multipart upload not implemented (>20MB)

**Use case:** Large PDFs, videos, archives

**Recommendation (P2):**
Implement chunked upload using `/v1/file_uploads/{id}/send`:

```python
def _upload_file_multipart(self, file_path: str, content_type: str, chunk_size=10*1024*1024):
    """Upload large file in chunks (10MB default)"""
    # 1. Create upload
    create_resp = self.post("/v1/file_uploads", json={...})
    file_id = create_resp["id"]
    
    # 2. Upload chunks
    with open(file_path, 'rb') as f:
        chunk_num = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            self.post(f"/v1/file_uploads/{file_id}/send", data=chunk, headers={
                "Content-Type": content_type,
                "Content-Range": f"bytes {chunk_num*chunk_size}-{chunk_num*chunk_size+len(chunk)-1}/{file_size}"
            })
            chunk_num += 1
    
    # 3. Complete upload
    self.post(f"/v1/file_uploads/{file_id}/complete", json={})
    return file_id
```

### 3. Users & Permissions

**Current state:** Not implemented

**Use case:**
- Resolve @mentions in pages
- Check page ownership
- Team management automation

**Recommendation (P1):**
```python
def get_user(self, user_id: str):
    """Get user by ID"""
    return self.get(f"/v1/users/{user_id}")

def list_users(self, start_cursor=None):
    """List all users in workspace (paginated)"""
    params = {}
    if start_cursor:
        params["start_cursor"] = start_cursor
    return self.get("/v1/users", params=params)

def get_bot_info(self):
    """Get current bot user info"""
    return self.get("/v1/users/me")
```

### 4. Comments

**Current state:** Not implemented

**Use case:**
- Automated review comments
- Discussion threading
- Collaboration workflows

**Recommendation (P1):**
```python
def create_comment(self, parent_id: str, rich_text: list, discussion_id=None):
    """Create comment on page or existing discussion"""
    payload = {
        "parent": {"page_id": parent_id},
        "rich_text": rich_text
    }
    if discussion_id:
        payload["discussion_id"] = discussion_id
    return self.post("/v1/comments", json=payload)

def get_comments(self, block_id: str, start_cursor=None):
    """List comments for a block"""
    params = {"block_id": block_id}
    if start_cursor:
        params["start_cursor"] = start_cursor
    return self.get("/v1/comments", params=params)
```

### 5. Database Creation/Modification

**Current state:** Not implemented

**Use case:**
- Programmatic database setup
- Schema migration
- Template instantiation

**Recommendation (P2):**
Defer unless specific need arises. Database creation is typically done via UI.

## Recommendations Summary

### Immediate (Next PR)
1. ✅ **File upload** - Implemented
2. ✅ **Archive/restore** - Implemented

### Short Term (1-2 weeks)
3. **Data source query** - 2025-09-03 compatibility (P1)
4. **User management** - `get_user()`, `list_users()` (P1)
5. **Comments** - `create_comment()`, `get_comments()` (P1)

### Medium Term (as needed)
6. **Multipart upload** - Large files >20MB (P2)
7. **Database creation** - `create_database()` (P2)

### Deferred
8. **Webhooks** - Requires server infrastructure (P3)
9. **Rich text helpers** - Nice-to-have utilities (P3)

## Testing Coverage

### Current Tests
- ✅ File upload (single-part)
- ✅ File upload error handling (>20MB, missing file)
- ✅ Content type detection
- ✅ Archive/restore pages
- ✅ Archive/restore blocks
- ✅ Retry logic (429, 5xx)
- ✅ Workspace selection

### Needed Tests (Future)
- Data source queries (when implemented)
- Multipart upload (when implemented)
- User management (when implemented)
- Comments (when implemented)

## Changelog

**v0.2.0 (2026-02-03)**
- ✅ Added file upload support (`upload_and_attach_file()`)
- ✅ Added archive/restore for pages and blocks
- ✅ Added 16 unit tests (100% pass rate)
- ✅ Auto-detect content type from file extension
- ⚠️ Multipart upload (>20MB) stubbed with clear error

**v0.1.0 (2026-02-03)**
- Initial implementation with retry logic
- Connection pooling via requests.Session
- Rate limit handling (429)
- Basic CRUD operations

## References

- [Notion API Reference (2025-09-03)](https://developers.notion.com/reference/intro)
- [File Upload Documentation](https://developers.notion.com/reference/upload-a-file)
- [Data Sources (2025-09-03)](https://developers.notion.com/reference/retrieve-a-data-source)
