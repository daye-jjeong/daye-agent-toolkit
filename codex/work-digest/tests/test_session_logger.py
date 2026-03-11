import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock


TESTS_DIR = Path(__file__).resolve().parent
WORK_DIGEST_DIR = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SCRIPTS_DIR = WORK_DIGEST_DIR / "scripts"
SESSION_LOGGER_PATH = SCRIPTS_DIR / "session_logger.py"


def load_session_logger_module():
    spec = importlib.util.spec_from_file_location("codex_session_logger", SESSION_LOGGER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load module spec for {SESSION_LOGGER_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class SessionLoggerContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.session_end_path = FIXTURES_DIR / "session_end.jsonl"
        self.compaction_path = FIXTURES_DIR / "compaction.jsonl"
        self.user_role_only_path = FIXTURES_DIR / "user_role_only.jsonl"
        self.plain_text_failure_path = FIXTURES_DIR / "plain_text_failure.jsonl"

    def require_module(self):
        try:
            return load_session_logger_module()
        except Exception as exc:  # noqa: BLE001 - red state may be import related
            self.fail(f"Unable to import session_logger module: {exc}")

    def require_function(self, module, name):
        if not hasattr(module, name):
            self.fail(f"session_logger.{name} is not implemented")
        return getattr(module, name)

    def test_parse_transcript_extracts_topic_commands_tokens(self):
        module = self.require_module()
        parse_transcript = self.require_function(module, "parse_transcript")

        data = parse_transcript(str(self.session_end_path))

        self.assertEqual(data["topic"], "codex/work-digest용 session logger를 구현해.")
        self.assertEqual(
            data["cwd"],
            "/Users/dayejeong/git_workplace/daye-agent-toolkit",
        )
        self.assertEqual(data["command_count"], 3)
        self.assertEqual(
            data["commands"],
            [
                "python3 -m unittest discover -s codex/work-digest/tests -p 'test_session_logger.py' -v",
                "git status --short codex/work-digest/tests",
                "git add codex/work-digest/tests/fixtures/session_end.jsonl codex/work-digest/tests/fixtures/compaction.jsonl codex/work-digest/tests/test_session_logger.py",
            ],
        )
        self.assertEqual(data["tokens"]["input"], 4210)
        self.assertEqual(data["tokens"]["cached_input"], 1024)
        self.assertEqual(data["tokens"]["output"], 220)
        self.assertEqual(data["tokens"]["reasoning_output"], 96)
        self.assertEqual(data["tokens"]["total"], 4430)
        self.assertEqual(data["approval_count"], 2)
        self.assertFalse(data["compaction_detected"])

    def test_parse_transcript_tracks_task_complete_message(self):
        module = self.require_module()
        parse_transcript = self.require_function(module, "parse_transcript")

        data = parse_transcript(str(self.session_end_path))

        self.assertEqual(data["last_agent_message"], "세션 로그용 RED 테스트를 추가했습니다.")
        self.assertEqual(
            data["task_complete_message"],
            "테스트 픽스처와 failing tests를 추가했습니다. 다음으로 session_logger.py 구현이 필요합니다.",
        )

    def test_extract_compaction_summary_uses_replacement_history(self):
        module = self.require_module()
        extract_compaction_text = self.require_function(module, "extract_compaction_text")

        summary = extract_compaction_text(str(self.compaction_path))

        self.assertIn("codex notify.sh는 완료되었거나 확인 필요할 때만 보내줘.", summary)
        self.assertIn("approval-requested와 완료/질문 필요 turn만 전송하도록 notify 필터", summary)

    def test_parse_transcript_detects_compaction_on_compaction_fixture(self):
        module = self.require_module()
        parse_transcript = self.require_function(module, "parse_transcript")

        data = parse_transcript(str(self.compaction_path))

        self.assertTrue(data["compaction_detected"])
        self.assertEqual(data["command_count"], 1)
        self.assertEqual(data["commands"], ["rg -n 'notify|session_logger' docs/plans"])

    def test_parse_transcript_uses_response_item_user_message_as_topic(self):
        module = self.require_module()
        parse_transcript = self.require_function(module, "parse_transcript")

        data = parse_transcript(str(self.user_role_only_path))

        self.assertEqual(data["topic"], "notify.sh 알림 조건이랑 session log 저장 시점을 짧게 정리해줘.")
        self.assertEqual(
            data["task_complete_message"],
            "알림은 turn 완료/질문 필요일 때만 보내고, 세션 로그는 compaction과 종료 시점에 저장하도록 정리했습니다.",
        )
        self.assertEqual(
            data["last_agent_message"],
            "notify는 완료나 확인 필요 턴에서만 보내고, session log는 compaction과 종료 시점에 남기겠습니다.",
        )

    def test_parse_transcript_captures_plain_text_exec_failures(self):
        module = self.require_module()
        parse_transcript = self.require_function(module, "parse_transcript")

        data = parse_transcript(str(self.plain_text_failure_path))

        self.assertEqual(data["command_count"], 1)
        self.assertEqual(data["commands"], ["pytest codex/work-digest/tests/test_session_logger.py -k plain_text_failure"])
        self.assertEqual(data["errors"], ["Process exited with code 1"])

    def test_build_session_section_marks_source_and_event(self):
        module = self.require_module()
        build_session_section = self.require_function(module, "build_session_section")

        now = datetime(2026, 3, 10, 23, 40)
        data = {
            "topic": "codex/work-digest용 session logger를 구현해.",
            "summary": {"tag": "설계", "text": "Codex 세션 종료 로그 섹션 포맷을 정리했다."},
            "commands": ["python3 -m unittest discover -s codex/work-digest/tests -p 'test_session_logger.py' -v"],
            "command_count": 1,
            "tokens": {"input": 4210, "cached_input": 1024, "output": 220, "reasoning_output": 96, "total": 4430},
            "duration_min": 5,
            "start_time": "23:10",
            "end_time": "23:17",
            "files": [],
            "task_complete_message": "테스트 픽스처와 failing tests를 추가했습니다.",
        }

        section = build_session_section("019cd900-aaaa-7bbb-8ccc-1234567890ab", data, now, "daye-agent-toolkit", "session_end")

        self.assertIn("## 세션 23:10~23:17", section)
        self.assertIn("(019cd900, daye-agent-toolkit)", section)
        self.assertIn("> source: codex | event: session_end", section)
        self.assertIn("[설계] Codex 세션 종료 로그 섹션 포맷을 정리했다.", section)

    def test_already_recorded_blocks_duplicate_event(self):
        module = self.require_module()
        already_recorded = self.require_function(module, "already_recorded")

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "session_logger_state.json"
            with mock.patch.object(module, "STATE_FILE", state_file):
                self.assertFalse(already_recorded("session-123", "compaction"))
                self.assertTrue(already_recorded("session-123", "compaction"))
                self.assertFalse(already_recorded("session-123", "session_end"))

    def test_main_logs_no_tool_session_when_response_item_has_user_request(self):
        module = self.require_module()
        main = self.require_function(module, "main")

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "session_logger_state.json"
            argv = [
                "session_logger.py",
                "--event",
                "session_end",
                "--transcript-path",
                str(self.user_role_only_path),
                "--session-id",
                "session-user-only",
            ]
            with mock.patch.object(module, "STATE_FILE", state_file), \
                mock.patch.object(module, "write_session_marker") as write_session_marker, \
                mock.patch.object(module, "send_session_telegram") as send_session_telegram, \
                mock.patch.object(module, "summarize_session", return_value=None), \
                mock.patch.object(sys, "argv", argv):
                main()

        write_session_marker.assert_called_once()
        send_session_telegram.assert_called_once()

    def test_summarize_session_uses_resolved_codex_binary(self):
        module = self.require_module()
        summarize_session = self.require_function(module, "summarize_session")

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="[설계]\nCodex 세션 종료 요약입니다.",
            stderr="",
        )

        with mock.patch.object(module, "resolve_codex_bin", return_value="/usr/local/bin/codex"), \
            mock.patch.object(module.subprocess, "run", return_value=completed) as run:
            summary = summarize_session(
                conversation="User: codex/work-digest용 session logger를 구현해.",
                repo="daye-agent-toolkit",
                cwd="/Users/dayejeong/git_workplace/daye-agent-toolkit",
            )

        self.assertEqual(summary, {"tag": "설계", "text": "Codex 세션 종료 요약입니다."})
        args, kwargs = run.call_args
        self.assertEqual(
            args[0][:5],
            [
                "/usr/local/bin/codex",
                "exec",
                "--ephemeral",
                "-C",
                "/Users/dayejeong/git_workplace/daye-agent-toolkit",
            ],
        )
        self.assertEqual(kwargs["capture_output"], True)
        self.assertEqual(kwargs["text"], True)
        self.assertIn("daye-agent-toolkit", kwargs["input"])


if __name__ == "__main__":
    unittest.main()
