#!/usr/bin/env python3
"""
Prompt Guard Inbound Message Scanner (Stage 1)

Token-0 local pattern detection for Clawdbot message intake.
Scans immediately after inbound user message, before planning/tool use.

Features:
- No LLM calls - pure pattern matching
- Blocks HIGH and CRITICAL severity
- Allows MEDIUM with warning logged
- Override phrase support for owner
- Logs to memory/prompt_guard_log.jsonl

Usage:
    python3 scripts/prompt_guard_scan.py --message "text" --user-id "12345"
    echo "message" | python3 scripts/prompt_guard_scan.py --user-id "12345"
    
Exit codes:
    0 - Allow (safe or below threshold)
    1 - Block (HIGH/CRITICAL detected)
    2 - Error
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import os
import subprocess


class Severity:
    """Severity levels for threat detection."""
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    
    _names = {0: 'SAFE', 1: 'LOW', 2: 'MEDIUM', 3: 'HIGH', 4: 'CRITICAL'}
    _values = {'SAFE': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
    
    @classmethod
    def from_string(cls, s: str) -> int:
        return cls._values.get(s.upper(), cls.HIGH)
    
    @classmethod
    def to_string(cls, level: int) -> str:
        return cls._names.get(level, 'UNKNOWN')


class PromptGuardScanner:
    """
    Inbound message scanner for prompt injection detection.
    
    Stage 1: Token-0 local pattern detection only.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize scanner with configuration."""
        if config_path is None:
            # Try workspace config first, then skill config
            workspace = Path(__file__).parent.parent
            config_path = workspace / 'config' / 'prompt_guard.json'
            if not config_path.exists():
                config_path = workspace / 'skills' / 'prompt-guard' / 'config.json'
        
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Set up log path
        workspace = Path(__file__).parent.parent
        self.log_path = workspace / self.config.get('log_path', 'memory/prompt_guard_log.jsonl')
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Compile patterns
        self.patterns = self._compile_patterns()
        
        # Threshold settings
        self.threshold = Severity.from_string(self.config.get('severity_threshold', 'HIGH'))
        self.block_levels = [Severity.from_string(l) for l in self.config.get('block_levels', ['HIGH', 'CRITICAL'])]
        self.warn_levels = [Severity.from_string(l) for l in self.config.get('warn_levels', ['MEDIUM'])]
    
    def _compile_patterns(self) -> Dict:
        """Compile regex patterns from config."""
        rules = self.config.get('detection_rules', {})
        compiled = {}
        
        for category, patterns in rules.items():
            compiled[category] = []
            for pattern in patterns:
                try:
                    compiled[category].append(re.compile(pattern, re.IGNORECASE | re.MULTILINE))
                except re.error as e:
                    print(f"WARNING: Invalid pattern in {category}: {pattern} - {e}", file=sys.stderr)
        
        return compiled
    
    def _check_override(self, message: str, user_id: str) -> bool:
        """
        Check if message contains override phrase from owner.
        
        Owner can use 'override:allow' to bypass blocking.
        Still scans and logs, but allows the message through.
        """
        owner_id = str(self.config.get('owner_id', ''))
        override_phrase = self.config.get('override_phrase', 'override:allow')
        
        if str(user_id) == owner_id:
            if override_phrase.lower() in message.lower():
                return True
        
        return False
    
    def _check_safe_prefix(self, message: str) -> bool:
        """Check if message starts with a safe command prefix."""
        message_lower = message.strip().lower()
        for prefix in self.config.get('safe_command_prefixes', []):
            if message_lower.startswith(prefix.lower()):
                return True
        return False
    
    def _match_patterns(self, text: str) -> Dict:
        """Match text against all detection patterns."""
        matches = {}
        weights = self.config.get('severity_weights', {})
        
        weight_key_map = {
            'jailbreak_patterns': 'jailbreak',
            'prompt_injection_patterns': 'injection',
            'data_exfiltration_patterns': 'exfiltration',
            'harmful_intent_patterns': 'harmful'
        }
        
        for category, patterns in self.patterns.items():
            category_matches = []
            for pattern in patterns:
                for match in pattern.finditer(text):
                    category_matches.append({
                        'pattern': pattern.pattern,
                        'match': match.group(0),
                        'start': match.start(),
                        'end': match.end()
                    })
            
            if category_matches:
                weight_key = weight_key_map.get(category, category.replace('_patterns', ''))
                matches[category] = {
                    'count': len(category_matches),
                    'matches': category_matches,
                    'weight': weights.get(weight_key, 0.5)
                }
        
        return matches
    
    def _calculate_severity(self, matches: Dict) -> Tuple[int, float]:
        """Calculate severity level and confidence score."""
        if not matches:
            return Severity.SAFE, 0.0
        
        max_weight = 0.0
        total_weight = 0.0
        
        for category, data in matches.items():
            weight = data['weight']
            count = data['count']
            max_weight = max(max_weight, weight)
            total_weight += weight * count
        
        confidence = min(1.0, total_weight / 2.0)
        
        if max_weight >= 0.95:
            severity = Severity.CRITICAL
        elif max_weight >= 0.85:
            severity = Severity.HIGH
        elif max_weight >= 0.6:
            severity = Severity.MEDIUM
        elif max_weight >= 0.3:
            severity = Severity.LOW
        else:
            severity = Severity.SAFE
        
        # Boost if multiple categories
        if len(matches) >= 3:
            severity = min(Severity.CRITICAL, severity + 1)
        
        return severity, confidence
    
    def _log_detection(self, result: Dict, message: str, user_id: str, session_id: str = None):
        """Log detection to JSONL file."""
        log_entry = {
            'timestamp': datetime.now().astimezone().isoformat(),
            'session': session_id or 'unknown',
            'user_id': user_id,
            'severity': result['severity'],
            'confidence': result['confidence'],
            'patterns': result['labels'],
            'snippet': message[:200] + ('...' if len(message) > 200 else ''),
            'blocked': result['blocked'],
            'override_used': result.get('override_used', False)
        }
        
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"WARNING: Failed to log detection: {e}", file=sys.stderr)
    
    def _notify_critical(self, result: Dict, message: str, user_id: str, is_group: bool = False):
        """Send Telegram notification for CRITICAL detections."""
        if not self.config.get('notify_critical', False):
            return
        
        # Only notify if in group context or always notify critical
        if not is_group and not self.config.get('always_notify_critical', True):
            return
        
        group_id = self.config.get('telegram_group_id')
        if not group_id:
            return
        
        thread_id = self.config.get('telegram_thread_id')
        owner_id = self.config.get('owner_id', '')
        
        notification = (
            f"🚨 **CRITICAL Prompt Guard Alert**\n\n"
            f"**Severity:** {result['severity']}\n"
            f"**Confidence:** {result['confidence']:.0%}\n"
            f"**User ID:** {user_id}\n"
            f"**Labels:** {', '.join(result['labels'])}\n\n"
            f"**Message Preview:**\n`{message[:150]}...`\n\n"
            f"**Time:** {datetime.now().isoformat()}"
        )
        
        try:
            cmd = ['clawdbot', 'message', 'send', '-t', str(group_id)]
            if thread_id:
                cmd.extend(['--thread-id', str(thread_id)])
            cmd.append(notification)
            
            subprocess.run(cmd, check=False, capture_output=True, timeout=10)
        except Exception as e:
            print(f"WARNING: Failed to send CRITICAL notification: {e}", file=sys.stderr)
    
    def scan(
        self,
        message: str,
        user_id: str = None,
        session_id: str = None,
        is_group: bool = False
    ) -> Dict:
        """
        Scan an inbound message for threats.
        
        Args:
            message: The message text to scan
            user_id: User ID of message sender
            session_id: Current session ID
            is_group: Whether message is from a group context
        
        Returns:
            dict with:
                - allow (bool): Whether to allow the message
                - blocked (bool): Whether message should be blocked
                - severity (str): Severity level
                - confidence (float): Confidence score (0.0-1.0)
                - labels (list): Matched threat categories
                - response (str): Response message if blocked
                - override_used (bool): Whether override was used
        """
        if not self.config.get('enabled', True):
            return {
                'allow': True,
                'blocked': False,
                'severity': 'SAFE',
                'confidence': 0.0,
                'labels': [],
                'response': None,
                'override_used': False
            }
        
        result = {
            'allow': True,
            'blocked': False,
            'severity': 'SAFE',
            'confidence': 0.0,
            'labels': [],
            'response': None,
            'override_used': False,
            'matches': {}
        }
        
        user_id = str(user_id) if user_id else 'unknown'
        
        # Check safe command prefixes first
        if self._check_safe_prefix(message):
            return result
        
        # Check for override phrase from owner
        override_used = self._check_override(message, user_id)
        result['override_used'] = override_used
        
        # Match patterns
        matches = self._match_patterns(message)
        
        if not matches:
            return result
        
        # Calculate severity
        severity_level, confidence = self._calculate_severity(matches)
        severity_str = Severity.to_string(severity_level)
        
        result['severity'] = severity_str
        result['confidence'] = confidence
        result['labels'] = list(matches.keys())
        result['matches'] = matches
        
        # Determine action
        should_block = severity_level in self.block_levels
        should_warn = severity_level in self.warn_levels
        
        # Override: owner can bypass with override phrase
        if override_used and should_block:
            should_block = False
            result['override_used'] = True
        
        result['blocked'] = should_block
        result['allow'] = not should_block
        
        # Set response if blocked
        if should_block:
            # Use Korean response by default
            result['response'] = self.config.get('blocked_response_korean')
        
        # Log detection (for MEDIUM and above)
        if severity_level >= Severity.MEDIUM:
            self._log_detection(result, message, user_id, session_id)
        
        # Notify for CRITICAL
        if severity_level == Severity.CRITICAL:
            self._notify_critical(result, message, user_id, is_group)
        
        return result
    
    def get_blocked_response(self, lang: str = 'ko') -> str:
        """Get the blocked response message."""
        if lang == 'ko':
            return self.config.get('blocked_response_korean', 
                '🛡️ 보안 검사 결과, 이 메시지에서 잠재적인 프롬프트 인젝션 시도가 감지되었습니다.\n\n'
                '도구 실행이 차단되었습니다.\n\n다른 방식으로 요청을 다시 표현해 주시겠어요?')
        else:
            return self.config.get('blocked_response_english',
                '🛡️ Security scan detected a potential prompt injection attempt in this message.\n\n'
                'Tool execution has been blocked.\n\nWould you like to rephrase your request differently?')


def main():
    parser = argparse.ArgumentParser(description='Prompt Guard Inbound Message Scanner')
    parser.add_argument('--message', '-m', type=str, help='Message text to scan')
    parser.add_argument('--file', '-f', type=Path, help='File containing message')
    parser.add_argument('--user-id', '-u', type=str, default='unknown', help='User ID')
    parser.add_argument('--session-id', '-s', type=str, help='Session ID')
    parser.add_argument('--config', '-c', type=Path, help='Config file path')
    parser.add_argument('--is-group', '-g', action='store_true', help='Message from group')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode (exit code only)')
    
    args = parser.parse_args()
    
    # Get message
    if args.message:
        text = args.message
    elif args.file:
        with open(args.file, 'r') as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("ERROR: No message provided", file=sys.stderr)
        sys.exit(2)
    
    try:
        scanner = PromptGuardScanner(config_path=args.config)
        result = scanner.scan(
            message=text,
            user_id=args.user_id,
            session_id=args.session_id,
            is_group=args.is_group
        )
        
        if args.json:
            # Remove matches from output for cleaner JSON
            output = {k: v for k, v in result.items() if k != 'matches'}
            print(json.dumps(output, indent=2, ensure_ascii=False))
        elif not args.quiet:
            if result['blocked']:
                print(f"❌ BLOCKED: {result['severity']} threat detected", file=sys.stderr)
                print(f"   Confidence: {result['confidence']:.0%}", file=sys.stderr)
                print(f"   Labels: {', '.join(result['labels'])}", file=sys.stderr)
                if result['response']:
                    print(f"\n{result['response']}")
            elif result['severity'] != 'SAFE':
                print(f"⚠️ WARNING: {result['severity']} detected (allowed)", file=sys.stderr)
                print(f"   Confidence: {result['confidence']:.0%}", file=sys.stderr)
            else:
                print(f"✅ SAFE")
        
        sys.exit(1 if result['blocked'] else 0)
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
