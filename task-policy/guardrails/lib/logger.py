#!/usr/bin/env python3
"""
Guardrails Logging
Track violations and bypasses for audit trail
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


# Log file paths
GUARDRAILS_DIR = Path.home() / ".clawdbot" / "guardrails"
VIOLATIONS_LOG = GUARDRAILS_DIR / "violations.jsonl"
GUARDRAILS_DIR.mkdir(parents=True, exist_ok=True)


def log_violation(
    session_id: str,
    violation_type: str,
    blocked: bool,
    details: Dict = None,
    user_response: str = None
):
    """
    Log a guardrails violation
    
    Args:
        session_id: Session identifier
        violation_type: "missing_task" | "missing_deliverable" | "validation_failed"
        blocked: True if work was blocked, False if warning only
        details: Additional context
        user_response: User's action ("approved", "declined", "bypassed", etc.)
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "violation": violation_type,
        "blocked": blocked,
        "user_response": user_response,
        "details": details or {}
    }
    
    # Append to JSONL
    with open(VIOLATIONS_LOG, 'a') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def log_bypass(
    session_id: str,
    reason: str,
    approver: str = "user"
):
    """
    Log a guardrails bypass
    
    Args:
        session_id: Session identifier
        reason: Reason for bypass
        approver: Who approved the bypass
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "violation": "bypass",
        "blocked": False,
        "user_response": "bypassed",
        "details": {
            "reason": reason,
            "approver": approver
        }
    }
    
    with open(VIOLATIONS_LOG, 'a') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def get_recent_violations(hours: int = 24) -> list:
    """
    Get violations from last N hours
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        List of violation entries
    """
    if not VIOLATIONS_LOG.exists():
        return []
    
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    violations = []
    with open(VIOLATIONS_LOG, 'r') as f:
        for line in f:
            entry = json.loads(line)
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time > cutoff:
                violations.append(entry)
    
    return violations


def generate_daily_report() -> str:
    """
    Generate daily audit report from violations log
    
    Returns:
        Markdown formatted report
    """
    violations = get_recent_violations(hours=24)
    
    if not violations:
        return "## Guardrails Daily Report\n\nNo violations in last 24 hours. ✅"
    
    # Count by type
    by_type = {}
    by_status = {"blocked": 0, "warned": 0, "bypassed": 0}
    
    for v in violations:
        vtype = v["violation"]
        by_type[vtype] = by_type.get(vtype, 0) + 1
        
        if v["blocked"]:
            by_status["blocked"] += 1
        elif v.get("user_response") == "bypassed":
            by_status["bypassed"] += 1
        else:
            by_status["warned"] += 1
    
    report = f"""## Guardrails Daily Report
**Period:** Last 24 hours  
**Total Violations:** {len(violations)}

### Summary
- ❌ Blocked: {by_status['blocked']}
- ⚠️  Warned: {by_status['warned']}
- 🔓 Bypassed: {by_status['bypassed']}

### By Type
"""
    
    for vtype, count in by_type.items():
        report += f"- {vtype}: {count}\n"
    
    report += "\n### Recent Events\n"
    
    # Show last 5 violations
    for v in violations[-5:]:
        timestamp = v["timestamp"][:16]  # YYYY-MM-DD HH:MM
        status = "🔓 BYPASS" if v.get("user_response") == "bypassed" else ("❌ BLOCK" if v["blocked"] else "⚠️  WARN")
        report += f"- **{timestamp}** {status} - {v['violation']} (session: ...{v['session_id'][-8:]})\n"
    
    return report


if __name__ == "__main__":
    # Test logging
    print("=== Guardrails Logger Test ===\n")
    
    # Log a violation
    log_violation(
        session_id="agent:main:subagent:test-123",
        violation_type="missing_task",
        blocked=True,
        user_response="declined"
    )
    print("✅ Logged violation: missing_task")
    
    # Log a bypass
    log_bypass(
        session_id="agent:main:subagent:test-456",
        reason="Emergency production fix"
    )
    print("✅ Logged bypass")
    
    # Get recent violations
    recent = get_recent_violations(hours=1)
    print(f"\n📊 Recent violations (last hour): {len(recent)}")
    
    # Generate report
    report = generate_daily_report()
    print("\n" + report)
