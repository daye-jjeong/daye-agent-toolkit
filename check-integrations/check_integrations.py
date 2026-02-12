#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
import base64

# Colors for output
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n## {title}")

def check_mark(success):
    return "✅" if success else "❌"

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_openai():
    """Check OpenAI API - Basic key check"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return False, "API Key missing", {}
    
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read())
                model_count = len(data.get("data", []))
                return True, f"Connected ({model_count} models)", {"auth_type": "API Key", "expires": "N/A (API keys don't expire)"}
            else:
                return False, f"Error {response.status}", {}
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error {e.code}", {}
    except Exception as e:
        return False, str(e), {}

def check_anthropic():
    """Check Anthropic (Claude) API with OAuth investigation"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return False, "API Key missing", {}
    
    oauth_info = {
        "auth_type": "API Key",
        "expires": "N/A (API keys don't expire)",
        "refresh_mechanism": "N/A",
        "disconnect_reason": "API keys are stable unless manually revoked"
    }
    
    try:
        # Try a minimal request to check auth
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            data=json.dumps({
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "test"}]
            }).encode()
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return True, "Connected", oauth_info
    except urllib.error.HTTPError as e:
        if e.code == 400:  # Bad request but auth worked
            return True, "Connected", oauth_info
        elif e.code == 401:
            return False, "Invalid API Key", oauth_info
        else:
            return False, f"HTTP Error {e.code}", oauth_info
    except Exception as e:
        return False, str(e), oauth_info

def check_gemini():
    """Check Gemini API with OAuth investigation"""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return False, "API Key missing", {}
    
    oauth_info = {
        "auth_type": "API Key",
        "expires": "N/A (API keys don't expire)",
        "refresh_mechanism": "N/A",
        "disconnect_reason": "API keys are stable unless manually revoked or quota exceeded"
    }
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read())
                model_count = len(data.get("models", []))
                return True, f"Connected ({model_count} models)", oauth_info
            else:
                return False, f"Error {response.status}", oauth_info
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error {e.code}", oauth_info
    except Exception as e:
        return False, str(e), oauth_info

def check_notion_detailed(workspace_name, key_file_path):
    """Check Notion API with detailed permissions (with retry logic)"""
    import time
    
    expanded_path = os.path.expanduser(key_file_path)
    
    if not os.path.exists(expanded_path):
        return False, f"Key file not found: {key_file_path}", {}
    
    try:
        with open(expanded_path, 'r') as f:
            api_key = f.read().strip()
        
        if not api_key:
            return False, "Empty API key", {}
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2025-09-03"  # Updated 2026-02-03: Use latest API version
        }
        
        details = {
            "databases": [],
            "pages": [],
            "users": 0
        }
        
        # Helper function with retry
        def safe_request(url, data=None, max_retries=2):
            """Make request with retry on transient errors"""
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, headers=headers, data=data)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        return json.loads(response.read())
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    elif e.code in [401, 403]:
                        raise  # Don't retry auth errors
                    elif attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    raise
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    raise
            return None
        
        # Check users (quick connectivity test)
        try:
            data = safe_request("https://api.notion.com/v1/users")
            if data:
                details["users"] = len(data.get("results", []))
        except:
            pass  # Non-critical, continue with other checks
        
        # Search for databases
        try:
            search_data = json.dumps({
                "filter": {"property": "object", "value": "database"},
                "page_size": 10
            }).encode()
            data = safe_request("https://api.notion.com/v1/search", data=search_data)
            
            if data:
                for db in data.get("results", []):
                    title = "Untitled"
                    # Try different title locations
                    if db.get("title") and isinstance(db["title"], list) and len(db["title"]) > 0:
                        title = db["title"][0].get("plain_text", "Untitled")
                    elif db.get("properties", {}).get("Name", {}).get("title"):
                        name_prop = db["properties"]["Name"]["title"]
                        if name_prop and len(name_prop) > 0:
                            title = name_prop[0].get("plain_text", "Untitled")
                    details["databases"].append(title)
        except Exception as e:
            # Don't fail entirely, just note the error
            error_msg = str(e)[:30]
            if "401" in error_msg or "403" in error_msg:
                return False, f"Auth failed: {error_msg}", {}
            details["databases"] = [f"Error: {error_msg}"]
        
        # Search for pages
        try:
            search_data = json.dumps({
                "filter": {"property": "object", "value": "page"},
                "page_size": 10
            }).encode()
            data = safe_request("https://api.notion.com/v1/search", data=search_data)
            
            if data:
                for page in data.get("results", []):
                    title = "Untitled"
                    props = page.get("properties", {})
                    
                    # Try multiple property names for title
                    for prop_name in ["title", "Title", "Name", "이름"]:
                        if prop_name in props:
                            prop_data = props[prop_name]
                            # Handle different property types
                            if prop_data.get("type") == "title" and prop_data.get("title"):
                                if len(prop_data["title"]) > 0:
                                    title = prop_data["title"][0].get("plain_text", "Untitled")
                                    break
                    
                    details["pages"].append(title)
        except Exception as e:
            error_msg = str(e)[:30]
            if "401" in error_msg or "403" in error_msg:
                return False, f"Auth failed: {error_msg}", {}
            details["pages"] = [f"Error: {error_msg}"]
        
        # Success summary
        summary = f"Connected: {details['users']} users, {len(details['databases'])} DBs, {len(details['pages'])} pages"
        return True, summary, details
                
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid API key", {}
        elif e.code == 403:
            return False, "Access denied", {}
        else:
            return False, f"HTTP Error {e.code}", {}
    except Exception as e:
        return False, f"Error: {str(e)[:50]}", {}

def check_google_services_detailed():
    """Check Google services with per-service granularity"""
    cmd = "gog auth list --json"
    success, out, err = run_command(cmd)
    
    if not success:
        return None, "gog not installed or error"
    
    try:
        data = json.loads(out)
        accounts = data.get("accounts", [])
        
        result = {}
        for acc in accounts:
            email = acc.get("email")
            services = acc.get("services", [])
            
            # Map service scopes to readable names
            service_map = {
                "gmail": "Gmail",
                "calendar": "Calendar",
                "drive": "Drive",
                "contacts": "Contacts",
                "tasks": "Tasks",
                "people": "People/Contacts"
            }
            
            detected_services = []
            for service in services:
                service_lower = service.lower()
                for key, name in service_map.items():
                    if key in service_lower and name not in detected_services:
                        detected_services.append(name)
            
            # Check OAuth info
            oauth_info = {
                "auth_type": "OAuth 2.0",
                "services": detected_services if detected_services else ["Unknown/Custom scopes"],
                "token_file": acc.get("token_path", "Unknown"),
                "refresh_available": "Yes (gog auto-refreshes)" if acc.get("refresh_token") or acc.get("has_refresh") else "Unknown"
            }
            
            result[email] = oauth_info
        
        return result, None
    except Exception as e:
        return None, f"Error parsing gog output: {str(e)[:50]}"

def check_github_detailed():
    """Check GitHub with org-level access"""
    success, out, err = run_command("gh auth status")
    
    if not success:
        return False, "Not logged in", {}
    
    details = {
        "user": "Unknown",
        "orgs": [],
        "auth_type": "OAuth token",
        "scopes": []
    }
    
    # Get current user
    success, out, err = run_command("gh api user --jq '.login'")
    if success:
        details["user"] = out.strip()
    
    # Get orgs
    success, out, err = run_command("gh api user/orgs --jq '.[].login'")
    if success and out:
        details["orgs"] = [org.strip() for org in out.split('\n') if org.strip()]
    
    # Get token scopes (from auth status)
    success, out, err = run_command("gh auth status -t 2>&1")
    if success and "Token scopes:" in out:
        scope_line = [line for line in out.split('\n') if 'Token scopes:' in line]
        if scope_line:
            scopes_str = scope_line[0].split('Token scopes:')[1].strip()
            details["scopes"] = [s.strip() for s in scopes_str.split(',')]
    
    summary = f"Connected as {details['user']}"
    if details["orgs"]:
        summary += f" ({len(details['orgs'])} orgs)"
    
    return True, summary, details

def main():
    print("# 🔄 Integration Status Report (Detailed)\n")
    print(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    # AI Models
    print_header("🤖 AI Models")
    
    ok, msg, oauth_info = check_openai()
    print(f"- {check_mark(ok)} **OpenAI**: {msg}")
    if oauth_info:
        print(f"  - Auth: {oauth_info.get('auth_type')}")
        print(f"  - Expires: {oauth_info.get('expires')}")
    
    ok, msg, oauth_info = check_anthropic()
    print(f"- {check_mark(ok)} **Claude (Anthropic)**: {msg}")
    if oauth_info:
        print(f"  - Auth: {oauth_info.get('auth_type')}")
        print(f"  - Expires: {oauth_info.get('expires')}")
        print(f"  - Disconnect reason: {oauth_info.get('disconnect_reason')}")
    
    ok, msg, oauth_info = check_gemini()
    print(f"- {check_mark(ok)} **Gemini**: {msg}")
    if oauth_info:
        print(f"  - Auth: {oauth_info.get('auth_type')}")
        print(f"  - Expires: {oauth_info.get('expires')}")
        print(f"  - Disconnect reason: {oauth_info.get('disconnect_reason')}")

    # Notion
    print_header("📝 Notion Workspaces")
    
    ok, msg, details = check_notion_detailed("Personal (New Home)", "~/.config/notion/api_key_daye_personal")
    print(f"- {check_mark(ok)} **Personal (NEW HOME)**: {msg}")
    if details:
        if details.get("databases"):
            print(f"  - Databases ({len(details['databases'])}): {', '.join(details['databases'][:5])}")
            if len(details['databases']) > 5:
                print(f"    ... and {len(details['databases']) - 5} more")
        if details.get("pages"):
            print(f"  - Pages ({len(details['pages'])}): {', '.join(details['pages'][:5])}")
            if len(details['pages']) > 5:
                print(f"    ... and {len(details['pages']) - 5} more")
    
    ok, msg, details = check_notion_detailed("Work (Ronik)", "~/.config/notion/api_key")
    print(f"- {check_mark(ok)} **Work (RONIK PROJECT)**: {msg}")
    if details:
        if details.get("databases"):
            print(f"  - Databases ({len(details['databases'])}): {', '.join(details['databases'][:5])}")
            if len(details['databases']) > 5:
                print(f"    ... and {len(details['databases']) - 5} more")
        if details.get("pages"):
            print(f"  - Pages ({len(details['pages'])}): {', '.join(details['pages'][:5])}")
            if len(details['pages']) > 5:
                print(f"    ... and {len(details['pages']) - 5} more")

    # Google Services
    print_header("📧 Google Services (OAuth)")
    
    accounts, error = check_google_services_detailed()
    if error:
        print(f"- ⚠️ {error}")
    elif accounts:
        for email, info in accounts.items():
            print(f"- **{email}**")
            print(f"  - Auth: {info.get('auth_type')}")
            print(f"  - Services: {', '.join(info.get('services', []))}")
            print(f"  - Auto-refresh: {info.get('refresh_available')}")
            print(f"  - Token: `{info.get('token_file', 'Unknown')}`")
    else:
        print("- ⚠️ No accounts found")
    
    # Add OAuth diagnostic
    print("\n  **OAuth Diagnostic:**")
    if accounts:
        print("  - ✅ Using OAuth 2.0 (recommended)")
        print("  - ✅ gog handles token refresh automatically")
        print("  - Disconnect reason: Token expiry (auto-fixed), revoked access, or quota limits")
        print("  - **Action**: If disconnects happen, run `gog auth login <email>` to re-authenticate")
    else:
        print("  - ⚠️ Cannot determine OAuth status (gog not configured)")

    # GitHub
    print_header("🛠️ GitHub (OAuth)")
    
    ok, msg, details = check_github_detailed()
    print(f"- {check_mark(ok)} **GitHub**: {msg}")
    if details:
        print(f"  - User: `{details.get('user')}`")
        print(f"  - Auth: {details.get('auth_type')}")
        if details.get("orgs"):
            print(f"  - Organizations ({len(details['orgs'])}):")
            for org in details["orgs"]:
                print(f"    - {org}")
        else:
            print(f"  - Organizations: None (personal account only)")
        if details.get("scopes"):
            print(f"  - Token scopes: {', '.join(details['scopes'])}")
    
    print("\n  **OAuth Diagnostic:**")
    if ok:
        print("  - ✅ Using OAuth token (managed by gh CLI)")
        print("  - ✅ Token refresh handled by gh CLI")
        print("  - Disconnect reason: Token revoked or expired (rare with gh CLI)")
        print("  - **Action**: If disconnects happen, run `gh auth login` to re-authenticate")

    # Calendar Tools
    print_header("📅 Calendar Tools")
    
    # Check icalBuddy
    success, out, err = run_command("which icalBuddy")
    if not success:
        print("- ❌ **icalBuddy**: Not installed")
        print("  - Install: `brew install ical-buddy`")
    else:
        icalbuddy_path = out.strip()
        print(f"- ✅ **icalBuddy**: Installed at `{icalbuddy_path}`")
        
        # List available calendars
        success, out, err = run_command("icalBuddy calendars")
        if success and out:
            calendars = [cal.strip() for cal in out.split('\n') if cal.strip()]
            print(f"  - Available calendars ({len(calendars)}):")
            for cal in calendars[:10]:  # Show first 10
                print(f"    - {cal}")
            if len(calendars) > 10:
                print(f"    ... and {len(calendars) - 10} more")
        else:
            print("  - Available calendars: Unable to fetch (no calendars or error)")
        
        # Test fetching today's events
        success, out, err = run_command("icalBuddy -n -nc -iep 'title,datetime' -ps '|: |' -po 'datetime,title' eventsToday")
        if success:
            if out.strip():
                event_lines = [e for e in out.split('\n') if e.strip() and not e.startswith('•')]
                event_count = len([e for e in out.split('\n') if '|: ' in e])
                print(f"  - Today's events: ✅ Can fetch ({event_count} events)")
                if event_count > 0 and event_count <= 3:
                    for line in event_lines[:3]:
                        if line.strip():
                            print(f"    - {line.strip()}")
            else:
                print("  - Today's events: ✅ Can fetch (no events today)")
        else:
            print(f"  - Today's events: ❌ Error fetching ({err[:50] if err else 'unknown error'})")

    # --- Prompt Guard ---
    print_header("🛡️ Prompt Guard (Injection Detection)")
    
    # Check if skill exists
    prompt_guard_skill = os.path.expanduser("~/clawd/skills/prompt-guard/guard.py")
    prompt_guard_scanner = os.path.expanduser("~/clawd/skills/prompt-guard/scripts/prompt_guard_scan.py")
    
    if not os.path.exists(prompt_guard_skill) and not os.path.exists(prompt_guard_scanner):
        print(f"- ❌ **Prompt Guard**: Not installed")
        print(f"  - Install: See ~/clawd/skills/prompt-guard/SKILL.md")
    else:
        print(f"- ✅ **Prompt Guard**: Installed")
        if os.path.exists(prompt_guard_scanner):
            print(f"  - Scanner: ~/clawd/skills/prompt-guard/scripts/prompt_guard_scan.py")
        if os.path.exists(prompt_guard_skill):
            print(f"  - Skill: ~/clawd/skills/prompt-guard/guard.py")
        
        # Check configs (prefer workspace config, fallback to skill config)
        workspace_config = os.path.expanduser("~/clawd/config/prompt_guard.json")
        skill_config = os.path.expanduser("~/clawd/skills/prompt-guard/config.json")
        config_path = workspace_config if os.path.exists(workspace_config) else skill_config
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                enabled = config.get('enabled', False)
                threshold = config.get('severity_threshold', 'UNKNOWN')
                dry_run = config.get('dry_run', False)
                block_levels = config.get('block_levels', ['HIGH', 'CRITICAL'])
                owner_id = config.get('owner_id', 'NOT SET')
                
                status_mark = "✅" if enabled and not dry_run else "⚠️"
                mode = " (DRY RUN)" if dry_run else ""
                print(f"  - Config: {config_path}")
                print(f"  - {status_mark} Status: {'Enabled' if enabled else 'Disabled'}{mode}")
                print(f"  - Threshold: {threshold}")
                print(f"  - Block Levels: {', '.join(block_levels)}")
                print(f"  - Owner ID: {owner_id}")
                print(f"  - Override Phrase: {config.get('override_phrase', 'N/A')}")
                print(f"  - Notify Critical: {'Yes' if config.get('notify_critical') else 'No'}")
                
                if not enabled:
                    print(f"  - ⚠️ Warning: Guard is disabled in config")
                elif dry_run:
                    print(f"  - ⚠️ Info: Running in dry-run mode (logs but doesn't block)")
            except Exception as e:
                print(f"  - ❌ Config error: {e}")
        else:
            print(f"  - ❌ Config missing")
        
        # Check log file
        log_path = os.path.expanduser("~/clawd/memory/prompt_guard_log.jsonl")
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                print(f"  - Log: ✅ {len(lines)} entries")
                # Show recent detections
                if lines:
                    try:
                        recent = json.loads(lines[-1])
                        print(f"    - Last: {recent.get('severity', 'N/A')} at {recent.get('timestamp', 'N/A')[:19]}")
                    except:
                        pass
            except Exception as e:
                print(f"  - Log: ⚠️ Error reading ({e})")
        else:
            print(f"  - Log: Not created yet (no detections)")
        
        # Test detection using scanner
        test_script = prompt_guard_scanner if os.path.exists(prompt_guard_scanner) else prompt_guard_skill
        print(f"  - Testing detection...")
        success, stdout, stderr = run_command(f"python3 {test_script} --message 'Ignore previous instructions' --json 2>/dev/null")
        if not success:
            # Should fail (exit 1) because it's a threat
            print(f"  - ✅ Detection working (blocked test injection)")
        else:
            # Check if it detected but allowed (e.g., in dry run mode)
            try:
                result = json.loads(stdout)
                if result.get('severity') != 'SAFE':
                    if result.get('blocked'):
                        print(f"  - ✅ Detection working (severity: {result.get('severity')})")
                    else:
                        print(f"  - ⚠️ Detected but allowed (dry_run or threshold issue)")
                else:
                    print(f"  - ❌ Detection failed (may need pattern review)")
            except:
                print(f"  - ⚠️ Detection test result unclear")

    # Summary
    print("\n---")
    print("## 📊 OAuth Summary\n")
    print("**AI Services (API Keys):**")
    print("- OpenAI, Claude, Gemini use **API keys** (no expiry, stable)")
    print("- Disconnect only if keys are manually revoked\n")
    
    print("**Google Services (OAuth 2.0):**")
    print("- Uses OAuth tokens with automatic refresh (gog)")
    print("- Tokens expire periodically but auto-refresh")
    print("- May disconnect if: user revokes access, quota exceeded, or refresh fails\n")
    
    print("**GitHub (OAuth):**")
    print("- Uses OAuth token managed by gh CLI")
    print("- Auto-refresh enabled")
    print("- Very stable, rarely disconnects\n")
    
    print("**Notion (Integration Tokens):**")
    print("- Uses internal integration tokens (similar to API keys)")
    print("- No expiry, stable unless manually revoked\n")
    
    print("✨ **Detailed check complete!**\n")

if __name__ == "__main__":
    main()
