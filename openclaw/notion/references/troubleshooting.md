# Troubleshooting

## "Notion API key not found"

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

## "Rate limited (429)"

**Cause:** Exceeded 3 requests/second.

**Fix:** Client automatically retries. If persistent, reduce request rate or batch operations.

## "Request timed out"

**Cause:** Network issue or Notion API slow.

**Fix:** Increase timeout:
```python
notion = NotionClient(workspace="personal", timeout=30)
```

## Migration Guide

See `docs/notion_integration_audit_2026-02-03.md` for detailed migration plan for all existing scripts.
