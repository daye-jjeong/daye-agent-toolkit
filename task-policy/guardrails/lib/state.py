#!/usr/bin/env python3
"""
Guardrails State File Management
Track work progress and gate checkpoints
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


# State directory
STATE_DIR = Path.home() / ".clawdbot" / "guardrails" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class GuardrailsState:
    """State schema for tracking work through gates"""
    session_id: str
    task_url: str | None
    task_id: str | None
    work_type: str  # "deliverable" | "trivial"
    gate_status: str  # "passed" | "warned" | "blocked"
    checkpoints: List[Dict]
    deliverables: List[Dict]
    bypass: Dict
    created_at: str
    updated_at: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


def create_state(
    session_id: str,
    task_url: Optional[str],
    task_id: Optional[str],
    work_type: str,
    gate_status: str = "passed"
) -> GuardrailsState:
    """
    Create new state file for a session
    
    Args:
        session_id: Session identifier
        task_url: Notion Task URL (if exists)
        task_id: Extracted Task ID
        work_type: "deliverable" | "trivial"
        gate_status: Initial gate status
        
    Returns:
        GuardrailsState object
    """
    now = datetime.now(timezone.utc).isoformat()
    
    state = GuardrailsState(
        session_id=session_id,
        task_url=task_url,
        task_id=task_id,
        work_type=work_type,
        gate_status=gate_status,
        checkpoints=[{
            "stage": "pre-work",
            "timestamp": now,
            "result": gate_status
        }],
        deliverables=[],
        bypass={
            "used": False,
            "reason": None,
            "approver": None
        },
        created_at=now,
        updated_at=now
    )
    
    # Save to file
    state_file = STATE_DIR / f"guardrails-{session_id}.json"
    with open(state_file, 'w') as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
    
    return state


def get_state(session_id: str) -> Optional[GuardrailsState]:
    """
    Load state from file
    
    Args:
        session_id: Session identifier
        
    Returns:
        GuardrailsState if exists, None otherwise
    """
    state_file = STATE_DIR / f"guardrails-{session_id}.json"
    
    if not state_file.exists():
        return None
    
    with open(state_file, 'r') as f:
        data = json.load(f)
    
    # Convert dict to GuardrailsState
    return GuardrailsState(**data)


def update_state(
    session_id: str,
    checkpoint: Optional[Dict] = None,
    deliverable: Optional[Dict] = None,
    gate_status: Optional[str] = None
) -> GuardrailsState:
    """
    Update existing state file
    
    Args:
        session_id: Session identifier
        checkpoint: New checkpoint to add
        deliverable: New deliverable to add
        gate_status: Updated gate status
        
    Returns:
        Updated GuardrailsState
    """
    state = get_state(session_id)
    if not state:
        raise ValueError(f"State not found for session: {session_id}")
    
    # Update fields
    if checkpoint:
        state.checkpoints.append(checkpoint)
    
    if deliverable:
        state.deliverables.append(deliverable)
    
    if gate_status:
        state.gate_status = gate_status
    
    state.updated_at = datetime.now(timezone.utc).isoformat()
    
    # Save
    state_file = STATE_DIR / f"guardrails-{session_id}.json"
    with open(state_file, 'w') as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
    
    return state


def finalize_state(session_id: str, final_status: str) -> GuardrailsState:
    """
    Finalize state on completion
    
    Args:
        session_id: Session identifier
        final_status: "passed" | "warned" | "blocked"
        
    Returns:
        Finalized GuardrailsState
    """
    now = datetime.now(timezone.utc).isoformat()
    
    return update_state(
        session_id,
        checkpoint={
            "stage": "post-work",
            "timestamp": now,
            "result": final_status
        },
        gate_status=final_status
    )


def archive_state(session_id: str):
    """Move state file to archive directory"""
    archive_dir = Path.home() / ".clawdbot" / "guardrails" / "state" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    state_file = STATE_DIR / f"guardrails-{session_id}.json"
    if state_file.exists():
        archive_file = archive_dir / f"guardrails-{session_id}.json"
        state_file.rename(archive_file)


if __name__ == "__main__":
    # Test state management
    print("=== State Management Test ===\n")
    
    # Create state
    test_session = "agent:main:subagent:test-123"
    state = create_state(
        session_id=test_session,
        task_url="https://notion.so/test",
        task_id="test123",
        work_type="deliverable"
    )
    print(f"Created state for: {test_session}")
    print(f"  Work type: {state.work_type}")
    print(f"  Gate status: {state.gate_status}")
    
    # Update state
    updated = update_state(
        test_session,
        checkpoint={"stage": "mid-work", "timestamp": datetime.now(timezone.utc).isoformat(), "result": "in-progress"}
    )
    print(f"\nUpdated state:")
    print(f"  Checkpoints: {len(updated.checkpoints)}")
    
    # Finalize
    final = finalize_state(test_session, "passed")
    print(f"\nFinalized state:")
    print(f"  Final status: {final.gate_status}")
    print(f"  Checkpoints: {len(final.checkpoints)}")
    
    # Cleanup
    (STATE_DIR / f"guardrails-{test_session}.json").unlink()
    print("\n✅ Test complete (cleaned up)")
