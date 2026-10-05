"""Adaptive MAYA personality, mode, seriousness and response-depth policy."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from maya_core.config import settings


class MayaMode(str, Enum):
    NORMAL = "Normal"
    WORK = "Work"
    FOCUS = "Focus"
    PRESENTATION = "Presentation"
    SAVAGE = "Savage"


class ResponseDepth(str, Enum):
    QUICK = "Quick"
    NORMAL = "Normal"
    DETAILED = "Detailed"
    DEEP = "Deep Analysis"


@dataclass(frozen=True)
class PersonalityPolicy:
    mode: MayaMode
    depth: ResponseDepth
    severity: str
    humor_allowed: bool
    max_new_tokens: int
    temperature: float


class PersonalityEngine:
    MODE_ALIASES = {
        "normal": MayaMode.NORMAL,
        "work": MayaMode.WORK,
        "focus": MayaMode.FOCUS,
        "presentation": MayaMode.PRESENTATION,
        "professional": MayaMode.PRESENTATION,
        "savage": MayaMode.SAVAGE,
        "chaos": MayaMode.SAVAGE,
    }

    SERIOUS_TERMS = {
        "security", "malware", "virus", "ransomware", "breach", "password",
        "lost file", "deleted", "data loss", "corrupt", "fatal", "critical",
        "crash", "deadline", "urgent", "emergency", "payment", "money",
        "bank", "format", "wipe", "overheat", "90°", "90c"
    }

    DEEP_TERMS = {
        "analyze entire", "analyse entire", "full analysis", "deep analysis",
        "go deep", "thorough", "everything wrong", "review whole", "entire project",
        "each and every", "comprehensive"
    }

    DETAILED_TERMS = {
        "explain properly", "explain clearly", "detailed", "how does",
        "why does", "compare", "architecture", "debug", "analyze", "analyse"
    }

    QUICK_TERMS = {
        "short answer", "answer short", "in short", "briefly", "just tell me",
        "only result", "just the result", "quick answer"
    }

    def current_mode(self) -> MayaMode:
        raw = str(settings.get("maya_mode", MayaMode.NORMAL.value)).strip().lower()
        return self.MODE_ALIASES.get(raw, MayaMode.NORMAL)

    def set_mode(self, mode_text: str) -> MayaMode:
        mode = self.MODE_ALIASES.get((mode_text or "").strip().lower())
        if not mode:
            raise ValueError(f"Unknown MAYA mode: {mode_text}")
        settings.set("maya_mode", mode.value)
        return mode

    def parse_mode_command(self, text: str) -> Optional[MayaMode]:
        lower = (text or "").strip().lower()
        match = re.search(
            r"\b(?:maya[, ]+)?(?:switch\s+to\s+|enable\s+|enter\s+|go\s+)?"
            r"(normal|work|focus|presentation|professional|savage|chaos)\s+mode\b",
            lower,
        )
        if not match:
            return None
        return self.MODE_ALIASES.get(match.group(1))

    def severity(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        lower = (text or "").lower()
        if any(term in lower for term in self.SERIOUS_TERMS):
            return "HIGH"

        context = context or {}
        visible_errors = context.get("visible_errors") or []
        if any(str(item.get("severity", "")).upper() == "CRITICAL" for item in visible_errors if isinstance(item, dict)):
            return "HIGH"
        if visible_errors:
            return "MEDIUM"
        return "NORMAL"

    def response_depth(self, text: str, mode: Optional[MayaMode] = None) -> ResponseDepth:
        lower = (text or "").strip().lower()
        if any(term in lower for term in self.QUICK_TERMS):
            return ResponseDepth.QUICK
        if any(term in lower for term in self.DEEP_TERMS):
            return ResponseDepth.DEEP
        if any(term in lower for term in self.DETAILED_TERMS):
            return ResponseDepth.DETAILED

        words = len(lower.split())
        question_count = lower.count("?")
        mode = mode or self.current_mode()

        if mode == MayaMode.FOCUS:
            return ResponseDepth.QUICK
        if mode == MayaMode.WORK and (words > 18 or question_count > 1):
            return ResponseDepth.DETAILED
        if words <= 7 and question_count <= 1:
            return ResponseDepth.QUICK
        if words > 35 or question_count > 2:
            return ResponseDepth.DETAILED
        return ResponseDepth.NORMAL

    def policy(self, text: str, context: Optional[Dict[str, Any]] = None) -> PersonalityPolicy:
        mode = self.current_mode()
        severity = self.severity(text, context)
        depth = self.response_depth(text, mode)

        humor_allowed = severity not in {"HIGH", "CRITICAL"} and mode != MayaMode.PRESENTATION
        if mode == MayaMode.FOCUS:
            humor_allowed = False

        max_tokens = {
            ResponseDepth.QUICK: 64,
            ResponseDepth.NORMAL: 128,
            ResponseDepth.DETAILED: 320,
            ResponseDepth.DEEP: 640,
        }[depth]

        temperature = 0.55
        if mode == MayaMode.SAVAGE and humor_allowed:
            temperature = 0.72
        elif mode == MayaMode.PRESENTATION:
            temperature = 0.35

        return PersonalityPolicy(
            mode=mode,
            depth=depth,
            severity=severity,
            humor_allowed=humor_allowed,
            max_new_tokens=max_tokens,
            temperature=temperature,
        )

    def contextual_humor_cues(self, context: Optional[Dict[str, Any]]) -> list[str]:
        """Derive humor opportunities only from real observed session state."""
        context = context or {}
        cues: list[str] = []

        battery = context.get("battery") or {}
        try:
            battery_percent = float(battery.get("percent"))
        except (TypeError, ValueError):
            battery_percent = None
        if battery_percent is not None and battery_percent <= 5 and not battery.get("plugged"):
            cues.append(f"Battery is genuinely low at {battery_percent:.0f}%.")

        recent_actions = context.get("recent_actions") or []
        statuses = [str(a.get("status", "")).lower() for a in recent_actions if isinstance(a, dict)]
        failed_count = statuses.count("failed")
        if failed_count >= 2:
            cues.append(f"There have been {failed_count} recent failed actions.")
        if statuses and statuses[0] == "success" and "failed" in statuses[1:]:
            cues.append("A recent action succeeded after earlier failures.")

        active_title = str(context.get("active_window_title") or "").lower()
        if "chrome" in active_title:
            cues.append("Chrome is the active application.")

        return cues

    def prompt_fragment(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        p = self.policy(text, context)
        mode_rules = {
            MayaMode.NORMAL: "Natural everyday assistant behavior; balanced detail and occasional dry humor.",
            MayaMode.WORK: "Technical and task-focused; deeper reasoning, low distraction, restrained humor.",
            MayaMode.FOCUS: "Extremely concise; no jokes, no filler, only information needed for the next action.",
            MayaMode.PRESENTATION: "Professional and polished; no sarcasm, slang, or private-style banter.",
            MayaMode.SAVAGE: "Witty and more sarcastic when safe, but never insulting, cruel, or distracting from correctness.",
        }

        humor_rule = (
            "Contextual humor is allowed sparingly when it naturally fits the event. Do not force a joke."
            if p.humor_allowed
            else "Do not use humor for this response; be direct and serious."
        )

        depth_rule = {
            ResponseDepth.QUICK: "Answer briefly: usually 1-3 compact sentences unless safety requires more.",
            ResponseDepth.NORMAL: "Use a normal conversational answer with enough explanation to be useful.",
            ResponseDepth.DETAILED: "Give a structured, detailed explanation with important reasoning and steps.",
            ResponseDepth.DEEP: "Provide a thorough analysis with structure, trade-offs, failure cases, and concrete next steps.",
        }[p.depth]

        cues = self.contextual_humor_cues(context)
        cue_text = ""
        if cues:
            cue_text = (
                "- Real contextual event cues: " + " ".join(cues) + "\n"
                "- If humor is allowed, MAYA may make at most one brief joke tied to a real cue; never invent a cue.\n"
            )

        return (
            "\nMAYA PERSONALITY POLICY:\n"
            "- Address the user as 'Boss' naturally and occasionally, not in every sentence.\n"
            "- Personality: intelligent, calm, loyal, conversational, slightly sarcastic when appropriate.\n"
            f"- Mode: {p.mode.value}. {mode_rules[p.mode]}\n"
            f"- Situation severity: {p.severity}. {humor_rule}\n"
            f"- Response depth: {p.depth.value}. {depth_rule}\n"
            + cue_text
            + "- Never let personality override truthfulness, permissions, or action verification.\n"
        )

    def describe_mode(self, mode: MayaMode) -> str:
        descriptions = {
            MayaMode.NORMAL: "Normal mode: balanced answers, natural conversation and occasional humor.",
            MayaMode.WORK: "Work mode: deeper technical answers, fewer distractions and restrained humor.",
            MayaMode.FOCUS: "Focus mode: short answers, no jokes and only the next useful information.",
            MayaMode.PRESENTATION: "Presentation mode: polished professional language with no sarcasm.",
            MayaMode.SAVAGE: "Savage mode: stronger contextual sarcasm while keeping facts and safety intact.",
        }
        return descriptions[mode]
