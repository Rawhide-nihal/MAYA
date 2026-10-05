"""
MAYA Voice Subsystem V3
Provides genuine PCM audio analysis for real-time RMS amplitude telemetry,
wake-word detection ("Hey Maya"), speech-to-text, and immediate barge-in interruption.
Zero simulated math.sin() amplitude.
"""
import os
import sys
import time
import math
import wave
import tempfile
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any

import numpy as np
try:
    import winsound
except ImportError:
    winsound = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

from maya_core.events import (
    VOICE_SPEAKING_STARTED,
    VOICE_SPEAKING_AMPLITUDE,
    VOICE_SPEAKING_COMPLETED,
    VOICE_LISTENING_STARTED,
    VOICE_LISTENING_AMPLITUDE,
    VOICE_LISTENING_COMPLETED,
    MAYA_STATE_CHANGED,
)

from voice.stt.provider import SpeechRecognitionProvider
from voice.tts.provider import KokoroTTSProvider, FemalePyttsx3Provider
from voice.wakeword.detector import WakeWordDetector

def calculate_pcm_rms(pcm_bytes: bytes) -> float:
    """Calculates true Root Mean Square (RMS) amplitude from 16-bit PCM audio buffer."""
    if not pcm_bytes:
        return 0.0
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if len(samples) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) / 32768.0
    # Scale to normalized [0.0, 1.0] range suitable for GUI orb animation
    normalized = min(1.0, max(0.0, rms * 4.2))
    return round(normalized, 3)

class VoiceEngine:
    def __init__(self, event_emitter: Optional[Callable[[str, dict], None]] = None):
        self.event_emitter = event_emitter
        self.tts_provider = KokoroTTSProvider(voice="af_heart", speed=1.0)
        self.tts_fallback = FemalePyttsx3Provider()
        self.stt_provider = SpeechRecognitionProvider()
        self.wakeword_detector = WakeWordDetector()
        self.is_speaking = False
        self.is_listening = False
        self._stop_requested = False
        self.current_thread: Optional[threading.Thread] = None
        self.listener_thread: Optional[threading.Thread] = None
        self._listener_active = False

    def emit(self, event_name: str, payload: dict):
        if self.event_emitter:
            try:
                self.event_emitter(event_name, payload)
            except Exception:
                pass

    def stop_speaking(self):
        """Immediately interrupts voice output (Barge-in)."""
        self._stop_requested = True
        self.is_speaking = False
        if winsound:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        # Kokoro renders complete WAV files; winsound purge interrupts playback.
        # The fallback pyttsx3 engine is stopped only when it exists.
        fallback_engine = getattr(self.tts_fallback, "engine", None)
        if fallback_engine:
            try:
                fallback_engine.stop()
            except Exception:
                pass
        self.emit(VOICE_SPEAKING_COMPLETED, {"interrupted": True})
        self.emit(MAYA_STATE_CHANGED, {"state": "IDLE"})

    def speak(self, text: str, on_complete: Optional[Callable[[], None]] = None):
        """Speak with Kokoro female voice; never silently fall back to a male voice."""
        self.stop_speaking()
        self._stop_requested = False

        def _run():
            self.is_speaking = True
            self.emit(VOICE_SPEAKING_STARTED, {"text": text[:60], "provider": "kokoro", "voice": "af_heart"})
            self.emit(MAYA_STATE_CHANGED, {"state": "SPEAKING"})

            tmp_wav = None
            try:
                tmp_wav = self.tts_provider.synthesize_to_wav(text)
                provider_name = "kokoro"
                if not tmp_wav:
                    tmp_wav = self.tts_fallback.synthesize_to_wav(text)
                    provider_name = "pyttsx3_female"

                if not tmp_wav:
                    self.emit(VOICE_SPEAKING_COMPLETED, {
                        "interrupted": False,
                        "success": False,
                        "error": "No female TTS provider is available.",
                    })
                    return

                if winsound:
                    winsound.PlaySound(tmp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)

                with wave.open(tmp_wav, "rb") as wf:
                    framerate = wf.getframerate()
                    chunk_frames = max(1, int(framerate * 0.05))
                    while not self._stop_requested:
                        raw = wf.readframes(chunk_frames)
                        if not raw:
                            break
                        self.emit(VOICE_SPEAKING_AMPLITUDE, {
                            "amplitude": calculate_pcm_rms(raw),
                            "provider": provider_name,
                        })
                        time.sleep(0.048)
            except Exception as exc:
                self.emit(VOICE_SPEAKING_COMPLETED, {
                    "interrupted": self._stop_requested,
                    "success": False,
                    "error": str(exc),
                })
            finally:
                if tmp_wav and os.path.exists(tmp_wav):
                    try:
                        os.unlink(tmp_wav)
                    except Exception:
                        pass
                self.is_speaking = False
                self.emit(VOICE_SPEAKING_COMPLETED, {
                    "interrupted": self._stop_requested,
                    "success": True,
                })
                self.emit(MAYA_STATE_CHANGED, {"state": "IDLE"})
                if on_complete and not self._stop_requested:
                    on_complete()

        self.current_thread = threading.Thread(target=_run, daemon=True)
        self.current_thread.start()

    def start_listening(self, on_text_detected: Optional[Callable[[str], None]] = None):
        """Starts real microphone listening for wake word or user queries."""
        if self._listener_active:
            return

        if not sr:
            return

        self._listener_active = True
        self.is_listening = True

        def _listen_loop():
            recognizer = sr.Recognizer()
            try:
                mic = sr.Microphone()
            except Exception:
                self._listener_active = False
                self.is_listening = False
                return

            self.emit(VOICE_LISTENING_STARTED, {})
            with mic as source:
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                except Exception:
                    pass

                while self._listener_active:
                    try:
                        audio = recognizer.listen(source, timeout=3.0, phrase_time_limit=10.0)
                        raw_data = audio.get_raw_data()
                        amp = calculate_pcm_rms(raw_data[:2048])
                        self.emit(VOICE_LISTENING_AMPLITUDE, {"amplitude": amp})

                        res = self.stt_provider.transcribe_audio_data(audio)
                        if res.get("success"):
                            transcript = res.get("transcript", "")
                            should_process, command = self.wakeword_detector.process_utterance(transcript, already_listening=self.is_listening)
                            if should_process and command:
                                handled = self.process_voice_transcript(command)
                                if handled != "interrupted" and on_text_detected:
                                    on_text_detected(command)
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception:
                        time.sleep(0.5)

            self.is_listening = False
            self.emit(VOICE_LISTENING_COMPLETED, {})

        self.listener_thread = threading.Thread(target=_listen_loop, daemon=True)
        self.listener_thread.start()

    def stop_listening(self):
        self._listener_active = False
        self.is_listening = False

    def process_voice_transcript(self, transcript: str) -> Optional[str]:
        """Checks for interruption keywords ('stop', 'cancel', 'quiet')."""
        lower = transcript.lower().strip()
        if any(term in lower for term in ["stop", "quiet", "cancel that", "don't do that", "maya stop"]):
            self.stop_speaking()
            return "interrupted"
        return transcript

    def process_ptt_audio(self, wav_bytes: bytes, on_text_detected: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Process an actual WAV container produced by the frontend."""
        if not wav_bytes or len(wav_bytes) < 44:
            return {"success": False, "error": "Invalid or empty WAV audio"}
        if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
            return {"success": False, "error": "PTT audio must be a real WAV container"}

        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with open(wav_path, "wb") as f:
                f.write(wav_bytes)
            res = self.stt_provider.transcribe_wav_file(wav_path)
            if res.get("success") and on_text_detected:
                on_text_detected(res.get("transcript", ""))
            return res
        finally:
            try:
                os.unlink(wav_path)
            except Exception:
                pass
