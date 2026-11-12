#!/usr/bin/env bash
# Instala lo necesario para generar vídeos (idempotente).
set -e
need_apt=""
command -v ffmpeg >/dev/null || need_apt="$need_apt ffmpeg"
command -v espeak-ng >/dev/null || need_apt="$need_apt espeak-ng"
[ -f /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf ] || need_apt="$need_apt fonts-dejavu-core"
if [ -n "$need_apt" ]; then
  apt-get install -y $need_apt >/dev/null 2>&1 || { apt-get update >/dev/null 2>&1; apt-get install -y $need_apt >/dev/null; }
fi
python3 -c "import PIL, numpy" 2>/dev/null || pip install -q pillow numpy
python3 -c "import piper" 2>/dev/null || pip install -q piper-tts

# Voces realistas de Piper (necesita acceso a huggingface.co; si falla se usa espeak-ng)
DIR="${PIPER_VOCES:-/opt/piper-voces}"
mkdir -p "$DIR"
URL=https://huggingface.co/rhasspy/piper-voices/resolve/main/es
for v in es_ES/davefx/medium/es_ES-davefx-medium es_ES/sharvard/medium/es_ES-sharvard-medium es_MX/claude/high/es_MX-claude-high; do
  n=$(basename "$v")
  for ext in onnx onnx.json; do
    [ -s "$DIR/$n.$ext" ] || curl -sSfL -o "$DIR/$n.$ext" "$URL/$v.$ext" || { rm -f "$DIR/$n.$ext"; echo "Aviso: no se pudo descargar la voz $n"; }
  done
done
echo "Herramientas de vídeo listas."
