#!/usr/bin/env python3
"""Register/unregister daye-agent-toolkit plugins in CC settings.json."""
import json
import sys
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"


def load():
    return json.loads(SETTINGS.read_text())


def save(data):
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def register(repo_dir: str, plugins: list[str], marketplace_key: str):
    d = load()
    m = d.setdefault("extraKnownMarketplaces", {})
    expected = {"source": {"source": "directory", "path": repo_dir}}
    if m.get(marketplace_key) == expected:
        print(f"  - {marketplace_key} (already registered)")
    else:
        m[marketplace_key] = expected
        print(f"  + {marketplace_key} registered")

    ep = d.setdefault("enabledPlugins", {})
    for plugin in plugins:
        key = f"{plugin}@{marketplace_key}"
        if ep.get(key) is True:
            print(f"  - {plugin} (already enabled)")
        else:
            ep[key] = True
            print(f"  + {plugin} enabled")

    save(d)


def unregister(plugins: list[str], marketplace_key: str):
    d = load()
    ep = d.get("enabledPlugins", {})
    for plugin in plugins:
        key = f"{plugin}@{marketplace_key}"
        if key in ep:
            del ep[key]
            print(f"  - {plugin} disabled")
    save(d)


def status(plugins: list[str], marketplace_key: str):
    d = load()
    m = d.get("extraKnownMarketplaces", {})
    print("=== Marketplace ===")
    if marketplace_key in m:
        print(f"  + {marketplace_key} registered")
    else:
        print(f"  x {marketplace_key} NOT registered")

    print("\n=== Plugins ===")
    ep = d.get("enabledPlugins", {})
    for plugin in plugins:
        key = f"{plugin}@{marketplace_key}"
        if ep.get(key) is True:
            print(f"  + {plugin}")
        else:
            print(f"  x {plugin} (disabled)")


if __name__ == "__main__":
    action = sys.argv[1]
    marketplace_key = sys.argv[2]
    plugins = sys.argv[3].split(",")
    repo_dir = sys.argv[4] if len(sys.argv) > 4 else ""

    if action == "register":
        register(repo_dir, plugins, marketplace_key)
    elif action == "unregister":
        unregister(plugins, marketplace_key)
    elif action == "status":
        status(plugins, marketplace_key)
