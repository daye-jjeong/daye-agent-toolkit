import subprocess
import tempfile
import unittest
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
WORK_DIGEST_DIR = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
WRAPPER_SCRIPT = WORK_DIGEST_DIR / "scripts" / "codex-wrapper.sh"
MOCK_CODEX = FIXTURES_DIR / "mock_codex.sh"
MOCK_SESSION_LOGGER = FIXTURES_DIR / "mock_session_logger.sh"


class CodexWrapperContractTests(unittest.TestCase):
    def run_wrapper(self, mode: str = "none", exit_code: str = "0"):
        tmpdir = tempfile.TemporaryDirectory()
        root = Path(tmpdir.name)
        args_log = root / "mock_codex_args.log"
        logger_log = root / "mock_session_logger.log"
        session_root = root / "sessions"

        result = subprocess.run(
            ["bash", str(WRAPPER_SCRIPT), "--version", "--json"],
            capture_output=True,
            text=True,
            env={
                "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
                "CODEX_REAL_BIN": str(MOCK_CODEX),
                "CODEX_SESSION_LOGGER": str(MOCK_SESSION_LOGGER),
                "CODEX_SESSION_ROOT": str(session_root),
                "CODEX_WRAPPER_POLL_INTERVAL": "0.05",
                "CODEX_WRAPPER_DISCOVERY_TIMEOUT": "2",
                "MOCK_CODEX_ARGS_FILE": str(args_log),
                "MOCK_CODEX_TRANSCRIPT_MODE": mode,
                "MOCK_CODEX_EXIT_CODE": exit_code,
                "MOCK_SESSION_LOGGER_LOG": str(logger_log),
            },
        )
        return result, root, tmpdir

    def test_wrapper_forwards_args_to_real_binary(self):
        result, root, tmpdir = self.run_wrapper()
        self.addCleanup(tmpdir.cleanup)

        self.assertEqual(result.returncode, 0)
        self.assertIn("--version --json", (root / "mock_codex_args.log").read_text())

    def test_wrapper_calls_session_logger_on_compaction(self):
        result, root, tmpdir = self.run_wrapper(mode="compaction")
        self.addCleanup(tmpdir.cleanup)

        self.assertEqual(result.returncode, 0)
        logged = (root / "mock_session_logger.log").read_text()
        self.assertIn("--event compaction", logged)
        self.assertIn("--event session_end", logged)

    def test_wrapper_calls_session_logger_on_session_end(self):
        result, root, tmpdir = self.run_wrapper()
        self.addCleanup(tmpdir.cleanup)

        self.assertEqual(result.returncode, 0)
        logged = (root / "mock_session_logger.log").read_text()
        self.assertIn("--event session_end", logged)

    def test_wrapper_preserves_real_exit_code(self):
        result, root, tmpdir = self.run_wrapper(exit_code="23")
        self.addCleanup(tmpdir.cleanup)

        self.assertEqual(result.returncode, 23)


if __name__ == "__main__":
    unittest.main()
