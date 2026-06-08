"""Turn quantized drum hits into readable drum-clef sheet music (MusicXML).

Real drum notation uses two voices on one staff:
  * voice 1 — the hands (snare, hi-hats, toms, cymbals): stems UP
  * voice 2 — the feet (kick, hi-hat pedal): stems DOWN

Each attack is written ringing to the next attack in its own voice (capped at a
beat), and the empty space is consolidated into the fewest standard rests — so a
groove reads like a chart, not a wall of sixteenth-notes.

Output is MusicXML: renders in the browser (OpenSheetMusicDisplay) and opens
cleanly in MuseScore/Sibelius for hand-correction.
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from music21 import (
    articulations,
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
    HIHAT_OPEN:    ("G", 5, "x"),       # 'open' shown via an 'o' articulation
    HIHAT_CLOSED:  ("G", 5, "x"),
    RIDE:          ("F", 5, "x"),
    TOM_HIGH:      ("E", 5, "normal"),
    TOM_MID:       ("D", 5, "normal"),
    SNARE:         ("C", 5, "normal"),
    TOM_LOW:       ("A", 4, "normal"),
    KICK:          ("F", 4, "normal"),
    HIHAT_PEDAL:   ("D", 4, "x"),
}

# Which staff voice each instrument belongs to.
FEET = {KICK, HIHAT_PEDAL}            # stems down
HANDS = set(VOICE_MAP) - FEET        # stems up

# A note rings at most this long before we cut it and write rests (keeps sparse
# parts — e.g. a backbeat — from becoming whole/half notes).
MAX_RING_QL = 1.0  # one quarter-note beat


def _make_unpitched(instrument: str, dur_ql: float) -> note.Unpitched:
    step, octave, nh = VOICE_MAP[instrument]
    u = note.Unpitched()
    u.displayStep = step
    u.displayOctave = octave
    u.notehead = nh
    u.duration = duration.Duration(dur_ql)
    if instrument == HIHAT_OPEN:
        u.articulations.append(articulations.OpenString())  # renders as 'o'
    return u


def _make_element(instruments: Sequence[str], dur_ql: float, stem: str):
    unps = [_make_unpitched(i, dur_ql) for i in instruments if i in VOICE_MAP]
    if len(unps) == 1:
        el = unps[0]
    else:
        el = percussion.PercussionChord(unps)
        el.duration = duration.Duration(dur_ql)
    el.stemDirection = stem
    return el


def _build_voice(
    events: List[Tuple[float, List[str]]],
    measure_ql: float,
    stem: str,
    voice_id: str,
) -> stream.Voice:
    """events: sorted (offset_ql, [instruments]) for one voice in one measure.

    Notes ring to the next attack (capped at MAX_RING_QL); gaps become rests.
    music21's makeNotation later splits any rest/note into beat-aligned,
    notatable values, which is what consolidates the busy grid.
    """
    v = stream.Voice(id=voice_id)
    if not events:
        v.insert(0.0, note.Rest(quarterLength=measure_ql))
        return v

    cursor = 0.0
    for i, (off, instruments) in enumerate(events):
        if off > cursor + 1e-6:
            v.insert(cursor, note.Rest(quarterLength=off - cursor))
            cursor = off
        next_off = events[i + 1][0] if i + 1 < len(events) else measure_ql
        dur = min(next_off - off, MAX_RING_QL)
        v.insert(off, _make_element(instruments, dur, stem))
        cursor = off + dur

    if cursor < measure_ql - 1e-6:
        v.insert(cursor, note.Rest(quarterLength=measure_ql - cursor))
    return v


def build_score(
    hits: List[DrumHit],
    bpm: float,
    grid: int = 4,
    beats_per_measure: int = 4,
    title: str = "Drum Transcription",
) -> stream.Score:
    slots_per_measure, slot_map = quantize_hits(hits, bpm, grid, beats_per_measure)
    slot_ql = 1.0 / grid                       # quarter note = 1.0
    measure_ql = float(beats_per_measure)       # 4/4 -> 4.0 quarter-lengths
    max_slot = max(slot_map) if slot_map else 0
    num_measures = max_slot // slots_per_measure + 1

    score = stream.Score()
    score.insert(0, metadata.Metadata())
    score.metadata.title = title
    part = stream.Part()
    part.partName = " "
    part.partAbbreviation = " "

    for m in range(num_measures):
        measure = stream.Measure(number=m + 1)
        if m == 0:
            measure.clef = clef.PercussionClef()
            measure.timeSignature = meter.TimeSignature(f"{beats_per_measure}/4")
            measure.insert(0, tempo.MetronomeMark(number=round(bpm)))

        hands_events: List[Tuple[float, List[str]]] = []
        feet_events: List[Tuple[float, List[str]]] = []
        for s in range(slots_per_measure):
            gslot = m * slots_per_measure + s
            hits_here = slot_map.get(gslot, [])
            if not hits_here:
                continue
            offset = s * slot_ql
            hands = [h.instrument for h in hits_here if h.instrument in HANDS]
            feet = [h.instrument for h in hits_here if h.instrument in FEET]
            if hands:
                hands_events.append((offset, hands))
            if feet:
                feet_events.append((offset, feet))

        measure.insert(0, _build_voice(hands_events, measure_ql, "up", "1"))
        measure.insert(0, _build_voice(feet_events, measure_ql, "down", "2"))
        part.append(measure)

    score.append(part)
    return score


def clean_musicxml_metadata(xml: str) -> str:
    """Remove renderer-visible defaults that make the sheet look noisy."""
    xml = re.sub(r"<part-name>.*?</part-name>", "<part-name> </part-name>", xml)
    xml = re.sub(r"<part-abbreviation>.*?</part-abbreviation>", "<part-abbreviation> </part-abbreviation>", xml)
    xml = re.sub(r'\s*<creator type="composer">Music21</creator>', "", xml)
    xml = re.sub(r'\s*<software>music21 v\.[^<]+</software>', "", xml)
    return xml


def to_musicxml(hits: List[DrumHit], bpm: float, **kwargs) -> str:
    """Render hits to a MusicXML string."""
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    score = build_score(hits, bpm, **kwargs)
    xml = GeneralObjectExporter(score).parse().decode("utf-8")
    return clean_musicxml_metadata(xml)
