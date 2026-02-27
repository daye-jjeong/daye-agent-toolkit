#!/usr/bin/env python3
"""
Unit tests for Notion client

Run with: python3 -m pytest skills/notion/test_client.py -v
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import json

from skills.notion.client import NotionClient


class TestNotionClientFileUpload(unittest.TestCase):
    """Test file upload functionality"""
    
    def setUp(self):
        """Set up test client with mocked API key"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    @patch('skills.notion.client.Path.exists', return_value=True)
    @patch('skills.notion.client.Path.stat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test file content')
    @patch('requests.put')
    def test_upload_file_single_part(self, mock_put, mock_file, mock_stat, mock_exists):
        """Test single-part file upload (<20MB)"""
        # Mock file size (1 MB)
        mock_stat.return_value = Mock(st_size=1024 * 1024)
        
        # Mock Notion API responses
        self.client.post = Mock(side_effect=[
            # Step 1: Create upload
            {
                "id": "test_file_id",
                "upload_url": "https://upload.example.com/test"
            },
            # Step 3: Complete upload
            {"id": "test_file_id", "status": "completed"}
        ])
        
        # Mock PUT upload
        mock_put.return_value = Mock(status_code=200)
        mock_put.return_value.raise_for_status = Mock()
        
        # Execute
        file_id = self.client._upload_file("test.pdf")
        
        # Assertions
        self.assertEqual(file_id, "test_file_id")
        self.assertEqual(self.client.post.call_count, 2)
        
        # Check first call (create upload)
        first_call = self.client.post.call_args_list[0]
        self.assertEqual(first_call[0][0], "/v1/file_uploads")
        self.assertEqual(first_call[1]["json"]["name"], "test.pdf")
        self.assertEqual(first_call[1]["json"]["content_type"], "application/pdf")
        
        # Check PUT call (upload content)
        mock_put.assert_called_once()
        self.assertEqual(mock_put.call_args[0][0], "https://upload.example.com/test")
        self.assertEqual(mock_put.call_args[1]["data"], b'test file content')
        
        # Check complete call
        second_call = self.client.post.call_args_list[1]
        self.assertEqual(second_call[0][0], "/v1/file_uploads/test_file_id/complete")
    
    @patch('skills.notion.client.Path.exists', return_value=True)
    @patch('skills.notion.client.Path.stat')
    def test_upload_file_too_large(self, mock_stat, mock_exists):
        """Test file upload fails for >20MB files"""
        # Mock file size (25 MB)
        mock_stat.return_value = Mock(st_size=25 * 1024 * 1024)
        
        # Execute and expect error
        with self.assertRaises(ValueError) as context:
            self.client._upload_file("large_file.pdf")
        
        self.assertIn("File too large", str(context.exception))
        self.assertIn("Multipart upload not yet implemented", str(context.exception))
    
    @patch('skills.notion.client.Path.exists', return_value=False)
    def test_upload_file_not_found(self, mock_exists):
        """Test file upload fails for missing file"""
        with self.assertRaises(FileNotFoundError):
            self.client._upload_file("missing.pdf")
    
    @patch('skills.notion.client.Path.exists', return_value=True)
    @patch('skills.notion.client.Path.stat')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test content')
    @patch('requests.put')
    def test_upload_and_attach_file(self, mock_put, mock_file, mock_stat, mock_exists):
        """Test uploading and attaching file as block"""
        # Mock file size
        mock_stat.return_value = Mock(st_size=1024)
        
        # Mock upload
        self.client._upload_file = Mock(return_value="uploaded_file_id")
        self.client.append_blocks = Mock(return_value={"object": "list", "results": []})
        
        # Execute
        result = self.client.upload_and_attach_file(
            page_id="page_123",
            file_path="report.pdf",
            block_type="pdf",
            caption="Test caption"
        )
        
        # Assertions
        self.client._upload_file.assert_called_once_with("report.pdf", None)
        
        # Check append_blocks call
        call_args = self.client.append_blocks.call_args
        self.assertEqual(call_args[0][0], "page_123")
        
        blocks = call_args[0][1]
        self.assertEqual(len(blocks), 1)
        
        block = blocks[0]
        self.assertEqual(block["type"], "pdf")
        self.assertEqual(block["pdf"]["file"]["file_id"], "uploaded_file_id")
        self.assertEqual(block["pdf"]["caption"][0]["text"]["content"], "Test caption")
    
    @patch('skills.notion.client.Path.exists', return_value=True)
    @patch('skills.notion.client.Path.stat')
    def test_content_type_detection(self, mock_stat, mock_exists):
        """Test automatic content type detection"""
        mock_stat.return_value = Mock(st_size=1024)
        
        test_cases = [
            ("file.pdf", "application/pdf"),
            ("file.jpg", "image/jpeg"),
            ("file.png", "image/png"),
            ("file.txt", "text/plain"),
            ("file.unknown", "application/octet-stream"),
        ]
        
        for filename, expected_type in test_cases:
            with patch('builtins.open', mock_open(read_data=b'test')):
                with patch('requests.put') as mock_put:
                    mock_put.return_value = Mock(status_code=200)
                    mock_put.return_value.raise_for_status = Mock()
                    
                    self.client.post = Mock(side_effect=[
                        {"id": "file_id", "upload_url": "http://test.com"},
                        {"id": "file_id"}
                    ])
                    
                    self.client._upload_file(filename)
                    
                    # Check content type in first POST call
                    first_call = self.client.post.call_args_list[0]
                    actual_type = first_call[1]["json"]["content_type"]
                    self.assertEqual(actual_type, expected_type, 
                                   f"Failed for {filename}: expected {expected_type}, got {actual_type}")


class TestNotionClientArchive(unittest.TestCase):
    """Test archive/restore functionality"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
        
        self.client.patch = Mock()
    
    def test_archive_page(self):
        """Test archiving a page"""
        self.client.patch.return_value = {"id": "page_123", "archived": True}
        
        result = self.client.archive_page("page_123")
        
        self.client.patch.assert_called_once_with(
            "/v1/pages/page_123",
            json={"archived": True}
        )
        self.assertTrue(result["archived"])
    
    def test_restore_page(self):
        """Test restoring an archived page"""
        self.client.patch.return_value = {"id": "page_123", "archived": False}
        
        result = self.client.restore_page("page_123")
        
        self.client.patch.assert_called_once_with(
            "/v1/pages/page_123",
            json={"archived": False}
        )
        self.assertFalse(result["archived"])
    
    def test_archive_block(self):
        """Test archiving a block"""
        self.client.patch.return_value = {"id": "block_456", "archived": True}
        
        result = self.client.archive_block("block_456")
        
        self.client.patch.assert_called_once_with(
            "/v1/blocks/block_456",
            json={"archived": True}
        )
        self.assertTrue(result["archived"])
    
    def test_restore_block(self):
        """Test restoring an archived block"""
        self.client.patch.return_value = {"id": "block_456", "archived": False}
        
        result = self.client.restore_block("block_456")
        
        self.client.patch.assert_called_once_with(
            "/v1/blocks/block_456",
            json={"archived": False}
        )
        self.assertFalse(result["archived"])


class TestNotionClientRetry(unittest.TestCase):
    """Test retry logic"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal", max_retries=3)
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_retry_on_429(self, mock_sleep):
        """Test retry logic on rate limit (429)"""
        # Mock session request: fail twice, succeed on third
        mock_response_fail = Mock(status_code=429)
        mock_response_fail.raise_for_status = Mock(side_effect=Exception("Rate limited"))
        
        mock_response_success = Mock(status_code=200)
        mock_response_success.json.return_value = {"status": "ok"}
        
        self.client.session.request = Mock(side_effect=[
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ])
        
        # Execute
        result = self.client.get("/v1/pages/test")
        
        # Assertions
        self.assertEqual(self.client.session.request.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Sleep before retry 2 and 3
        self.assertEqual(result, {"status": "ok"})
    
    @patch('time.sleep')
    def test_no_retry_on_400(self, mock_sleep):
        """Test no retry on client error (400)"""
        mock_response = Mock(status_code=400)
        mock_response.raise_for_status = Mock(side_effect=Exception("Bad request"))
        
        self.client.session.request = Mock(return_value=mock_response)
        
        # Execute and expect immediate failure
        with self.assertRaises(Exception):
            self.client.get("/v1/pages/invalid")
        
        # Should not retry
        self.assertEqual(self.client.session.request.call_count, 1)
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_retry_on_500(self, mock_sleep):
        """Test retry on server error (500)"""
        mock_response_fail = Mock(status_code=500)
        mock_response_fail.raise_for_status = Mock(side_effect=Exception("Server error"))
        
        mock_response_success = Mock(status_code=200)
        mock_response_success.json.return_value = {"status": "ok"}
        
        self.client.session.request = Mock(side_effect=[
            mock_response_fail,
            mock_response_success
        ])
        
        # Execute
        result = self.client.get("/v1/pages/test")
        
        # Should retry once and succeed
        self.assertEqual(self.client.session.request.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)


class TestNotionClientWorkspace(unittest.TestCase):
    """Test workspace selection"""
    
    @patch('skills.notion.client.Path.exists', return_value=True)
    @patch('skills.notion.client.Path.read_text', return_value='personal_key_123')
    def test_load_personal_workspace(self, mock_read, mock_exists):
        """Test loading personal workspace API key"""
        client = NotionClient(workspace="personal")
        
        self.assertEqual(client.api_key, "personal_key_123")
        mock_read.assert_called_once()
    
    @patch('skills.notion.client.Path.exists', return_value=True)
    @patch('skills.notion.client.Path.read_text', return_value='work_key_456')
    def test_load_work_workspace(self, mock_read, mock_exists):
        """Test loading work workspace API key"""
        client = NotionClient(workspace="ronik")
        
        self.assertEqual(client.api_key, "work_key_456")
    
    def test_invalid_workspace(self):
        """Test error on invalid workspace"""
        with self.assertRaises(ValueError) as context:
            NotionClient(workspace="invalid")
        
        self.assertIn("Unknown workspace", str(context.exception))
    
    @patch('skills.notion.client.Path.exists', return_value=False)
    def test_missing_api_key(self, mock_exists):
        """Test error on missing API key file"""
        with self.assertRaises(FileNotFoundError) as context:
            NotionClient(workspace="personal")
        
        self.assertIn("Notion API key not found", str(context.exception))


class TestNotionClientDataSources(unittest.TestCase):
    """Test data source query methods (2025-09-03 API)"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    def test_query_data_source(self):
        """Test querying a data source directly"""
        self.client.post = Mock(return_value={
            "results": [{"id": "page_1"}],
            "has_more": False
        })
        
        result = self.client.query_data_source(
            "ds_123",
            filter={"property": "Status", "status": {"equals": "Active"}},
            sorts=[{"property": "Created", "direction": "descending"}],
            page_size=50
        )
        
        self.client.post.assert_called_once_with(
            "/v1/data_sources/ds_123/query",
            json={
                "filter": {"property": "Status", "status": {"equals": "Active"}},
                "sorts": [{"property": "Created", "direction": "descending"}],
                "page_size": 50
            }
        )
        self.assertEqual(len(result["results"]), 1)
    
    def test_query_data_source_pagination(self):
        """Test data source query with pagination"""
        self.client.post = Mock(return_value={
            "results": [{"id": "page_1"}],
            "has_more": True,
            "next_cursor": "cursor_abc"
        })
        
        result = self.client.query_data_source(
            "ds_123",
            start_cursor="prev_cursor",
            page_size=25
        )
        
        call_args = self.client.post.call_args[1]["json"]
        self.assertEqual(call_args["start_cursor"], "prev_cursor")
        self.assertEqual(call_args["page_size"], 25)
    
    def test_query_database_v2_single_source(self):
        """Test query_database_v2 with single data source"""
        # Mock get_database to return data source
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": [{"id": "ds_456", "type": "database"}]
        })
        
        # Mock query_data_source
        self.client.query_data_source = Mock(return_value={
            "results": [{"id": "page_1"}]
        })
        
        result = self.client.query_database_v2(
            "db_123",
            filter={"property": "Status", "status": {"equals": "Done"}}
        )
        
        # Should call query_data_source with first data source
        self.client.query_data_source.assert_called_once_with(
            "ds_456",
            filter={"property": "Status", "status": {"equals": "Done"}},
            sorts=None,
            start_cursor=None,
            page_size=None
        )
    
    def test_query_database_v2_multi_source(self):
        """Test query_database_v2 with multiple data sources"""
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": [
                {"id": "ds_1", "type": "database"},
                {"id": "ds_2", "type": "database"}
            ]
        })
        
        self.client.query_data_source = Mock(return_value={"results": []})
        
        # Query second data source
        self.client.query_database_v2("db_123", data_source_index=1)
        
        # Should use ds_2
        self.client.query_data_source.assert_called_once()
        call_args = self.client.query_data_source.call_args[0]
        self.assertEqual(call_args[0], "ds_2")
    
    def test_query_database_v2_no_data_sources(self):
        """Test error when database has no data sources"""
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": []
        })
        
        with self.assertRaises(ValueError) as context:
            self.client.query_database_v2("db_123")
        
        self.assertIn("has no data sources", str(context.exception))


class TestNotionClientQueryDatabaseAutoRoute(unittest.TestCase):
    """Test automatic routing in query_database() (2025-09-03 compatibility)"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    def test_query_database_auto_route_with_data_sources(self):
        """Test query_database automatically routes to data source endpoint"""
        # Mock get_database to return data sources
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": [{"id": "ds_456", "type": "database"}]
        })
        
        # Mock query_data_source
        self.client.query_data_source = Mock(return_value={
            "results": [{"id": "page_1"}],
            "has_more": False
        })
        
        # Call query_database (should auto-route)
        result = self.client.query_database(
            "db_123",
            filter={"property": "Status", "status": {"equals": "Active"}},
            sorts=[{"property": "Created", "direction": "ascending"}],
            page_size=50
        )
        
        # Verify it routed to query_data_source
        self.client.query_data_source.assert_called_once_with(
            "ds_456",
            filter={"property": "Status", "status": {"equals": "Active"}},
            sorts=[{"property": "Created", "direction": "ascending"}],
            start_cursor=None,
            page_size=50
        )
        self.assertEqual(result["results"][0]["id"], "page_1")
    
    def test_query_database_fallback_no_data_sources(self):
        """Test query_database falls back to legacy endpoint when no data sources"""
        # Mock get_database to return no data sources (legacy database)
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": []
        })
        
        # Mock legacy POST endpoint
        self.client.post = Mock(return_value={
            "results": [{"id": "page_2"}],
            "has_more": False
        })
        
        # Call query_database (should fallback to legacy)
        result = self.client.query_database(
            "db_123",
            filter={"property": "Status", "status": {"equals": "Done"}}
        )
        
        # Verify it used legacy endpoint
        self.client.post.assert_called_once_with(
            "/v1/databases/db_123/query",
            json={
                "filter": {"property": "Status", "status": {"equals": "Done"}}
            }
        )
        self.assertEqual(result["results"][0]["id"], "page_2")
    
    def test_query_database_fallback_on_get_error(self):
        """Test query_database falls back to legacy if get_database fails"""
        # Mock get_database to raise error (e.g., network issue, permissions)
        self.client.get_database = Mock(side_effect=Exception("Network error"))
        
        # Mock legacy POST endpoint
        self.client.post = Mock(return_value={
            "results": [{"id": "page_3"}],
            "has_more": False
        })
        
        # Call query_database (should catch error and fallback)
        with patch('builtins.print'):  # Suppress warning output
            result = self.client.query_database("db_123")
        
        # Verify it fell back to legacy endpoint
        self.client.post.assert_called_once_with(
            "/v1/databases/db_123/query",
            json={}
        )
        self.assertEqual(result["results"][0]["id"], "page_3")
    
    def test_query_database_multi_source_index(self):
        """Test query_database with multiple data sources using index"""
        # Mock get_database with multiple data sources
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": [
                {"id": "ds_1", "type": "database"},
                {"id": "ds_2", "type": "external_sync"}
            ]
        })
        
        # Mock query_data_source
        self.client.query_data_source = Mock(return_value={"results": []})
        
        # Query second data source
        self.client.query_database("db_123", data_source_index=1)
        
        # Verify it used ds_2
        call_args = self.client.query_data_source.call_args
        self.assertEqual(call_args[0][0], "ds_2")
    
    def test_query_database_index_out_of_range(self):
        """Test error when data source index is out of range"""
        # Mock get_database with single data source
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": [{"id": "ds_1", "type": "database"}]
        })
        
        # Try to access index 1 (only index 0 exists)
        with self.assertRaises(ValueError) as context:
            self.client.query_database("db_123", data_source_index=1)
        
        self.assertIn("out of range", str(context.exception))
        self.assertIn("has 1 data source", str(context.exception))
    
    def test_query_database_with_pagination(self):
        """Test query_database auto-routing with pagination parameters"""
        # Mock database with data sources
        self.client.get_database = Mock(return_value={
            "id": "db_123",
            "data_sources": [{"id": "ds_123", "type": "database"}]
        })
        
        # Mock query_data_source
        self.client.query_data_source = Mock(return_value={
            "results": [],
            "has_more": True,
            "next_cursor": "next_123"
        })
        
        # Query with pagination
        result = self.client.query_database(
            "db_123",
            start_cursor="prev_123",
            page_size=25
        )
        
        # Verify pagination params passed through
        call_args = self.client.query_data_source.call_args
        self.assertEqual(call_args[1]["start_cursor"], "prev_123")
        self.assertEqual(call_args[1]["page_size"], 25)
        self.assertTrue(result["has_more"])


class TestNotionClientUsers(unittest.TestCase):
    """Test Users API methods"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    def test_get_user(self):
        """Test retrieving a user by ID"""
        self.client.get = Mock(return_value={
            "id": "user_123",
            "name": "John Doe",
            "type": "person",
            "avatar_url": "https://example.com/avatar.jpg"
        })
        
        user = self.client.get_user("user_123")
        
        self.client.get.assert_called_once_with("/v1/users/user_123")
        self.assertEqual(user["name"], "John Doe")
        self.assertEqual(user["type"], "person")
    
    def test_list_users(self):
        """Test listing workspace users"""
        self.client.get = Mock(return_value={
            "results": [
                {"id": "user_1", "name": "Alice"},
                {"id": "user_2", "name": "Bob"}
            ],
            "has_more": False
        })
        
        users = self.client.list_users()
        
        self.client.get.assert_called_once_with("/v1/users", params={})
        self.assertEqual(len(users["results"]), 2)
    
    def test_list_users_with_pagination(self):
        """Test listing users with pagination parameters"""
        self.client.get = Mock(return_value={"results": [], "has_more": False})
        
        self.client.list_users(start_cursor="cursor_123", page_size=50)
        
        call_args = self.client.get.call_args[1]["params"]
        self.assertEqual(call_args["start_cursor"], "cursor_123")
        self.assertEqual(call_args["page_size"], 50)
    
    def test_get_bot_info(self):
        """Test retrieving bot/integration info"""
        self.client.get = Mock(return_value={
            "id": "bot_123",
            "name": "My Integration",
            "type": "bot"
        })
        
        bot = self.client.get_bot_info()
        
        self.client.get.assert_called_once_with("/v1/users/me")
        self.assertEqual(bot["type"], "bot")


class TestNotionClientDatabaseSchema(unittest.TestCase):
    """Test database create/update schema methods"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    def test_create_database(self):
        """Test creating a new database"""
        self.client.post = Mock(return_value={
            "id": "db_new",
            "title": [{"text": {"content": "Tasks"}}]
        })
        
        db = self.client.create_database(
            parent_page_id="page_123",
            title="Tasks",
            properties={
                "Name": {"title": {}},
                "Status": {"status": {"options": [{"name": "Done", "color": "green"}]}}
            },
            icon={"type": "emoji", "emoji": "✅"}
        )
        
        call_args = self.client.post.call_args[1]["json"]
        self.assertEqual(call_args["parent"]["page_id"], "page_123")
        self.assertEqual(call_args["title"][0]["text"]["content"], "Tasks")
        self.assertIn("Name", call_args["properties"])
        self.assertEqual(call_args["icon"]["emoji"], "✅")
    
    def test_create_database_inline(self):
        """Test creating inline database"""
        self.client.post = Mock(return_value={"id": "db_inline"})
        
        self.client.create_database(
            parent_page_id="page_123",
            title="Inline DB",
            properties={"Name": {"title": {}}},
            is_inline=True
        )
        
        call_args = self.client.post.call_args[1]["json"]
        self.assertTrue(call_args["is_inline"])
    
    def test_update_database_title(self):
        """Test updating database title"""
        self.client.patch = Mock(return_value={
            "id": "db_123",
            "title": [{"text": {"content": "Updated Title"}}]
        })
        
        db = self.client.update_database("db_123", title="Updated Title")
        
        call_args = self.client.patch.call_args[1]["json"]
        self.assertEqual(call_args["title"][0]["text"]["content"], "Updated Title")
    
    def test_update_database_properties(self):
        """Test updating database properties"""
        self.client.patch = Mock(return_value={"id": "db_123"})
        
        self.client.update_database(
            "db_123",
            properties={
                "Assignee": {"people": {}}
            }
        )
        
        call_args = self.client.patch.call_args[1]["json"]
        self.assertIn("Assignee", call_args["properties"])
    
    def test_update_database_no_params(self):
        """Test error when no update parameters provided"""
        with self.assertRaises(ValueError) as context:
            self.client.update_database("db_123")
        
        self.assertIn("At least one update parameter", str(context.exception))


class TestNotionClientPageProperty(unittest.TestCase):
    """Test page property retrieval"""
    
    def setUp(self):
        """Set up test client"""
        with patch.object(NotionClient, '_load_api_key', return_value='test_key'):
            self.client = NotionClient(workspace="personal")
    
    def test_get_page_property(self):
        """Test getting a simple page property"""
        self.client.get = Mock(return_value={
            "id": "prop_123",
            "type": "status",
            "status": {"name": "Done"}
        })
        
        prop = self.client.get_page_property("page_123", "Status")
        
        self.client.get.assert_called_once_with(
            "/v1/pages/page_123/properties/Status",
            params={}
        )
        self.assertEqual(prop["status"]["name"], "Done")
    
    def test_get_page_property_paginated(self):
        """Test getting paginated property (e.g., rollup)"""
        self.client.get = Mock(return_value={
            "results": [{"id": "item_1"}],
            "has_more": True,
            "next_cursor": "cursor_abc"
        })
        
        prop = self.client.get_page_property(
            "page_123",
            "prop_456",
            start_cursor="prev_cursor",
            page_size=50
        )
        
        call_args = self.client.get.call_args[1]["params"]
        self.assertEqual(call_args["start_cursor"], "prev_cursor")
        self.assertEqual(call_args["page_size"], 50)
        self.assertTrue(prop["has_more"])


if __name__ == "__main__":
    unittest.main()
