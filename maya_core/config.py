"""
MAYA System Configuration & Portable Path Resolution
Provides dynamic path resolution, settings management, and local API authentication.
Zero hard-coded paths.
"""
import os
import sys
import json
import secrets
from pathlib import Path
from typing import Dict, Any

# Dynamic Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Windows Local AppData Storage (%LOCALAPPDATA%/Maya)
if sys.platform == "win32":
    APP_DATA_BASE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
else:
    APP_DATA_BASE = Path.home() / ".local" / "share"

MAYA_DATA_DIR = APP_DATA_BASE / "Maya"
MAYA_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Subdirectories in user data
DB_DIR = MAYA_DATA_DIR / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = MAYA_DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = MAYA_DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = MAYA_DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SCREENSHOTS_DIR = MAYA_DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = MAYA_DATA_DIR / "settings.json"
AUTH_TOKEN_FILE = MAYA_DATA_DIR / "auth.token"

# Database paths
AUDIT_DB_PATH = DB_DIR / "maya_audit.db"
MEMORY_DB_PATH = DB_DIR / "maya_memory.db"

# Default system settings
DEFAULT_SETTINGS: Dict[str, Any] = {
    "permission_level": 2,           # LEVEL_2_SAFE_ACTION
    "offline_only": True,
    "model_name": "maya-v1",
    "base_model": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "quantization": "Q4",
    "context_window": 8192,
    "voice_enabled": True,
    "wake_word_enabled": True,
    "proactive_mode": "Normal",      # Quiet, Normal, Proactive
    "telemetry_enabled": False,
    "theme": "dark-midnight",
    "chrome_main_account": "",       # Local-only email/profile hint for the user's primary Chrome profile
    "chrome_main_profile": ""        # Optional local Chrome profile directory/name override
}

def get_or_create_auth_token() -> str:
    """Generate or retrieve a cryptographically secure session token for local API calls."""
    if AUTH_TOKEN_FILE.exists():
        try:
            token = AUTH_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if len(token) >= 32:
                return token
        except Exception:
            pass
    token = secrets.token_hex(32)
    try:
        AUTH_TOKEN_FILE.write_text(token, encoding="utf-8")
    except Exception:
        pass
    return token

class SettingsManager:
    """Manages persistent application settings."""
    def __init__(self, filepath: Path = SETTINGS_FILE):
        self.filepath = filepath
        self._settings = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with defaults
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return dict(DEFAULT_SETTINGS)

    def save(self) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"[SettingsManager] Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()

    def all(self) -> Dict[str, Any]:
        return dict(self._settings)

# Global settings instance
settings = SettingsManager()
AUTH_TOKEN = get_or_create_auth_token()
