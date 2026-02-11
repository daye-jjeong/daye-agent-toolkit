#!/usr/bin/env python3
"""
Work Classification Logic
Determine if work is trivial (bypass) or deliverable (requires Task)
"""

import re
import sys
from pathlib import Path
from typing import Dict, Literal, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.task_io import extract_task_ref

WorkType = Literal["trivial", "deliverable"]

# Keywords that indicate trivial work
TRIVIAL_KEYWORDS = [
    # Status checks
    "status", "상태", "check", "확인", "조회",
    # Questions
    "what", "when", "where", "who", "why", "how", "무엇", "언제", "어디", "누구", "왜", "어떻게",
    # Simple commands
    "list", "show", "display", "목록", "보여줘",
    # Time queries
    "time", "date", "몇 시", "날짜",
]

# Keywords that indicate deliverable work
DELIVERABLE_KEYWORDS = [
    # Creation
    "create", "build", "implement", "생성", "구축", "구현", "만들어",
    # Analysis
    "analyze", "research", "investigate", "분석", "연구", "조사",
    # Writing
    "write", "document", "draft", "작성", "문서화", "초안",
    # Modification
    "update", "modify", "change", "fix", "수정", "변경", "개선",
    # Automation
    "automate", "integrate", "자동화", "연동",
    # Reports
    "report", "guide", "summary", "리포트", "가이드", "요약",
]

# Patterns that indicate deliverable work
DELIVERABLE_PATTERNS = [
    r".*파일.*생성",
    r".*페이지.*만들",
    r".*문서.*작성",
    r".*코드.*구현",
    r".*스크립트.*작성",
    r".*가이드.*작성",
]


def classify_work(task_description: str, context: Dict = None) -> Dict:
    """
    Classify work as trivial or deliverable

    Args:
        task_description: The work request/description
        context: Optional context (e.g., estimated duration)

    Returns:
        {
            "type": "trivial" | "deliverable",
            "confidence": float (0.0-1.0),
            "reasoning": str,
            "estimated_minutes": int | None
        }
    """
    desc_lower = task_description.lower()

    # Check for explicit time estimates in context
    estimated_minutes = None
    if context and "estimated_minutes" in context:
        estimated_minutes = context["estimated_minutes"]

    # Try to extract time from description
    time_match = re.search(r"(\d+)\s*(분|min|minute)", desc_lower)
    if time_match:
        estimated_minutes = int(time_match.group(1))

    hour_match = re.search(r"(\d+)\s*(시간|hour|hr)", desc_lower)
    if hour_match:
        estimated_minutes = int(hour_match.group(1)) * 60

    # Rule 1: If estimated time < 5 minutes -> trivial
    if estimated_minutes and estimated_minutes < 5:
        return {
            "type": "trivial",
            "confidence": 0.95,
            "reasoning": f"Estimated time ({estimated_minutes} min) < 5 min threshold",
            "estimated_minutes": estimated_minutes
        }

    # Rule 2: Check for trivial keywords
    trivial_matches = [kw for kw in TRIVIAL_KEYWORDS if kw in desc_lower]
    deliverable_matches = [kw for kw in DELIVERABLE_KEYWORDS if kw in desc_lower]

    # Count keyword matches
    trivial_score = len(trivial_matches)
    deliverable_score = len(deliverable_matches)

    # Rule 3: Check for deliverable patterns
    pattern_matches = [p for p in DELIVERABLE_PATTERNS if re.search(p, task_description)]
    if pattern_matches:
        deliverable_score += 2  # Patterns are strong indicators

    # Rule 4: Length heuristic
    if len(task_description) < 30:
        trivial_score += 1  # Short requests likely trivial
    elif len(task_description) > 100:
        deliverable_score += 1  # Long requests likely deliverable

    # Rule 5: Question marks indicate trivial (Q&A)
    if "?" in task_description:
        trivial_score += 1

    # Decision logic
    if deliverable_score > trivial_score:
        classification = "deliverable"
        confidence = min(0.5 + (deliverable_score * 0.1), 0.95)
        reasoning = f"Deliverable indicators: {deliverable_matches + [p for p in pattern_matches]}"
    elif trivial_score > deliverable_score:
        classification = "trivial"
        confidence = min(0.5 + (trivial_score * 0.1), 0.95)
        reasoning = f"Trivial indicators: {trivial_matches}"
    else:
        # Tie-breaker: default to deliverable (safer to require Task)
        classification = "deliverable"
        confidence = 0.5
        reasoning = "Ambiguous - defaulting to deliverable (safer)"

    # Rule 6: Override if time estimate suggests deliverable
    if estimated_minutes and estimated_minutes >= 30:
        classification = "deliverable"
        confidence = max(confidence, 0.85)
        reasoning += f" | Long duration ({estimated_minutes} min) -> deliverable"

    return {
        "type": classification,
        "confidence": confidence,
        "reasoning": reasoning,
        "estimated_minutes": estimated_minutes
    }


def extract_task_url(task_description: str) -> Optional[str]:
    """
    Extract task reference from task description.
    Supports vault task IDs (t-xxx-NNN), file paths, and legacy Notion URLs.

    Args:
        task_description: Task string from sessions_spawn

    Returns:
        Task reference if found, None otherwise
    """
    return extract_task_ref(task_description)


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "오늘 날씨 어때?",
        "세션 목록 보여줘",
        "AI 트렌드 분석 리포트 작성해줘",
        "vault 페이지 생성하고 문서 업로드",
        "5분만에 간단히 확인",
        "2시간 걸릴 것 같은데 구현해줘",
    ]

    print("=== Work Classification Test ===\n")
    for test in test_cases:
        result = classify_work(test)
        print(f"Input: {test}")
        print(f"  Type: {result['type']}")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Reasoning: {result['reasoning']}")
        print()
