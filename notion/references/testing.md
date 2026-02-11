# Testing

## Run Tests

```bash
# Run all tests
python3 -m unittest skills.notion.test_client -v

# Run specific test class
python3 -m unittest skills.notion.test_client.TestNotionClientFileUpload -v

# Run specific test
python3 -m unittest skills.notion.test_client.TestNotionClientFileUpload.test_upload_file_single_part -v
```

## Test Coverage

**Current: 32 tests, 100% pass rate**

**v0.3.0 features (10 tests):**
- Data source queries (single/multi-source, pagination)
- Database v2 queries (auto data source lookup)
- Users API (get_user, list_users, bot_info, pagination)
- Database create (schema, properties, icon, inline)
- Database update (title, properties, validation)
- Page property retrieval (simple, paginated)

**v0.2.0 features (10 tests):**
- File upload (single-part <20MB)
- File size validation (>20MB error)
- File not found handling
- Content type auto-detection (PDF, JPG, PNG, TXT)
- Upload and attach to page
- Archive/restore pages
- Archive/restore blocks

**Core features (12 tests):**
- Retry logic (429 rate limit, 5xx server errors)
- No retry on 4xx client errors
- Workspace selection (personal/ronik)
- API key loading

## Manual Testing

```bash
# Test connection
python3 skills/notion/client.py

# Expected output:
# Testing Notion API connection...
# Connection successful!
#    Found X databases
```

## Writing New Tests

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
