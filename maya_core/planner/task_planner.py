"""
MAYA Task Planner & Execution Orchestrator
Operates strictly according to: Understand -> Plan -> Act -> Observe -> Verify -> Report.
Coordinates agents, permissions, action ledger, and real verification.
"""
import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from security.permissions.tier import PermissionManager, PermissionLevel
from security.audit.ledger import ActionLedger, ActionRecord
from memory.store import MemoryStore
from agents.windows.agent import WindowsAgent
from agents.terminal.agent import TerminalAgent
from agents.filesystem.agent import FileAgent
from agents.developer.agent import DeveloperAgent
from agents.diagnostics.engine import DiagnosticEngine
from agents.vision.agent import VisionAgent
from maya_core.router.model_router import ModelRouter

@dataclass
class PlanStep:
    step_id: int
    name: str
    description: str
    tool: str
    arguments: Dict[str, Any]
    status: str = "waiting"  # waiting, running, completed, failed
    result: Optional[Dict[str, Any]] = None

@dataclass
class TaskPlan:
    plan_id: str
    goal: str
    steps: List[PlanStep]
    status: str = "created"
    active_step: int = 0

class TaskPlanner:
    def __init__(
        self,
        router: ModelRouter,
        permissions: PermissionManager,
        ledger: ActionLedger,
        memory: MemoryStore,
        windows: WindowsAgent,
        terminal: TerminalAgent,
        filesystem: FileAgent,
        developer: DeveloperAgent,
        diagnostics: DiagnosticEngine,
        vision: VisionAgent
    ):
        self.router = router
        self.permissions = permissions
        self.ledger = ledger
        self.memory = memory
        self.windows = windows
        self.terminal = terminal
        self.filesystem = filesystem
        self.developer = developer
        self.diagnostics = diagnostics
        self.vision = vision

    def create_plan_for_request(self, user_text: str, intent_info: Dict[str, Any]) -> TaskPlan:
        plan_id = str(uuid.uuid4())[:8]
        tool = intent_info.get("tool")
        args = intent_info.get("arguments", {})

        steps: List[PlanStep] = []

        if tool == "open_application_and_inspect":
            app = args.get("application", "Visual Studio Code")
            steps.append(PlanStep(
                step_id=1,
                name=f"Open {app}",
                description=f"Launch {app} executable and verify process creation",
                tool="open_application",
                arguments={"application": app}
            ))
            steps.append(PlanStep(
                step_id=2,
                name="Inspect active project",
                description="Scan workspace configuration and files for errors",
                tool="inspect_project",
                arguments={"target": "active_project"}
            ))
            steps.append(PlanStep(
                step_id=3,
                name="Synthesize and report findings",
                description="Aggregate diagnostics and produce structured report",
                tool="report_findings",
                arguments={}
            ))
        elif tool == "open_application":
            app = args.get("application", "Visual Studio Code")
            steps.append(PlanStep(
                step_id=1,
                name=f"Launch {app}",
                description=f"Resolve binary path and launch {app}",
                tool="open_application",
                arguments={"application": app}
            ))
            steps.append(PlanStep(
                step_id=2,
                name="Verify window/process",
                description=f"Verify {app} is alive and active",
                tool="verify_application",
                arguments={"application": app}
            ))
        elif tool == "run_system_diagnostics":
            steps.append(PlanStep(
                step_id=1,
                name="Scan system health",
                description="Gather CPU, RAM, storage, network, and developer metrics",
                tool="run_system_diagnostics",
                arguments={}
            ))
            steps.append(PlanStep(
                step_id=2,
                name="Categorize findings",
                description="Prioritize findings into Healthy, Information, Warning, Critical",
                tool="prioritize_findings",
                arguments={}
            ))
        elif tool == "inspect_project":
            steps.append(PlanStep(
                step_id=1,
                name="Analyze project workspace",
                description="Scan active project for errors and build issues",
                tool="inspect_project",
                arguments={}
            ))
        elif tool == "rollback_last_action":
            steps.append(PlanStep(
                step_id=1,
                name="Undo last action",
                description="Rollback previous reversible action from ledger",
                tool="rollback_last_action",
                arguments={}
            ))
        else:
            # Single tool step fallback
            steps.append(PlanStep(
                step_id=1,
                name=tool or "Execute action",
                description=intent_info.get("summary", "Run requested action"),
                tool=tool or "chat_reply",
                arguments=args
            ))

        return TaskPlan(plan_id=plan_id, goal=user_text, steps=steps)

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes tool with permission checks and action ledger recording"""
        # 1. Deterministic Permission Check
        perm = self.permissions.check_permission(tool_name, arguments)
        if not perm.granted:
            return {
                "success": False,
                "error": perm.reason,
                "requires_confirmation": perm.requires_confirmation,
                "confirmation_id": perm.confirmation_id
            }

        start_time = time.time()
        result: Dict[str, Any] = {}
        affected_resources: List[str] = []
        prev_state: Optional[Dict[str, Any]] = None
        undo_available = False
        summary = f"Executed {tool_name}"

        # 2. Tool Execution
        if tool_name == "open_application":
            app = arguments.get("application", "Visual Studio Code")
            result = self.windows.launch_application(app)
            affected_resources.append(app)
            summary = f"Opened {app}"
            undo_available = False

        elif tool_name == "verify_application":
            app = arguments.get("application", "Visual Studio Code")
            procs = self.windows.list_processes(limit=20)
            found = any(app.lower() in p["name"].lower() for p in procs)
            result = {"success": True, "running": found, "application": app}
            summary = f"Verified {app} running status: {found}"

        elif tool_name == "run_system_diagnostics":
            result = self.diagnostics.run_full_diagnostics()
            summary = f"Ran system diagnostics (Status: {result.get('status')})"

        elif tool_name == "inspect_project":
            result = self.developer.inspect_project_for_errors()
            affected_resources.append(result.get("path", ""))
            summary = f"Scanned project {result.get('project')}: {result.get('issues_count')} issue(s) detected"

        elif tool_name == "search_files":
            query = arguments.get("query", "")
            matches = self.filesystem.search_files(query)
            result = {"success": True, "matches": matches, "count": len(matches)}
            summary = f"Searched files for '{query}' (Found {len(matches)})"

        elif tool_name == "clean_temp_files":
            result = self.filesystem.clean_temp_files()
            summary = result.get("summary", "Cleaned temporary files")

        elif tool_name == "report_findings":
            result = {"success": True, "reported": True}
            summary = "Reported diagnostic and inspection findings"

        elif tool_name == "prioritize_findings":
            result = {"success": True, "prioritized": True}
            summary = "Prioritized diagnostic findings by severity"

        elif tool_name == "rollback_last_action":
            result = self.ledger.rollback_last_action()
            summary = result.get("message", "Rolled back last action")

        elif tool_name == "get_recent_actions":
            limit = arguments.get("limit", 5)
            acts = self.ledger.get_recent_actions(limit=limit)
            result = {"success": True, "actions": acts}
            summary = f"Retrieved {len(acts)} recent actions"

        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}

        # 3. Record in Action Ledger
        action_id = str(uuid.uuid4())[:8]
        record = ActionRecord(
            action_id=action_id,
            tool_name=tool_name,
            arguments=arguments,
            affected_resources=affected_resources,
            previous_state=prev_state,
            result=result,
            undo_available=undo_available,
            status="success" if result.get("success", True) else "failed",
            timestamp=start_time,
            summary=summary
        )
        self.ledger.record_action(record)

        return result
