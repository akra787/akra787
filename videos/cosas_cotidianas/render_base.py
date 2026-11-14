#!/usr/bin/env python3
"""Utilidades comunes del vídeo «5 cosas cotidianas…» (texto, emojis, subtítulos, cabecera).

Animaciones dibujadas en local (Pillow + emojis Twemoji en SVG, CC-BY 4.0) sincronizadas
con la voz `voz.mp3` usando los tiempos de palabra de `palabras.json` (faster-whisper).

    python3 videos/cosas_cotidianas/render.py   →  videos/cosas_cotidianas.mp4
"""
import io
import json
import math
import os
import random
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "video"))
import make_video as mv  # noqa: E402  (música y utilidades de audio)

W, H, FPS = 1080, 1920, 30
VOZ = os.path.join(AQUI, "voz.mp3")
SALIDA = os.path.join(AQUI, "..", "cosas_cotidianas.mp4")
FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
AMARILLO = (255, 214, 64)
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)

# (inicio, fin, nombre, color arriba, color abajo, acento)
SECCIONES = [
    (0.0, 3.55, "intro", "#24104f", "#4a1170", "#FFD640"),
    (3.55, 12.0, "gancho", "#121a45", "#2e1458", "#FFD640"),
    (12.0, 23.45, "puerta", "#0c3346", "#101c40", "#4FE3D0"),
    (23.45, 33.8, "movil", "#33103f", "#13143d", "#FF5C8A"),
    (33.8, 42.75, "bostezo", "#43300c", "#24133a", "#FFB347"),
    (42.75, 51.85, "semaforo", "#430f12", "#16102e", "#FF4D4D"),
    (51.85, 62.85, "mirada", "#06070f", "#1f0b33", "#B69CFF"),
    (62.85, 72.2, "final", "#0c3524", "#101b40", "#3DDC84"),
]
TITULOS = {
    "puerta": (1, "¿POR QUÉ OLVIDAS A QUÉ IBAS?"),
    "movil": (2, "¿POR QUÉ VUELVES A MIRAR EL MÓVIL?"),
    "bostezo": (3, "¿POR QUÉ SE CONTAGIA EL BOSTEZO?"),
    "semaforo": (4, "¿POR QUÉ EL SEMÁFORO TARDA MÁS?"),
    "mirada": (5, "¿POR QUÉ SIENTES QUE TE MIRAN?"),
}
# (sección, inicio, líneas) de la tarjeta de explicación
EXPLICACIONES = {
    "puerta": (16.3, ["CAMBIO DE CONTEXTO", "= «EFECTO PUERTA»"]),
    "movil": (28.44, ["COSTUMBRE", "+ ESPERAS ALGO NUEVO"]),
    "bostezo": (37.84, ["ES CONTAGIOSO", "¡INCLUSO EN VÍDEO!"]),
    "semaforo": (47.04, ["IMPACIENCIA", "= MÁS ATENCIÓN AL TIEMPO"]),
    "mirada": (57.14, ["TU CEREBRO DETECTA", "MOVIMIENTOS Y SONIDOS"]),
}
STAGE_Y = 800


# ------------------------------------------------------------------ utilidades
def cl(x):
    return max(0.0, min(1.0, x))


def pr(t, a, b):
    return cl((t - a) / (b - a)) if b > a else float(t >= a)


def eo(x):
    return 1 - (1 - x) ** 3


def eio(x):
    return 3 * x * x - 2 * x * x * x


def eob(x, k=1.9):
    x = cl(x)
    return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2


def pop(t, t0, d=0.4):
    return eob(pr(t, t0, t0 + d))


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mezcla(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


@lru_cache(maxsize=256)
def fuente(size, black=True):
    return ImageFont.truetype(FONT_BLACK if black else FONT_BOLD, max(4, int(size)))


def emoji_code(ch):
    return "-".join(f"{ord(c):x}" for c in ch if ord(c) != 0xFE0F)


@lru_cache(maxsize=2048)
def emoji(ch, size):
    png = cairosvg.svg2png(url=os.path.join(AQUI, "emoji", emoji_code(ch) + ".svg"),
                           output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def sprite(img, ch, cx, cy, size, alpha=1.0, rot=0.0, flip=False, sombra=True):
    size = int(round(size / 4) * 4)
    if size < 8 or alpha <= 0.01:
        return
    s = emoji(ch, size)
    if flip:
        s = s.transpose(Image.FLIP_LEFT_RIGHT)
    if rot:
        s = s.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        s = s.copy()
        s.putalpha(s.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(cx - s.width / 2), int(cy - s.height / 2)
    if sombra:
        sh = Image.new("RGBA", s.size, (0, 0, 0, 0))
        sh.putalpha(s.getchannel("A").point(lambda v: int(v * 0.45)))
        img.paste((0, 0, 0), (x + size // 30 + 4, y + size // 22 + 6), sh.getchannel("A"))
    img.paste(s, (x, y), s)


def texto(d, txt, cx, cy, size, color=BLANCO, alpha=1.0, stroke=None, black=True, anchor="mm"):
    if alpha <= 0.01 or size < 4:
        return
    f = fuente(size, black)
    a = int(255 * cl(alpha))
    sw = stroke if stroke is not None else max(2, int(size * 0.08))
    d.text((cx + size * 0.03, cy + size * 0.06), txt, font=f, fill=(0, 0, 0, int(a * 0.5)), anchor=anchor,
           stroke_width=sw, stroke_fill=(0, 0, 0, int(a * 0.5)))
    d.text((cx, cy), txt, font=f, fill=color + (a,), anchor=anchor, stroke_width=sw,
           stroke_fill=(10, 8, 20, a))


def texto_pop(d, txt, cx, cy, size, t, t0, color=BLANCO, d_in=0.35):
    k = pop(t, t0, d_in)
    if t < t0:
        return
    texto(d, txt, cx, cy, size * k, color, alpha=pr(t, t0, t0 + 0.12))


def ancho(txt, size, black=True):
    return fuente(size, black).getlength(txt)


def caja(d, x0, y0, x1, y1, r, fill, outline=None, w=0):
    d.rounded_rectangle((x0, y0, x1, y1), r, fill=fill, outline=outline, width=w)


def anillo(d, cx, cy, r, color, w):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)


# ------------------------------------------------------------------ fondos
def fondo_seccion(top, bot, acento):
    t, b, a = np.array(hexrgb(top), float), np.array(hexrgb(bot), float), np.array(hexrgb(acento), float)
    y = np.linspace(0, 1, H)[:, None, None]
    img = t * (1 - y) + b * y
    img = np.broadcast_to(img, (H, W, 3)).copy()
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt((xx - W / 2) ** 2 + ((yy - STAGE_Y) * 0.9) ** 2)
    glow = np.exp(-(dist / 430) ** 2)[..., None] * 0.22
    img = img * (1 - glow) + a * glow
    vig = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    img *= (1 - 0.55 * np.clip(vig - 0.25, 0, 1))[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


FONDOS = {}


def seccion(t):
    for s in SECCIONES:
        if s[0] <= t < s[1]:
            return s
    return SECCIONES[-1]


rng = random.Random(3)
PARTICULAS = [(rng.random() * W, rng.random() * H, rng.uniform(3, 9), rng.uniform(20, 70), rng.random() * 6.28)
              for _ in range(40)]


def particulas(d, t, acento):
    for x, y, r, v, ph in PARTICULAS:
        yy = (y - t * v) % (H + 40) - 20
        xx = x + 18 * math.sin(t * 0.8 + ph)
        a = int(60 + 50 * math.sin(t * 2 + ph))
        d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=acento + (a,))


# ------------------------------------------------------------------ subtítulos
def cargar_chunks():
    pal = json.load(open(os.path.join(AQUI, "palabras.json")))
    arreglos = {"cinco": "5", "diez": "10"}
    out = []
    for i, (a, b, w) in enumerate(pal):
        base = w.strip(".,¿?").lower()
        if base in arreglos:
            w = w.lower().replace(base, arreglos[base])
        if base == "que" and i + 1 < len(pal) and pal[i + 1][2].startswith("ibas"):
            w = "qué"
        out.append([a, b, w])
    chunks, cur = [], []
    for i, wd in enumerate(out):
        if cur and (wd[0] - cur[-1][1] > 0.45 or len(cur) >= 4 or wd[2].startswith("¿")):
            chunks.append(cur)
            cur = []
        cur.append(wd)
        if wd[2][-1] in ".,?!":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    res = []
    for i, c in enumerate(chunks):
        fin = chunks[i + 1][0][0] if i + 1 < len(chunks) else c[-1][1] + 0.6
        fin = min(fin, c[-1][1] + 0.7)
        res.append((c[0][0] - 0.05, fin, c))
    return res


CHUNKS = cargar_chunks()


def subtitulos(d, t, acento):
    if t < 3.5:
        return
    for a, b, c in CHUNKS:
        if a <= t < b:
            size = 76
            words = [w[2].upper() for w in c]
            sp = ancho(" ", size) + 16
            lines, line, lw = [], [], 0
            for i, w in enumerate(words):
                wl = ancho(w, size)
                if line and lw + sp + wl > 940:
                    lines.append(line)
                    line, lw = [], 0
                line.append(i)
                lw += (sp if len(line) > 1 else 0) + wl
            lines.append(line)
            k = pop(t, a, 0.25)
            y0 = 1600 - (len(lines) - 1) * 50
            for li, line in enumerate(lines):
                tot = sum(ancho(words[i], size) for i in line) + sp * (len(line) - 1)
                x = W / 2 - tot / 2
                y = y0 + li * 100
                for i in line:
                    wl = ancho(words[i], size)
                    activo = c[i][0] <= t
                    actual = activo and (i == len(c) - 1 or t < c[i + 1][0])
                    col = AMARILLO if actual else (BLANCO if activo else (200, 200, 215))
                    sz = size * k * (1.03 if actual else 1.0)
                    texto(d, words[i], W / 2 + (x + wl / 2 - W / 2) * k, y - (6 if actual else 0), sz, col,
                          alpha=1.0 if activo else 0.55, stroke=9)
                    x += wl + sp
            return


# ------------------------------------------------------------------ cabecera y tarjeta
def cabecera(img, d, t, nombre, t0, acento):
    if nombre not in TITULOS:
        return
    n, titulo = TITULOS[nombre]
    k = pop(t, t0 + 0.05, 0.45)
    r = 74 * k
    cx, cy = 150, 250
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=acento + (255,))
    anillo(d, cx, cy, r + 10, acento + (120,), 4)
    texto(d, f"#{n}", cx, cy + 2, 70 * k, (20, 14, 30), stroke=0)
    # título partido en 2 líneas
    palabras = titulo.split()
    mitad = len(palabras) // 2 + (1 if len(palabras) % 2 else 0)
    l1, l2 = " ".join(palabras[:mitad]), " ".join(palabras[mitad:])
    a = pr(t, t0 + 0.2, t0 + 0.5)
    dx = (1 - eo(a)) * 120
    for i, l in enumerate((l1, l2)):
        size = 58
        while ancho(l, size) > 760:
            size -= 2
        d.text((260 + dx, 205 + i * 72), l, font=fuente(size), fill=BLANCO + (int(255 * a),), anchor="lm",
               stroke_width=5, stroke_fill=(10, 8, 20, int(255 * a)))


def tarjeta(d, t, nombre, acento, salida):
    if nombre not in EXPLICACIONES:
        return
    t0, lineas = EXPLICACIONES[nombre]
    if t < t0:
        return
    a = eo(pr(t, t0, t0 + 0.45)) * (1 - pr(t, salida - 0.3, salida))
    y = 1235 + (1 - a) * 140
    caja(d, 70, y, W - 70, y + 205, 34, (12, 10, 24, int(225 * a)), outline=acento + (int(255 * a),), w=6)
    lab = "LA EXPLICACIÓN"
    lw = ancho(lab, 34) + 50
    caja(d, W / 2 - lw / 2, y - 26, W / 2 + lw / 2, y + 26, 26, acento + (int(255 * a),))
    texto(d, lab, W / 2, y + 1, 34, (15, 12, 25), alpha=a, stroke=0)
    for i, l in enumerate(lineas):
        ti = t0 + 0.25 + i * 1.2
        size = 66 if i == 0 else 50
        while ancho(l, size) > 880:
            size -= 2
        k = pop(t, ti, 0.35)
        texto(d, l, W / 2, y + 85 + i * 75, size * k, acento if i == 0 else BLANCO, alpha=a * pr(t, ti, ti + 0.1))


def progreso(d, t, nombre):
    orden = ["puerta", "movil", "bostezo", "semaforo", "mirada"]
    if nombre not in orden:
        return
    idx = orden.index(nombre)
    w, g = 150, 16
    x0 = W / 2 - (5 * w + 4 * g) / 2
    for i, sec in enumerate(orden):
        s = [x for x in SECCIONES if x[2] == sec][0]
        x = x0 + i * (w + g)
        caja(d, x, 80, x + w, 94, 7, (255, 255, 255, 60))
        f = 1.0 if i < idx else (pr(t, s[0], s[1]) if i == idx else 0)
        if f > 0:
            caja(d, x, 80, x + max(14, w * f), 94, 7, hexrgb(s[5]) + (255,))


