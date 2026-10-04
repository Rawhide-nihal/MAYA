"""
MAYA Brain Central Orchestrator
Coordinates: Context -> Memory -> Model Runtime -> Planner -> Tools -> Verification -> Response.
"""
from typing import Dict, Any, Optional, Generator
import time

from maya_core.models.base import DeterministicIntentClassifier
from maya_core.models.runtime import MayaModelRuntime, model_runtime
from maya_core.context.builder import ContextBuilder
from maya_core.planner.dynamic_planner import DynamicTaskPlanner, DynamicTaskPlan, PlanState
from memory.store import MemoryStore
from security.permissions.tier import PermissionManager
from security.audit.ledger import ActionLedger

class MayaBrain:
    def __init__(
        self,
        context_builder: ContextBuilder,
        planner: DynamicTaskPlanner,
        memory: MemoryStore,
        permissions: PermissionManager,
        ledger: ActionLedger,
        runtime: Optional[MayaModelRuntime] = None
    ):
        self.context_builder = context_builder
        self.planner = planner
        self.memory = memory
        self.permissions = permissions
        self.ledger = ledger
        self.runtime = runtime or model_runtime
        self.classifier = DeterministicIntentClassifier()

    def process_request(self, user_text: str, permission_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes complete cognitive pipeline:
        1. Understand: Extract intent & tool parameters
        2. Context Retrieval: Budgeted memory & active workspace state
        3. Decide: Conversational vs Multi-Step Action
        4. Plan & Act: Dynamic Task Planner execution
        5. Verify & Respond: Formulate natural verified output
        """
        cleaned_query = user_text.strip()
        if not cleaned_query:
            return {"error": "Empty query"}

        # 1. Store user message in memory
        self.memory.add_message("user", cleaned_query)

        # 2. Understand intent
        intent_info = self.classifier.classify_and_extract(cleaned_query)
        intent = intent_info.get("intent", "CHAT")
        tool = intent_info.get("tool")

        # 3. Retrieve context
        ctx = self.context_builder.build_context(cleaned_query)

        # If conversational or suggestion
        if intent in ["CHAT", "SUGGESTION", "QUESTION"] and not tool:
            self.planner.emit("maya.state.changed", {"state": "THINKING"})
            reply = self.runtime.generate(cleaned_query, system_prompt=ctx["prompt"])
            self.memory.add_message("maya", reply)
            self.planner.emit("maya.state.changed", {"state": "IDLE"})

            return {
                "intent": intent,
                "reply": reply,
                "executed_tool": None,
                "tasks": [],
                "timestamp": time.time()
            }

        # 4. Plan: Create dynamic multi-step plan
        self.planner.emit("maya.state.changed", {"state": "PLANNING"})
        plan = self.planner.create_plan(cleaned_query, intent_info)

        # 5. Execute Plan with verification
        plan_result = self.planner.execute_plan(plan, permission_token=permission_token)

        # Check if permission confirmation is needed
        if plan_result.get("requires_confirmation"):
            return {
                "intent": intent,
                "reply": f"This action requires your confirmation: {plan_result.get('step', {}).get('description', '')}",
                "requires_confirmation": True,
                "confirmation_id": plan_result.get("confirmation_id"),
                "plan_id": plan.plan_id,
                "tasks": plan_result.get("steps", []),
                "timestamp": time.time()
            }

        # 6. Natural Language Response Formulation from verified results
        reply = self._formulate_response(intent_info, plan_result)
        self.memory.add_message("maya", reply, metadata={"plan_id": plan.plan_id})

        return {
            "intent": intent,
            "reply": reply,
            "executed_tool": tool,
            "plan_id": plan.plan_id,
            "tasks": plan_result.get("steps", []),
            "details": plan_result.get("last_result"),
            "timestamp": time.time()
        }

    def _formulate_response(self, intent_info: Dict[str, Any], plan_result: Dict[str, Any]) -> str:
        tool = intent_info.get("tool")
        steps = plan_result.get("steps", [])
        last_res = plan_result.get("last_result") or {}

        # If any step failed, communicate failure honestly
        failed_steps = [s for s in steps if s.get("state") == "FAILED"]
        if failed_steps:
            f_step = failed_steps[0]
            err = f_step.get("result", {}).get("error", "Execution failed")
            return f"I ran into an issue while executing '{f_step.get('name')}': {err}"

        # Verified success responses
        if tool == "open_application_and_inspect":
            app = intent_info.get("arguments", {}).get("application", "VS Code")
            issues_count = last_res.get("issues_count", 0)
            if issues_count == 0:
                return f"{app} is open and I've scanned your project. No syntax or configuration errors were found. Workspace is healthy."
            else:
                return f"{app} is open and I've scanned your project. I found {issues_count} minor issue(s). Here's what I found:"

        elif tool == "open_application":
            app = intent_info.get("arguments", {}).get("application", "Application")
            return f"{app} has been launched and verified running."

        elif tool == "run_system_diagnostics":
            return "System diagnostic scan completed. Check the PC Control panel for detailed health indicators."

        elif tool == "rollback_last_action":
            return last_res.get("message", "Reversible action successfully rolled back in the action ledger.")

        elif tool == "get_recent_actions":
            return "Here are the recent actions recorded in the Action Ledger."

        elif tool == "clean_temp_files":
            return last_res.get("summary", "Temporary files cleaned.")

        elif tool == "search_files":
            count = last_res.get("count", 0)
            return f"Found {count} matching file(s)."

        return f"Completed requested task: {intent_info.get('summary', 'Action executed')}."
