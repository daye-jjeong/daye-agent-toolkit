# API Coverage

## Implemented Methods

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get(path)` | Any GET | Generic GET request |
| `post(path, json)` | Any POST | Generic POST request |
| `patch(path, json)` | Any PATCH | Generic PATCH request |
| `delete(path)` | Any DELETE | Generic DELETE request |
| `get_database(db_id)` | `/v1/databases/:id` | Retrieve database metadata |
| `query_database(db_id, filter, sorts)` | `/v1/databases/:id/query` | Query database (auto-routes to data source if available) |
| `query_data_source(ds_id, ...)` | `/v1/data_sources/:id/query` | Query data source (2025-09-03) |
| `query_database_v2(db_id, ...)` | `/v1/data_sources/:id/query` | Query database via data sources |
| `create_database(...)` | `/v1/databases` | Create new database |
| `update_database(db_id, ...)` | `/v1/databases/:id` | Update database schema |
| `create_page(parent, properties, children)` | `/v1/pages` | Create new page |
| `update_page(page_id, properties)` | `/v1/pages/:id` | Update page properties |
| `get_page_property(page_id, prop_id, ...)` | `/v1/pages/:id/properties/:property_id` | Get specific page property |
| `append_blocks(block_id, children)` | `/v1/blocks/:id/children` | Append blocks (max 100) |
| `append_blocks_batch(block_id, children)` | `/v1/blocks/:id/children` | Append blocks in batches |
| `search(query, filter, sort)` | `/v1/search` | Search pages/databases |
| `get_user(user_id)` | `/v1/users/:id` | Get user by ID |
| `list_users(...)` | `/v1/users` | List workspace users |
| `get_bot_info()` | `/v1/users/me` | Get bot/integration info |
| `upload_and_attach_file(...)` | `/v1/file_uploads` | Upload file and attach to page |
| `archive_page(page_id)` | `/v1/pages/:id` | Archive (soft delete) a page |
| `restore_page(page_id)` | `/v1/pages/:id` | Restore archived page |
| `archive_block(block_id)` | `/v1/blocks/:id` | Archive a block |
| `restore_block(block_id)` | `/v1/blocks/:id` | Restore archived block |

## Not Yet Implemented

- Multipart file upload (>20MB) - see `API_AUDIT.md`
- Comments (`create_comment()`, `get_comments()`)
- Webhook subscriptions

**Full gap analysis:** See `API_AUDIT.md` for detailed audit and implementation roadmap.

## Rate Limit Handling

The client automatically handles Notion's 3 req/sec rate limit:

- **On 429 error:** Waits 1s, 2s, 4s (exponential backoff) before retry
- **Max retries:** 3 attempts (configurable)
- **Fallback:** Raises exception after retries exhausted

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
