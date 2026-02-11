# Advanced Topics - Detailed Reference

## Performance

- **Pattern Matching:** <10ms per message (pure regex, no LLM calls)
- **Overhead:** Negligible (<1% of message processing time)
- **Memory:** <5MB (patterns cached at initialization)
- **Token Cost:** **Zero** (no external API calls)

## Language Support

Currently supports:
- English (en)
- Korean (ko)
- Chinese (zh) - partial support

To extend:
1. Add patterns in target language to `config.json`
2. Test with sample messages
3. Update `language_support` list

## External API Integration (Optional)

For advanced detection, enable HiveFence or similar service:

```json
{
  "external_api": {
    "enabled": true,
    "provider": "hivefence",
    "api_key_path": "~/.config/hivefence/api_key",
    "timeout_seconds": 2
  }
}
```

**Note:** Currently a placeholder. Implementation requires:
1. API client for chosen provider
2. Fallback to local patterns on timeout
3. Cost/latency considerations

## Security Considerations

### What Prompt Guard Does

- Detects known injection patterns
- Blocks obvious jailbreak attempts
- Logs all detections for audit
- Alerts on critical threats

### What Prompt Guard Does NOT Do

- Cannot detect novel/zero-day attacks
- Does not analyze semantic meaning (no LLM)
- Does not check URLs against threat intelligence
- Does not sandbox or execute code analysis

### Defense in Depth

Prompt Guard is **Layer 1** of defense. Other layers:

- **Layer 2:** Agent behavior constraints (AGENTS.md policies)
- **Layer 3:** Tool execution approvals (approval guardrails)
- **Layer 4:** System-level sandboxing (exec restrictions)
- **Layer 5:** Audit logging (message-backup system)

## Future Enhancements

1. **ML-based Detection**
   - Train classifier on labeled injection examples
   - Semantic analysis of intent
   - Anomaly detection

2. **URL Threat Intelligence**
   - Check extracted URLs against threat feeds
   - Phishing domain detection
   - Homograph attack prevention

3. **Gateway Plugin**
   - Native integration at gateway level
   - Pre-queue message filtering
   - Zero agent overhead

4. **Adaptive Thresholds**
   - Learn from false positives/negatives
   - User-specific sensitivity
   - Time-based rules (stricter at night)

5. **Pattern Auto-update**
   - Fetch latest patterns from central repo
   - Community-contributed rules
   - Versioned pattern releases
