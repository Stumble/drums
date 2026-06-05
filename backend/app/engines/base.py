"""The single interface every transcription engine implements.

Swapping the model (heuristic <-> omnizart <-> MT3 <-> your own CRNN) means
adding one class here. Nothing downstream changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import TranscriptionResult


class TranscriptionEngine(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: str, bpm: float) -> TranscriptionResult:
        """Analyze an audio file and return detected drum hits."""
        raise NotImplementedError
