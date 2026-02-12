#!/usr/bin/env python3
"""
Proactive Agent Background Checker
Runs periodic checks and logs findings to memory/proactive-queue.md
Only notifies on urgent/high-value items (rate-limited)
"""

import json
import os
import sys
import datetime
import subprocess
import fcntl
from pathlib import Path
from typing import Dict, List, Tuple

# Add clawd/scripts directory to path for imports (message_dedup.py lives there)
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from message_dedup import MessageDeduplicator, format_target

# Constants
WORKSPACE = Path("/Users/dayejeong/clawd")
QUEUE_FILE = WORKSPACE / "memory" / "proactive-queue.md"
STATE_FILE = WORKSPACE / "memory" / "proactive-state.json"
LOCK_FILE = WORKSPACE / "memory" / "proactive-check.lock"
PROJECTS_DIR = WORKSPACE / "memory" / "projects"

# Telegram config (JARVIS HQ group)
TELEGRAM_GROUP = "-1003242721592"
TOPIC_CALENDAR = "167"  # 📅 일정/준비 관련
TOPIC_NEWS = "171"      # 📰 뉴스/트렌드

# Thresholds for scoring
SCORE_URGENT = 80       # Immediate notification
SCORE_HIGH_VALUE = 60   # Notify if last alert > 4 hours
SCORE_MEDIUM = 40       # Log only, notify if > 8 hours
SCORE_LOW = 20          # Log only

# Rate limiting
MAX_ALERTS_PER_DAY = 3
MIN_HOURS_BETWEEN_ALERTS = 2


class ExecutionLock:
    """
    File-based execution lock to prevent concurrent runs.
    Uses flock for atomic locking.
    """
    
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_fd = None
    
    def __enter__(self):
        """Acquire lock."""
        try:
            # Create lock file if doesn't exist
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_fd = open(self.lock_file, 'w')
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write PID for debugging
            self.lock_fd.write(f"{os.getpid()}\n{datetime.datetime.now().isoformat()}\n")
            self.lock_fd.flush()
            
            return self
        except IOError as e:
            # Lock already held
            if self.lock_fd:
                self.lock_fd.close()
            raise RuntimeError("Another instance is already running") from e
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
            except:
                pass
            
            # Clean up lock file
            try:
                self.lock_file.unlink(missing_ok=True)
            except:
                pass
        
        return False  # Don't suppress exceptions


class ProactiveChecker:
    def __init__(self):
        self.state = self.load_state()
        self.findings = []
        self.dedup = MessageDeduplicator()
        
    def load_state(self) -> Dict:
        """Load state file with alert history"""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {
            "lastCheck": None,
            "lastAlert": None,
            "alertsToday": 0,
            "lastAlertDate": None
        }
    
    def save_state(self):
        """Save state file"""
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)
    
    def log_finding(self, category: str, message: str, score: int, metadata: Dict = None):
        """Add finding to queue"""
        finding = {
            "timestamp": datetime.datetime.now().isoformat(),
            "category": category,
            "message": message,
            "score": score,
            "metadata": metadata or {}
        }
        self.findings.append(finding)
    
    def check_calendar_deadlines(self) -> None:
        """Check for upcoming deadlines in next 24-48 hours"""
        try:
            # Use icalBuddy to fetch tomorrow's events
            result = subprocess.run([
                "/opt/homebrew/bin/icalBuddy",
                "-n", "-nc", "-b", "",
                "-ps", "||",
                "-ic", "daye@ronik.io,개인,Personal,Taling,daye.jjeong@gmail.com",
                "eventsToday+1"  # Returns both today + tomorrow
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return
            
            events = result.stdout.strip().split("\n")
            important_keywords = ["회의", "미팅", "발표", "제출", "마감", "PT", "수업"]
            
            # Track seen events to avoid duplicates
            seen_events = set()
            
            for event in events:
                if not event.strip():
                    continue
                
                # BUGFIX 2026-02-04: eventsToday+1 returns both today/tomorrow
                # Filter out today's events (labeled "today at")
                # Only process "tomorrow at" or unlabeled tomorrow events
                if "today at" in event:
                    continue  # Skip today's events
                
                # Extract event title (before time or notes)
                event_title = event.split("location:")[0].split("notes:")[0].split("tomorrow at")[0].strip()
                
                # Deduplicate by title
                if event_title in seen_events:
                    continue
                seen_events.add(event_title)
                
                # Check if event contains important keywords
                is_important = any(kw in event for kw in important_keywords)
                
                if is_important:
                    score = 70  # High priority for important upcoming events
                    self.log_finding(
                        "calendar",
                        f"내일 중요 일정: {event_title}",
                        score,
                        {"event": event_title}
                    )
        except Exception as e:
            # Silent failure - don't disrupt background process
            pass
    
    def check_vault_backlog(self) -> None:
        """Check vault t-*.md for overdue high-priority tasks"""
        try:
            today = datetime.date.today().isoformat()
            overdue_tasks = []

            for task_file in PROJECTS_DIR.rglob("t-*.md"):
                try:
                    fm = self._parse_frontmatter(task_file.read_text(encoding="utf-8"))
                except Exception:
                    continue

                priority = fm.get("priority", "medium")
                status = fm.get("status", "todo")
                deadline = str(fm.get("deadline", ""))

                if priority == "high" and status not in ("done", "on_hold") and deadline and deadline < today:
                    overdue_tasks.append({
                        "id": fm.get("id", ""),
                        "title": fm.get("title", "(untitled)"),
                        "deadline": deadline,
                    })

            if overdue_tasks:
                count = len(overdue_tasks)
                score = 85 if count >= 3 else 65
                task_names = [t["title"] for t in overdue_tasks[:3]]

                self.log_finding(
                    "backlog",
                    f"밀린 중요 작업 {count}개 발견: {', '.join(task_names)}",
                    score,
                    {"count": count, "tasks": [t["id"] for t in overdue_tasks[:5]]}
                )
        except Exception as e:
            pass

    @staticmethod
    def _parse_frontmatter(text: str) -> Dict:
        """Parse YAML frontmatter from markdown text."""
        if not text.startswith("---"):
            return {}
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}
        fm = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                fm[key.strip()] = val.strip().strip("'\"")
        return fm
    
    def check_system_health(self) -> None:
        """Check system issues from recent logs"""
        try:
            # REMOVED 2026-02-04: model_health.json is now PASSIVE monitoring
            # Real model failures detected through actual usage, not proactive pinging
            # See: scripts/check_model_health.sh (redesigned to prevent false positives)
            
            # Check failed tasks queue
            failed_queue = WORKSPACE / "memory" / "failed_tasks_queue.json"
            if failed_queue.exists():
                with open(failed_queue) as f:
                    queue = json.load(f)
                
                tasks = queue.get("tasks", [])
                if tasks:
                    score = 75
                    self.log_finding(
                        "system",
                        f"실패한 작업 {len(tasks)}개 대기 중",
                        score,
                        {"count": len(tasks)}
                    )
        except Exception as e:
            pass
    
    def check_unread_notes(self) -> None:
        """Check for uncategorized memory notes"""
        try:
            # Look for recent memory files with TODO or FIXME
            memory_dir = WORKSPACE / "memory"
            today = datetime.date.today()
            recent_files = []
            
            for f in memory_dir.glob("2026-*.md"):
                # Check files from last 3 days
                try:
                    date_str = f.stem.split("-")[:3]
                    file_date = datetime.date(int(date_str[0]), int(date_str[1]), int(date_str[2]))
                    
                    if (today - file_date).days <= 3:
                        content = f.read_text()
                        if "TODO" in content or "FIXME" in content or "⚠️" in content:
                            recent_files.append(f.name)
                except:
                    continue
            
            if recent_files:
                score = 45  # Medium priority
                self.log_finding(
                    "notes",
                    f"최근 메모에 TODO/FIXME 항목 있음: {', '.join(recent_files[:3])}",
                    score,
                    {"files": recent_files}
                )
        except Exception as e:
            pass
    
    def check_rate_limit(self) -> Tuple[bool, str]:
        """Check if we can send alert (rate limiting)"""
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Reset daily counter
        if self.state.get("lastAlertDate") != today_str:
            self.state["alertsToday"] = 0
            self.state["lastAlertDate"] = today_str
        
        # Check daily limit
        if self.state["alertsToday"] >= MAX_ALERTS_PER_DAY:
            return False, "Daily alert limit reached"
        
        # Check time since last alert
        if self.state.get("lastAlert"):
            last_alert = datetime.datetime.fromisoformat(self.state["lastAlert"])
            hours_since = (now - last_alert).total_seconds() / 3600
            
            if hours_since < MIN_HOURS_BETWEEN_ALERTS:
                return False, f"Too soon (last alert {hours_since:.1f}h ago)"
        
        return True, "OK"
    
    def write_to_queue(self):
        """Write findings to memory/proactive-queue.md"""
        if not self.findings:
            return
        
        # Prepare markdown
        lines = []
        lines.append(f"\n## Check Run: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        
        for finding in self.findings:
            emoji = "🔴" if finding["score"] >= SCORE_URGENT else "🟡" if finding["score"] >= SCORE_HIGH_VALUE else "🔵"
            lines.append(f"- {emoji} [{finding['category']}] **Score: {finding['score']}** - {finding['message']}")
            if finding["metadata"]:
                lines.append(f"  - Metadata: {json.dumps(finding['metadata'], ensure_ascii=False)}")
        
        lines.append("")
        
        # Append to queue file
        with open(QUEUE_FILE, "a") as f:
            f.write("\n".join(lines))
    
    def should_notify(self, max_score: int) -> Tuple[bool, str]:
        """Determine if we should send notification based on score and rate limit"""
        if max_score >= SCORE_URGENT:
            can_alert, reason = self.check_rate_limit()
            if not can_alert:
                return False, f"Urgent but rate limited: {reason}"
            return True, "Urgent item"
        
        if max_score >= SCORE_HIGH_VALUE:
            can_alert, reason = self.check_rate_limit()
            if not can_alert:
                return False, f"High value but rate limited: {reason}"
            
            # Check if last alert was > 4 hours ago
            if self.state.get("lastAlert"):
                last_alert = datetime.datetime.fromisoformat(self.state["lastAlert"])
                hours = (datetime.datetime.now() - last_alert).total_seconds() / 3600
                if hours < 4:
                    return False, f"High value but too soon ({hours:.1f}h)"
            
            return True, "High value item"
        
        return False, "Score too low for notification"
    
    def send_notification(self, findings: List[Dict]):
        """Send Telegram notification for high-priority findings"""
        # Group by category
        by_category = {}
        for f in findings:
            cat = f["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f)
        
        # Build message
        lines = ["🤖 **Proactive Check Alert**\n"]
        
        for cat, items in by_category.items():
            lines.append(f"**{cat.upper()}:**")
            for item in items:
                emoji = "🔴" if item["score"] >= SCORE_URGENT else "🟡"
                lines.append(f"  {emoji} {item['message']}")
            lines.append("")
        
        message = "\n".join(lines)
        
        # Determine topic (calendar vs general)
        topic = TOPIC_CALENDAR if "calendar" in by_category else TOPIC_NEWS
        
        # Check for duplicate message
        target = format_target(TELEGRAM_GROUP, topic)
        if not self.dedup.check_and_record(message, target):
            print(f"Skipping duplicate message (sent within last 5 minutes)", file=sys.stderr)
            return
        
        # Send via clawdbot message
        try:
            subprocess.run([
                "clawdbot", "message", "send",
                "--target", TELEGRAM_GROUP,
                "--thread-id", topic,
                "--message", message
            ], timeout=10)
            
            # Update state
            self.state["lastAlert"] = datetime.datetime.now().isoformat()
            self.state["alertsToday"] = self.state.get("alertsToday", 0) + 1
            self.save_state()
            
        except Exception as e:
            print(f"Failed to send notification: {e}", file=sys.stderr)
    
    def run(self):
        """Main check routine"""
        # Run all checks
        self.check_calendar_deadlines()
        self.check_vault_backlog()
        self.check_system_health()
        self.check_unread_notes()
        
        # Write all findings to queue
        self.write_to_queue()
        
        # Update state
        self.state["lastCheck"] = datetime.datetime.now().isoformat()
        self.save_state()
        
        # Determine if notification needed
        if not self.findings:
            return
        
        max_score = max(f["score"] for f in self.findings)
        high_priority = [f for f in self.findings if f["score"] >= SCORE_HIGH_VALUE]
        
        should_send, reason = self.should_notify(max_score)
        
        if should_send and high_priority:
            self.send_notification(high_priority)
        else:
            # Silent - logged to queue only
            pass


if __name__ == "__main__":
    try:
        with ExecutionLock(LOCK_FILE):
            checker = ProactiveChecker()
            checker.run()
    except RuntimeError as e:
        # Another instance is running, exit silently
        print(f"Exiting: {e}", file=sys.stderr)
        sys.exit(0)  # Exit 0 to avoid cron error emails
