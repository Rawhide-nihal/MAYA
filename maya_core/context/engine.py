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

from maya_core.config import CACHE_DIR, SCREENSHOTS_DIR


class UnifiedContextEngine:
    def __init__(self, windows, vision, memory=None, ledger=None):
        self.windows = windows
        self.vision = vision
        self.memory = memory
        self.ledger = ledger
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
        try:
            clipboard = self.windows.get_clipboard() or ""
        except Exception:
            pass

        recent_actions = []
        if self.ledger is not None:
            try:
                recent_actions = self.ledger.get_recent_actions(limit=5)
            except Exception:
                recent_actions = []

        snapshot: Dict[str, Any] = {
            "timestamp": time.time(),
            "session_id": self.session_id,
            "active_window": active,
            "active_window_title": active.get("title", ""),
            "clipboard": clipboard[:4000],
            "recent_files": self._recent_files(),
            "recent_actions": recent_actions,
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
            else:
                session_path = source
        except Exception:
            session_path = source

        windows = self.vision.detect_windows()
        active = next((w for w in windows if w.get("is_active")), None)
        errors = self.vision.extract_visible_errors(str(session_path))

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

    def prompt_fragment(self) -> str:
        snapshot = self.snapshot(include_processes=False)
        parts = ["\nLIVE MAYA CONTEXT:"]
        title = snapshot.get("active_window_title")
        if title:
            parts.append(f"- Active window: {title}")

        clipboard = snapshot.get("clipboard")
        if clipboard:
            preview = clipboard[:300].replace("\n", " ")
            parts.append(f"- Clipboard preview: {preview}")

        recent_files = snapshot.get("recent_files") or []
        if recent_files:
            parts.append("- Recent files: " + "; ".join(item["name"] for item in recent_files[:5]))

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
