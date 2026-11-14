#!/usr/bin/env python3
"""Vídeo «5 cosas cotidianas que tienen una explicación».

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
            sp = ancho(" ", size) + 26
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
                    sz = size * k * (1.04 if actual else 1.0)
                    texto(d, words[i], x + wl / 2, y - (6 if actual else 0), sz, col,
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


# ------------------------------------------------------------------ escenas
def esc_intro(img, d, t, ac):
    k = pop(t, 0.0, 0.5)
    rot = math.sin(t * 3) * 4
    f = fuente(560)
    lay = Image.new("RGBA", (700, 700))
    ld = ImageDraw.Draw(lay)
    ld.text((350, 350), "5", font=f, fill=AMARILLO, anchor="mm", stroke_width=22, stroke_fill=(20, 10, 40))
    lay = lay.rotate(rot, resample=Image.BICUBIC)
    s = max(8, int(700 * k))
    lay = lay.resize((s, s), Image.BICUBIC)
    img.paste(lay, (int(W / 2 - s / 2), int(560 - s / 2)), lay)
    texto_pop(d, "COSAS", W / 2, 960, 130, t, 0.32)
    texto_pop(d, "COTIDIANAS", W / 2, 1090, 130, t, 0.72)
    texto_pop(d, "QUE TIENEN UNA", W / 2, 1220, 72, t, 1.44)
    if t >= 2.3:
        k2 = pop(t, 2.3, 0.4)
        tw = ancho("EXPLICACIÓN", 112) + 60
        caja(d, W / 2 - tw / 2 * k2, 1345 - 75 * k2, W / 2 + tw / 2 * k2, 1345 + 75 * k2, 30, AMARILLO + (255,))
        texto(d, "EXPLICACIÓN", W / 2, 1345, 112 * k2, (25, 12, 45), stroke=0)
    sprite(img, "😳", 840, 400, 260 * pop(t, 2.6, 0.45), rot=-12 + 6 * math.sin(t * 6))


GANCHO_ICONOS = [("🚪", "PUERTAS"), ("📱", "MÓVIL"), ("🥱", "BOSTEZOS"), ("🚦", "SEMÁFORO"), ("👀", "MIRADAS")]


def esc_gancho(img, d, t, ac):
    texto_pop(d, "APUESTO A QUE...", W / 2, 260, 84, t, 3.7)
    pos = [(250, 600), (540, 600), (830, 600), (395, 900), (685, 900)]
    tiempos = [4.6, 4.9, 5.2, 5.5, 5.8]
    dim = pr(t, 9.4, 9.8)
    foco = eo(pr(t, 9.5, 10.2))
    for i, ((ch, lab), (x, y), t0) in enumerate(zip(GANCHO_ICONOS, pos, tiempos)):
        if t < t0:
            continue
        k = pop(t, t0, 0.4)
        bob = math.sin(t * 3 + i) * 8
        if i == 4:
            x = x + (W / 2 - x) * foco
            y = y + (840 - y) * foco
            size = 210 + 230 * foco
            r = 135 + 120 * foco
            alpha = 1
        else:
            size, r, alpha = 210, 135, 1 - 0.75 * dim
        d.ellipse((x - r * k, y + bob - r * k, x + r * k, y + bob + r * k),
                  fill=(255, 255, 255, int(28 * alpha)), outline=ac + (int(200 * alpha),), width=5)
        sprite(img, ch, x, y + bob, size * k, alpha=alpha)
        texto(d, lab, x, y + bob + r * k + 40, 40 * k, BLANCO, alpha=alpha * pr(t, t0, t0 + 0.2) * (1 - foco if i == 4 else 1))
        # «pero no sabes por qué»: interrogantes
        if 7.6 <= t and i < 4:
            q = pop(t, 7.6 + i * 0.12, 0.3)
            sprite(img, "❓", x + 95, y + bob - 95, 90 * q, alpha=alpha, rot=15)
    if 6.0 <= t < 9.6:
        texto_pop(d, "TODOS LOS DÍAS", W / 2, 1180, 92, t, 6.0, AMARILLO)
    if 7.45 <= t < 9.6:
        texto_pop(d, "...Y NO SABES POR QUÉ", W / 2, 1300, 64, t, 7.45)
    if t >= 9.6:
        texto_pop(d, "LA ÚLTIMA...", W / 2, 1230, 104, t, 9.6, AMARILLO)
        texto_pop(d, "¡SEGURO QUE TE HA PASADO!", W / 2, 1350, 58, t, 10.0)
    if t >= 4.6:
        texto(d, "5 COSAS QUE HACES", W / 2, 370, 62, ac, alpha=pr(t, 4.6, 4.9) * (1 - dim))


def puerta(d, x, y, abierta, ac):
    """Puerta dibujada: marco + hoja que se abre (0..1)."""
    w, h = 230, 430
    caja(d, x - w / 2 - 22, y - h - 22, x + w / 2 + 22, y + 10, 10, (90, 58, 38, 255))
    d.rectangle((x - w / 2, y - h, x + w / 2, y), fill=(255, 236, 170, 255))  # luz de la otra habitación
    hw = w * (1 - 0.8 * abierta)
    col = (176, 112, 64, 255)
    d.polygon([(x - w / 2, y - h), (x - w / 2 + hw, y - h + 30 * abierta), (x - w / 2 + hw, y - 30 * abierta),
               (x - w / 2, y)], fill=col, outline=(110, 66, 36, 255))
    if hw > 40:
        d.ellipse((x - w / 2 + hw - 38, y - h / 2 - 12, x - w / 2 + hw - 14, y - h / 2 + 12), fill=(255, 210, 90, 255))


def bocadillo(d, img, cx, cy, ch, k, alpha, contenido_alpha=1.0, ch2=None, k2=0):
    if k <= 0.02:
        return
    r = 105 * k
    d.ellipse((cx - r, cy - r * 0.85, cx + r, cy + r * 0.85), fill=(255, 255, 255, int(240 * alpha)))
    for i, (dx, dy, rr) in enumerate([(-70, 105, 22), (-100, 150, 13)]):
        d.ellipse((cx + dx * k - rr * k, cy + dy * k - rr * k, cx + dx * k + rr * k, cy + dy * k + rr * k),
                  fill=(255, 255, 255, int(240 * alpha)))
    sprite(img, ch, cx, cy, 120 * k, alpha=alpha * contenido_alpha, sombra=False)
    if ch2:
        sprite(img, ch2, cx, cy, 120 * k2, alpha=alpha, sombra=False)


def esc_puerta(img, d, t, ac):
    fase2 = pr(t, 16.0, 16.6)
    a1 = 1 - fase2
    if a1 > 0:
        # suelo
        d.rectangle((0, 1060, W, 1075), fill=(255, 255, 255, int(40 * a1)))
        abierta = eio(pr(t, 13.0, 13.8))
        puerta(d, 640, 1060, abierta, ac)
        # persona caminando de izquierda a derecha y cruzando
        px = 120 + (920 - 120) * eio(pr(t, 12.3, 15.0))
        paso = abs(math.sin(t * 9)) * 14 if t < 15.0 else 0
        sprite(img, "🚶", px, 940 - paso, 250, alpha=a1, flip=True)
        if px > 560 and px < 720:
            # repinta el marco derecho por delante: sensación de cruzar
            d.rectangle((640 + 115, 1060 - 452, 640 + 137, 1068), fill=(90, 58, 38, int(255 * a1)))
        cruzado = pr(t, 14.3, 14.9)
        kb = pop(t, 12.6, 0.4)
        bocadillo(d, img, px - 40, 640, "🍪", kb, a1, contenido_alpha=1 - cruzado, ch2="❓", k2=pop(t, 14.9, 0.35))
        # chispas de memoria que se van
        if 14.3 <= t < 15.6:
            for i in range(10):
                ang = i * 0.63
                rr = 60 + 260 * pr(t, 14.3, 15.6)
                al = int(255 * (1 - pr(t, 14.3, 15.6)) * a1)
                x, y = px - 40 + math.cos(ang) * rr, 640 + math.sin(ang) * rr * 0.6
                d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=ac + (al,))
        if t >= 15.0:
            texto_pop(d, "¿A QUÉ IBA YO? 🤔".replace(" 🤔", ""), W / 2, 1180, 78, t, 15.0, AMARILLO)
    if fase2 > 0:
        a = fase2
        # cerebro con dos «salas» de memoria
        kb = pop(t, 16.4, 0.45)
        pulso = 1 + 0.05 * math.sin(t * 6)
        sprite(img, "🧠", W / 2, 520, 250 * kb * pulso, alpha=a)
        for i, (x, lab, col) in enumerate([(270, "SALA A", (80, 160, 255)), (810, "SALA B", (255, 120, 160))]):
            k = pop(t, 17.0 + i * 0.35, 0.35)
            caja(d, x - 190 * k, 760 - 150 * k, x + 190 * k, 760 + 150 * k, 30, col + (int(70 * a),),
                 outline=col + (int(255 * a),), w=6)
            texto(d, lab, x, 650, 38 * k, BLANCO, alpha=a)
        # puerta en el medio
        if t >= 17.9:
            k = pop(t, 17.9, 0.35)
            sprite(img, "🚪", W / 2, 770, 170 * k, alpha=a)
        # la llave/galleta (información) viaja de A a B y se pierde
        if t >= 17.2:
            via = eio(pr(t, 18.4, 20.6))
            x = 270 + (810 - 270) * via
            y = 780 - math.sin(via * math.pi) * 120
            perdida = pr(t, 19.8, 21.0)
            sprite(img, "🍪", x, y, 130 * (1 - 0.5 * perdida), alpha=a * (1 - perdida))
            if t >= 20.6:
                sprite(img, "❓", 810, 780, 140 * pop(t, 20.6, 0.35), alpha=a, rot=-10)
        # etiqueta «temporalmente»
        if t >= 20.1:
            tw = ancho("¡SOLO UN RATO!", 40) + 40
            kk = pop(t, 20.1, 0.3)
            caja(d, W / 2 - tw / 2, 1010 - 30 * kk, W / 2 + tw / 2, 1010 + 30 * kk, 28, ac + (int(255 * a),))
            texto(d, "¡SOLO UN RATO!", W / 2, 1010, 40 * kk, (15, 12, 25), stroke=0, alpha=a)


def movil(img, d, cx, cy, s, t, pantalla_on, notis=0):
    w, h = 300 * s, 600 * s
    caja(d, cx - w / 2 - 6, cy - h / 2 - 6, cx + w / 2 + 6, cy + h / 2 + 6, 56 * s, (20, 20, 28, 255))
    caja(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 50 * s, (55, 55, 70, 255))
    pw, ph = w - 26 * s, h - 26 * s
    base = mezcla((15, 15, 22), (40, 60, 120), pantalla_on)
    caja(d, cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2, 40 * s, base + (255,))
    d.rounded_rectangle((cx - 50 * s, cy - ph / 2 + 14 * s, cx + 50 * s, cy - ph / 2 + 40 * s), 13 * s,
                        fill=(5, 5, 8, 255))
    if pantalla_on > 0.05:
        a = int(255 * pantalla_on)
        scroll = (t * 160 * s) % (120 * s)
        top = cy - ph / 2 + 70 * s
        for i in range(6):
            y = top + i * 120 * s - scroll
            if y < top - 10 or y > cy + ph / 2 - 100 * s:
                continue
            d.rounded_rectangle((cx - pw / 2 + 20 * s, y, cx + pw / 2 - 20 * s, y + 95 * s), 16 * s,
                                fill=(255, 255, 255, int(a * 0.18)))
            d.ellipse((cx - pw / 2 + 32 * s, y + 18 * s, cx - pw / 2 + 92 * s, y + 78 * s),
                      fill=hexrgb(["#FF5C8A", "#4FE3D0", "#FFD640"][i % 3]) + (a,))
            d.rounded_rectangle((cx - pw / 2 + 108 * s, y + 26 * s, cx + pw / 2 - 40 * s, y + 42 * s), 8 * s,
                                fill=(255, 255, 255, int(a * 0.7)))
            d.rounded_rectangle((cx - pw / 2 + 108 * s, y + 54 * s, cx + 40 * s, y + 68 * s), 7 * s,
                                fill=(255, 255, 255, int(a * 0.4)))


def esc_movil(img, d, t, ac):
    # 24.0 miras · 25.4 guardas · 26.4 cuenta 10 s · 27.3 vuelves a mirar
    sube = eo(pr(t, 23.6, 24.2))
    baja = eio(pr(t, 25.35, 25.9))
    vuelve = eob(pr(t, 27.3, 27.75), 1.2)
    off = (1 - sube) * 1500 + baja * 1500 - (vuelve * 1500 if t >= 27.3 else 0)
    explic = pr(t, 28.4, 28.9)
    cx = W / 2 - 170 * eio(explic)
    cy = 790 + off
    s = 1.0 - 0.15 * eio(explic)
    if t >= 28.0:
        # vibración de «otra vez»
        cx += math.sin(t * 60) * 6 * (1 - pr(t, 28.0, 28.5))
    movil(img, d, cx, cy, s, t, pantalla_on=1.0 if (t < 25.4 or t >= 27.3) else 0.0)
    # bolsillo
    if 25.2 <= t < 27.6:
        a = pr(t, 25.2, 25.4) * (1 - pr(t, 27.4, 27.6))
        caja(d, 260, 1080, 820, 1240, 40, (52, 72, 120, int(255 * a)), outline=(30, 40, 80, int(255 * a)), w=6)
        texto(d, "BOLSILLO", W / 2, 1160, 44, BLANCO, alpha=a * 0.8)
    # contador de 10 segundos
    if 26.3 <= t < 27.4:
        n = min(10, int(1 + 10 * pr(t, 26.4, 27.2)))
        k = pop(t, 26.3, 0.3)
        anillo(d, W / 2, 680, 170 * k, ac + (255,), 14)
        ang = 360 * pr(t, 26.4, 27.2)
        d.arc((W / 2 - 170 * k, 680 - 170 * k, W / 2 + 170 * k, 680 + 170 * k), -90, -90 + ang,
              fill=AMARILLO + (255,), width=18)
        texto(d, f"{n}s", W / 2, 680, 150 * k, BLANCO)
    if 27.3 <= t < 28.5:
        texto_pop(d, "¡OTRA VEZ!", W / 2, 360, 96, t, 27.4, AMARILLO)
    # explicación: hábito en bucle + notificaciones
    if t >= 28.6:
        a = pr(t, 28.6, 29.0)
        rx, ry = 820, 560
        k = pop(t, 29.3, 0.4)
        rot = (t * 120) % 360
        d.arc((rx - 120 * k, ry - 120 * k, rx + 120 * k, ry + 120 * k), rot, rot + 290, fill=ac + (255,), width=16)
        sprite(img, "🔁", rx, ry, 120 * k, alpha=a)
        texto(d, "HÁBITO", rx, ry + 165, 50 * k, ac, alpha=a)
        notis = [("🔔", 31.2, 790, 870), ("❤️", 31.6, 900, 1010), ("💬", 32.0, 740, 1060)]
        for ch, t0, x, y in notis:
            kk = pop(t, t0, 0.35)
            sprite(img, ch, x, y + math.sin(t * 4 + x) * 10, 120 * kk, rot=math.sin(t * 5 + x) * 10)
        if t >= 31.2:
            # globo rojo de notificaciones en el móvil
            n = min(99, 1 + int((t - 31.2) * 9))
            kk = pop(t, 31.2, 0.3)
            bx, by = cx + 125 * s, cy - 255 * s
            d.ellipse((bx - 48 * kk, by - 48 * kk, bx + 48 * kk, by + 48 * kk), fill=(255, 59, 48, 255),
                      outline=BLANCO + (255,), width=5)
            texto(d, str(n), bx, by, 44 * kk, BLANCO, stroke=0)


def cara(img, d, x, y, size, t, t_bostezo, alpha=1.0, ondas=True):
    if t >= t_bostezo:
        k = pop(t, t_bostezo, 0.4)
        sprite(img, "🥱", x, y, size * (0.9 + 0.1 * k), alpha=alpha, rot=math.sin(t * 2) * 5)
        if ondas and t < t_bostezo + 1.6:
            for i in range(3):
                f = ((t - t_bostezo) * 1.2 + i / 3) % 1
                anillo(d, x, y, size * (0.55 + 0.6 * f), (255, 200, 120, int(180 * (1 - f) * alpha)), 6)
    else:
        sprite(img, "😐", x, y, size, alpha=alpha)


def esc_bostezo(img, d, t, ac):
    ex = pr(t, 37.7, 38.2)
    a1 = 1 - ex
    if a1 > 0:
        cara(img, d, 300, 760, 300, t, 34.6, alpha=a1)
        cara(img, d, 780, 760, 300, t, 36.5, alpha=a1)
        if t >= 35.3:
            # flecha de contagio
            k = eo(pr(t, 35.4, 36.2))
            x0, x1 = 470, 470 + (610 - 470) * k
            d.line((x0, 760, x1, 760), fill=ac + (int(255 * a1),), width=14)
            if k > 0.95:
                d.polygon([(x1 + 30, 760), (x1 - 5, 732), (x1 - 5, 788)], fill=ac + (int(255 * a1),))
        if t >= 34.4:
            texto(d, "TÚ", 780, 980, 56, BLANCO, alpha=a1 * pr(t, 35.3, 35.6))
            texto(d, "OTRA PERSONA", 300, 980, 46, BLANCO, alpha=a1 * pr(t, 35.3, 35.6))
    if ex > 0:
        # cuadrícula 3x3 que se va contagiando como una ola
        if t < 40.3:
            for r in range(3):
                for c in range(3):
                    x, y = 270 + c * 270, 520 + r * 240
                    dist = math.hypot(r - 1, c - 1)
                    cara(img, d, x, y, 170, t, 38.5 + dist * 0.55, alpha=ex * (1 - pr(t, 40.0, 40.3)), ondas=False)
        else:
            # «incluso en un vídeo»: un móvil con un bostezo y tú bostezando
            a = pr(t, 40.3, 40.6)
            movil(img, d, 330, 760, 0.85, t, pantalla_on=0.4)
            sprite(img, "🥱", 330, 760, 190 * pop(t, 40.5, 0.35), alpha=a, sombra=False)
            d.polygon([(330 - 40, 900), (330 + 45, 945), (330 - 40, 990)], fill=(255, 255, 255, int(200 * a)))
            cara(img, d, 790, 760, 280, t, 41.5, alpha=a)
            texto(d, "TÚ", 790, 980, 56, BLANCO, alpha=a)
            if t >= 41.9:
                texto_pop(d, "¿YA HAS BOSTEZADO? 😏".replace(" 😏", ""), W / 2, 420, 66, t, 41.9, AMARILLO)


def semaforo(d, x, y, estado, t):
    caja(d, x - 120, y - 330, x + 120, y + 330, 50, (28, 28, 34, 255), outline=(70, 70, 80, 255), w=8)
    d.rectangle((x - 22, y + 330, x + 22, y + 400), fill=(55, 55, 64, 255))
    cols = [(255, 60, 60), (255, 190, 40), (60, 220, 110)]
    for i, col in enumerate(cols):
        cy = y - 200 + i * 200
        on = (estado == i)
        base = col if on else tuple(int(v * 0.22) for v in col)
        if on:
            for g in range(5, 0, -1):
                r = 85 + g * 16
                d.ellipse((x - r, cy - r, x + r, cy + r), fill=col + (int(24 + 4 * math.sin(t * 6)),))
        d.ellipse((x - 80, cy - 80, x + 80, cy + 80), fill=base + (255,))
        d.ellipse((x - 50, cy - 60, x - 10, cy - 30), fill=(255, 255, 255, 70 if on else 15))


def reloj(d, cx, cy, r, ang, ac, a=1.0):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 250, 250, int(255 * a)), outline=ac + (int(255 * a),),
              width=12)
    for i in range(12):
        an = i * math.pi / 6
        d.line((cx + math.cos(an) * r * 0.78, cy + math.sin(an) * r * 0.78, cx + math.cos(an) * r * 0.9,
                cy + math.sin(an) * r * 0.9), fill=(40, 40, 50, int(255 * a)), width=6)
    an = math.radians(ang - 90)
    d.line((cx, cy, cx + math.cos(an) * r * 0.82, cy + math.sin(an) * r * 0.82), fill=(230, 40, 40, int(255 * a)),
           width=8)
    d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(30, 30, 40, int(255 * a)))


def esc_semaforo(img, d, t, ac):
    estado = 2 if t >= 50.9 else 0
    semaforo(d, 300, 700, estado, t)
    # persona impaciente
    if t < 50.9:
        sprite(img, "😤", 760, 560, 230 * pop(t, 43.6, 0.4), rot=math.sin(t * 14) * 5)
        # pie golpeando: ondas pequeñas bajo la cara
        for i in range(3):
            f = (t * 2.2 + i / 3) % 1
            d.arc((760 - 60 - 60 * f, 740 - 15, 760 + 60 + 60 * f, 760 + 15 + 20 * f), 20, 160,
                  fill=(255, 255, 255, int(120 * (1 - f))), width=5)
    else:
        sprite(img, "🙂", 760, 560, 230, rot=math.sin(t * 4) * 6)
        texto_pop(d, "¡POR FIN!", W / 2, 1150, 84, t, 50.9, (90, 230, 120))
    # cuenta atrás que «se estira»
    if 44.0 <= t < 47.0:
        lento = 30 - (t - 44.0) * 0.45
        n = int(math.ceil(lento))
        k = pop(t, 44.0, 0.35)
        caja(d, 640, 830, 900, 1000, 26, (0, 0, 0, 200), outline=(255, 60, 60, 255), w=5)
        texto(d, f"{n:02d}", 770, 915, 110 * k, (255, 70, 70), stroke=0)
        if t >= 44.7:
            texto_pop(d, "¡NO SE ACABA NUNCA!", W / 2, 1180, 66, t, 44.7, AMARILLO)
    # explicación: reloj bajo la lupa
    if t >= 47.0:
        a = pr(t, 47.0, 47.4)
        k = pop(t, 47.2, 0.4)
        lento = 1 + 5 * pr(t, 48.4, 49.5)  # cuanto más atención, más lento parece
        ang = (t - 47.0) * 360 / 4 / lento * 4
        reloj(d, 770, 930, 130 * k, ang % 360, ac, a)
        if t >= 49.3:
            kk = pop(t, 49.3, 0.4)
            sprite(img, "🔍", 840, 870, 260 * kk, rot=-15 + 6 * math.sin(t * 2))
        if t >= 50.4:
            texto_pop(d, "1 SEGUNDO = ∞", W / 2, 1150, 0 if t >= 50.9 else 60, t, 50.4, AMARILLO)


def esc_mirada(img, d, t, ac):
    expl = pr(t, 57.0, 57.5)
    a1 = 1 - expl
    if a1 > 0:
        # foco de luz sobre la persona
        for g in range(8, 0, -1):
            r = 120 + g * 40
            d.ellipse((W / 2 + 100 - r, 1050 - r * 0.25, W / 2 + 100 + r, 1050 + r * 0.25),
                      fill=(255, 240, 200, int(10 * a1)))
        girado = t >= 55.55
        k = pop(t, 55.55, 0.3)
        ch = "😱" if girado else "🧍"
        if girado:
            sprite(img, "😱", W / 2 + 100, 770, 300 * (0.8 + 0.2 * k), alpha=a1, rot=math.sin(t * 20) * 4 * (1 - pr(t, 55.6, 56.4)))
            texto_pop(d, "¡!", W / 2 + 100, 520, 140, t, 55.6, AMARILLO)
        else:
            sprite(img, ch, W / 2 + 100, 830, 420, alpha=a1)
        # ojos en la oscuridad
        if t >= 53.4:
            ka = pr(t, 53.4, 54.2)
            parp = 0.1 if (t % 2.2) < 0.12 else 1
            x, y = 230, 560
            for g in range(6, 0, -1):
                r = 50 + g * 22
                d.ellipse((x - r, y - r, x + r, y + r), fill=ac + (int(10 * ka * a1),))
            sprite(img, "👀", x, y, 170 * (0.6 + 0.4 * ka) * parp if parp < 1 else 170 * (0.6 + 0.4 * ka),
                   alpha=ka * a1, sombra=False)
            # línea de mirada
            if not girado:
                for i in range(8):
                    f = ((t * 0.9) + i / 8) % 1
                    xx = x + 90 + (W / 2 - 40 - x - 90) * f
                    yy = y + 40 + (760 - y - 40) * f
                    d.ellipse((xx - 6, yy - 6, xx + 6, yy + 6), fill=ac + (int(200 * ka * a1 * (1 - f)),))
    if expl > 0:
        a = expl
        cx, cy = W / 2, 780
        # radar: visión periférica + sonidos
        k = pop(t, 57.4, 0.45)
        rad = 360 * k
        d.pieslice((cx - rad, cy - rad, cx + rad, cy + rad), -180 + 20, -20, fill=ac + (int(45 * a),))
        for i in range(3):
            anillo(d, cx, cy, rad * (i + 1) / 3, ac + (int(80 * a),), 3)
        bar = (t * 140) % 360
        d.pieslice((cx - rad, cy - rad, cx + rad, cy + rad), bar - 12, bar, fill=ac + (int(110 * a),))
        sprite(img, "🧠", cx, cy, 170 * k, alpha=a)
        # pequeños movimientos (puntos en los bordes)
        if t >= 59.0:
            for i, (ang, rr) in enumerate([(200, 0.85), (330, 0.8), (250, 0.95), (300, 0.7)]):
                kk = pop(t, 59.0 + i * 0.2, 0.3)
                an = math.radians(ang + 8 * math.sin(t * 3 + i))
                x, y = cx + math.cos(an) * rad * rr, cy + math.sin(an) * rad * rr
                d.ellipse((x - 18 * kk, y - 18 * kk, x + 18 * kk, y + 18 * kk), fill=AMARILLO + (int(255 * a),))
                anillo(d, x, y, 30 + 20 * ((t * 2 + i / 4) % 1), AMARILLO + (int(150 * a),), 3)
            texto(d, "MOVIMIENTOS", 220, 420, 42, AMARILLO, alpha=a * pr(t, 59.0, 59.3))
        # sonidos
        if t >= 60.4:
            kk = pop(t, 60.4, 0.35)
            sprite(img, "👂", 900, 1000, 140 * kk, alpha=a)
            for i in range(3):
                f = ((t * 1.4) + i / 3) % 1
                r = 80 + 140 * f
                d.arc((900 - r, 1000 - r, 900 + r, 1000 + r), 150, 230, fill=(255, 255, 255, int(200 * (1 - f) * a)),
                      width=6)
            texto(d, "SONIDOS", 860, 420, 42, BLANCO, alpha=a * pr(t, 60.4, 60.7))
        if t >= 61.3:
            texto_pop(d, "...SIN DARTE CUENTA", W / 2, 1150, 64, t, 61.3)


def esc_final(img, d, t, ac):
    if t < 67.0:
        texto_pop(d, "¿CUÁL HACES TÚ?", W / 2, 300, 100, t, 64.2, AMARILLO)
        texto_pop(d, "AHORA DIME...", W / 2, 300, 0 if t >= 64.2 else 90, t, 63.1)
        for i, (ch, lab) in enumerate(GANCHO_ICONOS):
            t0 = 64.5 + i * 0.3
            if t < t0:
                continue
            k = eo(pr(t, t0, t0 + 0.4))
            y = 470 + i * 150
            x0 = 130 + (1 - k) * -500
            caja(d, x0, y - 60, x0 + 820, y + 60, 30, (255, 255, 255, 30), outline=ac + (160,), w=4)
            sprite(img, ch, x0 + 80, y, 95)
            texto(d, lab, x0 + 160, y, 56, BLANCO, anchor="lm")
            caja(d, x0 + 700, y - 38, x0 + 776, y + 38, 14, (255, 255, 255, 40), outline=BLANCO + (220,), w=5)
            tc = 65.4 + i * 0.25
            if t >= tc:
                sprite(img, "✅", x0 + 738, y, 90 * pop(t, tc, 0.3), sombra=False)
    else:
        a = pr(t, 67.0, 67.4)
        texto_pop(d, "Y CONFIESA...", W / 2, 300, 96, t, 67.2, AMARILLO)
        movil(img, d, W / 2, 800, 0.95, t, pantalla_on=1.0)
        if t >= 68.3:
            n = min(9, 1 + int((t - 68.3) * 2.6))
            k = pop(t, 68.3 + (n - 1) / 2.6, 0.25)
            caja(d, W / 2 - 200, 1130, W / 2 + 200, 1250, 40, (0, 0, 0, 210), outline=ac + (255,), w=5)
            texto(d, f"👀 x{n}".replace("👀 ", ""), W / 2 + 40, 1190, 90 * k, AMARILLO, stroke=0)
            sprite(img, "👀", W / 2 - 110, 1190, 90, sombra=False)
            texto(d, "¿CUÁNTAS VECES?", W / 2, 420, 64, BLANCO, alpha=pr(t, 68.3, 68.6))
        if t >= 70.2:
            k = pop(t, 70.2, 0.4)
            bob = math.sin(t * 8) * 12
            texto(d, "COMENTA", W / 2 - 60, 1390, 70 * k, ac)
            sprite(img, "👇", W / 2 + 200, 1390 + bob, 110 * k)


ESCENAS = {"intro": esc_intro, "gancho": esc_gancho, "puerta": esc_puerta, "movil": esc_movil,
           "bostezo": esc_bostezo, "semaforo": esc_semaforo, "mirada": esc_mirada, "final": esc_final}


def frame(t):
    sec = seccion(t)
    t0, t1, nombre, top, bot, acs = sec
    ac = hexrgb(acs)
    if nombre not in FONDOS:
        FONDOS[nombre] = fondo_seccion(top, bot, acs)
    img = FONDOS[nombre].copy()
    d = ImageDraw.Draw(img, "RGBA")
    particulas(d, t, ac)
    ESCENAS[nombre](img, d, t, ac)
    cabecera(img, d, t, nombre, t0, ac)
    progreso(d, t, nombre)
    tarjeta(d, t, nombre, ac, t1)
    subtitulos(d, t, ac)
    # destello y «zoom» de entrada en cada sección
    if t0 > 0 and t - t0 < 0.25:
        f = 1 - (t - t0) / 0.25
        sc = 1 + 0.06 * f
        img = img.resize((int(W * sc), int(H * sc)), Image.BILINEAR).crop(
            (int((W * sc - W) / 2), int((H * sc - H) / 2), int((W * sc - W) / 2) + W, int((H * sc - H) / 2) + H))
        img = Image.blend(img, Image.new("RGB", (W, H), BLANCO), 0.55 * f)
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
    pops = [0.0, 0.32, 0.72, 2.3, 2.6, 4.6, 4.9, 5.2, 5.5, 5.8, 9.6, 12.6, 14.9, 20.6, 24.0, 27.4, 31.2, 31.6, 32.0,
            34.6, 36.5, 41.5, 43.6, 49.3, 50.9, 55.55, 59.0, 60.4, 64.5, 64.8, 65.1, 65.4, 65.7, 70.2]
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
