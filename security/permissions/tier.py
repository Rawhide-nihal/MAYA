"""
MAYA Security & Permission System V2
Deterministic access control with Level 0-4 tiers, signed permission tokens, and strict confirmation.
AI cannot bypass this layer.
"""
from enum import IntEnum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import uuid
import time
import hashlib
import json

class PermissionLevel(IntEnum):
    LEVEL_0_CONVERSATION = 0  # Pure chat, no PC access
    LEVEL_1_OBSERVATION = 1   # Read system metrics, logs, search files, read file content
    LEVEL_2_SAFE_ACTION = 2   # Launch known apps, harmless directory creation, harmless build diagnostics
    LEVEL_3_MODIFICATION = 3  # File edits, moving data, stopping processes, package install, patches
    LEVEL_4_CRITICAL = 4      # Permanent deletion, registry changes, security changes, formatting

@dataclass
class PermissionDecision:
    granted: bool
    required_level: PermissionLevel
    user_configured_max_level: PermissionLevel
    requires_confirmation: bool
    confirmation_id: Optional[str] = None
    permission_token: Optional[str] = None
    reason: str = ""

@dataclass
class PendingConfirmation:
    confirmation_id: str
    tool_name: str
    arguments: Dict[str, Any]
    arguments_hash: str
    level: PermissionLevel
    description: str
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, rejected, expired

# Default tool mapping to permission levels
TOOL_PERMISSION_MAP: Dict[str, PermissionLevel] = {
    # Observation (Level 1)
    "get_system_status": PermissionLevel.LEVEL_1_OBSERVATION,
    "run_system_diagnostics": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_files": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_file_content": PermissionLevel.LEVEL_1_OBSERVATION,
    "find_largest_files": PermissionLevel.LEVEL_1_OBSERVATION,
    "find_duplicates": PermissionLevel.LEVEL_1_OBSERVATION,
    "read_file": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_directory": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_processes": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_active_window": PermissionLevel.LEVEL_1_OBSERVATION,
    "capture_screen": PermissionLevel.LEVEL_1_OBSERVATION,
    "analyze_screen": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_recent_actions": PermissionLevel.LEVEL_1_OBSERVATION,
    "inspect_project": PermissionLevel.LEVEL_1_OBSERVATION,
    "check_git_status": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_memory": PermissionLevel.LEVEL_1_OBSERVATION,
    "report_findings": PermissionLevel.LEVEL_1_OBSERVATION,
    "verify_application": PermissionLevel.LEVEL_1_OBSERVATION,
    "prioritize_findings": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_web": PermissionLevel.LEVEL_1_OBSERVATION,
    "fetch_page_text": PermissionLevel.LEVEL_1_OBSERVATION,

    # Safe actions (Level 2)
    "open_application": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "open_url": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "focus_window": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "create_directory": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "run_safe_command": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "build_project": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "run_tests": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "store_memory": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "rollback_last_action": PermissionLevel.LEVEL_2_SAFE_ACTION,

    # Modification (Level 3)
    "write_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "move_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "apply_patch": PermissionLevel.LEVEL_3_MODIFICATION,
    "copy_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "terminate_process": PermissionLevel.LEVEL_3_MODIFICATION,
    "clean_temp_files": PermissionLevel.LEVEL_3_MODIFICATION,
    "execute_terminal_command": PermissionLevel.LEVEL_3_MODIFICATION,

    # Critical (Level 4)
    "delete_file": PermissionLevel.LEVEL_4_CRITICAL,
    "modify_system_setting": PermissionLevel.LEVEL_4_CRITICAL,
    "execute_privileged_script": PermissionLevel.LEVEL_4_CRITICAL,
}

def hash_arguments(args: Dict[str, Any]) -> str:
    """Generates deterministic SHA-256 hash of arguments to prevent argument tampering."""
    serialized = json.dumps(args, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

class PermissionManager:
    def __init__(self, default_allowed_level: PermissionLevel = PermissionLevel.LEVEL_2_SAFE_ACTION):
        self.current_max_level = default_allowed_level
        self.pending_confirmations: Dict[str, PendingConfirmation] = {}
        self.issued_tokens: Dict[str, Dict[str, Any]] = {}

    def set_max_level(self, level: PermissionLevel) -> None:
        self.current_max_level = level

    def check_permission(self, tool_name: str, arguments: Dict[str, Any], token: Optional[str] = None) -> PermissionDecision:
        required_level = TOOL_PERMISSION_MAP.get(tool_name, PermissionLevel.LEVEL_3_MODIFICATION)
        args_hash = hash_arguments(arguments)

        # 1. If valid approved signed token is provided, verify it matches exact tool and argument hash
        if token and token in self.issued_tokens:
            token_meta = self.issued_tokens[token]
            if token_meta["tool"] == tool_name and token_meta["args_hash"] == args_hash:
                if time.time() < token_meta["expires_at"]:
                    # Valid token: consume token and grant
                    del self.issued_tokens[token]
                    return PermissionDecision(
                        granted=True,
                        required_level=required_level,
                        user_configured_max_level=self.current_max_level,
                        requires_confirmation=False,
                        reason="Authorized via valid user-approved permission token."
                    )

        # 2. Level 4 ALWAYS requires explicit user confirmation
        if required_level >= PermissionLevel.LEVEL_4_CRITICAL:
            conf_id = str(uuid.uuid4())
            desc = f"Execute critical tool '{tool_name}' with arguments {arguments}"
            self.pending_confirmations[conf_id] = PendingConfirmation(
                confirmation_id=conf_id,
                tool_name=tool_name,
                arguments=arguments,
                arguments_hash=args_hash,
                level=required_level,
                description=desc
            )
            return PermissionDecision(
                granted=False,
                required_level=required_level,
                user_configured_max_level=self.current_max_level,
                requires_confirmation=True,
                confirmation_id=conf_id,
                reason=f"Action '{tool_name}' is CRITICAL (Level 4) and strictly requires confirmation."
            )

        # 3. If required level exceeds current allowed level, request confirmation
        if required_level > self.current_max_level:
            conf_id = str(uuid.uuid4())
            desc = f"Execute '{tool_name}' (requires Level {required_level.name}, currently allowed: Level {self.current_max_level.name})"
            self.pending_confirmations[conf_id] = PendingConfirmation(
                confirmation_id=conf_id,
                tool_name=tool_name,
                arguments=arguments,
                arguments_hash=args_hash,
                level=required_level,
                description=desc
            )
            return PermissionDecision(
                granted=False,
                required_level=required_level,
                user_configured_max_level=self.current_max_level,
                requires_confirmation=True,
                confirmation_id=conf_id,
                reason=f"Action '{tool_name}' exceeds current permission level {self.current_max_level.name}. Requires user approval."
            )

        return PermissionDecision(
            granted=True,
            required_level=required_level,
            user_configured_max_level=self.current_max_level,
            requires_confirmation=False,
            reason="Granted under current permission policy."
        )

    def resolve_confirmation(self, confirmation_id: str, approved: bool) -> Optional[str]:
        """Resolves confirmation. If approved, issues a signed single-use permission token."""
        if confirmation_id not in self.pending_confirmations:
            return None
        conf = self.pending_confirmations[confirmation_id]
        if not approved:
            conf.status = "rejected"
            return None

        conf.status = "approved"
        # Issue signed single-use token (valid for 60 seconds)
        token = "perm_" + str(uuid.uuid4()).replace("-", "")
        self.issued_tokens[token] = {
            "tool": conf.tool_name,
            "args_hash": conf.arguments_hash,
            "expires_at": time.time() + 60.0
        }
        return token
