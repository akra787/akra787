# Instrucciones para Claude: hacer vídeos

El usuario habla español. Cuando pida un vídeo ("hazme un vídeo de…"), hazlo de principio a fin sin preguntar
salvo que falte algo imprescindible:

1. Asegura las herramientas: `bash video/instalar.sh` (rápido si ya están instaladas).
2. Escribe el guion en `videos/<nombre>.json` siguiendo el formato de `video/README.md`
   (por defecto: vertical 1080x1920, idioma `es`, música `alegre`, 4–8 escenas, textos cortos y voz natural).
   Si el usuario sube imágenes, úsalas con `"imagen"` en las escenas.
3. Genera: `python3 video/make_video.py videos/<nombre>.json` → crea `videos/<nombre>.mp4`.
4. Comprueba un fotograma (`ffmpeg -ss 3 -i videos/<nombre>.mp4 -frames:v 1 frame.png` en el scratchpad) y míralo.
5. Envía el MP4 al usuario con SendUserFile, y haz commit + push de `videos/<nombre>.json` y `.mp4`.

La voz por defecto es Piper (realista, voces en `/opt/piper-voces`, descargadas por `instalar.sh` desde
huggingface.co, que está permitido en la red del entorno). Si no hay voces Piper, se usa espeak-ng (robótica).
No hay generadores de imagen en la nube; las imágenes se dibujan en local (Pillow, numpy, ffmpeg).
