#!/usr/bin/env python3
"""
Agent Templates - Role-based presets for subagent spawning

Defines standardized templates for common agent roles (researcher, coder, analyst, etc.)
Each template includes complexity, prompt prefix, and expected output type.

Uses model_selector.py's central model mapping for consistency.
"""

from typing import Dict, Optional

from .model_selector import TaskComplexity, COMPLEXITY_MODEL_MAP


# ─── Role Templates ───────────────────────────────────────────────────────────

AGENT_TEMPLATES: Dict[str, Dict] = {
    "researcher": {
        "complexity": TaskComplexity.COMPLEX,
        "prompt_prefix": (
            "You are a research specialist. Conduct thorough investigation, "
            "cite sources, and provide structured findings with evidence."
        ),
        "expected_output": "markdown",
        "description": "심층 연구, 자료 수집, 분석 보고서 작성",
        "constraints": [
            "DO NOT modify or create files (read-only access)",
            "DO NOT send external messages (Telegram, email, Slack)",
            "DO NOT spawn sub-agents",
        ],
    },
    "coder": {
        "complexity": TaskComplexity.MODERATE,
        "prompt_prefix": (
            "You are a coding specialist. Write clean, tested, production-ready code. "
            "Follow existing project conventions and include error handling."
        ),
        "expected_output": "code",
        "description": "코드 작성, 리팩토링, 버그 수정",
        "constraints": [
            "DO NOT send external messages (Telegram, email, Slack)",
            "DO NOT spawn sub-agents",
            "DO NOT modify system config files (AGENTS.md, SOUL.md, crontab, etc.)",
        ],
    },
    "analyst": {
        "complexity": TaskComplexity.MODERATE,
        "prompt_prefix": (
            "You are a data analyst. Process data systematically, identify patterns, "
            "and present findings with clear metrics and visualizations."
        ),
        "expected_output": "markdown",
        "description": "데이터 분석, 패턴 식별, 인사이트 도출",
        "constraints": [
            "DO NOT modify source code (analysis output only)",
            "DO NOT send external messages (Telegram, email, Slack)",
            "DO NOT spawn sub-agents",
        ],
    },
    "writer": {
        "complexity": TaskComplexity.MODERATE,
        "prompt_prefix": (
            "You are a technical writer. Produce clear, well-structured documentation "
            "in Korean (unless otherwise specified). Use consistent formatting."
        ),
        "expected_output": "markdown",
        "description": "문서 작성, 가이드, 매뉴얼",
        "constraints": [
            "DO NOT modify source code (documentation only)",
            "DO NOT send external messages (Telegram, email, Slack)",
            "DO NOT spawn sub-agents",
            "DO NOT run destructive commands (rm, git reset, etc.)",
        ],
    },
    "reviewer": {
        "complexity": TaskComplexity.SIMPLE,
        "prompt_prefix": (
            "You are a code/document reviewer. Check for correctness, consistency, "
            "and adherence to project standards. Provide actionable feedback."
        ),
        "expected_output": "markdown",
        "description": "코드 리뷰, 문서 검증, 품질 검사",
        "constraints": [
            "DO NOT modify any files (read-only, feedback only)",
            "DO NOT send external messages (Telegram, email, Slack)",
            "DO NOT spawn sub-agents",
            "DO NOT run any commands (read and review only)",
        ],
    },
    "integrator": {
        "complexity": TaskComplexity.MODERATE,
        "prompt_prefix": (
            "You are an integration specialist. Combine multiple outputs into a "
            "cohesive deliverable. Resolve conflicts and ensure consistency."
        ),
        "expected_output": "markdown",
        "description": "산출물 통합, 병합, 일관성 확보",
        "constraints": [
            "DO NOT send external messages (Telegram, email, Slack)",
            "DO NOT spawn sub-agents",
            "DO NOT access web or external APIs",
        ],
    },
}


# ─── Public API ────────────────────────────────────────────────────────────────

def get_template(role: str) -> Dict:
    """
    Get template for a given role.

    Args:
        role: One of: researcher, coder, analyst, writer, reviewer, integrator

    Returns:
        Template dict with complexity, prompt_prefix, expected_output, description

    Raises:
        KeyError: If role is not found
    """
    if role not in AGENT_TEMPLATES:
        available = ", ".join(AGENT_TEMPLATES.keys())
        raise KeyError(f"Unknown role '{role}'. Available: {available}")
    return AGENT_TEMPLATES[role].copy()


def get_model_for_role(role: str) -> str:
    """
    Resolve model string for a role via central COMPLEXITY_MODEL_MAP.

    Args:
        role: Template role name

    Returns:
        Model string (e.g., "anthropic/claude-sonnet-4-5")
    """
    template = get_template(role)
    return COMPLEXITY_MODEL_MAP[template["complexity"]]


def resolve_subtask_template(
    subtask: Dict,
    default_role: Optional[str] = None,
) -> Dict:
    """
    Apply template defaults to a subtask dict.

    If the subtask already has explicit values (model, complexity, prompt_prefix),
    those are preserved. Template only fills in missing fields.

    Args:
        subtask: Subtask dict with at least "name" and "task" keys
        default_role: Fallback role if subtask has no "role" key

    Returns:
        Updated subtask dict with template fields applied
    """
    result = subtask.copy()
    role = result.get("role", default_role)

    if not role or role not in AGENT_TEMPLATES:
        return result

    template = AGENT_TEMPLATES[role]

    # Fill missing fields from template (don't overwrite explicit values)
    if "complexity" not in result:
        result["complexity"] = template["complexity"].value
    if "prompt_prefix" not in result:
        result["prompt_prefix"] = template["prompt_prefix"]
    if "expected_output" not in result:
        result["expected_output"] = template["expected_output"]
    if "model" not in result:
        result["model"] = COMPLEXITY_MODEL_MAP[template["complexity"]]

    # Inject constraints into prompt_prefix so the agent sees them
    constraints = template.get("constraints", [])
    if constraints and "constraints" not in result:
        result["constraints"] = constraints
        constraint_block = "\n".join(f"- {c}" for c in constraints)
        result["prompt_prefix"] = (
            f"{result['prompt_prefix']}\n\n"
            f"CONSTRAINTS (you MUST follow these):\n{constraint_block}"
        )

    return result


def list_roles() -> Dict[str, str]:
    """Return dict of role -> description for all templates."""
    return {role: t["description"] for role, t in AGENT_TEMPLATES.items()}


# ─── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Agent Templates - Test ===\n")

    # List all templates
    print("📋 Available templates:")
    for role, desc in list_roles().items():
        model = get_model_for_role(role)
        print(f"  • {role}: {desc} → {model}")

    # Test resolve_subtask_template
    print("\n📝 Template resolution test:")
    subtask = {"name": "Research", "task": "Investigate market trends", "role": "researcher"}
    resolved = resolve_subtask_template(subtask)
    print(f"  Input:  role=researcher, no model/complexity")
    print(f"  Output: complexity={resolved['complexity']}, model={resolved['model']}")

    # Test explicit override preservation
    subtask2 = {
        "name": "Custom",
        "task": "Do stuff",
        "role": "coder",
        "model": "anthropic/claude-opus-4-5",  # explicit override
    }
    resolved2 = resolve_subtask_template(subtask2)
    print(f"\n  Input:  role=coder, model=opus (explicit)")
    print(f"  Output: model={resolved2['model']} (preserved)")

    print("\n✅ Agent templates tests complete")
