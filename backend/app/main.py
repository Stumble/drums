"""FastAPI server: upload a drum stem + BPM -> get drum-clef MusicXML back.

Run:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from .engines import get_engine
from .notation import to_musicxml

app = FastAPI(title="drumscribe")

# Dev convenience: allow the static frontend (any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index():
    if FRONTEND.exists():
        return FRONTEND.read_text()
    return "<h1>drumscribe</h1><p>frontend/index.html not found</p>"


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    bpm: float = Form(...),
    engine: str = Form("heuristic"),
    grid: int = Form(4),
    beats_per_measure: int = Form(4),
):
    if bpm <= 0:
        raise HTTPException(400, "bpm must be > 0")

    suffix = Path(file.filename or "audio").suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        audio_path = tmp.name

    try:
        eng = get_engine(engine)
        result = eng.transcribe(audio_path, bpm)
        xml = to_musicxml(
            result.hits, result.bpm, grid=grid, beats_per_measure=beats_per_measure,
            title=Path(file.filename or "Drum Transcription").stem,
        )
    except Exception as e:  # surface engine/setup errors to the UI
        raise HTTPException(500, f"{engine} engine failed: {e}")
    finally:
        Path(audio_path).unlink(missing_ok=True)

    return Response(
        content=xml,
        media_type="application/vnd.recordare.musicxml+xml",
        headers={"X-Hit-Count": str(len(result.hits))},
    )


@app.post("/export/pdf")
async def export_pdf(musicxml: str = Body(..., media_type="text/plain")):
    """Engrave MusicXML (from /transcribe) into a downloadable PDF."""
    try:
        from .export import musicxml_to_pdf
        pdf = musicxml_to_pdf(musicxml)
    except Exception as e:
        raise HTTPException(500, f"PDF export failed: {e}")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="drums.pdf"'},
    )
