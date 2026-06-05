"""Zero-setup engine: onset detection + spectral-feature classification.

No heavy/old dependencies, so the whole app works end-to-end while you wire up
the Dockerized pretrained engine. It now classifies a fuller kit by combining
three cues per onset:

  * band energy    — where the energy sits (sub-bass .. brilliance)
  * decay time     — how long the hit rings (closed vs open hi-hat, cymbals)
  * spectral crest — max/mean of the spectrum: high for tonal hits (kick, toms,
                     ride ping), low for noisy ones (snare, hi-hats, crash)

Mapping (best-effort — a trained model still wins on real music):
  high-band dominant + tonal .................. ride
  high-band dominant, very short decay ........ closed hi-hat
  high-band dominant, long decay .............. crash
  high-band dominant, medium decay ............ open hi-hat
  sub-bass dominant, low centroid ............. kick
  tonal low-mid ............................... tom (high/mid/low by centroid)
  otherwise (mid-band noise) .................. snare
"""

from __future__ import annotations

import numpy as np

from .base import TranscriptionEngine
from ..schemas import (
    CRASH, HIHAT_CLOSED, HIHAT_OPEN, KICK, RIDE, SNARE,
    TOM_HIGH, TOM_LOW, TOM_MID, DrumHit, TranscriptionResult,
)


class HeuristicEngine(TranscriptionEngine):
    name = "heuristic"

    def __init__(self, sr: int = 44100, max_seg_ms: float = 300.0):
        self.sr = sr
        self.max_seg = int(sr * max_seg_ms / 1000.0)

    def transcribe(self, audio_path: str, bpm: float) -> TranscriptionResult:
        import librosa

        y, sr = librosa.load(audio_path, sr=self.sr, mono=True)
        duration_sec = len(y) / sr

        onsets = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True, units="samples")

        hits: list[DrumHit] = []
        peaks: list[float] = []
        for idx, start in enumerate(onsets):
            end = onsets[idx + 1] if idx + 1 < len(onsets) else len(y)
            end = min(int(end), start + self.max_seg)
            seg = y[start:end]
            if len(seg) < 256:
                continue
            instrument, peak = self._classify(seg, sr)
            peaks.append(peak)
            hits.append(DrumHit(time_sec=start / sr, instrument=instrument, velocity=peak))

        if peaks:
            vmax = max(peaks) or 1.0
            for h in hits:
                h.velocity = float(min(1.0, h.velocity / vmax))

        return TranscriptionResult(hits=hits, bpm=bpm, duration_sec=duration_sec)

    def _classify(self, seg: np.ndarray, sr: int):
        import librosa

        peak = float(np.max(np.abs(seg)))

        # --- spectral shape from the attack (first ~46 ms) ---
        attack = seg[: min(len(seg), 2048)]
        win = attack * np.hanning(len(attack))
        spec = np.abs(np.fft.rfft(win))
        freqs = np.fft.rfftfreq(len(win), 1.0 / sr)
        total = spec.sum() + 1e-9

        sub = spec[freqs < 120].sum() / total
        low_mid = spec[(freqs >= 120) & (freqs < 500)].sum() / total
        mid = spec[(freqs >= 500) & (freqs < 5000)].sum() / total
        high = spec[freqs >= 5000].sum() / total

        centroid = float((freqs * spec).sum() / total)
        crest = float(spec.max() / (spec.mean() + 1e-9))  # tonal -> high, noise -> low
        tonal = crest > 50.0

        # --- decay: time for the RMS envelope to fall to 20% of its peak ---
        rms = librosa.feature.rms(y=seg, frame_length=512, hop_length=128)[0]
        decay = len(seg) / sr
        if rms.size and rms.max() > 0:
            pk = int(rms.argmax())
            thr = rms.max() * 0.2
            below = np.where(rms[pk:] < thr)[0]
            if below.size:
                decay = float(below[0] * 128 / sr)

        # --- decision tree ---
        if high > 0.42:                        # cymbals / hi-hats
            if tonal:
                return RIDE, peak              # the tonal cymbal (ping)
            if decay < 0.08:
                return HIHAT_CLOSED, peak
            if decay > 0.25:
                return CRASH, peak
            return HIHAT_OPEN, peak

        if sub > 0.40 and centroid < 300:      # low + tonal thump
            return KICK, peak

        if tonal and low_mid > mid:            # tonal low-mid -> tom
            if centroid > 380:
                return TOM_HIGH, peak
            if centroid > 220:
                return TOM_MID, peak
            return TOM_LOW, peak

        return SNARE, peak
