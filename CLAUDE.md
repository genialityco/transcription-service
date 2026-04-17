# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this service does

A Flask-based async transcription service. Clients POST a video URL → get a `job_id` back → poll for status/result. Internally: yt-dlp downloads the video, ffmpeg converts it to 16 kHz mono WAV, whisper.cpp transcribes it, optionally Gemini generates embeddings per segment, and the result is returned as structured segments with timestamps. The service does not persist anything — it returns data for the caller to store.

## Running the service

**Prerequisites (local/Windows):** Git Bash, ffmpeg on PATH, whisper.cpp compiled at `./build/bin/whisper-cli`, model at `./models/ggml-large-v3-q5_0.bin`, Python deps installed.

```bash
# One-time setup (clones + compiles whisper.cpp, downloads model, installs pip deps)
bash setup.sh

# Start the service
python3 app.py                  # dev, port 5001
# or
gunicorn --bind 0.0.0.0:5001 --workers 1 --threads 4 --timeout 600 app:app
```

**Docker (recommended for deployment):**
```bash
docker build -t transcription-service .

# With GPU (requires NVIDIA Container Toolkit on host)
docker run --gpus all -p 5001:5001 --env-file .env transcription-service

# CPU only
docker run -p 5001:5001 --env-file .env transcription-service
```

The Docker image is based on `nvidia/cuda:12.3.1-devel-ubuntu22.04` and compiles whisper.cpp with `-DGGML_CUDA=ON`. The build takes several minutes the first time.

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5001` | Flask/gunicorn port |
| `WHISPER_BIN` | `./build/bin/whisper-cli` | Path to compiled whisper-cli |
| `WHISPER_MODEL` | `./models/ggml-large-v3-q5_0.bin` | Path to ggml model file |
| `WHISPER_LANG` | `es` | Transcription language |
| `WHISPER_THREADS` | `16` | CPU threads for whisper inference |
| `GEMINI_API_KEY` | — | Google Gemini API key (required when `generate_embeddings: true`) |

Copy `.env.example` to `.env` to override defaults.

## API

| Endpoint | Method | Description |
|---|---|---|
| `POST /transcribe` | JSON body (see below) | Enqueue job → 202 with `job_id` |
| `GET /transcribe/<job_id>/status` | — | Returns `enqueued \| processing \| done \| error` |
| `GET /transcribe/<job_id>/result` | — | Returns segments or 202 if still processing |
| `GET /health` | — | Health check |

**POST /transcribe body fields:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `video_url` | string | Yes | — | Video URL (Vimeo, YouTube, etc.) |
| `activity_id` | string | No | `null` | Client identifier, echoed in result |
| `name_activity` | string | No | `null` | Activity name, echoed in result |
| `use_gpu` | boolean | No | `false` | Use CUDA GPU for whisper inference (requires `--gpus all` on docker run) |
| `generate_embeddings` | boolean | No | `true` | Generate Gemini embeddings per segment (requires `GEMINI_API_KEY`) |

Result segments shape (with embeddings): `[{"startTime": 0.0, "endTime": 3.5, "text": "...", "embedding": [...3072 floats...]}]`
Result segments shape (without embeddings): `[{"startTime": 0.0, "endTime": 3.5, "text": "..."}]`

## Architecture

```
app.py           Flask API — enqueues jobs, exposes status/result endpoints
job_queue.py     Shared in-memory state (queue.Queue + two dicts for status/results)
queue_worker.py  Single background thread that drains the queue sequentially
transcriber.py   download_video() via yt-dlp · run_transcription(use_gpu) via transcribir.sh
transcribir.sh   Bash script: ffmpeg → WAV, whisper-cli → JSON, parse segments, cleanup
                 Passes -ngl 99 to whisper-cli when USE_GPU=1 (GPU inference via CUDA)
embedder.py      generate_embeddings() — batched Gemini embedding-001 calls (3072 dims)
```

**Key constraint:** gunicorn is run with `--workers 1` intentionally — the job queue and status dicts are plain Python in-memory objects. Multiple workers would not share state. Concurrency within the worker comes from `--threads 4`.

**Windows quirk:** `transcriber.py` explicitly uses Git Bash (`C:\Program Files\Git\usr\bin\bash.exe`) to run `transcribir.sh` and converts Windows paths (`D:\...`) to Unix-style (`/d/...`) before passing them to the shell. This is only relevant for local Windows development; the Docker image runs on Linux.

**Temporary files:** Downloaded videos land in `./downloads/`, WAV conversions in `./samples/`. Both are deleted by `transcribir.sh` after transcription completes.

## Changing the model

Set `WHISPER_MODEL_NAME` before running `setup.sh` to download a different ggml model from Hugging Face:
```bash
WHISPER_MODEL_NAME=ggml-medium.bin bash setup.sh
```
Update `WHISPER_MODEL` env var to point the service at the new file.
