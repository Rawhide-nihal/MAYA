"""MAYA speech-to-text providers.

Local faster-whisper is preferred. Google Speech Recognition is an optional
online fallback. No heuristic or fabricated transcript is ever returned.
"""
from __future__ import annotations

from typing import Optional, Dict, Any
import os
import tempfile
import wave

try:
    import speech_recognition as sr
except ImportError:
    sr = None


class SpeechRecognitionProvider:
    def __init__(
        self,
        model_size: str = "base.en",
        allow_online_fallback: bool = True,
    ):
        self.model_size = model_size
        self.allow_online_fallback = allow_online_fallback
        self._whisper = None
        self._whisper_error: Optional[str] = None
        self.recognizer = sr.Recognizer() if sr else None

    def _ensure_whisper(self) -> bool:
        if self._whisper is not None:
            return True
        if self._whisper_error is not None:
            return False
        try:
            from faster_whisper import WhisperModel
            try:
                import torch
                use_cuda = torch.cuda.is_available()
            except Exception:
                use_cuda = False
            device = "cuda" if use_cuda else "cpu"
            compute_type = "float16" if use_cuda else "int8"
            self._whisper = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
            return True
        except Exception as exc:
            self._whisper_error = str(exc)
            return False

    def transcribe_wav_file(self, wav_path: str) -> Dict[str, Any]:
        """Transcribe a real WAV file. Local STT is always attempted first."""
        if self._ensure_whisper():
            try:
                segments, info = self._whisper.transcribe(
                    wav_path,
                    beam_size=3,
                    vad_filter=True,
                    language="en",
                )
                text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
                if text:
                    return {
                        "success": True,
                        "transcript": text,
                        "provider": "faster_whisper_local",
                        "language": getattr(info, "language", "en"),
                    }
            except Exception as exc:
                local_error = str(exc)
            else:
                local_error = "No speech detected"
        else:
            local_error = self._whisper_error or "faster-whisper unavailable"

        if self.allow_online_fallback and self.recognizer and sr:
            try:
                with sr.AudioFile(wav_path) as source:
                    audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio).strip()
                if text:
                    return {
                        "success": True,
                        "transcript": text,
                        "provider": "google_online_fallback",
                    }
            except Exception as exc:
                return {
                    "success": False,
                    "transcript": "",
                    "error": f"Local STT failed ({local_error}); online fallback failed ({exc})",
                }

        return {
            "success": False,
            "transcript": "",
            "error": f"OFFLINE_STT_UNAVAILABLE: {local_error}",
        }

    def transcribe_audio_data(self, audio_data: Any) -> Dict[str, Any]:
        """Compatibility path for SpeechRecognition AudioData."""
        if audio_data is None:
            return {"success": False, "transcript": "", "error": "No audio"}
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(audio_data.get_wav_data(convert_rate=16000, convert_width=2))
            return self.transcribe_wav_file(path)
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
