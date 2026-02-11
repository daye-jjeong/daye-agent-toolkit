"""
Agent OS Orchestrator Library

Main components:
- gates: Confirmation Gates (Gate 1: Plan, Gate 2: Budget)
- model_selector: Automatic model selection based on task complexity
- orchestrator: Main execution engine coordinating all components

Usage:
    from skills.orchestrator.lib import execute_orchestrator_task

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
    
    # Orchestrator
    'WorkSize',
    'classify_work_size',
    'estimate_cost',
    'run_confirmation_gates',
    'execute_orchestrator_task'
]
