#!/bin/bash
# transcribir.sh — Convierte video a WAV y ejecuta whisper-cli
# Paths configurables via variables de entorno con defaults razonables

VIDEO_PATH="$1"

# Paths al binario y modelo de whisper.cpp (sobreescribibles por env)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHISPER_BIN="${WHISPER_BIN:-$SCRIPT_DIR/build/bin/whisper-cli}"
MODEL_PATH="${WHISPER_MODEL:-$SCRIPT_DIR/models/ggml-large-v3-q5_0.bin}"
LANGUAGE="${WHISPER_LANG:-es}"

SAMPLES_DIR="./samples"
TMP_ID=$(basename "$VIDEO_PATH" | cut -d. -f1)
WAV_PATH="${SAMPLES_DIR}/${TMP_ID}.wav"
SEGMENTS_FILE="${WAV_PATH}.json"

# Validaciones
if [ -z "$VIDEO_PATH" ]; then
  echo '{"error": "Falta ruta del video"}' >&2
  exit 1
fi

if [ ! -f "$VIDEO_PATH" ]; then
  echo "{\"error\": \"Archivo no existe: $VIDEO_PATH\"}" >&2
  exit 1
fi

if [ ! -f "$WHISPER_BIN" ]; then
  echo "{\"error\": \"whisper-cli no encontrado en: $WHISPER_BIN\"}" >&2
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "{\"error\": \"Modelo no encontrado en: $MODEL_PATH\"}" >&2
  exit 1
fi

mkdir -p "$SAMPLES_DIR"

# Convertir video a WAV 16kHz mono
ffmpeg -y -i "$VIDEO_PATH" -ar 16000 -ac 1 -c:a pcm_s16le "$WAV_PATH" > /dev/null 2>&1

if [ $? -ne 0 ]; then
  echo '{"error": "ffmpeg falló al convertir el video"}' >&2
  exit 1
fi

# Ejecutar transcripción
THREADS="${WHISPER_THREADS:-8}"
"$WHISPER_BIN" -m "$MODEL_PATH" -f "$WAV_PATH" -otxt -osrt -oj -l "$LANGUAGE" -t "$THREADS" > /dev/null 2>&1

if [ ! -f "$SEGMENTS_FILE" ]; then
  echo "{\"error\": \"No se generó el archivo JSON: $SEGMENTS_FILE\"}" >&2
  exit 1
fi

# Debug: mostrar las claves del JSON generado por whisper
echo "[DEBUG] Claves del JSON generado:" >&2
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(list(d.keys()))" "$SEGMENTS_FILE" >&2

# Extraer segmentos — intentar .transcription, luego .segments como fallback
TRANSCRIPTION=$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
val = d.get('transcription') or d.get('segments')
if val is not None:
    print(json.dumps(val))
" "$SEGMENTS_FILE")

if [ -z "$TRANSCRIPTION" ] || [ "$TRANSCRIPTION" = "null" ]; then
  echo "[DEBUG] JSON completo del archivo:" >&2
  cat "$SEGMENTS_FILE" >&2
  echo "{\"error\": \"No se encontró clave transcription ni segments en el JSON\"}" >&2
  exit 1
fi

echo "{\"segments\": $TRANSCRIPTION }"

# Limpieza de temporales
rm -f "$VIDEO_PATH" "$WAV_PATH" "$SEGMENTS_FILE"
