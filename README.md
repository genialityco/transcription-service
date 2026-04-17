# transcription-service

Microservicio de transcripción de video basado en [whisper.cpp](https://github.com/ggerganov/whisper.cpp).

Recibe una URL de video, la descarga, la transcribe, opcionalmente genera embeddings con Gemini, y expone el resultado via HTTP polling. El servicio no guarda nada en base de datos — devuelve los segmentos para que el cliente los persista como prefiera.

---

## Requisitos del sistema

| Herramienta | Versión mínima | Para qué |
|-------------|---------------|----------|
| Python      | 3.10+         | Ejecutar el servicio Flask |
| cmake       | 3.16+         | Compilar whisper.cpp |
| ffmpeg      | 4.x+          | Convertir video a WAV |
| yt-dlp      | cualquiera    | Descargar videos (Vimeo, YouTube, etc.) |
| wget        | cualquiera    | Descargar el modelo (solo setup.sh) |

En Ubuntu/Debian:
```bash
sudo apt install cmake ffmpeg wget python3 python3-pip yt-dlp
```

---

## Instalación local

```bash
# 1. Clonar el proyecto
git clone https://github.com/tu-usuario/transcription-service.git
cd transcription-service

# 2. Setup: compila whisper.cpp, descarga el modelo e instala dependencias Python
bash setup.sh

# 3. Configurar entorno
cp .env.example .env
# Editar .env si necesitas cambiar puerto, idioma u otros paths
```

El `setup.sh` es idempotente: si el binario o el modelo ya existen, los omite.

### Modelos disponibles

Por defecto se descarga `ggml-large-v3-q5_0.bin` (alta precisión, ~1.1 GB). Para usar un modelo más liviano:

```bash
WHISPER_MODEL_NAME=ggml-medium.bin bash setup.sh
```

| Modelo | Tamaño | Velocidad | Precisión |
|--------|--------|-----------|-----------|
| `ggml-tiny.bin` | ~75 MB | muy rápido | baja |
| `ggml-base.bin` | ~142 MB | rápido | media-baja |
| `ggml-medium.bin` | ~1.5 GB | medio | alta |
| `ggml-large-v3-q5_0.bin` | ~1.1 GB | lento | muy alta |

---

## Iniciar el servicio (desarrollo)

```bash
python3 app.py
```

El servicio queda disponible en `http://localhost:5001`.

---

## API

### `POST /transcribe`

Encola un trabajo de transcripción y devuelve un `job_id` para hacer polling.

**Body:**
```json
{
  "video_url": "https://vimeo.com/123456789",
  "activity_id": "abc123",
  "name_activity": "Clase 1",
  "use_gpu": false,
  "generate_embeddings": true
}
```

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `video_url` | string | Sí | — | URL del video (Vimeo, YouTube, etc.) |
| `activity_id` | string | No | `null` | Identificador propio del cliente, se devuelve en el resultado |
| `name_activity` | string | No | `null` | Nombre de la actividad, se devuelve en el resultado |
| `use_gpu` | boolean | No | `false` | Usa GPU (CUDA) para la transcripción si está disponible |
| `generate_embeddings` | boolean | No | `true` | Genera embeddings Gemini por cada segmento |

**Respuesta `202 Accepted`:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "enqueued",
  "activity_id": "abc123"
}
```

---

### `GET /transcribe/<job_id>/status`

Consulta el estado actual de un job.

**Respuesta `200 OK`:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing"
}
```

| Status | Significado |
|--------|-------------|
| `enqueued` | En cola, esperando worker |
| `processing` | Descargando / transcribiendo |
| `done` | Transcripción lista |
| `error` | Falló, ver `/result` para el mensaje |

---

### `GET /transcribe/<job_id>/result`

Devuelve el resultado cuando el job termina. Usar para polling.

**Respuesta `202` — todavía procesando:**
```json
{
  "job_id": "550e8400-...",
  "status": "processing"
}
```

**Respuesta `200` — transcripción lista (con embeddings):**
```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "activity_id": "abc123",
  "name_activity": "Clase 1",
  "segments": [
    {
      "startTime": 0.0,
      "endTime": 3.84,
      "text": "Bienvenidos al curso de introducción.",
      "embedding": [0.012, -0.034, ...]
    }
  ]
}
```

**Respuesta `200` — transcripción lista (sin embeddings):**
```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "activity_id": "abc123",
  "name_activity": "Clase 1",
  "segments": [
    { "startTime": 0.0, "endTime": 3.84, "text": "Bienvenidos al curso de introducción." }
  ]
}
```

**Respuesta `500` — error:**
```json
{
  "job_id": "550e8400-...",
  "status": "error",
  "error": "No se pudo descargar el video: ..."
}
```

---

### `GET /health`

Healthcheck del servicio.

**Respuesta `200`:**
```json
{ "status": "ok" }
```

---

## Probar con curl

```bash
# Healthcheck
curl http://localhost:5001/health

# Encolar transcripción con GPU y embeddings
curl -X POST http://localhost:5001/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://vimeo.com/123456789", "activity_id": "actividad-42", "use_gpu": true, "generate_embeddings": true}'

# Encolar solo transcripción (sin GPU, sin embeddings)
curl -X POST http://localhost:5001/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://vimeo.com/123456789", "use_gpu": false, "generate_embeddings": false}'

# Consultar estado (reemplaza <job_id>)
curl http://localhost:5001/transcribe/<job_id>/status

# Obtener resultado
curl http://localhost:5001/transcribe/<job_id>/result
```

---

## Docker

### Build

La imagen base es `nvidia/cuda:12.3.1-devel-ubuntu22.04`, lo que permite compilar whisper.cpp con soporte CUDA.

```bash
docker build -t transcription-service .
```

### Correr con GPU

```bash
docker run -d \
  --gpus all \
  -p 5001:5001 \
  --env-file .env \
  transcription-service
```

> `--gpus all` es necesario para que `use_gpu: true` funcione. Sin este flag, el contenedor solo puede usar CPU.

### Correr solo CPU (sin GPU en el host)

```bash
docker run -d \
  -p 5001:5001 \
  --env-file .env \
  transcription-service
```

> Si el host no tiene GPU NVIDIA, omitir `--gpus all`. En ese caso enviar siempre `use_gpu: false` en las peticiones.

---

## Despliegue en servidor con GPU

### 1. Instalar Docker + NVIDIA Container Toolkit

```bash
# Docker
curl -fsSL https://get.docker.com | sh

# NVIDIA Container Toolkit (necesario para --gpus all)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 2. Clonar y construir

```bash
git clone https://github.com/tu-usuario/transcription-service.git /app
cd /app
docker build -t transcription-service .
```

### 3. Correr el contenedor

```bash
docker run -d \
  --name transcription \
  --restart unless-stopped \
  --gpus all \
  -p 5001:5001 \
  --env-file .env \
  transcription-service

# Verificar
docker logs -f transcription
curl http://localhost:5001/health
```

### Actualizar el servicio

```bash
cd /app
git pull
docker build -t transcription-service .
docker stop transcription && docker rm transcription
docker run -d \
  --name transcription \
  --restart unless-stopped \
  --gpus all \
  -p 5001:5001 \
  --env-file .env \
  transcription-service
```

---

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | `5001` | Puerto del servidor Flask |
| `WHISPER_BIN` | `/app/build/bin/whisper-cli` | Path al binario compilado |
| `WHISPER_MODEL` | `/app/models/ggml-large-v3-q5_0.bin` | Path al modelo ggml |
| `WHISPER_LANG` | `es` | Idioma de transcripción |
| `WHISPER_THREADS` | `16` | Threads de CPU para whisper (relevante en modo CPU) |
| `GEMINI_API_KEY` | — | API key de Google Gemini (requerida si `generate_embeddings: true`) |

---

## Estructura del proyecto

```
transcription-service/
├── app.py              # Flask: endpoints HTTP
├── job_queue.py        # Cola en memoria + estado + resultados
├── queue_worker.py     # Worker: procesa jobs en background
├── transcriber.py      # Descarga de video + parseo de segmentos
├── transcribir.sh      # Conversión WAV + ejecución de whisper-cli
├── embedder.py         # Generación de embeddings con Gemini
├── setup.sh            # Instala binario, modelo y dependencias (desarrollo local)
├── requirements.txt
├── Dockerfile
├── .env.example
├── models/             # No incluido en git (se descarga en el build Docker)
└── build/              # Generado dentro del contenedor Docker
```

---

## Flujo interno

```
POST /transcribe
      │
      ▼
  job_queue (Queue en memoria)
      │
      ▼
  worker thread
      ├── yt-dlp          → descarga video → downloads/<uuid>.mp4
      ├── ffmpeg          → convierte a WAV 16kHz mono
      ├── whisper-cli     → transcribe (CPU o GPU según use_gpu)
      ├── embedder        → genera embeddings Gemini (si generate_embeddings=true)
      └── job_results     → almacena segmentos en memoria

GET /transcribe/<id>/result
      │
      └── lee job_results → devuelve segmentos (+ embeddings si se generaron)
```

> **Nota**: la cola de jobs es en memoria. Si el contenedor se reinicia, los jobs en curso se pierden. Para producción con alta disponibilidad, reemplazar con Redis + Celery.
