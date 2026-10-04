"""
MAYA Vision Agent
Screen capture, active window detection, and visual inspection subsystem.
"""
import os
import time
import base64
from io import BytesIO
from typing import Dict, Any, List, Optional
from PIL import ImageGrab
import pygetwindow as gw

class VisionAgent:
    def __init__(self, output_dir: str = "d:\\MAYA\\screenshots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def capture_screen(self, return_base64: bool = False) -> Dict[str, Any]:
        """Captures the primary monitor screen"""
        try:
            screenshot = ImageGrab.grab()
            timestamp = int(time.time())
            filename = f"maya_screen_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            screenshot.save(filepath, "PNG")

            b64_data = None
            if return_base64:
                buffer = BytesIO()
                screenshot.save(buffer, format="JPEG", quality=75)
                b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return {
                "success": True,
                "filepath": filepath,
                "width": screenshot.width,
                "height": screenshot.height,
                "base64": b64_data,
                "timestamp": timestamp
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_windows(self) -> List[Dict[str, Any]]:
        """Enumerates visible application windows on Windows"""
        windows = []
        try:
            all_windows = gw.getAllWindows()
            for w in all_windows:
                if w.title and w.visible and w.width > 50 and w.height > 50:
                    windows.append({
                        "title": w.title,
                        "left": w.left,
                        "top": w.top,
                        "width": w.width,
                        "height": w.height,
                        "is_active": w.isActive
                    })
        except Exception as e:
            pass
        return windows
