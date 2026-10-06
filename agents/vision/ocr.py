"""Windows-native OCR provider for MAYA vision.

Uses Windows.Media.Ocr locally. No cloud upload and no external Tesseract binary.
Returns explicit availability/failure information instead of fabricated text.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image


class WindowsOcrProvider:
    def __init__(self):
        self.last_error = None

    def is_available(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            from winrt.windows.media.ocr import OcrEngine
            return OcrEngine.try_create_from_user_profile_languages() is not None
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def _software_bitmap_from_image(self, image: Image.Image):
        from winrt.windows.graphics.imaging import (
            BitmapAlphaMode,
            BitmapPixelFormat,
            SoftwareBitmap,
        )
        from winrt.windows.storage.streams import DataWriter

        rgba = image.convert("RGBA")
        raw = rgba.tobytes()
        writer = DataWriter()
        writer.write_bytes(list(raw))
        buffer = writer.detach_buffer()
        return SoftwareBitmap.create_copy_from_buffer(
            buffer,
            BitmapPixelFormat.RGBA8,
            rgba.width,
            rgba.height,
            BitmapAlphaMode.STRAIGHT,
        )

    async def _recognize_async(self, image: Image.Image) -> Dict[str, Any]:
        from winrt.windows.media.ocr import OcrEngine

        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return {
                "success": False,
                "available": False,
                "text": "",
                "lines": [],
                "error": "Windows OCR has no recognizer for the installed user languages.",
            }

        bitmap = self._software_bitmap_from_image(image)
        result = await engine.recognize_async(bitmap)

        lines: List[Dict[str, Any]] = []
        for line_index, line in enumerate(result.lines):
            words = []
            for word in line.words:
                rect = word.bounding_rect
                words.append({
                    "text": str(word.text),
                    "bounds": {
                        "left": round(float(rect.x), 2),
                        "top": round(float(rect.y), 2),
                        "right": round(float(rect.x + rect.width), 2),
                        "bottom": round(float(rect.y + rect.height), 2),
                    },
                })
            lines.append({
                "index": line_index,
                "text": str(line.text),
                "words": words,
            })

        return {
            "success": True,
            "available": True,
            "text": str(result.text or ""),
            "lines": lines,
            "text_angle": (
                float(result.text_angle.value)
                if getattr(result, "text_angle", None) is not None
                else None
            ),
        }

    def recognize_image(self, image: Image.Image) -> Dict[str, Any]:
        if sys.platform != "win32":
            return {
                "success": False,
                "available": False,
                "text": "",
                "lines": [],
                "error": "Windows OCR is only available on Windows.",
            }
        try:
            return asyncio.run(self._recognize_async(image))
        except RuntimeError as exc:
            # Some host threads may already have an event loop. Run OCR in a
            # dedicated loop so the synchronous MAYA agents stay deterministic.
            if "asyncio.run()" not in str(exc):
                self.last_error = str(exc)
                return {
                    "success": False,
                    "available": False,
                    "text": "",
                    "lines": [],
                    "error": str(exc),
                }
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._recognize_async(image))
            except Exception as nested:
                self.last_error = str(nested)
                return {
                    "success": False,
                    "available": False,
                    "text": "",
                    "lines": [],
                    "error": str(nested),
                }
            finally:
                loop.close()
        except Exception as exc:
            self.last_error = str(exc)
            return {
                "success": False,
                "available": False,
                "text": "",
                "lines": [],
                "error": str(exc),
            }

    def recognize_file(self, filepath: str) -> Dict[str, Any]:
        path = Path(filepath)
        if not path.exists():
            return {
                "success": False,
                "available": False,
                "text": "",
                "lines": [],
                "error": f"Image file not found: {path}",
            }
        try:
            with Image.open(path) as image:
                return self.recognize_image(image.copy())
        except Exception as exc:
            return {
                "success": False,
                "available": False,
                "text": "",
                "lines": [],
                "error": f"Could not open image for OCR: {exc}",
            }


windows_ocr = WindowsOcrProvider()
