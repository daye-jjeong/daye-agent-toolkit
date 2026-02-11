#!/usr/bin/env python3
"""
Guardrails Gates - Pre-work and Post-work enforcement
Main integration points for session lifecycle.
Uses Obsidian vault for task storage (replaces Notion).
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.task_io import validate_task_path, extract_task_ref, save_deliverable, add_deliverable_link

from .classifier import classify_work, extract_task_url
from .validator import validate_task_ref as validate_task, validate_deliverables
from .state import create_state, update_state, finalize_state
from .deliverable_checker import check_deliverables, detect_created_files
from .vault_writer import upload_deliverable_to_notion, update_task_deliverables_section
from .logger import log_violation, log_bypass


class GuardrailsViolation(Exception):
    """Raised when guardrails check fails and work should be blocked"""
    pass


def pre_work_gate(
    task_description: str,
    session_id: str,
    bypass: bool = False,
    bypass_reason: str = None,
    context: Dict = None
) -> Dict:
    """
    Gate 1: Pre-work validation (BLOCKING)

    Call this BEFORE spawning a subagent to validate:
    1. Work is classified correctly
    2. Task reference exists for deliverable work
    3. Task is accessible in vault

    Args:
        task_description: Work request from user
        session_id: Session identifier
        bypass: If True, skip checks (log only)
        bypass_reason: Reason for bypass (required if bypass=True)
        context: Additional context (e.g., estimated_minutes)

    Returns:
        {
            "allowed": bool,
            "work_type": str,
            "task_url": str | None,  -- task file path or ID
            "task_id": str | None,
            "state_file": str,
            "action_required": str | None,
            "message": str
        }

    Raises:
        GuardrailsViolation: If work should be blocked
    """
    # Step 1: Check bypass
    if bypass:
        if not bypass_reason:
            raise ValueError("bypass_reason required when bypass=True")

        log_bypass(session_id, bypass_reason)

        # Still create state file for audit trail
        state = create_state(
            session_id=session_id,
            task_url=None,
            task_id=None,
            work_type="bypassed",
            gate_status="bypassed"
        )
        state.bypass = {
            "used": True,
            "reason": bypass_reason,
            "approver": "user"
        }

        return {
            "allowed": True,
            "work_type": "bypassed",
            "task_url": None,
            "task_id": None,
            "state_file": f"~/.clawdbot/guardrails/state/guardrails-{session_id}.json",
            "action_required": None,
            "message": f"Guardrails bypassed: {bypass_reason}"
        }

    # Step 2: Classify work
    classification = classify_work(task_description, context)
    work_type = classification["type"]

    # Step 3: If trivial, allow immediately
    if work_type == "trivial":
        state = create_state(
            session_id=session_id,
            task_url=None,
            task_id=None,
            work_type="trivial",
            gate_status="passed"
        )

        return {
            "allowed": True,
            "work_type": "trivial",
            "task_url": None,
            "task_id": None,
            "state_file": f"~/.clawdbot/guardrails/state/guardrails-{session_id}.json",
            "action_required": None,
            "message": f"Trivial work - no Task required ({classification['reasoning']})"
        }

    # Step 4: For deliverable work, check Task reference
    task_ref = extract_task_url(task_description)

    if not task_ref:
        # No Task reference found - this should be blocked
        log_violation(
            session_id=session_id,
            violation_type="missing_task",
            blocked=True,
            details={"classification": classification},
            user_response="blocked"
        )

        raise GuardrailsViolation(
            f"Task required for deliverable work. Classification: {classification['reasoning']}\n"
            f"Action: Create Task via task-triage or add 'Task: t-xxx-NNN' to request"
        )

    # Step 5: Validate Task accessibility
    validation = validate_task(task_ref)

    if not validation["accessible"]:
        log_violation(
            session_id=session_id,
            violation_type="task_not_accessible",
            blocked=True,
            details={"task_ref": task_ref, "error": validation["error"]},
            user_response="blocked"
        )

        raise GuardrailsViolation(
            f"Task not accessible: {validation['error']}\n"
            f"Ref: {task_ref}\n"
            f"Action: Check Task exists in vault (~/mingming-vault/projects/)"
        )

    # Step 6: All checks passed - create state and allow
    state = create_state(
        session_id=session_id,
        task_url=validation.get("path", task_ref),
        task_id=validation["task_id"],
        work_type="deliverable",
        gate_status="passed"
    )

    return {
        "allowed": True,
        "work_type": "deliverable",
        "task_url": validation.get("path", task_ref),
        "task_id": validation["task_id"],
        "state_file": f"~/.clawdbot/guardrails/state/guardrails-{session_id}.json",
        "action_required": None,
        "message": f"Pre-work gate passed - Task validated: {validation.get('title', 'N/A')}"
    }


def post_work_gate(
    session_id: str,
    final_output: str,
    created_files: list = None,
    auto_upload: bool = True,
    model: str = "unknown"
) -> Dict:
    """
    Gate 2: Post-work validation (WARNING -> BLOCKING)

    Call this AFTER subagent completes work to validate:
    1. Deliverables exist
    2. Deliverables are accessible (in vault or web URLs)
    3. Auto-save local files to vault if enabled

    Args:
        session_id: Session identifier
        final_output: Subagent final report/output
        created_files: List of file paths created during work
        auto_upload: If True, auto-save local files to vault
        model: AI model used (for footer)

    Returns:
        {
            "passed": bool,
            "deliverables": List[Dict],
            "uploaded": List[Dict],
            "action_required": str | None,
            "message": str
        }
    """
    from .state import get_state

    # Get state
    state = get_state(session_id)
    if not state:
        return {
            "passed": True,
            "deliverables": [],
            "uploaded": [],
            "action_required": None,
            "message": "No state found - assuming trivial work"
        }

    # Skip validation for trivial/bypassed work
    if state.work_type in ["trivial", "bypassed"]:
        finalize_state(session_id, "passed")
        return {
            "passed": True,
            "deliverables": [],
            "uploaded": [],
            "action_required": None,
            "message": f"{state.work_type.title()} work - no validation needed"
        }

    # Check deliverables
    check_result = check_deliverables(session_id, final_output, created_files)

    if not check_result["has_deliverables"]:
        # No deliverables found - WARNING
        log_violation(
            session_id=session_id,
            violation_type="missing_deliverable",
            blocked=False,
            details={"final_output_length": len(final_output)},
            user_response="warned"
        )

        update_state(
            session_id,
            checkpoint={
                "stage": "post-work",
                "timestamp": Path(__file__).stat().st_mtime,
                "result": "warned"
            },
            gate_status="warned"
        )

        return {
            "passed": False,
            "deliverables": [],
            "uploaded": [],
            "action_required": "upload_required",
            "message": "No deliverables found - please save results to vault Task"
        }

    # Check if all deliverables are accessible
    if check_result["all_accessible"]:
        for deliverable in check_result["deliverables"]:
            update_state(session_id, deliverable=deliverable)

        finalize_state(session_id, "passed")

        return {
            "passed": True,
            "deliverables": check_result["deliverables"],
            "uploaded": [],
            "action_required": None,
            "message": f"All deliverables accessible ({len(check_result['deliverables'])} found)"
        }

    # Has deliverables but some are local - try auto-save if enabled
    uploaded = []
    if auto_upload and state.task_url:
        for deliverable in check_result["deliverables"]:
            if not deliverable["verified"] and deliverable["type"] in ["file", "markdown_file"]:
                # Try to save to vault
                upload_result = upload_deliverable_to_notion(
                    file_path=deliverable["url"],
                    task_url=state.task_url,
                    task_id=state.task_id,
                    session_id=session_id,
                    model=model,
                    language="ko"
                )

                if upload_result["success"]:
                    uploaded.append({
                        "original_path": deliverable["url"],
                        "vault_path": upload_result["page_url"],
                        "task_id": upload_result["page_id"]
                    })
                    deliverable["url"] = upload_result["page_url"]
                    deliverable["verified"] = True

        # Update Task with new deliverable paths
        if uploaded:
            update_task_deliverables_section(
                task_id=state.task_id,
                deliverable_urls=[u["vault_path"] for u in uploaded]
            )

    # Re-check after upload
    all_verified = all(d["verified"] for d in check_result["deliverables"])

    if all_verified:
        finalize_state(session_id, "passed")

        return {
            "passed": True,
            "deliverables": check_result["deliverables"],
            "uploaded": uploaded,
            "action_required": None,
            "message": f"Auto-saved {len(uploaded)} deliverables to vault"
        }
    else:
        # Still has inaccessible deliverables - WARN
        log_violation(
            session_id=session_id,
            violation_type="deliverable_not_accessible",
            blocked=False,
            details={"validation": check_result["validation"]},
            user_response="warned"
        )

        update_state(session_id, gate_status="warned")

        return {
            "passed": False,
            "deliverables": check_result["deliverables"],
            "uploaded": uploaded,
            "action_required": "upload_required",
            "message": f"{check_result['validation']['local_count']} deliverables still local - manual save required"
        }


if __name__ == "__main__":
    # Test gates
    print("=== Guardrails Gates Test ===\n")

    # Test 1: Trivial work (should pass)
    print("Test 1: Trivial work")
    try:
        result = pre_work_gate(
            task_description="오늘 날씨 어때?",
            session_id="test-session-1"
        )
        print(f"  Result: {result['message']}")
    except GuardrailsViolation as e:
        print(f"  Blocked: {e}")

    # Test 2: Deliverable work without Task (should block)
    print("\nTest 2: Deliverable work without Task")
    try:
        result = pre_work_gate(
            task_description="AI 트렌드 리포트 작성해줘",
            session_id="test-session-2"
        )
        print(f"  Result: {result['message']}")
    except GuardrailsViolation as e:
        print(f"  Blocked: {e}")

    # Test 3: Bypass
    print("\nTest 3: Bypass")
    try:
        result = pre_work_gate(
            task_description="긴급 수정",
            session_id="test-session-3",
            bypass=True,
            bypass_reason="Production emergency"
        )
        print(f"  Result: {result['message']}")
    except GuardrailsViolation as e:
        print(f"  Blocked: {e}")

    print("\nGate tests complete")
