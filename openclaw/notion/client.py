#!/usr/bin/env python3
"""
Unified Notion API Client with retry logic and connection reuse

Features:
- Automatic retry with exponential backoff
- Connection pooling via requests.Session
- Rate limit handling (429)
- Server error retry (5xx)
- Configurable timeout and retries

Usage:
    from skills.notion.client import NotionClient
    
    client = NotionClient(workspace="personal")
    
    # GET request
    response = client.get("/v1/databases/xxx")
    
    # POST request
    response = client.post("/v1/pages", json={"parent": {...}, "properties": {...}})
"""

import time
import json
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any
import requests


class NotionClient:
    """Notion API client with retry logic and connection reuse"""
    
    BASE_URL = "https://api.notion.com"
    API_VERSION = "2025-09-03"  # Latest version
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace: str = "personal",
        max_retries: int = 3,
        timeout: int = 10,
        version: Optional[str] = None
    ):
        """
        Initialize Notion client
        
        Args:
            api_key: Notion API key (if None, loads from config)
            workspace: "personal" or "ronik" (loads corresponding key)
            max_retries: Maximum retry attempts on rate limit/server errors
            timeout: Request timeout in seconds
            version: API version (default: 2025-09-03)
        """
        self.api_key = api_key or self._load_api_key(workspace)
        self.max_retries = max_retries
        self.timeout = timeout
        self.api_version = version or self.API_VERSION
        
        # Create session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.api_version,
            "Content-Type": "application/json"
        })
    
    def _load_api_key(self, workspace: str) -> str:
        """Load Notion API key from standard location"""
        key_paths = {
            "personal": "~/.config/notion/api_key_daye_personal",
            "ronik": "~/.config/notion/api_key"
        }
        
        if workspace not in key_paths:
            raise ValueError(
                f"Unknown workspace: {workspace}. "
                f"Expected: {', '.join(key_paths.keys())}"
            )
        
        key_path = Path(key_paths[workspace]).expanduser()
        if not key_path.exists():
            raise FileNotFoundError(
                f"Notion API key not found: {key_path}\n"
                f"Expected workspace: {workspace}\n"
                f"See TOOLS.md for setup instructions"
            )
        
        api_key = key_path.read_text().strip()
        if not api_key:
            raise ValueError(f"Empty API key in {key_path}")
        
        return api_key
    
    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:
        """
        Execute request with exponential backoff retry
        
        Retries on:
        - 429 (rate limit) → Wait and retry
        - 500-503 (server errors) → Wait and retry
        - Network errors → Wait and retry
        
        Does NOT retry on:
        - 400 (bad request)
        - 401 (unauthorized)
        - 404 (not found)
        """
        kwargs.setdefault('timeout', self.timeout)
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Success
                if response.status_code < 400:
                    return response
                
                # Rate limit → retry with backoff
                if response.status_code == 429:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    if attempt < self.max_retries - 1:
                        print(f"⚠️  Rate limited (429). Retrying in {wait_time}s... (attempt {attempt+1}/{self.max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                
                # Server error (5xx) → retry
                if 500 <= response.status_code < 600:
                    wait_time = 2 ** attempt
                    if attempt < self.max_retries - 1:
                        print(f"⚠️  Server error {response.status_code}. Retrying in {wait_time}s... (attempt {attempt+1}/{self.max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                
                # Client error (4xx) → don't retry, raise immediately
                if 400 <= response.status_code < 500:
                    response.raise_for_status()
                
                # Unknown status code → raise
                response.raise_for_status()
                
            except requests.exceptions.HTTPError as e:
                # HTTPError from raise_for_status() → check if retriable
                if hasattr(e.response, 'status_code'):
                    status = e.response.status_code
                    # Don't retry client errors (4xx)
                    if 400 <= status < 500:
                        raise
                # Otherwise, let general exception handler retry
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⚠️  HTTP error: {e}. Retrying in {wait_time}s... (attempt {attempt+1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                raise
                
            except requests.exceptions.Timeout as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⚠️  Request timeout. Retrying in {wait_time}s... (attempt {attempt+1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Request timed out after {self.max_retries} attempts: {e}")
            
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⚠️  Network error: {e}. Retrying in {wait_time}s... (attempt {attempt+1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Request failed after {self.max_retries} attempts: {e}")
        
        # All retries exhausted (shouldn't reach here, but safety net)
        raise Exception(f"Request failed after {self.max_retries} attempts")
    
    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """GET request"""
        url = f"{self.BASE_URL}{path}"
        response = self._request_with_retry("GET", url, **kwargs)
        return response.json()
    
    def post(self, path: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """POST request"""
        url = f"{self.BASE_URL}{path}"
        response = self._request_with_retry("POST", url, json=json, **kwargs)
        return response.json()
    
    def patch(self, path: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """PATCH request"""
        url = f"{self.BASE_URL}{path}"
        response = self._request_with_retry("PATCH", url, json=json, **kwargs)
        return response.json()
    
    def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        """DELETE request"""
        url = f"{self.BASE_URL}{path}"
        response = self._request_with_retry("DELETE", url, **kwargs)
        return response.json() if response.content else {}
    
    # File upload methods (2025-09-03 API)
    
    def _upload_file(
        self,
        file_path: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload file to Notion using file upload API
        
        Steps:
        1. POST /v1/file_uploads - Get upload URL
        2. PUT to upload URL - Upload file content
        3. POST /v1/file_uploads/:id/complete - Finalize upload
        
        Args:
            file_path: Path to file to upload
            content_type: MIME type (auto-detected if None)
        
        Returns:
            file_id: Notion file ID for use in blocks
        
        Raises:
            ValueError: If file > 20MB (multipart not yet supported)
        """
        file_path_obj = Path(file_path).expanduser()
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size (20MB limit for single-part upload)
        file_size = file_path_obj.stat().st_size
        MAX_SIZE = 20 * 1024 * 1024  # 20 MB
        if file_size > MAX_SIZE:
            raise ValueError(
                f"File too large: {file_size / 1024 / 1024:.1f}MB > 20MB. "
                f"Multipart upload not yet implemented. "
                f"Please split file or use external hosting."
            )
        
        # Auto-detect content type
        if content_type is None:
            content_type, _ = mimetypes.guess_type(str(file_path_obj))
            if content_type is None:
                content_type = "application/octet-stream"
        
        filename = file_path_obj.name
        
        # Step 1: Create file upload
        print(f"📤 Uploading {filename} ({file_size / 1024:.1f}KB)...")
        create_response = self.post(
            "/v1/file_uploads",
            json={
                "name": filename,
                "content_type": content_type
            }
        )
        
        file_id = create_response["id"]
        upload_url = create_response["upload_url"]
        
        # Step 2: Upload file content to upload URL
        with open(file_path_obj, 'rb') as f:
            file_content = f.read()
        
        # Use raw PUT request (not through Notion API)
        upload_response = requests.put(
            upload_url,
            data=file_content,
            headers={"Content-Type": content_type},
            timeout=self.timeout
        )
        upload_response.raise_for_status()
        
        # Step 3: Complete upload
        complete_response = self.post(
            f"/v1/file_uploads/{file_id}/complete",
            json={}
        )
        
        print(f"✅ Uploaded: {filename} (file_id: {file_id})")
        return file_id
    
    def upload_and_attach_file(
        self,
        page_id: str,
        file_path: str,
        block_type: str = "file",
        content_type: Optional[str] = None,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file and attach as block to a page
        
        Args:
            page_id: Notion page ID to attach file to
            file_path: Path to file to upload
            block_type: "file" or "image" or "pdf" or "video"
            content_type: MIME type (auto-detected if None)
            caption: Optional caption for the file block
        
        Returns:
            Block object representing the attached file
        
        Example:
            notion.upload_and_attach_file(
                page_id="xxx",
                file_path="~/report.pdf",
                block_type="pdf",
                caption="Monthly report"
            )
        """
        # Upload file
        file_id = self._upload_file(file_path, content_type)
        
        # Create file block
        filename = Path(file_path).expanduser().name
        
        # Build block structure
        block_data = {
            "type": block_type,
            block_type: {
                "type": "file",
                "file": {
                    "type": "file",
                    "file_id": file_id,
                    "name": filename
                }
            }
        }
        
        # Add caption if provided
        if caption:
            block_data[block_type]["caption"] = [
                {"type": "text", "text": {"content": caption}}
            ]
        
        # Append block to page
        result = self.append_blocks(page_id, [block_data])
        
        print(f"✅ Attached {block_type} block to page {page_id}")
        return result
    
    # Archive/Restore methods
    
    def archive_page(self, page_id: str) -> Dict[str, Any]:
        """
        Archive a page (soft delete)
        
        Args:
            page_id: Notion page ID
        
        Returns:
            Updated page object with archived=True
        """
        return self.patch(f"/v1/pages/{page_id}", json={"archived": True})
    
    def restore_page(self, page_id: str) -> Dict[str, Any]:
        """
        Restore an archived page
        
        Args:
            page_id: Notion page ID
        
        Returns:
            Updated page object with archived=False
        """
        return self.patch(f"/v1/pages/{page_id}", json={"archived": False})
    
    def archive_block(self, block_id: str) -> Dict[str, Any]:
        """
        Archive a block (soft delete)
        
        Args:
            block_id: Notion block ID
        
        Returns:
            Updated block object with archived=True
        """
        return self.patch(f"/v1/blocks/{block_id}", json={"archived": True})
    
    def restore_block(self, block_id: str) -> Dict[str, Any]:
        """
        Restore an archived block
        
        Args:
            block_id: Notion block ID
        
        Returns:
            Updated block object with archived=False
        """
        return self.patch(f"/v1/blocks/{block_id}", json={"archived": False})
    
    # Convenience methods for common operations
    
    def get_database(self, database_id: str) -> Dict[str, Any]:
        """Retrieve database metadata (2025-09-03: returns data sources list)"""
        return self.get(f"/v1/databases/{database_id}")
    
    def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: Dict[str, Dict],
        description: Optional[str] = None,
        icon: Optional[Dict] = None,
        cover: Optional[Dict] = None,
        is_inline: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new database
        
        Args:
            parent_page_id: Page ID to create database in
            title: Database title
            properties: Database schema (property definitions)
            description: Optional database description
            icon: Optional icon (emoji or external URL)
            cover: Optional cover image
            is_inline: If True, creates inline database; if False, full-page database
        
        Returns:
            Created database object
        
        Example:
            # Create a simple task database
            db = notion.create_database(
                parent_page_id="page_id",
                title="Tasks",
                properties={
                    "Name": {"title": {}},  # Title property (required)
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
                    }
                },
                icon={"type": "emoji", "emoji": "✅"},
                is_inline=False
            )
        """
        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
            "is_inline": is_inline
        }
        
        if description:
            payload["description"] = [{"type": "text", "text": {"content": description}}]
        if icon:
            payload["icon"] = icon
        if cover:
            payload["cover"] = cover
        
        return self.post("/v1/databases", json=payload)
    
    def update_database(
        self,
        database_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Dict]] = None,
        icon: Optional[Dict] = None,
        cover: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update database schema or metadata
        
        Args:
            database_id: Database ID to update
            title: New title (optional)
            description: New description (optional)
            properties: Property schema updates (optional)
            icon: New icon (optional)
            cover: New cover (optional)
        
        Returns:
            Updated database object
        
        Example:
            # Add a new property to existing database
            db = notion.update_database(
                "db_id",
                properties={
                    "Assignee": {"people": {}}  # Add people property
                }
            )
            
            # Rename database and update icon
            db = notion.update_database(
                "db_id",
                title="Updated Tasks",
                icon={"type": "emoji", "emoji": "🎯"}
            )
            
            # Update select property options
            db = notion.update_database(
                "db_id",
                properties={
                    "Status": {
                        "status": {
                            "options": [
                                {"name": "Blocked", "color": "red"},  # Add new option
                                {"name": "Done", "color": "green"}
                            ]
                        }
                    }
                }
            )
        
        Note: Property updates are merged, not replaced. To remove a property,
              set it to null in the properties dict.
        """
        payload = {}
        
        if title is not None:
            payload["title"] = [{"type": "text", "text": {"content": title}}]
        if description is not None:
            payload["description"] = [{"type": "text", "text": {"content": description}}]
        if properties is not None:
            payload["properties"] = properties
        if icon is not None:
            payload["icon"] = icon
        if cover is not None:
            payload["cover"] = cover
        
        if not payload:
            raise ValueError("At least one update parameter must be provided")
        
        return self.patch(f"/v1/databases/{database_id}", json=payload)
    
    def query_database(
        self,
        database_id: str,
        filter: Optional[Dict] = None,
        sorts: Optional[list] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        data_source_index: int = 0
    ) -> Dict[str, Any]:
        """
        Query database with automatic routing (2025-09-03 compatible)
        
        This method automatically detects if the database has data_sources
        and routes to the appropriate endpoint:
        - If data_sources present (2025-09-03): Uses /v1/data_sources/{id}/query
        - If no data_sources (legacy): Fallback to /v1/databases/{id}/query
        
        Args:
            database_id: Database ID to query
            filter: Filter conditions (Notion filter syntax)
            sorts: Sort conditions
            start_cursor: Pagination cursor
            page_size: Number of results per page (max 100)
            data_source_index: Which data source to use (default: 0 = first)
        
        Returns:
            Query results with pages and pagination info
        
        Example:
            # Simple query (auto-routes)
            results = notion.query_database(
                "db_id",
                filter={"property": "Status", "status": {"equals": "Active"}}
            )
            
            # With pagination
            results = notion.query_database(
                "db_id",
                filter={...},
                page_size=50,
                start_cursor=prev_cursor
            )
        
        Note: For multi-source databases, use data_source_index to select source,
              or call query_data_source() directly for more control.
        """
        # Try to get database metadata to check for data_sources
        try:
            db = self.get_database(database_id)
            data_sources = db.get("data_sources", [])
            
            if data_sources:
                # 2025-09-03 API: Use data source endpoint
                if data_source_index >= len(data_sources):
                    raise ValueError(
                        f"data_source_index {data_source_index} out of range. "
                        f"Database has {len(data_sources)} data source(s)."
                    )
                
                data_source_id = data_sources[data_source_index]["id"]
                
                # Route to data source endpoint
                return self.query_data_source(
                    data_source_id,
                    filter=filter,
                    sorts=sorts,
                    start_cursor=start_cursor,
                    page_size=page_size
                )
            else:
                # No data sources → fallback to legacy endpoint
                # This handles older API versions or edge cases
                payload = {}
                if filter:
                    payload["filter"] = filter
                if sorts:
                    payload["sorts"] = sorts
                if start_cursor:
                    payload["start_cursor"] = start_cursor
                if page_size:
                    if page_size > 100:
                        raise ValueError("page_size cannot exceed 100")
                    payload["page_size"] = page_size
                
                return self.post(f"/v1/databases/{database_id}/query", json=payload)
                
        except ValueError as e:
            # ValueError = user error (bad params), don't fallback
            raise
        except Exception as e:
            # Network/auth error → try legacy endpoint as fallback
            # This maintains backward compatibility with existing code
            print(f"⚠️  Could not fetch database metadata: {e}")
            print(f"⚠️  Falling back to legacy endpoint /v1/databases/{database_id}/query")
            
            payload = {}
            if filter:
                payload["filter"] = filter
            if sorts:
                payload["sorts"] = sorts
            if start_cursor:
                payload["start_cursor"] = start_cursor
            if page_size:
                if page_size > 100:
                    raise ValueError("page_size cannot exceed 100")
                payload["page_size"] = page_size
            
            return self.post(f"/v1/databases/{database_id}/query", json=payload)
    
    def query_data_source(
        self,
        data_source_id: str,
        filter: Optional[Dict] = None,
        sorts: Optional[list] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Query a data source (2025-09-03 API for multi-source databases)
        
        Args:
            data_source_id: Data source ID (from database.data_sources[])
            filter: Filter conditions (same syntax as query_database)
            sorts: Sort conditions
            start_cursor: Pagination cursor
            page_size: Number of results per page (max 100)
        
        Returns:
            Query results with pages and pagination info
        
        Example:
            # Get database metadata to find data source IDs
            db = notion.get_database("db_id")
            data_source_id = db["data_sources"][0]["id"]
            
            # Query the data source
            results = notion.query_data_source(
                data_source_id,
                filter={"property": "Status", "status": {"equals": "Active"}},
                sorts=[{"property": "Created", "direction": "descending"}],
                page_size=50
            )
        """
        payload = {}
        if filter:
            payload["filter"] = filter
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if page_size:
            if page_size > 100:
                raise ValueError("page_size cannot exceed 100")
            payload["page_size"] = page_size
        
        return self.post(f"/v1/data_sources/{data_source_id}/query", json=payload)
    
    def query_database_v2(
        self,
        database_id: str,
        filter: Optional[Dict] = None,
        sorts: Optional[list] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        data_source_index: int = 0
    ) -> Dict[str, Any]:
        """
        Query database using data sources (2025-09-03 API)
        
        This is a convenience wrapper that:
        1. Fetches database metadata to get data_sources[]
        2. Selects data source by index (default: first source)
        3. Queries the data source
        
        Args:
            database_id: Database ID
            filter: Filter conditions
            sorts: Sort conditions
            start_cursor: Pagination cursor
            page_size: Number of results per page (max 100)
            data_source_index: Which data source to use (default: 0 = first)
        
        Returns:
            Query results
        
        Example:
            # Query first data source
            results = notion.query_database_v2("db_id", filter={...})
            
            # Query second data source (if database has multiple sources)
            results = notion.query_database_v2("db_id", filter={...}, data_source_index=1)
        """
        # Get database metadata to extract data source ID
        db = self.get_database(database_id)
        data_sources = db.get("data_sources", [])
        
        if not data_sources:
            raise ValueError(
                f"Database {database_id} has no data sources. "
                f"This may be a legacy database or API version mismatch. "
                f"Try using query_database() instead."
            )
        
        if data_source_index >= len(data_sources):
            raise ValueError(
                f"data_source_index {data_source_index} out of range. "
                f"Database has {len(data_sources)} data source(s)."
            )
        
        data_source_id = data_sources[data_source_index]["id"]
        
        return self.query_data_source(
            data_source_id,
            filter=filter,
            sorts=sorts,
            start_cursor=start_cursor,
            page_size=page_size
        )
    
    def create_page(self, parent: Dict, properties: Dict, children: Optional[list] = None) -> Dict[str, Any]:
        """Create a new page"""
        payload = {
            "parent": parent,
            "properties": properties
        }
        if children:
            payload["children"] = children
        
        return self.post("/v1/pages", json=payload)
    
    def update_page(self, page_id: str, properties: Dict) -> Dict[str, Any]:
        """Update page properties"""
        return self.patch(f"/v1/pages/{page_id}", json={"properties": properties})
    
    def get_page_property(
        self,
        page_id: str,
        property_id: str,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieve a specific page property (useful for paginated properties like rollup)
        
        Args:
            page_id: Page ID
            property_id: Property ID or property name
            start_cursor: Pagination cursor for large property values
            page_size: Number of items per page (for paginated properties)
        
        Returns:
            Property value with pagination info if applicable
        
        Example:
            # Get a simple property
            status = notion.get_page_property("page_id", "Status")
            print(status["status"]["name"])
            
            # Get a rollup property (may be paginated)
            rollup = notion.get_page_property("page_id", "Related Tasks")
            for item in rollup["results"]:
                print(item)
            
            # Paginate through large property
            cursor = None
            all_items = []
            while True:
                result = notion.get_page_property("page_id", "prop_id", start_cursor=cursor, page_size=50)
                all_items.extend(result.get("results", []))
                if not result.get("has_more"):
                    break
                cursor = result["next_cursor"]
        
        Note: For properties with large values (like relation, rollup), this endpoint
              returns paginated results. Use start_cursor to iterate through pages.
        """
        params = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        if page_size:
            if page_size > 100:
                raise ValueError("page_size cannot exceed 100")
            params["page_size"] = page_size
        
        return self.get(f"/v1/pages/{page_id}/properties/{property_id}", params=params)
    
    def append_blocks(self, block_id: str, children: list) -> Dict[str, Any]:
        """Append blocks to a page or block (batch up to 100)"""
        if len(children) > 100:
            raise ValueError(f"Cannot append more than 100 blocks at once (got {len(children)}). Use append_blocks_batch()")
        
        return self.patch(f"/v1/blocks/{block_id}/children", json={"children": children})
    
    def append_blocks_batch(self, block_id: str, children: list) -> list:
        """Append blocks in batches of 100 (Notion limit)"""
        BATCH_SIZE = 100
        results = []
        
        for i in range(0, len(children), BATCH_SIZE):
            batch = children[i:i+BATCH_SIZE]
            result = self.append_blocks(block_id, batch)
            results.append(result)
        
        return results
    
    def search(self, query: str = "", filter: Optional[Dict] = None, sort: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Search pages and databases
        
        Note: In 2025-09-03, filter["value"] should be "page" or "data_source" (not "database")
        """
        payload = {}
        if query:
            payload["query"] = query
        if filter:
            # Auto-convert "database" to "data_source" for 2025-09-03 compatibility
            if filter.get("value") == "database":
                filter = {**filter, "value": "data_source"}
            payload["filter"] = filter
        if sort:
            payload["sort"] = sort
        
        return self.post("/v1/search", json=payload)
    
    # Users API
    
    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve a user by ID
        
        Args:
            user_id: Notion user ID (UUID format)
        
        Returns:
            User object with name, avatar, type (person/bot)
        
        Example:
            user = notion.get_user("user_uuid")
            print(f"Name: {user['name']}")
            print(f"Type: {user['type']}")  # person or bot
        """
        return self.get(f"/v1/users/{user_id}")
    
    def list_users(
        self,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List all users in the workspace
        
        Args:
            start_cursor: Pagination cursor from previous response
            page_size: Number of results per page (max 100)
        
        Returns:
            Paginated list of users with has_more and next_cursor
        
        Example:
            # Get all users
            users = notion.list_users()
            for user in users["results"]:
                print(f"{user['name']} ({user['type']})")
            
            # Paginate through users
            cursor = None
            all_users = []
            while True:
                response = notion.list_users(start_cursor=cursor, page_size=50)
                all_users.extend(response["results"])
                if not response["has_more"]:
                    break
                cursor = response["next_cursor"]
        """
        params = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        if page_size:
            if page_size > 100:
                raise ValueError("page_size cannot exceed 100")
            params["page_size"] = page_size
        
        return self.get("/v1/users", params=params)
    
    def get_bot_info(self) -> Dict[str, Any]:
        """
        Get information about the bot user (the integration itself)
        
        Returns:
            Bot user object with name, avatar, type=bot
        
        Example:
            bot = notion.get_bot_info()
            print(f"Bot name: {bot['name']}")
            print(f"Bot ID: {bot['id']}")
        
        Note: This is equivalent to GET /v1/users/me
        """
        return self.get("/v1/users/me")


def create_client(workspace: str = "personal", **kwargs) -> NotionClient:
    """
    Factory function for creating NotionClient
    
    Usage:
        from skills.notion.client import create_client
        notion = create_client("personal")
    """
    return NotionClient(workspace=workspace, **kwargs)


# Example usage
if __name__ == "__main__":
    # Test connection
    client = NotionClient(workspace="personal")
    
    # Test search
    print("Testing Notion API connection...")
    results = client.search(query="", filter={"property": "object", "value": "database"})
    
    print(f"✅ Connection successful!")
    print(f"   Found {len(results.get('results', []))} databases")
    
    # Test rate limit handling (would need to make many rapid requests)
    # Not included here to avoid hitting actual rate limits
