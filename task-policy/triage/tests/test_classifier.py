#!/usr/bin/env python3
"""
Unit tests for task classification logic
Run: python3 -m pytest skills/task-triage/tests/test_classifier.py -v
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from triage import classify_request


def test_task_classification():
    """Test that typical task keywords result in Task classification"""
    cases = [
        "API 문서 리뷰",
        "PT 숙제 30분",
        "회의록 작성",
        "코드 리뷰해줘",
        "분석 보고서 작성",
    ]
    
    for case in cases:
        result = classify_request(case)
        assert result["type"] == "Task", f"Expected Task for '{case}', got {result['type']}"
        print(f"✅ Task: {case} → {result['confidence']:.0%}")


def test_project_classification():
    """Test that project keywords result in Project classification"""
    cases = [
        "토스 API 연동 구현",
        "PT 숙제 자동화 시스템",
        "Clawdbot 가이드 문서화",
        "파이프라인 아키텍처 설계",
    ]
    
    for case in cases:
        result = classify_request(case)
        assert result["type"] == "Project", f"Expected Project for '{case}', got {result['type']}"
        print(f"✅ Project: {case} → {result['confidence']:.0%}")


def test_epic_classification():
    """Test that epic keywords result in Epic classification"""
    cases = [
        "로닉 플랫폼 전략 수립",
        "건강 생태계 구축",
        "AI 이니셔티브 기획",
    ]
    
    for case in cases:
        result = classify_request(case)
        assert result["type"] == "Epic", f"Expected Epic for '{case}', got {result['type']}"
        print(f"✅ Epic: {case} → {result['confidence']:.0%}")


def test_followup_detection():
    """Test that follow-up keywords are detected"""
    cases = [
        "가이드 v2 작성",
        "API 개선 작업",
        "문서 수정해줘",
        "코드 리팩토링",
    ]
    
    for case in cases:
        result = classify_request(case)
        assert result["is_followup"] == True, f"Expected followup=True for '{case}'"
        print(f"✅ Follow-up detected: {case}")


def test_title_cleaning():
    """Test that suggested titles are cleaned up"""
    cases = [
        ("API 문서 리뷰해줘", "API 문서 리뷰"),
        ("토스 연동 부탁", "토스 연동"),
        ("코드 작성 please", "코드 작성"),
    ]
    
    for input_text, expected_title in cases:
        result = classify_request(input_text)
        assert result["suggested_title"] == expected_title, \
            f"Expected '{expected_title}', got '{result['suggested_title']}'"
        print(f"✅ Title cleaned: '{input_text}' → '{expected_title}'")


def test_confidence_scores():
    """Test that confidence scores are reasonable"""
    high_confidence_case = "API 문서 리뷰"  # Clear Task keywords
    low_confidence_case = "애매한 요청"  # No clear indicators
    
    high_result = classify_request(high_confidence_case)
    low_result = classify_request(low_confidence_case)
    
    assert high_result["confidence"] > 0.7, f"Expected high confidence for '{high_confidence_case}'"
    assert low_result["confidence"] < 0.7, f"Expected low confidence for '{low_confidence_case}'"
    
    print(f"✅ High confidence: {high_confidence_case} → {high_result['confidence']:.0%}")
    print(f"✅ Low confidence: {low_confidence_case} → {low_result['confidence']:.0%}")


if __name__ == "__main__":
    print("Running Task Triage Classification Tests\n")
    
    print("Test 1: Task Classification")
    test_task_classification()
    print()
    
    print("Test 2: Project Classification")
    test_project_classification()
    print()
    
    print("Test 3: Epic Classification")
    test_epic_classification()
    print()
    
    print("Test 4: Follow-Up Detection")
    test_followup_detection()
    print()
    
    print("Test 5: Title Cleaning")
    test_title_cleaning()
    print()
    
    print("Test 6: Confidence Scores")
    test_confidence_scores()
    print()
    
    print("✅ All tests passed!")
