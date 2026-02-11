#!/usr/bin/env python3
"""
Prompt Guard - Injection Detection System

Scans incoming messages for prompt injection, jailbreak attempts, and malicious patterns.
Applied at message input time before agent processing.

Usage:
    python3 guard.py --message "text to scan"
    python3 guard.py --file path/to/message.txt
    python3 guard.py --dry-run --message "test message"
    
Exit codes:
    0 - Safe (no threats detected or below threshold)
    1 - Blocked (threat severity >= threshold)
    2 - Error
"""

import re
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import os


# Severity levels
class Severity:
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    
    @classmethod
    def from_string(cls, s: str) -> int:
        mapping = {
            'SAFE': cls.SAFE,
            'LOW': cls.LOW,
            'MEDIUM': cls.MEDIUM,
            'HIGH': cls.HIGH,
            'CRITICAL': cls.CRITICAL
        }
        return mapping.get(s.upper(), cls.HIGH)
    
    @classmethod
    def to_string(cls, level: int) -> str:
        mapping = {
            cls.SAFE: 'SAFE',
            cls.LOW: 'LOW',
            cls.MEDIUM: 'MEDIUM',
            cls.HIGH: 'HIGH',
            cls.CRITICAL: 'CRITICAL'
        }
        return mapping.get(level, 'UNKNOWN')


class PromptGuard:
    def __init__(self, config_path: str = None):
        """Initialize Prompt Guard with configuration."""
        if config_path is None:
            script_dir = Path(__file__).parent
            config_path = script_dir / 'config.json'
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Setup logging
        log_path = os.path.expanduser(self.config.get('log_path', '~/.clawdbot/agents/main/logs/prompt-guard.log'))
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(sys.stderr) if self.config.get('dry_run', False) else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger('prompt-guard')
        
        # Compile patterns
        self.patterns = self._compile_patterns()
        
        # Threshold
        self.threshold = Severity.from_string(self.config.get('severity_threshold', 'HIGH'))
    
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
                    self.logger.warning(f"Invalid pattern in {category}: {pattern} - {e}")
        
        return compiled
    
    def _check_whitelist(self, message: str, metadata: Dict = None) -> bool:
        """Check if message is from whitelisted owner or contains safe commands."""
        # Check owner whitelist
        if metadata and metadata.get('user_id') in self.config.get('owner_whitelist', []):
            return True
        
        if metadata and metadata.get('username') in self.config.get('owner_whitelist', []):
            return True
        
        # Check safe command prefixes
        message_lower = message.strip().lower()
        for prefix in self.config.get('safe_command_prefixes', []):
            if message_lower.startswith(prefix.lower()):
                return True
        
        return False
    
    def _match_patterns(self, text: str) -> Dict:
        """Match text against all detection patterns."""
        matches = {}
        weights = self.config.get('severity_weights', {})
        
        # Map category names to weight keys
        weight_key_map = {
            'jailbreak_patterns': 'jailbreak',
            'prompt_injection_patterns': 'injection',
            'data_exfiltration_patterns': 'exfiltration',
            'harmful_intent_patterns': 'harmful'
        }
        
        for category, patterns in self.patterns.items():
            category_matches = []
            for pattern in patterns:
                found = pattern.finditer(text)
                for match in found:
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
        """
        Calculate overall severity based on matches.
        
        Returns:
            (severity_level, confidence_score)
        """
        if not matches:
            return Severity.SAFE, 0.0
        
        # Weighted scoring
        max_weight = 0.0
        total_weight = 0.0
        match_count = 0
        
        for category, data in matches.items():
            weight = data['weight']
            count = data['count']
            
            max_weight = max(max_weight, weight)
            total_weight += weight * count
            match_count += count
        
        # Calculate confidence (0.0 - 1.0)
        confidence = min(1.0, total_weight / 2.0)  # Normalize
        
        # Determine severity
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
        
        # Boost severity if multiple categories matched
        if len(matches) >= 3:
            severity = min(Severity.CRITICAL, severity + 1)
        
        return severity, confidence
    
    def scan(self, message: str, metadata: Dict = None) -> Dict:
        """
        Scan a message for threats.
        
        Args:
            message: The message text to scan
            metadata: Optional metadata (user_id, username, urls, etc.)
        
        Returns:
            dict with keys:
                - safe (bool): Whether message is safe to process
                - severity (str): Severity level (SAFE, LOW, MEDIUM, HIGH, CRITICAL)
                - confidence (float): Confidence score (0.0 - 1.0)
                - labels (list): Matched threat categories
                - reason (str): Human-readable explanation
                - matches (dict): Detailed match information
                - blocked (bool): Whether message should be blocked
        """
        result = {
            'safe': True,
            'severity': 'SAFE',
            'confidence': 0.0,
            'labels': [],
            'reason': 'No threats detected',
            'matches': {},
            'blocked': False,
            'timestamp': datetime.now().astimezone().isoformat()
        }
        
        # Check whitelist first
        if self._check_whitelist(message, metadata):
            result['reason'] = 'Whitelisted user or safe command'
            self.logger.info(f"WHITELISTED | {message[:50]}...")
            return result
        
        # Match patterns
        matches = self._match_patterns(message)
        
        if not matches:
            self.logger.info(f"SAFE | {message[:50]}...")
            return result
        
        # Calculate severity
        severity_level, confidence = self._calculate_severity(matches)
        severity_str = Severity.to_string(severity_level)
        
        # Build labels
        labels = list(matches.keys())
        
        # Determine if should block
        blocked = severity_level >= self.threshold
        
        # Build reason
        reason_parts = [f"Detected {len(matches)} threat category(ies):"]
        for category in labels:
            count = matches[category]['count']
            reason_parts.append(f"  - {category}: {count} match(es)")
        reason = "\n".join(reason_parts)
        
        result.update({
            'safe': not blocked,
            'severity': severity_str,
            'confidence': confidence,
            'labels': labels,
            'reason': reason,
            'matches': matches,
            'blocked': blocked
        })
        
        # Log detection
        log_msg = f"{severity_str} | Confidence: {confidence:.2f} | Labels: {', '.join(labels)} | Message: {message[:100]}..."
        self.logger.warning(log_msg)
        
        # Notify if critical
        if severity_level == Severity.CRITICAL and self.config.get('notify_critical', False):
            self._notify_critical(result, message)
        
        return result
    
    def _notify_critical(self, result: Dict, message: str):
        """Send Telegram notification for critical detections."""
        try:
            group_id = self.config.get('telegram_group_id')
            thread_id = self.config.get('telegram_thread_id')
            
            if not group_id:
                self.logger.warning("CRITICAL detection but no telegram_group_id configured")
                return
            
            notification = (
                f"🚨 CRITICAL Prompt Guard Alert\n\n"
                f"**Severity:** {result['severity']}\n"
                f"**Confidence:** {result['confidence']:.0%}\n"
                f"**Labels:** {', '.join(result['labels'])}\n\n"
                f"**Message Preview:**\n{message[:200]}...\n\n"
                f"**Time:** {result['timestamp']}"
            )
            
            # Build clawdbot message command
            cmd = ['clawdbot', 'message', 'send', '-t', str(group_id)]
            if thread_id:
                cmd.extend(['--thread-id', str(thread_id)])
            cmd.append(notification)
            
            import subprocess
            subprocess.run(cmd, check=False, capture_output=True)
            self.logger.info("CRITICAL notification sent to Telegram")
        
        except Exception as e:
            self.logger.error(f"Failed to send CRITICAL notification: {e}")
    
    def check_urls(self, urls: List[str]) -> List[Dict]:
        """
        Check URLs for suspicious patterns (future enhancement).
        
        Args:
            urls: List of URLs extracted from message
        
        Returns:
            List of suspicious URL findings
        """
        # Placeholder for URL checking logic
        # Could check for:
        # - Known malicious domains
        # - Suspicious TLDs
        # - URL shorteners
        # - Homograph attacks
        return []


def main():
    parser = argparse.ArgumentParser(description='Prompt Guard - Injection Detection')
    parser.add_argument('--message', type=str, help='Message text to scan')
    parser.add_argument('--file', type=Path, help='File containing message text')
    parser.add_argument('--config', type=Path, help='Config file path (default: ./config.json)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (verbose output)')
    parser.add_argument('--json', action='store_true', help='Output JSON result')
    parser.add_argument('--metadata', type=str, help='JSON metadata (user_id, username, etc.)')
    
    args = parser.parse_args()
    
    # Get message text
    if args.message:
        text = args.message
    elif args.file:
        with open(args.file, 'r') as f:
            text = f.read()
    else:
        # Read from stdin
        text = sys.stdin.read()
    
    # Parse metadata
    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print("ERROR: Invalid JSON metadata", file=sys.stderr)
            sys.exit(2)
    
    # Load config
    config_path = args.config if args.config else None
    
    # Override dry_run if specified
    if args.dry_run and config_path:
        with open(config_path, 'r') as f:
            config = json.load(f)
        config['dry_run'] = True
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(config, tmp)
            config_path = tmp.name
    
    # Initialize guard
    guard = PromptGuard(config_path=config_path)
    
    # Scan message
    result = guard.scan(text, metadata=metadata)
    
    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result['blocked']:
            print(f"❌ BLOCKED: {result['severity']} threat detected", file=sys.stderr)
            print(f"   Confidence: {result['confidence']:.0%}", file=sys.stderr)
            print(f"   Labels: {', '.join(result['labels'])}", file=sys.stderr)
            print(f"   {result['reason']}", file=sys.stderr)
        else:
            print(f"✅ SAFE: Severity {result['severity']} below threshold")
    
    # Exit code
    sys.exit(1 if result['blocked'] else 0)


if __name__ == '__main__':
    main()
