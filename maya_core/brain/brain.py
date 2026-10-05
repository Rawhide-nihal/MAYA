"""
MAYA Brain Central Cognitive Orchestrator (Phase 4 Neural Architecture)
Coordinates: Context -> Memory -> Neural Model -> Structured Decision ->
             Schema Validation -> Deterministic Permissions -> Dynamic Planner ->
             Verification -> Neural Result Synthesis.
Deterministic Intent Classifier is maintained strictly as an emergency safety fallback.
"""
from typing import Dict, Any, Optional, List
import time
import json

from maya_core.models.base import DeterministicIntentClassifier
from maya_core.models.runtime import MayaModelRuntime, model_runtime
from maya_core.context.builder import ContextBuilder
from maya_core.planner.dynamic_planner import DynamicTaskPlanner, DynamicTaskPlan, PlanState
from maya_core.brain.decision import parse_and_validate_decision, NeuralDecision
from maya_core.tools.registry import default_tool_registry
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
        self.tool_registry = default_tool_registry
        # Deterministic classifier reserved as emergency safety fallback
        self.fallback_classifier = DeterministicIntentClassifier()

    def process_request(self, user_text: str, permission_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes the complete cognitive loop:
        1. Understand & Context: Budgeted memory & active workspace state
        2. Neural Inference: Model emits structured decision JSON
        3. Validation: Verify against canonical ToolRegistry schemas
        4. Fallback Handling: Deterministic safety fallback if malformed
        5. Authorization & Planning: Dynamic Task Planner execution
        6. Verification & Result Synthesis: Neural natural language formulation
        """
        cleaned_query = user_text.strip()
        if not cleaned_query:
            return {"error": "Empty query"}

        # 1. Store user message in episodic memory
        self.memory.add_message("user", cleaned_query)

        # Fast conversation path: do not scan the project/system for ordinary chat.
        intent_info = self.fallback_classifier.classify_and_extract(cleaned_query)
        detected_tool = intent_info.get("tool")
        intent = intent_info.get("intent", "CHAT")
        if not detected_tool and intent in ["QUESTION", "SUGGESTION", "CHAT"]:
            self.planner.emit("maya.state.changed", {"state": "THINKING"})
            ctx = self.context_builder.build_chat_context(cleaned_query)
            try:
                raw_chat = self.runtime.generate(
                    cleaned_query,
                    system_prompt=ctx["prompt"],
                    max_new_tokens=96,
                    temperature=0.6,
                    top_p=0.9,
                ).strip()
                reply = self._extract_conversation_text(raw_chat)
            except Exception as e:
                print(f"[MayaBrain] Fast chat generation error: {e}")
                reply = "I hit a local model error while answering that."
            self.memory.add_message("maya", reply)
            self.planner.emit("maya.state.changed", {"state": "IDLE"})
            return {
                "intent": "CHAT",
                "reply": reply,
                "executed_tool": None,
                "tasks": [],
                "fallback_used": False,
                "fast_path": True,
                "timestamp": time.time(),
            }

        # 2. Full context is reserved for operational/tool requests.
        ctx = self.context_builder.build_context(cleaned_query)

        # 3. Neural Decision Step
        self.planner.emit("maya.state.changed", {"state": "THINKING"})
        raw_output = ""
        decision: Optional[NeuralDecision] = None

        try:
            raw_output = self.runtime.generate(cleaned_query, system_prompt=ctx["prompt"])
            decision = parse_and_validate_decision(raw_output, self.tool_registry)
        except Exception as e:
            print(f"[MayaBrain] Neural generation error: {e}")

        # 4. Fallback if model did not return a valid structured decision for an action command
        fallback_used = False

        if not decision or not getattr(decision, "is_valid", True) or (decision.decision_type == "conversation" and detected_tool):
            fallback_used = True
            print(f"[MayaBrain] Triggering deterministic safety fallback for: '{cleaned_query}'")
            intent = intent_info.get("intent", "CHAT")

            if detected_tool:
                decision = NeuralDecision(
                    decision_type="tool_call",
                    tool=detected_tool,
                    arguments=intent_info.get("arguments", {}),
                    confidence=0.85,
                    reasoning=intent_info.get("summary", "Deterministic fallback match")
                )
            elif intent in ["QUESTION", "SUGGESTION", "CHAT"]:
                # Simple conversational reply
                decision = NeuralDecision(
                    decision_type="conversation",
                    message=raw_output if raw_output.strip() else "I understand. How else can I assist with your system or development workspace?",
                    confidence=0.9
                )
            else:
                decision = NeuralDecision(
                    decision_type="conversation",
                    message=raw_output or "I processed your request.",
                    confidence=0.8
                )

        # 5. Route based on validated decision type
        if decision.decision_type == "conversation":
            reply = decision.message or raw_output
            self.memory.add_message("maya", reply)
            self.planner.emit("maya.state.changed", {"state": "IDLE"})
            return {
                "intent": "CHAT",
                "reply": reply,
                "executed_tool": None,
                "tasks": [],
                "fallback_used": fallback_used,
                "timestamp": time.time()
            }

        elif decision.decision_type == "clarification":
            reply = decision.message or "Could you please provide more details so I can safely proceed?"
            self.memory.add_message("maya", reply)
            self.planner.emit("maya.state.changed", {"state": "IDLE"})
            return {
                "intent": "CLARIFICATION",
                "reply": reply,
                "requires_clarification": True,
                "executed_tool": None,
                "tasks": [],
                "fallback_used": fallback_used,
                "timestamp": time.time()
            }

        elif decision.decision_type == "refusal":
            reply = decision.message or "I cannot execute this request due to safety and security policies."
            self.memory.add_message("maya", reply)
            self.planner.emit("maya.state.changed", {"state": "IDLE"})
            return {
                "intent": "REFUSAL",
                "reply": reply,
                "refused": True,
                "executed_tool": None,
                "tasks": [],
                "fallback_used": fallback_used,
                "timestamp": time.time()
            }

        # 6. Planning & Execution for tool_call and plan
        self.planner.emit("maya.state.changed", {"state": "PLANNING"})
        plan = self.planner.create_plan_from_neural(cleaned_query, decision)

        # Execute Plan with deterministic verification
        plan_result = self.planner.execute_plan(plan, permission_token=permission_token)

        # Check if permission confirmation is needed
        if plan_result.get("requires_confirmation"):
            return {
                "intent": "PERMISSION_REQUIRED",
                "reply": f"This action requires your confirmation: {plan_result.get('step', {}).get('description', '')}",
                "requires_confirmation": True,
                "confirmation_id": plan_result.get("confirmation_id"),
                "plan_id": plan.plan_id,
                "tasks": plan_result.get("steps", []),
                "fallback_used": fallback_used,
                "timestamp": time.time()
            }

        # 7. Natural Result Synthesis: Model verbalizes verified results
        reply = self._synthesize_natural_response(cleaned_query, decision, plan_result)
        self.memory.add_message("maya", reply, metadata={"plan_id": plan.plan_id, "fallback_used": fallback_used})

        intent_label = decision.intent
        if not intent_label:
            if decision.tool == "run_system_diagnostics":
                intent_label = "SYSTEM_DIAGNOSTIC"
            elif decision.tool in ["open_application", "close_application", "set_volume"]:
                intent_label = "PC_ACTION"
            elif decision.tool in ["inspect_project", "run_build", "run_tests", "open_application_and_inspect"]:
                intent_label = "DEVELOPMENT_ACTION"
            else:
                intent_label = "TOOL_EXECUTION"

        return {
            "intent": intent_label,
            "reply": reply,
            "executed_tool": decision.tool if decision.decision_type == "tool_call" else "multi_step_plan",
            "plan_id": plan.plan_id,
            "tasks": plan_result.get("steps", []),
            "details": plan_result.get("last_result"),
            "fallback_used": fallback_used,
            "timestamp": time.time()
        }

    @staticmethod
    def _extract_conversation_text(raw_output: str) -> str:
        """Hide internal structured conversation JSON from the user when the model emits it."""
        text = (raw_output or "").strip()
        if not text:
            return "I'm here. What do you want to work on?"
        try:
            candidate = text
            if "```" in candidate:
                start = candidate.find("{")
                end = candidate.rfind("}")
                if start >= 0 and end > start:
                    candidate = candidate[start:end + 1]
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                message = parsed.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
        except Exception:
            pass
        return text

    def _synthesize_natural_response(
        self,
        user_query: str,
        decision: NeuralDecision,
        plan_result: Dict[str, Any]
    ) -> str:
        """
        Synthesizes a natural, factual verbal confirmation using the neural model
        grounded in the actual verified execution results.
        Zero hardcoded templates when model is available.
        """
        steps = plan_result.get("steps", [])
        last_res = plan_result.get("last_result") or {}

        # If any step failed, report honest diagnostic failure
        failed_steps = [s for s in steps if s.get("state") == "FAILED"]
        if failed_steps:
            f_step = failed_steps[0]
            err = f_step.get("result", {}).get("error", "Execution failed")
            return f"I ran into an issue while executing '{f_step.get('name')}': {err}"

        # Build factual verification payload
        tool_name = decision.tool or "action"
        exec_payload = {
            "query": user_query,
            "tool": tool_name,
            "arguments": decision.arguments,
            "verified": True,
            "result_summary": last_res
        }

        # Ask MAYA model to formulate a natural concise response
        synth_prompt = (
            f"Execution result: {json.dumps(exec_payload, default=str)}\n"
            f"Synthesize a concise, natural, professional confirmation to the user in 1-2 sentences. "
            f"Be factual, direct, and conversational. Do not mention JSON or execution data structures."
        )

        try:
            synth_reply = self.runtime.generate(
                prompt=synth_prompt,
                system_prompt="You are MAYA, reporting verified execution results to your user."
            )
            if synth_reply and synth_reply.strip() and not synth_reply.startswith("{"):
                return synth_reply.strip()
            # If the model returned JSON or empty, extract message if present
            if synth_reply and "{" in synth_reply:
                try:
                    parsed = json.loads(synth_reply)
                    if isinstance(parsed, dict) and "message" in parsed:
                        return parsed["message"]
                except Exception:
                    pass
        except Exception as e:
            print(f"[MayaBrain] Synthesis generation fallback: {e}")

        # Grounded factual fallback
        if tool_name == "open_application":
            app = (decision.arguments or {}).get("application", "Application")
            return f"{app} has been launched and verified running."
        elif tool_name == "close_application":
            app = (decision.arguments or {}).get("application", "Application")
            return f"{app} has been closed."
        elif tool_name == "search_files":
            count = last_res.get("count", 0)
            return f"Found {count} matching file(s)."
        elif tool_name == "run_system_diagnostics":
            return "System diagnostic scan completed. Hardware telemetry and toolchains are verified."
        elif tool_name == "rollback_last_action":
            return last_res.get("message", "Action successfully rolled back.")
        elif tool_name == "set_volume":
            lvl = (decision.arguments or {}).get("level", "target")
            return f"Master audio volume set to {lvl}%."

        return f"Successfully completed: {user_query}."
