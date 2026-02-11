# Session Manager Operations

## Monitoring

### View Fallback Log

```bash
# Last 20 fallback decisions
tail -n 20 ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | jq

# Count fallbacks by error type
cat ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | \
  jq -r '.error_type' | sort | uniq -c

# Fallback rate for specific model
cat ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | \
  jq -r 'select(.original_model == "openai-codex/gpt-5.2")' | wc -l
```

### Alert Conditions

Consider alerting when:
- Fallback rate > 30% for any model in 1 hour window
- All models in chain fail (critical failure)
- Specific model consistently unavailable (>5 consecutive failures)

## Testing

Run the test suite:
```bash
cd /Users/dayejeong/clawd
python3 tests/test_session_fallback.py
```

**Test Coverage:**
- Error classification (429, timeout, unavailable)
- Single worker fallback logic
- Parallel workers with partial substitution
- Custom fallback order override
- Fallback decision logging
- All models fail scenario

## Configuration

### Default Fallback Order

Edit `DEFAULT_FALLBACK_ORDER` in `spawn_with_fallback.py`:
```python
DEFAULT_FALLBACK_ORDER = [
    "openai-codex/gpt-5.2",
    "anthropic/claude-sonnet-4-5",
    "google-gemini-3-pro",
    "anthropic/claude-haiku-4-5"
]
```

### Retry Parameters

Adjust defaults in function calls:
- `max_retries`: Number of retries per model (default: 3)
- `retry_delay`: Seconds between retries (default: 5)
- `timeout`: Command timeout in seconds (default: 30)

## Known Limitations

1. **Session ID Extraction:** Relies on parsing `clawdbot sessions spawn` output format
   - May break if output format changes
   - Consider using structured JSON output if available

2. **Log File Growth:** `fallback_decisions.jsonl` grows unbounded
   - Consider adding log rotation (e.g., weekly cleanup)
   - Add to session cleanup scripts

3. **Parallel Spawn:** Workers spawn sequentially, not truly in parallel
   - Could be optimized with async/concurrent execution
   - Current approach ensures ordered logging

## Future Enhancements

- [ ] Async/concurrent worker spawning
- [ ] Log rotation and archival
- [ ] Real-time fallback rate monitoring dashboard
- [ ] Auto-adjust fallback order based on historical success rates
- [ ] Integration with cost tracking (model usage analytics)
- [ ] Webhook notifications for critical fallback events

---

**Version:** 1.0
**Created:** 2026-02-04
**Last Updated:** 2026-02-04 16:37:46 KST
**Author:** Orchestrator Update Subagent
