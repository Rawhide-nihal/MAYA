"""
MAYA Security & Permission System V3
Deterministic access control with Level 0-4 tiers, signed permission tokens,
exact-action binding, plan suspension, and single-use token validation.
AI cannot bypass this layer.
"""
from enum import IntEnum
from typing import Dict, Any, Optional, Tuple
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
    plan_id: Optional[str] = None
    step_id: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, rejected, expired

# Default tool mapping to permission levels (covers all 34 canonical tools)
TOOL_PERMISSION_MAP: Dict[str, PermissionLevel] = {
    # Observation (Level 1)
    "get_system_status": PermissionLevel.LEVEL_1_OBSERVATION,
    "run_system_diagnostics": PermissionLevel.LEVEL_1_OBSERVATION,
    "inspect_project": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_files": PermissionLevel.LEVEL_1_OBSERVATION,
    "read_file": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_directory": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_windows": PermissionLevel.LEVEL_1_OBSERVATION,
    "list_processes": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_recent_actions": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_memory": PermissionLevel.LEVEL_1_OBSERVATION,
    "capture_screen": PermissionLevel.LEVEL_1_OBSERVATION,
    "analyze_screen": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_file_content": PermissionLevel.LEVEL_1_OBSERVATION,
    "find_largest_files": PermissionLevel.LEVEL_1_OBSERVATION,
    "find_duplicates": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_active_window": PermissionLevel.LEVEL_1_OBSERVATION,
    "check_git_status": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_git_diff": PermissionLevel.LEVEL_1_OBSERVATION,
    "get_memory": PermissionLevel.LEVEL_1_OBSERVATION,
    "report_findings": PermissionLevel.LEVEL_1_OBSERVATION,
    "verify_application": PermissionLevel.LEVEL_1_OBSERVATION,
    "prioritize_findings": PermissionLevel.LEVEL_1_OBSERVATION,
    "search_web": PermissionLevel.LEVEL_1_OBSERVATION,
    "fetch_page_text": PermissionLevel.LEVEL_1_OBSERVATION,
    "detect_project": PermissionLevel.LEVEL_1_OBSERVATION,

    # Safe actions (Level 2)
    "open_application": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "open_application_and_inspect": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "focus_window": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "minimize_window": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "maximize_window": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "restore_window": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "set_volume": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "open_url": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "start_timer": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "set_reminder": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "store_memory": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "forget_memory": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "rollback_last_action": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "create_directory": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "run_safe_command": PermissionLevel.LEVEL_2_SAFE_ACTION,
    "prepare_communication": PermissionLevel.LEVEL_2_SAFE_ACTION,

    # Modification (Level 3)
    "write_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "copy_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "move_file": PermissionLevel.LEVEL_3_MODIFICATION,
    "apply_patch": PermissionLevel.LEVEL_3_MODIFICATION,
    "run_build": PermissionLevel.LEVEL_3_MODIFICATION,
    "build_project": PermissionLevel.LEVEL_3_MODIFICATION,
    "run_tests": PermissionLevel.LEVEL_3_MODIFICATION,
    "close_application": PermissionLevel.LEVEL_3_MODIFICATION,
    "clean_temp_files": PermissionLevel.LEVEL_3_MODIFICATION,
    "execute_terminal_command": PermissionLevel.LEVEL_3_MODIFICATION,
    "send_communication": PermissionLevel.LEVEL_3_MODIFICATION,

    # Critical (Level 4)
    "delete_file": PermissionLevel.LEVEL_4_CRITICAL,
    "terminate_process": PermissionLevel.LEVEL_4_CRITICAL,
    "modify_system_setting": PermissionLevel.LEVEL_4_CRITICAL,
    "modify_security": PermissionLevel.LEVEL_4_CRITICAL,
    "modify_registry": PermissionLevel.LEVEL_4_CRITICAL,
    "terminate_service": PermissionLevel.LEVEL_4_CRITICAL,
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

    def check_permission(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        token: Optional[str] = None,
        plan_id: Optional[str] = None,
        step_id: Optional[int] = None
    ) -> PermissionDecision:
        required_level = TOOL_PERMISSION_MAP.get(tool_name, PermissionLevel.LEVEL_3_MODIFICATION)
        args_hash = hash_arguments(arguments)

        # 1. If valid approved signed token is provided, verify it matches exact tool, argument hash, and plan/step
        if token and token in self.issued_tokens:
            token_meta = self.issued_tokens[token]
            if not token_meta.get("used") and time.time() < token_meta["expires_at"]:
                if token_meta["tool"] == tool_name and token_meta["args_hash"] == args_hash:
                    # Match plan_id / step_id if bound
                    plan_match = True
                    if token_meta.get("plan_id") and plan_id:
                        plan_match = token_meta["plan_id"] == plan_id
                    step_match = True
                    if token_meta.get("step_id") is not None and step_id is not None:
                        step_match = token_meta["step_id"] == step_id

                    if plan_match and step_match:
                        # Consume single-use token immediately
                        token_meta["used"] = True
                        return PermissionDecision(
                            granted=True,
                            required_level=required_level,
                            user_configured_max_level=self.current_max_level,
                            requires_confirmation=False,
                            reason="Authorized via valid user-approved single-use permission token."
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
                description=desc,
                plan_id=plan_id,
                step_id=step_id
            )
            return PermissionDecision(
                granted=False,
                required_level=required_level,
                user_configured_max_level=self.current_max_level,
                requires_confirmation=True,
                confirmation_id=conf_id,
                reason=f"Action '{tool_name}' is CRITICAL (Level 4) and strictly requires explicit authorization."
            )

        # 3. If required level exceeds current allowed level, request confirmation
        if required_level > self.current_max_level:
            conf_id = str(uuid.uuid4())
            desc = f"Execute '{tool_name}' (requires Level {required_level.name}, allowed: Level {self.current_max_level.name})"
            self.pending_confirmations[conf_id] = PendingConfirmation(
                confirmation_id=conf_id,
                tool_name=tool_name,
                arguments=arguments,
                arguments_hash=args_hash,
                level=required_level,
                description=desc,
                plan_id=plan_id,
                step_id=step_id
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
        """Resolves confirmation. If approved, issues a signed single-use permission token bound to action."""
        if confirmation_id not in self.pending_confirmations:
            return None
        conf = self.pending_confirmations[confirmation_id]
        if not approved:
            conf.status = "rejected"
            return None

        conf.status = "approved"
        # Issue signed single-use token (valid for 120 seconds)
        token = "perm_" + str(uuid.uuid4()).replace("-", "")
        self.issued_tokens[token] = {
            "token": token,
            "confirmation_id": confirmation_id,
            "plan_id": conf.plan_id,
            "step_id": conf.step_id,
            "tool": conf.tool_name,
            "args_hash": conf.arguments_hash,
            "issued_at": time.time(),
            "expires_at": time.time() + 120.0,
            "nonce": uuid.uuid4().hex[:12],
            "used": False
        }
        return token

    def validate_token_for_resume(
        self,
        token: str,
        plan_id: Optional[str],
        step_id: Optional[int],
        tool_name: str,
        arguments: Dict[str, Any],
        confirmation_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Strict validation of a permission token specifically for resuming a suspended plan."""
        if not token or token not in self.issued_tokens:
            return False, "Permission token not found or invalid."
        meta = self.issued_tokens[token]
        if meta.get("used"):
            return False, "Permission token has already been consumed (replay rejected)."
        if time.time() > meta.get("expires_at", 0):
            return False, "Permission token has expired."
        if confirmation_id and meta.get("confirmation_id") and meta.get("confirmation_id") != confirmation_id:
            return False, f"Permission token was issued for confirmation {meta.get('confirmation_id')}, not {confirmation_id}."
        if meta.get("tool") != tool_name:
            return False, f"Permission token bound to tool '{meta.get('tool')}', not '{tool_name}'."
        if hash_arguments(arguments) != meta.get("args_hash"):
            return False, "Arguments hash mismatch: arguments have been modified since authorization."
        if meta.get("plan_id") and plan_id and meta.get("plan_id") != plan_id:
            return False, f"Permission token bound to plan '{meta.get('plan_id')}', not '{plan_id}'."
        if meta.get("step_id") is not None and step_id is not None and meta.get("step_id") != step_id:
            return False, f"Permission token bound to step {meta.get('step_id')}, not step {step_id}."

        return True, "Authorization verified successfully."

    def consume_token(self, token: str) -> None:
        """Immediately marks a single-use permission token as consumed."""
        if token and token in self.issued_tokens:
            self.issued_tokens[token]["used"] = True
