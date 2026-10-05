"""Unified live session context for MAYA.

Combines conversation-adjacent PC state, screenshots, attachments and pronoun/reference
resolution without persisting sensitive transient context by default.
"""
from __future__ import annotations

import os
import re
import shutil
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from PIL import Image, ImageChops, ImageStat

from maya_core.config import CACHE_DIR, SCREENSHOTS_DIR, settings
from agents.vision.ocr import windows_ocr


class UnifiedContextEngine:
    def __init__(self, windows, vision, memory=None, ledger=None, browser_context_source=None):
        self.windows = windows
        self.vision = vision
        self.memory = memory
        self.ledger = ledger
        self.browser_context_source = browser_context_source
        self.session_id = uuid.uuid4().hex[:12]
        self.session_dir = CACHE_DIR / "sessions" / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.screenshots: Deque[Dict[str, Any]] = deque(maxlen=20)
        self.attachments: Deque[Dict[str, Any]] = deque(maxlen=20)
        self.entities: Deque[Dict[str, Any]] = deque(maxlen=40)
        self.named_refs: Dict[str, Dict[str, Any]] = {}
        self.last_snapshot: Dict[str, Any] = {}

    def _active_window(self) -> Dict[str, Any]:
        try:
            windows = self.windows.list_windows()
            if not windows:
                return {}
            if hasattr(self.windows, "_find_window_hwnd"):
                try:
                    hwnd = self.windows._find_window_hwnd(None)
                    for item in windows:
                        if hwnd and item.get("hwnd") == hwnd:
                            return item
                except Exception:
                    pass
            return windows[0]
        except Exception:
            return {}

    def _recent_files(self, limit: int = 8) -> List[Dict[str, Any]]:
        roots = []
        home = Path.home()
        for candidate in [home / "Downloads", home / "Desktop"]:
            if candidate.exists():
                roots.append(candidate)

        items: List[Dict[str, Any]] = []
        cutoff = time.time() - (24 * 60 * 60)
        for root in roots:
            try:
                for path in root.iterdir():
                    if not path.is_file():
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    if stat.st_mtime < cutoff:
                        continue
                    items.append({
                        "path": str(path),
                        "name": path.name,
                        "modified_at": stat.st_mtime,
                        "size_bytes": stat.st_size,
                    })
            except OSError:
                continue

        items.sort(key=lambda x: x["modified_at"], reverse=True)
        return items[:limit]

    def snapshot(self, include_processes: bool = False) -> Dict[str, Any]:
        active = self._active_window()
        clipboard = ""
        if settings.get("context_clipboard_enabled", True):
            try:
                clipboard = self.windows.get_clipboard() or ""
            except Exception:
                pass

        battery = None
        try:
            import psutil
            sensor = psutil.sensors_battery()
            if sensor is not None:
                battery = {
                    "percent": round(float(sensor.percent), 1),
                    "plugged": bool(sensor.power_plugged),
                    "seconds_left": getattr(sensor, "secsleft", None),
                }
        except Exception:
            battery = None

        recent_actions = []
        if self.ledger is not None:
            try:
                recent_actions = self.ledger.get_recent_actions(limit=5)
            except Exception:
                recent_actions = []

        browser_context = {}
        if self.browser_context_source is not None:
            try:
                getter = getattr(self.browser_context_source, "get_browser_context", None)
                if callable(getter):
                    browser_context = getter() or {}
            except Exception:
                browser_context = {}

        selected_files = []
        try:
            selected_files = self.windows.get_explorer_selection()
        except Exception:
            selected_files = []

        snapshot: Dict[str, Any] = {
            "timestamp": time.time(),
            "session_id": self.session_id,
            "active_window": active,
            "active_window_title": active.get("title", ""),
            "active_process": active.get("process_name"),
            "selected_files": selected_files,
            "clipboard": clipboard[:4000],
            "recent_files": self._recent_files() if settings.get("context_recent_files_enabled", True) else [],
            "recent_actions": recent_actions,
            "battery": battery,
            "browser_context": browser_context,
            "latest_screenshot": self.screenshots[-1] if self.screenshots else None,
            "previous_screenshot": self.screenshots[-2] if len(self.screenshots) > 1 else None,
            "latest_attachment": self.attachments[-1] if self.attachments else None,
        }

        if include_processes:
            try:
                snapshot["processes"] = self.windows.list_processes(limit=10)
            except Exception:
                snapshot["processes"] = []

        self.last_snapshot = snapshot
        return snapshot

    def remember_entity(self, kind: str, value: Any, label: Optional[str] = None) -> Dict[str, Any]:
        entity = {
            "id": uuid.uuid4().hex[:12],
            "kind": kind,
            "value": value,
            "label": label or kind,
            "timestamp": time.time(),
        }
        self.entities.append(entity)
        if label:
            self.named_refs[label.lower().strip()] = entity
        return entity

    def register_attachment(self, metadata: Dict[str, Any], label: Optional[str] = None) -> Dict[str, Any]:
        record = dict(metadata)
        record.setdefault("id", uuid.uuid4().hex[:12])
        record.setdefault("timestamp", time.time())
        record.setdefault("kind", "attachment")
        self.attachments.append(record)
        self.remember_entity("attachment", record, label=label or "latest attachment")
        return record

    def capture_screen(self, label: Optional[str] = None, save: bool = False) -> Dict[str, Any]:
        cap = self.vision.capture_screen(return_base64=False)
        if not cap.get("success"):
            return cap

        source = Path(cap["filepath"])
        session_path = self.session_dir / source.name
        try:
            if source.resolve() != session_path.resolve():
                shutil.copy2(source, session_path)
                # capture_screen historically writes to the permanent screenshot
                # directory. Context captures are temporary by default, so remove
                # that transient source after safely copying it into this session.
                try:
                    if source.parent.resolve() == SCREENSHOTS_DIR.resolve():
                        source.unlink()
                except Exception:
                    pass
            else:
                session_path = source
        except Exception:
            session_path = source

        windows = self.vision.detect_windows()
        active = next((w for w in windows if w.get("is_active")), None)
        errors = self.vision.extract_visible_errors(str(session_path))

        ocr = {"success": False, "available": False, "text": "", "lines": []}
        try:
            ocr = windows_ocr.recognize_file(str(session_path))
        except Exception:
            pass

        if ocr.get("success"):
            for line in ocr.get("lines", []):
                text = str(line.get("text", ""))
                low = text.lower()
                if any(term in low for term in [
                    "error", "exception", "failed", "failure",
                    "fatal", "warning", "traceback", "not responding"
                ]):
                    errors.append({
                        "source": "windows_ocr",
                        "text": text,
                        "words": line.get("words", []),
                        "severity": "CRITICAL" if any(term in low for term in ["fatal", "not responding"]) else "WARNING",
                        "description": f"OCR alert text: {text}",
                    })

        record = {
            "id": uuid.uuid4().hex[:12],
            "kind": "screenshot",
            "filepath": str(session_path),
            "original_filepath": str(source),
            "timestamp": cap.get("timestamp", time.time()),
            "width": cap.get("width"),
            "height": cap.get("height"),
            "active_window": active,
            "visible_errors": errors,
            "ocr": ocr,
            "label": label,
            "saved": False,
        }
        self.screenshots.append(record)
        self.remember_entity("screenshot", record, label=label or "latest screenshot")

        if save:
            return self.save_screenshot(record["id"], label=label)
        return {"success": True, "verified": True, **record}

    def _find_screenshot(self, ref: Optional[str]) -> Optional[Dict[str, Any]]:
        if not self.screenshots:
            return None
        if not ref or ref.lower() in {"latest", "this", "that", "current", "latest screenshot"}:
            return self.screenshots[-1]
        if ref.lower() in {"previous", "before", "previous screenshot"}:
            return self.screenshots[-2] if len(self.screenshots) > 1 else None

        ref_lower = ref.lower().strip()

        # Time-relative references such as "screenshot from five minutes ago".
        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "fifteen": 15, "twenty": 20, "thirty": 30,
        }
        time_match = re.search(
            r"(?:(\d+)|(" + "|".join(number_words.keys()) + r"))\s+"
            r"(second|seconds|minute|minutes|hour|hours)\s+ago",
            ref_lower
        )
        if time_match:
            amount = int(time_match.group(1)) if time_match.group(1) else number_words[time_match.group(2)]
            unit = time_match.group(3)
            multiplier = 1
            if unit.startswith("minute"):
                multiplier = 60
            elif unit.startswith("hour"):
                multiplier = 3600
            target = time.time() - (amount * multiplier)
            candidates = list(self.screenshots)
            if candidates:
                nearest = min(candidates, key=lambda item: abs(float(item.get("timestamp", 0)) - target))
                tolerance = max(90, amount * multiplier * 0.75)
                if abs(float(nearest.get("timestamp", 0)) - target) <= tolerance:
                    return nearest

        if ref_lower in self.named_refs:
            entity = self.named_refs[ref_lower]
            value = entity.get("value")
            if isinstance(value, dict) and value.get("kind") == "screenshot":
                return value

        for record in reversed(self.screenshots):
            if record.get("id") == ref or str(record.get("label") or "").lower() == ref_lower:
                return record
        return None

    def save_screenshot(self, ref: Optional[str] = None, label: Optional[str] = None) -> Dict[str, Any]:
        record = self._find_screenshot(ref)
        if not record:
            return {"success": False, "verified": False, "error": "No matching screenshot is available in this session."}

        src = Path(record["filepath"])
        if not src.exists():
            return {"success": False, "verified": False, "error": "Screenshot file no longer exists."}

        safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", (label or record.get("label") or "saved").strip()).strip("_")
        dest = SCREENSHOTS_DIR / f"maya_{safe_label}_{int(time.time())}.png"
        shutil.copy2(src, dest)
        record["saved"] = True
        record["saved_path"] = str(dest)
        if label:
            record["label"] = label
            self.named_refs[label.lower().strip()] = {
                "id": record["id"],
                "kind": "screenshot",
                "value": record,
                "label": label,
                "timestamp": time.time(),
            }
        return {"success": True, "verified": dest.exists(), **record}

    def compare_screenshots(self, newer_ref: Optional[str] = "latest", older_ref: Optional[str] = "previous") -> Dict[str, Any]:
        newer = self._find_screenshot(newer_ref)
        older = self._find_screenshot(older_ref)
        if not newer or not older:
            return {
                "success": False,
                "verified": False,
                "error": "Two screenshots are required for comparison.",
            }

        try:
            with Image.open(newer["filepath"]).convert("RGB") as a, Image.open(older["filepath"]).convert("RGB") as b:
                if a.size != b.size:
                    b = b.resize(a.size)
                diff = ImageChops.difference(a, b)
                stat = ImageStat.Stat(diff)
                mean = sum(stat.mean) / len(stat.mean)
                changed_percent = min(100.0, (mean / 255.0) * 100.0)
                bbox = diff.getbbox()
        except Exception as exc:
            return {"success": False, "verified": False, "error": f"Screenshot comparison failed: {exc}"}

        newer_title = ((newer.get("active_window") or {}).get("title") or "")
        older_title = ((older.get("active_window") or {}).get("title") or "")
        return {
            "success": True,
            "verified": True,
            "newer_id": newer["id"],
            "older_id": older["id"],
            "pixel_change_percent": round(changed_percent, 2),
            "visual_change_detected": bool(bbox),
            "changed_region": list(bbox) if bbox else None,
            "active_window_changed": newer_title != older_title,
            "newer_window": newer_title,
            "older_window": older_title,
            "newer_errors": newer.get("visible_errors", []),
            "older_errors": older.get("visible_errors", []),
        }

    def resolve_reference(self, phrase: str) -> Optional[Dict[str, Any]]:
        """Resolve natural references against recent session entities."""
        raw = (phrase or "").strip().lower()
        if not raw:
            return None

        if raw in self.named_refs:
            return self.named_refs[raw]

        if "screenshot" in raw or raw in {"this", "that", "before", "previous", "latest"}:
            record = self._find_screenshot(raw)
            if record:
                return {"kind": "screenshot", "value": record, "label": raw}

        if any(word in raw for word in ["attachment", "file", "document"]) and self.attachments:
            return {"kind": "attachment", "value": self.attachments[-1], "label": raw}

        if raw in {"it", "that", "this"} and self.entities:
            return self.entities[-1]

        if raw in {"before", "previous"} and len(self.entities) > 1:
            return self.entities[-2]

        return None

    def prompt_fragment(self, snapshot: Optional[Dict[str, Any]] = None) -> str:
        snapshot = snapshot or self.snapshot(include_processes=False)
        parts = ["\nLIVE MAYA CONTEXT:"]
        title = snapshot.get("active_window_title")
        if title:
            process_name = snapshot.get("active_process")
            suffix = f" [process: {process_name}]" if process_name else ""
            parts.append(f"- Active window: {title}{suffix}")

        selected_files = snapshot.get("selected_files") or []
        if selected_files:
            parts.append("- Selected File Explorer item(s): " + "; ".join(selected_files[:8]))

        clipboard = snapshot.get("clipboard")
        if clipboard:
            preview = clipboard[:300].replace("\n", " ")
            parts.append(f"- Clipboard preview: {preview}")

        recent_files = snapshot.get("recent_files") or []
        if recent_files:
            parts.append("- Recent files: " + "; ".join(item["name"] for item in recent_files[:5]))

        browser_context = snapshot.get("browser_context") or {}
        if browser_context.get("title") or browser_context.get("url"):
            parts.append(
                f"- Active browser tab: {browser_context.get('title') or 'Untitled'} "
                f"({browser_context.get('url') or 'URL unavailable'})"
            )

        battery = snapshot.get("battery")
        if battery:
            parts.append(
                f"- Battery: {battery.get('percent')}% "
                f"({'plugged in' if battery.get('plugged') else 'on battery'})"
            )

        recent_actions = snapshot.get("recent_actions") or []
        failed_actions = [a for a in recent_actions if str(a.get("status", "")).lower() == "failed"]
        if failed_actions:
            parts.append(f"- Recent failed actions: {len(failed_actions)}")

        latest = snapshot.get("latest_screenshot")
        if latest:
            parts.append(
                f"- Latest screenshot: id={latest.get('id')} "
                f"label={latest.get('label') or 'unnamed'} "
                f"window={((latest.get('active_window') or {}).get('title') or 'unknown')}"
            )

        previous = snapshot.get("previous_screenshot")
        if previous:
            parts.append(f"- Previous screenshot: id={previous.get('id')}")

        attachment = snapshot.get("latest_attachment")
        if attachment:
            parts.append(
                f"- Latest attachment: {attachment.get('name') or attachment.get('path')} "
                f"type={attachment.get('type', 'unknown')}"
            )
            context_text = str(attachment.get("context_text") or "")
            if context_text:
                parts.append("- Attachment context:\n" + context_text[:10000])

        parts.append(
            "- Resolve words like 'this', 'that', 'it', 'before', 'previous' using this live session context when unambiguous. "
            "If ambiguous, ask instead of guessing."
        )
        return "\n".join(parts)

    def session_summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "screenshots": list(self.screenshots),
            "attachments": list(self.attachments),
            "entities": list(self.entities)[-10:],
            "named_references": list(self.named_refs.keys()),
            "snapshot": self.last_snapshot or self.snapshot(),
        }
