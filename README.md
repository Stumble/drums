# 🥁 drumscribe

Convert an isolated **drum stem** (mp3/m4a/wav — e.g. exported from Moises) into
**drum sheet music** you can read, edit, and practice from.

Because the stem is already separated and you supply the **BPM**, the two hardest
parts of automatic drum transcription (source separation, blind tempo estimation)
are out of the way — so this stays simple and accurate.

## Pipeline

```
audio stem + BPM
   → Engine (swappable)        detect WHAT was hit and WHEN  → list of DrumHits
       • heuristic  — librosa onset + frequency-band classify (no setup, runs now)
       • omnizart   — pretrained model in Docker (best accuracy)
   → quantize.py                snap hits to the BPM grid
   → notation.py (music21)      DrumHits → drum-clef MusicXML
   → browser (OpenSheetMusicDisplay) renders it; download MusicXML to edit in MuseScore
```

Every engine emits the same `DrumHit` list, so swapping models never touches the
notation/UI. See `app/engines/base.py`.

## Quick start (heuristic engine — zero model setup)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>, choose a drum stem, enter the BPM from Moises, and
hit **Transcribe**. Download the MusicXML and open it in [MuseScore](https://musescore.org)
(free) to correct any mistakes.

## Better accuracy (omnizart pretrained engine)

omnizart needs an old TensorFlow stack, so it runs in Docker, isolated from the API:

```bash
cd backend
docker build -f Dockerfile.omnizart -t drumscribe-omnizart .
export DRUMSCRIBE_OMNIZART_CMD="docker run --rm -v {dir}:/work drumscribe-omnizart \
    omnizart drum transcribe /work/{name} --output /work"
uvicorn app.main:app --reload --port 8000   # then pick the 'omnizart' engine in the UI
```

## Layout

```
backend/
  app/
    schemas.py            DrumHit — the engine-independent currency
    quantize.py           hit times → grid slots
    notation.py           grid → drum-clef MusicXML (music21)   ← verified core
    engines/
      base.py             TranscriptionEngine interface
      heuristic.py        librosa onset + band classification
      omnizart_worker.py  pretrained model via Docker, MIDI → DrumHits
  tests/test_notation.py  synthetic rock beat → valid MusicXML
  Dockerfile.omnizart
frontend/index.html       upload UI + OpenSheetMusicDisplay renderer
```

## Roadmap / known MVP limits

- Notation is single-voice with every grid slot written explicitly — readable but
  busy. Next: split hands-up / feet-down voices, merge rests, add beaming.
- Heuristic engine detects 3 voices (kick/snare/hi-hat). The model engine covers
  toms/cymbals (the full GM map is already wired in `omnizart_worker.py`).
- Future engines (Magenta OaF-Drums, MT3, your own CRNN) drop in behind the same
  interface — copy `omnizart_worker.py`, change the command + MIDI parse.
- Add server-side PDF export via the MuseScore CLI (`mscore -o out.pdf in.musicxml`).
```
