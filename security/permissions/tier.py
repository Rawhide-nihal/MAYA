"""
MAYA Security & Permission System
Enforces deterministic access control for all tool calls.
AI cannot bypass this layer.
"""
from enum import IntEnum
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import uuid
import time

class PermissionLevel(IntEnum):
    LEVEL_0_CONVERSATION = 0  # Pure chat, no PC access
    LEVEL_1_OBSERVATION = 1   # Read system metrics, logs, search files, read file content
    LEVEL_2_SAFE_ACTION = 2   # Launch known apps, harmless directory creation, harmless build
    LEVEL_3_MODIFICATION = 3  # File edits, moving data, stopping processes, package install
    LEVEL_4_CRITICAL = 4      # Permanent deletion, registry changes, security changes, format

@dataclass
class PermissionDecision:
    granted: bool
    required_level: PermissionLevel
    user_configured_max_level: PermissionLevel
    requires_confirmation: bool
    confirmation_id: Optional[str] = None
    reason: str = ""

@dataclass
class PendingConfirmation:
    confirmation_id: str
    tool_name: str
    arguments: Dict[str, Any]
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
    "read_file": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_directory": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_processes": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_active_window": PermissionLevel.LEVEL_1_OBSERVATION,
    "capture_screen": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_recent_actions": PermissionLevel.LEVEL_1_OBSERVATION,
    "inspect_project": PermissionLevel.LEVEL_1_OBSERVATION,
    "check_git_status": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_memory": PermissionLevel.LEVEL_1_OBSERVATION,
    "report_findings": PermissionLevel.LEVEL_1_OBSERVATION,
    "verify_application": PermissionLevel.LEVEL_1_OBSERVATION,
    "prioritize_findings": PermissionLevel.LEVEL_1_OBSERVATION,

    # Safe actions (Level 2)
    "open_application": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "open_file_in_editor": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "create_directory": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "run_safe_command": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "build_project": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "run_tests": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "store_memory": PermissionLevel.LEVEL_2_SAFE_ACTION,

    # Modification (Level 3)
    "write_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "move_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "copy_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "kill_process": PermissionLevel.LEVEL_3_MODIFICATION,
    "clean_temp_files": PermissionLevel.LEVEL_3_MODIFICATION,
    "execute_terminal_command": PermissionLevel.LEVEL_3_MODIFICATION,
    "install_dependency": PermissionLevel.LEVEL_3_MODIFICATION,

    # Critical (Level 4)
    "delete_file": PermissionLevel.LEVEL_4_CRITICAL,
    "modify_system_setting": PermissionLevel.LEVEL_4_CRITICAL,
    "execute_privileged_script": PermissionLevel.LEVEL_4_CRITICAL,
}

class PermissionManager:
    def __init__(self, default_allowed_level: PermissionLevel = PermissionLevel.LEVEL_2_SAFE_ACTION):
        self.current_max_level = default_allowed_level
        self.pending_confirmations: Dict[str, PendingConfirmation] = {}

    def set_max_level(self, level: PermissionLevel) -> None:
        self.current_max_level = level

    def check_permission(self, tool_name: str, arguments: Dict[str, Any]) -> PermissionDecision:
        required_level = TOOL_PERMISSION_MAP.get(tool_name, PermissionLevel.LEVEL_3_MODIFICATION)

        # Level 4 ALWAYS requires explicit user confirmation
        if required_level >= PermissionLevel.LEVEL_4_CRITICAL:
            conf_id = str(uuid.uuid4())
            desc = f"Execute critical tool '{tool_name}' with arguments {arguments}"
            self.pending_confirmations[conf_id] = PendingConfirmation(
                confirmation_id=conf_id,
                tool_name=tool_name,
                arguments=arguments,
                level=required_level,
                description=desc
            )
            return PermissionDecision(
                granted=False,
                required_level=required_level,
                user_configured_max_level=self.current_max_level,
                requires_confirmation=True,
                confirmation_id=conf_id,
                reason=f"Action '{tool_name}' is CRITICAL (Level 4) and requires explicit confirmation."
            )

        # If required level exceeds current allowed level, request confirmation
        if required_level > self.current_max_level:
            conf_id = str(uuid.uuid4())
            desc = f"Execute '{tool_name}' (requires Level {required_level.name}, currently allowed: Level {self.current_max_level.name})"
            self.pending_confirmations[conf_id] = PendingConfirmation(
                confirmation_id=conf_id,
                tool_name=tool_name,
                arguments=arguments,
                level=required_level,
                description=desc
            )
            return PermissionDecision(
                granted=False,
                required_level=required_level,
                user_configured_max_level=self.current_max_level,
                requires_confirmation=True,
                confirmation_id=conf_id,
                reason=f"Action '{tool_name}' exceeds current permission level {self.current_max_level.name}. Requires confirmation."
            )

        return PermissionDecision(
            granted=True,
            required_level=required_level,
            user_configured_max_level=self.current_max_level,
            requires_confirmation=False,
            reason="Granted under current permission policy."
        )

    def resolve_confirmation(self, confirmation_id: str, approved: bool) -> Optional[PendingConfirmation]:
        if confirmation_id not in self.pending_confirmations:
            return None
        conf = self.pending_confirmations[confirmation_id]
        conf.status = "approved" if approved else "rejected"
        return conf
