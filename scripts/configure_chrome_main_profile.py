"""One-time local setup for MAYA's primary Chrome profile.

This script reads Chrome's local profile metadata on this PC and stores only the
selected profile directory in %LOCALAPPDATA%/Maya/settings.json. No account
identifier is committed to GitHub.
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.windows.agent import WindowsAgent
from maya_core.config import settings


def main() -> int:
    windows = WindowsAgent()
    state = windows._load_chrome_profile_state()
    profile_state = state.get("profile", {}) if isinstance(state, dict) else {}
    info_cache = profile_state.get("info_cache", {}) if isinstance(profile_state, dict) else {}

    if not isinstance(info_cache, dict) or not info_cache:
        print("No Chrome profiles were found in the current Windows user account.")
        print("Open Chrome once, sign in, then run this setup again.")
        return 1

    profiles = []
    print("\nChrome profiles detected on this PC:\n")
    for index, (directory, meta) in enumerate(info_cache.items(), start=1):
        meta = meta if isinstance(meta, dict) else {}
        name = str(meta.get("name") or directory)
        user_name = str(meta.get("user_name") or "")
        label = f"{index}. {name}  [{directory}]"
        if user_name:
            label += f"  - {user_name}"
        print(label)
        profiles.append((directory, name))

    print()
    try:
        raw = input("Choose the profile MAYA should treat as 'main' (number): ").strip()
        choice = int(raw)
    except (ValueError, EOFError, KeyboardInterrupt):
        print("\nNo profile selected.")
        return 1

    if choice < 1 or choice > len(profiles):
        print("Invalid profile number.")
        return 1

    directory, name = profiles[choice - 1]
    settings.set("chrome_main_profile", directory)
    settings.set("chrome_main_account", "")

    resolved = windows.resolve_chrome_profile("main")
    if not resolved.get("success"):
        print(f"Could not verify selected profile: {resolved.get('error')}")
        return 1

    print(f"\nMAYA main Chrome profile set to: {name} [{directory}]")
    print("This preference is stored locally under %LOCALAPPDATA%\\Maya\\settings.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
