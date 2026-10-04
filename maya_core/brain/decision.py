"""
MAYA Structured Neural Decision Schema & Validation Engine
Parses and validates the 5 canonical structured neural decision types:
conversation, tool_call, plan, clarification, refusal.
Zero raw unchecked neural execution.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from maya_core.tools.registry import ToolRegistry, default_tool_registry

DECISION_TYPES = {"conversation", "tool_call", "plan", "clarification", "refusal"}

@dataclass
class NeuralPlanStep:
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    name: Optional[str] = None
    description: Optional[str] = None

@dataclass
class NeuralDecision:
    decision_type: str  # "conversation", "tool_call", "plan", "clarification", "refusal"
    message: Optional[str] = None
    intent: Optional[str] = None
    tool: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    goal: Optional[str] = None
    steps: List[NeuralPlanStep] = field(default_factory=list)
    reasoning: Optional[str] = None
    raw_output: str = ""
    is_valid: bool = True
    validation_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "type": self.decision_type,
            "is_valid": self.is_valid
        }
        if self.message:
            res["message"] = self.message
        if self.intent:
            res["intent"] = self.intent
        if self.tool:
            res["tool"] = self.tool
            res["arguments"] = self.arguments
            res["confidence"] = self.confidence
        if self.goal:
            res["goal"] = self.goal
            res["steps"] = [{"tool": s.tool, "arguments": s.arguments} for s in self.steps]
        if self.validation_error:
            res["validation_error"] = self.validation_error
        return res

def extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Extracts JSON object from text, handling markdown fences, leading/trailing prose."""
    if not text:
        return None
    cleaned = text.strip()

    # 1. Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. Try markdown fenced code block ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # 3. Try finding first '{' and matching last '}'
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx:end_idx + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None

def parse_and_validate_decision(
    raw_output: str,
    registry: Optional[ToolRegistry] = None
) -> NeuralDecision:
    """
    Parses neural model output into a strictly validated NeuralDecision.
    If output is conversational plain text without JSON, interprets as conversation.
    If JSON is present but invalid/unsupported, returns invalid decision with reason.
    """
    reg = registry or default_tool_registry
    raw_str = (raw_output or "").strip()

    parsed_json = extract_json_block(raw_str)

    # If no JSON block found, treat as direct conversational response
    if not parsed_json:
        return NeuralDecision(
            decision_type="conversation",
            message=raw_str,
            raw_output=raw_str,
            is_valid=True
        )

    # Validate decision type
    dec_type = parsed_json.get("type", "").lower().strip()
    if dec_type not in DECISION_TYPES:
        # Fallback check: does it have a "tool" field?
        if "tool" in parsed_json:
            dec_type = "tool_call"
        elif "steps" in parsed_json:
            dec_type = "plan"
        elif "message" in parsed_json:
            dec_type = "conversation"
        else:
            return NeuralDecision(
                decision_type="conversation",
                message=raw_str,
                raw_output=raw_str,
                is_valid=False,
                validation_error=f"Unrecognized decision type '{dec_type}'."
            )

    # 1. Conversation
    if dec_type == "conversation":
        msg = parsed_json.get("message", raw_str)
        return NeuralDecision(
            decision_type="conversation",
            message=str(msg),
            raw_output=raw_str,
            is_valid=True
        )

    # 2. Clarification
    if dec_type == "clarification":
        msg = parsed_json.get("message", "Could you please clarify what you would like me to do?")
        return NeuralDecision(
            decision_type="clarification",
            message=str(msg),
            raw_output=raw_str,
            is_valid=True
        )

    # 3. Refusal
    if dec_type == "refusal":
        msg = parsed_json.get("message", "I cannot execute this request due to safety policies.")
        return NeuralDecision(
            decision_type="refusal",
            message=str(msg),
            raw_output=raw_str,
            is_valid=True
        )

    # 4. Tool Call
    if dec_type == "tool_call":
        tool_name = parsed_json.get("tool")
        if not tool_name or not isinstance(tool_name, str):
            return NeuralDecision(
                decision_type="tool_call",
                raw_output=raw_str,
                is_valid=False,
                validation_error="Missing or invalid 'tool' name in tool_call."
            )

        tool_schema = reg.get(tool_name)
        if not tool_schema:
            return NeuralDecision(
                decision_type="tool_call",
                tool=tool_name,
                raw_output=raw_str,
                is_valid=False,
                validation_error=f"Tool '{tool_name}' does not exist in MAYA tool registry."
            )

        args = parsed_json.get("arguments", {})
        if not isinstance(args, dict):
            return NeuralDecision(
                decision_type="tool_call",
                tool=tool_name,
                raw_output=raw_str,
                is_valid=False,
                validation_error=f"Arguments for tool '{tool_name}' must be an object."
            )

        # Validate arguments against tool schema
        valid, err = tool_schema.validate_arguments(args)
        if not valid:
            return NeuralDecision(
                decision_type="tool_call",
                tool=tool_name,
                arguments=args,
                raw_output=raw_str,
                is_valid=False,
                validation_error=err
            )

        confidence = float(parsed_json.get("confidence", 1.0))
        intent = parsed_json.get("intent", "PC_ACTION")

        return NeuralDecision(
            decision_type="tool_call",
            tool=tool_name,
            arguments=args,
            intent=intent,
            confidence=confidence,
            message=parsed_json.get("message"),
            raw_output=raw_str,
            is_valid=True
        )

    # 5. Multi-Step Plan
    if dec_type == "plan":
        goal = parsed_json.get("goal", "Multi-step plan")
        raw_steps = parsed_json.get("steps", [])
        if not isinstance(raw_steps, list) or len(raw_steps) == 0:
            return NeuralDecision(
                decision_type="plan",
                goal=goal,
                raw_output=raw_str,
                is_valid=False,
                validation_error="Plan must contain a non-empty list of 'steps'."
            )

        validated_steps = []
        for idx, s in enumerate(raw_steps, 1):
            if not isinstance(s, dict) or "tool" not in s:
                return NeuralDecision(
                    decision_type="plan",
                    goal=goal,
                    raw_output=raw_str,
                    is_valid=False,
                    validation_error=f"Plan step {idx} must be an object with a 'tool' field."
                )

            s_tool = s["tool"]
            s_schema = reg.get(s_tool)
            if not s_schema:
                return NeuralDecision(
                    decision_type="plan",
                    goal=goal,
                    raw_output=raw_str,
                    is_valid=False,
                    validation_error=f"Step {idx} references unknown tool '{s_tool}'."
                )

            s_args = s.get("arguments", {})
            valid, err = s_schema.validate_arguments(s_args)
            if not valid:
                return NeuralDecision(
                    decision_type="plan",
                    goal=goal,
                    raw_output=raw_str,
                    is_valid=False,
                    validation_error=f"Step {idx} ({s_tool}) invalid arguments: {err}"
                )

            validated_steps.append(NeuralPlanStep(
                tool=s_tool,
                arguments=s_args,
                name=s.get("name", f"Step {idx}: {s_tool}"),
                description=s.get("description", "")
            ))

        return NeuralDecision(
            decision_type="plan",
            goal=goal,
            steps=validated_steps,
            message=parsed_json.get("message"),
            raw_output=raw_str,
            is_valid=True
        )

    return NeuralDecision(
        decision_type="conversation",
        message=raw_str,
        raw_output=raw_str,
        is_valid=True
    )
