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

```bash
# Healthcheck
curl http://localhost:5001/health

# Encolar una transcripción
curl -X POST http://localhost:5001/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://vimeo.com/123456789", "activity_id": "actividad-42"}'

# Consultar estado (reemplaza <job_id>)
curl http://localhost:5001/transcribe/<job_id>/status

# Obtener resultado
curl http://localhost:5001/transcribe/<job_id>/result
```

---

## Docker

### Build local

```bash
# El modelo debe estar en ./models/ antes del build
# Si no lo tienes, ejecuta: bash setup.sh

docker build -t transcription-service .
docker run -d -p 5001:5001 transcription-service
```

### Build con modelo externo (sin incluirlo en la imagen)

```bash
docker run -d \
  -p 5001:5001 \
  -v /ruta/local/models:/app/models \
  -e WHISPER_LANG=es \
  transcription-service
```

---

## Despliegue en Digital Ocean (Droplet)

### 1. Crear el Droplet

- **Image**: Ubuntu 22.04 LTS
- **Plan mínimo recomendado**: 4 GB RAM / 2 vCPUs / 80 GB SSD (~$24/mes)
- **Authentication**: SSH Key

### 2. Instalar Docker en el Droplet

```bash
ssh root@<IP_DEL_DROPLET>
curl -fsSL https://get.docker.com | sh
```

### 3. Subir el modelo al Droplet

El modelo no está en git (pesa ~1.1 GB). Súbelo una sola vez:

```bash
# Desde tu máquina local
scp ./models/ggml-large-v3-q5_0.bin root@<IP_DEL_DROPLET>:/root/models/
```

### 4. Clonar el repositorio y hacer el build

```bash
# En el Droplet
git clone https://github.com/tu-usuario/transcription-service.git /app
cd /app

mkdir -p models
cp /root/models/ggml-large-v3-q5_0.bin ./models/

# Build (tarda ~5-10 min, compila whisper.cpp desde cero)
docker build -t transcription-service .
```

### 5. Correr el contenedor

```bash
docker run -d \
  --name transcription \
  --restart unless-stopped \
  -p 80:5001 \
  -e WHISPER_LANG=es \
  transcription-service

# Verificar
docker logs -f transcription
curl http://localhost/health
```

### 6. Configurar firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 7. (Opcional) HTTPS con Nginx + Certbot

```bash
apt install -y nginx certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/transcription <<'EOF'
server {
    server_name tu-dominio.com;
    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_read_timeout 600s;
    }
}
EOF

ln -s /etc/nginx/sites-available/transcription /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d tu-dominio.com
```

### Actualizar el servicio

```bash
# En el Droplet
cd /app
git pull
docker build -t transcription-service .
docker stop transcription && docker rm transcription
docker run -d \
  --name transcription \
  --restart unless-stopped \
  -p 80:5001 \
  -e WHISPER_LANG=es \
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

---

## Estructura del proyecto

```
transcription-service/
├── app.py              # Flask: endpoints HTTP
├── job_queue.py        # Cola en memoria + estado + resultados
├── queue_worker.py     # Worker: procesa jobs en background
├── transcriber.py      # Descarga de video + parseo de segmentos
├── transcribir.sh      # Conversión WAV + ejecución de whisper-cli
├── setup.sh            # Instala binario, modelo y dependencias (desarrollo local)
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
├── models/             # No incluido en git ni en Docker build (se copia manualmente)
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
      ├── whisper-cli     → transcribe → <uuid>.wav.json
      └── job_results     → almacena segmentos en memoria

GET /transcribe/<id>/result
      │
      └── lee job_results → devuelve segmentos al cliente
```

> **Nota**: la cola de jobs es en memoria. Si el contenedor se reinicia, los jobs en curso se pierden. Para producción con alta disponibilidad, reemplazar con Redis + Celery.
