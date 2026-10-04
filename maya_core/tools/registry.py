"""
MAYA Central Tool Schema & Registration System
Defines explicit tool schemas, parameter validations, permission levels,
execution handlers, verification handlers, and neural prompt schemas.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
import inspect

from security.permissions.tier import PermissionLevel

@dataclass
class ToolParameter:
    name: str
    type_name: str  # "string", "integer", "boolean", "dict", "list", "number"
    description: str
    required: bool = True
    default: Any = None

@dataclass
class ToolSchema:
    name: str
    description: str
    category: str
    parameters: List[ToolParameter]
    permission_level: PermissionLevel
    execution_handler: Optional[Callable] = None
    verification_handler: Optional[Callable] = None
    undo_available: bool = False

    def validate_arguments(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Strict validation of passed arguments against defined parameter schema."""
        if not isinstance(args, dict):
            return False, f"Arguments for tool '{self.name}' must be a dictionary/object."

        # Check required arguments
        for param in self.parameters:
            if param.required and param.name not in args:
                return False, f"Missing required parameter '{param.name}' for tool '{self.name}'."

            if param.name in args:
                val = args[param.name]
                if val is not None:
                    if param.type_name == "string" and not isinstance(val, str):
                        return False, f"Parameter '{param.name}' must be a string."
                    elif param.type_name == "integer" and not isinstance(val, int):
                        return False, f"Parameter '{param.name}' must be an integer."
                    elif param.type_name == "number" and not isinstance(val, (int, float)):
                        return False, f"Parameter '{param.name}' must be a number."
                    elif param.type_name == "boolean" and not isinstance(val, bool):
                        return False, f"Parameter '{param.name}' must be a boolean."
                    elif param.type_name == "dict" and not isinstance(val, dict):
                        return False, f"Parameter '{param.name}' must be a dictionary."
                    elif param.type_name == "list" and not isinstance(val, list):
                        return False, f"Parameter '{param.name}' must be a list."

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes tool schema into prompt-friendly dictionary representation."""
        params_dict = {}
        for p in self.parameters:
            params_dict[p.name] = {
                "type": p.type_name,
                "description": p.description,
                "required": p.required
            }
            if p.default is not None:
                params_dict[p.name]["default"] = p.default

        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": params_dict,
            "permission_level": self.permission_level.value,
            "undo_available": self.undo_available
        }

class ToolRegistry:
    """Central registry of all executable tools available to MAYA."""
    def __init__(self):
        self._tools: Dict[str, ToolSchema] = {}

    def register(self, tool: ToolSchema) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolSchema]:
        return self._tools.get(name)

    def exists(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> List[ToolSchema]:
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_prompt_schemas(self) -> List[Dict[str, Any]]:
        """Returns structured schemas for neural prompt context."""
        return [t.to_dict() for t in self._tools.values()]

    def validate_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates that a tool exists and all required parameters are provided."""
        tool = self.get(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' does not exist in registry."
        for p in tool.parameters:
            if p.required and p.name not in arguments:
                return False, f"Missing required parameter: '{p.name}'"
        return True, None

# Global default tool registry instance
tool_registry = ToolRegistry()

def build_default_tool_registry() -> ToolRegistry:
    """Populates registry with the complete canonical suite of MAYA tools."""
    registry = ToolRegistry()

    # 1. System Observation (Level 1)
    registry.register(ToolSchema(
        name="get_system_status",
        description="Reads real-time hardware telemetry: CPU, RAM, GPU, storage, and active tasks.",
        category="system",
        parameters=[],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="run_system_diagnostics",
        description="Runs system health diagnostics across hardware metrics, storage, and developer toolchains.",
        category="diagnostics",
        parameters=[
            ToolParameter("depth", "string", "Scan depth: 'quick' or 'full'", required=False, default="quick")
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="inspect_project",
        description="Inspects active development workspace, build configurations, and checks for syntax/compiler errors.",
        category="developer",
        parameters=[
            ToolParameter("target", "string", "Project path or 'active_project'", required=False, default="active_project")
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="search_files",
        description="Searches directory tree for files matching pattern, extension, or modification date.",
        category="filesystem",
        parameters=[
            ToolParameter("query", "string", "Filename or pattern to search for", required=True),
            ToolParameter("directory", "string", "Base directory to start search in", required=False),
            ToolParameter("extension", "string", "Optional extension filter (e.g. '.pdf', '.py')", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="read_file",
        description="Reads plain text content of a local file safely.",
        category="filesystem",
        parameters=[
            ToolParameter("filepath", "string", "Absolute or relative path to file", required=True),
            ToolParameter("max_lines", "integer", "Maximum lines to read", required=False, default=200)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="list_directory",
        description="Lists contents of a directory with file sizes and modification timestamps.",
        category="filesystem",
        parameters=[
            ToolParameter("path", "string", "Directory path to list", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="list_windows",
        description="Lists all visible desktop application windows with their titles and bounds.",
        category="windows",
        parameters=[],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="list_processes",
        description="Lists running processes filtered by name or sorted by memory/CPU usage.",
        category="windows",
        parameters=[
            ToolParameter("filter", "string", "Process name filter", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="get_recent_actions",
        description="Retrieves audit log of recent actions from the Action Ledger.",
        category="security",
        parameters=[
            ToolParameter("limit", "integer", "Number of recent actions to fetch", required=False, default=15)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="search_memory",
        description="Searches long-term semantic and episodic memory for relevant facts or preferences.",
        category="memory",
        parameters=[
            ToolParameter("query", "string", "Search query keyword or question", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    # 2. Safe Actions (Level 2)
    registry.register(ToolSchema(
        name="open_application",
        description="Launches or focuses an authorized application executable and verifies its process launch.",
        category="windows",
        parameters=[
            ToolParameter("application", "string", "Application name (e.g. 'Visual Studio Code', 'Notepad')", required=True),
            ToolParameter("path", "string", "Optional target file or workspace directory to open", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="open_application_and_inspect",
        description="Opens developer environment and automatically performs background workspace error analysis.",
        category="developer",
        parameters=[
            ToolParameter("application", "string", "Application to open", required=True),
            ToolParameter("project_path", "string", "Project directory path", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="focus_window",
        description="Brings a specific window to the foreground by title.",
        category="windows",
        parameters=[
            ToolParameter("title", "string", "Window title substring", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="minimize_window",
        description="Minimizes active or specified application window.",
        category="windows",
        parameters=[
            ToolParameter("title", "string", "Window title substring (or empty for active)", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="maximize_window",
        description="Maximizes active or specified application window.",
        category="windows",
        parameters=[
            ToolParameter("title", "string", "Window title substring (or empty for active)", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="restore_window",
        description="Restores a minimized or maximized window to normal size.",
        category="windows",
        parameters=[
            ToolParameter("title", "string", "Window title substring", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="set_volume",
        description="Adjusts master system audio volume (0 to 100) or mutes audio.",
        category="windows",
        parameters=[
            ToolParameter("level", "integer", "Volume percentage (0-100)", required=False),
            ToolParameter("mute", "boolean", "Toggle mute status", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="capture_screen",
        description="Captures primary screen display subject to user privacy policy.",
        category="vision",
        parameters=[],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="analyze_screen",
        description="Performs visual and UI automation analysis on current desktop state.",
        category="vision",
        parameters=[],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="open_url",
        description="Opens a URL in the user's default web browser.",
        category="browser",
        parameters=[
            ToolParameter("url", "string", "Web URL starting with http:// or https://", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="search_web",
        description="Performs web search for user queries.",
        category="browser",
        parameters=[
            ToolParameter("query", "string", "Search query", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="start_timer",
        description="Starts a desktop countdown timer for the specified seconds with notification.",
        category="assistant",
        parameters=[
            ToolParameter("duration_seconds", "integer", "Countdown duration in seconds", required=True),
            ToolParameter("label", "string", "Timer description", required=False, default="Timer")
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="set_reminder",
        description="Schedules a desktop notification reminder for a future time.",
        category="assistant",
        parameters=[
            ToolParameter("message", "string", "Reminder message content", required=True),
            ToolParameter("time_expression", "string", "Time description (e.g. 'in 10 minutes', '3pm')", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="store_memory",
        description="Stores verified user preference, project information, or persistent memory.",
        category="memory",
        parameters=[
            ToolParameter("category", "string", "Memory category: preference, project, personal, fact", required=True),
            ToolParameter("key", "string", "Unique key identifier", required=True),
            ToolParameter("value", "string", "Memory value string", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=True
    ))

    registry.register(ToolSchema(
        name="rollback_last_action",
        description="Reverts the most recent reversible action recorded in the Action Ledger.",
        category="security",
        parameters=[],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    # 3. Modification Actions (Level 3)
    registry.register(ToolSchema(
        name="write_file",
        description="Creates or modifies content in a local file with backup snapshot for undo.",
        category="filesystem",
        parameters=[
            ToolParameter("filepath", "string", "Path of file to write", required=True),
            ToolParameter("content", "string", "Text content to write", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=True
    ))

    registry.register(ToolSchema(
        name="copy_file",
        description="Copies a file or directory to a target location.",
        category="filesystem",
        parameters=[
            ToolParameter("source", "string", "Source file path", required=True),
            ToolParameter("destination", "string", "Destination file path", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=True
    ))

    registry.register(ToolSchema(
        name="move_file",
        description="Moves or renames a file or directory.",
        category="filesystem",
        parameters=[
            ToolParameter("source", "string", "Source file path", required=True),
            ToolParameter("destination", "string", "Destination file path", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=True
    ))

    registry.register(ToolSchema(
        name="apply_patch",
        description="Applies unified diff patch to workspace code files with atomic rollback.",
        category="developer",
        parameters=[
            ToolParameter("filepath", "string", "Target source file path", required=True),
            ToolParameter("diff", "string", "Unified diff or replacement content", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=True
    ))

    registry.register(ToolSchema(
        name="run_build",
        description="Executes project build toolchain (npm build, cargo build, mvn compile, etc.).",
        category="developer",
        parameters=[
            ToolParameter("project_path", "string", "Project path", required=False),
            ToolParameter("command", "string", "Build command override", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="run_tests",
        description="Runs test suite in project workspace and parses pass/fail results.",
        category="developer",
        parameters=[
            ToolParameter("project_path", "string", "Project path", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="close_application",
        description="Gracefully closes an open application window.",
        category="windows",
        parameters=[
            ToolParameter("application", "string", "Application name to close", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=False
    ))

    # 4. Critical Actions (Level 4) - ALWAYS requires explicit single-use user authorization
    registry.register(ToolSchema(
        name="delete_file",
        description="Deletes a file (prefers Recycle Bin; permanent deletion requires critical authorization).",
        category="filesystem",
        parameters=[
            ToolParameter("filepath", "string", "File path to delete", required=True),
            ToolParameter("permanent", "boolean", "Permanent delete without Recycle Bin", required=False, default=False)
        ],
        permission_level=PermissionLevel.LEVEL_4_CRITICAL,
        undo_available=True
    ))

    registry.register(ToolSchema(
        name="terminate_process",
        description="Forcefully terminates a running process by PID or executable name.",
        category="windows",
        parameters=[
            ToolParameter("pid", "integer", "Process ID to terminate", required=False),
            ToolParameter("process_name", "string", "Executable name to kill", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_4_CRITICAL,
        undo_available=False
    ))

    return registry

default_tool_registry = build_default_tool_registry()
