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
    """Check Notion API with detailed permissions"""
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
            "Notion-Version": "2022-06-28"
        }
        
        details = {
            "databases": [],
            "pages": [],
            "users": 0
        }
        
        # Check users
        try:
            req = urllib.request.Request("https://api.notion.com/v1/users", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read())
                details["users"] = len(data.get("results", []))
        except:
            pass
        
        # Search for databases
        try:
            req = urllib.request.Request(
                "https://api.notion.com/v1/search",
                headers=headers,
                data=json.dumps({
                    "filter": {"property": "object", "value": "database"},
                    "page_size": 10
                }).encode()
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read())
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
            details["databases"] = [f"Error: {str(e)[:30]}"]
        
        # Search for pages
        try:
            req = urllib.request.Request(
                "https://api.notion.com/v1/search",
                headers=headers,
                data=json.dumps({
                    "filter": {"property": "object", "value": "page"},
                    "page_size": 10
                }).encode()
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read())
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
            details["pages"] = [f"Error: {str(e)[:30]}"]
        
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
