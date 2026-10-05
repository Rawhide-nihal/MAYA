"""MAYA authenticated web communication agent.

This agent never reads passwords or browser cookies. It launches the user's selected
Chrome profile and delegates authenticated DOM interaction to the MAYA Browser Bridge
extension running inside that profile.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from agents.communication.bridge import CommunicationBridge, communication_bridge
from agents.windows.agent import WindowsAgent


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

        if attachment_path:
            expanded = os.path.abspath(os.path.expanduser(attachment_path))
            if not os.path.exists(expanded):
                return {
                    "success": False,
                    "verified": False,
                    "error": f"Attachment does not exist: {expanded}",
                }
            # Browser-file handoff is deliberately not faked. The extension will
            # gain attachment transport in the next capability pass.
            return {
                "success": False,
                "verified": False,
                "error": (
                    "Text messaging is ready, but local attachment transfer is not enabled yet. "
                    "MAYA will not claim an attachment was sent when it was not."
                ),
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

        command = {
            "service": service_name,
            "action": action,
            "recipient": recipient,
            "message": message,
            "subject": (subject or "").strip(),
            "profile": profile or "main",
        }
        result = self.bridge.submit(command, timeout=30.0)
        result.setdefault("service", service_name)
        result.setdefault("recipient", recipient)
        result["chrome_profile"] = launch.get("profile_name") or launch.get("profile_directory")
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
