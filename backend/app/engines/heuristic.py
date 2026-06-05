"""Zero-setup engine: onset detection + frequency-band classification.

Not as accurate as a trained model, but it has no heavy/old dependencies and
runs immediately, so the whole app works end-to-end while you wire up the
Dockerized pretrained engine. Detects three voices (kick / snare / hi-hat),
which already covers most practice grooves.

Heuristic: each onset is classified by where its energy concentrates.
  low band  (< ~150 Hz)            -> kick
  high band (> ~6 kHz), noisy      -> hi-hat / cymbal
  otherwise (mid, broadband noise) -> snare
"""

from __future__ import annotations

import numpy as np

from .base import TranscriptionEngine
from ..schemas import DrumHit, HIHAT_CLOSED, KICK, SNARE, TranscriptionResult


class HeuristicEngine(TranscriptionEngine):
    name = "heuristic"

    def __init__(self, sr: int = 44100, window_ms: float = 40.0):
        self.sr = sr
        self.window = int(sr * window_ms / 1000.0)

    def transcribe(self, audio_path: str, bpm: float) -> TranscriptionResult:
        import librosa

        y, sr = librosa.load(audio_path, sr=self.sr, mono=True)
        duration_sec = len(y) / sr

        onset_frames = librosa.onset.onset_detect(
            y=y, sr=sr, backtrack=True, units="samples",
        )

        hits = []
        rms_values = []
        for start in onset_frames:
            seg = y[start:start + self.window]
            if len(seg) < 64:
                continue
            instrument, rms = self._classify(seg, sr)
            rms_values.append(rms)
            hits.append(DrumHit(time_sec=start / sr, instrument=instrument, velocity=rms))

        # Normalize velocities to 0..1 across the track.
        if rms_values:
            vmax = max(rms_values) or 1.0
            for h in hits:
                h.velocity = float(h.velocity / vmax)

        return TranscriptionResult(hits=hits, bpm=bpm, duration_sec=duration_sec)

    def _classify(self, seg: np.ndarray, sr: int):
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
        rms = float(np.sqrt(np.mean(seg ** 2)))

        low = spec[freqs < 150].sum()
        mid = spec[(freqs >= 150) & (freqs < 6000)].sum()
        high = spec[freqs >= 6000].sum()
        total = low + mid + high + 1e-9

        low_r, high_r = low / total, high / total
        if low_r > 0.45:
            return KICK, rms
        if high_r > 0.35:
            return HIHAT_CLOSED, rms
        return SNARE, rms
