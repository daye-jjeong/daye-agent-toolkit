#!/usr/bin/env python3
"""
Example: sessions_spawn wrapper with guardrails enforcement.
Uses Obsidian vault for task storage.
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guardrails.lib.gates import pre_work_gate, GuardrailsViolation
from triage.triage import handle_user_request


def spawn_with_guardrails(
    task: str,
    model: str,
    label: str = None,
    bypass_guardrails: bool = False,
    bypass_reason: str = None,
    auto_create_task: bool = True,
    **kwargs
) -> Dict:
    """
    Spawn subagent with guardrails enforcement.

    Args:
        task: Task description/request
        model: AI model to use
        label: Session label
        bypass_guardrails: Skip guardrails checks
        bypass_reason: Reason for bypass (required if bypass=True)
        auto_create_task: Auto-create Task via task-triage if missing
        **kwargs: Additional spawn parameters

    Returns:
        {
            "session_id": str,
            "gate_result": Dict,
            "task_created": bool,
            "task_ref": str | None
        }

    Raises:
        GuardrailsViolation: If work blocked by guardrails
    """
    import uuid
    session_id = f"agent:main:subagent:{uuid.uuid4()}"

    task_created = False
    task_ref = None

    # Step 1: Pre-work gate
    try:
        gate_result = pre_work_gate(
            task_description=task,
            session_id=session_id,
            bypass=bypass_guardrails,
            bypass_reason=bypass_reason,
            context=kwargs.get("context")
        )

        print(f"Pre-work gate: {gate_result['message']}")

        # Proceed to spawn
        print(f"Spawning subagent: {session_id}")
        print(f"   Model: {model}")
        print(f"   Label: {label}")

        return {
            "session_id": session_id,
            "gate_result": gate_result,
            "task_created": task_created,
            "task_ref": task_ref
        }

    except GuardrailsViolation as e:
        if auto_create_task and "Task required" in str(e):
            print(f"Guardrails blocked: {e}")
            print(f"Attempting auto-create Task via task-triage...")

            triage_result = handle_user_request(
                user_message=task,
                auto_approve=False
            )

            if triage_result.get("yaml_entry") and triage_result["yaml_entry"].get("id"):
                task_ref = triage_result["yaml_entry"]["id"]
                task_created = True

                print(f"Task created: {task_ref}")

                # Retry with Task reference
                updated_task = f"{task}\nTask: {task_ref}"

                gate_result = pre_work_gate(
                    task_description=updated_task,
                    session_id=session_id
                )

                print(f"Pre-work gate passed with new Task")
                print(f"Spawning subagent: {session_id}")

                return {
                    "session_id": session_id,
                    "gate_result": gate_result,
                    "task_created": task_created,
                    "task_ref": task_ref
                }
            else:
                print(f"User declined task creation - work blocked")
                raise
        else:
            print(f"Guardrails blocked: {e}")
            raise


def example_usage():
    """Example usage of guardrails-wrapped spawn"""

    print("=== Guardrails Spawn Examples ===\n")

    # Example 1: Trivial work (should pass)
    print("Example 1: Trivial work")
    try:
        result = spawn_with_guardrails(
            task="오늘 날씨 어때?",
            model="anthropic/claude-sonnet-4-5",
            label="weather-check"
        )
        print(f"  Session: {result['session_id']}")
        print()
    except GuardrailsViolation as e:
        print(f"  Blocked: {e}\n")

    # Example 2: Deliverable work with Task reference (should pass)
    print("Example 2: Deliverable work with Task reference")
    try:
        result = spawn_with_guardrails(
            task="AI 트렌드 분석 리포트 작성. Task: t-ronik-001",
            model="anthropic/claude-sonnet-4-5",
            label="ai-trends-analysis"
        )
        print(f"  Session: {result['session_id']}")
        print()
    except GuardrailsViolation as e:
        print(f"  Blocked: {e}\n")

    # Example 3: Deliverable work without Task (should block or auto-create)
    print("Example 3: Deliverable work without Task (auto-create disabled)")
    try:
        result = spawn_with_guardrails(
            task="가이드 문서 작성해줘",
            model="anthropic/claude-sonnet-4-5",
            label="guide-writing",
            auto_create_task=False
        )
        print(f"  Session: {result['session_id']}")
        print()
    except GuardrailsViolation as e:
        print(f"  Blocked (expected): {str(e)[:80]}...\n")

    # Example 4: Emergency bypass
    print("Example 4: Emergency bypass")
    try:
        result = spawn_with_guardrails(
            task="긴급 시스템 재시작",
            model="anthropic/claude-sonnet-4-5",
            label="emergency-restart",
            bypass_guardrails=True,
            bypass_reason="Production outage - critical fix"
        )
        print(f"  Session: {result['session_id']}")
        print()
    except GuardrailsViolation as e:
        print(f"  Blocked: {e}\n")


if __name__ == "__main__":
    example_usage()
