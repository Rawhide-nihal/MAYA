"""Thread-safe command bridge between MAYA Core and the MAYA Chrome extension."""
from __future__ import annotations

import threading
import time
import uuid
import mimetypes
import os
from collections import deque
from typing import Any, Deque, Dict, Optional


class CommunicationBridge:
    def __init__(self):
        self._lock = threading.RLock()
        self._queues: Dict[str, Deque[str]] = {
            "gmail": deque(),
            "whatsapp": deque(),
            "telegram": deque(),
        }
        self._commands: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, threading.Event] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._last_extension_seen: Optional[float] = None
        self._browser_context: Dict[str, Any] = {}

    def heartbeat(self) -> None:
        with self._lock:
            self._last_extension_seen = time.time()

    def update_browser_context(self, context: Dict[str, Any]) -> None:
        with self._lock:
            self._last_extension_seen = time.time()
            self._browser_context = {
                "title": str(context.get("title", ""))[:500],
                "url": str(context.get("url", ""))[:2000],
                "window_id": context.get("window_id"),
                "tab_id": context.get("tab_id"),
                "tab_count": context.get("tab_count"),
                "updated_at": time.time(),
            }

    def get_browser_context(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._browser_context)

    def submit(self, command: Dict[str, Any], timeout: float = 25.0) -> Dict[str, Any]:
        service = str(command.get("service", "")).lower().strip()
        if service not in self._queues:
            return {"success": False, "verified": False, "error": f"Unsupported communication service: {service}"}

        command_id = uuid.uuid4().hex
        payload = dict(command)
        payload["command_id"] = command_id
        payload["created_at"] = time.time()
        payload["status"] = "queued"

        event = threading.Event()
        with self._lock:
            self._commands[command_id] = payload
            self._events[command_id] = event
            self._queues[service].append(command_id)

        if not event.wait(timeout=max(1.0, timeout)):
            with self._lock:
                existing = self._commands.get(command_id)
                if existing:
                    existing["status"] = "timed_out"
            return {
                "success": False,
                "verified": False,
                "command_id": command_id,
                "error": (
                    "MAYA Chrome Bridge did not respond in time. "
                    "Make sure Chrome is open on the requested profile and the MAYA Browser Bridge extension is enabled."
                ),
            }

        with self._lock:
            result = dict(self._results.pop(command_id, {}))
            self._events.pop(command_id, None)
        result.setdefault("command_id", command_id)
        return result

    def next_command(self, service: str, tab_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        service = service.lower().strip()
        if service not in self._queues:
            return None

        self.heartbeat()
        with self._lock:
            queue = self._queues[service]
            attempts = len(queue)
            for _ in range(attempts):
                command_id = queue.popleft()
                command = self._commands.get(command_id)
                if not command or command.get("status") != "queued":
                    continue

                target_tab_id = command.get("target_tab_id")
                if target_tab_id is not None and int(target_tab_id) != int(tab_id or -1):
                    # This command was explicitly bound to the Chrome tab that
                    # was active when the user said "current chat".
                    queue.append(command_id)
                    continue

                command["status"] = "dispatched"
                command["dispatched_at"] = time.time()

                # Never reveal an arbitrary local filesystem path to page content.
                public_command = dict(command)
                attachment_path = public_command.pop("attachment_path", None)
                public_command.pop("target_tab_id", None)
                if attachment_path:
                    public_command["has_attachment"] = True
                    public_command["attachment_name"] = os.path.basename(attachment_path)
                    public_command["attachment_size"] = os.path.getsize(attachment_path)
                    public_command["attachment_mime"] = (
                        mimetypes.guess_type(attachment_path)[0]
                        or "application/octet-stream"
                    )
                else:
                    public_command["has_attachment"] = False
                return public_command
        return None

    def get_attachment(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Return the attachment bound to an exact dispatched communication command."""
        with self._lock:
            command = self._commands.get(command_id)
            if not command or command.get("status") != "dispatched":
                return None
            path = command.get("attachment_path")
            if not path or not os.path.isfile(path):
                return None
            return {
                "path": path,
                "name": os.path.basename(path),
                "mime_type": mimetypes.guess_type(path)[0] or "application/octet-stream",
                "size_bytes": os.path.getsize(path),
            }

    def complete(self, command_id: str, result: Dict[str, Any]) -> bool:
        with self._lock:
            command = self._commands.get(command_id)
            event = self._events.get(command_id)
            if not command or not event:
                return False
            command["status"] = "completed"
            command["completed_at"] = time.time()
            self._results[command_id] = dict(result)
            event.set()
            return True

    def status(self) -> Dict[str, Any]:
        with self._lock:
            pending = sum(
                1 for command in self._commands.values()
                if command.get("status") in {"queued", "dispatched"}
            )
            last_seen = self._last_extension_seen
        return {
            "connected_recently": bool(last_seen and (time.time() - last_seen) < 5.0),
            "last_extension_seen": last_seen,
            "pending_commands": pending,
            "browser_context": self.get_browser_context(),
        }


communication_bridge = CommunicationBridge()
