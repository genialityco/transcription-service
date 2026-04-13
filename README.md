# transcription-service

Microservicio de transcripción de video basado en [whisper.cpp](https://github.com/ggerganov/whisper.cpp).

Recibe una URL de video, la descarga, la transcribe y expone el resultado via HTTP polling. El servicio no guarda nada en base de datos — devuelve los segmentos para que el cliente los persista como prefiera.

---

## Requisitos del sistema

| Herramienta | Versión mínima | Para qué |
|-------------|---------------|----------|
| Python      | 3.10+         | Ejecutar el servicio Flask |
| cmake       | 3.16+         | Compilar whisper.cpp |
| ffmpeg      | 4.x+          | Convertir video a WAV |
| jq          | 1.6+          | Parsear JSON del output de whisper |
| yt-dlp      | cualquiera    | Descargar videos (Vimeo, YouTube, etc.) |
| wget        | cualquiera    | Descargar el modelo (solo setup.sh) |

En Ubuntu/Debian:
```bash
sudo apt install cmake ffmpeg jq wget python3 python3-pip yt-dlp
```

---

## Instalación

```bash
# 1. Clonar / copiar el proyecto
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

## Iniciar el servicio

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
  "activity_id": "abc123"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `video_url` | string | Sí | URL del video (Vimeo, YouTube, etc.) |
| `activity_id` | string | No | Identificador propio del cliente, se devuelve en la respuesta |

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

**Respuesta `200` — transcripción lista:**
```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "segments": [
    { "startTime": 0.0,  "endTime": 3.84,  "text": "Bienvenidos al curso de introducción." },
    { "startTime": 3.84, "endTime": 7.12,  "text": "Hoy vamos a ver los conceptos básicos." }
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

### Healthcheck
```bash
curl http://localhost:5001/health
```

### Encolar una transcripción
```bash
curl -X POST http://localhost:5001/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://vimeo.com/123456789", "activity_id": "actividad-42"}'
```

Guarda el `job_id` de la respuesta para los siguientes pasos.

### Consultar estado
```bash
curl http://localhost:5001/transcribe/<job_id>/status
```

### Obtener resultado (polling manual)
```bash
curl http://localhost:5001/transcribe/<job_id>/result
```

### Script de polling automático
```bash
JOB_ID="<job_id>"
while true; do
  RESPONSE=$(curl -s http://localhost:5001/transcribe/$JOB_ID/result)
  STATUS=$(echo $RESPONSE | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "done" ] || [ "$STATUS" = "error" ]; then
    echo "$RESPONSE" | jq .
    break
  fi
  sleep 10
done
```

---

## Probar con Postman

1. **Importar colección** — crea una colección con las siguientes requests:

   | Método | URL | Body |
   |--------|-----|------|
   | POST | `http://localhost:5001/transcribe` | JSON con `video_url` y `activity_id` |
   | GET  | `http://localhost:5001/transcribe/{{job_id}}/status` | — |
   | GET  | `http://localhost:5001/transcribe/{{job_id}}/result` | — |
   | GET  | `http://localhost:5001/health` | — |

2. **Guardar `job_id` automáticamente** — en el POST `/transcribe`, agregar en la pestaña *Tests*:
   ```javascript
   const res = pm.response.json();
   pm.collectionVariables.set("job_id", res.job_id);
   ```
   Así las requests de status y result usan `{{job_id}}` automáticamente.

---

## Docker

```bash
# Requiere tener ./models/ con el modelo descargado antes de hacer build
bash setup.sh   # solo para descargar el modelo, o copiarlo manualmente

docker build -t transcription-service .
docker run -p 5001:5001 transcription-service
```

---

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | `5001` | Puerto del servidor Flask |
| `WHISPER_BIN` | `./build/bin/whisper-cli` | Path al binario compilado |
| `WHISPER_MODEL` | `./models/ggml-large-v3-q5_0.bin` | Path al modelo ggml |
| `WHISPER_LANG` | `es` | Idioma de transcripción |

---

## Estructura del proyecto

```
transcription-service/
├── app.py              # Flask: endpoints HTTP
├── job_queue.py        # Cola en memoria + estado + resultados
├── queue_worker.py     # Worker: procesa jobs en background
├── transcriber.py      # Descarga de video + parseo de segmentos
├── transcribir.sh      # Conversión WAV + ejecución de whisper-cli
├── setup.sh            # Instala binario, modelo y dependencias
├── requirements.txt
├── Dockerfile
├── .env.example
├── build/              # Generado por setup.sh (whisper-cli)
└── models/             # Generado por setup.sh (modelo ggml)
```

---

## Flujo interno

```
POST /transcribe
      │
      ▼
  job_queue (Queue)
      │
      ▼
  worker thread
      ├── yt-dlp          → descarga video → downloads/<uuid>.mp4
      ├── ffmpeg          → convierte a WAV 16kHz mono
      ├── whisper-cli     → transcribe → <uuid>.wav.json
      └── job_results     → almacena segmentos en memoria
      
GET /transcribe/<id>/result
      │
      └── lee job_results → devuelve segmentos al cliente
```
# transcription-service
