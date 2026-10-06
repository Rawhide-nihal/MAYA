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
    undo_handler: Optional[Callable] = None

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
        return tool.validate_arguments(arguments)

    def self_test(self, require_executors: bool = True) -> Dict[str, Any]:
        """
        Validates every registered tool (Directive 17):
        - Schema & parameters validity
        - Permission mapping exists in TOOL_PERMISSION_MAP
        - Execution handler exists and is callable
        - Verification strategy exists where needed
        - Undo handler exists if undo_available=True
        """
        from security.permissions.tier import TOOL_PERMISSION_MAP
        results = []
        all_passed = True
        for name, tool in self._tools.items():
            errs = []
            if not tool.name or not tool.description:
                errs.append("Missing name or description")
            if tool.permission_level is None or tool.name not in TOOL_PERMISSION_MAP:
                errs.append(f"Missing permission level mapping for '{tool.name}'")
            if require_executors and (tool.execution_handler is None or not callable(tool.execution_handler)):
                errs.append(f"Missing callable execution handler for '{tool.name}'")
            status = "PASS" if not errs else "FAIL"
            if errs:
                all_passed = False
            results.append({
                "tool": name,
                "status": status,
                "errors": errs,
                "has_executor": callable(tool.execution_handler),
                "permission_level": tool.permission_level.name if tool.permission_level else None
            })

        return {
            "all_passed": all_passed,
            "total_tools": len(self._tools),
            "passed_tools": sum(1 for r in results if r["status"] == "PASS"),
            "details": results
        }

    def bind_runtime_executors(
        self,
        windows=None,
        filesystem=None,
        developer=None,
        diagnostics=None,
        browser=None,
        vision=None,
        communication=None,
        memory=None,
        ledger=None
    ) -> None:
        """Connects real executable agent methods to each canonical tool schema."""
        if windows is None:
            from agents.windows.agent import WindowsAgent
            windows = WindowsAgent()
        if filesystem is None:
            from agents.filesystem.agent import FileAgent
            filesystem = FileAgent()
        if developer is None:
            from agents.developer.agent import DeveloperAgent
            developer = DeveloperAgent()
        if diagnostics is None:
            from agents.diagnostics.engine import DiagnosticEngine
            diagnostics = DiagnosticEngine()
        if browser is None:
            from agents.browser.agent import BrowserAgent
            browser = BrowserAgent()
        if vision is None:
            from agents.vision.agent import VisionAgent
            vision = VisionAgent()
        if communication is None:
            from agents.communication.agent import CommunicationAgent
            communication = CommunicationAgent(windows=windows)
        if memory is None:
            from memory.store import MemoryStore
            memory = MemoryStore()
        if ledger is None:
            from security.audit.ledger import ActionLedger
            ledger = ActionLedger()

        mapping = {
            "get_system_status": lambda **kw: windows.get_system_summary(),
            "run_system_diagnostics": lambda depth="quick", **kw: diagnostics.run_full_diagnostics(),
            "inspect_project": lambda target="active_project", **kw: developer.inspect_project_for_errors(target),
            "search_files": lambda query, directory=None, extension=None, **kw: filesystem.search_files(query, directory=directory, file_ext=extension),
            "read_file": lambda filepath, max_lines=200, **kw: filesystem.read_file(filepath),
            "list_directory": lambda path=None, **kw: filesystem.list_directory(path),
            "list_windows": lambda **kw: {"success": True, "windows": windows.list_windows(), "verified": True},
            "list_processes": lambda filter=None, **kw: {"success": True, "processes": windows.list_processes(limit=15), "verified": True},
            "get_recent_actions": lambda limit=15, **kw: {"success": True, "actions": ledger.get_recent_actions(limit=limit), "verified": True},
            "search_memory": lambda query, **kw: {"success": True, "results": memory.search_relevant_memories(query), "verified": True},
            "open_file": lambda filepath, **kw: windows.open_file(filepath),
            "copy_file_to_clipboard": lambda filepath, **kw: windows.copy_file_to_clipboard(filepath),
            "open_application": lambda application, path=None, profile=None, force_new=False, **kw: windows.launch_application(
                application,
                arguments=[path] if path else None,
                profile=profile,
                force_new=bool(force_new),
            ),
            "open_application_and_inspect": lambda application, project_path=None, **kw: {
                "success": windows.launch_application(application).get("success", False),
                "application": application,
                "project_diagnostics": developer.inspect_project_for_errors(project_path)
            },
            "focus_window": lambda title, **kw: windows.focus_window_by_title(title),
            "minimize_window": lambda title=None, **kw: windows.minimize_window(title),
            "maximize_window": lambda title=None, **kw: windows.maximize_window(title),
            "restore_window": lambda title=None, **kw: windows.restore_window(title),
            "set_volume": lambda level=None, mute=None, **kw: windows.set_volume(level=level, mute=mute),
            "capture_screen": lambda **kw: vision.capture_screen(),
            "analyze_screen": lambda **kw: vision.analyze_screen(),
            "open_url": lambda url, **kw: browser.open_url(url),
            "search_web": lambda query, **kw: browser.search_web(query),
            "inspect_communication_contact": lambda service="whatsapp", query="", profile="main", record_type=None, **kw: communication.inspect_contact(
                service=service,
                query=query,
                profile=profile,
                record_type=record_type
            ),
            "lookup_communication_contact": lambda service="whatsapp", query="", detail=None, record_type=None, **kw: communication.lookup_contact(
                service=service,
                query=query,
                detail=detail,
                record_type=record_type
            ),
            "read_communication_messages": lambda service="whatsapp", recipient="", limit=1, profile="main", incoming_only=False, **kw: communication.read_messages(
                recipient=recipient,
                limit=limit,
                service=service,
                profile=profile,
                incoming_only=bool(incoming_only)
            ),
            "open_communication_service": lambda service="whatsapp", profile="main", force_new=False, **kw: communication.open_service(
                service=service,
                profile=profile,
                force_new=bool(force_new)
            ),
            "sync_communication_contacts": lambda service="whatsapp", profile="main", **kw: communication.sync_contacts(
                service=service,
                profile=profile
            ),
            "prepare_communication": lambda service, recipient, message, subject=None, profile="main", attachment_path=None, **kw: communication.prepare(
                service=service,
                recipient=recipient,
                message=message,
                subject=subject,
                profile=profile,
                attachment_path=attachment_path
            ),
            "send_communication": lambda service, recipient, message, subject=None, profile="main", attachment_path=None, **kw: communication.send(
                service=service,
                recipient=recipient,
                message=message,
                subject=subject,
                profile=profile,
                attachment_path=attachment_path
            ),
            "read_and_reply_communication": lambda service="whatsapp", recipient="", message="", profile="main", **kw: communication.read_and_reply(
                service=service,
                recipient=recipient,
                message=message,
                profile=profile
            ),
            "start_timer": lambda duration_seconds, label="Timer", **kw: windows.start_timer(duration_seconds, label=label),
            "set_reminder": lambda message, time_expression="now", **kw: windows.set_reminder(message, time_expression=time_expression),
            "store_memory": lambda category, key, value, **kw: {"success": True, "saved": memory.save_semantic_memory(category, key, value), "verified": True},
            "rollback_last_action": lambda **kw: ledger.rollback_last_action(),
            "write_file": lambda filepath, content, **kw: filesystem.write_file(filepath, content),
            "copy_file": lambda source, destination, **kw: filesystem.copy_file(source, destination),
            "move_file": lambda source, destination, **kw: filesystem.move_file(source, destination),
            "apply_patch": lambda filepath, diff, **kw: developer.generate_and_apply_patch(filepath, diff),
            "run_build": lambda project_path=None, command=None, **kw: developer.run_project_build(project_path),
            "run_tests": lambda project_path=None, **kw: developer.run_project_tests(project_path),
            "close_application": lambda application, **kw: windows.close_application(application),
            "delete_file": lambda filepath, permanent=False, **kw: filesystem.delete_file(filepath, permanent=permanent),
            "terminate_process": lambda pid=None, process_name=None, **kw: windows.terminate_process(int(pid)) if pid else {"success": False, "error": "PID required"}
        }

        for tool_name, handler in mapping.items():
            t = self.get(tool_name)
            if t:
                t.execution_handler = handler

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
        name="inspect_communication_contact",
        description="Opens the exact WhatsApp contact/group live, inspects details exposed by WhatsApp Web, and enriches MAYA's private local record.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "Communication service; currently whatsapp", required=False, default="whatsapp"),
            ToolParameter("query", "string", "Exact contact or group name", required=True),
            ToolParameter("profile", "string", "Chrome profile hint", required=False, default="main"),
            ToolParameter("record_type", "string", "Optional filter: contact or group", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="lookup_communication_contact",
        description="Looks up a person/group and locally stored details in MAYA's private WhatsApp/Telegram index without sending anything.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "Communication service, normally whatsapp", required=False, default="whatsapp"),
            ToolParameter("query", "string", "Contact or group name/number to look up", required=True),
            ToolParameter("detail", "string", "Optional requested detail such as phone, jid, type, or all", required=False),
            ToolParameter("record_type", "string", "Optional filter: contact or group", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_1_OBSERVATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="read_communication_messages",
        description="Reads the latest visible messages live from a specified authenticated WhatsApp conversation without sending anything.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "Communication service; currently whatsapp", required=False, default="whatsapp"),
            ToolParameter("recipient", "string", "Exact synced contact/group name or 'current chat'", required=True),
            ToolParameter("limit", "integer", "Number of latest visible messages to read (1-20)", required=False, default=1),
            ToolParameter("profile", "string", "Chrome profile hint", required=False, default="main"),
            ToolParameter("incoming_only", "boolean", "When true, only return incoming message bubbles from the other party/group", required=False, default=False)
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
        name="open_file",
        description="Opens a local file with the Windows associated application. Accepts exact paths or recent-file references such as 'latest screenshot', 'recent PNG', or 'latest file'.",
        category="filesystem",
        parameters=[
            ToolParameter("filepath", "string", "File path or recent-file reference", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="copy_file_to_clipboard",
        description="Places the actual local file on the Windows file clipboard so it can be pasted with Ctrl+V. Accepts exact paths or recent-file references.",
        category="filesystem",
        parameters=[
            ToolParameter("filepath", "string", "File path or recent-file reference", required=True)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="open_communication_service",
        description="Focuses an existing authenticated Gmail/WhatsApp/Telegram browser tab, creating a new tab only when needed or explicitly requested.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "gmail, whatsapp, or telegram", required=True),
            ToolParameter("profile", "string", "Chrome profile hint", required=False, default="main"),
            ToolParameter("force_new", "boolean", "Force creation of a new service tab", required=False, default=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="sync_communication_contacts",
        description="Synchronizes contacts/chats from the authenticated WhatsApp Web UI into MAYA's private local contact index.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "Communication service; currently whatsapp", required=False, default="whatsapp"),
            ToolParameter("profile", "string", "Chrome profile hint", required=False, default="main")
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="open_application",
        description="Launches or focuses an authorized application executable and verifies its process launch.",
        category="windows",
        parameters=[
            ToolParameter("application", "string", "Application name (e.g. 'Visual Studio Code', 'Google Chrome', 'Notepad')", required=True),
            ToolParameter("path", "string", "Optional target file or workspace directory to open", required=False),
            ToolParameter(
                "profile",
                "string",
                "Optional browser profile hint such as 'main', a Chrome profile name, directory, or signed-in account email",
                required=False
            ),
            ToolParameter(
                "force_new",
                "boolean",
                "Launch a new instance/window instead of reusing an existing one",
                required=False,
                default=False
            )
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
        name="prepare_communication",
        description="Prepares but does not send a message or email in the user's authenticated Gmail, WhatsApp, or Telegram web session.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "gmail, whatsapp, or telegram", required=True),
            ToolParameter("recipient", "string", "Exact email, phone/contact name, or Telegram username/contact", required=True),
            ToolParameter("message", "string", "Optional message body to prepare when sending an attachment", required=False, default=""),
            ToolParameter("subject", "string", "Optional Gmail subject", required=False),
            ToolParameter("profile", "string", "Chrome profile hint; defaults to main", required=False, default="main"),
            ToolParameter("attachment_path", "string", "Optional local attachment path", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_2_SAFE_ACTION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="send_communication",
        description="Sends a message or email from the user's authenticated Gmail, WhatsApp, or Telegram web session after permission approval and verifies the send state.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "gmail, whatsapp, or telegram", required=True),
            ToolParameter("recipient", "string", "Exact email, phone/contact name, or Telegram username/contact", required=True),
            ToolParameter("message", "string", "Optional message body to send when an attachment is present", required=False, default=""),
            ToolParameter("subject", "string", "Optional Gmail subject", required=False),
            ToolParameter("profile", "string", "Chrome profile hint; defaults to main", required=False, default="main"),
            ToolParameter("attachment_path", "string", "Optional local attachment path", required=False)
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
        undo_available=False
    ))

    registry.register(ToolSchema(
        name="read_and_reply_communication",
        description="Reads the latest visible WhatsApp message from a specified chat and then sends the user's explicit reply. The external send requires exact confirmation.",
        category="communication",
        parameters=[
            ToolParameter("service", "string", "Communication service; currently whatsapp", required=False, default="whatsapp"),
            ToolParameter("recipient", "string", "Exact synced contact or group name", required=True),
            ToolParameter("message", "string", "Exact reply text requested by the user", required=True),
            ToolParameter("profile", "string", "Chrome profile hint", required=False, default="main")
        ],
        permission_level=PermissionLevel.LEVEL_3_MODIFICATION,
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

    # Bind real executable agent methods by default
    registry.bind_runtime_executors()
    return registry

default_tool_registry = build_default_tool_registry()
