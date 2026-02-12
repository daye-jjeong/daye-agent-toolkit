#!/usr/bin/env python3
import os
import re
import datetime
import subprocess
import sys

# Configuration
DOCS_DIR = "memory"
DAYS_UNTIL_OUTDATED = 30
DEPRECATED_TERMS = [
    "gpt-3.5",
    "gpt-4-turbo",
    "legacy protocol",
    "direct execution",
]
TELEGRAM_TOPIC_ID = "167" # Using "Scheduling/Prep" or generic. TOOLS.md says 167 is Morning brief/Evening prep. 
# Maybe better to use the main group without topic or a specific "System" topic if it existed.
# TOOLS.md says JARVIS HQ Group ID: -1003242721592. 
# I will use the main group, maybe without topic or just default.
TELEGRAM_GROUP_ID = "-1003242721592"

def get_files(directory):
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".md"):
                files.append(os.path.join(root, filename))
    return files

def check_broken_links(file_path, content):
    broken_links = []
    # Match [text](path)
    links = re.findall(r'\[.*?\]\((.*?)\)', content)
    for link in links:
        if link.startswith("http") or link.startswith("#"):
            continue
        
        # Resolve relative paths
        base_dir = os.path.dirname(file_path)
        target_path = os.path.join(base_dir, link)
        
        # Remove anchors
        if "#" in target_path:
            target_path = target_path.split("#")[0]
            
        if not os.path.exists(target_path):
            broken_links.append(link)
    return broken_links

def check_deprecated_terms(content):
    found_terms = []
    for term in DEPRECATED_TERMS:
        if term.lower() in content.lower():
            found_terms.append(term)
    return found_terms

def check_outdated(content):
    # Look for **Last Updated:** YYYY-MM-DD
    match = re.search(r'\*\*Last Updated:\*\*\s*(\d{4}-\d{2}-\d{2})', content)
    if match:
        date_str = match.group(1)
        last_updated = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        age = (datetime.datetime.now() - last_updated).days
        if age > DAYS_UNTIL_OUTDATED:
            return age, date_str
    return None

def main():
    report = []
    files = get_files(DOCS_DIR)
    
    issues_found = False
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            report.append(f"❌ Could not read {file_path}: {e}")
            issues_found = True
            continue

        file_issues = []
        
        # 1. Broken Links
        broken = check_broken_links(file_path, content)
        if broken:
            file_issues.append(f"  - Broken Links: {', '.join(broken)}")
            
        # 2. Deprecated Terms
        deprecated = check_deprecated_terms(content)
        if deprecated:
            file_issues.append(f"  - Deprecated Terms: {', '.join(deprecated)}")
            
        # 3. Outdated
        outdated = check_outdated(content)
        if outdated:
            age, date_str = outdated
            file_issues.append(f"  - Outdated: {date_str} ({age} days old)")

        if file_issues:
            issues_found = True
            report.append(f"📄 **{os.path.basename(file_path)}**")
            report.extend(file_issues)
            
    if issues_found:
        summary = "🚨 **Policy & Health Audit Report**\n\n" + "\n".join(report)
    else:
        summary = "✅ **Policy & Health Audit Passed**\nAll documents are healthy."

    print(summary)
    
    # Send to Telegram
    try:
        subprocess.run([
            "clawdbot", "message", "send",
            "-t", TELEGRAM_GROUP_ID,
            "-m", summary
        ], check=True)
    except Exception as e:
        print(f"Failed to send to Telegram: {e}")

if __name__ == "__main__":
    main()
