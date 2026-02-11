#!/usr/bin/env python3
"""
Taling Challenge Checklist Automation

Detects zip/mission file uploads in Telegram topic 168,
parses content, generates checklist with ✅/❌/⚠️,
updates Obsidian vault (~/mingming-vault/taling/), and sends formatted results.

Architecture: Tier 1 (Pure Script) with Obsidian vault integration
- Input: Telegram Bot API (getUpdates or Webhook)
- State: memory/taling_checklist_state.json
- Output: Obsidian vault (Dataview-queryable) + Telegram message

Author: Clawdbot Subagent
Version: 2.0.0
Date: 2026-02-11
"""

import os
import sys
import json
import zipfile
import tempfile
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import urllib.request
import urllib.error
import re

# Add scripts directory to path for taling_io import
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import taling_io

# Configuration
GROUP_ID = "-1003242721592"  # JARVIS HQ
THREAD_ID = 168  # 탈잉 챌린지 토픽
STATE_FILE = Path.home() / "clawd/memory/taling_checklist_state.json"
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSc7gbLmkgDeOFePJitafYLgXKbtR_Rhgb9h3ECyWch-snFH_Q/viewform"

# File classification patterns (use word boundaries for better matching)
FILE_PATTERNS = {
    "수강시작": {
        "patterns": ["시작", "start", "begin", "수강시작"],
        "required_weekdays": [0, 2, 4],  # Mon, Wed, Fri
        "validation": ["date", "lecture_name"],
    },
    "수강종료": {
        "patterns": ["종료", "finish", "완료", "수강종료", "_end"],  # "end" removed to avoid "spending" false positive
        "required_weekdays": [0, 2, 4],
        "validation": ["date", "lecture_name", "progress_97"],
    },
    "과제인증": {
        "patterns": ["과제", "assignment", "homework", "숙제"],
        "required_weekdays": [0, 2, 4],
        "validation": ["keyword", "story", "task"],
    },
    "불렛저널": {
        "patterns": ["메모", "할일", "불렛", "bullet", "journal", "todo"],
        "required_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "validation": ["three_items"],
    },
    "침구정리": {
        "patterns": ["침구", "이불", "정리", "bed", "bedding"],
        "required_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "validation": ["image_present"],
    },
    "지출일기": {
        "patterns": ["지출", "소비", "일기", "expense", "spending"],
        "required_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "validation": ["expense_entry"],
    },
    "저녁운동": {
        "patterns": ["운동", "전신", "저녁", "workout", "exercise", "evening"],
        "required_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "validation": ["full_body"],
    },
    "학습후기": {
        "patterns": ["학습", "후기", "review", "reflection"],
        "required_weekdays": [0, 2, 4],  # 500 char text
        "validation": ["min_500_chars"],
    },
}


class ChecklistResult:
    """Result for a single checklist item."""

    def __init__(self, item_type: str):
        self.item_type = item_type
        self.status: str = "❌"  # ✅ passed, ❌ missing, ⚠️ warning
        self.evidence: List[str] = []
        self.filename: Optional[str] = None
        self.validation_errors: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "type": self.item_type,
            "status": self.status,
            "evidence": self.evidence,
            "filename": self.filename,
            "validation_errors": self.validation_errors,
        }


class TalingChecklistAutomation:
    """Main automation class for Taling challenge checklist."""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from file."""
        self.state_file = STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "last_update_id": 0,
            "processed_files": {},  # hash -> date processed
            "daily_checklists": {},  # date -> checklist results
        }

    def _save_state(self):
        """Save state to file."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def get_required_items(self, date: datetime) -> List[str]:
        """Get required items for a specific date based on weekday."""
        weekday = date.weekday()
        required = []

        for item_type, config in FILE_PATTERNS.items():
            if weekday in config["required_weekdays"]:
                required.append(item_type)

        return required

    def classify_file(self, filename: str, content_hint: str = "") -> Optional[str]:
        """Classify a file based on filename and content hints."""
        text = f"{filename} {content_hint}".lower()

        for file_type, config in FILE_PATTERNS.items():
            if any(pattern in text for pattern in config["patterns"]):
                return file_type

        return None

    def download_telegram_file(self, file_id: str, local_path: Path) -> bool:
        """Download file from Telegram."""
        try:
            # Get file info
            url = f"https://api.telegram.org/bot{self.bot_token}/getFile?file_id={file_id}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())

            if not data.get("ok"):
                print(f"Failed to get file info: {data.get('description')}")
                return False

            file_path = data["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"

            req = urllib.request.Request(download_url)
            with urllib.request.urlopen(req, timeout=60) as response:
                with open(local_path, "wb") as f:
                    f.write(response.read())

            return True
        except Exception as e:
            print(f"Error downloading file: {e}")
            return False

    def parse_zip_file(self, zip_path: Path) -> List[Tuple[str, Path]]:
        """Parse a zip file and extract contents.

        Returns list of (classified_type, extracted_file_path) tuples.
        """
        results = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(temp_path)

                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        file_type = self.classify_file(file_path.name)
                        if file_type:
                            # Copy to persistent location
                            dest_dir = Path.home() / "clawd/temp/taling_extracted"
                            dest_dir.mkdir(parents=True, exist_ok=True)
                            dest_path = dest_dir / file_path.name

                            import shutil
                            shutil.copy2(file_path, dest_path)
                            results.append((file_type, dest_path))

            except zipfile.BadZipFile:
                print(f"Invalid zip file: {zip_path}")
            except Exception as e:
                print(f"Error parsing zip: {e}")

        return results

    def validate_item(self, item_type: str, file_path: Optional[Path] = None,
                      text_content: str = "") -> ChecklistResult:
        """Validate a checklist item and gather evidence."""
        result = ChecklistResult(item_type)
        config = FILE_PATTERNS.get(item_type, {})
        validations = config.get("validation", [])

        if file_path and file_path.exists():
            result.filename = file_path.name
            result.evidence.append(f"File: {file_path.name}")
            result.status = "✅"

            # Additional validations based on type
            if "min_500_chars" in validations:
                if len(text_content) >= 500:
                    result.evidence.append(f"{len(text_content)} chars (>=500)")
                else:
                    result.status = "⚠️"
                    result.validation_errors.append(f"Only {len(text_content)} chars (need >=500)")

            if "progress_97" in validations:
                # Would need OCR to validate - mark as needing manual check
                result.evidence.append("Progress % requires manual verification")

        elif text_content:
            # Text-based validation (e.g., 학습후기)
            if "min_500_chars" in validations:
                if len(text_content) >= 500:
                    result.status = "✅"
                    result.evidence.append(f"{len(text_content)} chars (>=500)")
                else:
                    result.status = "⚠️"
                    result.validation_errors.append(f"Only {len(text_content)} chars (need >=500)")
            else:
                result.status = "✅"
                result.evidence.append("Text submitted")
        else:
            result.status = "❌"
            result.validation_errors.append("Missing file or content")

        return result

    def generate_checklist(self, date: datetime,
                           files: List[Tuple[str, Path]],
                           texts: Dict[str, str] = None) -> Dict[str, ChecklistResult]:
        """Generate full checklist for a date."""
        texts = texts or {}
        required = self.get_required_items(date)
        results = {}

        # Map files to their types
        file_map = {item_type: path for item_type, path in files}

        for item_type in required:
            file_path = file_map.get(item_type)
            text_content = texts.get(item_type, "")
            result = self.validate_item(item_type, file_path, text_content)
            results[item_type] = result

        return results

    def format_checklist_message(self, date: datetime,
                                 checklist: Dict[str, ChecklistResult],
                                 include_form_link: bool = False) -> str:
        """Format checklist as Telegram message."""
        date_str = date.strftime("%Y-%m-%d")
        weekday = date.weekday()
        day_type = "월수금" if weekday in [0, 2, 4] else "화목토일"

        lines = [
            f"📋 탈잉 챌린지 체크리스트 ({date_str})",
            f"📅 {day_type}",
            "",
        ]

        all_passed = True
        for item_type, result in sorted(checklist.items()):
            status = result.status
            if status != "✅":
                all_passed = False

            lines.append(f"{status} {item_type}")

            for evidence in result.evidence:
                lines.append(f"    {evidence}")

            for error in result.validation_errors:
                lines.append(f"    ⚠️ {error}")

        lines.append("")

        if all_passed:
            lines.append("🎉 모든 미션 완료!")
            if include_form_link:
                lines.append("")
                lines.append("📝 인증 폼 제출:")
                lines.append(GOOGLE_FORM_URL)
        else:
            passed = sum(1 for r in checklist.values() if r.status == "✅")
            total = len(checklist)
            lines.append(f"⏳ 진행률: {passed}/{total}")

        return "\n".join(lines)

    def save_checklist_to_vault(self, date: datetime, checklist: Dict[str, ChecklistResult]) -> bool:
        """Save checklist to Obsidian vault as a Dataview-queryable markdown file.

        File: ~/mingming-vault/taling/checklists/YYYY-MM-DD.md
        """
        try:
            date_str = date.strftime("%Y-%m-%d")
            weekday = date.weekday()
            day_type = "월수금" if weekday in [0, 2, 4] else "화목토일"

            all_passed = all(r.status == "✅" for r in checklist.values())
            passed_count = sum(1 for r in checklist.values() if r.status == "✅")
            total_count = len(checklist)
            status = "Done" if all_passed else "In Progress"

            frontmatter = {
                "type": "taling-checklist",
                "date": date_str,
                "day_type": day_type,
                "status": status,
                "passed": passed_count,
                "total": total_count,
                "all_complete": all_passed,
                "updated": taling_io.now(),
            }

            # Build markdown body with checklist items
            body_lines = [f"# 탈잉 챌린지 {date_str}"]
            body_lines.append("")
            body_lines.append("## 체크리스트")
            body_lines.append("")

            for item_type, result in sorted(checklist.items()):
                checked = "x" if result.status == "✅" else " "
                body_lines.append(f"- [{checked}] {item_type}")

                for evidence in result.evidence:
                    body_lines.append(f"    - {evidence}")

                for error in result.validation_errors:
                    body_lines.append(f"    - ⚠️ {error}")

            body_lines.append("")
            body_lines.append(f"진행률: {passed_count}/{total_count}")

            if all_passed:
                body_lines.append("")
                body_lines.append("모든 미션 완료!")

            body = "\n".join(body_lines)
            filename = f"{date_str}.md"

            fpath = taling_io.write_entry("checklists", filename, frontmatter, body)
            print(f"Saved checklist to vault: {fpath}")
            return True

        except Exception as e:
            print(f"Error saving to vault: {e}")
            return False

    def send_telegram_message(self, message: str) -> bool:
        """Send message to Telegram topic."""
        try:
            result = subprocess.run([
                "clawdbot", "message", "send",
                "--channel", "telegram",
                "-t", GROUP_ID,
                "--thread-id", str(THREAD_ID),
                message
            ], check=True, capture_output=True, text=True)
            print(f"Sent Telegram message")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to send Telegram message: {e.stderr}")
            return False

    def get_telegram_updates(self) -> List[Dict]:
        """Get new updates from Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {
            "offset": self.state["last_update_id"] + 1,
            "timeout": 5,
            "allowed_updates": json.dumps(["message"]),
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query_string}"

        try:
            req = urllib.request.Request(full_url)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())

            if data.get("ok"):
                return data.get("result", [])
            return []
        except Exception as e:
            print(f"Error getting updates: {e}")
            return []

    def process_update(self, update: Dict) -> Optional[Dict]:
        """Process a single Telegram update.

        Returns processed file info if zip/mission file detected.
        """
        message = update.get("message", {})
        chat = message.get("chat", {})

        # Check if message is in target group and thread
        if str(chat.get("id")) != GROUP_ID:
            return None

        if message.get("message_thread_id") != THREAD_ID:
            return None

        # Check for document (zip files)
        document = message.get("document")
        if document:
            filename = document.get("file_name", "")
            file_id = document["file_id"]

            # Check if it's a zip file
            if filename.lower().endswith(".zip"):
                return {
                    "type": "zip",
                    "file_id": file_id,
                    "filename": filename,
                    "date": datetime.fromtimestamp(message.get("date", 0)),
                }
            else:
                # Regular document - classify it
                file_type = self.classify_file(filename, message.get("caption", ""))
                if file_type:
                    return {
                        "type": "file",
                        "file_type": file_type,
                        "file_id": file_id,
                        "filename": filename,
                        "date": datetime.fromtimestamp(message.get("date", 0)),
                    }

        # Check for photo
        photo = message.get("photo")
        if photo:
            caption = message.get("caption", "photo.jpg")
            file_id = photo[-1]["file_id"]  # Largest photo
            file_type = self.classify_file(caption)

            if file_type:
                return {
                    "type": "file",
                    "file_type": file_type,
                    "file_id": file_id,
                    "filename": caption,
                    "date": datetime.fromtimestamp(message.get("date", 0)),
                }

        return None

    def check(self):
        """Check for new uploads and process them."""
        updates = self.get_telegram_updates()

        if not updates:
            print("No new updates")
            return

        for update in updates:
            update_id = update.get("update_id", 0)

            file_info = self.process_update(update)

            if file_info:
                self._handle_file_upload(file_info)

            self.state["last_update_id"] = update_id

        self._save_state()

    def _handle_file_upload(self, file_info: Dict):
        """Handle a detected file upload."""
        date = file_info["date"]
        date_str = date.strftime("%Y-%m-%d")

        print(f"Processing: {file_info['filename']} ({file_info['type']})")

        if file_info["type"] == "zip":
            # Download and parse zip
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
                temp_path = Path(tf.name)

            if self.download_telegram_file(file_info["file_id"], temp_path):
                files = self.parse_zip_file(temp_path)

                # Generate checklist
                checklist = self.generate_checklist(date, files)

                # Save to Obsidian vault
                self.save_checklist_to_vault(date, checklist)

                # Send Telegram message
                all_passed = all(r.status == "✅" for r in checklist.values())
                message = self.format_checklist_message(date, checklist, include_form_link=all_passed)
                self.send_telegram_message(message)

                # Save to state
                self.state["daily_checklists"][date_str] = {
                    item_type: result.to_dict()
                    for item_type, result in checklist.items()
                }

            temp_path.unlink(missing_ok=True)

        else:
            # Single file - update running checklist
            file_type = file_info.get("file_type")
            if not file_type:
                return

            # Download file
            dest_dir = Path.home() / "clawd/temp/taling_extracted"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{file_type}_{date_str}.jpg"

            if self.download_telegram_file(file_info["file_id"], dest_path):
                # Get or create daily checklist
                if date_str not in self.state["daily_checklists"]:
                    self.state["daily_checklists"][date_str] = {}

                # Update single item
                result = self.validate_item(file_type, dest_path)
                self.state["daily_checklists"][date_str][file_type] = result.to_dict()

                # Regenerate full checklist
                checklist = {}
                required = self.get_required_items(date)

                for item in required:
                    if item in self.state["daily_checklists"][date_str]:
                        data = self.state["daily_checklists"][date_str][item]
                        r = ChecklistResult(item)
                        r.status = data.get("status", "❌")
                        r.evidence = data.get("evidence", [])
                        r.filename = data.get("filename")
                        checklist[item] = r
                    else:
                        checklist[item] = ChecklistResult(item)

                # Save to Obsidian vault
                self.save_checklist_to_vault(date, checklist)

                # Send progress update
                all_passed = all(r.status == "✅" for r in checklist.values())
                message = self.format_checklist_message(date, checklist, include_form_link=all_passed)
                self.send_telegram_message(message)

    def reset(self):
        """Reset state (for testing)."""
        self.state = {
            "last_update_id": 0,
            "processed_files": {},
            "daily_checklists": {},
        }
        self._save_state()
        print("State reset")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: checklist_automation.py [check|reset]")
        sys.exit(1)

    command = sys.argv[1]

    try:
        automation = TalingChecklistAutomation()

        if command == "check":
            automation.check()
        elif command == "reset":
            automation.reset()
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)

    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
