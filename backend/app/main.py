"""FastAPI server: upload a drum stem + BPM -> get drum-clef MusicXML back.

Run:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""

from __future__ import annotations

import json
import re
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response

from .engines import get_engine
from .notation import clean_musicxml_metadata, to_musicxml

app = FastAPI(title="drumscribe")

# Dev convenience: allow the static frontend (any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
LIBRARY_DIR = Path(os.environ.get("DRUMSCRIBE_LIBRARY_DIR", "/app/library"))


def _safe_title(title: str | None, filename: str | None = None) -> str:
    title = (title or "").strip()
    if not title:
        title = Path(filename or "Drum Transcription").stem.strip()
    return title or "Drum Transcription"


def _record_paths(record_id: str) -> dict[str, Path]:
    if not re.fullmatch(r"[0-9a-f]{32}", record_id):
        raise HTTPException(404, "transcription not found")
    return {
        "meta": LIBRARY_DIR / f"{record_id}.json",
        "musicxml": LIBRARY_DIR / f"{record_id}.musicxml",
        "pdf": LIBRARY_DIR / f"{record_id}.pdf",
        "audio": LIBRARY_DIR / f"{record_id}.audio",
    }


def _load_record(record_id: str) -> dict:
    paths = _record_paths(record_id)
    if not paths["meta"].exists():
        raise HTTPException(404, "transcription not found")
    return json.loads(paths["meta"].read_text())


def _save_meta(meta: dict) -> dict:
    paths = _record_paths(meta["id"])
    paths["meta"].write_text(json.dumps(meta, indent=2, sort_keys=True))
    return meta


def _save_record(meta: dict, musicxml: str, audio: bytes) -> dict:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    paths = _record_paths(meta["id"])
    paths["musicxml"].write_text(musicxml)
    paths["audio"].write_bytes(audio)
    return _save_meta(meta)


def _retitle_musicxml(musicxml: str, title: str) -> str:
    title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    musicxml = re.sub(r"<work-title>.*?</work-title>", f"<work-title>{title}</work-title>", musicxml)
    musicxml = re.sub(r"<movement-title>.*?</movement-title>", f"<movement-title>{title}</movement-title>", musicxml)
    return clean_musicxml_metadata(musicxml)


def _read_clean_musicxml(path: Path, pdf_path: Path | None = None) -> str:
    musicxml = path.read_text()
    cleaned = clean_musicxml_metadata(musicxml)
    if cleaned != musicxml:
        path.write_text(cleaned)
        if pdf_path:
            pdf_path.unlink(missing_ok=True)
    return cleaned


def _list_records() -> list[dict]:
    if not LIBRARY_DIR.exists():
        return []

    records = []
    for path in LIBRARY_DIR.glob("*.json"):
        try:
            record = json.loads(path.read_text())
            paths = _record_paths(record.get("id", ""))
        except json.JSONDecodeError:
            continue
        except HTTPException:
            continue
        record["has_pdf"] = paths["pdf"].exists()
        record["has_audio"] = paths["audio"].exists()
        records.append(record)
    return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)


@app.get("/", response_class=HTMLResponse)
def index():
    if FRONTEND.exists():
        return FRONTEND.read_text()
    return "<h1>drumscribe</h1><p>frontend/index.html not found</p>"


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/library")
def library():
    return {"items": _list_records()}


@app.get("/library/{record_id}/musicxml")
def library_musicxml(record_id: str):
    record = _load_record(record_id)
    path = _record_paths(record_id)["musicxml"]
    if not path.exists():
        raise HTTPException(404, "MusicXML not found")
    _read_clean_musicxml(path, _record_paths(record_id)["pdf"])
    return FileResponse(
        path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"{record.get('title') or record_id}.musicxml",
    )


@app.get("/library/{record_id}/audio")
def library_audio(record_id: str):
    record = _load_record(record_id)
    path = _record_paths(record_id)["audio"]
    if not path.exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(
        path,
        media_type=record.get("content_type") or "application/octet-stream",
        filename=record.get("filename") or f"{record_id}.audio",
    )


@app.get("/library/{record_id}/pdf")
def library_pdf(record_id: str):
    record = _load_record(record_id)
    paths = _record_paths(record_id)
    if not paths["musicxml"].exists():
        raise HTTPException(404, "MusicXML not found")

    if not paths["pdf"].exists():
        try:
            from .export import musicxml_to_pdf
            pdf = musicxml_to_pdf(_read_clean_musicxml(paths["musicxml"], paths["pdf"]))
            paths["pdf"].write_bytes(pdf)
        except Exception as e:
            raise HTTPException(500, f"PDF export failed: {e}")

    return FileResponse(
        paths["pdf"],
        media_type="application/pdf",
        filename=f"{record.get('title') or record_id}.pdf",
    )


@app.patch("/library/{record_id}")
def rename_record(record_id: str, payload: dict = Body(...)):
    record = _load_record(record_id)
    title = _safe_title(payload.get("title"), record.get("filename"))
    paths = _record_paths(record_id)
    if paths["musicxml"].exists():
        paths["musicxml"].write_text(_retitle_musicxml(paths["musicxml"].read_text(), title))
    paths["pdf"].unlink(missing_ok=True)
    record["title"] = title
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _save_meta(record)


@app.delete("/library/{record_id}")
def delete_record(record_id: str):
    _load_record(record_id)
    for path in _record_paths(record_id).values():
        path.unlink(missing_ok=True)
    return {"ok": True}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    bpm: float = Form(...),
    engine: str = Form("heuristic"),
    grid: int = Form(4),
    beats_per_measure: int = Form(4),
    title: str | None = Form(None),
):
    if bpm <= 0:
        raise HTTPException(400, "bpm must be > 0")

    filename = file.filename or "audio"
    suffix = Path(filename).suffix or ".mp3"
    audio = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio)
        audio_path = tmp.name

    try:
        eng = get_engine(engine)
        result = eng.transcribe(audio_path, bpm)
        title = _safe_title(title, filename)
        xml = to_musicxml(
            result.hits, result.bpm, grid=grid, beats_per_measure=beats_per_measure,
            title=title,
        )
        record = _save_record(
            {
                "id": uuid.uuid4().hex,
                "title": title,
                "filename": filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "bpm": result.bpm,
                "engine": engine,
                "grid": grid,
                "beats_per_measure": beats_per_measure,
                "hit_count": len(result.hits),
                "duration_sec": result.duration_sec,
                "content_type": file.content_type,
            },
            xml,
            audio,
        )
    except Exception as e:  # surface engine/setup errors to the UI
        raise HTTPException(500, f"{engine} engine failed: {e}")
    finally:
        Path(audio_path).unlink(missing_ok=True)

    return Response(
        content=xml,
        media_type="application/vnd.recordare.musicxml+xml",
        headers={"X-Hit-Count": str(len(result.hits)), "X-Record-Id": record["id"]},
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
