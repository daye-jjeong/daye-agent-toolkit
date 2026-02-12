#!/usr/bin/env python3
"""Integration tests for guardrails gates (Obsidian vault backend)"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from task_policy.guardrails.lib.gates import (
    pre_work_gate,
    post_work_gate,
    GuardrailsViolation
)


class TestPreWorkGate(unittest.TestCase):
    """Test pre-work gate enforcement"""

    def tearDown(self):
        """Clean up state files after each test"""
        state_dir = Path.home() / ".clawdbot" / "guardrails" / "state"
        for state_file in state_dir.glob("guardrails-test-*.json"):
            state_file.unlink()

    def test_trivial_work_passes(self):
        """Trivial work should pass without Task"""
        result = pre_work_gate(
            task_description="오늘 날씨 어때?",
            session_id="test-session-trivial-1"
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["work_type"], "trivial")
        self.assertIsNone(result["task_url"])

    def test_deliverable_without_task_blocks(self):
        """Deliverable work without Task should raise GuardrailsViolation"""
        with self.assertRaises(GuardrailsViolation) as ctx:
            pre_work_gate(
                task_description="AI 트렌드 리포트 작성해줘",
                session_id="test-session-block-1"
            )

        self.assertIn("Task required", str(ctx.exception))

    @patch('task_policy.guardrails.lib.gates.validate_task')
    def test_deliverable_with_valid_task_passes(self, mock_validate):
        """Deliverable work with valid Task should pass"""
        mock_validate.return_value = {
            "valid": True,
            "accessible": True,
            "task_id": "t-ronik-001",
            "title": "Test Task",
            "path": "/Users/dayejeong/openclaw/vault/projects/work/ronik/t-ronik-001.md",
            "error": None
        }

        result = pre_work_gate(
            task_description="리포트 작성. Task: t-ronik-001",
            session_id="test-session-valid-1"
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["work_type"], "deliverable")
        self.assertIsNotNone(result["task_url"])
        self.assertEqual(result["task_id"], "t-ronik-001")

    @patch('task_policy.guardrails.lib.gates.validate_task')
    def test_inaccessible_task_blocks(self, mock_validate):
        """Task that can't be found should block"""
        mock_validate.return_value = {
            "valid": False,
            "accessible": False,
            "task_id": None,
            "title": None,
            "path": None,
            "error": "Task not found: t-nonexistent-999"
        }

        with self.assertRaises(GuardrailsViolation) as ctx:
            pre_work_gate(
                task_description="작업. Task: t-nonexistent-999",
                session_id="test-session-block-2"
            )

        self.assertIn("not accessible", str(ctx.exception))

    def test_bypass_allows_work(self):
        """Bypass flag should allow work to proceed"""
        result = pre_work_gate(
            task_description="긴급 수정",
            session_id="test-session-bypass-1",
            bypass=True,
            bypass_reason="Production emergency"
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["work_type"], "bypassed")


class TestPostWorkGate(unittest.TestCase):
    """Test post-work gate validation"""

    def tearDown(self):
        """Clean up state files"""
        state_dir = Path.home() / ".clawdbot" / "guardrails" / "state"
        for state_file in state_dir.glob("guardrails-test-*.json"):
            state_file.unlink()

    @patch('task_policy.guardrails.lib.gates.get_state')
    def test_no_state_passes(self, mock_get_state):
        """No state file should pass (trivial work)"""
        mock_get_state.return_value = None

        result = post_work_gate(
            session_id="test-session-post-1",
            final_output="Quick answer"
        )

        self.assertTrue(result["passed"])

    @patch('task_policy.guardrails.lib.gates.get_state')
    def test_trivial_state_passes(self, mock_get_state):
        """Trivial work state should skip validation"""
        from task_policy.guardrails.lib.state import GuardrailsState

        mock_state = GuardrailsState(
            session_id="test",
            task_url=None,
            task_id=None,
            work_type="trivial",
            gate_status="passed",
            checkpoints=[],
            deliverables=[],
            bypass={},
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z"
        )
        mock_get_state.return_value = mock_state

        result = post_work_gate(
            session_id="test-session-post-2",
            final_output="Answer"
        )

        self.assertTrue(result["passed"])

    @patch('task_policy.guardrails.lib.gates.get_state')
    def test_accessible_deliverables_pass(self, mock_get_state):
        """Accessible vault wiki-links and URLs should pass"""
        from task_policy.guardrails.lib.state import GuardrailsState

        mock_state = GuardrailsState(
            session_id="test",
            task_url="/Users/dayejeong/openclaw/vault/projects/work/ronik/t-ronik-001.md",
            task_id="t-ronik-001",
            work_type="deliverable",
            gate_status="passed",
            checkpoints=[],
            deliverables=[],
            bypass={},
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z"
        )
        mock_get_state.return_value = mock_state

        final_output = """
        ## 산출물
        - [[report-page-123]]
        - https://example.com/data
        """

        result = post_work_gate(
            session_id="test-session-post-3",
            final_output=final_output,
            auto_upload=False
        )

        self.assertTrue(result["passed"])
        self.assertGreater(len(result["deliverables"]), 0)

    @patch('task_policy.guardrails.lib.gates.get_state')
    def test_no_deliverables_warns(self, mock_get_state):
        """No deliverables should trigger warning"""
        from task_policy.guardrails.lib.state import GuardrailsState

        mock_state = GuardrailsState(
            session_id="test",
            task_url="/Users/dayejeong/openclaw/vault/projects/work/ronik/t-ronik-001.md",
            task_id="t-ronik-001",
            work_type="deliverable",
            gate_status="passed",
            checkpoints=[],
            deliverables=[],
            bypass={},
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z"
        )
        mock_get_state.return_value = mock_state

        result = post_work_gate(
            session_id="test-session-post-4",
            final_output="Work done but no deliverable links"
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["action_required"], "upload_required")


if __name__ == "__main__":
    unittest.main()
