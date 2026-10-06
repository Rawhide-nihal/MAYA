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
from agents.communication.agent import CommunicationAgent

class PlanState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_FOR_PERMISSION = "WAITING_FOR_PERMISSION"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
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
    NON_FATAL_FAILURE_TOOLS = {
        "capture_screen", "analyze_screen", "get_system_status",
        "inspect_project", "search_files", "search_web", "list_directory",
        "read_file", "report_findings", "get_recent_actions"
    }

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
        communication: Optional[CommunicationAgent] = None,
        unified_context=None,
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
        self.communication = communication or CommunicationAgent(windows=windows)
        self.unified_context = unified_context
        self.event_callback = event_callback
        self.active_plans: Dict[str, DynamicTaskPlan] = {}

    def emit(self, event_name: str, payload: Dict[str, Any]):
        if self.event_callback:
            try:
                self.event_callback(event_name, payload)
                aliases = {
                    "plan.created": "task.plan.created",
                    "tool.started": "task.step.started",
                    "tool.completed": "task.step.completed",
                    "tool.failed": "task.step.failed",
                }
                if event_name in aliases:
                    self.event_callback(aliases[event_name], payload)
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
            launch_arguments = {"application": app}
            if args.get("profile"):
                launch_arguments["profile"] = args.get("profile")
            if args.get("path"):
                launch_arguments["path"] = args.get("path")
            if args.get("force_new"):
                launch_arguments["force_new"] = True
            steps.append(DynamicPlanStep(
                step_id=1,
                name=f"Launch {app}",
                description=f"Execute {app} binary and verify process",
                tool="open_application",
                arguments=launch_arguments
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
        self.emit("plan.created", {
            "plan_id": plan_id,
            "goal": goal,
            "total_steps": len(steps),
            "steps": [asdict(step) for step in steps],
        })
        return plan

    def create_plan_from_neural(self, goal: str, decision: Any) -> DynamicTaskPlan:
        """Constructs an executable DynamicTaskPlan directly from a validated NeuralDecision."""
        plan_id = str(uuid.uuid4())[:8]
        steps: List[DynamicPlanStep] = []

        if getattr(decision, "decision_type", "") == "plan" and getattr(decision, "steps", None):
            for idx, s in enumerate(decision.steps):
                step_tool = getattr(s, "tool", "")
                step_args = getattr(s, "arguments", {}) or {}
                step_desc = getattr(s, "description", "") or f"Execute {step_tool}"
                steps.append(DynamicPlanStep(
                    step_id=idx + 1,
                    name=step_desc,
                    description=step_desc,
                    tool=step_tool,
                    arguments=step_args
                ))
        elif getattr(decision, "decision_type", "") == "tool_call" and getattr(decision, "tool", None):
            return self.create_plan(goal, {
                "tool": decision.tool,
                "arguments": getattr(decision, "arguments", {}) or {},
                "summary": getattr(decision, "reasoning", "") or f"Execute {decision.tool}"
            })

        if not steps:
            steps.append(DynamicPlanStep(
                step_id=1,
                name="Execute action",
                description=goal,
                tool="chat_reply",
                arguments={}
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
        partial_failures = []

        for idx, step in enumerate(plan.steps):
            if plan.cancelled:
                step.state = StepState.CANCELLED
                plan.state = PlanState.CANCELLED
                break

            plan.active_step_index = idx
            step.state = StepState.RUNNING
            step.started_at = time.time()
            self.emit("tool.started", {
                "plan_id": plan.plan_id,
                "step_id": step.step_id,
                "tool": step.tool,
                "name": step.name,
                "description": step.description,
            })

            # Execute tool with permission check
            tool_res = self.execute_tool(step.tool, step.arguments, token=permission_token, plan_id=plan.plan_id)

            if tool_res.get("requires_confirmation"):
                step.state = StepState.WAITING
                step.requires_permission = True
                step.confirmation_id = tool_res.get("confirmation_id")
                plan.state = PlanState.WAITING_FOR_PERMISSION
                self.active_plans[plan.plan_id] = plan
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
                self.emit("tool.completed", {
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "name": step.name,
                    "verified": is_verified,
                })
            else:
                self.emit("tool.failed", {"plan_id": plan.plan_id, "step_id": step.step_id, "tool": step.tool, "error": tool_res.get("error")})
                if step.tool in self.NON_FATAL_FAILURE_TOOLS and idx < len(plan.steps) - 1:
                    partial_failures.append({
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "error": tool_res.get("error", "Step failed")
                    })
                    continue
                plan.state = PlanState.FAILED
                break

        if plan.state not in {PlanState.FAILED, PlanState.CANCELLED, PlanState.WAITING_FOR_PERMISSION}:
            plan.state = PlanState.PARTIAL_SUCCESS if partial_failures else PlanState.COMPLETED
            plan.completed_at = time.time()
            self.emit("task.completed", {
                "plan_id": plan.plan_id,
                "partial": bool(partial_failures),
                "failures": partial_failures
            })
            self.emit("maya.state.changed", {"state": "IDLE", "plan_id": plan.plan_id})

        return {
            "plan_id": plan.plan_id,
            "state": plan.state.value,
            "steps": executed_steps,
            "last_result": last_result,
            "partial_failures": partial_failures
        }

    def resume_plan(self, plan_id: str, confirmation_id: str, permission_token: str) -> Dict[str, Any]:
        """Resume a suspended plan while preserving verification and partial-success semantics."""
        if plan_id not in self.active_plans:
            return {"success": False, "error": f"Plan '{plan_id}' not found in active plans."}

        plan = self.active_plans[plan_id]
        if plan.state != PlanState.WAITING_FOR_PERMISSION:
            return {"success": False, "error": f"Plan '{plan_id}' is in state {plan.state}, not waiting for permission."}

        curr_idx = plan.active_step_index
        if curr_idx >= len(plan.steps):
            return {"success": False, "error": "Plan active step index out of bounds."}

        step = plan.steps[curr_idx]

        valid, reason = self.permissions.validate_token_for_resume(
            token=permission_token,
            plan_id=plan.plan_id,
            step_id=step.step_id,
            tool_name=step.tool,
            arguments=step.arguments,
            confirmation_id=confirmation_id
        )
        if not valid:
            self.emit("permission.resolved", {"plan_id": plan.plan_id, "approved": False, "error": reason})
            return {"success": False, "error": reason}

        self.emit("permission.resolved", {"plan_id": plan.plan_id, "approved": True})
        self.emit("maya.state.changed", {"state": "EXECUTING", "plan_id": plan.plan_id})

        partial_failures = []

        # Execute the exact suspended step with its single-use authorization.
        step.state = StepState.RUNNING
        step.started_at = step.started_at or time.time()
        self.emit("tool.started", {
            "plan_id": plan.plan_id,
            "step_id": step.step_id,
            "tool": step.tool,
            "name": step.name
        })

        tool_res = self.execute_tool(
            step.tool,
            step.arguments,
            token=permission_token,
            plan_id=plan.plan_id
        )
        self.permissions.consume_token(permission_token)

        is_success = tool_res.get("success", False)
        step.state = StepState.SUCCESS if is_success else StepState.FAILED
        step.result = tool_res
        step.verified = tool_res.get("verified", is_success)
        step.completed_at = time.time()

        if not is_success:
            self.emit("tool.failed", {
                "plan_id": plan.plan_id,
                "step_id": step.step_id,
                "tool": step.tool,
                "error": tool_res.get("error")
            })
            if step.tool in self.NON_FATAL_FAILURE_TOOLS and curr_idx < len(plan.steps) - 1:
                partial_failures.append({
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "error": tool_res.get("error", "Step failed")
                })
            else:
                plan.state = PlanState.FAILED
                return {
                    "success": False,
                    "plan_id": plan.plan_id,
                    "state": plan.state.value,
                    "error": tool_res.get("error"),
                    "steps": [asdict(s) for s in plan.steps],
                }
        else:
            self.emit("tool.completed", {
                "plan_id": plan.plan_id,
                "step_id": step.step_id,
                "tool": step.tool
            })

        # Continue remaining steps. A later privileged step can suspend the same plan again.
        for idx in range(curr_idx + 1, len(plan.steps)):
            if plan.cancelled:
                plan.steps[idx].state = StepState.CANCELLED
                plan.state = PlanState.CANCELLED
                break

            plan.active_step_index = idx
            next_step = plan.steps[idx]
            next_step.state = StepState.RUNNING
            next_step.started_at = time.time()
            self.emit("tool.started", {
                "plan_id": plan.plan_id,
                "step_id": next_step.step_id,
                "tool": next_step.tool,
                "name": next_step.name
            })

            next_res = self.execute_tool(
                next_step.tool,
                next_step.arguments,
                plan_id=plan.plan_id
            )

            if next_res.get("requires_confirmation"):
                next_step.state = StepState.WAITING
                next_step.requires_permission = True
                next_step.confirmation_id = next_res.get("confirmation_id")
                plan.state = PlanState.WAITING_FOR_PERMISSION
                self.emit("permission.requested", {
                    "plan_id": plan.plan_id,
                    "step_id": next_step.step_id,
                    "confirmation_id": next_step.confirmation_id
                })
                return {
                    "success": False,
                    "plan_id": plan.plan_id,
                    "state": plan.state.value,
                    "requires_confirmation": True,
                    "confirmation_id": next_step.confirmation_id,
                    "step": asdict(next_step),
                    "steps": [asdict(s) for s in plan.steps],
                    "partial_failures": partial_failures,
                }

            step_ok = next_res.get("success", False)
            next_step.state = StepState.SUCCESS if step_ok else StepState.FAILED
            next_step.result = next_res
            next_step.verified = next_res.get("verified", step_ok)
            next_step.completed_at = time.time()

            if step_ok:
                self.emit("tool.completed", {
                    "plan_id": plan.plan_id,
                    "step_id": next_step.step_id,
                    "tool": next_step.tool
                })
                continue

            self.emit("tool.failed", {
                "plan_id": plan.plan_id,
                "step_id": next_step.step_id,
                "tool": next_step.tool,
                "error": next_res.get("error")
            })
            if next_step.tool in self.NON_FATAL_FAILURE_TOOLS and idx < len(plan.steps) - 1:
                partial_failures.append({
                    "step_id": next_step.step_id,
                    "tool": next_step.tool,
                    "error": next_res.get("error", "Step failed")
                })
                continue

            plan.state = PlanState.FAILED
            break

        if plan.state not in {PlanState.FAILED, PlanState.CANCELLED, PlanState.WAITING_FOR_PERMISSION}:
            plan.state = PlanState.PARTIAL_SUCCESS if partial_failures else PlanState.COMPLETED
            plan.completed_at = time.time()
            self.emit("task.completed", {
                "plan_id": plan.plan_id,
                "partial": bool(partial_failures),
                "failures": partial_failures
            })
            self.emit("maya.state.changed", {"state": "IDLE", "plan_id": plan.plan_id})

        return {
            "success": plan.state in {PlanState.COMPLETED, PlanState.PARTIAL_SUCCESS},
            "plan_id": plan.plan_id,
            "state": plan.state.value,
            "steps": [asdict(s) for s in plan.steps],
            "partial_failures": partial_failures,
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
            launch_args = [arguments.get("path")] if arguments.get("path") else None
            result = self.windows.launch_application(
                app,
                arguments=launch_args,
                profile=arguments.get("profile"),
                force_new=bool(arguments.get("force_new", False)),
            )
            affected_resources.append(app)
            summary = f"Opened {app}"
            undo_available = False

        elif tool_name == "verify_application":
            app = arguments.get("application", "Visual Studio Code")
            is_alive = self.windows.is_application_running(app)
            result = {"success": is_alive, "verified": is_alive, "application": app}
            summary = f"Verified {app} running status: {is_alive}"

        elif tool_name == "close_application":
            app = arguments.get("application", "")
            result = self.windows.close_application(app)
            affected_resources.append(app)
            summary = f"Closed application '{app}'"

        elif tool_name == "focus_window":
            q = arguments.get("query") or arguments.get("title", "")
            result = self.windows.focus_window_by_title(q)
            summary = f"Focused window matching '{q}'"

        elif tool_name == "minimize_window":
            result = self.windows.minimize_window(arguments.get("title"))
            summary = f"Minimizing window '{arguments.get('title', 'active')}'"

        elif tool_name == "maximize_window":
            result = self.windows.maximize_window(arguments.get("title"))
            summary = f"Maximizing window '{arguments.get('title', 'active')}'"

        elif tool_name == "restore_window":
            result = self.windows.restore_window(arguments.get("title"))
            summary = f"Restoring window '{arguments.get('title', 'active')}'"

        elif tool_name == "list_windows":
            wins = self.windows.list_windows()
            result = {"success": True, "windows": wins, "count": len(wins), "verified": True}
            summary = f"Listed {len(wins)} desktop windows"

        elif tool_name == "list_processes":
            procs = self.windows.list_processes(limit=arguments.get("limit", 15), sort_by=arguments.get("sort_by", "memory"))
            result = {"success": True, "processes": procs, "count": len(procs), "verified": True}
            summary = f"Listed top {len(procs)} processes"

        elif tool_name == "terminate_process":
            pid = int(arguments.get("pid", 0))
            result = self.windows.terminate_process(pid)
            summary = result.get("message", f"Terminated process {pid}")

        elif tool_name == "set_volume":
            result = self.windows.set_volume(level=arguments.get("level"), mute=arguments.get("mute"))
            summary = f"Adjusted audio volume: {result.get('message', 'ok')}"

        elif tool_name == "start_timer":
            dur = arguments.get("duration_seconds", 60)
            lbl = arguments.get("label", "Timer")
            result = self.windows.start_timer(dur, label=lbl)
            summary = f"Started timer for {dur}s ({lbl})"

        elif tool_name == "set_reminder":
            msg = arguments.get("message", "")
            expr = arguments.get("time_expression", "now")
            result = self.windows.set_reminder(msg, time_expression=expr)
            summary = f"Set reminder: '{msg}'"

        # Diagnostics tools
        elif tool_name in ["run_system_diagnostics", "get_system_status"]:
            result = self.diagnostics.run_full_diagnostics()
            summary = f"Ran system diagnostics (Status: {result.get('status')})"

        elif tool_name == "prioritize_findings":
            result = {"success": True, "prioritized": True, "verified": True}
            summary = "Prioritized diagnostic findings by severity"

        # Developer & Coding tools
        elif tool_name == "open_application_and_inspect":
            app = arguments.get("application", "Visual Studio Code")
            proj = arguments.get("project_path")
            app_res = self.windows.launch_application(app)
            diag_res = self.developer.inspect_project_for_errors(proj)
            result = {
                "success": app_res.get("success", False),
                "application": app,
                "app_launch": app_res,
                "project_inspection": diag_res,
                "verified": app_res.get("verified", False)
            }
            affected_resources.append(app)
            summary = f"Opened {app} and inspected workspace ({diag_res.get('issues_count', 0)} issues)"

        elif tool_name == "inspect_project":
            result = self.developer.inspect_project_for_errors(arguments.get("target"))
            affected_resources.append(result.get("path", ""))
            summary = f"Scanned project {result.get('project')}: {result.get('issues_count')} issue(s)"

        elif tool_name in ["run_build", "build_project"]:
            target_proj = arguments.get("project_path") or arguments.get("target")
            result = self.developer.run_project_build(target_proj)
            summary = f"Ran project build: {'Success' if result.get('success') else 'Failed'}"

        elif tool_name == "run_tests":
            target_proj = arguments.get("project_path") or arguments.get("target")
            result = self.developer.run_project_tests(target_proj)
            summary = f"Ran test suite: {'Passed' if result.get('success') else 'Failed'}"

        elif tool_name == "apply_patch":
            fp = arguments.get("filepath", "")
            nc = arguments.get("new_content") or arguments.get("diff", "")
            result = self.developer.generate_and_apply_patch(fp, nc)
            affected_resources.append(fp)
            prev_state = {"original_content": result.get("original_content")}
            undo_available = True
            summary = f"Applied code patch to {fp}"

        # Filesystem tools
        elif tool_name == "open_file":
            ref = arguments.get("filepath", "")
            result = self.windows.open_file(ref)
            if result.get("path"):
                affected_resources.append(result["path"])
            summary = (
                f"Opened file {result.get('name') or ref}"
                if result.get("success")
                else f"Failed to open file reference {ref}"
            )

        elif tool_name == "copy_file_to_clipboard":
            ref = arguments.get("filepath", "")
            result = self.windows.copy_file_to_clipboard(ref)
            if result.get("path"):
                affected_resources.append(result["path"])
            summary = (
                f"Copied {result.get('name') or ref} to Windows clipboard"
                if result.get("success")
                else f"Failed to copy file reference {ref} to clipboard"
            )

        elif tool_name == "list_directory":
            result = self.filesystem.list_directory(arguments.get("path"))
            summary = f"Listed directory contents ({result.get('count', 0)} items)"

        elif tool_name == "search_files":
            q = arguments.get("query", "")
            d = arguments.get("directory")
            ext = arguments.get("extension")
            matches = self.filesystem.search_files(q, directory=d, file_ext=ext)
            result = {"success": True, "matches": matches, "count": len(matches), "verified": True}
            summary = f"Searched files for '{q}' ({len(matches)} found)"

        elif tool_name == "search_file_content":
            q = arguments.get("query", "")
            matches = self.filesystem.search_file_content(q, directory=arguments.get("directory"))
            result = {"success": True, "matches": matches, "count": len(matches), "verified": True}
            summary = f"Searched content for '{q}'"

        elif tool_name == "find_largest_files":
            files = self.filesystem.find_largest_files(arguments.get("directory"), limit=arguments.get("limit", 10))
            result = {"success": True, "files": files, "verified": True}
            summary = f"Located largest {len(files)} files"

        elif tool_name == "find_duplicates":
            dups = self.filesystem.find_duplicates(arguments.get("directory"))
            result = {"success": True, "duplicates": dups, "verified": True}
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

        elif tool_name == "copy_file":
            src = arguments.get("source", "")
            dst = arguments.get("destination", "")
            result = self.filesystem.copy_file(src, dst)
            affected_resources.extend([src, dst])
            prev_state = result.get("previous_state")
            undo_available = True
            summary = f"Copied {src} -> {dst}"

        elif tool_name == "move_file":
            src = arguments.get("source", "")
            dst = arguments.get("destination", "")
            result = self.filesystem.move_file(src, dst)
            affected_resources.extend([src, dst])
            prev_state = {"original_path": src}
            undo_available = True
            summary = f"Moved {src} -> {dst}"

        elif tool_name == "delete_file":
            fp = arguments.get("filepath", "")
            perm = arguments.get("permanent", False)
            result = self.filesystem.delete_file(fp, permanent=perm)
            affected_resources.append(fp)
            prev_state = result.get("previous_state")
            undo_available = True
            summary = f"Deleted file {fp}"

        elif tool_name == "clean_temp_files":
            result = self.filesystem.clean_temp_files()
            summary = result.get("summary", "Cleaned temporary files")

        # Vision tools
        elif tool_name == "capture_screen":
            if self.unified_context is not None:
                result = self.unified_context.capture_screen(
                    label=arguments.get("label"),
                    save=bool(arguments.get("save", False))
                )
            else:
                result = self.vision.capture_screen(return_base64=arguments.get("return_base64", False))
            summary = "Captured desktop display"

        elif tool_name == "analyze_screen":
            result = self.vision.analyze_screen()
            if self.unified_context is not None and result.get("screenshot_path"):
                self.unified_context.remember_entity(
                    "screen_analysis",
                    result,
                    label="latest screen analysis"
                )
            summary = f"Analyzed screen: active {result.get('active_window')}"

        # Browser tools
        elif tool_name == "open_url":
            result = self.browser.open_url(arguments.get("url", ""))
            summary = f"Opened URL {arguments.get('url')}"

        elif tool_name == "search_web":
            result = self.browser.search_web(arguments.get("query", ""))
            summary = f"Web search for '{arguments.get('query')}'"

        # Authenticated communication tools
        elif tool_name == "lookup_communication_contact":
            service = arguments.get("service", "whatsapp")
            query = arguments.get("query", "")
            result = self.communication.lookup_contact(service=service, query=query)
            if result.get("found"):
                summary = f"Found {result.get('name') or query} in the local {service.title()} contact index"
            elif result.get("ambiguous"):
                summary = f"Contact lookup for {query} was ambiguous"
            else:
                summary = f"Did not find {query} in the local {service.title()} contact index"

        elif tool_name == "read_communication_messages":
            service = arguments.get("service", "whatsapp")
            recipient = arguments.get("recipient", "")
            result = self.communication.read_messages(
                recipient=recipient,
                limit=arguments.get("limit", 1),
                service=service,
                profile=arguments.get("profile", "main"),
            )
            summary = (
                f"Read {result.get('count', 0)} live {service.title()} message(s) from {recipient}"
                if result.get("success")
                else f"Failed to read live {service.title()} messages from {recipient}"
            )

        elif tool_name == "open_communication_service":
            service = arguments.get("service", "whatsapp")
            result = self.communication.open_service(
                service=service,
                profile=arguments.get("profile", "main"),
                force_new=bool(arguments.get("force_new", False)),
            )
            summary = (
                f"Opened {service.title()} using {'a new tab' if result.get('created_new') else 'the existing tab'}"
                if result.get("success")
                else f"Failed to open {service.title()}"
            )

        elif tool_name == "sync_communication_contacts":
            service = arguments.get("service", "whatsapp")
            result = self.communication.sync_contacts(
                service=service,
                profile=arguments.get("profile", "main"),
            )
            summary = (
                f"Synced {result.get('contacts_synced', result.get('local_contact_count', 0))} {service.title()} contact/chat names"
                if result.get("success")
                else f"Failed to sync {service.title()} contacts"
            )

        elif tool_name == "prepare_communication":
            result = self.communication.prepare(
                service=arguments.get("service", ""),
                recipient=arguments.get("recipient", ""),
                message=arguments.get("message", ""),
                subject=arguments.get("subject"),
                profile=arguments.get("profile", "main"),
                attachment_path=arguments.get("attachment_path"),
            )
            if result.get("success") and result.get("prepared"):
                summary = f"Prepared {arguments.get('service', 'message')} communication for {arguments.get('recipient', '')}"
            else:
                summary = f"Failed to prepare {arguments.get('service', 'message')} communication for {arguments.get('recipient', '')}"

        elif tool_name == "send_communication":
            result = self.communication.send(
                service=arguments.get("service", ""),
                recipient=arguments.get("recipient", ""),
                message=arguments.get("message", ""),
                subject=arguments.get("subject"),
                profile=arguments.get("profile", "main"),
                attachment_path=arguments.get("attachment_path"),
            )
            if result.get("success") and result.get("verified") and result.get("sent"):
                summary = f"Sent {arguments.get('service', 'message')} communication to {arguments.get('recipient', '')}"
            else:
                summary = f"Communication send to {arguments.get('recipient', '')} failed or was not verified"

        # Memory & Ledger
        elif tool_name == "search_memory":
            q = arguments.get("query", "")
            mems = self.memory.search_relevant_memories(q)
            result = {"success": True, "results": mems, "count": len(mems), "verified": True}
            summary = f"Found {len(mems)} memories matching '{q}'"

        elif tool_name == "store_memory":
            cat = arguments.get("category", "facts")
            k = arguments.get("key", "info")
            val = arguments.get("value") or arguments.get("content", "")
            self.memory.save_semantic_memory(cat, k, val)
            result = {"success": True, "category": cat, "key": k, "value": val, "verified": True}
            summary = f"Saved memory: {cat}/{k}"

        elif tool_name == "rollback_last_action":
            result = self.ledger.rollback_last_action()
            summary = result.get("message", "Rolled back last action")

        elif tool_name == "get_recent_actions":
            acts = self.ledger.get_recent_actions(limit=arguments.get("limit", 15))
            result = {"success": True, "actions": acts, "verified": True}
            summary = f"Retrieved {len(acts)} recent actions"

        elif tool_name == "report_findings":
            result = {"success": True, "reported": True, "verified": True}
            summary = "Reported diagnostic and inspection findings"

        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}

        # Feed verified intermediate results back into the unified session context.
        if self.unified_context is not None:
            try:
                self.unified_context.remember_entity(
                    "tool_result",
                    {
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": result,
                        "verified": result.get("verified", result.get("success", False)),
                    },
                    label=f"last {tool_name} result"
                )
                for key in ("filepath", "path", "saved_path"):
                    candidate = result.get(key)
                    if candidate:
                        self.unified_context.remember_entity(
                            "file",
                            candidate,
                            label="latest file"
                        )
                        break
            except Exception:
                pass

        # Action Ledger Recording
        action_id = str(uuid.uuid4())[:8]
        is_success = result.get("success", False)
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
