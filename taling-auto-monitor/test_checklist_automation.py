#!/usr/bin/env python3
"""
Unit and Integration Tests for Taling Checklist Automation

Tests cover:
- File classification
- Checklist generation
- Message formatting
- State management
- Obsidian vault I/O
- Telegram integration (mocked)

Usage:
    python -m pytest test_checklist_automation.py -v
    python test_checklist_automation.py  # Direct run
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Set mock environment variable
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token_123"

# Create temp directories for testing
TEMP_DIR = tempfile.mkdtemp()
MOCK_STATE_FILE = Path(TEMP_DIR) / "test_state.json"
MOCK_VAULT_DIR = Path(TEMP_DIR) / "mock_vault"


def create_test_automation():
    """Create automation instance with mocked paths."""
    import checklist_automation as ca
    import taling_io

    # Temporarily override module constants
    original_state_file = ca.STATE_FILE

    ca.STATE_FILE = MOCK_STATE_FILE

    # Override vault directory for tests
    original_vault = taling_io.VAULT_DIR
    original_taling = taling_io.TALING_DIR
    original_categories = taling_io.CATEGORIES

    taling_io.VAULT_DIR = MOCK_VAULT_DIR
    taling_io.TALING_DIR = MOCK_VAULT_DIR / "taling"
    taling_io.CATEGORIES = {
        "checklists": MOCK_VAULT_DIR / "taling" / "checklists",
    }

    try:
        automation = ca.TalingChecklistAutomation()
    finally:
        ca.STATE_FILE = original_state_file
        taling_io.VAULT_DIR = original_vault
        taling_io.TALING_DIR = original_taling
        taling_io.CATEGORIES = original_categories

    return automation


class TestFileClassification(unittest.TestCase):
    """Tests for file classification logic."""

    def setUp(self):
        self.automation = create_test_automation()

    def test_classify_수강시작(self):
        """Test classification of 수강시작 files."""
        test_cases = [
            ("수강시작_20260203.png", "수강시작"),
            ("시작_screenshot.jpg", "수강시작"),
            ("start_lecture.png", "수강시작"),
            ("begin_study.jpg", "수강시작"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_수강종료(self):
        """Test classification of 수강종료 files."""
        test_cases = [
            ("수강종료_20260203.png", "수강종료"),
            ("종료_screenshot.jpg", "수강종료"),
            ("lecture_end.png", "수강종료"),  # Uses _end pattern
            ("완료_study.jpg", "수강종료"),
            ("finish.png", "수강종료"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_불렛저널(self):
        """Test classification of 불렛저널 files."""
        test_cases = [
            ("불렛저널.jpg", "불렛저널"),
            ("메모_today.png", "불렛저널"),
            ("할일_list.jpg", "불렛저널"),
            ("bullet_journal.png", "불렛저널"),
            ("todo_20260203.jpg", "불렛저널"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_침구정리(self):
        """Test classification of 침구정리 files."""
        test_cases = [
            ("침구정리.jpg", "침구정리"),
            ("이불_정리.png", "침구정리"),
            ("bed_making.jpg", "침구정리"),
            ("bedding.png", "침구정리"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_지출일기(self):
        """Test classification of 지출일기 files."""
        test_cases = [
            ("지출일기.jpg", "지출일기"),
            ("소비_기록.png", "지출일기"),
            ("expense_diary.jpg", "지출일기"),
            ("spending.png", "지출일기"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_저녁운동(self):
        """Test classification of 저녁운동 files."""
        test_cases = [
            ("저녁운동.jpg", "저녁운동"),
            ("운동_인증.png", "저녁운동"),
            ("workout.jpg", "저녁운동"),
            ("exercise_evening.png", "저녁운동"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_과제인증(self):
        """Test classification of 과제인증 files."""
        test_cases = [
            ("과제인증.jpg", "과제인증"),
            ("homework_submission.png", "과제인증"),
            ("assignment.jpg", "과제인증"),
            ("숙제.png", "과제인증"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertEqual(result, expected)

    def test_classify_unknown(self):
        """Test that unknown files return None."""
        test_cases = [
            "random_photo.jpg",
            "vacation.png",
            "screenshot_123.jpg",
            "IMG_20260203.png",
        ]

        for filename in test_cases:
            with self.subTest(filename=filename):
                result = self.automation.classify_file(filename)
                self.assertIsNone(result)

    def test_classify_with_caption(self):
        """Test classification using caption hints."""
        # Filename doesn't match, but caption does
        result = self.automation.classify_file("IMG_1234.jpg", "불렛저널 인증")
        self.assertEqual(result, "불렛저널")

        result = self.automation.classify_file("photo.jpg", "오늘의 운동")
        self.assertEqual(result, "저녁운동")


class TestRequiredItems(unittest.TestCase):
    """Tests for required items by weekday."""

    def setUp(self):
        self.automation = create_test_automation()

    def test_monday_requirements(self):
        """Test Monday (월수금) requirements - 8 items."""
        # Feb 9, 2026 is Monday (weekday=0)
        monday = datetime(2026, 2, 9)
        required = self.automation.get_required_items(monday)

        self.assertIn("수강시작", required)
        self.assertIn("수강종료", required)
        self.assertIn("과제인증", required)
        self.assertIn("불렛저널", required)
        self.assertIn("침구정리", required)
        self.assertIn("지출일기", required)
        self.assertIn("저녁운동", required)
        self.assertIn("학습후기", required)
        self.assertEqual(len(required), 8)

    def test_wednesday_requirements(self):
        """Test Wednesday (월수금) requirements."""
        # Feb 4, 2026 is Wednesday (weekday=2)
        wednesday = datetime(2026, 2, 4)
        required = self.automation.get_required_items(wednesday)

        self.assertIn("수강시작", required)
        self.assertIn("과제인증", required)
        self.assertEqual(len(required), 8)

    def test_tuesday_requirements(self):
        """Test Tuesday (화목토일) requirements - 4 items."""
        # Feb 3, 2026 is Tuesday (weekday=1)
        tuesday = datetime(2026, 2, 3)
        required = self.automation.get_required_items(tuesday)

        self.assertNotIn("수강시작", required)
        self.assertNotIn("수강종료", required)
        self.assertNotIn("과제인증", required)
        self.assertNotIn("학습후기", required)
        self.assertIn("불렛저널", required)
        self.assertIn("침구정리", required)
        self.assertIn("지출일기", required)
        self.assertIn("저녁운동", required)
        self.assertEqual(len(required), 4)

    def test_sunday_requirements(self):
        """Test Sunday (화목토일) requirements."""
        # Feb 8, 2026 is Sunday (weekday=6)
        sunday = datetime(2026, 2, 8)
        required = self.automation.get_required_items(sunday)

        self.assertNotIn("수강시작", required)
        self.assertEqual(len(required), 4)


class TestChecklistGeneration(unittest.TestCase):
    """Tests for checklist generation."""

    def setUp(self):
        self.automation = create_test_automation()

    def test_all_passed_monday(self):
        """Test checklist with all items passed on Monday."""
        # Feb 9, 2026 is Monday (weekday=0)
        monday = datetime(2026, 2, 9)

        # Create mock files
        files = [
            ("수강시작", Path("/mock/수강시작.jpg")),
            ("수강종료", Path("/mock/수강종료.jpg")),
            ("과제인증", Path("/mock/과제.jpg")),
            ("불렛저널", Path("/mock/불렛.jpg")),
            ("침구정리", Path("/mock/침구.jpg")),
            ("지출일기", Path("/mock/지출.jpg")),
            ("저녁운동", Path("/mock/운동.jpg")),
        ]

        texts = {"학습후기": "A" * 550}  # 550 chars > 500 min

        with patch.object(Path, 'exists', return_value=True):
            checklist = self.automation.generate_checklist(monday, files, texts)

        # Check all passed
        for item_type, result in checklist.items():
            if item_type == "학습후기":
                self.assertEqual(result.status, "✅", f"{item_type} should pass")
            else:
                self.assertEqual(result.status, "✅", f"{item_type} should pass")

    def test_missing_items(self):
        """Test checklist with missing items."""
        # Feb 9, 2026 is Monday (weekday=0) - 월수금
        monday = datetime(2026, 2, 9)

        # Only provide 3 files
        files = [
            ("수강시작", Path("/mock/수강시작.jpg")),
            ("불렛저널", Path("/mock/불렛.jpg")),
            ("침구정리", Path("/mock/침구.jpg")),
        ]

        with patch.object(Path, 'exists', return_value=True):
            checklist = self.automation.generate_checklist(monday, files)

        # Check statuses - should have 8 items on Monday
        self.assertIn("수강시작", checklist)
        self.assertEqual(checklist["수강시작"].status, "✅")
        self.assertEqual(checklist["불렛저널"].status, "✅")
        self.assertEqual(checklist["침구정리"].status, "✅")
        self.assertEqual(checklist["수강종료"].status, "❌")
        self.assertEqual(checklist["과제인증"].status, "❌")


class TestMessageFormatting(unittest.TestCase):
    """Tests for message formatting."""

    def setUp(self):
        from checklist_automation import ChecklistResult
        self.automation = create_test_automation()
        self.ChecklistResult = ChecklistResult

    def test_format_complete_checklist(self):
        """Test message formatting for complete checklist."""
        monday = datetime(2026, 2, 3)

        checklist = {}
        for item in ["수강시작", "수강종료", "불렛저널", "침구정리"]:
            result = self.ChecklistResult(item)
            result.status = "✅"
            result.evidence = [f"File: {item}.jpg"]
            checklist[item] = result

        message = self.automation.format_checklist_message(monday, checklist, include_form_link=True)

        self.assertIn("탈잉 챌린지 체크리스트", message)
        self.assertIn("2026-02-03", message)
        self.assertIn("✅", message)
        self.assertIn("모든 미션 완료!", message)
        # Check for form link (case-insensitive)
        self.assertIn("forms/d", message.lower())

    def test_format_incomplete_checklist(self):
        """Test message formatting for incomplete checklist."""
        monday = datetime(2026, 2, 3)

        checklist = {}
        result1 = self.ChecklistResult("수강시작")
        result1.status = "✅"
        checklist["수강시작"] = result1

        result2 = self.ChecklistResult("수강종료")
        result2.status = "❌"
        checklist["수강종료"] = result2

        message = self.automation.format_checklist_message(monday, checklist)

        self.assertIn("✅ 수강시작", message)
        self.assertIn("❌ 수강종료", message)
        self.assertIn("진행률: 1/2", message)
        self.assertNotIn("모든 미션 완료", message)

    def test_format_warning_checklist(self):
        """Test message formatting with warnings."""
        monday = datetime(2026, 2, 3)

        checklist = {}
        result = self.ChecklistResult("학습후기")
        result.status = "⚠️"
        result.validation_errors = ["Only 350 chars (need >=500)"]
        checklist["학습후기"] = result

        message = self.automation.format_checklist_message(monday, checklist)

        self.assertIn("⚠️", message)
        self.assertIn("350 chars", message)


class TestStateManagement(unittest.TestCase):
    """Tests for state management."""

    def test_state_persistence(self):
        """Test state saving and loading."""
        import checklist_automation as ca

        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "test_state.json"

            # Override module constants
            original_state = ca.STATE_FILE
            ca.STATE_FILE = state_file

            try:
                automation = ca.TalingChecklistAutomation()
                automation.state["last_update_id"] = 12345
                automation.state["daily_checklists"]["2026-02-03"] = {"test": "data"}
                automation._save_state()

                # Create new instance
                automation2 = ca.TalingChecklistAutomation()
                self.assertEqual(automation2.state["last_update_id"], 12345)
                self.assertEqual(automation2.state["daily_checklists"]["2026-02-03"], {"test": "data"})
            finally:
                ca.STATE_FILE = original_state


class TestObsidianVaultIO(unittest.TestCase):
    """Tests for Obsidian vault I/O integration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.vault_dir = Path(self.temp_dir) / "test_vault"

        import taling_io
        self.taling_io = taling_io
        self.original_vault = taling_io.VAULT_DIR
        self.original_taling = taling_io.TALING_DIR
        self.original_categories = taling_io.CATEGORIES

        taling_io.VAULT_DIR = self.vault_dir
        taling_io.TALING_DIR = self.vault_dir / "taling"
        taling_io.CATEGORIES = {
            "checklists": self.vault_dir / "taling" / "checklists",
        }

    def tearDown(self):
        self.taling_io.VAULT_DIR = self.original_vault
        self.taling_io.TALING_DIR = self.original_taling
        self.taling_io.CATEGORIES = self.original_categories

        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read_entry(self):
        """Test writing and reading a checklist entry."""
        frontmatter = {
            "type": "taling-checklist",
            "date": "2026-02-09",
            "status": "In Progress",
            "passed": 3,
            "total": 8,
            "all_complete": False,
        }
        body = "# Test Checklist\n\n- [ ] item1\n- [x] item2"

        fpath = self.taling_io.write_entry("checklists", "2026-02-09.md", frontmatter, body)

        self.assertTrue(fpath.exists())

        # Read it back
        text = fpath.read_text(encoding="utf-8")
        fm, read_body = self.taling_io.parse_frontmatter(text)

        self.assertEqual(fm["type"], "taling-checklist")
        self.assertEqual(fm["date"], "2026-02-09")
        self.assertEqual(fm["status"], "In Progress")
        self.assertEqual(fm["passed"], 3)
        self.assertEqual(fm["total"], 8)
        self.assertEqual(fm["all_complete"], False)
        self.assertIn("item1", read_body)

    def test_update_entry(self):
        """Test updating an existing entry."""
        frontmatter = {
            "type": "taling-checklist",
            "date": "2026-02-09",
            "status": "In Progress",
            "passed": 3,
            "total": 8,
        }

        fpath = self.taling_io.write_entry("checklists", "2026-02-09.md", frontmatter)

        # Update
        result = self.taling_io.update_entry(fpath, {"status": "Done", "passed": 8})
        self.assertIsNotNone(result)

        # Read back
        text = fpath.read_text(encoding="utf-8")
        fm, _ = self.taling_io.parse_frontmatter(text)
        self.assertEqual(fm["status"], "Done")
        self.assertEqual(fm["passed"], 8)

    def test_read_entries_with_date_filter(self):
        """Test reading entries with date filter."""
        # Write two entries
        self.taling_io.write_entry(
            "checklists", "2026-01-01.md",
            {"type": "taling-checklist", "date": "2026-01-01", "status": "Done"},
        )
        self.taling_io.write_entry(
            "checklists", "2026-02-09.md",
            {"type": "taling-checklist", "date": "2026-02-09", "status": "In Progress"},
        )

        # Read with days filter (recent entries)
        results = self.taling_io.read_entries("checklists", days=30)
        # Only the recent entry should be returned
        dates = [fm["date"] for _, fm in results]
        self.assertIn("2026-02-09", dates)

    def test_find_entry(self):
        """Test finding a specific entry."""
        self.taling_io.write_entry(
            "checklists", "2026-02-09.md",
            {"type": "taling-checklist", "date": "2026-02-09"},
            "Test body",
        )

        result = self.taling_io.find_entry("checklists", "2026-02-09.md")
        self.assertIsNotNone(result)
        fpath, fm, body = result
        self.assertEqual(fm["date"], "2026-02-09")
        self.assertIn("Test body", body)

    def test_find_missing_entry(self):
        """Test finding a non-existent entry."""
        result = self.taling_io.find_entry("checklists", "nonexistent.md")
        self.assertIsNone(result)

    def test_save_checklist_to_vault(self):
        """Test full save_checklist_to_vault method."""
        from checklist_automation import ChecklistResult
        import checklist_automation as ca

        original_state = ca.STATE_FILE
        ca.STATE_FILE = Path(self.temp_dir) / "state.json"

        try:
            automation = ca.TalingChecklistAutomation()
            monday = datetime(2026, 2, 9)

            checklist = {}
            for item in ["불렛저널", "침구정리", "지출일기", "저녁운동"]:
                r = ChecklistResult(item)
                r.status = "✅"
                r.evidence = [f"File: {item}.jpg"]
                checklist[item] = r

            success = automation.save_checklist_to_vault(monday, checklist)
            self.assertTrue(success)

            # Verify the file was created
            expected_path = self.vault_dir / "taling" / "checklists" / "2026-02-09.md"
            self.assertTrue(expected_path.exists())

            # Verify frontmatter
            text = expected_path.read_text(encoding="utf-8")
            fm, body = self.taling_io.parse_frontmatter(text)
            self.assertEqual(fm["type"], "taling-checklist")
            self.assertEqual(fm["status"], "Done")
            self.assertEqual(fm["passed"], 4)
            self.assertEqual(fm["total"], 4)
            self.assertEqual(fm["all_complete"], True)
            self.assertIn("불렛저널", body)

        finally:
            ca.STATE_FILE = original_state

    def test_dataview_queryable_frontmatter(self):
        """Test that frontmatter is Dataview-queryable format."""
        frontmatter = {
            "type": "taling-checklist",
            "date": "2026-02-09",
            "day_type": "월수금",
            "status": "In Progress",
            "passed": 5,
            "total": 8,
            "all_complete": False,
        }
        fpath = self.taling_io.write_entry("checklists", "2026-02-09.md", frontmatter)
        text = fpath.read_text(encoding="utf-8")

        # Verify YAML frontmatter delimiters
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("\n---\n", text)

        # Verify key fields for Dataview queries
        fm, _ = self.taling_io.parse_frontmatter(text)
        self.assertIn("type", fm)
        self.assertIn("date", fm)
        self.assertIn("status", fm)
        self.assertIn("passed", fm)
        self.assertIn("total", fm)


class TestIntegration(unittest.TestCase):
    """Integration tests (with mocked external services)."""

    @patch('urllib.request.urlopen')
    def test_telegram_get_updates(self, mock_urlopen):
        """Test Telegram getUpdates API call."""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": [
                {
                    "update_id": 123456,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": -1003242721592},
                        "message_thread_id": 168,
                        "document": {
                            "file_id": "test_file_id",
                            "file_name": "taling_20260203.zip"
                        },
                        "date": 1738540800
                    }
                }
            ]
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        automation = create_test_automation()
        updates = automation.get_telegram_updates()

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["update_id"], 123456)

    @patch('urllib.request.urlopen')
    def test_process_zip_update(self, mock_urlopen):
        """Test processing a zip file update."""
        automation = create_test_automation()

        update = {
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "chat": {"id": -1003242721592},
                "message_thread_id": 168,
                "document": {
                    "file_id": "test_file_id",
                    "file_name": "taling_20260203.zip"
                },
                "date": 1738540800
            }
        }

        result = automation.process_update(update)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "zip")
        self.assertEqual(result["filename"], "taling_20260203.zip")

    def test_process_wrong_group_update(self):
        """Test that updates from wrong group are ignored."""
        automation = create_test_automation()

        update = {
            "update_id": 123456,
            "message": {
                "chat": {"id": -999999999},  # Wrong group
                "message_thread_id": 168,
                "document": {
                    "file_id": "test_file_id",
                    "file_name": "taling_20260203.zip"
                },
                "date": 1738540800
            }
        }

        result = automation.process_update(update)
        self.assertIsNone(result)

    def test_process_wrong_thread_update(self):
        """Test that updates from wrong thread are ignored."""
        automation = create_test_automation()

        update = {
            "update_id": 123456,
            "message": {
                "chat": {"id": -1003242721592},
                "message_thread_id": 999,  # Wrong thread
                "document": {
                    "file_id": "test_file_id",
                    "file_name": "taling_20260203.zip"
                },
                "date": 1738540800
            }
        }

        result = automation.process_update(update)
        self.assertIsNone(result)


class TestMessageTemplate(unittest.TestCase):
    """Tests for message template examples."""

    def test_complete_template(self):
        """Test complete checklist message template."""
        from checklist_automation import ChecklistResult

        expected_lines = [
            "탈잉 챌린지 체크리스트",
            "✅",  # passed items
            "모든 미션 완료!",
        ]

        automation = create_test_automation()

        checklist = {}
        for item in ["불렛저널", "침구정리", "지출일기", "저녁운동"]:
            result = ChecklistResult(item)
            result.status = "✅"
            checklist[item] = result

        # Feb 3, 2026 is Tuesday (weekday=1) = 화목토일
        tuesday = datetime(2026, 2, 3)
        message = automation.format_checklist_message(tuesday, checklist, include_form_link=True)

        for expected in expected_lines:
            self.assertIn(expected, message)
        # Check for form link (URL is present)
        self.assertIn("forms/d", message.lower())

    def test_incomplete_template(self):
        """Test incomplete checklist message template."""
        from checklist_automation import ChecklistResult

        automation = create_test_automation()

        checklist = {}
        result1 = ChecklistResult("불렛저널")
        result1.status = "✅"
        checklist["불렛저널"] = result1

        result2 = ChecklistResult("침구정리")
        result2.status = "❌"
        checklist["침구정리"] = result2

        # Feb 3, 2026 is Tuesday
        tuesday = datetime(2026, 2, 3)
        message = automation.format_checklist_message(tuesday, checklist)

        self.assertIn("진행률: 1/2", message)
        self.assertNotIn("forms.d", message)  # No form link


class TestTalingIO(unittest.TestCase):
    """Tests for taling_io module standalone."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        import taling_io
        self.taling_io = taling_io
        self.original_vault = taling_io.VAULT_DIR
        self.original_taling = taling_io.TALING_DIR
        self.original_categories = taling_io.CATEGORIES

        taling_io.VAULT_DIR = Path(self.temp_dir)
        taling_io.TALING_DIR = Path(self.temp_dir) / "taling"
        taling_io.CATEGORIES = {
            "checklists": Path(self.temp_dir) / "taling" / "checklists",
        }

    def tearDown(self):
        self.taling_io.VAULT_DIR = self.original_vault
        self.taling_io.TALING_DIR = self.original_taling
        self.taling_io.CATEGORIES = self.original_categories
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize(self):
        """Test filename sanitization."""
        self.assertEqual(self.taling_io.sanitize("hello world"), "hello_world")
        self.assertEqual(self.taling_io.sanitize("file:name"), "filename")
        self.assertEqual(self.taling_io.sanitize("a" * 100), "a" * 50)

    def test_today(self):
        """Test today() returns correct format."""
        result = self.taling_io.today()
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2}")

    def test_now(self):
        """Test now() returns correct format."""
        result = self.taling_io.now()
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")

    def test_parse_frontmatter_empty(self):
        """Test parsing text without frontmatter."""
        fm, body = self.taling_io.parse_frontmatter("Just some text")
        self.assertEqual(fm, {})
        self.assertEqual(body, "Just some text")

    def test_parse_frontmatter_bool_coercion(self):
        """Test boolean coercion in frontmatter parsing."""
        text = "---\ncomplete: true\npending: false\n---\nbody"
        fm, body = self.taling_io.parse_frontmatter(text)
        self.assertTrue(fm["complete"])
        self.assertFalse(fm["pending"])

    def test_parse_frontmatter_number_coercion(self):
        """Test number coercion in frontmatter parsing."""
        text = "---\ncount: 42\nrate: 3.14\n---\nbody"
        fm, body = self.taling_io.parse_frontmatter(text)
        self.assertEqual(fm["count"], 42)
        self.assertAlmostEqual(fm["rate"], 3.14)

    def test_write_entry_raw(self):
        """Test write_entry_raw creates file at exact path."""
        fpath = Path(self.temp_dir) / "direct.md"
        result = self.taling_io.write_entry_raw(fpath, {"key": "value"}, "body text")
        self.assertEqual(result, fpath)
        self.assertTrue(fpath.exists())
        text = fpath.read_text(encoding="utf-8")
        self.assertIn("key: value", text)
        self.assertIn("body text", text)

    def test_format_frontmatter_special_chars(self):
        """Test that special characters in values get quoted."""
        lines = self.taling_io._format_frontmatter({"title": "hello: world"})
        self.assertIn('title: "hello: world"', lines)

    def test_format_frontmatter_list(self):
        """Test list formatting in frontmatter."""
        lines = self.taling_io._format_frontmatter({"tags": ["a", "b", "c"]})
        self.assertIn("tags:", lines)
        self.assertIn("  - a", lines)
        self.assertIn("  - b", lines)
        self.assertIn("  - c", lines)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFileClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestRequiredItems))
    suite.addTests(loader.loadTestsFromTestCase(TestChecklistGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestMessageFormatting))
    suite.addTests(loader.loadTestsFromTestCase(TestStateManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestObsidianVaultIO))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMessageTemplate))
    suite.addTests(loader.loadTestsFromTestCase(TestTalingIO))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
