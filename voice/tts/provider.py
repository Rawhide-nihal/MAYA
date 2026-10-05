"""MAYA text-to-speech providers.

Kokoro is the preferred local TTS engine. A female-only pyttsx3 provider is
kept as a compatibility fallback; it never silently accepts an arbitrary
system-default voice.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import os
import tempfile

import numpy as np


class KokoroTTSProvider:
    name = "kokoro"

    def __init__(self, voice: str = "af_heart", speed: float = 1.0):
        self.voice = voice
        self.speed = speed
        self._pipeline = None
        self.last_error: Optional[str] = None

    def _ensure_loaded(self) -> bool:
        if self._pipeline is not None:
            return True
        try:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code="a")
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self._pipeline = None
            return False

    def synthesize_to_wav(self, text: str) -> Optional[str]:
        if not text.strip() or not self._ensure_loaded():
            return None
        try:
            import soundfile as sf
            chunks = []
            for _graphemes, _phonemes, audio in self._pipeline(
                text, voice=self.voice, speed=self.speed
            ):
                if audio is not None:
                    if hasattr(audio, "detach"):
                        audio = audio.detach().cpu().numpy()
                    chunks.append(np.asarray(audio, dtype=np.float32))
            if not chunks:
                return None
            pcm = np.concatenate(chunks)
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            sf.write(path, pcm, 24000)
            return path
        except Exception as exc:
            self.last_error = str(exc)
            return None


class FemalePyttsx3Provider:
    """Female-only Windows fallback. Returns None if no female voice is found."""

    name = "pyttsx3_female"

    FEMALE_HINTS = ("zira", "hazel", "eva", "aria", "jenny", "female")

    def __init__(self, rate: int = 175, volume: float = 0.95):
        self.engine = None
        self.voice_name: Optional[str] = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            selected = None
            for voice in voices:
                haystack = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                if any(hint in haystack for hint in self.FEMALE_HINTS):
                    selected = voice
                    break
            if selected is None:
                return
            engine.setProperty("voice", selected.id)
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)
            self.voice_name = getattr(selected, "name", selected.id)
            self.engine = engine
        except Exception:
            self.engine = None

    def synthesize_to_wav(self, text: str) -> Optional[str]:
        if self.engine is None or not text.strip():
            return None
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            self.engine.save_to_file(text, path)
            self.engine.runAndWait()
            if Path(path).exists() and Path(path).stat().st_size > 100:
                return path
        except Exception:
            pass
        try:
            os.unlink(path)
        except Exception:
            pass
        return None
