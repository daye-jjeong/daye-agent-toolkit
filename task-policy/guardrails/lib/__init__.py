"""Task Policy Guardrails Library - Core enforcement system for deliverable accessibility.
Storage backend: Obsidian vault (~/openclaw/vault/projects/).
"""

from .classifier import classify_work
from .validator import validate_task_ref, validate_deliverables
from .state import (
    create_state,
    update_state,
    get_state,
    finalize_state,
    GuardrailsState
)
from .deliverable_checker import check_deliverables, extract_deliverables
from .vault_writer import upload_deliverable_to_notion, update_task_deliverables_section
from .logger import log_violation, log_bypass

__version__ = "2.0.0"
__all__ = [
    "classify_work",
    "validate_task_ref",
    "validate_deliverables",
    "create_state",
    "update_state",
    "get_state",
    "finalize_state",
    "GuardrailsState",
    "check_deliverables",
    "extract_deliverables",
    "upload_deliverable_to_notion",
    "update_task_deliverables_section",
    "log_violation",
    "log_bypass",
]
