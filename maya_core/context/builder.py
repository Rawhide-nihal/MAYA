"""
MAYA Context Builder
Assembles budgeted, relevance-ranked contextual prompts combining personality,
working memory, active project, active window, recent actions, and retrieved memories.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
from maya_core.personality.spec import MAYA_SYSTEM_PROMPT
from memory.store import MemoryStore
from security.audit.ledger import ActionLedger
from agents.windows.agent import WindowsAgent
from agents.developer.agent import DeveloperAgent
from maya_core.personality.engine import PersonalityEngine

class ContextBuilder:
    def __init__(
        self,
        memory: MemoryStore,
        ledger: ActionLedger,
        windows: WindowsAgent,
        developer: DeveloperAgent,
        max_context_chars: int = 6000,
        unified_context=None,
        personality: Optional[PersonalityEngine] = None
    ):
        self.memory = memory
        self.ledger = ledger
        self.windows = windows
        self.developer = developer
        self.max_context_chars = max_context_chars
        self.unified_context = unified_context
        self.personality = personality or PersonalityEngine()

    def build_chat_context(self, user_query: str) -> Dict[str, Any]:
        """Builds lightweight context for ordinary conversation without scanning the PC."""
        relevant_mems = self.memory.search_relevant_memories(user_query, top_k=2)
        history = self.memory.get_conversation_history(limit=7)
        # process_request stores the current user message before building context;
        # exclude that same message so it is not sent to the model twice.
        if history and history[-1].get("role") == "user" and history[-1].get("message", "").strip() == user_query.strip():
            history = history[:-1]
        formatted_history = [
            f"{h['role'].upper()}: {h['message']}"
            for h in history[-4:]
        ]

        live_context = {}
        if self.unified_context is not None:
            try:
                live_context = self.unified_context.snapshot(include_processes=False)
            except Exception:
                live_context = {}

        prompt_parts = [MAYA_SYSTEM_PROMPT]
        prompt_parts.append(self.personality.prompt_fragment(user_query, live_context))
        if self.unified_context is not None:
            try:
                prompt_parts.append(self.unified_context.prompt_fragment())
            except Exception:
                pass
        if relevant_mems:
            prompt_parts.append("\nRELEVANT MEMORY:")
            prompt_parts.extend(f"- {m}" for m in relevant_mems)
        if formatted_history:
            prompt_parts.append("\nRECENT CONVERSATION:")
            prompt_parts.extend(formatted_history)

        full_prompt = "\n".join(prompt_parts)
        if len(full_prompt) > 3500:
            head = "\n".join(prompt_parts[:2])
            remaining = max(0, 3500 - len(head) - 2)
            full_prompt = head + "\n" + full_prompt[-remaining:]

        return {
            "prompt": full_prompt,
            "context_metadata": {
                "mode": "conversation",
                "relevant_memories": relevant_mems,
                "conversation_history": formatted_history,
                "live_context": live_context,
                "personality_mode": self.personality.current_mode().value,
                "response_depth": self.personality.response_depth(user_query).value,
            },
        }

    def build_context(self, user_query: str) -> Dict[str, Any]:
        """Gathers full agent context only for operational/tool requests."""
        # 1. Active project details
        proj_details = self.developer.detect_project_details()

        # 2. System summary
        sys_summary = self.windows.get_system_summary()

        # 3. Recent Action Ledger history (last 3)
        recent_acts = self.ledger.get_recent_actions(limit=3)
        recent_action_summaries = [f"{a['summary']} ({a['status']})" for a in recent_acts]

        # 4. Semantic memory retrieval
        relevant_mems = self.memory.search_relevant_memories(user_query, top_k=3)

        # 5. Recent conversation turns
        history = self.memory.get_conversation_history(limit=7)
        if history and history[-1].get("role") == "user" and history[-1].get("message", "").strip() == user_query.strip():
            history = history[:-1]
        formatted_history = []
        for h in history[-6:]:
            formatted_history.append(f"{h['role'].upper()}: {h['message']}")

        # 6. Working memory context
        last_error = self.memory.get_working_memory("last_error", None)

        live_context = {}
        if self.unified_context is not None:
            try:
                live_context = self.unified_context.snapshot(include_processes=True)
            except Exception:
                live_context = {}

        context_data = {
            "active_project": proj_details.get("project_name", "None"),
            "active_project_path": proj_details.get("project_path", ""),
            "project_language": ", ".join(proj_details.get("languages", [])),
            "system_cpu": f"{sys_summary.get('cpu_percent', 0)}%",
            "system_ram": f"{sys_summary.get('ram_percent', 0)}%",
            "recent_actions": recent_action_summaries,
            "relevant_memories": relevant_mems,
            "conversation_history": formatted_history,
            "last_error": last_error,
            "live_context": live_context
        }

        # 7. Format into prompt string with budget

        prompt_parts = [MAYA_SYSTEM_PROMPT]
        prompt_parts.append(self.personality.prompt_fragment(user_query, live_context))
        if self.unified_context is not None:
            try:
                prompt_parts.append(self.unified_context.prompt_fragment())
            except Exception:
                pass
        prompt_parts.append("\nACTIVE WORKSPACE CONTEXT:")
        prompt_parts.append(f"- Project: {context_data['active_project']} ({context_data['project_language']})")
        if context_data["recent_actions"]:
            prompt_parts.append(f"- Recent Actions: {'; '.join(context_data['recent_actions'])}")
        if context_data["relevant_memories"]:
            prompt_parts.append(f"- Memories: {'; '.join(context_data['relevant_memories'])}")
        if last_error:
            prompt_parts.append(f"- Active Context Error: {last_error}")

        if formatted_history:
            prompt_parts.append("\nRECENT CONVERSATION:")
            for turn in formatted_history[-4:]:
                prompt_parts.append(turn)

        # The user message is passed separately to the model runtime. Do not duplicate it here.
        full_prompt = "\n".join(prompt_parts)

        # Budget trimming if needed
        if len(full_prompt) > self.max_context_chars:
            # Preserve system/personality instructions while trimming older context.
            head = "\n".join(prompt_parts[:2])
            remaining = max(0, self.max_context_chars - len(head) - 2)
            full_prompt = head + "\n" + full_prompt[-remaining:]

        return {
            "prompt": full_prompt,
            "context_metadata": context_data
        }
