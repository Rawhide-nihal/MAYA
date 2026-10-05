"""
MAYA Brain Central Cognitive Orchestrator (Phase 4 Neural Architecture)
Coordinates: Context -> Memory -> Neural Model -> Structured Decision ->
             Schema Validation -> Deterministic Permissions -> Dynamic Planner ->
             Verification -> Neural Result Synthesis.
Deterministic Intent Classifier is maintained strictly as an emergency safety fallback.
"""
from typing import Dict, Any, Optional, List, Generator
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
from maya_core.personality.engine import PersonalityEngine

class MayaBrain:
    def __init__(
        self,
        context_builder: ContextBuilder,
        planner: DynamicTaskPlanner,
        memory: MemoryStore,
        permissions: PermissionManager,
        ledger: ActionLedger,
        runtime: Optional[MayaModelRuntime] = None,
        unified_context=None,
        personality: Optional[PersonalityEngine] = None
    ):
        self.context_builder = context_builder
        self.planner = planner
        self.memory = memory
        self.permissions = permissions
        self.ledger = ledger
        self.runtime = runtime or model_runtime
        self.tool_registry = default_tool_registry
        self.unified_context = unified_context
        self.personality = personality or PersonalityEngine()
        # Deterministic classifier reserved as emergency safety fallback
        self.fallback_classifier = DeterministicIntentClassifier()

    def _is_context_command(self, user_text: str) -> bool:
        lower = (user_text or "").strip().lower()
        if self.personality.parse_mode_command(lower):
            return True
        patterns = [
            "take a screenshot", "take screenshot", "capture screenshot",
            "save that screenshot", "save this screenshot", "keep that screenshot",
            "keep this screenshot", "compare this with before", "compare with before",
            "compare screenshots", "look at my screen", "check my screen",
            "what's on my screen", "what is on my screen", "what's this error",
            "what is this error", "read this page", "where should i click",
            "what am i doing", "what's open", "what is open"
        ]
        return any(p in lower for p in patterns)

    def _handle_context_command(self, user_text: str) -> Optional[Dict[str, Any]]:
        cleaned = (user_text or "").strip()
        lower = cleaned.lower()

        mode = self.personality.parse_mode_command(cleaned)
        if mode:
            self.personality.set_mode(mode.value)
            reply = f"{self.personality.describe_mode(mode)} Ready, Boss."
            return {
                "intent": "MODE_CHANGE",
                "reply": reply,
                "mode": mode.value,
                "executed_tool": None,
                "tasks": [],
                "verified": True,
                "timestamp": time.time(),
            }

        if self.unified_context is None:
            return None

        if any(p in lower for p in ["take a screenshot", "take screenshot", "capture screenshot"]):
            should_save = any(p in lower for p in ["keep it", "save it", "keep this", "save this"])
            result = self.unified_context.capture_screen(save=should_save)
            if result.get("success"):
                window = ((result.get("active_window") or {}).get("title") or "the current desktop")
                reply = (
                    f"Screenshot {'saved' if should_save else 'captured for this session'}, Boss. "
                    f"The active window is {window}."
                )
            else:
                reply = f"I couldn't capture the screen: {result.get('error', 'unknown capture error')}"
            return {
                "intent": "VISION_ACTION",
                "reply": reply,
                "executed_tool": "capture_screen",
                "details": result,
                "tasks": [],
                "verified": bool(result.get("verified", result.get("success"))),
                "timestamp": time.time(),
            }

        if any(p in lower for p in [
            "save that screenshot", "save this screenshot", "keep that screenshot",
            "keep this screenshot", "keep the screenshot", "save the screenshot"
        ]):
            result = self.unified_context.save_screenshot("latest")
            reply = (
                f"Saved it permanently, Boss: {result.get('saved_path')}"
                if result.get("success")
                else f"I couldn't save that screenshot: {result.get('error')}"
            )
            return {
                "intent": "VISION_ACTION",
                "reply": reply,
                "executed_tool": "save_screenshot",
                "details": result,
                "tasks": [],
                "verified": bool(result.get("verified")),
                "timestamp": time.time(),
            }

        if any(p in lower for p in ["compare this with before", "compare with before", "compare screenshots"]):
            result = self.unified_context.compare_screenshots("latest", "previous")
            if result.get("success"):
                reply = (
                    f"I compared the latest capture with the previous one, Boss. "
                    f"Pixel-level change is about {result.get('pixel_change_percent')}%. "
                    f"Active window changed: {'yes' if result.get('active_window_changed') else 'no'}."
                )
                if result.get("newer_errors") and not result.get("older_errors"):
                    reply += " A new visible error-window signal appeared in the latest capture."
            else:
                reply = f"I need two session screenshots to compare: {result.get('error')}"
            return {
                "intent": "VISION_COMPARE",
                "reply": reply,
                "executed_tool": "compare_screenshots",
                "details": result,
                "tasks": [],
                "verified": bool(result.get("verified")),
                "timestamp": time.time(),
            }

        screen_phrases = [
            "look at my screen", "check my screen", "what's on my screen",
            "what is on my screen", "what's this error", "what is this error",
            "read this page", "where should i click"
        ]
        if any(p in lower for p in screen_phrases):
            capture = self.unified_context.capture_screen(save=False)
            if not capture.get("success"):
                return {
                    "intent": "VISION_ANALYSIS",
                    "reply": f"I couldn't inspect the screen: {capture.get('error')}",
                    "details": capture,
                    "tasks": [],
                    "timestamp": time.time(),
                }
            window = ((capture.get("active_window") or {}).get("title") or "Desktop")
            errors = capture.get("visible_errors") or []
            if errors:
                error_text = "; ".join(str(e.get("description", "")) for e in errors[:3])
                reply = f"I'm looking at {window}, Boss. I detected: {error_text}"
            else:
                reply = f"I'm looking at {window}, Boss. I don't see an error signal in the visible window titles."

            if "read this page" in lower or "where should i click" in lower:
                reply += (
                    " The capture is in session context, but this local build does not yet have a general "
                    "visual-language/OCR model, so I won't invent page text or click targets I cannot actually read."
                )

            return {
                "intent": "VISION_ANALYSIS",
                "reply": reply,
                "executed_tool": "capture_screen",
                "details": capture,
                "tasks": [],
                "verified": True,
                "timestamp": time.time(),
            }

        if any(p in lower for p in ["what am i doing", "what's open", "what is open"]):
            snapshot = self.unified_context.snapshot(include_processes=False)
            title = snapshot.get("active_window_title") or "Desktop"
            recent = snapshot.get("recent_files") or []
            reply = f"You're currently focused on {title}, Boss."
            if recent:
                reply += " Your most recent local file is " + recent[0].get("name", "unknown") + "."
            return {
                "intent": "CONTEXT_QUERY",
                "reply": reply,
                "details": snapshot,
                "tasks": [],
                "verified": True,
                "timestamp": time.time(),
            }

        return None

    def is_fast_conversation(self, user_text: str) -> bool:
        """Return True only for ordinary conversation that does not map to an action/context command."""
        cleaned_query = (user_text or "").strip()
        if not cleaned_query or self._is_context_command(cleaned_query):
            return False
        intent_info = self.fallback_classifier.classify_and_extract(cleaned_query)
        return (
            not intent_info.get("tool")
            and intent_info.get("intent", "CHAT") in ["QUESTION", "SUGGESTION", "CHAT"]
        )

    def stream_conversation(self, user_text: str) -> Generator[Dict[str, Any], None, None]:
        """Stream ordinary conversation while keeping structured internal output hidden."""
        cleaned_query = (user_text or "").strip()
        if not cleaned_query:
            yield {"type": "error", "error": "Empty query"}
            return
        if not self.is_fast_conversation(cleaned_query):
            yield {"type": "error", "error": "Request is not eligible for conversational streaming"}
            return

        self.memory.add_message("user", cleaned_query)
        self.planner.emit("maya.state.changed", {"state": "THINKING"})
        ctx = self.context_builder.build_chat_context(cleaned_query)
        policy = self.personality.policy(
            cleaned_query,
            (ctx.get("context_metadata") or {}).get("live_context") or {}
        )

        started_at = time.perf_counter()
        first_token_at: Optional[float] = None
        raw_output = ""
        pending = ""
        output_mode: Optional[str] = None
        streamed_any = False

        try:
            for chunk in self.runtime.stream_generate(
                cleaned_query,
                system_prompt=ctx["prompt"],
                max_new_tokens=policy.max_new_tokens,
                temperature=policy.temperature,
                top_p=0.9,
            ):
                if not chunk:
                    continue
                raw_output += chunk

                if output_mode is None:
                    pending += chunk
                    probe = pending.lstrip()
                    if probe.startswith("{"):
                        output_mode = "buffer"
                        continue
                    if probe.startswith("`") and len(probe) < 3:
                        continue
                    if probe.startswith("```"):
                        output_mode = "buffer"
                        continue
                    output_mode = "stream"
                    if pending:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        streamed_any = True
                        yield {"type": "token", "delta": pending}
                        pending = ""
                    continue

                if output_mode == "stream":
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    streamed_any = True
                    yield {"type": "token", "delta": chunk}

            reply = self._extract_conversation_text(raw_output)
            if output_mode == "buffer" or not streamed_any:
                if reply:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    yield {"type": "token", "delta": reply}

            self.memory.add_message("maya", reply)
            finished_at = time.perf_counter()
            first_token_ms = (
                round((first_token_at - started_at) * 1000, 1)
                if first_token_at is not None
                else None
            )
            total_ms = round((finished_at - started_at) * 1000, 1)
            print(
                f"[MayaBrain] Streamed chat: first_token={first_token_ms}ms "
                f"total={total_ms}ms chars={len(reply)}"
            )
            yield {
                "type": "done",
                "result": {
                    "intent": "CHAT",
                    "reply": reply,
                    "executed_tool": None,
                    "tasks": [],
                    "fallback_used": False,
                    "fast_path": True,
                    "timing": {"first_token_ms": first_token_ms, "total_ms": total_ms},
                    "timestamp": time.time(),
                },
            }
        except Exception as e:
            print(f"[MayaBrain] Streaming chat generation error: {e}")
            reply = (
                self._extract_conversation_text(raw_output)
                if raw_output.strip()
                else "I hit a local model error while answering that."
            )
            if not streamed_any and reply:
                yield {"type": "token", "delta": reply}
            self.memory.add_message("maya", reply)
            yield {
                "type": "done",
                "result": {
                    "intent": "CHAT",
                    "reply": reply,
                    "executed_tool": None,
                    "tasks": [],
                    "fallback_used": False,
                    "fast_path": True,
                    "timestamp": time.time(),
                },
            }
        finally:
            self.planner.emit("maya.state.changed", {"state": "IDLE"})

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

        direct_context = self._handle_context_command(cleaned_query)
        if direct_context is not None:
            self.memory.add_message("user", cleaned_query)
            self.memory.add_message("maya", direct_context.get("reply", ""))
            return direct_context

        # 1. Store user message in episodic memory
        self.memory.add_message("user", cleaned_query)

        # Fast conversation path: do not scan the project/system for ordinary chat.
        intent_info = self.fallback_classifier.classify_and_extract(cleaned_query)
        detected_tool = intent_info.get("tool")
        intent = intent_info.get("intent", "CHAT")
        if not detected_tool and intent in ["QUESTION", "SUGGESTION", "CHAT"]:
            self.planner.emit("maya.state.changed", {"state": "THINKING"})
            ctx = self.context_builder.build_chat_context(cleaned_query)
            policy = self.personality.policy(
                cleaned_query,
                (ctx.get("context_metadata") or {}).get("live_context") or {}
            )
            try:
                raw_chat = self.runtime.generate(
                    cleaned_query,
                    system_prompt=ctx["prompt"],
                    max_new_tokens=policy.max_new_tokens,
                    temperature=policy.temperature,
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
            pending_step = plan_result.get("step", {}) or {}
            pending_tool = pending_step.get("tool")
            pending_args = pending_step.get("arguments", {}) or {}
            confirmation_reply = (
                f"This action requires your confirmation: "
                f"{pending_step.get('description', '')}"
            )

            if pending_tool == "send_communication":
                service = str(pending_args.get("service", "message")).title()
                recipient = pending_args.get("recipient", "")
                message = str(pending_args.get("message", ""))
                subject = str(pending_args.get("subject", "") or "")
                preview = message if len(message) <= 240 else message[:237] + "..."
                confirmation_reply = (
                    f"Ready to send via {service} to {recipient}.\n"
                    + (f"Subject: {subject}\n" if subject else "")
                    + f"Message: {preview}\n\n"
                    + "Authorize once to send exactly this."
                )

            return {
                "intent": "PERMISSION_REQUIRED",
                "reply": confirmation_reply,
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
                system_prompt=(
                    "You are MAYA, reporting verified execution results to your user. "
                    + self.personality.prompt_fragment(user_query)
                ),
                max_new_tokens=96,
                temperature=0.45,
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
