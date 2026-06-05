"""Smoke test: a synthetic one-bar rock beat -> valid drum MusicXML.

No audio, no model — just proves the quantize -> notation core produces
well-formed drum-clef MusicXML that a renderer/MuseScore can read.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.notation import to_musicxml  # noqa: E402
from app.schemas import DrumHit, KICK, SNARE, HIHAT_CLOSED  # noqa: E402


def synthetic_rock_beat(bpm=120.0):
    """Classic 8th-note rock beat, one bar:
      hi-hat on every 8th, kick on 1 & 3, snare on 2 & 4."""
    beat = 60.0 / bpm
    hits = []
    for i in range(8):  # eight 8th notes
        t = i * (beat / 2)
        hits.append(DrumHit(t, HIHAT_CLOSED, 0.8))
    hits.append(DrumHit(0 * beat, KICK, 1.0))
    hits.append(DrumHit(2 * beat, KICK, 1.0))
    hits.append(DrumHit(1 * beat, SNARE, 1.0))
    hits.append(DrumHit(3 * beat, SNARE, 1.0))
    return hits


def test_produces_valid_musicxml():
    xml = to_musicxml(synthetic_rock_beat(), bpm=120.0)
    assert xml.startswith("<?xml")
    assert "<score-partwise" in xml
    # drum clef + unpitched percussion present
    assert "percussion" in xml.lower()
    assert "<unpitched>" in xml
    # the three voices we played should all appear
    assert xml.count("<note") >= 12
    return xml


if __name__ == "__main__":
    xml = test_produces_valid_musicxml()
    out = Path(__file__).resolve().parents[1] / "sample_rock_beat.musicxml"
    out.write_text(xml)
    print(f"OK — wrote {out} ({len(xml)} bytes)")
