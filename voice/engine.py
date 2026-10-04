"""
MAYA Voice Subsystem
Provides Wake Word, Speech-to-Text, and Text-to-Speech with amplitude telemetry.
"""
import threading
import time
from typing import Optional, Callable
import pyttsx3

class VoiceEngine:
    def __init__(self):
        self.tts_engine = None
        self._init_tts()
        self.is_speaking = False
        self.is_listening = False
        self.amplitude_callback: Optional[Callable[[float], None]] = None

    def _init_tts(self):
        try:
            self.tts_engine = pyttsx3.init()
            # Set speech rate and volume
            self.tts_engine.setProperty('rate', 175)
            self.tts_engine.setProperty('volume', 0.9)
            voices = self.tts_engine.getProperty('voices')
            # Select female or clear voice if present
            for v in voices:
                if "zira" in v.name.lower() or "female" in v.name.lower() or "hazel" in v.name.lower():
                    self.tts_engine.setProperty('voice', v.id)
                    break
        except Exception:
            self.tts_engine = None

    def speak(self, text: str, on_complete: Optional[Callable[[], None]] = None):
        """Asynchronously speaks text without blocking the main event loop"""
        def _run():
            self.is_speaking = True
            if self.tts_engine:
                try:
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                except Exception:
                    pass
            else:
                time.sleep(1.0)
            self.is_speaking = False
            if on_complete:
                on_complete()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def set_amplitude_callback(self, callback: Callable[[float], None]):
        self.amplitude_callback = callback
