# drumscribe — single image that runs the API and serves the web UI.
#
# Bundles every system dependency so there is nothing to install by hand:
#   ffmpeg      — decode mp3/m4a/etc. for librosa
#   libsndfile1 — soundfile (WAV I/O)
#   libcairo2   — cairosvg (MusicXML -> PDF export)
#
# Build & run:
#   docker build -t drumscribe .
#   docker run --rm -p 8000:8000 drumscribe
# then open http://localhost:8000
#
# (The 'omnizart' pretrained engine is a separate image — see
#  backend/Dockerfile.omnizart. The default 'heuristic' engine runs here.)

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so they cache across code changes.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# App code + the static frontend (served by FastAPI at "/").
COPY backend backend
COPY frontend frontend

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
