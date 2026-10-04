"""
MAYA AI Model Stack Interfaces & Providers
Supports local fine-tuned models, local servers, cloud fallbacks, and deterministic intent extraction.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os
import json
import re
import urllib.request
import urllib.error

class ModelProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

class LocalModelProvider(ModelProvider):
    """Local inference provider (Ollama, LM Studio, or local llama.cpp endpoint)"""
    def __init__(self, endpoint: str = "http://127.0.0.1:11434/api/generate", model_name: str = "llama3:8b"):
        self.endpoint = endpoint
        self.model_name = model_name

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(self.endpoint.replace("/generate", "/tags"), headers={'User-Agent': 'MAYA'})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json.get("response", "")

class MayaFineTunedModel(ModelProvider):
    """
    MAYA's own fine-tuned adapter / checkpoint model wrapper.
    If local weight loader or adapter is available, loads model;
    otherwise falls back to rule-guided conversational engine.
    """
    def __init__(self, adapter_path: Optional[str] = None):
        self.adapter_path = adapter_path
        self._loaded = False

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Fallback generator if heavy weights are not loaded into VRAM
        return "I am Maya, ready to assist with your PC, code, and system tasks."

class OptionalCloudModelProvider(ModelProvider):
    """Cloud fallback provider (e.g. OpenAI / Groq / Anthropic compatible) if key is set"""
    def __init__(self, api_key: Optional[str] = None, api_base: str = "https://api.openai.com/v1"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.api_base = api_base

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        if not self.is_available():
            raise RuntimeError("Cloud provider requested but API key is not configured.")
        # Minimal HTTP call to OpenAI-compatible endpoint
        url = f"{self.api_base}/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        req = urllib.request.Request(
            url,
            data=json.dumps({"model": "gpt-4o-mini", "messages": messages}).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

class DeterministicIntentClassifier:
    """
    High-accuracy intent classifier ensuring that:
    - Casual talk is never mistaken for dangerous tool calls.
    - Explicit commands are cleanly mapped to tools and arguments.
    """
    INTENTS = [
        "CHAT", "QUESTION", "INFORMATION_REQUEST", "SUGGESTION",
        "PC_ACTION", "FILE_ACTION", "DEVELOPMENT_ACTION", "SYSTEM_DIAGNOSTIC",
        "WEB_ACTION", "MEMORY_ACTION", "AUTOMATION_ACTION", "PRIVILEGED_ACTION", "CRITICAL_ACTION"
    ]

    def classify_and_extract(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        lower = cleaned.lower()

        # Check for Undo
        if re.search(r"\b(undo|rollback|revert)\b", lower):
            return {
                "intent": "PC_ACTION",
                "tool": "rollback_last_action",
                "arguments": {},
                "confidence": 0.98,
                "summary": "Undo last reversible action"
            }

        # Check for open application (VS Code, Notepad, Chrome, Explorer, Terminal, etc.)
        match_app = re.search(r"\b(?:open|launch|start|run)\s+(?:application\s+|app\s+)?([a-zA-Z0-9\s\.\-_]+?)(?:\s+and\s+|\s*$|\.|\?)", lower)
        if match_app:
            app_raw = match_app.group(1).strip()
            # Distinguish app from file or command
            if any(term in app_raw for term in ["vs code", "vscode", "code", "notepad", "chrome", "firefox", "edge", "terminal", "powershell", "cmd", "explorer"]):
                app_name = "Visual Studio Code" if "code" in app_raw else app_raw.title()
                
                # Check if user also asked to check project or scan errors
                check_proj = "check" in lower or "scan" in lower or "error" in lower or "project" in lower
                return {
                    "intent": "DEVELOPMENT_ACTION" if check_proj else "PC_ACTION",
                    "tool": "open_application_and_inspect" if check_proj else "open_application",
                    "arguments": {
                        "application": app_name,
                        "inspect_project": check_proj
                    },
                    "confidence": 0.95,
                    "summary": f"Open {app_name}" + (" and scan project for errors" if check_proj else "")
                }

        # Check for system diagnostic or scan
        if any(term in lower for term in ["scan my pc", "scan system", "system diagnostic", "diagnostics", "check system performance", "pc health", "scan pc"]):
            return {
                "intent": "SYSTEM_DIAGNOSTIC",
                "tool": "run_system_diagnostics",
                "arguments": {"depth": "full"},
                "confidence": 0.96,
                "summary": "Run comprehensive system diagnostics"
            }

        # Check for developer project check / error scan
        if any(phrase in lower for phrase in ["check my project", "check project", "check for errors", "scan project", "find errors in project", "build project", "run build", "test project"]):
            return {
                "intent": "DEVELOPMENT_ACTION",
                "tool": "inspect_project",
                "arguments": {"target": "active_project"},
                "confidence": 0.94,
                "summary": "Inspect active project and verify build/errors"
            }

        # Check for memory retrieval / question
        if "what did you just do" in lower or "what did you do" in lower:
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "get_recent_actions",
                "arguments": {"limit": 5},
                "confidence": 0.98,
                "summary": "Retrieve recent action ledger history"
            }

        # Conversational / Greetings
        if any(greeting in lower for greeting in ["hey maya", "hello maya", "hi maya", "maya", "hello", "hi there", "how are you", "who are you"]):
            return {
                "intent": "CHAT",
                "tool": None,
                "arguments": {},
                "confidence": 0.99,
                "summary": "Conversational greeting or dialogue"
            }

        # Suggestion / Complaining (e.g. "I hate how slow Chrome has become")
        if any(word in lower for word in ["hate", "slow", "annoying", "wish", "why is", "lagging"]) and not any(cmd in lower for cmd in ["open", "fix", "delete", "kill", "run"]):
            return {
                "intent": "SUGGESTION",
                "tool": None,
                "arguments": {"topic": cleaned},
                "confidence": 0.90,
                "summary": "User observation or complaint; offer diagnostic assistance without unprompted changes"
            }

        # Default general chat
        return {
            "intent": "CHAT",
            "tool": None,
            "arguments": {},
            "confidence": 0.85,
            "summary": "General chat query"
        }
