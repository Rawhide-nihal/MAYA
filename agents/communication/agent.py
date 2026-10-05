"""MAYA authenticated web communication agent.

This agent never reads passwords or browser cookies. It launches the user's selected
Chrome profile and delegates authenticated DOM interaction to the MAYA Browser Bridge
extension running inside that profile.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, Optional

from agents.communication.bridge import CommunicationBridge, communication_bridge
from agents.windows.agent import WindowsAgent
from maya_core.config import settings


SERVICE_URLS = {
    "gmail": "https://mail.google.com/mail/",
    "whatsapp": "https://web.whatsapp.com/",
    "telegram": "https://web.telegram.org/k/",
}


class CommunicationAgent:
    def __init__(
        self,
        windows: Optional[WindowsAgent] = None,
        bridge: Optional[CommunicationBridge] = None,
    ):
        self.windows = windows or WindowsAgent()
        self.bridge = bridge or communication_bridge

    @staticmethod
    def _normalize_service(service: str) -> str:
        value = (service or "").strip().lower()
        aliases = {
            "mail": "gmail",
            "email": "gmail",
            "google mail": "gmail",
            "wa": "whatsapp",
            "whatsapp web": "whatsapp",
            "tg": "telegram",
            "telegram web": "telegram",
        }
        return aliases.get(value, value)

    def _execute(
        self,
        *,
        action: str,
        service: str,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
        profile: Optional[str] = "main",
        attachment_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        service_name = self._normalize_service(service)
        if service_name not in SERVICE_URLS:
            return {
                "success": False,
                "verified": False,
                "error": "Service must be gmail, whatsapp, or telegram.",
            }

        recipient = (recipient or "").strip()
        message = (message or "").strip()
        if not recipient:
            return {"success": False, "verified": False, "error": "Recipient is required."}
        if not message and not attachment_path:
            return {"success": False, "verified": False, "error": "Message or attachment is required."}

        expanded_attachment = None
        if attachment_path:
            expanded_attachment = str(Path(attachment_path).expanduser().resolve())
            if not os.path.isfile(expanded_attachment):
                return {
                    "success": False,
                    "verified": False,
                    "error": f"Attachment does not exist or is not a file: {expanded_attachment}",
                }
            max_mb = int(settings.get("communication_attachment_max_mb", 12))
            size_bytes = os.path.getsize(expanded_attachment)
            if size_bytes > max_mb * 1024 * 1024:
                return {
                    "success": False,
                    "verified": False,
                    "error": (
                        f"Attachment is {round(size_bytes / (1024 * 1024), 1)} MB. "
                        f"The current verified browser bridge limit is {max_mb} MB."
                    ),
                }

        current_chat = recipient.lower() in {"current chat", "current conversation"}
        target_tab_id = None

        if not current_chat and service_name in {"whatsapp", "telegram"}:
            resolver = getattr(self.bridge, "resolve_contact", None)
            resolved_contact = resolver(service_name, recipient) if callable(resolver) else {}
            if resolved_contact.get("matched") and resolved_contact.get("name"):
                recipient = str(resolved_contact["name"]).strip()
            elif resolved_contact.get("ambiguous"):
                suggestions = [
                    str(name) for name in (resolved_contact.get("suggestions") or [])
                    if name
                ]
                return {
                    "success": False,
                    "verified": False,
                    "error": (
                        f"More than one {service_name.title()} contact could match '{recipient}'. "
                        + ("Possible matches: " + ", ".join(suggestions[:6]) if suggestions else "Please use the exact contact name.")
                    ),
                    "contact_resolution": resolved_contact,
                }

        if current_chat:
            browser_context = self.bridge.get_browser_context()
            active_url = str(browser_context.get("url") or "")
            active_host = (urlparse(active_url).hostname or "").lower()
            expected_hosts = {
                "whatsapp": "web.whatsapp.com",
                "telegram": "web.telegram.org",
            }
            expected_host = expected_hosts.get(service_name)
            target_tab_id = browser_context.get("tab_id")

            if not expected_host or active_host != expected_host or target_tab_id is None:
                return {
                    "success": False,
                    "verified": False,
                    "error": (
                        f"Open the exact {service_name.title()} conversation you want in the active Chrome tab, "
                        "then retry. MAYA refused to guess which chat you meant."
                    ),
                }

            launch = {
                "success": True,
                "verified": True,
                "profile_name": profile or "main",
                "reused_active_tab": True,
            }
        else:
            launch = self.windows.launch_application(
                "Google Chrome",
                arguments=[SERVICE_URLS[service_name]],
                profile=profile or "main",
            )
            if not launch.get("success"):
                return {
                    "success": False,
                    "verified": False,
                    "error": launch.get("error", "Could not launch Chrome."),
                    "launch": launch,
                }

        command = {
            "service": service_name,
            "action": action,
            "recipient": recipient,
            "message": message,
            "subject": (subject or "").strip(),
            "profile": profile or "main",
            "attachment_path": expanded_attachment,
            "target_tab_id": target_tab_id,
        }
        result = self.bridge.submit(command, timeout=30.0)
        result.setdefault("service", service_name)
        result.setdefault("recipient", recipient)
        result["chrome_profile"] = launch.get("profile_name") or launch.get("profile_directory")
        return result

    def sync_contacts(
        self,
        service: str = "whatsapp",
        profile: Optional[str] = "main",
    ) -> Dict[str, Any]:
        service_name = self._normalize_service(service)
        if service_name != "whatsapp":
            return {
                "success": False,
                "verified": False,
                "error": "Full contact sync is currently implemented for WhatsApp Web.",
            }

        launch = self.windows.launch_application(
            "Google Chrome",
            arguments=[SERVICE_URLS[service_name]],
            profile=profile or "main",
        )
        if not launch.get("success"):
            return {
                "success": False,
                "verified": False,
                "error": launch.get("error", "Could not launch Chrome."),
                "launch": launch,
            }

        result = self.bridge.submit({
            "service": service_name,
            "action": "sync_contacts",
            "recipient": "",
            "message": "",
            "subject": "",
            "profile": profile or "main",
            "attachment_path": None,
            "target_tab_id": None,
        }, timeout=45.0)
        result.setdefault("service", service_name)
        result["chrome_profile"] = launch.get("profile_name") or launch.get("profile_directory")
        result["local_contact_count"] = len(self.bridge.list_contacts(service_name))
        return result

    def prepare(
        self,
        service: str,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
        profile: Optional[str] = "main",
        attachment_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._execute(
            action="compose",
            service=service,
            recipient=recipient,
            message=message,
            subject=subject,
            profile=profile,
            attachment_path=attachment_path,
        )

    def send(
        self,
        service: str,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
        profile: Optional[str] = "main",
        attachment_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._execute(
            action="send",
            service=service,
            recipient=recipient,
            message=message,
            subject=subject,
            profile=profile,
            attachment_path=attachment_path,
        )
