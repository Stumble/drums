"""Snap raw hit times onto a musical grid.

Because the BPM is known up front (Moises gives it to you), quantization is a
simple nearest-grid-slot snap rather than a blind tempo-inference problem.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schemas import DrumHit


def quantize_hits(
    hits: List[DrumHit],
    bpm: float,
    grid: int = 4,
    beats_per_measure: int = 4,
) -> Tuple[int, Dict[int, List[DrumHit]]]:
    """Snap each hit to the nearest subdivision slot.

    grid=4 -> sixteenth-note grid (4 slots per quarter-note beat).
    Returns (slots_per_measure, {global_slot_index: [hits in that slot]}).
    """
    beat_sec = 60.0 / bpm
    slot_sec = beat_sec / grid
    slots_per_measure = beats_per_measure * grid

    slots: Dict[int, List[DrumHit]] = {}
    for hit in hits:
        slot = round(hit.time_sec / slot_sec)
        slots.setdefault(slot, []).append(hit)

    # Deduplicate: if the same voice lands twice in one slot, keep the loudest.
    for slot, slot_hits in slots.items():
        best: Dict[str, DrumHit] = {}
        for h in slot_hits:
            if h.instrument not in best or h.velocity > best[h.instrument].velocity:
                best[h.instrument] = h
        slots[slot] = list(best.values())

    return slots_per_measure, slots
