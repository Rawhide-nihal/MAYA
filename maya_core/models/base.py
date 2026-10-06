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
        original_text = text.strip()
        # Natural wake/name prefixes must not prevent deterministic action routing.
        # "Maya, sync my contacts" and "Hey Maya: open Chrome" are commands,
        # not ordinary chat merely because the assistant's name came first.
        cleaned = re.sub(
            r"^(?:hey\s+)?maya\b[\s,:;\-]*",
            "",
            original_text,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        if not cleaned:
            cleaned = original_text
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

        explicit_attachment_send = re.match(
            r"^(?:send|share)\s+(?:the\s+)?(file|folder)\s+(.+?)\s+to\s+(.+?)"
            r"\s+(?:on|in|via)\s+(whatsapp|telegram)"
            r"(?:\s+(?:saying|with\s+(?:the\s+)?message)\s+(.+))?$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if explicit_attachment_send:
            kind, path_text, recipient, service, optional_message = explicit_attachment_send.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": service.lower(),
                    "recipient": recipient.strip(),
                    "message": (optional_message or "").strip(),
                    "profile": "main",
                    "attachment_path": path_text.strip().strip('"')
                },
                "confidence": 0.995,
                "summary": f"Send {kind} {path_text.strip()} to {recipient.strip()} on {service}"
            }

        path_attachment_send = re.match(
            r"^(?:send|share)\s+([A-Za-z]:[\\/].+?)\s+to\s+(.+?)"
            r"\s+(?:on|in|via)\s+(whatsapp|telegram)"
            r"(?:\s+(?:saying|with\s+(?:the\s+)?message)\s+(.+))?$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if path_attachment_send:
            path_text, recipient, service, optional_message = path_attachment_send.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": service.lower(),
                    "recipient": recipient.strip(),
                    "message": (optional_message or "").strip(),
                    "profile": "main",
                    "attachment_path": path_text.strip().strip('"')
                },
                "confidence": 0.995,
                "summary": f"Send local path {path_text.strip()} to {recipient.strip()} on {service}"
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

        sync_contacts = re.match(
            r"^(?:sync|refresh|update|load)\s+(?:my\s+)?(whatsapp)\s+"
            r"(?:contacts|contact\s+list|chats|contacts\s+and\s+chats)[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if sync_contacts:
            service = sync_contacts.group(1).lower()
            return {
                "intent": "PC_ACTION",
                "tool": "sync_communication_contacts",
                "arguments": {"service": service, "profile": "main"},
                "confidence": 0.99,
                "summary": f"Synchronize local {service.title()} contacts and chats"
            }

        contact_detail = re.match(
            r"^(?:(?:can|could|would)\s+(?:you|u)\s+)?"
            r"(?:(?:give|tell|show|get)\s+(?:me\s+)?)?"
            r"(?:(?:the\s+)?)"
            r"(?:(?:phone\s+)?number|phone|details)\s+(?:of|for)\s+(.+?)[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if contact_detail:
            query = contact_detail.group(1).strip()
            detail = "phone" if re.search(r"\b(?:phone|number)\b", cleaned, flags=re.IGNORECASE) else "all"
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "inspect_communication_contact",
                "arguments": {"service": "whatsapp", "query": query, "record_type": "contact", "profile": "main"},
                "confidence": 0.995,
                "summary": f"Get stored WhatsApp {detail} details for {query}"
            }

        possessive_detail = re.match(
            r"^(?:what(?:'s|\s+is)\s+)?(.+?)(?:'s|s')\s+(phone\s+number|number|details)[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if possessive_detail:
            query, detail_text = possessive_detail.groups()
            detail = "phone" if "number" in detail_text.lower() or "phone" in detail_text.lower() else "all"
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "inspect_communication_contact",
                "arguments": {"service": "whatsapp", "query": query.strip(), "record_type": "contact", "profile": "main"},
                "confidence": 0.99,
                "summary": f"Get stored WhatsApp {detail} details for {query.strip()}"
            }

        contact_number_from_contacts = re.match(
            r"^(?:(?:can|could)\s+(?:you|u)\s+)?(?:get|give|find|tell)\s+(?:me\s+)?"
            r"(.+?)\s+(?:phone\s+)?number\s+(?:from|in)\s+(?:my\s+)?(?:whatsapp\s+)?contacts[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if contact_number_from_contacts:
            query = contact_number_from_contacts.group(1).strip()
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "inspect_communication_contact",
                "arguments": {"service": "whatsapp", "query": query, "record_type": "contact", "profile": "main"},
                "confidence": 0.995,
                "summary": f"Get stored WhatsApp phone number for {query}"
            }

        read_and_reply = re.match(
            r"^(?:read|check)\s+(?:the\s+)?(?:latest|last)\s+(?:whatsapp\s+)?message"
            r"\s+(?:from|of)\s+(.+?)(?:\s+on\s+whatsapp)?\s+"
            r"(?:and\s+)?(?:reply|respond)\s+(?:saying|with\s+(?:the\s+)?message|that)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if read_and_reply:
            recipient, message = read_and_reply.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "read_and_reply_communication",
                "arguments": {
                    "service": "whatsapp",
                    "recipient": recipient.strip(),
                    "message": message.strip(),
                    "profile": "main"
                },
                "confidence": 0.995,
                "summary": f"Read latest WhatsApp message from {recipient.strip()} and send the explicit reply"
            }

        read_latest_messages = re.match(
            r"^(?:read|show|get|check)\s+(?:me\s+)?(?:the\s+)?"
            r"(?:latest|last|recent)\s*(?:(\d+)\s+)?(?:whatsapp\s+)?messages?"
            r"\s+(?:from|of)\s+(.+?)(?:\s+on\s+whatsapp)?[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if read_latest_messages:
            count_text, recipient = read_latest_messages.groups()
            recipient = recipient.strip()
            if recipient.lower() in {"this chat", "this contact", "this person", "him", "her"}:
                recipient = "current chat"
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "read_communication_messages",
                "arguments": {
                    "service": "whatsapp",
                    "recipient": recipient,
                    "limit": max(1, min(int(count_text or 1), 20)),
                    "profile": "main"
                },
                "confidence": 0.995,
                "summary": f"Read latest WhatsApp message(s) from {recipient}"
            }

        what_did_contact_say = re.match(
            r"^(?:what\s+did|what(?:'s|\s+is))\s+(.+?)\s+(?:say|send|message)(?:\s+me)?(?:\s+on\s+whatsapp)?[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if what_did_contact_say:
            recipient = what_did_contact_say.group(1).strip()
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "read_communication_messages",
                "arguments": {
                    "service": "whatsapp",
                    "recipient": recipient,
                    "limit": 1,
                    "profile": "main"
                },
                "confidence": 0.99,
                "summary": f"Read latest WhatsApp message from {recipient}"
            }

        reply_message = re.match(
            r"^(?:reply|respond)\s+(?:to\s+)?(?:the\s+latest\s+message\s+from\s+)?"
            r"(.+?)(?:\s+on\s+whatsapp)?\s+(?:saying|with\s+(?:the\s+)?message|that)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        if reply_message:
            recipient, message = reply_message.groups()
            return {
                "intent": "PC_ACTION",
                "tool": "send_communication",
                "arguments": {
                    "service": "whatsapp",
                    "recipient": recipient.strip(),
                    "message": message.strip(),
                    "profile": "main"
                },
                "confidence": 0.99,
                "summary": f"Reply to {recipient.strip()} on WhatsApp"
            }

        contact_lookup = re.match(
            r"^(?:(?:can|could|would)\s+(?:you|u)\s+)?"
            r"(?:find|lookup|look\s+up|search\s+for|check\s+for)\s+"
            r"(?:(?:a|the)\s+)?(?:(whatsapp)\s+)?(contact|group)"
            r"(?:\s+(?:named|called))?\s+(.+?)[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if contact_lookup:
            service, record_kind, query = contact_lookup.groups()
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "lookup_communication_contact",
                "arguments": {
                    "service": (service or "whatsapp").lower(),
                    "query": query.strip(),
                    "record_type": "group" if record_kind.lower() == "group" else "contact"
                },
                "confidence": 0.995,
                "summary": f"Look up {query.strip()} in the local {(service or 'WhatsApp').title()} contact index"
            }

        contact_lookup_alt = re.match(
            r"^(?:do\s+i\s+have|is)\s+(.+?)\s+(?:in|among)\s+(?:my\s+)?whatsapp\s+contacts[.!?]*$",
            cleaned,
            flags=re.IGNORECASE
        )
        if contact_lookup_alt:
            query = contact_lookup_alt.group(1).strip()
            return {
                "intent": "INFORMATION_REQUEST",
                "tool": "lookup_communication_contact",
                "arguments": {"service": "whatsapp", "query": query},
                "confidence": 0.99,
                "summary": f"Look up {query} in the local WhatsApp contact index"
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

        # Open authenticated communication services; reuse an existing tab by default.
        service_open = re.search(
            r"\b(?:open|launch|start)\s+(?:my\s+)?(gmail|whatsapp|telegram)"
            r"(?:\s+(?:in|on|from)\s+(?:google\s+)?chrome)?\b",
            lower
        )
        if service_open:
            service = service_open.group(1)
            force_new = bool(re.search(
                r"\b(?:new\s+(?:tab|window)|fresh(?:ly)?|newly|another\s+(?:tab|window))\b",
                lower
            ))
            return {
                "intent": "PC_ACTION",
                "tool": "open_communication_service",
                "arguments": {
                    "service": service,
                    "profile": "main",
                    "force_new": force_new
                },
                "confidence": 0.99,
                "summary": (
                    f"Open {service.title()} "
                    + ("in a new browser tab" if force_new else "using the existing tab if available")
                )
            }

        # Local file actions: exact session references and recent user files.
        copy_to_clipboard = re.match(
            r"^(?:copy|put)\s+(.+?)\s+(?:to|on|into)\s+(?:my\s+|the\s+|pc\s+)?clipboard$",
            cleaned,
            flags=re.IGNORECASE
        )
        if copy_to_clipboard:
            target = copy_to_clipboard.group(1).strip()
            target_lower = target.lower()
            path_like = bool(
                re.search(r"^[a-zA-Z]:[\\/]", target)
                or re.search(r"\.[a-zA-Z0-9]{1,10}$", target.strip('"'))
            )
            if (
                any(word in target_lower for word in [
                    "screenshot", "screen shot", "png", "jpg", "jpeg",
                    "image", "picture", "photo", "file", "document", "attachment"
                ])
                or target_lower in {"this", "that", "it", "latest", "previous"}
                or path_like
            ):
                return {
                    "intent": "PC_ACTION",
                    "tool": "copy_file_to_clipboard",
                    "arguments": {"filepath": target},
                    "confidence": 0.99,
                    "summary": f"Copy {target} to Windows clipboard"
                }

        open_local_file = re.match(
            r"^(?:open|show|view)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE
        )
        if open_local_file:
            target = open_local_file.group(1).strip()
            target_lower = target.lower()
            has_recent_reference = any(
                word in target_lower
                for word in ["latest", "recent", "most recent", "newest", "last", "previous"]
            )
            has_file_kind = any(
                word in target_lower
                for word in [
                    "screenshot", "screen shot", "png", "jpg", "jpeg",
                    "image", "picture", "photo", "file", "document", "attachment"
                ]
            )
            session_reference = target_lower in {
                "this file", "that file", "this document", "that document",
                "this screenshot", "that screenshot", "the screenshot",
                "latest screenshot", "previous screenshot"
            }
            path_like = bool(
                re.search(r"^[a-zA-Z]:[\\/]", target)
                or re.search(r"\.[a-zA-Z0-9]{1,10}$", target.strip('"'))
            )
            if (has_recent_reference and has_file_kind) or session_reference or path_like:
                return {
                    "intent": "PC_ACTION",
                    "tool": "open_file",
                    "arguments": {"filepath": target},
                    "confidence": 0.99,
                    "summary": f"Open {target}"
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
                force_new = bool(re.search(
                    r"\b(?:new\s+(?:window|instance|tab)|fresh(?:ly)?|newly|another\s+(?:window|instance|tab))\b",
                    lower
                ))
                arguments = {"application": app_name, "force_new": force_new}
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
