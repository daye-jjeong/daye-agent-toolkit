"""
Agent OS Orchestrator Library

Main components:
- gates: Confirmation Gates (Gate 1: Plan, Gate 2: Budget)
- model_selector: Automatic model selection based on task complexity
- agent_templates: Role-based presets for subagent spawning
- agent_workspace: File-based workspace for subagent execution
- orchestrator: Main execution engine coordinating all components

Usage:
    from skills.orchestrator.scripts import execute_orchestrator_task

    result = execute_orchestrator_task(
        request="Your task description",
        context={"taskUrl": "projects/folder/tasks.yml"},
        deliverable={"type": "report", "format": "markdown", "destination": "file"},
        acceptance_criteria=["Criterion 1", "Criterion 2"]
    )
"""

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
    select_models_for_plan,
    COMPLEXITY_MODEL_MAP
)

from .agent_templates import (
    AGENT_TEMPLATES,
    get_template,
    get_model_for_role,
    resolve_subtask_template,
    list_roles
)

from .agent_workspace import (
    generate_run_id,
    create_workspace,
    write_instructions,
    update_status,
    read_status,
    collect_outbox,
    list_agent_workspaces,
    cleanup_run,
    write_execution_summary
)

from .orchestrator import (
    WorkSize,
    classify_work_size,
    estimate_cost,
    run_confirmation_gates,
    execute_orchestrator_task
)

__all__ = [
    # Gates
    'format_plan_confirmation',
    'format_budget_confirmation',
    'check_approval',
    'ask_approval',

    # Model Selection
    'TaskComplexity',
    'classify_task_complexity',
    'select_model_for_task',
    'select_models_for_plan',
    'COMPLEXITY_MODEL_MAP',

    # Agent Templates
    'AGENT_TEMPLATES',
    'get_template',
    'get_model_for_role',
    'resolve_subtask_template',
    'list_roles',

    # Agent Workspace
    'generate_run_id',
    'create_workspace',
    'write_instructions',
    'update_status',
    'read_status',
    'collect_outbox',
    'list_agent_workspaces',
    'cleanup_run',
    'write_execution_summary',

    # Orchestrator
    'WorkSize',
    'classify_work_size',
    'estimate_cost',
    'run_confirmation_gates',
    'execute_orchestrator_task'
]
