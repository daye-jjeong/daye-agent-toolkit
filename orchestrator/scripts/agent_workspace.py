#!/usr/bin/env python3
"""
Agent Workspace - File-based workspace for subagent execution

Provides a structured directory for each agent run, enabling:
- Debugging: inspect instructions sent to each agent
- Reproducibility: replay agent runs from saved instructions
- Traceability: track status transitions and outputs

Workspace structure:
    ~/.clawdbot/orchestrator/workspaces/{run-id}/{agent-name}/
    ├── inbox/instructions.md    # orchestrator → agent
    ├── outbox/                  # agent → orchestrator (deliverables)
    ├── workspace/               # agent scratch space
    └── status.json              # pending → running → completed | failed
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ─── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_WORKSPACE_ROOT = Path.home() / ".clawdbot" / "orchestrator" / "workspaces"

VALID_STATUSES = {"pending", "running", "completed", "failed"}


# ─── Run ID ────────────────────────────────────────────────────────────────────

def generate_run_id() -> str:
    """Generate a timestamped run ID: '20260211-143022'"""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ─── Workspace Lifecycle ──────────────────────────────────────────────────────

def _get_workspace_root(workspace_root: Optional[str] = None) -> Path:
    """Resolve workspace root directory."""
    if workspace_root:
        return Path(workspace_root)
    return DEFAULT_WORKSPACE_ROOT


def create_workspace(
    agent_name: str,
    run_id: str,
    workspace_root: Optional[str] = None,
) -> Path:
    """
    Create workspace directory structure for an agent.

    Args:
        agent_name: Agent identifier (e.g., "researcher-1")
        run_id: Run identifier from generate_run_id()
        workspace_root: Override default workspace root

    Returns:
        Path to the agent's workspace root directory
    """
    root = _get_workspace_root(workspace_root)
    ws_path = root / run_id / agent_name

    # Create directory structure
    (ws_path / "inbox").mkdir(parents=True, exist_ok=True)
    (ws_path / "outbox").mkdir(parents=True, exist_ok=True)
    (ws_path / "workspace").mkdir(parents=True, exist_ok=True)

    # Initialize status
    update_status(ws_path, "pending")

    return ws_path


def write_instructions(
    ws_path: Path,
    task: str,
    context: str = "",
    model: str = "",
    role_desc: str = "",
) -> Path:
    """
    Write agent instructions to inbox/instructions.md.

    Args:
        ws_path: Agent workspace path
        task: Task description
        context: Additional context
        model: Assigned model
        role_desc: Role description from template

    Returns:
        Path to the instructions file
    """
    instructions_path = ws_path / "inbox" / "instructions.md"

    lines = [
        f"# Agent Instructions",
        f"",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Model:** {model or 'auto'}",
        f"",
    ]

    if role_desc:
        lines += [f"## Role", f"", role_desc, f""]

    lines += [f"## Task", f"", task, f""]

    if context:
        lines += [f"## Context", f"", context, f""]

    instructions_path.write_text("\n".join(lines), encoding="utf-8")
    return instructions_path


# ─── Status Management ─────────────────────────────────────────────────────────

def update_status(
    ws_path: Path,
    status: str,
    metadata: Optional[Dict] = None,
) -> None:
    """
    Update status.json for an agent workspace.

    Args:
        ws_path: Agent workspace path
        status: One of: pending, running, completed, failed
        metadata: Optional extra fields (session_id, model_used, error, etc.)
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid: {VALID_STATUSES}")

    status_path = ws_path / "status.json"

    # Load existing status to preserve history
    existing = {}
    if status_path.exists():
        try:
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    data = {
        "status": status,
        "updated_at": datetime.now().isoformat(),
        "agent_name": ws_path.name,
    }

    # Track timestamps for each transition
    timestamps = existing.get("timestamps", {})
    timestamps[status] = datetime.now().isoformat()
    data["timestamps"] = timestamps

    if metadata:
        data["metadata"] = {**existing.get("metadata", {}), **metadata}

    status_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_status(ws_path: Path) -> Dict:
    """
    Read status.json from an agent workspace.

    Args:
        ws_path: Agent workspace path

    Returns:
        Status dict, or {"status": "unknown"} if file missing
    """
    status_path = ws_path / "status.json"
    if not status_path.exists():
        return {"status": "unknown", "agent_name": ws_path.name}

    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "unknown", "agent_name": ws_path.name}


# ─── Output Collection ─────────────────────────────────────────────────────────

def collect_outbox(ws_path: Path) -> List[Path]:
    """
    Collect all files in agent's outbox directory.

    Args:
        ws_path: Agent workspace path

    Returns:
        List of file paths in outbox
    """
    outbox = ws_path / "outbox"
    if not outbox.exists():
        return []
    return sorted(f for f in outbox.iterdir() if f.is_file())


def list_agent_workspaces(
    run_id: str,
    workspace_root: Optional[str] = None,
) -> List[Path]:
    """
    List all agent workspace directories for a given run.

    Args:
        run_id: Run identifier
        workspace_root: Override default workspace root

    Returns:
        List of agent workspace paths
    """
    root = _get_workspace_root(workspace_root)
    run_path = root / run_id
    if not run_path.exists():
        return []
    return sorted(d for d in run_path.iterdir() if d.is_dir())


# ─── Cleanup ────────────────────────────────────────────────────────────────────

def cleanup_run(
    run_id: str,
    workspace_root: Optional[str] = None,
    keep_inbox_outbox: bool = True,
) -> Dict:
    """
    Clean up workspace/ directories for a run, optionally preserving inbox/outbox.

    Args:
        run_id: Run identifier
        workspace_root: Override default workspace root
        keep_inbox_outbox: If True, preserve inbox/ and outbox/ (default)

    Returns:
        Summary dict with cleaned agents and bytes freed
    """
    root = _get_workspace_root(workspace_root)
    run_path = root / run_id
    if not run_path.exists():
        return {"cleaned": 0, "skipped": True}

    cleaned = 0
    for agent_dir in run_path.iterdir():
        if not agent_dir.is_dir():
            continue

        scratch = agent_dir / "workspace"
        if scratch.exists():
            shutil.rmtree(scratch)
            scratch.mkdir()  # recreate empty dir
            cleaned += 1

        if not keep_inbox_outbox:
            for subdir in ("inbox", "outbox"):
                target = agent_dir / subdir
                if target.exists():
                    shutil.rmtree(target)
                    target.mkdir()

    return {"run_id": run_id, "agents_cleaned": cleaned}


def write_execution_summary(
    run_id: str,
    summary: Dict,
    workspace_root: Optional[str] = None,
) -> Path:
    """
    Write execution_summary.json to the run directory.

    Args:
        run_id: Run identifier
        summary: Summary dict to write
        workspace_root: Override default workspace root

    Returns:
        Path to the summary file
    """
    root = _get_workspace_root(workspace_root)
    summary_path = root / run_id / "execution_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary_path


# ─── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=== Agent Workspace - Test ===\n")

    # Use temp dir to avoid polluting real workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = generate_run_id()
        print(f"📁 Run ID: {run_id}")
        print(f"   Root: {tmpdir}\n")

        # Create workspace
        ws = create_workspace("researcher-1", run_id, workspace_root=tmpdir)
        print(f"✅ Created workspace: {ws}")

        # Write instructions
        write_instructions(
            ws,
            task="Research market trends for Q1 2026",
            context="Focus on AI/ML sector",
            model="anthropic/claude-opus-4-5",
            role_desc="Deep research specialist",
        )
        print("✅ Instructions written")

        # Update status
        update_status(ws, "running")
        status = read_status(ws)
        print(f"✅ Status: {status['status']}")

        # Complete
        update_status(ws, "completed", metadata={"session_id": "test-123"})
        status = read_status(ws)
        print(f"✅ Final status: {status['status']}")

        # List workspaces
        agents = list_agent_workspaces(run_id, workspace_root=tmpdir)
        print(f"✅ Agents in run: {[a.name for a in agents]}")

        # Outbox
        outbox = collect_outbox(ws)
        print(f"✅ Outbox files: {len(outbox)}")

        # Cleanup
        result = cleanup_run(run_id, workspace_root=tmpdir)
        print(f"✅ Cleanup: {result}")

    print("\n✅ Agent workspace tests complete")
