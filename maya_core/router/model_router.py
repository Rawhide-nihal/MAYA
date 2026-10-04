"""
MAYA Model Router
Routes requests to the optimal model provider based on task complexity, privacy mode, and resource availability.
"""
from typing import Dict, Any, Optional
from maya_core.models.base import (
    ModelProvider,
    LocalModelProvider,
    MayaFineTunedModel,
    OptionalCloudModelProvider,
    DeterministicIntentClassifier
)

class ModelRouter:
    def __init__(self):
        self.intent_classifier = DeterministicIntentClassifier()
        self.local_provider = LocalModelProvider()
        self.maya_model = MayaFineTunedModel()
        self.cloud_provider = OptionalCloudModelProvider()
        self.offline_only = True  # Default to offline-first privacy

    def set_offline_mode(self, offline: bool) -> None:
        self.offline_only = offline

    def route_intent(self, text: str) -> Dict[str, Any]:
        """Sub-millisecond intent extraction before any tool execution"""
        return self.intent_classifier.classify_and_extract(text)

    def generate_response(self, prompt: str, system_prompt: Optional[str] = None, task_type: str = "chat") -> str:
        # 1. Try local fine-tuned / local server if available
        if self.local_provider.is_available():
            try:
                return self.local_provider.generate(prompt, system_prompt)
            except Exception:
                pass

        # 2. Try cloud if permitted and configured
        if not self.offline_only and self.cloud_provider.is_available():
            try:
                return self.cloud_provider.generate(prompt, system_prompt)
            except Exception:
                pass

        # 3. Use Maya's integrated conversational generator
        return self._generate_conversational_reply(prompt)

    def _generate_conversational_reply(self, prompt: str) -> str:
        lower = prompt.lower()
        if "hey maya" in lower or "hello" in lower or "hi" in lower:
            return "Hey there! How can I help you with your PC or projects today?"
        if "how are you" in lower:
            return "I'm running smoothly and all systems are nominal. What are we working on?"
        if "hate how slow" in lower or "chrome is slow" in lower:
            return "Want me to check what is making Chrome slow? I can inspect memory usage and background processes."
        if "who are you" in lower:
            return "I'm Maya, your personal AI desktop companion. I assist with PC control, development diagnostics, system performance, and your ongoing projects."
        return "I understand. Let me know if you'd like me to run diagnostics, inspect your workspace, or assist with anything on your PC."
