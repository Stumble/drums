"""Turn quantized drum hits into drum-clef sheet music (MusicXML).

Output is MusicXML so it renders in the browser (OpenSheetMusicDisplay) and
opens cleanly in MuseScore/Sibelius for hand-correction — the editing loop that
makes this useful as a practice tool.

MVP simplifications (tracked for later polish):
  * single voice, all stems up (real charts split hands-up / feet-down)
  * every grid slot is written explicitly (no rest merging / beaming cleanup)
"""

from __future__ import annotations

from typing import List

from music21 import (
    clef,
    duration,
    metadata,
    meter,
    note,
    percussion,
    stream,
    tempo,
)

from .quantize import quantize_hits
from .schemas import (
    CRASH, HIHAT_CLOSED, HIHAT_OPEN, HIHAT_PEDAL, KICK, RIDE,
    SNARE, TOM_HIGH, TOM_LOW, TOM_MID, DrumHit,
)

# instrument -> (display step, display octave, notehead) on a 5-line drum staff.
# Positions follow the de-facto MuseScore drumset layout.
VOICE_MAP = {
    CRASH:         ("A", 5, "x"),
    HIHAT_OPEN:    ("G", 5, "circle-x"),
    HIHAT_CLOSED:  ("G", 5, "x"),
    RIDE:          ("F", 5, "x"),
    TOM_HIGH:      ("E", 5, "normal"),
    TOM_MID:       ("D", 5, "normal"),
    SNARE:         ("C", 5, "normal"),
    TOM_LOW:       ("A", 4, "normal"),
    KICK:          ("F", 4, "normal"),
    HIHAT_PEDAL:   ("D", 4, "x"),
}


def _make_unpitched(instrument: str, slot_ql: float) -> note.Unpitched:
    step, octave, nh = VOICE_MAP[instrument]
    u = note.Unpitched()
    u.displayStep = step
    u.displayOctave = octave
    u.notehead = nh
    u.duration = duration.Duration(slot_ql)
    return u


def build_score(
    hits: List[DrumHit],
    bpm: float,
    grid: int = 4,
    beats_per_measure: int = 4,
    title: str = "Drum Transcription",
) -> stream.Score:
    slots_per_measure, slot_map = quantize_hits(hits, bpm, grid, beats_per_measure)
    max_slot = max(slot_map) if slot_map else 0
    num_measures = max_slot // slots_per_measure + 1
    slot_ql = 1.0 / grid  # quarter note = 1.0; grid=4 -> 0.25 (sixteenth)

    score = stream.Score()
    score.insert(0, metadata.Metadata())
    score.metadata.title = title

    part = stream.Part()
    part.insert(0, clef.PercussionClef())
    part.insert(0, meter.TimeSignature(f"{beats_per_measure}/4"))
    part.insert(0, tempo.MetronomeMark(number=round(bpm)))

    for m in range(num_measures):
        measure = stream.Measure(number=m + 1)
        for s in range(slots_per_measure):
            gslot = m * slots_per_measure + s
            voices = [h for h in slot_map.get(gslot, []) if h.instrument in VOICE_MAP]
            if not voices:
                measure.append(note.Rest(quarterLength=slot_ql))
                continue
            unps = [_make_unpitched(h.instrument, slot_ql) for h in voices]
            if len(unps) == 1:
                measure.append(unps[0])
            else:
                chord = percussion.PercussionChord(unps)
                chord.duration = duration.Duration(slot_ql)
                measure.append(chord)
        part.append(measure)

    score.append(part)
    return score


def to_musicxml(hits: List[DrumHit], bpm: float, **kwargs) -> str:
    """Render hits to a MusicXML string."""
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    score = build_score(hits, bpm, **kwargs)
    return GeneralObjectExporter(score).parse().decode("utf-8")
