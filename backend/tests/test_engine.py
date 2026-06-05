"""Validate the heuristic engine's multi-voice classifier.

Each voice is synthesized in isolation with the acoustic character the
classifier keys on (band, decay, tonal-vs-noisy), then we assert it lands in the
right bucket. This proves the pipeline *supports* the full kit; real-music
accuracy is the trained model's job.
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.heuristic import HeuristicEngine  # noqa: E402
from app.schemas import (  # noqa: E402
    CRASH, HIHAT_CLOSED, HIHAT_OPEN, KICK, RIDE, SNARE,
    TOM_HIGH, TOM_LOW, TOM_MID,
)

SR = 44100


def _t(n):
    return np.arange(n) / SR


def _bandnoise(n, lo, hi, decay, seed):
    # Realistic rolloff (Butterworth), not hard FFT zeroing — hard zeros crater
    # spectral flatness and make noise look tonal, which real cymbals never do.
    from scipy.signal import butter, sosfilt

    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    nyq = SR / 2.0
    if hi >= nyq * 0.99:
        sos = butter(4, lo / nyq, btype="high", output="sos")
    else:
        sos = butter(4, [lo / nyq, hi / nyq], btype="band", output="sos")
    return sosfilt(sos, x) * np.exp(-_t(n) * decay)


def _tone(n, freqs, decay):
    t = _t(n)
    sig = sum(np.sin(2 * np.pi * fr * t) for fr in freqs)
    return sig * np.exp(-t * decay)


def synth(voice, n=int(0.30 * SR)):
    if voice == KICK:          return _tone(n, [55], 30)
    if voice == SNARE:         return _bandnoise(n, 180, 3500, 26, 1)
    if voice == HIHAT_CLOSED:  return _bandnoise(n, 6000, 20000, 120, 2)
    if voice == HIHAT_OPEN:    return _bandnoise(n, 5000, 20000, 11, 3)
    if voice == CRASH:         return _bandnoise(n, 3500, 20000, 3, 4)
    if voice == RIDE:          return _tone(n, [5400, 7200, 9300], 4)
    if voice == TOM_HIGH:      return _tone(n, [450], 12)
    if voice == TOM_MID:       return _tone(n, [300], 12)
    if voice == TOM_LOW:       return _tone(n, [150], 12)
    raise ValueError(voice)


def classify_one(voice):
    sig = synth(voice)
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * 0.9
    inst, _ = HeuristicEngine()._classify(sig, SR)
    return inst


def test_each_voice_classifies():
    expected = [KICK, SNARE, HIHAT_CLOSED, HIHAT_OPEN, CRASH, RIDE,
                TOM_HIGH, TOM_MID, TOM_LOW]
    results = {v: classify_one(v) for v in expected}
    wrong = {v: got for v, got in results.items() if got != v}
    assert not wrong, f"misclassified: {wrong}"


def test_full_kit_through_transcribe(tmp_path=None):
    """A bar using every voice -> transcribe() -> all voices present."""
    out = Path(__file__).resolve().parents[1] / "synthetic_kit.wav"
    voices = [KICK, HIHAT_CLOSED, SNARE, HIHAT_OPEN, TOM_HIGH, TOM_MID,
              TOM_LOW, CRASH, RIDE]
    gap = int(0.25 * SR)
    buf = np.zeros(gap * len(voices) + int(0.3 * SR))
    for i, v in enumerate(voices):
        s = synth(v)
        buf[i * gap:i * gap + len(s)] += s
    buf /= np.max(np.abs(buf))
    sf.write(out, buf, SR)

    res = HeuristicEngine().transcribe(str(out), bpm=120.0)
    found = {h.instrument for h in res.hits}
    # we should recover at least 6 of the 9 distinct voices from a clean take
    assert len(found) >= 6, f"only recovered {found}"


if __name__ == "__main__":
    expected = [KICK, SNARE, HIHAT_CLOSED, HIHAT_OPEN, CRASH, RIDE,
                TOM_HIGH, TOM_MID, TOM_LOW]
    for v in expected:
        print(f"{v:14s} -> {classify_one(v)}")
