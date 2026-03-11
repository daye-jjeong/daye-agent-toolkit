import subprocess
import tempfile
import unittest
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
WORK_DIGEST_DIR = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
NOTIFY_SCRIPT = WORK_DIGEST_DIR / "scripts" / "notify.sh"


class NotifyScriptContractTests(unittest.TestCase):
    def run_notify(self, fixture_name: str, now: str = "1710000000"):
        payload = (FIXTURES_DIR / fixture_name).read_text().strip()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["bash", str(NOTIFY_SCRIPT), payload],
                capture_output=True,
                text=True,
                env={
                    "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin")) + ":" + str(Path("/opt/homebrew/bin")),
                    "TELEGRAM_DRY_RUN": "1",
                    "NOTIFY_NOW": now,
                    "NOTIFY_STATE_DIR": tmpdir,
                },
            )
        return result

    def test_notify_sends_for_approval_requested(self):
        result = self.run_notify("notify-approval-requested.json")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[Codex]", result.stdout)
        self.assertIn("승인", result.stdout)
        self.assertIn("git status", result.stdout)

    def test_notify_sends_for_completion_message(self):
        result = self.run_notify("notify-turn-complete-finished.json")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[Codex]", result.stdout)
        self.assertIn("작업 완료", result.stdout)
        self.assertIn("session_logger.py와 notify.sh 연결을 마쳤습니다.", result.stdout)

    def test_notify_sends_for_question_message(self):
        result = self.run_notify("notify-turn-complete-question.json")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[Codex]", result.stdout)
        self.assertIn("확인 필요", result.stdout)
        self.assertIn("~/.codex/config.toml", result.stdout)

    def test_notify_skips_progress_only_message(self):
        result = self.run_notify("notify-turn-complete-progress.json")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_notify_dedupes_repeated_message(self):
        payload = (FIXTURES_DIR / "notify-turn-complete-finished.json").read_text().strip()
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin")) + ":" + str(Path("/opt/homebrew/bin")),
                "TELEGRAM_DRY_RUN": "1",
                "NOTIFY_NOW": "1710000000",
                "NOTIFY_STATE_DIR": tmpdir,
            }
            first = subprocess.run(
                ["bash", str(NOTIFY_SCRIPT), payload],
                capture_output=True,
                text=True,
                env=env,
            )
            second = subprocess.run(
                ["bash", str(NOTIFY_SCRIPT), payload],
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(first.returncode, 0)
        self.assertIn("[Codex]", first.stdout)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(second.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
