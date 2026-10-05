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
from maya_core.brain.decision import parse_and_validate_decision, NeuralDecision, NeuralPlanStep
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

    def _reference_to_path(self, reference: str) -> Optional[str]:
        if self.unified_context is None:
            return None
        entity = self.unified_context.resolve_reference(reference)
        if not entity:
            return None

        value = entity.get("value")
        kind = entity.get("kind")

        if kind == "file" and isinstance(value, str):
            return value

        if isinstance(value, dict):
            for key in ("saved_path", "filepath", "path"):
                candidate = value.get(key)
                if candidate:
                    return str(candidate)

        if isinstance(value, str):
            return value
        return None

    def _resolve_argument_references(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve file/screenshot pronouns in tool arguments against session context."""
        if self.unified_context is None or not isinstance(arguments, dict):
            return arguments

        reference_values = {
            "this", "that", "it", "this file", "that file", "the file",
            "latest file", "this document", "that document", "the document",
            "latest attachment", "this attachment", "that attachment",
            "this screenshot", "that screenshot", "the screenshot",
            "latest screenshot", "previous screenshot", "before"
        }
        path_keys = {
            "filepath", "path", "source", "attachment_path",
            "project_path", "directory", "target"
        }

        resolved = dict(arguments)
        for key, value in list(resolved.items()):
            if key not in path_keys or not isinstance(value, str):
                continue
            normalized = value.strip().lower()
            if normalized not in reference_values and "screenshot" not in normalized:
                continue
            path = self._reference_to_path(value)
            if path:
                resolved[key] = path
        return resolved

    def _resolve_decision_references(self, decision: NeuralDecision) -> NeuralDecision:
        if self.unified_context is None:
            return decision

        if decision.decision_type == "tool_call":
            decision.arguments = self._resolve_argument_references(decision.arguments or {})
        elif decision.decision_type == "plan":
            for step in decision.steps:
                step.arguments = self._resolve_argument_references(step.arguments or {})
        return decision

    def _compound_fallback_decision(self, user_text: str) -> Optional[NeuralDecision]:
        """Build a conservative multi-step fallback for explicit compound commands."""
        cleaned = (user_text or "").strip()
        lower = cleaned.lower()

        # Split obvious sequential clauses while keeping punctuation-independent commands.
        clauses = [
            c.strip(" ,.;")
            for c in __import__("re").split(r"\b(?:then|after that|next)\b|[,;]+|\band\b", cleaned, flags=__import__("re").IGNORECASE)
            if c.strip(" ,.;")
        ]

        steps: List[NeuralPlanStep] = []
        seen = set()

        def add(tool: str, arguments: Dict[str, Any], description: str):
            key = (tool, json.dumps(arguments, sort_keys=True, default=str))
            if key in seen:
                return
            schema = self.tool_registry.get(tool)
            if not schema:
                return
            valid, _ = schema.validate_arguments(arguments)
            if not valid:
                return
            seen.add(key)
            steps.append(NeuralPlanStep(
                tool=tool,
                arguments=arguments,
                name=description,
                description=description
            ))

        for clause in clauses:
            c_lower = clause.lower()

            if "screenshot" in c_lower or "capture screen" in c_lower:
                add("capture_screen", {}, "Capture the current screen")
                continue

            if (
                ("open" in c_lower and "project" in c_lower and "folder" in c_lower)
                or "open project folder" in c_lower
            ):
                project_path = getattr(self.context_builder.developer, "active_project_path", None)
                args = {"application": "Explorer"}
                if project_path:
                    args["path"] = str(project_path)
                add("open_application", args, "Open the active project folder")
                continue

            if any(term in c_lower for term in [
                "find where this error", "find where the error", "check project",
                "inspect project", "find the error", "scan project", "what should i change"
            ]):
                add("inspect_project", {"target": "active_project"}, "Inspect the active project for the error")
                continue

            classified = self.fallback_classifier.classify_and_extract(clause)
            tool = classified.get("tool")
            if tool:
                add(
                    tool,
                    classified.get("arguments", {}) or {},
                    classified.get("summary", f"Execute {tool}")
                )

        # Whole-query hints cover clauses the simple splitter may phrase awkwardly.
        if "screenshot" in lower:
            add("capture_screen", {}, "Capture the current screen")
        if "project" in lower and any(term in lower for term in ["error", "wrong", "issue", "inspect", "check"]):
            add("inspect_project", {"target": "active_project"}, "Inspect the active project")

        if len(steps) < 2:
            return None

        return NeuralDecision(
            decision_type="plan",
            goal=cleaned,
            steps=steps,
            confidence=0.92,
            reasoning="Deterministic compound-command fallback"
        )

    def _has_multiple_operational_actions(self, user_text: str) -> bool:
        return self._compound_fallback_decision(user_text) is not None

    def _is_context_command(self, user_text: str) -> bool:
        lower = (user_text or "").strip().lower()
        if self.personality.parse_mode_command(lower):
            return True
        patterns = [
            "take a screenshot", "take screenshot", "capture screenshot",
            "save that screenshot", "save this screenshot", "keep that screenshot",
            "keep this screenshot", "compare this with before", "compare with before",
            "compare screenshots", "compare this with the screenshot", "compare screenshot",
            "verify the screenshot", "verify this screenshot", "verify that screenshot",
            "look at my screen", "check my screen", "look at this", "look at that",
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

        # Compound commands belong to the planner, not the one-shot context handler.
        if self._has_multiple_operational_actions(cleaned):
            return None

        if self.unified_context is None:
            return None

        if any(p in lower for p in ["take a screenshot", "take screenshot", "capture screenshot"]):
            should_save = any(p in lower for p in ["keep it", "save it", "keep this", "save this"])
            label = None
            import re as _re
            label_match = _re.search(r"\b(?:label it|call it)\s+(.+)$", cleaned, flags=_re.IGNORECASE)
            if label_match:
                label = label_match.group(1).strip(" .")
            else:
                before_match = _re.search(r"\bbefore\s+([a-zA-Z0-9 _-]{2,60})$", cleaned, flags=_re.IGNORECASE)
                if before_match:
                    label = "before " + before_match.group(1).strip(" .")
            result = self.unified_context.capture_screen(label=label, save=should_save)
            if result.get("success"):
                window = ((result.get("active_window") or {}).get("title") or "the current desktop")
                reply = (
                    f"Screenshot saved, Boss: {result.get('saved_path') or result.get('filepath')}. "
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

        if any(p in lower for p in [
            "verify the screenshot", "verify this screenshot", "verify that screenshot"
        ]):
            record = self.unified_context._find_screenshot("latest")
            if not record:
                return {
                    "intent": "VISION_ANALYSIS",
                    "reply": "I don't have a session screenshot to verify yet, Boss.",
                    "tasks": [],
                    "verified": False,
                    "timestamp": time.time(),
                }

            ocr = record.get("ocr") or {}
            errors = record.get("visible_errors") or []
            payload = {
                "screenshot_id": record.get("id"),
                "captured_at": record.get("timestamp"),
                "active_window": record.get("active_window"),
                "ocr_text": str(ocr.get("text") or "")[:12000],
                "visible_errors": errors[:20],
            }
            policy = self.personality.policy(cleaned, {"visible_errors": errors})
            if payload["ocr_text"] or errors:
                try:
                    raw = self.runtime.generate(
                        (
                            "Verify and summarize this EXACT previously captured screenshot using only "
                            "the grounded OCR/window/error metadata below. Do not claim the current screen "
                            "still looks the same.\n" + json.dumps(payload, default=str)
                        ),
                        system_prompt=(
                            "You are MAYA verifying a stored screenshot. "
                            + self.personality.prompt_fragment(cleaned, {"visible_errors": errors})
                        ),
                        max_new_tokens=min(policy.max_new_tokens, 256),
                        temperature=0.25,
                        top_p=0.9,
                    )
                    reply = self._extract_conversation_text(raw)
                except Exception:
                    reply = ""
            else:
                reply = ""

            if not reply:
                title = ((record.get("active_window") or {}).get("title") or "unknown window")
                reply = (
                    f"I verified the stored capture from {title}, Boss. "
                    "It has no readable OCR/error metadata, so I won't invent details beyond the saved image."
                )

            return {
                "intent": "VISION_ANALYSIS",
                "reply": reply,
                "executed_tool": "verify_screenshot",
                "details": payload,
                "tasks": [],
                "verified": True,
                "timestamp": time.time(),
            }

        if (
            any(p in lower for p in ["compare this with before", "compare with before", "compare screenshots"])
            or ("compare" in lower and "screenshot" in lower)
        ):
            older_ref = "previous"
            import re as _re
            with_match = _re.search(r"\bwith\s+(?:the\s+)?(.+)$", cleaned, flags=_re.IGNORECASE)
            if with_match:
                older_ref = with_match.group(1).strip(" .")
            result = self.unified_context.compare_screenshots("latest", older_ref)
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

        if any(p in lower for p in ["look at this", "look at that"]):
            current_ref = self.unified_context.resolve_reference("this")
            if current_ref and current_ref.get("kind") == "attachment":
                return None

        screen_phrases = [
            "look at my screen", "check my screen", "look at this", "look at that",
            "what's on my screen", "what is on my screen", "what's this error", "what is this error",
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

            ui_context = {}
            try:
                ui_context = self.context_builder.windows.get_ui_context(max_controls=120)
            except Exception:
                ui_context = {}

            window = (
                ui_context.get("window_title")
                or ((capture.get("active_window") or {}).get("title"))
                or "Desktop"
            )
            errors = capture.get("visible_errors") or []
            controls = ui_context.get("controls") or []

            # Keep only real accessibility data exposed by the foreground app.
            visible_controls = [
                c for c in controls
                if c.get("visible", True) and (c.get("name") or c.get("control_type"))
            ][:120]
            error_controls = [
                c for c in visible_controls
                if any(term in str(c.get("name", "")).lower() for term in [
                    "error", "exception", "failed", "failure", "fatal",
                    "warning", "traceback", "not responding"
                ])
            ]

            ocr = capture.get("ocr") or {}
            ocr_text = str(ocr.get("text") or "").strip()
            factual_payload = {
                "window_title": window,
                "window_title_errors": errors[:5],
                "accessibility_available": bool(ui_context.get("success")),
                "controls": visible_controls,
                "error_related_controls": error_controls[:20],
                "ocr_available": bool(ocr.get("success")),
                "ocr_text": ocr_text[:12000],
                "ocr_lines": (ocr.get("lines") or [])[:120],
            }

            if (ui_context.get("success") and visible_controls) or ocr_text:
                policy = self.personality.policy(cleaned, {"visible_errors": errors})
                analysis_prompt = (
                    "The user asked: " + cleaned + "\n"
                    "You are given ONLY grounded Windows accessibility/UI Automation data and Windows OCR text from the foreground app. "
                    "Use only controls/text actually present below. Do not invent page text, buttons, errors, or click targets. "
                    "If asked where to click, prefer an exact accessible control and its bounds; if only OCR is available, "
                    "you may reference OCR word bounds but must say it came from OCR. "
                    "If asked to read/summarize, summarize only the exposed accessible/OCR text. "
                    "If the grounded data is insufficient, say so clearly.\n"
                    "UI DATA:\n" + json.dumps(factual_payload, default=str)[:16000]
                )
                try:
                    reply = self.runtime.generate(
                        analysis_prompt,
                        system_prompt=(
                            "You are MAYA performing grounded screen/UI analysis. "
                            + self.personality.prompt_fragment(cleaned, {"visible_errors": errors})
                        ),
                        max_new_tokens=min(policy.max_new_tokens, 320),
                        temperature=0.25,
                        top_p=0.9,
                    ).strip()
                    reply = self._extract_conversation_text(reply)
                except Exception as exc:
                    print(f"[MayaBrain] UI analysis generation error: {exc}")
                    reply = ""

                if not reply:
                    if error_controls:
                        names = ", ".join(str(c.get("name")) for c in error_controls[:5] if c.get("name"))
                        reply = f"I'm looking at {window}, Boss. The accessibility tree exposes error-related UI: {names}."
                    elif ocr_text:
                        preview = " ".join(ocr_text.split())[:500]
                        reply = f"I'm looking at {window}, Boss. Windows OCR reads: {preview}"
                    else:
                        reply = (
                            f"I'm looking at {window}, Boss. I can read {len(visible_controls)} accessible UI controls, "
                            "but I couldn't synthesize a reliable interpretation."
                        )
            else:
                if errors:
                    error_text = "; ".join(str(e.get("description", "")) for e in errors[:3])
                    reply = f"I'm looking at {window}, Boss. I detected: {error_text}"
                else:
                    reply = (
                        f"I'm looking at {window}, Boss. The screenshot is captured, but neither UI Automation nor "
                        "Windows OCR exposed enough readable data, so I won't guess what the pixels say."
                    )

            details = {
                "capture": capture,
                "ui_context": ui_context,
                "grounding": "Windows UI Automation + captured screen metadata"
            }
            self.unified_context.remember_entity(
                "screen_analysis",
                details,
                label="latest screen analysis"
            )
            return {
                "intent": "VISION_ANALYSIS",
                "reply": reply,
                "executed_tool": "analyze_screen",
                "details": details,
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
        compound_fallback = self._compound_fallback_decision(cleaned_query)
        if not detected_tool and compound_fallback is None and intent in ["QUESTION", "SUGGESTION", "CHAT"]:
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

        if (
            not decision
            or not getattr(decision, "is_valid", True)
            or (decision.decision_type == "conversation" and (detected_tool or compound_fallback is not None))
        ):
            fallback_used = True
            print(f"[MayaBrain] Triggering deterministic safety fallback for: '{cleaned_query}'")
            intent = intent_info.get("intent", "CHAT")

            if compound_fallback is not None:
                decision = compound_fallback
            elif detected_tool:
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

        decision = self._resolve_decision_references(decision)

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
                attachment_path = str(pending_args.get("attachment_path", "") or "")
                attachment_line = ""
                if attachment_path:
                    normalized_attachment = attachment_path.replace("\\", "/")
                    attachment_name = normalized_attachment.rsplit("/", 1)[-1]
                    attachment_line = f"Attachment: {attachment_name}\n"

                confirmation_reply = (
                    f"Ready to send via {service} to {recipient}.\n"
                    + (f"Subject: {subject}\n" if subject else "")
                    + attachment_line
                    + (f"Message: {preview}\n" if preview else "")
                    + "\nAuthorize once to send exactly this."
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
            f"Synthesize a natural grounded response at the response depth requested by the personality policy. "
            f"For simple actions, stay concise; for explicit detailed/deep-analysis requests, explain the verified findings. "
            f"Be factual, direct, and conversational. Do not mention JSON or execution data structures."
        )

        try:
            synth_policy = self.personality.policy(user_query)
            synth_reply = self.runtime.generate(
                prompt=synth_prompt,
                system_prompt=(
                    "You are MAYA, reporting verified execution results to your user. "
                    + self.personality.prompt_fragment(user_query)
                ),
                max_new_tokens=min(synth_policy.max_new_tokens, 384),
                temperature=min(synth_policy.temperature, 0.55),
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
