"""
MAYA Vision Agent V2
Screen capture, active window geometry, error dialog detection, and structured scene analysis.
"""
import os
import time
import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import ImageGrab
from maya_core.config import SCREENSHOTS_DIR

try:
    import win32gui
    import win32process
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pygetwindow as gw
    HAS_GW = True
except ImportError:
    HAS_GW = False

class VisionAgent:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or SCREENSHOTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_screen(self, return_base64: bool = False) -> Dict[str, Any]:
        """Captures primary display screen and records file metadata."""
        try:
            screenshot = ImageGrab.grab()
            timestamp = int(time.time())
            filename = f"maya_screen_{timestamp}.png"
            filepath = self.output_dir / filename
            screenshot.save(str(filepath), "PNG")

            b64_data = None
            if return_base64:
                buffer = BytesIO()
                screenshot.save(buffer, format="JPEG", quality=75)
                b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return {
                "success": True,
                "filepath": str(filepath),
                "width": screenshot.width,
                "height": screenshot.height,
                "base64": b64_data,
                "timestamp": timestamp
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_windows(self) -> List[Dict[str, Any]]:
        """Enumerates active visible application windows on Windows with geometry."""
        windows = []
        if HAS_WIN32:
            def _enum(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title and not win32gui.IsIconic(hwnd):
                        rect = win32gui.GetWindowRect(hwnd)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 80 and h > 80:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            windows.append({
                                "title": title,
                                "hwnd": hwnd,
                                "pid": pid,
                                "bbox": [rect[0], rect[1], rect[2], rect[3]],
                                "width": w,
                                "height": h,
                                "is_active": hwnd == win32gui.GetForegroundWindow()
                            })
            try:
                win32gui.EnumWindows(_enum, None)
                return windows
            except Exception:
                pass

        if HAS_GW:
            try:
                for w in gw.getAllWindows():
                    if w.title and w.visible and w.width > 80 and w.height > 80:
                        windows.append({
                            "title": w.title,
                            "bbox": [w.left, w.top, w.left + w.width, w.top + w.height],
                            "width": w.width,
                            "height": w.height,
                            "is_active": w.isActive
                        })
            except Exception:
                pass

        return windows

    def analyze_screen(self) -> Dict[str, Any]:
        """
        Produces a structured scene description of visible windows,
        detecting error alerts, active workspace, and foreground focus.
        """
        cap = self.capture_screen(return_base64=False)
        windows = self.detect_windows()

        active_win = None
        for w in windows:
            if w.get("is_active"):
                active_win = w
                break

        # Detect error/warning dialogs in window titles
        dialog_elements = []
        for w in windows:
            t_low = w["title"].lower()
            if any(term in t_low for term in ["error", "fatal", "failed", "crash", "exception", "warning"]):
                dialog_elements.append({
                    "type": "error_dialog",
                    "title": w["title"],
                    "bbox": w["bbox"]
                })

        return {
            "screenshot_path": cap.get("filepath"),
            "display_resolution": f"{cap.get('width', 1920)}x{cap.get('height', 1080)}",
            "active_window": active_win["title"] if active_win else "Desktop",
            "active_window_details": active_win,
            "total_windows_detected": len(windows),
            "elements": dialog_elements,
            "scene_summary": f"Active: {active_win['title'] if active_win else 'Desktop'}. {len(dialog_elements)} alert dialog(s) found."
        }
