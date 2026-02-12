#!/usr/bin/env python3
"""
Automatic Model Selection Based on Task Complexity

Implements AGENTS.md § 2 Session Protection Policy model selection rules.
Maps task complexity to appropriate models per config/session-models.json.

Complexity Levels:
- Simple: google-gemini-cli/gemini-3-flash-preview (데이터 fetch, 단순 변환, 규칙 기반 작업)
- Moderate: anthropic/claude-sonnet-4-5 (분석, 문서 작성, 컨텍스트 해석)
- Complex: anthropic/claude-opus-4-5 (연구, 복잡한 의사결정, 창의적 생성)
"""

import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class TaskComplexity(Enum):
    """Task complexity levels per AGENTS.md § 2"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


# Model mapping (from config/session-models.json)
COMPLEXITY_MODEL_MAP = {
    TaskComplexity.SIMPLE: "google-gemini-cli/gemini-3-flash-preview",
    TaskComplexity.MODERATE: "anthropic/claude-sonnet-4-5",
    TaskComplexity.COMPLEX: "anthropic/claude-opus-4-5"
}


# Keywords/patterns for automatic classification
SIMPLE_KEYWORDS = [
    "fetch", "get", "retrieve", "조회", "가져오", "읽기", "read",
    "convert", "format", "변환", "포맷", "정리",
    "list", "목록", "리스트",
    "check", "확인", "검사",
    "단순", "간단",
    "code", "코드", "프로그래밍"
]

COMPLEX_KEYWORDS = [
    "research", "연구", "분석", "analyze",
    "design", "설계", "architecture", "아키텍처",
    "decision", "의사결정", "판단",
    "create", "생성", "작성", "write",
    "integrate", "통합", "연동",
    "optimize", "최적화",
    "복잡", "어려운"
]


def classify_task_complexity(task_description: str) -> TaskComplexity:
    """
    Automatically classify task complexity from description
    
    Args:
        task_description: Task description text
        
    Returns:
        TaskComplexity enum value
        
    Classification Rules:
    1. Check for explicit complexity keywords
    2. Consider task length/depth
    3. Default to MODERATE if uncertain
    """
    desc_lower = task_description.lower()
    
    # Count keyword matches
    simple_matches = sum(1 for kw in SIMPLE_KEYWORDS if kw in desc_lower)
    complex_matches = sum(1 for kw in COMPLEX_KEYWORDS if kw in desc_lower)
    
    # Rule 1: Strong signals
    if simple_matches >= 2 and complex_matches == 0:
        return TaskComplexity.SIMPLE
    
    if complex_matches >= 2:
        return TaskComplexity.COMPLEX
    
    # Rule 2: Length/depth heuristics
    # Simple: Short, single action
    if len(task_description) < 50 and simple_matches > 0:
        return TaskComplexity.SIMPLE
    
    # Complex: Long description with multiple steps
    if len(task_description) > 200 or "\n" in task_description:
        return TaskComplexity.COMPLEX
    
    # Rule 3: Default to MODERATE
    return TaskComplexity.MODERATE


def select_model_for_task(
    task_description: str,
    complexity_override: Optional[TaskComplexity] = None,
    custom_model: Optional[str] = None
) -> str:
    """
    Select appropriate model for a task
    
    Args:
        task_description: Task description
        complexity_override: Manually specified complexity level (optional)
        custom_model: Manually specified model (bypasses auto-selection)
        
    Returns:
        Model string (e.g., "anthropic/claude-sonnet-4-5")
        
    Priority:
    1. custom_model (if provided)
    2. complexity_override (if provided)
    3. Auto-classify from task_description
    """
    # Priority 1: Manual model override
    if custom_model:
        return custom_model
    
    # Priority 2: Manual complexity override
    if complexity_override:
        complexity = complexity_override
    else:
        # Priority 3: Auto-classify
        complexity = classify_task_complexity(task_description)
    
    return COMPLEXITY_MODEL_MAP[complexity]


def select_models_for_plan(
    subtasks: List[Dict[str, str]],
    default_complexity: TaskComplexity = TaskComplexity.MODERATE
) -> List[Dict[str, str]]:
    """
    Assign models to all subtasks in an execution plan
    
    Args:
        subtasks: List of dicts with keys: "name", "task", optionally "complexity"/"model"
        default_complexity: Fallback complexity if not specified
        
    Returns:
        Same list with "model" key added to each subtask
        
    Example:
        Input:
        [
            {"name": "데이터 수집", "task": "Fetch calendar events"},
            {"name": "분석", "task": "Analyze patterns", "complexity": "complex"}
        ]
        
        Output:
        [
            {"name": "데이터 수집", "task": "Fetch calendar events", "model": "google-gemini-flash"},
            {"name": "분석", "task": "Analyze patterns", "complexity": "complex", "model": "anthropic/claude-opus-4"}
        ]
    """
    result = []
    
    for subtask in subtasks:
        # Parse complexity override (if specified)
        complexity_override = None
        if "complexity" in subtask:
            try:
                complexity_override = TaskComplexity(subtask["complexity"])
            except ValueError:
                print(f"⚠️  Invalid complexity '{subtask['complexity']}' for subtask '{subtask['name']}', using default")
        
        # Select model
        model = select_model_for_task(
            task_description=subtask["task"],
            complexity_override=complexity_override or default_complexity,
            custom_model=subtask.get("model")  # Respect pre-assigned model
        )
        
        # Add model to subtask
        updated = subtask.copy()
        updated["model"] = model
        result.append(updated)
    
    return result


def load_config_models() -> Dict:
    """
    Load model configuration from config/session-models.json
    
    Returns:
        Dict with model configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    config_path = Path.home() / "openclaw" / "config" / "session-models.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Model config not found: {config_path}")
    
    with open(config_path) as f:
        return json.load(f)


def validate_model_availability(model: str) -> bool:
    """
    Check if a model exists in current Clawdbot configuration
    
    Args:
        model: Model string (e.g., "anthropic/claude-sonnet-4-5")
        
    Returns:
        True if model is available, False otherwise
        
    Note:
        This is a simple check. Real validation would query Clawdbot's model registry.
    """
    # Known valid models (from config/session-models.json)
    valid_models = [
        "openai-codex/gpt-5.2",
        "openai-codex/gpt-5.2-codex",
        "anthropic/claude-sonnet-4-5",
        "anthropic/claude-opus-4-5",
        "google-gemini-cli/gemini-3-flash-preview",
        "google-gemini-cli/gemini-3-pro-preview",
        "anthropic/claude-haiku-4-5"
    ]
    
    return model in valid_models


# Example usage
if __name__ == "__main__":
    print("=== Model Selector - Test ===\n")
    
    # Test 1: Simple task
    task1 = "Fetch calendar events from Google Calendar API"
    complexity1 = classify_task_complexity(task1)
    model1 = select_model_for_task(task1)
    print(f"Task 1: {task1}")
    print(f"  → Complexity: {complexity1.value}")
    print(f"  → Model: {model1}\n")
    
    # Test 2: Complex task
    task2 = "Research and design a multi-agent architecture for distributed task execution with fault tolerance"
    complexity2 = classify_task_complexity(task2)
    model2 = select_model_for_task(task2)
    print(f"Task 2: {task2}")
    print(f"  → Complexity: {complexity2.value}")
    print(f"  → Model: {model2}\n")
    
    # Test 3: Moderate task (default)
    task3 = "Write a guide for using YAML files"
    complexity3 = classify_task_complexity(task3)
    model3 = select_model_for_task(task3)
    print(f"Task 3: {task3}")
    print(f"  → Complexity: {complexity3.value}")
    print(f"  → Model: {model3}\n")
    
    # Test 4: Execution plan
    subtasks = [
        {"name": "데이터 수집", "task": "Fetch data from API"},
        {"name": "분석", "task": "Analyze data patterns", "complexity": "complex"},
        {"name": "리포트 작성", "task": "Generate summary report"}
    ]
    
    print("Test 4: Execution plan model assignment")
    result = select_models_for_plan(subtasks)
    for st in result:
        print(f"  • {st['name']}: {st['model']}")
    
    print("\n✅ Model selector tests complete")
