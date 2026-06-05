"""Shared data types for the drumscribe pipeline.

A DrumHit is the engine-independent currency of the app: every transcription
engine (heuristic, omnizart, MT3, ...) must emit a list of these, and every
downstream stage (quantize, notation) consumes only these. That keeps the
model swappable without touching the rest of the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

# Canonical drum voice names used throughout the app. Engines must map their
# own label space (GM MIDI notes, model class indices, ...) onto these.
KICK = "kick"
SNARE = "snare"
HIHAT_CLOSED = "hihat_closed"
HIHAT_OPEN = "hihat_open"
HIHAT_PEDAL = "hihat_pedal"
TOM_HIGH = "tom_high"
TOM_MID = "tom_mid"
TOM_LOW = "tom_low"
CRASH = "crash"
RIDE = "ride"

ALL_VOICES = [
    KICK, SNARE, HIHAT_CLOSED, HIHAT_OPEN, HIHAT_PEDAL,
    TOM_HIGH, TOM_MID, TOM_LOW, CRASH, RIDE,
]


@dataclass
class DrumHit:
    """A single detected drum stroke."""
    time_sec: float          # onset time in seconds from start of audio
    instrument: str          # one of the canonical voice names above
    velocity: float = 1.0    # 0..1, loudness/confidence (used later for ghost notes)


@dataclass
class TranscriptionResult:
    hits: List[DrumHit]
    bpm: float
    duration_sec: float
