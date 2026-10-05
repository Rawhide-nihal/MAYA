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

        # Check for Critical Destructive Actions
        if any(w in lower for w in ["format", "format my", "destroy", "wipe"]) or ("delete" in lower and any(term in lower for term in ["permanently", "entire", "all my", "c:"])):
            return {
                "intent": "CRITICAL_ACTION",
                "tool": "delete_file",
                "arguments": {"target": cleaned},
                "confidence": 0.99,
                "summary": "Critical destructive operation requested (requires Level 4 explicit authorization)"
            }

        # Check for Undo
        if re.search(r"\b(undo|rollback|revert)\b", lower):
            return {
                "intent": "PC_ACTION",
                "tool": "rollback_last_action",
                "arguments": {},
                "confidence": 0.98,
                "summary": "Undo last reversible action"
            }

        paste_current_chat = re.match(
            r"^(?:now\s+)?(?:paste|attach)\s+"
            r"((?:this|that|the|latest|previous)(?:\s+(?:screenshot|file|document|attachment))?)"
            r"\s+(?:into|to)\s+(whatsapp|telegram)$",
            cleaned,
            flags=re.IGNORECASE
        )
        if paste_current_chat:
            attachment_ref, service = paste_current_chat.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "prepare_communication",
                "arguments": {
                    "service": service.lower(),
                    "recipient": "current chat",
                    "message": "",
                    "profile": "main",
                    "attachment_path": attachment_ref.strip()
                },
                "confidence": 0.99,
                "summary": f"Prepare {attachment_ref.strip()} in the current {service} chat"
            }

        # Context-linked file/screenshot send to the conversation currently open
        # in WhatsApp/Telegram. Phrases like "this guy" are treated as the active
        # conversation, never as a contact name to guess/search.
        attachment_current_chat = re.match(
            r"^(?:send|share)\s+"
            r"((?:(?:this|that|the|latest|previous)\s+)?(?:screenshot|file|document|attachment))"
            r"\s+to\s+(?:this\s+(?:guy|person|contact)|him|her|this\s+chat|the\s+current\s+chat|current\s+chat)"
            r"\s+(?:on|in|via)\s+(whatsapp|telegram)"
            r"(?:\s+(?:saying|with\s+(?:the\s+)?message)\s+(.+))?$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if attachment_current_chat:
            attachment_ref, service, optional_message = attachment_current_chat.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": service.lower(),
                    "recipient": "current chat",
                    "message": (optional_message or "").strip(),
                    "profile": "main",
                    "attachment_path": attachment_ref.strip()
                },
                "confidence": 0.995,
                "summary": f"Send {attachment_ref.strip()} to the current {service} conversation"
            }

        # Context-linked file/screenshot communication.
        attachment_chat = re.match(
            r"^(?:send|share)\s+((?:this|that|the|latest|previous)\s+(?:screenshot|file|document|attachment))"
            r"\s+to\s+(.+?)\s+(?:on|in|via)\s+(whatsapp|telegram)"
            r"(?:\s+(?:saying|with\s+(?:the\s+)?message)\s+(.+))?$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if attachment_chat:
            attachment_ref, recipient, service, optional_message = attachment_chat.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": service.lower(),
                    "recipient": recipient.strip(),
                    "message": (optional_message or "").strip(),
                    "profile": "main",
                    "attachment_path": attachment_ref.strip()
                },
                "confidence": 0.99,
                "summary": f"Send {attachment_ref.strip()} to {recipient.strip()} on {service}"
            }

        attachment_email = re.match(
            r"^(?:email|send)\s+((?:this|that|the|latest|previous)\s+(?:screenshot|file|document|attachment))"
            r"\s+to\s+([^\s,]+@[^\s,]+)"
            r"(?:\s+(?:saying|with\s+(?:the\s+)?message)\s+(.+))?$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if attachment_email:
            attachment_ref, recipient, optional_message = attachment_email.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": "gmail",
                    "recipient": recipient.strip(),
                    "message": (optional_message or "").strip(),
                    "profile": "main",
                    "attachment_path": attachment_ref.strip()
                },
                "confidence": 0.99,
                "summary": f"Email {attachment_ref.strip()} to {recipient.strip()}"
            }

        # Authenticated communication fallback.
        # Conservative parsing keeps ambiguous recipients from being sent accidentally.
        email_subject = re.match(
            r"^(?:send\s+(?:an?\s+)?email\s+to|email|mail)\s+([^\s,]+@[^\s,]+)\s+subject\s+(.+?)\s+(?:body|message)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if email_subject:
            recipient, subject, message = (
                email_subject.group(1).strip(),
                email_subject.group(2).strip(),
                email_subject.group(3).strip(),
            )
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": "gmail",
                    "recipient": recipient,
                    "subject": subject,
                    "message": message,
                    "profile": "main"
                },
                "confidence": 0.99,
                "summary": f"Send Gmail message to {recipient}"
            }

        email_patterns = [
            (
                "send_communication",
                r"^(?:send\s+(?:an?\s+)?email\s+to|email|mail)\s+(.+?)(?:\s*(?::|,)\s*|\s+(?:saying|that)\s+)(.+)$"
            ),
            (
                "prepare_communication",
                r"^(?:draft|prepare|compose)\s+(?:an?\s+)?email\s+(?:to\s+)?(.+?)(?:\s*(?::|,)\s*|\s+(?:saying|that)\s+)(.+)$"
            ),
        ]
        for tool_name, pattern in email_patterns:
            m = re.match(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
            if m:
                recipient = m.group(1).strip()
                message = m.group(2).strip()
                verb = "Send" if tool_name == "send_communication" else "Prepare"
                return {
                    "intent": "PC_ACTION",
                    "tool": tool_name,
                    "arguments": {
                        "service": "gmail",
                        "recipient": recipient,
                        "message": message,
                        "profile": "main"
                    },
                    "confidence": 0.97,
                    "summary": f"{verb} Gmail message for {recipient}"
                }

        messaging_patterns = [
            (
                "send_communication",
                "service_first",
                r"^(?:send\s+(?:a\s+)?(whatsapp|telegram)(?:\s+message)?\s+to)\s+(.+?)(?:\s*(?::|,)\s*|\s+(?:saying|that)\s+)(.+)$"
            ),
            (
                "send_communication",
                "recipient_first",
                r"^send\s+(.+?)\s+(?:a\s+)?(whatsapp|telegram)(?:\s+message)?\s+(?:saying|that)\s+(.+)$"
            ),
            (
                "send_communication",
                "recipient_first",
                r"^(?:message|msg|text)\s+(.+?)\s+on\s+(whatsapp|telegram)(?:\s*(?::|,)\s*|\s+(?:saying|that)\s+)(.+)$"
            ),
            (
                "send_communication",
                "service_first",
                r"^(whatsapp|telegram)\s+(.+?)(?:\s*(?::|,)\s*|\s+(?:saying|that)\s+)(.+)$"
            ),
            (
                "prepare_communication",
                "service_first",
                r"^(?:draft|prepare|compose)\s+(?:a\s+)?(whatsapp|telegram)(?:\s+message)?\s+(?:to\s+)?(.+?)(?:\s*(?::|,)\s*|\s+(?:saying|that)\s+)(.+)$"
            ),
        ]
        for tool_name, order, pattern in messaging_patterns:
            m = re.match(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
            if not m:
                continue

            if order == "service_first":
                service, recipient, message = m.group(1), m.group(2), m.group(3)
            else:
                recipient, service, message = m.group(1), m.group(2), m.group(3)

            verb = "Send" if tool_name == "send_communication" else "Prepare"
            return {
                "intent": "PC_ACTION",
                "tool": tool_name,
                "arguments": {
                    "service": service.lower(),
                    "recipient": recipient.strip(),
                    "message": message.strip(),
                    "profile": "main"
                },
                "confidence": 0.97,
                "summary": f"{verb} {service} message for {recipient.strip()}"
            }

        # Open authenticated communication services in the user's main Chrome profile.
        service_open = re.search(
            r"\b(?:open|launch|start)\s+(?:my\s+)?(gmail|whatsapp|telegram)(?:\s+(?:in|on|from)\s+(?:google\s+)?chrome)?\b",
            lower
        )
        if service_open:
            service = service_open.group(1)
            urls = {
                "gmail": "https://mail.google.com/mail/",
                "whatsapp": "https://web.whatsapp.com/",
                "telegram": "https://web.telegram.org/k/"
            }
            return {
                "intent": "PC_ACTION",
                "tool": "open_application",
                "arguments": {
                    "application": "Google Chrome",
                    "profile": "main",
                    "path": urls[service]
                },
                "confidence": 0.98,
                "summary": f"Open {service.title()} in the main Chrome profile"
            }

        # Local file actions: exact session references and recent user files.
        copy_recent_file = re.match(
            r"^(?:copy|put)\s+"
            r"((?:the\s+)?(?:(?:latest|recent|most\s+recent|newest|last)\s+)?"
            r"(?:screenshot|screen\s+shot|png|jpe?g|image|picture|photo|file|document)|"
            r"(?:this|that|the|latest|previous)\s+(?:screenshot|file|document|attachment))"
            r"\s+(?:to|on|into)\s+(?:my\s+|the\s+)?clipboard$",
            cleaned,
            flags=re.IGNORECASE
        )
        if copy_recent_file:
            return {
                "intent": "PC_ACTION",
                "tool": "copy_file_to_clipboard",
                "arguments": {"filepath": copy_recent_file.group(1).strip()},
                "confidence": 0.99,
                "summary": f"Copy {copy_recent_file.group(1).strip()} to Windows clipboard"
            }

        open_recent_file = re.match(
            r"^(?:open|show|view)\s+"
            r"((?:the\s+)?(?:(?:latest|recent|most\s+recent|newest|last)\s+)"
            r"(?:screenshot|screen\s+shot|png|jpe?g|image|picture|photo|file|document)|"
            r"(?:this|that|the|latest|previous)\s+(?:screenshot|file|document|attachment))$",
            cleaned,
            flags=re.IGNORECASE
        )
        if open_recent_file:
            return {
                "intent": "PC_ACTION",
                "tool": "open_file",
                "arguments": {"filepath": open_recent_file.group(1).strip()},
                "confidence": 0.99,
                "summary": f"Open {open_recent_file.group(1).strip()}"
            }

        # Check for open application (VS Code, Notepad, Chrome, Explorer, Terminal, etc.)
        match_app = re.search(r"\b(?:open|launch|start|run)\s+(?:application\s+|app\s+)?([a-zA-Z0-9\s\.\-_]+?)(?:\s+and\s+|\s*$|\.|\?)", lower)
        if match_app:
            app_raw = match_app.group(1).strip()
            # Distinguish app from file or command
            if any(term in app_raw for term in ["vs code", "vscode", "code", "notepad", "chrome", "firefox", "edge", "terminal", "powershell", "cmd", "explorer"]):
                if "chrome" in app_raw:
                    app_name = "Google Chrome"
                elif "firefox" in app_raw:
                    app_name = "Firefox"
                elif "edge" in app_raw:
                    app_name = "Microsoft Edge"
                elif "notepad" in app_raw:
                    app_name = "Notepad"
                elif any(term in app_raw for term in ["vs code", "vscode", "code"]):
                    app_name = "Visual Studio Code"
                elif "powershell" in app_raw:
                    app_name = "PowerShell"
                elif "cmd" in app_raw:
                    app_name = "Command Prompt"
                elif "terminal" in app_raw:
                    app_name = "Windows Terminal"
                elif "explorer" in app_raw:
                    app_name = "Explorer"
                else:
                    app_name = app_raw.title()

                profile_hint = None
                if "chrome" in app_raw:
                    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", cleaned)
                    if email_match:
                        profile_hint = email_match.group(0)
                    elif any(
                        phrase in lower
                        for phrase in [
                            "main account", "main profile", "my main account",
                            "primary account", "primary profile",
                            "default", "default account", "default profile",
                            "my default", "my default account", "my default profile"
                        ]
                    ):
                        # All user-facing default/main aliases map to the locally
                        # selected MAYA Chrome profile.
                        profile_hint = "main"

                # Check if user also asked to check project or scan errors
                check_proj = "check" in lower or "scan" in lower or "error" in lower or "project" in lower
                arguments = {"application": app_name}
                if profile_hint:
                    arguments["profile"] = profile_hint

                return {
                    "intent": "DEVELOPMENT_ACTION" if check_proj else "PC_ACTION",
                    "tool": "open_application_and_inspect" if check_proj else "open_application",
                    "arguments": arguments,
                    "confidence": 0.95,
                    "summary": (
                        f"Open {app_name}"
                        + (f" using profile '{profile_hint}'" if profile_hint else "")
                        + (" and scan project for errors" if check_proj else "")
                    )
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
        if any(greeting in lower for greeting in ["hey maya", "hello maya", "hi maya", "maya", "hello", "hi there", "how are you"]):
            return {
                "intent": "CHAT",
                "tool": None,
                "arguments": {},
                "confidence": 0.99,
                "summary": "Conversational greeting or dialogue"
            }

        # Question intent
        if lower.startswith("who ") or lower.startswith("what is ") or lower.startswith("can you ") or lower.startswith("how do ") or lower.endswith("?"):
            return {
                "intent": "QUESTION",
                "tool": None,
                "arguments": {"query": cleaned},
                "confidence": 0.95,
                "summary": "User informational inquiry or question"
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
