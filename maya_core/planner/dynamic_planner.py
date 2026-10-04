"""
MAYA Dynamic Multi-Step Task Planner & State Machine
Implements: Understand -> Plan -> Act -> Observe -> Verify -> Report.
Supports dynamic step adaptation, typed state transitions, and real-time event dispatching.
"""
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict

from security.permissions.tier import PermissionManager, PermissionLevel
from security.audit.ledger import ActionLedger, ActionRecord
from memory.store import MemoryStore
from agents.windows.agent import WindowsAgent
from agents.terminal.agent import TerminalAgent
from agents.filesystem.agent import FileAgent
from agents.developer.agent import DeveloperAgent
from agents.diagnostics.engine import DiagnosticEngine
from agents.vision.agent import VisionAgent
from agents.browser.agent import BrowserAgent

class PlanState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_FOR_PERMISSION = "WAITING_FOR_PERMISSION"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class StepState(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

@dataclass
class DynamicPlanStep:
    step_id: int
    name: str
    description: str
    tool: str
    arguments: Dict[str, Any]
    state: StepState = StepState.WAITING
    result: Optional[Dict[str, Any]] = None
    verified: bool = False
    requires_permission: bool = False
    confirmation_id: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

@dataclass
class DynamicTaskPlan:
    plan_id: str
    goal: str
    state: PlanState = PlanState.CREATED
    steps: List[DynamicPlanStep] = field(default_factory=list)
    active_step_index: int = 0
    cancelled: bool = False
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

class DynamicTaskPlanner:
    def __init__(
        self,
        permissions: PermissionManager,
        ledger: ActionLedger,
        memory: MemoryStore,
        windows: WindowsAgent,
        terminal: TerminalAgent,
        filesystem: FileAgent,
        developer: DeveloperAgent,
        diagnostics: DiagnosticEngine,
        vision: VisionAgent,
        browser: Optional[BrowserAgent] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        self.permissions = permissions
        self.ledger = ledger
        self.memory = memory
        self.windows = windows
        self.terminal = terminal
        self.filesystem = filesystem
        self.developer = developer
        self.diagnostics = diagnostics
        self.vision = vision
        self.browser = browser or BrowserAgent()
        self.event_callback = event_callback
        self.active_plans: Dict[str, DynamicTaskPlan] = {}

    def emit(self, event_name: str, payload: Dict[str, Any]):
        if self.event_callback:
            try:
                self.event_callback(event_name, payload)
            except Exception:
                pass

    def create_plan(self, goal: str, intent_info: Dict[str, Any]) -> DynamicTaskPlan:
        plan_id = str(uuid.uuid4())[:8]
        tool = intent_info.get("tool")
        args = intent_info.get("arguments", {})
        steps: List[DynamicPlanStep] = []

        if tool == "open_application_and_inspect":
            app = args.get("application", "Visual Studio Code")
            steps.append(DynamicPlanStep(
                step_id=1,
                name=f"Launch {app}",
                description=f"Resolve binary and launch {app}",
                tool="open_application",
                arguments={"application": app}
            ))
            steps.append(DynamicPlanStep(
                step_id=2,
                name="Inspect active workspace",
                description="Scan workspace files and compiler configurations",
                tool="inspect_project",
                arguments={"target": "active_project"}
            ))
            steps.append(DynamicPlanStep(
                step_id=3,
                name="Synthesize and report findings",
                description="Aggregate diagnostics and verify status",
                tool="report_findings",
                arguments={}
            ))

        elif tool == "open_application":
            app = args.get("application", "Visual Studio Code")
            steps.append(DynamicPlanStep(
                step_id=1,
                name=f"Launch {app}",
                description=f"Execute {app} binary and verify process",
                tool="open_application",
                arguments={"application": app}
            ))
            steps.append(DynamicPlanStep(
                step_id=2,
                name="Verify active application",
                description=f"Verify {app} process and window state",
                tool="verify_application",
                arguments={"application": app}
            ))

        elif tool == "run_system_diagnostics":
            steps.append(DynamicPlanStep(
                step_id=1,
                name="Scan system telemetry",
                description="Gather CPU, RAM, GPU, storage, and developer metrics",
                tool="run_system_diagnostics",
                arguments={}
            ))
            steps.append(DynamicPlanStep(
                step_id=2,
                name="Categorize findings",
                description="Prioritize findings into Healthy, Information, Warning, Critical",
                tool="prioritize_findings",
                arguments={}
            ))

        elif tool == "inspect_project":
            steps.append(DynamicPlanStep(
                step_id=1,
                name="Analyze workspace files",
                description="Inspect syntax, build configurations, and test runners",
                tool="inspect_project",
                arguments=args
            ))

        elif tool == "rollback_last_action":
            steps.append(DynamicPlanStep(
                step_id=1,
                name="Rollback last action",
                description="Revert previous reversible action from Action Ledger",
                tool="rollback_last_action",
                arguments=args
            ))

        elif tool == "clean_temp_files":
            steps.append(DynamicPlanStep(
                step_id=1,
                name="Clean temporary files",
                description="Purge stale files (>24h) from Windows Temp",
                tool="clean_temp_files",
                arguments={}
            ))

        elif tool == "search_files":
            q = args.get("query", "")
            steps.append(DynamicPlanStep(
                step_id=1,
                name=f"Search files for '{q}'",
                description=f"Recursively search files matching '{q}'",
                tool="search_files",
                arguments=args
            ))

        else:
            steps.append(DynamicPlanStep(
                step_id=1,
                name=tool or "Execute action",
                description=intent_info.get("summary", "Execute requested action"),
                tool=tool or "chat_reply",
                arguments=args
            ))

        plan = DynamicTaskPlan(plan_id=plan_id, goal=goal, state=PlanState.CREATED, steps=steps)
        self.active_plans[plan_id] = plan
        self.emit("plan.created", {"plan_id": plan_id, "goal": goal, "total_steps": len(steps)})
        return plan

    def execute_plan(self, plan: DynamicTaskPlan, permission_token: Optional[str] = None) -> Dict[str, Any]:
        """Executes all plan steps sequentially with verification and state emission."""
        plan.state = PlanState.RUNNING
        self.emit("maya.state.changed", {"state": "EXECUTING", "plan_id": plan.plan_id})

        executed_steps = []
        last_result = None

        for idx, step in enumerate(plan.steps):
            if plan.cancelled:
                step.state = StepState.CANCELLED
                plan.state = PlanState.CANCELLED
                break

            plan.active_step_index = idx
            step.state = StepState.RUNNING
            step.started_at = time.time()
            self.emit("tool.started", {"plan_id": plan.plan_id, "step_id": step.step_id, "tool": step.tool, "name": step.name})

            # Execute tool with permission check
            tool_res = self.execute_tool(step.tool, step.arguments, token=permission_token, plan_id=plan.plan_id)

            if tool_res.get("requires_confirmation"):
                step.state = StepState.WAITING
                step.requires_permission = True
                step.confirmation_id = tool_res.get("confirmation_id")
                plan.state = PlanState.WAITING_FOR_PERMISSION
                self.emit("permission.requested", {
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "confirmation_id": step.confirmation_id,
                    "reason": tool_res.get("error", "Permission required")
                })
                return {
                    "plan_id": plan.plan_id,
                    "state": plan.state.value,
                    "requires_confirmation": True,
                    "confirmation_id": step.confirmation_id,
                    "step": asdict(step),
                    "steps": [asdict(s) for s in plan.steps]
                }

            is_success = tool_res.get("success", True)
            is_verified = tool_res.get("verified", is_success)

            step.state = StepState.SUCCESS if is_success else StepState.FAILED
            step.result = tool_res
            step.verified = is_verified
            step.completed_at = time.time()
            last_result = tool_res

            executed_steps.append(asdict(step))

            if is_success:
                self.emit("tool.completed", {"plan_id": plan.plan_id, "step_id": step.step_id, "tool": step.tool})
            else:
                self.emit("tool.failed", {"plan_id": plan.plan_id, "step_id": step.step_id, "tool": step.tool, "error": tool_res.get("error")})
                plan.state = PlanState.FAILED
                break

        if plan.state != PlanState.FAILED and plan.state != PlanState.CANCELLED and plan.state != PlanState.WAITING_FOR_PERMISSION:
            plan.state = PlanState.COMPLETED
            plan.completed_at = time.time()
            self.emit("task.completed", {"plan_id": plan.plan_id})
            self.emit("maya.state.changed", {"state": "IDLE", "plan_id": plan.plan_id})

        return {
            "plan_id": plan.plan_id,
            "state": plan.state.value,
            "steps": executed_steps,
            "last_result": last_result
        }

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], token: Optional[str] = None, plan_id: str = "direct") -> Dict[str, Any]:
        """Executes a single tool with deterministic permission validation and Action Ledger recording."""
        perm = self.permissions.check_permission(tool_name, arguments, token=token)
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

        # Windows Agent tools
        if tool_name == "open_application":
            app = arguments.get("application", "Visual Studio Code")
            result = self.windows.launch_application(app)
            affected_resources.append(app)
            summary = f"Opened {app}"
            undo_available = False

        elif tool_name == "verify_application":
            app = arguments.get("application", "Visual Studio Code")
            is_alive = self.windows.is_application_running(app)
            result = {"success": is_alive, "verified": is_alive, "application": app}
            summary = f"Verified {app} running status: {is_alive}"

        elif tool_name == "focus_window":
            q = arguments.get("query", "")
            result = self.windows.focus_window_by_title(q)
            summary = f"Focused window matching '{q}'"

        elif tool_name == "list_processes":
            procs = self.windows.list_processes(limit=arguments.get("limit", 15), sort_by=arguments.get("sort_by", "memory"))
            result = {"success": True, "processes": procs, "count": len(procs)}
            summary = f"Listed top {len(procs)} processes"

        elif tool_name == "terminate_process":
            pid = int(arguments.get("pid", 0))
            result = self.windows.terminate_process(pid)
            summary = result.get("message", f"Terminated process {pid}")

        # Diagnostics tools
        elif tool_name in ["run_system_diagnostics", "get_system_status"]:
            result = self.diagnostics.run_full_diagnostics()
            summary = f"Ran system diagnostics (Status: {result.get('status')})"

        elif tool_name == "prioritize_findings":
            result = {"success": True, "prioritized": True}
            summary = "Prioritized diagnostic findings by severity"

        # Developer & Coding tools
        elif tool_name == "inspect_project":
            result = self.developer.inspect_project_for_errors(arguments.get("target"))
            affected_resources.append(result.get("path", ""))
            summary = f"Scanned project {result.get('project')}: {result.get('issues_count')} issue(s)"

        elif tool_name == "build_project":
            result = self.developer.run_project_build(arguments.get("target"))
            summary = f"Ran project build: {'Success' if result.get('success') else 'Failed'}"

        elif tool_name == "run_tests":
            result = self.developer.run_project_tests(arguments.get("target"))
            summary = f"Ran test suite: {'Passed' if result.get('success') else 'Failed'}"

        elif tool_name == "apply_patch":
            fp = arguments.get("filepath", "")
            nc = arguments.get("new_content", "")
            result = self.developer.generate_and_apply_patch(fp, nc)
            affected_resources.append(fp)
            prev_state = {"original_content": result.get("original_content")}
            undo_available = True
            summary = f"Applied code patch to {fp}"

        # Filesystem tools
        elif tool_name == "search_files":
            q = arguments.get("query", "")
            d = arguments.get("directory")
            matches = self.filesystem.search_files(q, directory=d)
            result = {"success": True, "matches": matches, "count": len(matches)}
            summary = f"Searched files for '{q}' ({len(matches)} found)"

        elif tool_name == "search_file_content":
            q = arguments.get("query", "")
            matches = self.filesystem.search_file_content(q, directory=arguments.get("directory"))
            result = {"success": True, "matches": matches, "count": len(matches)}
            summary = f"Searched content for '{q}'"

        elif tool_name == "find_largest_files":
            files = self.filesystem.find_largest_files(arguments.get("directory"), limit=arguments.get("limit", 10))
            result = {"success": True, "files": files}
            summary = f"Located largest {len(files)} files"

        elif tool_name == "find_duplicates":
            dups = self.filesystem.find_duplicates(arguments.get("directory"))
            result = {"success": True, "duplicates": dups}
            summary = f"Detected {len(dups)} duplicate candidates"

        elif tool_name == "read_file":
            result = self.filesystem.read_file(arguments.get("filepath", ""))
            summary = f"Read file {arguments.get('filepath')}"

        elif tool_name == "write_file":
            fp = arguments.get("filepath", "")
            c = arguments.get("content", "")
            result = self.filesystem.write_file(fp, c)
            affected_resources.append(fp)
            prev_state = {"original_content": result.get("previous_content")}
            undo_available = True
            summary = f"Wrote file {fp}"

        elif tool_name == "move_file":
            src = arguments.get("source", "")
            dst = arguments.get("destination", "")
            result = self.filesystem.move_file(src, dst)
            affected_resources.extend([src, dst])
            prev_state = {"original_path": src}
            undo_available = True
            summary = f"Moved {src} -> {dst}"

        elif tool_name == "clean_temp_files":
            result = self.filesystem.clean_temp_files()
            summary = result.get("summary", "Cleaned temporary files")

        # Vision tools
        elif tool_name == "capture_screen":
            result = self.vision.capture_screen(return_base64=arguments.get("return_base64", False))
            summary = "Captured desktop display"

        elif tool_name == "analyze_screen":
            result = self.vision.analyze_screen()
            summary = f"Analyzed screen: active {result.get('active_window')}"

        # Browser tools
        elif tool_name == "open_url":
            result = self.browser.open_url(arguments.get("url", ""))
            summary = f"Opened URL {arguments.get('url')}"

        elif tool_name == "search_web":
            result = self.browser.search_web(arguments.get("query", ""))
            summary = f"Web search for '{arguments.get('query')}'"

        # Memory & Ledger
        elif tool_name == "store_memory":
            cat = arguments.get("category", "facts")
            k = arguments.get("key", "info")
            c = arguments.get("content", "")
            self.memory.save_semantic_memory(cat, k, c)
            result = {"success": True}
            summary = f"Saved memory: {cat}/{k}"

        elif tool_name == "rollback_last_action":
            result = self.ledger.rollback_last_action()
            summary = result.get("message", "Rolled back last action")

        elif tool_name == "get_recent_actions":
            acts = self.ledger.get_recent_actions(limit=arguments.get("limit", 5))
            result = {"success": True, "actions": acts}
            summary = f"Retrieved {len(acts)} recent actions"

        elif tool_name == "report_findings":
            result = {"success": True, "reported": True}
            summary = "Reported diagnostic and inspection findings"

        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}

        # Action Ledger Recording
        action_id = str(uuid.uuid4())[:8]
        is_success = result.get("success", True)
        record = ActionRecord(
            action_id=action_id,
            plan_id=plan_id,
            tool_name=tool_name,
            arguments=arguments,
            affected_resources=affected_resources,
            previous_state=prev_state,
            result=result,
            verified=result.get("verified", is_success),
            undo_available=undo_available,
            status="success" if is_success else "failed",
            timestamp=start_time,
            summary=summary
        )
        self.ledger.record_action(record)

        return result

    def cancel_plan(self, plan_id: str) -> bool:
        if plan_id in self.active_plans:
            plan = self.active_plans[plan_id]
            plan.cancelled = True
            plan.state = PlanState.CANCELLED
            self.emit("maya.state.changed", {"state": "IDLE", "plan_id": plan_id})
            return True
        return False
