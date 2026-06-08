"""HTTP-level e2e tests: drive the real FastAPI app through TestClient.

Covers the full request path a browser takes:
  upload stem -> /transcribe -> MusicXML -> /export/pdf -> PDF,
plus health, the served page, and error handling.
"""

import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

import app.main as main
from app.main import app

SR = 44100
client = TestClient(app)


def _beat_wav_bytes(bpm=120.0):
    """A simple rock beat (kick/snare/hi-hat) encoded as in-memory WAV bytes."""
    beat = 60.0 / bpm
    n = int(SR * beat * 4) + SR // 2
    buf = np.zeros(n)
    rng = np.random.default_rng(0)

    def place(sig, t):
        i = int(t * SR)
        buf[i:i + len(sig)] += sig[: n - i]

    seg = int(0.12 * SR)
    t = np.arange(seg) / SR
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 30)
    snare = rng.standard_normal(seg) * np.exp(-t * 26) * 0.0  # placeholder
    # band-limited-ish snare without scipy: noise minus its smoothed self
    raw = rng.standard_normal(seg)
    snare = (raw - np.convolve(raw, np.ones(8) / 8, mode="same")) * np.exp(-t * 26)
    hat = np.diff(rng.standard_normal(seg), prepend=0) * np.exp(-t * 100)

    for i in range(8):
        place(hat * 0.4, i * beat / 2)
    place(kick, 0); place(kick, 2 * beat)
    place(snare * 0.9, beat); place(snare * 0.9, 3 * beat)

    buf /= np.max(np.abs(buf))
    bio = io.BytesIO()
    sf.write(bio, buf, SR, format="WAV")
    return bio.getvalue()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "drumscribe" in r.text.lower()


def test_transcribe_returns_musicxml():
    wav = _beat_wav_bytes()
    r = client.post(
        "/transcribe",
        files={"file": ("beat.wav", wav, "audio/wav")},
        data={"bpm": "120", "engine": "heuristic", "grid": "4"},
    )
    assert r.status_code == 200, r.text
    assert "musicxml" in r.headers["content-type"]
    assert int(r.headers["X-Hit-Count"]) > 0
    assert r.text.startswith("<?xml") and "<score-partwise" in r.text
    assert "<unpitched>" in r.text
    assert r.headers["X-Record-Id"]


def test_transcribe_saves_library_record(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "LIBRARY_DIR", tmp_path)
    wav = _beat_wav_bytes()
    r = client.post(
        "/transcribe",
        files={"file": ("beat.wav", wav, "audio/wav")},
        data={"bpm": "120", "engine": "heuristic", "grid": "4", "title": "My Groove"},
    )
    assert r.status_code == 200, r.text
    record_id = r.headers["X-Record-Id"]

    listing = client.get("/library")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == record_id
    assert items[0]["title"] == "My Groove"
    assert items[0]["has_pdf"] is False
    assert items[0]["has_audio"] is True

    musicxml = client.get(f"/library/{record_id}/musicxml")
    assert musicxml.status_code == 200
    assert musicxml.text == r.text
    assert "<movement-title>My Groove</movement-title>" in musicxml.text

    audio = client.get(f"/library/{record_id}/audio")
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    assert audio.content == wav

    pdf = client.get(f"/library/{record_id}/pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"

    listing = client.get("/library")
    assert listing.json()["items"][0]["has_pdf"] is True

    renamed = client.patch(f"/library/{record_id}", json={"title": "Renamed Beat"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed Beat"
    musicxml = client.get(f"/library/{record_id}/musicxml")
    assert "<movement-title>Renamed Beat</movement-title>" in musicxml.text
    assert client.get("/library").json()["items"][0]["has_pdf"] is False

    deleted = client.delete(f"/library/{record_id}")
    assert deleted.status_code == 200
    assert client.get("/library").json()["items"] == []
    assert client.get(f"/library/{record_id}/musicxml").status_code == 404


def test_transcribe_rejects_bad_bpm():
    wav = _beat_wav_bytes()
    r = client.post(
        "/transcribe",
        files={"file": ("beat.wav", wav, "audio/wav")},
        data={"bpm": "0", "engine": "heuristic"},
    )
    assert r.status_code == 400


def test_transcribe_unknown_engine():
    wav = _beat_wav_bytes()
    r = client.post(
        "/transcribe",
        files={"file": ("beat.wav", wav, "audio/wav")},
        data={"bpm": "120", "engine": "does-not-exist"},
    )
    assert r.status_code == 500
    assert "unknown engine" in r.text.lower()


def test_full_pipeline_transcribe_then_pdf():
    wav = _beat_wav_bytes()
    r = client.post(
        "/transcribe",
        files={"file": ("beat.wav", wav, "audio/wav")},
        data={"bpm": "120", "engine": "heuristic", "grid": "4"},
    )
    assert r.status_code == 200
    musicxml = r.text

    r2 = client.post("/export/pdf", content=musicxml,
                     headers={"Content-Type": "text/plain"})
    assert r2.status_code == 200, r2.text
    assert r2.headers["content-type"] == "application/pdf"
    assert r2.content[:5] == b"%PDF-"
