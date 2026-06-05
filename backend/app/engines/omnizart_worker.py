"""Pretrained-model engine: shells out to omnizart's drum transcriber.

omnizart depends on old TensorFlow, so it runs in its own Docker image
(see backend/Dockerfile.omnizart) rather than in the API's environment. This
class invokes that command, then parses the resulting MIDI into DrumHits using
the General MIDI percussion map.

Set DRUMSCRIBE_OMNIZART_CMD to control how omnizart is invoked, e.g.:
  export DRUMSCRIBE_OMNIZART_CMD="docker run --rm -v {dir}:/work drumscribe-omnizart \
      omnizart drum transcribe /work/{name} --output /work"
The tokens {dir}, {name}, {stem} are substituted per request.

To swap in Magenta OaF-Drums or MT3 later, copy this file and change the
command + MIDI parsing — the DrumHit output contract stays identical.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .base import TranscriptionEngine
from ..schemas import (
    CRASH, HIHAT_CLOSED, HIHAT_OPEN, HIHAT_PEDAL, KICK, RIDE,
    SNARE, TOM_HIGH, TOM_LOW, TOM_MID, DrumHit, TranscriptionResult,
)

# General MIDI percussion note -> canonical voice.
GM_DRUM_MAP = {
    35: KICK, 36: KICK,
    38: SNARE, 40: SNARE, 37: SNARE,
    42: HIHAT_CLOSED, 44: HIHAT_PEDAL, 46: HIHAT_OPEN,
    41: TOM_LOW, 43: TOM_LOW, 45: TOM_MID, 47: TOM_MID,
    48: TOM_HIGH, 50: TOM_HIGH,
    49: CRASH, 57: CRASH, 55: CRASH, 52: CRASH,
    51: RIDE, 59: RIDE, 53: RIDE,
}

DEFAULT_CMD = "omnizart drum transcribe {dir}/{name} --output {dir}"


class OmnizartEngine(TranscriptionEngine):
    name = "omnizart"

    def __init__(self, command: str | None = None):
        self.command = command or os.environ.get("DRUMSCRIBE_OMNIZART_CMD", DEFAULT_CMD)

    def transcribe(self, audio_path: str, bpm: float) -> TranscriptionResult:
        import pretty_midi

        src = Path(audio_path)
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            local = work / src.name
            local.write_bytes(src.read_bytes())

            cmd = self.command.format(dir=str(work), name=src.name, stem=src.stem)
            subprocess.run(cmd, shell=True, check=True)

            midi_files = list(work.glob("*.mid")) + list(work.glob("*.midi"))
            if not midi_files:
                raise RuntimeError(f"omnizart produced no MIDI in {work}")
            pm = pretty_midi.PrettyMIDI(str(midi_files[0]))

        hits = []
        for inst in pm.instruments:
            for n in inst.notes:
                voice = GM_DRUM_MAP.get(n.pitch)
                if voice:
                    hits.append(DrumHit(
                        time_sec=float(n.start),
                        instrument=voice,
                        velocity=n.velocity / 127.0,
                    ))
        hits.sort(key=lambda h: h.time_sec)
        return TranscriptionResult(hits=hits, bpm=bpm, duration_sec=pm.get_end_time())
