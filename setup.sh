#!/bin/bash
# setup.sh — Prepara el entorno del transcription-service:
#   1. Clona y compila whisper.cpp en ./build/
#   2. Descarga el modelo en ./models/
#   3. Instala dependencias Python

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="${WHISPER_MODEL_NAME:-ggml-large-v3-q5_0.bin}"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${MODEL_NAME}"

echo "=== [1/3] Compilando whisper.cpp ==="

if [ -f "$SCRIPT_DIR/build/bin/whisper-cli" ]; then
  echo "    whisper-cli ya existe, omitiendo compilación."
else
  TMP_SRC="$SCRIPT_DIR/_whisper_src"
  git clone --depth=1 https://github.com/ggerganov/whisper.cpp.git "$TMP_SRC"
  cmake -S "$TMP_SRC" -B "$SCRIPT_DIR/build" -DGGML_CUDA=OFF
  cmake --build "$SCRIPT_DIR/build" --config Release
  rm -rf "$TMP_SRC"
  echo "    Compilación completada."
fi

echo ""
echo "=== [2/3] Descargando modelo ${MODEL_NAME} ==="

mkdir -p "$SCRIPT_DIR/models"

if [ -f "$SCRIPT_DIR/models/$MODEL_NAME" ]; then
  echo "    Modelo ya existe, omitiendo descarga."
else
  echo "    Descargando desde Hugging Face (puede tardar varios minutos)..."
  wget -q --show-progress -O "$SCRIPT_DIR/models/$MODEL_NAME" "$MODEL_URL"
  echo "    Modelo descargado."
fi

echo ""
echo "=== [3/3] Instalando dependencias Python ==="
pip3 install --no-cache-dir -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Setup completado ==="
echo "    Binario : $SCRIPT_DIR/build/bin/whisper-cli"
echo "    Modelo  : $SCRIPT_DIR/models/$MODEL_NAME"
echo ""
echo "Para iniciar el servicio:"
echo "    python3 app.py"
