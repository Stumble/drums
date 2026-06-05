"""Full vertical slice (minus browser): synthesize a drum-ish WAV ->
HeuristicEngine -> notation -> MusicXML. Proves audio actually flows through.
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.heuristic import HeuristicEngine  # noqa: E402
from app.notation import to_musicxml  # noqa: E402
from app.schemas import KICK, SNARE, HIHAT_CLOSED  # noqa: E402

SR = 44100


def kick(n):     # low thump ~60 Hz, fast decay
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 60 * t) * np.exp(-t * 35)


def snare(n):    # broadband noise burst
    t = np.arange(n) / SR
    return np.random.randn(n) * np.exp(-t * 30)


def hihat(n):    # high-passed noisy tick
    t = np.arange(n) / SR
    noise = np.random.randn(n)
    hp = np.diff(noise, prepend=0)           # crude high-pass
    return hp * np.exp(-t * 90)


def render():
    # Voices at DISTINCT times (no overlap) so we can validate single-label
    # classification. Overlapping voices are the model engine's job, not this one.
    bpm = 120.0
    beat = 60.0 / bpm
    total = int(SR * beat * 4) + SR // 4
    buf = np.zeros(total)

    def place(sig, t):
        i = int(t * SR)
        buf[i:i + len(sig)] += sig[: total - i]

    seg = int(0.12 * SR)
    # One bar, 8th-note pattern: K h S h K h S h  — each on its own 8th.
    pattern = [KICK, HIHAT_CLOSED, SNARE, HIHAT_CLOSED,
               KICK, HIHAT_CLOSED, SNARE, HIHAT_CLOSED]
    gen = {KICK: lambda: kick(seg), SNARE: lambda: snare(seg) * 0.9,
           HIHAT_CLOSED: lambda: hihat(seg) * 0.5}
    for i, voice in enumerate(pattern):
        place(gen[voice](), i * beat / 2)

    buf /= np.max(np.abs(buf))
    path = Path(__file__).resolve().parents[1] / "synthetic_beat.wav"
    sf.write(path, buf, SR)
    return str(path)


def main():
    np.random.seed(0)
    path = render()
    result = HeuristicEngine().transcribe(path, bpm=120.0)

    counts = {}
    for h in result.hits:
        counts[h.instrument] = counts.get(h.instrument, 0) + 1
    print(f"detected {len(result.hits)} hits: {counts}")

    assert len(result.hits) >= 8, "should detect most onsets"
    assert KICK in counts and SNARE in counts and HIHAT_CLOSED in counts, \
        f"all three voices should appear, got {counts}"

    xml = to_musicxml(result.hits, result.bpm, grid=4)
    assert "<score-partwise" in xml and "<unpitched>" in xml
    print("end-to-end OK — audio -> hits -> valid drum MusicXML")


if __name__ == "__main__":
    main()
