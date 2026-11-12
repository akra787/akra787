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
echo "Herramientas de vídeo listas."
