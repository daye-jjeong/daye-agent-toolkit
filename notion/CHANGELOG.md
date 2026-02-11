# Changelog

All notable changes to this skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ✨ **Markdown Converter** (`markdown_converter.py`) - Convert markdown to Notion blocks
  - Supports headings (H1-H6 → heading_1/2/3), lists (bulleted/numbered), code blocks
  - Inline formatting: **bold**, *italic*, `code`, [links](url)
  - Blockquotes (rendered as callouts), dividers
  - Automatic batch processing for documents >100 blocks
  - Fixes issue where markdown headings appeared as plain text with '##' prefixes
  - Documentation added to SKILL.md with usage examples and limitations

### Changed
- Enhanced SKILL.md with "Markdown Support" section (usage, supported elements, batch processing)

### Fixed
- Markdown headings now render as proper Notion heading blocks instead of plain text paragraphs

## [0.4.0] - 2026-02-03

### Added
- ✨ **Automatic endpoint routing** in `query_database()` - Smart detection of 2025-09-03 data sources
  - Automatically routes to `/v1/data_sources/{id}/query` when data_sources present
  - Falls back to legacy `/v1/databases/{id}/query` for older databases
  - Graceful fallback on network/permission errors
  - Multi-source database support via `data_source_index` parameter
- 🧪 **Extended test coverage** - 6 new tests for automatic routing
  - `TestNotionClientQueryDatabaseAutoRoute` - Auto-routing, fallback, multi-source, error handling
  - Total: 38 unit tests, 100% pass rate
- 📚 **Comprehensive migration audit** - `ENDPOINT_MIGRATION_AUDIT.md`
  - Complete analysis of 2025-09-03 breaking changes
  - Backward compatibility matrix
  - Future considerations and enhancement opportunities

### Changed
- **BREAKING (internal only):** `query_database()` signature extended with optional parameters
  - Added: `start_cursor`, `page_size`, `data_source_index`
  - **Backward compatible:** All parameters optional, existing calls work unchanged
- Updated `SKILL.md` with automatic routing documentation
- Status: Experimental → **Stable** (fully tested and production-ready)

### Fixed
- ValueError handling in `query_database()` - User errors (bad params) now correctly raised instead of fallback
- Improved error messages for data source index out of range

## [0.3.0] - 2026-02-03

### Added
- ✨ **Data source query support** (2025-09-03 API)
  - `query_data_source(data_source_id, ...)` - Query multi-source databases
  - `query_database_v2(database_id, ...)` - Convenience wrapper using data_sources[]
- ✨ **Users API** - User and bot information retrieval
  - `get_user(user_id)` - Get user by ID
  - `list_users(start_cursor, page_size)` - List workspace users
  - `get_bot_info()` - Get integration bot details
- ✨ **Database schema management** - Create and update database structures
  - `create_database(parent_page_id, title, properties, ...)` - Create new database
  - `update_database(database_id, title, properties, ...)` - Update schema/metadata
- ✨ **Page property retrieval** - Paginated property access
  - `get_page_property(page_id, property_id, ...)` - Get specific property with pagination
- 🧪 **Extended test coverage** - 10 new tests for v0.3.0 features
  - Data source queries (single/multi-source, pagination)
  - Users API (get_user, list_users, bot_info)
  - Database create/update (schema, properties, icon)
  - Page property retrieval (simple/paginated)

### Changed
- Updated API method table in SKILL.md (19 total methods)
- Enhanced QUICK_REFERENCE.md with new feature examples
- Improved error messages for data source edge cases

## [0.2.0] - 2026-02-03

### Added
- ✨ **File upload support** - `upload_and_attach_file()` for single-part uploads (<20MB)
  - Auto-detect MIME type from file extension
  - Support for file, pdf, image, video block types
  - Clear error message for files >20MB (multipart not yet supported)
- ✨ **Archive/restore functionality** for pages and blocks
  - `archive_page()` / `restore_page()`
  - `archive_block()` / `restore_block()`
- 🧪 **Comprehensive test suite** - 16 unit tests with 100% pass rate
  - File upload tests (single-part, size validation, content type detection)
  - Archive/restore tests
  - Retry logic tests (429, 5xx, 4xx)
  - Workspace selection tests
- 📚 **API audit document** - `API_AUDIT.md` with P0/P1/P2 gap analysis
- 📖 **Enhanced documentation** - Examples for all new features in SKILL.md

### Changed
- Updated API version to 2025-09-03 (latest)
- Improved error messages with actionable guidance

### Known Limitations
- Multipart upload (>20MB) not yet implemented - planned for P2
- Data source queries (2025-09-03 multi-source DBs) not yet supported - planned for P1

## [0.1.0] - 2026-02-03

### Added
- Initial release with retry logic and connection reuse
- Rate limit handling (429) with exponential backoff
- Server error retry (5xx)
- Workspace selection (personal/ronik)
- Basic CRUD operations (GET, POST, PATCH, DELETE)
- Convenience methods for pages, blocks, databases
