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

## Run it (full Omnizart Docker image — recommended for servers)

For the full pretrained-engine version, build one deployable Docker image that
contains the API, web UI, Omnizart, TensorFlow, audio/PDF system libraries, and
the Omnizart checkpoints:

```bash
docker build -f Dockerfile.full -t drumscribe-full . && \
docker run -d --restart unless-stopped --name drumscribe -p 8000:8000 drumscribe-full
```

Then open `http://SERVER_IP:8000` (or <http://localhost:8000> locally), choose a
drum stem, enter the BPM from Moises, choose the `omnizart` engine, and hit
**Transcribe**. Download **MusicXML** to fine-tune in
[MuseScore](https://musescore.org) (free), or **PDF** to print and play.

The full image keeps the API and Omnizart in separate Python runtimes inside one
container, so you deploy a single image while avoiding TensorFlow
dependency conflicts. The build downloads Omnizart checkpoints into the image,
so expect a large image, about 5 GB.

Prefer `make`? `make run-full` builds and runs this image.

## Run it (small Docker image — heuristic engine only)

For a faster local smoke test, the default Compose image runs the lightweight
heuristic engine and does not include Omnizart:

```bash
docker compose up --build
```

Or without Compose:

```bash
docker build -t drumscribe . && docker run --rm -p 8000:8000 drumscribe
```

Then open <http://localhost:8000>. Prefer `make`? `make up` builds + runs,
`make down` stops it, and `make logs` tails logs.

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

## Alternative local Omnizart setup

For local Python development, you can still run Omnizart as a separate helper
image instead of using `Dockerfile.full`:

```bash
cd backend
docker build -f Dockerfile.omnizart -t drumscribe-omnizart .
export DRUMSCRIBE_OMNIZART_CMD="docker run --rm -v {dir}:/work drumscribe-omnizart \
    omnizart drum transcribe /work/{name} --output /work"
uvicorn app.main:app --reload --port 8000   # then pick the 'omnizart' engine in the UI
```

Run the API **on the host** with this setup because it shells out to `docker run`.
For server deployment, prefer the full image above so the API and Omnizart ship
inside one container.

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
Dockerfile.full          full image (API + UI + Omnizart + checkpoints)
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
