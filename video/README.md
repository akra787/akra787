# Generador de vídeos

```bash
bash video/instalar.sh                       # ffmpeg, espeak-ng, Piper + voces, Pillow, numpy
python3 video/make_video.py videos/mi.json   # → videos/mi.mp4
```

## Formato del guion (JSON)

| Clave global | Valores | Por defecto |
|---|---|---|
| `formato` | `vertical` (1080x1920), `horizontal` (1920x1080), `cuadrado` | `vertical` |
| `idioma` | código de voz de espeak-ng: `es`, `es-419`, `en`, `fr`… | `es` |
| `voz_modelo` | voz realista Piper: `es_ES-davefx-medium` (hombre, España), `es_ES-sharvard-medium` (España), `es_MX-claude-high` (México), o `espeak` (robótica) | `es_ES-davefx-medium` |
| `velocidad_voz` | palabras/minuto (150 = normal) | `150` |
| `voz_hablante` | número de hablante en voces con varios (p. ej. `es_ES-sharvard-medium`: 0 = hombre, 1 = mujer) | – |
| `voz_efecto` | `ia`: voz con más presencia y volumen, estilo vídeos de IA/TikTok | – |
| `voz_audio` | `false` = sin locución: el texto de `voz` solo sale como subtítulo (duración según `velocidad_lectura`, 160 palabras/min) | `true` |
| `musica` | `alegre`, `epica`, `tranquila` o `no` | `alegre` |
| `musica_archivo` | ruta a un mp3/wav propio (sustituye a la generada) | – |
| `volumen_musica`, `volumen_voz` | multiplicadores | `1.0` |
| `transicion` | segundos de fundido entre escenas | `0.5` |
| `marca` | texto en la esquina (p. ej. `@usuario`) | – |
| `salida` | ruta del MP4 (relativa al JSON) | mismo nombre que el JSON |
| `fondo`, `acento`, `color_texto`, `subtitulos`, `particulas` | valores por defecto para todas las escenas | – |

Cada elemento de `escenas`:

| Clave | Descripción |
|---|---|
| `titulo` | texto grande |
| `texto` | texto secundario |
| `voz` | locución (también se muestra como subtítulo) |
| `voz_modelo` | voz distinta solo para esta escena |
| `duracion` | segundos; si falta, se ajusta a la voz (mín. 3 s) |
| `fondo` | color `"#rrggbb"` o degradado `["#a", "#b"]` |
| `imagen` | foto de fondo (ruta relativa al JSON); `oscurecer` 0–1 |
| `vineta` | `false` quita el viñeteado (bordes oscuros) de las fotos | `true` |
| `zoom` | `in` / `out` (efecto Ken Burns) · `pan`: `derecha` / `izquierda` |
| `posicion_y` | altura del título (0–1), por defecto `0.38` |
| `personaje` | stickman animado: `{"pose": …, "x": 0.5, "y": 0.74, "altura": 0.3, "objeto": "taza"}` · poses: `saludo`, `beber`, `dolor`, `pensando`, `dormido`, `energia`, `feliz`, `señalar` · objeto: `taza`, `taza_tachada` |
| `encuesta` | opciones A/B/C… para que comenten su letra: `{"opciones": [...], "y": 0.36, "llamada": "¡Comenta tu letra!"}` |
| `pregunta` | banda «comenta» con icono de bocadillo: `{"texto": "...", "y": 0.3}` |

Ejemplo: `video/ejemplos/demo.json` → `videos/demo.mp4`.
