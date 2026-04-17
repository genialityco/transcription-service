# ─── BASE ──────────────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.3.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# ─── DEPENDENCIAS DE SISTEMA ───────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    git cmake build-essential ffmpeg curl wget jq \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir -U yt-dlp

# ─── COMPILAR WHISPER.CPP ──────────────────────────────────────────────────────
RUN git clone --depth=1 https://github.com/ggerganov/whisper.cpp.git /tmp/whisper_src && \
    cmake -S /tmp/whisper_src -B /app/build -DGGML_CUDA=ON && \
    cmake --build /app/build --config Release && \
    rm -rf /tmp/whisper_src

# ─── DEPENDENCIAS PYTHON ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# ─── CÓDIGO DEL SERVICIO ───────────────────────────────────────────────────────
COPY app.py .
COPY job_queue.py .
COPY queue_worker.py .
COPY transcriber.py .
COPY transcribir.sh .
RUN chmod +x transcribir.sh

# ─── MODELO (se descarga desde Hugging Face durante el build) ─────────────────
ARG WHISPER_MODEL_NAME=ggml-large-v3-q5_0.bin
RUN mkdir -p /app/models && \
    wget -q --show-progress \
      -O /app/models/${WHISPER_MODEL_NAME} \
      https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${WHISPER_MODEL_NAME}

# ─── VARIABLES DE ENTORNO POR DEFECTO ─────────────────────────────────────────
ENV WHISPER_BIN=/app/build/bin/whisper-cli
ENV WHISPER_MODEL=/app/models/ggml-large-v3-q5_0.bin
ENV WHISPER_LANG=es
ENV PORT=5001
# GEMINI_API_KEY debe inyectarse en runtime (no hardcodear en la imagen)

# ─── PUERTO ────────────────────────────────────────────────────────────────────
EXPOSE 5001

# ─── ARRANCAR ──────────────────────────────────────────────────────────────────
# Gunicorn con 1 worker para mantener la cola en memoria compartida
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]
