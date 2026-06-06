# 🥁 drumscribe

Convert an isolated **drum stem** (mp3/m4a/wav — e.g. exported from Moises) into
readable **drum sheet music** you can edit, print, and practice from.

Because the stem is already separated and you supply the **BPM**, the two hardest
parts of automatic drum transcription (source separation, blind tempo estimation)
are out of the way — so this stays simple and accurate.

## Pipeline

```
audio stem + BPM
   → Engine (swappable)        detect WHAT was hit and WHEN  → list of DrumHits
       • heuristic  — librosa onset + spectral classify (no setup, runs now)
       • omnizart   — pretrained model in Docker (best accuracy)
   → quantize.py                snap hits to the BPM grid
   → notation.py (music21)      DrumHits → two-voice drum-clef MusicXML
   → browser (OpenSheetMusicDisplay) renders it
   → download MusicXML (edit in MuseScore)  or  PDF (verovio, print & play)
```

Every engine emits the same `DrumHit` list, so swapping models never touches the
notation/UI. See `app/engines/base.py`.

## What it produces

- **Two-voice drum notation** — hands (snare, hi-hats, toms, cymbals) stems-up,
  feet (kick, hi-hat pedal) stems-down, with **consolidated rests** so a groove
  reads like a real chart instead of a wall of sixteenth-notes.
- **Full kit** — kick, snare, closed/open hi-hat, hi-hat pedal, high/mid/low
  toms, crash, ride (proper staff positions + `x` noteheads for cymbals/hats,
  `o` for open hi-hat).
- **MusicXML + PDF** export.

## Run it (Docker — recommended)

Everything (Python deps **and** the system libs for audio decoding + PDF export)
is baked into the image, so there's nothing to install by hand:

```bash
docker compose up --build      # or: docker build -t drumscribe . && docker run --rm -p 8000:8000 drumscribe
```

Then open <http://localhost:8000>, choose a drum stem, enter the BPM from Moises,
and hit **Transcribe**. Download **MusicXML** to fine-tune in
[MuseScore](https://musescore.org) (free), or **PDF** to print and play.

> Prefer `make`? `make up` builds + runs, `make down` stops it, `make logs` tails logs.

## Run it (local Python — for development)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# PDF export needs the system Cairo lib once:
#   sudo apt-get install -y libcairo2     # (macOS: brew install cairo)
uvicorn app.main:app --reload --port 8000
```

Or with the Makefile from the repo root: `make dev` (sets up the venv and runs
with autoreload) and `make test`.

## Better accuracy (omnizart pretrained engine)

omnizart needs an old TensorFlow stack, so it runs in its own Docker image,
isolated from the API:

```bash
cd backend
docker build -f Dockerfile.omnizart -t drumscribe-omnizart .
export DRUMSCRIBE_OMNIZART_CMD="docker run --rm -v {dir}:/work drumscribe-omnizart \
    omnizart drum transcribe /work/{name} --output /work"
uvicorn app.main:app --reload --port 8000   # then pick the 'omnizart' engine in the UI
```

Run the API **on the host** (local Python) when using this engine — it shells
out to `docker run`, so running the API itself in a container would need the
Docker socket mounted (docker-in-docker). The default `heuristic` engine has no
such requirement and is what the bundled image / `docker compose up` uses.

## Tests

```bash
cd backend && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Coverage:
- `test_notation.py` — synthetic beat → valid two-voice MusicXML
- `test_engine.py` — every kit voice classifies to the right bucket
- `test_end_to_end.py` — synthesized audio → hits → MusicXML
- `test_api.py` — HTTP e2e: `/transcribe` and `/export/pdf` through `TestClient`

## API

| Method | Path           | Body                                   | Returns        |
| ------ | -------------- | -------------------------------------- | -------------- |
| POST   | `/transcribe`  | multipart: `file`, `bpm`, `engine`, `grid`, `beats_per_measure` | MusicXML       |
| POST   | `/export/pdf`  | `text/plain` MusicXML                  | `application/pdf` |
| GET    | `/health`      | —                                      | `{"ok": true}` |

## Layout

```
Dockerfile               app image (API + UI + system libs)
docker-compose.yml       one-command run
Makefile                 up / down / dev / test helpers
backend/
  app/
    schemas.py            DrumHit — the engine-independent currency
    quantize.py           hit times → grid slots
    notation.py           grid → two-voice drum-clef MusicXML (music21)
    export.py             MusicXML → SVG/PDF (verovio + cairosvg)
    main.py               FastAPI: /transcribe, /export/pdf
    engines/
      base.py             TranscriptionEngine interface
      heuristic.py        librosa onset + spectral-feature classification
      omnizart_worker.py  pretrained model via Docker, MIDI → DrumHits
  tests/                  notation, engine, end-to-end, API
  requirements.txt / requirements-dev.txt
  Dockerfile.omnizart     separate image for the pretrained engine
frontend/index.html       upload UI + OpenSheetMusicDisplay + PDF download
```

## Roadmap

- Swap the heuristic for the pretrained model on real practice tracks; compare.
- Future engines (Magenta OaF-Drums, MT3, a custom CRNN) drop in behind the same
  interface — copy `omnizart_worker.py`, change the command + MIDI parse.
- Sticking/flam/ghost-note (velocity → parenthesized) refinements.
- Per-section repeats and bar-count compaction for long songs.
```
