"""
MAYA Wake-Word Detector Subsystem
Performs real-time wake-word phrase spotting ("Maya", "Hey Maya")
to gate conversational activation and ignore background chatter.
"""
import re
from typing import Tuple, Optional

class WakeWordDetector:
    def __init__(self, wake_words: Optional[list] = None):
        self.wake_words = wake_words or ["maya", "hey maya", "ok maya", "okay maya", "hi maya"]
        self.is_active_listening = False

    def is_wake_word(self, transcript: str) -> bool:
        """Determines if the transcript triggers Maya wake phrase."""
        if not transcript:
            return False
        clean = transcript.lower().strip()
        # Direct wake words
        for w in self.wake_words:
            if w in clean:
                return True
        # Regex word-boundary check
        if re.search(r"\b(maya|hey maya)\b", clean):
            return True
        return False

    def strip_wake_word(self, transcript: str) -> str:
        """Removes the wake word prefix from the user's spoken command."""
        clean = transcript.strip()
        pattern = r"^(?:hey\s+|okay\s+|ok\s+|hi\s+)?maya[,\.\s]*"
        stripped = re.sub(pattern, "", clean, flags=re.IGNORECASE).strip()
        return stripped if stripped else clean

    def process_utterance(self, transcript: str, already_listening: bool = False) -> Tuple[bool, str]:
        """
        Processes an utterance through wake-word gating.
        Returns: (should_process, command_text)
        """
        if already_listening or self.is_active_listening:
            # Already in active conversation: process command directly
            command = self.strip_wake_word(transcript)
            return True, command

        if self.is_wake_word(transcript):
            self.is_active_listening = True
            command = self.strip_wake_word(transcript)
            return True, command

        # Gated out as ambient noise
        return False, ""
