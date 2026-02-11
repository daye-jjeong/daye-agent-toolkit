#!/usr/bin/env python3
"""Unit tests for work classification"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from task_policy.guardrails.lib.classifier import classify_work, extract_task_url


class TestWorkClassifier(unittest.TestCase):
    """Test work classification logic"""

    def test_trivial_questions(self):
        """Q&A should be classified as trivial"""
        cases = [
            "오늘 날씨 어때?",
            "What time is it?",
            "세션 몇 개야?",
            "Check system status"
        ]

        for case in cases:
            with self.subTest(case=case):
                result = classify_work(case)
                self.assertEqual(result["type"], "trivial", f"Failed for: {case}")

    def test_trivial_status_checks(self):
        """Status checks should be trivial"""
        cases = [
            "상태 확인해줘",
            "Show me the status",
            "목록 보여줘",
            "List all tasks"
        ]

        for case in cases:
            with self.subTest(case=case):
                result = classify_work(case)
                self.assertEqual(result["type"], "trivial")

    def test_deliverable_creation(self):
        """Creation work should be deliverable"""
        cases = [
            "리포트 작성해줘",
            "Build a dashboard",
            "문서 만들어줘",
            "Implement the feature"
        ]

        for case in cases:
            with self.subTest(case=case):
                result = classify_work(case)
                self.assertEqual(result["type"], "deliverable", f"Failed for: {case}")

    def test_deliverable_analysis(self):
        """Analysis work should be deliverable"""
        cases = [
            "데이터 분석해줘",
            "Research AI trends",
            "조사해서 정리해줘",
            "Investigate the issue"
        ]

        for case in cases:
            with self.subTest(case=case):
                result = classify_work(case)
                self.assertEqual(result["type"], "deliverable")

    def test_time_threshold(self):
        """Work <5 min should be trivial"""
        result = classify_work("간단한 작업 (3분)", context={"estimated_minutes": 3})
        self.assertEqual(result["type"], "trivial")

        result = classify_work("긴 작업 (30분)", context={"estimated_minutes": 30})
        self.assertEqual(result["type"], "deliverable")

    def test_extract_task_ref(self):
        """Test Task reference extraction"""
        # Pattern 1: "Task: t-xxx-NNN"
        text1 = "분석해줘. Task: t-ronik-001"
        ref1 = extract_task_url(text1)
        self.assertEqual(ref1, "t-ronik-001")

        # Pattern 2: Bare task ID
        text2 = "리포트 작성 t-ming-002"
        ref2 = extract_task_url(text2)
        self.assertEqual(ref2, "t-ming-002")

        # No reference
        text3 = "리포트 작성해줘"
        ref3 = extract_task_url(text3)
        self.assertIsNone(ref3)


if __name__ == "__main__":
    unittest.main()
