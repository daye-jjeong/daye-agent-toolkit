#!/usr/bin/env python3
"""
Agent OS Orchestrator - Main Execution Engine

Coordinates all Agent OS components:
1. Confirmation Gates (Gate 1: Plan, Gate 2: Budget)
2. Model Selection (Complexity-based auto-selection)
3. Subagent Spawning (With fallback/retry)
4. Execution Tracking (Checkpoints, logging)
5. Dissolution (Cleanup, archive, metrics)

Implements AGENTS.md § 2 Session Protection Policy, § 2.5 gates, § 2.6 checkpoints, § 2.7 reapproval.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import Agent OS components
from .gates import (
    format_plan_confirmation,
    format_budget_confirmation,
    check_approval,
    ask_approval
)
from .model_selector import (
    TaskComplexity,
    classify_task_complexity,
    select_model_for_task,
    select_models_for_plan
)
from .agent_templates import resolve_subtask_template
from .agent_workspace import (
    generate_run_id,
    create_workspace,
    write_instructions,
    update_status,
    read_status,
    collect_outbox,
    list_agent_workspaces,
    cleanup_run,
    write_execution_summary,
)

# Session manager import (optional — may be removed)
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../session_manager'))
try:
    from spawn_with_fallback import spawn_subagent_with_retry
except ImportError:
    spawn_subagent_with_retry = None


class WorkSize:
    """Work size classification per AGENTS.md § 2.7"""
    TRIVIAL = "trivial"  # <2 min, no deliverable
    SMALL = "small"      # 2-10 min, 5K-20K tokens
    MEDIUM = "medium"    # 10-45 min, 20K-100K tokens
    LARGE = "large"      # 45 min - 3 hr, 100K-500K tokens
    EPIC = "epic"        # 3+ hr, 500K+ tokens


def classify_work_size(
    eta_min: int,
    tokens_in_k: int,
    has_deliverable: bool
) -> str:
    """
    Classify work size based on ETA and token count

    Args:
        eta_min: Estimated time in minutes
        tokens_in_k: Estimated input tokens in thousands
        has_deliverable: Whether work produces deliverable

    Returns:
        WorkSize constant
    """
    # Trivial: <2 min, no deliverable
    if eta_min < 2 and not has_deliverable:
        return WorkSize.TRIVIAL

    # Small: 2-10 min OR <20K tokens
    if eta_min <= 10 or tokens_in_k < 20:
        return WorkSize.SMALL

    # Medium: 10-45 min OR 20K-100K tokens
    if eta_min <= 45 or tokens_in_k < 100:
        return WorkSize.MEDIUM

    # Large: 45 min - 3 hr OR 100K-500K tokens
    if eta_min <= 180 or tokens_in_k < 500:
        return WorkSize.LARGE

    # Epic: 3+ hr OR 500K+ tokens
    return WorkSize.EPIC


def estimate_cost(tokens_in_k: int, tokens_out_k: int) -> float:
    """
    Estimate cost in USD based on GPT-4 pricing

    Args:
        tokens_in_k: Input tokens in thousands
        tokens_out_k: Output tokens in thousands

    Returns:
        Estimated cost in USD

    Pricing (GPT-4 reference):
    - Input: $0.03 per 1K tokens
    - Output: $0.06 per 1K tokens
    """
    cost_in = tokens_in_k * 0.03
    cost_out = tokens_out_k * 0.06
    return cost_in + cost_out


def run_confirmation_gates(
    title: str,
    goal: str,
    steps: List[str],
    deliverable: str,
    eta_min: int,
    tokens_in_k: int,
    tokens_out_k: int,
    work_size: str,
    interactive: bool = True
) -> Tuple[bool, str]:
    """
    Execute confirmation gates (Gate 1 and Gate 2 if needed)

    Args:
        title: Work title
        goal: 1-line goal description
        steps: List of key steps (will show first 3)
        deliverable: Deliverable description + destination
        eta_min: Estimated time in minutes
        tokens_in_k: Estimated input tokens in thousands
        tokens_out_k: Estimated output tokens in thousands
        work_size: Work size classification (from WorkSize)
        interactive: If True, prompts for user input; if False, returns gate messages

    Returns:
        (approved: bool, message: str)
    """
    # Gate 1: Plan Confirmation (ALL non-trivial work)
    if work_size == WorkSize.TRIVIAL:
        print("⏭️  Trivial work - skipping confirmation gates")
        return True, "Trivial work (gates skipped)"

    gate1_msg = format_plan_confirmation(
        title, goal, steps, deliverable, eta_min, tokens_in_k, tokens_out_k
    )

    if interactive:
        print("\n" + "="*60)
        print("🚦 GATE 1: Plan Confirmation")
        print("="*60)
        print(gate1_msg)

        try:
            resp1 = input("\n> ")
            if not check_approval(resp1):
                return False, "Gate 1: User declined"
        except (EOFError, KeyboardInterrupt):
            return False, "Gate 1: User timeout/cancel"
    else:
        # Non-interactive mode: return gate message for user to review
        return False, gate1_msg

    # Gate 2: Token Budget Confirmation (Medium+ work only)
    if work_size in [WorkSize.MEDIUM, WorkSize.LARGE, WorkSize.EPIC]:
        cost_usd = estimate_cost(tokens_in_k, tokens_out_k)
        gate2_msg = format_budget_confirmation(eta_min, tokens_in_k, tokens_out_k, cost_usd)

        if interactive:
            print("\n" + "="*60)
            print("🚦 GATE 2: Token Budget Confirmation")
            print("="*60)
            print(gate2_msg)

            try:
                resp2 = input("\n> ")
                if not check_approval(resp2):
                    return False, "Gate 2: User declined (budget)"
            except (EOFError, KeyboardInterrupt):
                return False, "Gate 2: User timeout/cancel"
        else:
            return False, gate2_msg

    return True, "All gates approved"


# ─── Phase 4: Dissolution ────────────────────────────────────────────────────

def _run_dissolution_phase(
    run_id: str,
    execution_log: List[Dict],
    workspace_root: Optional[str] = None,
    archive: bool = True,
) -> Dict:
    """
    Phase 4: Post-execution cleanup, archival, and metrics collection.

    1. Verify all agent outboxes have deliverables
    2. Write execution_summary.json
    3. Clean up workspace/ scratch dirs (preserve inbox/outbox)
    4. Mark as archived

    Args:
        run_id: Run identifier
        execution_log: List of execution log entries from Phase 2
        workspace_root: Override default workspace root
        archive: Whether to archive (clean scratch) after summary

    Returns:
        Dissolution summary dict
    """
    print("\n" + "="*60)
    print("🧹 PHASE 4: Dissolution")
    print("="*60)

    agents = list_agent_workspaces(run_id, workspace_root=workspace_root)
    agents_total = len(agents)

    # 1. Verify outbox deliverables
    agents_with_output = 0
    missing_output = []
    for agent_dir in agents:
        outbox_files = collect_outbox(agent_dir)
        status = read_status(agent_dir)
        if outbox_files or status.get("status") == "completed":
            agents_with_output += 1
        else:
            missing_output.append(agent_dir.name)

    if missing_output:
        print(f"   ⚠️  Missing deliverables: {', '.join(missing_output)}")

    # 2. Build execution summary
    agents_successful = sum(
        1 for log in execution_log if log.get("status") == "completed"
    )
    agents_failed = sum(
        1 for log in execution_log if log.get("status") == "failed"
    )
    models_used = list(set(log.get("agent", "unknown") for log in execution_log))

    summary = {
        "run_id": run_id,
        "completed_at": datetime.now().isoformat(),
        "agents_total": agents_total,
        "agents_successful": agents_successful,
        "agents_failed": agents_failed,
        "models_used": models_used,
        "execution_log": execution_log,
        "archived": False,
    }

    # Write summary file
    if agents_total > 0:
        summary_path = write_execution_summary(
            run_id, summary, workspace_root=workspace_root
        )
        print(f"   📄 Summary: {summary_path}")

    # 3. Cleanup scratch directories
    if archive and agents_total > 0:
        cleanup_result = cleanup_run(
            run_id,
            workspace_root=workspace_root,
            keep_inbox_outbox=True,
        )
        summary["archived"] = True
        print(f"   🗂️  Archived: {cleanup_result['agents_cleaned']} agents cleaned")

    print(f"   📊 Result: {agents_successful}/{agents_total} successful")

    return {
        "run_id": run_id,
        "workspace_path": str(
            Path(workspace_root or "~/.clawdbot/orchestrator/workspaces") / run_id
        ),
        "archived": summary["archived"],
        "agents_total": agents_total,
        "agents_successful": agents_successful,
    }


# ─── Main Execution ──────────────────────────────────────────────────────────

def execute_orchestrator_task(
    request: str,
    context: Dict,
    deliverable: Dict,
    acceptance_criteria: List[str],
    interactive: bool = True,
    dry_run: bool = False,
    # New options (backward-compatible)
    workspace_root: Optional[str] = None,
    archive_workspace: bool = True,
    enable_workspace: bool = True,
) -> Dict:
    """
    Main orchestrator execution function

    Args:
        request: User's original request
        context: Context dict with keys: taskUrl, relatedDocs, constraints
        deliverable: Deliverable dict with keys: type, format, destination
        acceptance_criteria: List of success criteria
        interactive: If True, prompts for user approval
        dry_run: If True, only shows plan without execution
        workspace_root: Override default workspace directory
        archive_workspace: If True, run dissolution/cleanup after execution
        enable_workspace: If True, create file-based workspace per agent

    Returns:
        Execution result dict with keys: status, executionLog, deliverables, summary

    Execution Flow:
    Phase 0: Confirmation Gates
    Phase 1: Planning (decompose, estimate, classify, apply templates)
    Phase 2: Execution (workspace setup → spawn subagents → track status)
    Phase 3: Integration (merge results, validate, deliver)
    Phase 4: Dissolution (cleanup, archive, metrics)
    """
    result = {
        "status": "failed",
        "executionLog": [],
        "deliverables": [],
        "checkpoints": {},
        "summary": "",
        "issuesEncountered": [],
        "recommendations": []
    }

    # Generate run ID for workspace tracking
    run_id = generate_run_id() if enable_workspace and not dry_run else None

    # --- Phase 1: Planning ---
    print("\n" + "="*60)
    print("📋 PHASE 1: Planning")
    print("="*60)

    # TODO: Implement actual task decomposition (for now, mock)
    # In real implementation, this would use LLM to decompose task
    # Note: Task SOT is now vault/projects/{type}/{name}/t-{prefix}-NNN.md
    subtasks = [
        {"name": "Setup", "task": "Initialize environment", "complexity": "simple"},
        {"name": "Main Work", "task": request, "complexity": "moderate"},
        {"name": "Validation", "task": "Validate output", "complexity": "simple"}
    ]

    # Apply role templates to subtasks (fills in missing fields from template)
    for i, st in enumerate(subtasks):
        subtasks[i] = resolve_subtask_template(st)

    # Assign models to subtasks (respects pre-assigned models from templates)
    subtasks = select_models_for_plan(subtasks)

    # Calculate estimates
    total_eta = sum([10 if st.get("complexity") == "simple" else 20 for st in subtasks])
    total_tokens_in = sum([5 if st.get("complexity") == "simple" else 30 for st in subtasks])
    total_tokens_out = sum([2 if st.get("complexity") == "simple" else 10 for st in subtasks])

    work_size = classify_work_size(total_eta, total_tokens_in, has_deliverable=True)

    print(f"📊 Execution Plan:")
    print(f"   • Subtasks: {len(subtasks)}")
    print(f"   • Total ETA: ~{total_eta} min")
    print(f"   • Tokens: ~{total_tokens_in}K in / ~{total_tokens_out}K out")
    print(f"   • Work Size: {work_size}")
    if run_id:
        print(f"   • Run ID: {run_id}")
    print(f"\n📝 Subtasks:")
    for i, st in enumerate(subtasks, 1):
        role_tag = f" [{st['role']}]" if st.get("role") else ""
        print(f"   {i}. {st['name']}{role_tag} → {st['model']}")

    # --- Phase 0: Confirmation Gates ---
    print("\n" + "="*60)
    print("🚦 PHASE 0: Confirmation Gates")
    print("="*60)

    approved, gate_msg = run_confirmation_gates(
        title=deliverable.get("type", "Work").title(),
        goal=request[:80],  # First 80 chars as goal
        steps=[st["name"] for st in subtasks],
        deliverable=f"{deliverable.get('type', 'output')} → {deliverable.get('destination', 'vault')}",
        eta_min=total_eta,
        tokens_in_k=total_tokens_in,
        tokens_out_k=total_tokens_out,
        work_size=work_size,
        interactive=interactive
    )

    if not approved:
        result["status"] = "cancelled"
        result["summary"] = gate_msg
        return result

    print("✅ All gates approved - proceeding with execution\n")

    if dry_run:
        result["status"] = "dry_run_complete"
        result["summary"] = "Dry run complete - no execution"
        return result

    # --- Phase 2: Execution ---
    print("\n" + "="*60)
    print("⚙️  PHASE 2: Execution")
    print("="*60)

    for i, subtask in enumerate(subtasks, 1):
        print(f"\n[{i}/{len(subtasks)}] Executing: {subtask['name']}")
        print(f"   Model: {subtask['model']}")

        # Workspace setup (if enabled)
        ws_path = None
        if enable_workspace and run_id:
            agent_name = f"{subtask['name'].lower().replace(' ', '-')}-{i}"
            ws_path = create_workspace(
                agent_name, run_id, workspace_root=workspace_root
            )
            write_instructions(
                ws_path,
                task=subtask["task"],
                context=json.dumps(context, ensure_ascii=False),
                model=subtask["model"],
                role_desc=subtask.get("prompt_prefix", ""),
            )
            update_status(ws_path, "running")
            print(f"   📁 Workspace: {ws_path}")

        # Spawn subagent with fallback
        if spawn_subagent_with_retry is None:
            # session_manager not available — record as skipped
            log_entry = {
                "subtask": subtask["name"],
                "agent": subtask["model"],
                "status": "failed",
                "duration": 0,
                "output": "spawn_subagent_with_retry not available"
            }
            result["executionLog"].append(log_entry)
            result["issuesEncountered"].append(
                f"Skipped {subtask['name']}: session_manager not installed"
            )
            print("   ⚠️  Skipped: session_manager not available")
            if ws_path:
                update_status(ws_path, "failed", metadata={"error": "no session_manager"})
            continue

        try:
            spawn_result = spawn_subagent_with_retry(
                task=subtask["task"],
                model=subtask["model"],
                label=f"orchestrator-{subtask['name'].lower().replace(' ', '-')}",
                task_url=context.get("taskUrl"),
                current_depth=1  # Orchestrator is depth 1, spawned agents are depth 2
            )

            log_entry = {
                "subtask": subtask["name"],
                "agent": spawn_result["model_used"],
                "status": "completed" if spawn_result["success"] else "failed",
                "duration": 5,  # Mock duration (would track actual time)
                "output": spawn_result.get("session_id", "unknown")
            }

            result["executionLog"].append(log_entry)

            if not spawn_result["success"]:
                result["issuesEncountered"].append(f"Failed subtask: {subtask['name']}")
                print(f"   ❌ Failed: {spawn_result.get('error', 'Unknown error')}")
                if ws_path:
                    update_status(ws_path, "failed", metadata={
                        "error": spawn_result.get("error"),
                        "model_used": spawn_result.get("model_used"),
                    })
            else:
                print(f"   ✅ Completed: {spawn_result['session_id']}")
                if ws_path:
                    update_status(ws_path, "completed", metadata={
                        "session_id": spawn_result["session_id"],
                        "model_used": spawn_result["model_used"],
                    })

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            result["issuesEncountered"].append(f"Exception in {subtask['name']}: {str(e)}")
            log_entry = {
                "subtask": subtask["name"],
                "agent": subtask["model"],
                "status": "failed",
                "duration": 0,
                "output": str(e)
            }
            result["executionLog"].append(log_entry)
            if ws_path:
                update_status(ws_path, "failed", metadata={"error": str(e)})

    # --- Phase 3: Integration ---
    print("\n" + "="*60)
    print("🔗 PHASE 3: Integration")
    print("="*60)

    # Count successes
    successful = sum(1 for log in result["executionLog"] if log["status"] == "completed")
    total = len(result["executionLog"])

    if successful == total:
        result["status"] = "completed"
        result["summary"] = f"Successfully completed all {total} subtasks"
    elif successful > 0:
        result["status"] = "partial"
        result["summary"] = f"Completed {successful}/{total} subtasks (partial success)"
    else:
        result["status"] = "failed"
        result["summary"] = f"All subtasks failed"

    print(f"\n📊 Final Status: {result['status']}")
    print(f"   {result['summary']}")

    # --- Phase 4: Dissolution ---
    if enable_workspace and run_id:
        result["dissolution"] = _run_dissolution_phase(
            run_id=run_id,
            execution_log=result["executionLog"],
            workspace_root=workspace_root,
            archive=archive_workspace,
        )

    return result


# Example usage (CLI entry point)
if __name__ == "__main__":
    print("=== Agent OS Orchestrator - Test ===\n")

    # Test orchestration with mock data
    result = execute_orchestrator_task(
        request="Create a comprehensive guide for using Clawdbot's Agent OS",
        context={
            "taskUrl": "projects/agent-os/tasks.yml",
            "relatedDocs": ["AGENTS.md", "skills/orchestrator/README.md"],
            "constraints": ["Must be in Korean", "Include code examples"]
        },
        deliverable={
            "type": "documentation",
            "format": "markdown",
            "destination": "file"
        },
        acceptance_criteria=[
            "All sections completed",
            "Code examples tested",
            "Korean language"
        ],
        interactive=False,  # Non-interactive for testing
        dry_run=True         # Dry run only
    )

    print("\n" + "="*60)
    print("📄 RESULT")
    print("="*60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
