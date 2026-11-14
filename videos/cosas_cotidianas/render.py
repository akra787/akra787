#!/usr/bin/env python3
"""Vídeo «5 cosas cotidianas que tienen una explicación».

Cada curiosidad tiene su propio escenario dibujado en local (salón/cocina, mesa, metro, calle, noche) con
personajes animados (Pillow + emojis Twemoji en SVG, CC-BY 4.0), sincronizado con la voz `voz.mp3` usando
los tiempos de palabra de `palabras.json` (faster-whisper).

    python3 videos/cosas_cotidianas/render.py                 →  videos/cosas_cotidianas.mp4
    python3 videos/cosas_cotidianas/render.py --frame 15 a.png   (vista previa de un fotograma)
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from render_base import *  # noqa
from render_base import mv, FONDOS, SALIDA, VOZ  # noqa
import escenas  # noqa

def _sombras():
    a = np.zeros((H, W), np.float32)
    y = np.arange(H, dtype=np.float32)
    top = np.clip(1 - y / 420, 0, 1) ** 1.5 * 170
    bot = np.clip((y - 1180) / 740, 0, 1) ** 1.2 * 200
    a[:] = np.maximum(top, bot)[:, None]
    return Image.fromarray(a.astype(np.uint8))


SOMBRA = _sombras()
CON_ESCENARIO = {"puerta", "movil", "bostezo", "semaforo", "mirada"}


def render_seccion(sec, t):
    t0, t1, nombre, top, bot, acs = sec
    ac = hexrgb(acs)
    if nombre not in FONDOS:
        FONDOS[nombre] = fondo_seccion(top, bot, acs)
    img = FONDOS[nombre].copy()
    d = ImageDraw.Draw(img, "RGBA")
    if nombre not in CON_ESCENARIO:
        particulas(d, t, ac)
    escenas.ESCENAS[nombre](img, d, t, ac)
    z, cx, cy = escenas.camara(nombre, t, t0, t1)
    if z > 1.001:
        w, h = W / z, H / z
        x0 = min(max(0, cx - w / 2), W - w)
        y0 = min(max(0, cy - h / 2), H - h)
        img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))
    if nombre in CON_ESCENARIO:
        img.paste((0, 0, 0), (0, 0), SOMBRA)
    d = ImageDraw.Draw(img, "RGBA")
    cabecera(img, d, t, nombre, t0, ac)
    progreso(d, t, nombre)
    tarjeta(d, t, nombre, ac, t1 + 1)
    return img


TRANS = 0.32


def frame(t):
    i = next((k for k, s in enumerate(SECCIONES) if s[0] <= t < s[1]), len(SECCIONES) - 1)
    sec = SECCIONES[i]
    img = render_seccion(sec, t)
    if i > 0 and t - sec[0] < TRANS:
        prev = SECCIONES[i - 1]
        old = render_seccion(prev, min(t, prev[1] - 0.001))
        f = eio((t - sec[0]) / TRANS)
        off = int(W * (1 - f))
        lienzo = Image.new("RGB", (W, H))
        lienzo.paste(old, (off - W, 0))
        lienzo.paste(img, (off, 0))
        dd = ImageDraw.Draw(lienzo, "RGBA")
        dd.rectangle((off - 14, 0, off + 14, H), fill=hexrgb(sec[5]) + (255,))
        img = lienzo
    d = ImageDraw.Draw(img, "RGBA")
    subtitulos(d, t, hexrgb(sec[5]))
    if t < 0.15:
        img = Image.blend(img, Image.new("RGB", (W, H), BLANCO), 0.6 * (1 - t / 0.15))
    return img


# ------------------------------------------------------------------ render
def render_trozo(args):
    i, a, b, ruta = args
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                          "-pix_fmt", "yuv420p", ruta], stdin=subprocess.PIPE)
    for n in range(a, b):
        p.stdin.write(frame(n / FPS).tobytes())
    p.stdin.close()
    p.wait()
    return ruta


def tono(f0, f1, dur, vol=0.3, tipo="sin"):
    n = int(dur * mv.SR)
    tt = np.arange(n) / mv.SR
    fr = np.linspace(f0, f1, n)
    ph = 2 * np.pi * np.cumsum(fr) / mv.SR
    s = np.sin(ph) if tipo == "sin" else np.sign(np.sin(ph)) * 0.5
    return s * np.exp(-tt * 8 / dur) * vol


def whoosh(dur=0.35, vol=0.25):
    n = int(dur * mv.SR)
    ruido = np.random.default_rng(1).normal(0, 1, n)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    # filtro paso-bajo sencillo que se abre
    out = np.zeros(n)
    acc = 0
    alpha = np.linspace(0.02, 0.25, n)
    for i in range(n):
        acc += alpha[i] * (ruido[i] - acc)
        out[i] = acc
    return out / (np.abs(out).max() + 1e-9) * env * vol


def audio(dur, ruta):
    voz_wav = ruta + ".voz.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", VOZ, "-ac", "1", "-ar", str(mv.SR), voz_wav], check=True)
    voz = mv.read_wav(voz_wav)
    n = int(dur * mv.SR) + mv.SR
    mix = np.zeros(n)
    mus = mv.music(dur, "alegre", seed=11)
    # la música baja mientras habla la voz (ducking según la envolvente)
    env = np.abs(np.pad(voz, (0, max(0, len(mus) - len(voz))))[:len(mus)])
    k = int(0.25 * mv.SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    duck = 1 - 0.45 * np.clip(env / 0.05, 0, 1)
    mix[:len(mus)] += mus * duck * 1.3
    mix[:len(voz)] += voz * 1.0
    efectos = []
    for s in SECCIONES[1:]:
        efectos.append((s[0] - 0.12, whoosh()))
    pops = [0.0, 0.32, 0.72, 2.3, 2.6, 4.6, 4.9, 5.2, 5.5, 5.8, 9.6, 12.4, 14.2, 15.05, 17.0, 17.35, 17.9, 20.6, 24.0, 27.4, 31.2, 31.6, 32.0,
            34.6, 36.5, 38.4, 38.7, 40.45, 41.5, 43.6, 47.2, 49.3, 50.9, 53.4, 55.55, 57.4, 59.0, 60.4, 63.4, 63.62, 63.84, 64.06, 64.28, 68.3, 70.2]
    for p in pops:
        efectos.append((p, tono(500, 900, 0.12, 0.18)))
    for p in [65.4, 65.65, 65.9, 66.15, 66.4]:
        efectos.append((p, tono(1200, 1500, 0.1, 0.12)))
    for i in range(10):  # tic-tac del contador de 10 s
        efectos.append((26.4 + i * 0.08, tono(1800, 1800, 0.04, 0.08, "sq")))
    for st, e in efectos:
        a = int(max(0, st) * mv.SR)
        b = min(n, a + len(e))
        mix[a:b] += e[:b - a]
    mix = mix[:int(dur * mv.SR)]
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    mv.write_wav(ruta, mix)
    os.remove(voz_wav)


def main():
    import tempfile
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "csv=p=0", VOZ]).decode()) + 0.6
    total = int(dur * FPS)
    if len(sys.argv) > 1 and sys.argv[1] == "--frame":  # vista previa: --frame 15.2 salida.png
        frame(float(sys.argv[2])).save(sys.argv[3])
        return
    tmp = tempfile.mkdtemp()
    nproc = os.cpu_count() or 2
    paso = math.ceil(total / nproc)
    trozos = [(i, i * paso, min(total, (i + 1) * paso), os.path.join(tmp, f"p{i}.mp4")) for i in range(nproc)]
    with Pool(nproc) as pool:
        rutas = pool.map(render_trozo, trozos)
    lista = os.path.join(tmp, "lista.txt")
    open(lista, "w").write("".join(f"file '{r}'\n" for r in rutas))
    wav = os.path.join(tmp, "audio.wav")
    audio(dur, wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    os.path.abspath(SALIDA)], check=True)
    print("Listo:", os.path.abspath(SALIDA))


if __name__ == "__main__":
    main()
