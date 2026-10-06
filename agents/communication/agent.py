"""MAYA authenticated web communication agent.

This agent never reads passwords or browser cookies. It launches the user's selected
Chrome profile and delegates authenticated DOM interaction to the MAYA Browser Bridge
extension running inside that profile.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, Optional

from agents.communication.bridge import CommunicationBridge, communication_bridge
from agents.windows.agent import WindowsAgent
from maya_core.config import settings, MAYA_DATA_DIR


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

    def _attach_active_browser_tab(
        self,
        result: Dict[str, Any],
        expected_url_prefix: str,
        timeout: float = 1.4,
    ) -> Dict[str, Any]:
        """Attach the Browser Bridge's active tab id after a Windows/UIA fallback."""
        getter = getattr(self.bridge, "get_browser_context", None)
        if not callable(getter):
            return result

        deadline = time.time() + max(0.1, timeout)
        while time.time() < deadline:
            context = getter() or {}
            url = str(context.get("url") or "")
            tab_id = context.get("tab_id")
            if tab_id is not None and url.startswith(expected_url_prefix):
                result["tab_id"] = tab_id
                result["window_id"] = context.get("window_id")
                result["url"] = url
                result["bridge_tab_bound"] = True
                return result
            time.sleep(0.10)
        result["bridge_tab_bound"] = False
        return result

    def open_service(
        self,
        service: str,
        profile: Optional[str] = "main",
        force_new: bool = False,
    ) -> Dict[str, Any]:
        """Focus an existing authenticated service tab, creating one only when needed."""
        service_name = self._normalize_service(service)
        if service_name not in SERVICE_URLS:
            return {
                "success": False,
                "verified": False,
                "error": "Service must be gmail, whatsapp, or telegram.",
            }

        submit_browser = getattr(self.bridge, "submit_browser_action", None)
        bridge_status = getattr(self.bridge, "status", None)
        recent = None
        if callable(bridge_status):
            try:
                recent = bool((bridge_status() or {}).get("connected_recently"))
            except Exception:
                recent = None

        if callable(submit_browser) and recent is not False:
            browser_result = submit_browser({
                "type": "focus_service",
                "service": service_name,
                "url": SERVICE_URLS[service_name],
                "force_new": bool(force_new),
            }, timeout=2.8)
        else:
            browser_result = {
                "success": False,
                "verified": False,
                "error": (
                    "MAYA Browser Bridge is not responding recently."
                    if recent is False
                    else "Browser background action bridge is unavailable."
                ),
            }

        if browser_result.get("success"):
            browser_result.setdefault("service", service_name)
            browser_result["profile"] = profile or "main"
            return browser_result

        # Real-machine fallback: if the MV3 worker slept, search the exact Chrome
        # profile's existing tabs before creating anything new.
        if not force_new:
            search_labels = {
                "whatsapp": ("WhatsApp", "whatsapp"),
                "gmail": ("Gmail", "gmail"),
                "telegram": ("Telegram", "telegram"),
            }
            search_text, expected_title = search_labels[service_name]
            focus_tab = getattr(self.windows, "focus_chrome_tab_by_search", None)
            if callable(focus_tab):
                tab_result = focus_tab(
                    profile or "main",
                    search_text,
                    expected_title=expected_title,
                )
                if tab_result.get("success") and tab_result.get("verified"):
                    tab_result.setdefault("service", service_name)
                    tab_result["profile"] = profile or "main"
                    tab_result["browser_bridge_fallback"] = True
                    tab_result["browser_bridge_error"] = browser_result.get("error")
                    return self._attach_active_browser_tab(
                        tab_result,
                        SERVICE_URLS[service_name],
                    )

        # No verified existing service tab was found, or the user explicitly
        # requested a new/fresh tab. Create one in the exact configured profile.
        open_url = getattr(self.windows, "open_url_in_chrome_profile", None)
        if callable(open_url):
            fallback = open_url(
                profile or "main",
                SERVICE_URLS[service_name],
            )
        else:
            try:
                fallback = self.windows.launch_application(
                    "Google Chrome",
                    arguments=[SERVICE_URLS[service_name]],
                    profile=profile or "main",
                    force_new=True,
                )
            except TypeError:
                fallback = self.windows.launch_application(
                    "Google Chrome",
                    arguments=[SERVICE_URLS[service_name]],
                    profile=profile or "main",
                )

        fallback.setdefault("service", service_name)
        fallback["browser_bridge_fallback"] = True
        fallback["browser_bridge_error"] = browser_result.get("error")
        if not fallback.get("success"):
            fallback.setdefault(
                "error",
                browser_result.get("error") or "Could not open the communication service."
            )
            return fallback
        return self._attach_active_browser_tab(
            fallback,
            SERVICE_URLS[service_name],
        )

    def read_messages(
        self,
        recipient: str,
        limit: int = 1,
        service: str = "whatsapp",
        profile: Optional[str] = "main",
        incoming_only: bool = False,
    ) -> Dict[str, Any]:
        service_name = self._normalize_service(service)
        if service_name != "whatsapp":
            return {
                "success": False,
                "verified": False,
                "error": "Live message reading is currently implemented for WhatsApp Web.",
            }

        recipient_text = str(recipient or "").strip()
        if not recipient_text:
            return {"success": False, "verified": False, "error": "Recipient is required."}

        current_chat = recipient_text.lower() in {"current chat", "current conversation"}
        if not current_chat:
            resolved = self.bridge.resolve_contact("whatsapp", recipient_text)
            if resolved.get("matched") and resolved.get("record"):
                recipient_text = str(resolved["record"].get("name") or recipient_text)
            elif resolved.get("ambiguous"):
                suggestions = [
                    (item.get("name") if isinstance(item, dict) else str(item))
                    for item in (resolved.get("suggestions") or [])
                ]
                return {
                    "success": False,
                    "verified": False,
                    "error": (
                        f"More than one WhatsApp record could match '{recipient_text}'. "
                        + ("Possible matches: " + ", ".join([x for x in suggestions if x][:6]) if suggestions else "Use the exact name.")
                    ),
                    "suggestions": resolved.get("suggestions") or [],
                }

        opened = self.open_service("whatsapp", profile=profile, force_new=False)
        if not opened.get("success"):
            return {
                "success": False,
                "verified": False,
                "error": opened.get("error", "Could not open WhatsApp Web."),
                "open_result": opened,
            }

        result = self.bridge.submit({
            "service": "whatsapp",
            "action": "read_messages",
            "recipient": recipient_text,
            "message": "",
            "subject": "",
            "profile": profile or "main",
            "attachment_path": None,
            "target_tab_id": opened.get("tab_id"),
            "limit": max(1, min(int(limit or 1), 20)),
            "incoming_only": bool(incoming_only),
        }, timeout=25.0)
        result.setdefault("service", "whatsapp")
        result.setdefault("recipient", recipient_text)
        return result

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
        generated_archive = None
        original_attachment = None

        def cleanup_generated_archive() -> None:
            if generated_archive:
                try:
                    if os.path.exists(generated_archive):
                        os.remove(generated_archive)
                except OSError:
                    pass
        if attachment_path:
            original_attachment = str(Path(attachment_path).expanduser().resolve())
            expanded_attachment = original_attachment

            if os.path.isdir(original_attachment):
                outbox = MAYA_DATA_DIR / "communication_outbox"
                outbox.mkdir(parents=True, exist_ok=True)
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_attachment).name).strip("_") or "folder"
                archive_base = outbox / f"{safe_name}_{int(time.time() * 1000)}"
                try:
                    generated_archive = shutil.make_archive(
                        str(archive_base),
                        "zip",
                        root_dir=original_attachment,
                    )
                    expanded_attachment = generated_archive
                except Exception as exc:
                    return {
                        "success": False,
                        "verified": False,
                        "error": f"Could not package folder for WhatsApp transfer: {exc}",
                    }

            if not os.path.isfile(expanded_attachment):
                return {
                    "success": False,
                    "verified": False,
                    "error": f"Attachment does not exist: {expanded_attachment}",
                }

            max_mb = int(settings.get("communication_attachment_max_mb", 12))
            size_bytes = os.path.getsize(expanded_attachment)
            if size_bytes > max_mb * 1024 * 1024:
                if generated_archive:
                    try:
                        os.remove(generated_archive)
                    except OSError:
                        pass
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
                cleanup_generated_archive()
                suggestions = [
                    (item.get("name") if isinstance(item, dict) else str(item))
                    for item in (resolved_contact.get("suggestions") or [])
                    if item
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
                cleanup_generated_archive()
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
            launch = self.open_service(
                service_name,
                profile=profile or "main",
                force_new=False,
            )
            if not launch.get("success"):
                cleanup_generated_archive()
                return {
                    "success": False,
                    "verified": False,
                    "error": launch.get("error", "Could not open communication service."),
                    "launch": launch,
                }
            target_tab_id = launch.get("tab_id")

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
        try:
            result = self.bridge.submit(command, timeout=30.0)
        except Exception as exc:
            result = {
                "success": False,
                "verified": False,
                "error": f"Communication bridge failed: {exc}",
            }
        finally:
            cleanup_generated_archive()

        result.setdefault("service", service_name)
        result.setdefault("recipient", recipient)
        result["chrome_profile"] = (
            launch.get("profile_name")
            or launch.get("profile_directory")
            or launch.get("profile")
        )
        if generated_archive:
            result["folder_packaged_as_zip"] = True
            result["original_attachment_path"] = original_attachment
            result["archive_name"] = os.path.basename(generated_archive)
        return result

    def inspect_contact(
        self,
        service: str = "whatsapp",
        query: str = "",
        profile: Optional[str] = "main",
        record_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        service_name = self._normalize_service(service)
        if service_name != "whatsapp":
            return {
                "success": False,
                "verified": False,
                "error": "Live contact inspection is currently implemented for WhatsApp Web.",
            }

        query_text = str(query or "").strip()
        if not query_text:
            return {"success": False, "verified": False, "error": "Contact or group name is required."}

        local = self.bridge.resolve_contact(
            service_name,
            query_text,
            record_type=record_type,
        )
        recipient = (
            str((local.get("record") or {}).get("name") or local.get("name") or query_text)
            if local.get("matched")
            else query_text
        )

        opened = self.open_service("whatsapp", profile=profile, force_new=False)
        if not opened.get("success"):
            return {
                "success": False,
                "verified": False,
                "error": opened.get("error", "Could not open WhatsApp Web."),
                "open_result": opened,
            }

        result = self.bridge.submit({
            "service": "whatsapp",
            "action": "inspect_contact",
            "recipient": recipient,
            "message": "",
            "subject": "",
            "profile": profile or "main",
            "attachment_path": None,
            "target_tab_id": opened.get("tab_id"),
            "record_type": record_type,
        }, timeout=25.0)

        record = result.get("record") if isinstance(result, dict) else None
        if result.get("success") and isinstance(record, dict) and record.get("name"):
            self.bridge.update_contacts(
                "whatsapp",
                [record],
                source="whatsapp_live_contact_inspection",
            )
            enriched = self.bridge.resolve_contact(
                "whatsapp",
                record.get("name") or query_text,
                record_type=record_type,
            )
            merged_record = dict(enriched.get("record") or record)
            return {
                "success": True,
                "verified": True,
                "found": True,
                "service": "whatsapp",
                "query": query_text,
                "name": merged_record.get("name") or query_text,
                "record": merged_record,
                "type": merged_record.get("type"),
                "phone": merged_record.get("phone"),
                "jid": merged_record.get("jid"),
                "chat_id": merged_record.get("chat_id"),
                "aliases": merged_record.get("aliases") or [],
                "live_inspected": True,
            }

        return {
            "success": False,
            "verified": False,
            "query": query_text,
            "error": result.get("error", "WhatsApp did not expose contact details."),
            "live_result": result,
        }

    def lookup_contact(
        self,
        service: str = "whatsapp",
        query: str = "",
        detail: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        service_name = self._normalize_service(service)
        if service_name not in {"whatsapp", "telegram"}:
            return {
                "success": False,
                "verified": False,
                "error": "Contact lookup supports WhatsApp or Telegram indexes.",
            }

        query_text = str(query or "").strip()
        if not query_text:
            return {
                "success": False,
                "verified": False,
                "error": "Contact name is required.",
            }

        resolution = self.bridge.resolve_contact(
            service_name,
            query_text,
            record_type=record_type,
        )
        indexed_count = len(self.bridge.list_contacts(service_name))

        if resolution.get("matched"):
            record = dict(resolution.get("record") or {})
            return {
                "success": True,
                "verified": True,
                "found": True,
                "service": service_name,
                "query": query_text,
                "name": resolution.get("name"),
                "record": record,
                "type": record.get("type"),
                "phone": record.get("phone"),
                "jid": record.get("jid"),
                "chat_id": record.get("chat_id"),
                "aliases": record.get("aliases") or [],
                "resolution": resolution.get("resolution"),
                "score": resolution.get("score"),
                "detail_requested": detail,
                "indexed_count": indexed_count,
            }

        if service_name == "whatsapp":
            live = self.inspect_contact(
                service="whatsapp",
                query=query_text,
                profile="main",
                record_type=record_type,
            )
            if live.get("success") and live.get("found"):
                live["resolution"] = live.get("resolution") or "live_whatsapp_fuzzy"
                live["local_search_before_live"] = resolution
                live["indexed_count"] = len(self.bridge.list_contacts(service_name))
                live["detail_requested"] = detail
                return live

            live_suggestions = (
                (live.get("live_result") or {}).get("suggestions")
                or live.get("suggestions")
                or []
            )
            return {
                "success": True,
                "verified": True,
                "found": False,
                "ambiguous": bool(
                    resolution.get("ambiguous")
                    or (live.get("live_result") or {}).get("ambiguous")
                    or live.get("ambiguous")
                ),
                "service": service_name,
                "query": query_text,
                "suggestions": live_suggestions or resolution.get("suggestions") or [],
                "indexed_count": indexed_count,
                "local_search": resolution,
                "live_search_attempted": True,
                "live_error": live.get("error"),
            }

        return {
            "success": True,
            "verified": True,
            "found": False,
            "ambiguous": bool(resolution.get("ambiguous")),
            "service": service_name,
            "query": query_text,
            "suggestions": resolution.get("suggestions") or [],
            "indexed_count": indexed_count,
        }

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

        launch = self.open_service(
            service_name,
            profile=profile or "main",
            force_new=False,
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
            "target_tab_id": launch.get("tab_id"),
        }, timeout=45.0)
        result.setdefault("service", service_name)
        result["chrome_profile"] = launch.get("profile_name") or launch.get("profile_directory")
        local_records = self.bridge.list_contacts(service_name, limit=5000)
        result["local_contact_count"] = len(local_records)
        result["local_group_count"] = sum(1 for r in local_records if r.get("type") == "group")
        result["local_typed_contact_count"] = sum(1 for r in local_records if r.get("type") == "contact")
        return result

    def read_and_reply(
        self,
        recipient: str,
        message: str,
        service: str = "whatsapp",
        profile: Optional[str] = "main",
    ) -> Dict[str, Any]:
        """Read the latest live message, then send the user's explicit reply."""
        live = self.read_messages(
            recipient=recipient,
            limit=1,
            service=service,
            profile=profile,
            incoming_only=True,
        )
        if not live.get("success") or not live.get("verified"):
            return {
                "success": False,
                "verified": False,
                "service": service,
                "recipient": recipient,
                "live_read": live,
                "error": live.get("error", "Could not verify the latest message before replying."),
            }

        sent = self.send(
            service=service,
            recipient=recipient,
            message=message,
            profile=profile,
        )
        return {
            "success": bool(sent.get("success") and sent.get("verified") and sent.get("sent")),
            "verified": bool(sent.get("verified") and sent.get("sent")),
            "service": service,
            "recipient": recipient,
            "latest_read": live.get("latest"),
            "messages": live.get("messages") or [],
            "reply_message": message,
            "send_result": sent,
            "sent": bool(sent.get("sent")),
            "error": sent.get("error"),
        }

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
