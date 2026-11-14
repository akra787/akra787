#!/usr/bin/env python3
"""Vídeo animado «5 gastos pequeños que te están robando dinero».

Uso:  python3 videos/gastos/animar.py [salida.mp4] [--desde S --hasta S]

Dibuja cada fotograma con cairo (vectorial + emojis Noto), sincronizado con la
voz de `voz.mp3` usando los tiempos por palabra de `palabras.json` (faster-whisper).
Genera también música y efectos de sonido con numpy y lo monta todo con ffmpeg.
"""
import json
import math
import os
import subprocess
import sys
from contextlib import contextmanager
from multiprocessing import Pool

import cairo
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
DUR = 69.5
SR = 44100
BLACK = "Inter Black"
BOLD = "Inter"
MONO = "JetBrains Mono"
EMOJI = "Noto Color Emoji"

PALABRAS = json.load(open(os.path.join(AQUI, "palabras.json")))


# ------------------------------------------------------------------ utilidades
def hx(c, a=1.0):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


AMARILLO, VERDE, ROJO, BLANCO = hx("#ffd23f"), hx("#2ee59d"), hx("#ff4d6d"), hx("#ffffff")
OSCURO = hx("#1a1033")


def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def pr(T, t0, d):
    return cl((T - t0) / d) if d > 0 else float(T >= t0)


def eo(x):
    return 1 - (1 - x) ** 3


def ei(x):
    return x ** 3


def eio(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def eob(x, s=1.9):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def eel(x):
    if x <= 0 or x >= 1:
        return float(x >= 1)
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi / 3)) + 1


def lerp(a, b, t):
    return a + (b - a) * t


def lerpc(c1, c2, t):
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def pop(T, t0, d=0.4):
    """(escala, alfa) para aparecer con rebote."""
    x = pr(T, t0, d)
    return (eob(x) if x > 0 else 0.0), cl(x * 3)


def eur(v, dec=2):
    s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def src(c, col):
    c.set_source_rgba(*col) if len(col) == 4 else c.set_source_rgb(*col)


@contextmanager
def tf(c, x=0, y=0, s=1.0, r=0.0, a=1.0, sx=1.0, sy=1.0):
    c.save()
    c.translate(x, y)
    if r:
        c.rotate(r)
    fx, fy = s * sx, s * sy
    fx = fx if abs(fx) > 1e-4 else 1e-4
    fy = fy if abs(fy) > 1e-4 else 1e-4
    c.scale(fx, fy)
    grp = a < 0.999
    if grp:
        c.push_group()
    try:
        yield
    finally:
        if grp:
            c.pop_group_to_source()
            c.paint_with_alpha(max(0.0, a))
        c.restore()


def rr(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()


def box(c, cx, cy, w, h, r, col, sombra=0.3, borde=None, bw=0):
    if sombra:
        rr(c, cx - w / 2, cy - h / 2 + 12, w, h, r)
        src(c, (0, 0, 0, sombra))
        c.fill()
    rr(c, cx - w / 2, cy - h / 2, w, h, r)
    src(c, col)
    if borde:
        c.fill_preserve()
        src(c, borde)
        c.set_line_width(bw)
        c.stroke()
    else:
        c.fill()


def fuente(c, font, size):
    bold = cairo.FONT_WEIGHT_BOLD if font in (BOLD, MONO) else cairo.FONT_WEIGHT_NORMAL
    c.select_font_face(font, cairo.FONT_SLANT_NORMAL, bold)
    c.set_font_size(size)


def ancho(c, s, size, font=BLACK):
    fuente(c, font, size)
    return c.text_extents(s).x_advance


def txt(c, s, x, y, size, col=BLANCO, font=BLACK, al="c", borde=0, bcol=(0, 0, 0), sombra=0.35, maxw=None):
    if maxw:
        w = ancho(c, s, size, font)
        if w > maxw:
            size *= maxw / w
    fuente(c, font, size)
    xa = c.text_extents(s).x_advance
    x0 = x - xa / 2 if al == "c" else (x - xa if al == "r" else x)
    y0 = y + size * 0.36
    if sombra:
        c.move_to(x0 + size * 0.03, y0 + size * 0.07)
        c.text_path(s)
        src(c, (0, 0, 0, sombra * (col[3] if len(col) == 4 else 1)))
        c.fill()
    if borde:
        c.move_to(x0, y0)
        c.text_path(s)
        src(c, bcol)
        c.set_line_width(borde)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.stroke()
    c.move_to(x0, y0)
    c.text_path(s)
    src(c, col)
    c.fill()
    return xa


def emo(c, ch, x, y, size, a=1.0, r=0.0, s=1.0):
    if a <= 0 or s <= 0:
        return
    with tf(c, x, y, s, r, a):
        fuente(c, EMOJI, size)
        xb, yb, w, h, xa, ya = c.text_extents(ch)
        c.move_to(-(xb + w / 2), -(yb + h / 2))
        c.show_text(ch)


def tachar(c, x0, x1, y, p, col=ROJO, lw=10):
    if p <= 0:
        return
    c.move_to(x0, y)
    c.line_to(lerp(x0, x1, p), y)
    src(c, col)
    c.set_line_width(lw)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.stroke()


# ------------------------------------------------------------------ dibujos vectoriales
def billete(c):
    rr(c, -110, -55, 220, 110, 12)
    src(c, hx("#43c47a"))
    c.fill()
    rr(c, -98, -43, 196, 86, 8)
    src(c, hx("#1f8a4c"))
    c.set_line_width(5)
    c.stroke()
    c.arc(0, 0, 30, 0, 2 * math.pi)
    src(c, hx("#bff3d2"))
    c.fill()
    txt(c, "€", 0, 0, 40, hx("#1f8a4c"), sombra=0)


def moneda(c, r=60):
    c.arc(0, 4, r, 0, 2 * math.pi)
    src(c, hx("#c98a00"))
    c.fill()
    c.arc(0, 0, r, 0, 2 * math.pi)
    src(c, hx("#ffc93c"))
    c.fill()
    c.arc(0, 0, r * 0.78, 0, 2 * math.pi)
    src(c, hx("#e8a800"))
    c.set_line_width(r * 0.08)
    c.stroke()
    txt(c, "€", 0, 0, r * 1.0, hx("#b07700"), sombra=0)


def cartera(c, con_billetes=True, abierta=0.0):
    if con_billetes:
        for dx, rot in ((-40, -0.12), (30, 0.1)):
            with tf(c, dx, -120, 0.9, rot):
                billete(c)
    rr(c, -190, -130, 380, 260, 40)
    src(c, hx("#6b3e22"))
    c.fill()
    rr(c, -190, -60, 380, 190, 40)
    src(c, hx("#8f5530"))
    c.fill()
    rr(c, -170, -40, 340, 150, 28)
    src(c, hx("#b06c3d", 0.6))
    c.set_line_width(5)
    c.set_dash([14, 10])
    c.stroke()
    c.set_dash([])
    rr(c, 60, -30, 160, 90, 30)
    src(c, hx("#5a321b"))
    c.fill()
    c.arc(110, 15, 18, 0, 2 * math.pi)
    src(c, hx("#ffd23f"))
    c.fill()


def vaso_cafe(c, T=0.0, vapor=True):
    if vapor:
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        for k, dx in enumerate((-60, 0, 60)):
            ph = T * 3 + k * 1.7
            c.move_to(dx, -265)
            for i in range(1, 21):
                yy = -265 - i * 8
                c.line_to(dx + math.sin(ph + i * 0.35) * 16 * (i / 20 + 0.3), yy)
            a = 0.35 + 0.2 * math.sin(T * 2 + k)
            src(c, (1, 1, 1, a))
            c.set_line_width(14)
            c.stroke()
    # cuerpo
    c.move_to(-150, -180)
    c.line_to(150, -180)
    c.line_to(112, 230)
    c.line_to(-112, 230)
    c.close_path()
    g = cairo.LinearGradient(-150, 0, 150, 0)
    g.add_color_stop_rgb(0, *hx("#ffffff")[:3])
    g.add_color_stop_rgb(1, *hx("#ddd5c8")[:3])
    c.set_source(g)
    c.fill()
    # funda
    def hw(y):
        return lerp(150, 112, (y + 180) / 410)
    y0, y1 = -40, 110
    c.move_to(-hw(y0) - 4, y0)
    c.line_to(hw(y0) + 4, y0)
    c.line_to(hw(y1) + 4, y1)
    c.line_to(-hw(y1) - 4, y1)
    c.close_path()
    src(c, hx("#a0612f"))
    c.fill()
    c.arc(0, 35, 46, 0, 2 * math.pi)
    src(c, hx("#f6e7cf"))
    c.fill()
    txt(c, "€", 0, 35, 56, hx("#a0612f"), sombra=0)
    # tapa
    rr(c, -168, -218, 336, 46, 18)
    src(c, hx("#efe9df"))
    c.fill()
    rr(c, -132, -250, 264, 40, 16)
    src(c, hx("#e2dace"))
    c.fill()
    rr(c, -40, -252, 80, 14, 7)
    src(c, hx("#b9ae9d"))
    c.fill()


def ticket_zigzag(c, x0, x1, y, dz=24):
    n = int((x1 - x0) / dz)
    c.line_to(x1, y)
    for i in range(n, 0, -1):
        c.line_to(x0 + (i - 0.5) * dz, y + 14)
        c.line_to(x0 + (i - 1) * dz, y)


def carrito(c, ruedas=0.0, items_fn=None):
    acero = hx("#dfe7f1")
    # cesta trasera
    c.move_to(-230, -150)
    c.line_to(230, -150)
    c.line_to(180, 90)
    c.line_to(-170, 90)
    c.close_path()
    src(c, (1, 1, 1, 0.10))
    c.fill()
    if items_fn:
        items_fn()
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    src(c, acero)
    # rejilla
    c.set_line_width(6)
    for i in range(1, 7):
        f = i / 7
        c.move_to(lerp(-230, 230, f), -150)
        c.line_to(lerp(-170, 180, f), 90)
    for j in range(1, 3):
        f = j / 3
        y = lerp(-150, 90, f)
        c.move_to(lerp(-230, -170, f), y)
        c.line_to(lerp(230, 180, f), y)
    c.stroke()
    c.set_line_width(12)
    c.move_to(-340, -215)
    c.line_to(-290, -215)
    c.line_to(-230, -150)
    c.line_to(230, -150)
    c.line_to(180, 90)
    c.line_to(-170, 90)
    c.line_to(-230, -150)
    c.move_to(-170, 90)
    c.line_to(-190, 140)
    c.line_to(205, 140)
    c.stroke()
    src(c, hx("#ff4d6d"))
    c.set_line_width(20)
    c.move_to(-345, -215)
    c.line_to(-305, -215)
    c.stroke()
    for wx in (-150, 170):
        c.arc(wx, 172, 30, 0, 2 * math.pi)
        src(c, hx("#2a2a3a"))
        c.fill()
        c.arc(wx, 172, 12, 0, 2 * math.pi)
        src(c, acero)
        c.fill()
        for k in range(3):
            a = ruedas + k * 2 * math.pi / 3
            c.move_to(wx, 172)
            c.line_to(wx + 24 * math.cos(a), 172 + 24 * math.sin(a))
        c.set_line_width(4)
        c.stroke()


def etiqueta_precio(c, T):
    c.move_to(0, 0)
    c.line_to(0, 150)
    src(c, hx("#2b1a00"))
    c.set_line_width(6)
    c.stroke()
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    def forma():
        c.move_to(-170, 175)
        c.line_to(0, 80)
        c.line_to(170, 175)
        c.line_to(170, 600)
        c.line_to(-170, 600)
        c.close_path()
    with tf(c, 10, 14):
        forma()
        src(c, (0, 0, 0, 0.3))
        c.set_line_width(40)
        c.stroke_preserve()
        c.fill()
    forma()
    src(c, hx("#ffd23f"))
    c.set_line_width(40)
    c.stroke_preserve()
    c.fill()
    c.arc(0, 150, 22, 0, 2 * math.pi)
    src(c, hx("#7a4f00"))
    c.fill()
    txt(c, "-50%", 0, 300, 130, hx("#e63946"), sombra=0)
    txt(c, "40 €", 0, 430, 64, hx("#7a6a4a"), sombra=0)
    tachar(c, -85, 85, 432, 1, hx("#e63946"), 8)
    txt(c, "20 €", 0, 535, 96, hx("#2b1a00"), sombra=0)


def estrella(c, r1, r2, n=16):
    for i in range(2 * n):
        r = r1 if i % 2 == 0 else r2
        a = i * math.pi / n
        (c.move_to if i == 0 else c.line_to)(r * math.cos(a), r * math.sin(a))
    c.close_path()


def nube(c, w, h, col=(1, 1, 1, 0.95)):
    for dx, dy, r in ((-0.32, 0.1, 0.32), (0.0, -0.12, 0.42), (0.3, 0.08, 0.34), (-0.08, 0.2, 0.3), (0.18, 0.22, 0.28)):
        c.new_sub_path()
        c.arc(dx * w, dy * h, r * h * 1.4 if r * h * 1.4 < w else r * w, 0, 2 * math.pi)
    rr(c, -w * 0.42, -h * 0.25, w * 0.84, h * 0.6, h * 0.3)
    src(c, col)
    c.fill()


def sello(c, s, size, col=ROJO):
    fuente(c, BLACK, size)
    w = c.text_extents(s).x_advance + size * 0.9
    h = size * 1.6
    rr(c, -w / 2, -h / 2, w, h, size * 0.25)
    src(c, col)
    c.set_line_width(size * 0.13)
    c.stroke()
    rr(c, -w / 2 + size * 0.16, -h / 2 + size * 0.16, w - size * 0.32, h - size * 0.32, size * 0.15)
    c.set_line_width(size * 0.04)
    c.stroke()
    txt(c, s, 0, 0, size, col, sombra=0)


def flecha_compartir(c, col):
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.move_to(-62, 52)
    c.curve_to(-62, -20, -20, -38, 30, -38)
    src(c, col)
    c.set_line_width(34)
    c.stroke()
    c.move_to(18, -100)
    c.line_to(92, -38)
    c.line_to(18, 24)
    c.close_path()
    c.set_line_width(14)
    c.stroke_preserve()
    c.fill()


# ------------------------------------------------------------------ partículas fijas
RNG = np.random.default_rng(7)
SIMBOLOS = [dict(x=RNG.uniform(40, W - 40), y=RNG.uniform(0, H), v=RNG.uniform(25, 60),
                 s=RNG.uniform(40, 100), r=RNG.uniform(-0.4, 0.4), ch=RNG.choice(["€", "€", "%", "$"]))
            for _ in range(16)]
BURST = [dict(a=RNG.uniform(0, 2 * math.pi), v=RNG.uniform(600, 1300), giro=RNG.uniform(3, 9),
              rot=RNG.uniform(0, 6.28), d=RNG.uniform(0, 0.25), em=RNG.random() < 0.3) for _ in range(26)]
FUGA = [dict(a=RNG.uniform(-2.6, -0.5), v=RNG.uniform(500, 900), giro=RNG.uniform(3, 8),
             rot=RNG.uniform(0, 6.28)) for _ in range(16)]


# ------------------------------------------------------------------ escenas
# (inicio, fondo arriba, fondo abajo, acento)
ESCENAS = [
    (0.0, "#14072f", "#43106b", AMARILLO),
    (2.85, "#0a1636", "#1d3f80", VERDE),
    (11.2, "#1e0f07", "#6e3a1c", AMARILLO),
    (20.5, "#2c070f", "#8c1c33", AMARILLO),
    (29.0, "#0b1238", "#43188a", VERDE),
    (38.0, "#04231f", "#0f6d56", AMARILLO),
    (45.9, "#2d1300", "#b04c00", AMARILLO),
    (54.9, "#14072f", "#6a1290", AMARILLO),
]
FIN = DUR


def escena_de(T):
    i = 0
    for k, e in enumerate(ESCENAS):
        if T >= e[0]:
            i = k
    fin = ESCENAS[i + 1][0] if i + 1 < len(ESCENAS) else FIN
    return i, ESCENAS[i][0], fin


def fondo(c, T):
    i, t0, _ = escena_de(T)
    top, bot = hx(ESCENAS[i][1]), hx(ESCENAS[i][2])
    if i > 0:
        k = eio(pr(T, t0 - 0.1, 0.5))
        top = lerpc(hx(ESCENAS[i - 1][1]), top, k)
        bot = lerpc(hx(ESCENAS[i - 1][2]), bot, k)
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *top[:3])
    g.add_color_stop_rgb(1, *bot[:3])
    c.set_source(g)
    c.paint()
    # manchas de luz suaves
    for k, (bx, by, br, sp) in enumerate(((0.2, 0.25, 520, 0.3), (0.85, 0.6, 600, 0.23), (0.35, 0.9, 480, 0.37))):
        x = bx * W + math.sin(T * sp + k) * 120
        y = by * H + math.cos(T * sp * 0.8 + k * 2) * 140
        g = cairo.RadialGradient(x, y, 0, x, y, br)
        g.add_color_stop_rgba(0, 1, 1, 1, 0.09)
        g.add_color_stop_rgba(1, 1, 1, 1, 0)
        c.set_source(g)
        c.paint()
    # símbolos de dinero flotando
    for p in SIMBOLOS:
        y = (p["y"] - T * p["v"]) % (H + 200) - 100
        with tf(c, p["x"] + math.sin(T + p["y"]) * 20, y, 1, p["r"] + math.sin(T * 0.7 + p["x"]) * 0.2):
            txt(c, p["ch"], 0, 0, p["s"], (1, 1, 1, 0.07), sombra=0)
    # viñeta
    g = cairo.RadialGradient(W / 2, H * 0.45, H * 0.3, W / 2, H * 0.45, H * 0.75)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.45)
    c.set_source(g)
    c.paint()


def progreso(c, T):
    i, t0, _ = escena_de(T)
    if i < 2:
        return
    a = pr(T, 11.0, 0.4)
    actual = i - 1  # 1..5, 6 = final
    with tf(c, 0, 0, 1, 0, a):
        pw, gap = 118, 18
        x0 = W / 2 - (5 * pw + 4 * gap) / 2
        for k in range(5):
            n = k + 1
            x = x0 + k * (pw + gap)
            rr(c, x, 140, pw, 16, 8)
            src(c, (1, 1, 1, 0.22))
            c.fill()
            if n < actual or actual == 6:
                f = 1.0
            elif n == actual:
                f = eo(pr(T, t0, 0.6))
            else:
                f = 0
            if f > 0:
                rr(c, x, 140, pw * f, 16, 8)
                src(c, AMARILLO if n == actual else BLANCO)
                c.fill()


def cabecera(c, T, t0, n, titulo, col=AMARILLO):
    s, a = pop(T, t0 + 0.05, 0.45)
    if a > 0:
        rot = lerp(-0.6, -0.08, eo(pr(T, t0 + 0.05, 0.45))) + math.sin(T * 2) * 0.03
        with tf(c, 540, 300, lerp(2.4, 1, eo(pr(T, t0 + 0.05, 0.3))), rot, a):
            c.arc(0, 10, 92, 0, 2 * math.pi)
            src(c, (0, 0, 0, 0.35))
            c.fill()
            c.arc(0, 0, 92, 0, 2 * math.pi)
            src(c, BLANCO)
            c.fill()
            c.arc(0, 0, 80, 0, 2 * math.pi)
            src(c, col)
            c.fill()
            txt(c, str(n), 0, 2, 118, OSCURO, sombra=0)
    x = eo(pr(T, t0 + 0.3, 0.4))
    if x > 0:
        with tf(c, 540, 452 + (1 - x) * 60, 1, 0, x):
            w = min(960, ancho(c, titulo, 70) + 80)
            box(c, 0, 0, w, 104, 52, (0, 0, 0, 0.35), sombra=0)
            txt(c, titulo, 0, 0, 70, BLANCO, maxw=900, borde=0)


# ---------- intro
def sc_intro(c, T):
    # rayos giratorios
    s5, a5 = pop(T, 0.0, 0.5)
    with tf(c, 540, 600, 1, T * 0.25, a5 * 0.5):
        for k in range(14):
            a = k * 2 * math.pi / 14
            c.move_to(0, 0)
            c.arc(0, 0, 1400, a, a + math.pi / 14)
            c.close_path()
        src(c, (1, 1, 1, 0.08))
        c.fill()
    # billetes que salen disparados
    if T > 2.4:
        for p in BURST:
            tt = T - 2.45 - p["d"]
            if tt <= 0:
                continue
            x = 540 + math.cos(p["a"]) * p["v"] * tt
            y = 1000 + math.sin(p["a"]) * p["v"] * tt + 500 * tt * tt
            if p["em"]:
                emo(c, "💸", x, y, 110, r=p["rot"] + tt * 2)
            else:
                with tf(c, x, y, 0.75, p["rot"] + tt * p["giro"] * 0.4, sx=math.cos(tt * p["giro"])):
                    billete(c)
    if a5 > 0:
        with tf(c, 540, 600, lerp(2.6, 1, eo(pr(T, 0, 0.35))) * (1 + 0.04 * math.sin(T * 6)), -0.08, a5):
            c.arc(0, 14, 200, 0, 2 * math.pi)
            src(c, (0, 0, 0, 0.35))
            c.fill()
            c.arc(0, 0, 200, 0, 2 * math.pi)
            src(c, BLANCO)
            c.fill()
            c.arc(0, 0, 182, 0, 2 * math.pi)
            src(c, AMARILLO)
            c.fill()
            txt(c, "5", 0, 6, 290, OSCURO, sombra=0)
    lineas = [(0.34, "GASTOS PEQUEÑOS", 930, 100, BLANCO), (1.32, "QUE TE ESTÁN", 1050, 84, BLANCO),
              (1.94, "ROBANDO", 1190, 150, ROJO), (2.52, "DINERO", 1340, 150, VERDE)]
    for t0, s, y, size, col in lineas:
        x = pr(T, t0 - 0.05, 0.3)
        if x > 0:
            with tf(c, 540, y + (1 - eo(x)) * 80, eob(x), (1 - eo(x)) * 0.1, cl(x * 2)):
                txt(c, s, 0, 0, size, col, borde=14, bcol=OSCURO, maxw=1000)
    if T > 2.52:
        s, a = pop(T, 2.55, 0.35)
        emo(c, "💸", 870, 1250, 150, a, -0.3 + math.sin(T * 8) * 0.1, s)


# ---------- gancho
def sc_gancho(c, T):
    out = eo(pr(T, 7.25, 0.35))
    # notificación del banco
    k = eob(pr(T, 2.92, 0.5))
    if T > 2.92 and out < 1:
        with tf(c, 540, lerp(-150, 520, k) - out * 400, 1, 0, cl(pr(T, 2.92, 0.15)) * (1 - out)):
            box(c, 0, 0, 920, 200, 44, (1, 1, 1, 0.97), sombra=0.35)
            c.arc(-370, 0, 58, 0, 2 * math.pi)
            src(c, hx("#22b573"))
            c.fill()
            txt(c, "€", -370, 0, 64, BLANCO, sombra=0)
            txt(c, "BANCO · ahora", -285, -46, 30, hx("#8a8aa0"), font=BOLD, al="l", sombra=0)
            txt(c, "Nómina recibida", -285, 12, 46, hx("#1a1a2e"), font=BOLD, al="l", sombra=0)
            txt(c, "+1.400 €", 420, 12, 54, hx("#16a05c"), al="r", sombra=0)
    # saldo
    if T > 3.0 and out < 1:
        if T < 4.94:
            v = 1400 * eo(pr(T, 3.0, 0.8))
            col = BLANCO
        else:
            q = eio(pr(T, 4.94, 2.3))
            v = 1400 - (1400 - 87.35) * q
            col = lerpc(BLANCO, ROJO, q)
        sh = math.sin(T * 60) * 6 * (1 if 4.94 < T < 7.24 else 0)
        with tf(c, 540 + sh, 0, 1, 0, cl(pr(T, 3.0, 0.2)) * (1 - out)):
            txt(c, "TU SALDO", 0, 780, 44, (1, 1, 1, 0.75), font=BOLD)
            txt(c, eur(v), 0, 900, 150, col, borde=12, bcol=OSCURO, maxw=1000)
    # billetes que se van
    if 4.94 < T < 8.0:
        for j, p in enumerate(FUGA):
            tt = T - (5.0 + j * 0.14)
            if tt <= 0:
                continue
            x = 540 + math.cos(p["a"]) * p["v"] * tt
            y = 900 + math.sin(p["a"]) * p["v"] * tt + 300 * tt * tt
            with tf(c, x, y, 0.55, p["rot"] + tt * 2, a=cl(1.2 - tt), sx=math.cos(tt * p["giro"])):
                billete(c)
    # calendario
    s, a = pop(T, 4.94, 0.35)
    if a > 0 and out < 1:
        dia = 1 + int(8 * pr(T, 4.94, 2.3) + 0.001) if T < 7.24 else 9
        fase = (8 * pr(T, 4.94, 2.3)) % 1
        flip = 1 - 0.5 * (1 - eo(cl(fase * 4))) if T < 7.24 else 1
        with tf(c, 540, 1185, s, -0.05, a * (1 - out)):
            box(c, 0, 0, 230, 240, 30, BLANCO, sombra=0.35)
            rr(c, -115, -120, 230, 72, 30)
            src(c, hx("#e63946"))
            c.fill()
            c.rectangle(-115, -78, 230, 30)
            c.fill()
            txt(c, "DÍA", 0, -84, 40, BLANCO, sombra=0)
            with tf(c, 0, 40, 1, 0, 1, sy=flip):
                txt(c, str(dia), 0, 0, 120, hx("#1a1a2e"), sombra=0)
        emo(c, "💸", 790, 1170, 120, a * (1 - out), math.sin(T * 7) * 0.2)
    # cartera vacía
    s, a = pop(T, 7.45, 0.35)
    salida = eo(pr(T, 8.3, 0.3))
    if a > 0 and salida < 1:
        with tf(c, 540, 900 - salida * 200, s * (1 - salida * 0.5), math.sin(T * 25) * 0.08, a * (1 - salida)):
            cartera(c, con_billetes=False)
        ct = T - 7.8
        if ct > 0:
            y = 1000 + min(ct, 0.45) / 0.45 * 260 - (abs(math.sin(max(0, ct - 0.45) * 9)) * 60 * math.exp(-(ct - 0.45) * 4) if ct > 0.45 else 0)
            with tf(c, 600, y, 0.6, ct * 4, (1 - salida)):
                moneda(c)
        emo(c, "😰", 540, 640, 150, a * (1 - salida), 0, s)
    # sospechosos
    x = eo(pr(T, 8.8, 0.35))
    if x > 0:
        with tf(c, 540, 700 + (1 - x) * 50, 1, 0, x):
            txt(c, "LOS 5 SOSPECHOSOS", 0, 0, 82, BLANCO, borde=12, bcol=OSCURO, maxw=980)
    rojo = pr(T, 10.0, 0.4)
    for k, ch in enumerate(["☕", "🛵", "📱", "🛒", "🏷️"]):
        s, a = pop(T, 8.82 + k * 0.17, 0.35)
        if a <= 0:
            continue
        cx = 540 + (k - 2) * 196
        bob = math.sin(T * 4 + k) * 8
        with tf(c, cx, 960 + bob, s, 0, a):
            c.arc(0, 8, 84, 0, 2 * math.pi)
            src(c, (0, 0, 0, 0.35))
            c.fill()
            c.arc(0, 0, 84, 0, 2 * math.pi)
            src(c, lerpc(BLANCO, ROJO, rojo))
            c.fill()
            c.arc(0, 0, 72, 0, 2 * math.pi)
            src(c, BLANCO)
            c.fill()
            emo(c, ch, 0, 0, 88)
            txt(c, str(k + 1), 0, 125, 46, AMARILLO, borde=8, bcol=OSCURO)
    s, a = pop(T, 10.55, 0.3)
    if a > 0:
        with tf(c, 540, 1230, lerp(2.2, 1, eo(pr(T, 10.55, 0.2))), -0.1, a):
            sello(c, "¡CULPABLES!", 92)


# ---------- 1: café
def sc_cafe(c, T):
    cabecera(c, T, 11.2, 1, "EL CAFÉ DIARIO")
    sal = eo(pr(T, 15.8, 0.3))
    s, a = pop(T, 11.8, 0.45)
    if a > 0 and sal < 1:
        with tf(c, 540, 970 + math.sin(T * 2.5) * 10, 0.95 * s * (1 - sal), math.sin(T * 1.7) * 0.03, a):
            vaso_cafe(c, T)
    s, a = pop(T, 13.74, 0.4)
    if a > 0 and sal < 1:
        with tf(c, 815, 700, s * (1 - sal), 0.18 + math.sin(T * 3) * 0.05, a):
            box(c, 0, 0, 280, 110, 26, AMARILLO, sombra=0.35)
            c.arc(-112, 0, 10, 0, 2 * math.pi)
            src(c, OSCURO)
            c.fill()
            txt(c, "2,50 €", 20, 0, 62, OSCURO, sombra=0)
        x = eo(pr(T, 14.5, 0.3))
        if x > 0:
            with tf(c, 240, 640, 1, -0.12, x * (1 - sal)):
                txt(c, "«solo»", 0, 0, 70, BLANCO, borde=10, bcol=OSCURO)
    # cuadrícula de 22 cafés
    n = 0
    dim = 1 - 0.7 * eo(pr(T, 18.3, 0.3))
    for i in range(22):
        t0 = 16.05 + i * 0.09
        s, a = pop(T, t0, 0.3)
        if a <= 0:
            continue
        n = i + 1
        col, fila = i % 6, i // 6
        x = 540 + (col - 2.5) * 160
        y = 650 + fila * 165 + math.sin(T * 3 + i) * 4
        with tf(c, x, y, 0.27 * s, math.sin(T * 2 + i) * 0.06, a * dim):
            vaso_cafe(c, T, vapor=False)
    if n:
        x = eo(pr(T, 16.05, 0.3))
        with tf(c, 540, 1330, 1, 0, x):
            txt(c, f"{n} días × 2,50 €", 0, 0, 66, AMARILLO, borde=10, bcol=OSCURO)
    s, a = pop(T, 18.45, 0.4)
    if a > 0:
        sh = math.sin(T * 70) * 10 * (1 - pr(T, 19.68, 0.35)) if T > 19.68 else 0
        with tf(c, 540 + sh, 860, s, -0.04, a):
            txt(c, "= " + eur(55 * eo(pr(T, 18.45, 0.6)), 0), 0, 0, 200, ROJO, borde=16, bcol=BLANCO, maxw=1000)
            txt(c, "AL MES", 0, 150, 72, BLANCO, borde=10, bcol=OSCURO)
    s, a = pop(T, 19.6, 0.4)
    if a > 0:
        with tf(c, 540, 1130, s, 0.03, a):
            box(c, 0, 0, 760, 130, 65, AMARILLO, sombra=0.35)
            txt(c, "660 € AL AÑO", -40, 0, 72, OSCURO, sombra=0)
            emo(c, "😱", 300, 0, 80)


# ---------- 2: comida a domicilio
def sc_domicilio(c, T):
    cabecera(c, T, 20.5, 2, "COMIDA A DOMICILIO")
    if T < 24.6:
        xin = eo(pr(T, 20.9, 0.7))
        xout = ei(pr(T, 23.6, 0.6))
        x = lerp(1450, 560, xin) - xout * 1100
        mov = (0 < pr(T, 20.9, 0.7) < 1) or xout > 0
        y = 1000 + abs(math.sin(T * 14)) * 8
        if mov:
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            for k in range(4):
                lx = x + 170 + k * 25 + (T * 900) % 60
                c.move_to(lx, y - 60 + k * 45)
                c.line_to(lx + 110, y - 60 + k * 45)
            src(c, (1, 1, 1, 0.4))
            c.set_line_width(10)
            c.stroke()
        emo(c, "🍕", x + 120, y - 155, 140, r=0.1)
        emo(c, "🛵", x, y, 380)
    # bocadillo de pensamiento: pereza de cocinar
    s, a = pop(T, 22.2, 0.4)
    fin = eo(pr(T, 23.5, 0.3))
    if a > 0 and fin < 1:
        with tf(c, 330, 650, s, 0, a * (1 - fin)):
            c.arc(160, 150, 18, 0, 2 * math.pi)
            c.new_sub_path()
            c.arc(200, 200, 11, 0, 2 * math.pi)
            src(c, (1, 1, 1, 0.95))
            c.fill()
            nube(c, 330, 170)
            emo(c, "🍳", -45, -5, 90)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            for d in (1, -1):
                c.move_to(-95, -55 * d)
                c.line_to(5, 45 * d)
            src(c, hx("#e63946"))
            c.set_line_width(14)
            c.stroke()
            emo(c, "😴", 75, 0, 80)
    # ticket
    if T > 23.8:
        alto = 130
        for t0, h in ((23.8, 140), (24.24, 210), (25.14, 280), (25.88, 350), (26.64, 490)):
            alto = max(alto, lerp(alto, h, eo(pr(T, t0, 0.3))))
        x0, x1, top = 230, 850, 600
        with tf(c, 0, 0, 1, 0, cl(pr(T, 23.8, 0.2))):
            c.move_to(x0, top)
            c.line_to(x1, top)
            ticket_zigzag(c, x0, x1, top + alto)
            c.close_path()
            src(c, (0, 0, 0, 0.3))
            with tf(c, 8, 14):
                c.move_to(x0, top)
                c.line_to(x1, top)
                ticket_zigzag(c, x0, x1, top + alto)
                c.close_path()
                c.fill()
            c.move_to(x0, top)
            c.line_to(x1, top)
            ticket_zigzag(c, x0, x1, top + alto)
            c.close_path()
            src(c, hx("#fbfaf5"))
            c.fill()
            c.save()
            c.rectangle(x0, top, x1 - x0, alto)
            c.clip()
            gris = hx("#2a2a35")
            txt(c, "TU PEDIDO", 540, top + 60, 44, gris, font=MONO, sombra=0)
            c.set_dash([10, 10])
            src(c, hx("#999999"))
            c.set_line_width(3)
            for yy in (top + 105, top + 385):
                c.move_to(x0 + 30, yy)
                c.line_to(x1 - 30, yy)
                c.stroke()
            c.set_dash([])
            for t0, nom, precio, yy in ((24.24, "Envío", "2,99 €", 165), (25.14, "Tasas", "1,50 €", 235),
                                         (25.88, "Comida", "12,90 €", 305)):
                k = eo(pr(T, t0, 0.25))
                if k > 0:
                    with tf(c, (1 - k) * -40, 0, 1, 0, k):
                        txt(c, nom, x0 + 40, top + yy, 44, gris, font=MONO, al="l", sombra=0)
                        txt(c, precio, x1 - 40, top + yy, 44, gris, font=MONO, al="r", sombra=0)
            if T > 26.64:
                v = 17.39 * eo(pr(T, 26.64, 0.7))
                txt(c, "TOTAL", x0 + 40, top + 440, 56, hx("#e63946"), font=MONO, al="l", sombra=0)
                txt(c, eur(v), x1 - 40, top + 440, 56, hx("#e63946"), font=MONO, al="r", sombra=0)
            c.restore()
    s, a = pop(T, 27.5, 0.4)
    if a > 0:
        with tf(c, 540, 1205, s, -0.03, a):
            box(c, 0, 0, 640, 110, 55, VERDE, sombra=0.35)
            emo(c, "🍳", -235, 0, 66)
            txt(c, "EN CASA ≈ 4 €", 40, 0, 58, OSCURO, sombra=0)
    s, a = pop(T, 27.94, 0.4)
    if a > 0:
        with tf(c, 540, 1335, s, 0.02, a):
            txt(c, "¡CASI 4 VECES MÁS!", 0, 0, 66, AMARILLO, borde=10, bcol=OSCURO)


# ---------- 3: suscripciones
SUSC = [(31.86, "🎵", "Música", "-10,99 €", "#ff6b9d"), (32.64, "🎬", "Películas", "-13,99 €", "#7c5cff"),
        (33.48, "📱", "Apps", "-4,99 €", "#22b5e5"), (35.3, "☁️", "Nube extra", "-2,99 €", "#8fa3c4"),
        (35.75, "📺", "Prueba «gratis»", "-8,99 €", "#ff9f43")]


def sc_suscripciones(c, T):
    cabecera(c, T, 29.0, 3, "SUSCRIPCIONES OLVIDADAS")
    s, a = pop(T, 29.3, 0.5)
    if a <= 0:
        return
    pw, ph = 580, 860
    with tf(c, 540, 965 + (1 - s) * 200 if s < 1 else 965, 1, 0, a):
        top = -ph / 2
        rr(c, -pw / 2, top + 16, pw, ph, 64)
        src(c, (0, 0, 0, 0.4))
        c.fill()
        rr(c, -pw / 2, top, pw, ph, 64)
        src(c, hx("#121218"))
        c.fill()
        rr(c, -pw / 2 + 16, top + 16, pw - 32, ph - 32, 50)
        src(c, hx("#f2f3f8"))
        c.fill()
        rr(c, -70, top + 30, 140, 30, 15)
        src(c, hx("#121218"))
        c.fill()
        txt(c, "9:41", -200, top + 46, 26, hx("#121218"), font=BOLD, sombra=0)
        txt(c, "Movimientos", -240, top + 115, 42, hx("#121218"), al="l", sombra=0)
        txt(c, "Este mes", -240, top + 160, 26, hx("#8a8aa0"), font=BOLD, al="l", sombra=0)
        c.save()
        rr(c, -pw / 2 + 16, top + 16, pw - 32, ph - 32, 50)
        c.clip()
        for k, (t0, ch, nom, imp, col) in enumerate(SUSC):
            x = eob(pr(T, t0, 0.4))
            if x <= 0:
                continue
            cy = top + 245 + k * 112
            with tf(c, (1 - x) * 600, cy, 1, 0, cl(x * 2)):
                box(c, 0, 0, 500, 96, 24, BLANCO, sombra=0.08)
                c.arc(-195, 0, 34, 0, 2 * math.pi)
                src(c, hx(col, 0.25))
                c.fill()
                emo(c, ch, -195, 0, 40)
                txt(c, nom, -145, -14, 32, hx("#1a1a2e"), font=BOLD, al="l", sombra=0, maxw=200)
                txt(c, "Cobro mensual", -145, 22, 22, hx("#8a8aa0"), font=BOLD, al="l", sombra=0)
                txt(c, imp, 225, 0, 34, hx("#e63946"), al="r", sombra=0)
                if k >= 3:
                    q = pop(T, t0 + 0.2, 0.3)
                    with tf(c, 225, -40, q[0], 0.2, q[1]):
                        box(c, 0, 0, 56, 40, 20, AMARILLO, sombra=0)
                        txt(c, "¿?", 0, 0, 26, OSCURO, sombra=0)
        c.restore()
        if T > 36.0:
            k = eo(pr(T, 36.0, 0.6))
            rr(c, -pw / 2 + 16, top + ph - 130, pw - 32, 114, 0)
            c.save()
            rr(c, -pw / 2 + 16, top + 16, pw - 32, ph - 32, 50)
            c.clip()
            rr(c, -pw / 2 + 16, top + ph - 130, pw - 32, 120, 0)
            src(c, hx("#e63946", k))
            c.fill()
            c.restore()
            txt(c, "TOTAL / MES", -235, top + ph - 75, 34, (1, 1, 1, k), al="l", sombra=0)
            txt(c, "-" + eur(41.95 * k), 235, top + ph - 75, 46, (1, 1, 1, k), al="r", sombra=0)
    s, a = pop(T, 36.75, 0.4)
    if a > 0:
        emo(c, "🤔", 205, 640, 150, a, -0.15 + math.sin(T * 3) * 0.08, s)
        with tf(c, 850, 660, s, 0.2, a):
            box(c, 0, 0, 300, 100, 50, AMARILLO, sombra=0.35)
            txt(c, "¿LAS USAS?", 0, 0, 44, OSCURO, sombra=0)


# ---------- 4: súper sin lista
ITEMS = ["🍫", "🍪", "🧃", "🍕", "🥤", "🍟", "🧀", "🍦", "🍩", "🥓", "🍿", "🧁", "🍬", "🥨"]
HUECOS = [(-130, 20), (-40, 25), (50, 22), (140, 18), (-150, -60), (-60, -55), (30, -62), (120, -58),
          (-110, -140), (-20, -135), (70, -142), (160, -138), (-60, -215), (40, -222)]


def sc_super(c, T):
    cabecera(c, T, 38.0, 4, "SÚPER SIN LISTA")
    # carrito
    xin = eo(pr(T, 38.3, 0.8))
    if xin > 0:
        cx = lerp(-500, 540, xin)
        cy = 1110
        ruedas = (cx + 500) / 30
        llenos = 0

        def items():
            nonlocal llenos
            for i, ch in enumerate(ITEMS):
                t0 = 41.94 + i * 0.16
                tt = T - t0
                if tt <= 0:
                    continue
                hx_, hy = HUECOS[i]
                caida = cl(tt / 0.35)
                y = lerp(-470, hy, caida ** 2)
                if caida >= 1:
                    llenos += 1
                    b = tt - 0.35
                    y -= abs(math.sin(b * 12)) * 30 * math.exp(-b * 6)
                    if T > 44.6:
                        y += math.sin(T * 14 + i) * 3
                emo(c, ch, hx_, y, 92, a=cl(tt / 0.12), r=math.sin(i * 1.7) * 0.4)

        with tf(c, cx, cy + abs(math.sin(T * 10)) * 3 * (1 - xin), 1.15, 0):
            carrito(c, ruedas, items)
        if T > 41.94:
            x = eo(pr(T, 41.94, 0.3))
            with tf(c, 540, 1395, 1, 0, x):
                txt(c, f"{3 + llenos} PRODUCTOS", 0, 0, 62, AMARILLO, borde=10, bcol=OSCURO)
    # nube con lo que ibas a comprar
    s, a = pop(T, 40.2, 0.4)
    fin = eo(pr(T, 44.35, 0.3))
    if a > 0 and fin < 1:
        with tf(c, 540, 620, s, 0, a * (1 - fin)):
            nube(c, 560, 190)
            for k, (t0, ch) in enumerate(((40.32, "🥛"), (40.9, "🍞"), (41.12, "🥚"))):
                q = pop(T, t0, 0.35)
                emo(c, ch, -150 + k * 150, 0, 92, q[1], 0, q[0])
            txt(c, "SOLO 3 COSAS", 0, 150, 46, BLANCO, borde=10, bcol=OSCURO)
    # comparación final
    x = eo(pr(T, 44.5, 0.35))
    if x > 0:
        with tf(c, 540, 610, 1, 0, x):
            txt(c, "IBAS A GASTAR: 5 €", 0, 0, 56, BLANCO, borde=10, bcol=OSCURO)
    s, a = pop(T, 44.75, 0.4)
    if a > 0:
        with tf(c, 540, 715, s, -0.03, a):
            box(c, 0, 0, 760, 110, 55, ROJO, sombra=0.35)
            txt(c, "HAS GASTADO: 47 €", 0, 0, 62, BLANCO, sombra=0)


# ---------- 5: ofertas
def sc_oferta(c, T):
    cabecera(c, T, 45.9, 5, "COMPRAR POR OFERTA")
    sal = eo(pr(T, 48.7, 0.35))
    s, a = pop(T, 46.1, 0.5)
    if a > 0 and sal < 1:
        sb = pop(T, 47.75, 0.4)
        if sb[1] > 0:
            with tf(c, 540, 900, sb[0] * (1 - sal) * (1 + 0.05 * math.sin(T * 8)), T * 0.4, sb[1]):
                estrella(c, 380, 300, 18)
                src(c, hx("#e63946"))
                c.fill()
        tt = T - 46.1
        rot = 0.45 * math.exp(-1.2 * tt) * math.sin(5 * tt) + math.sin(T * 1.5) * 0.03
        with tf(c, 540, 560 - (1 - s) * 400, 1 - sal, rot, a * (1 - sal)):
            etiqueta_precio(c, T)
        for k, (ex, ey) in enumerate(((220, 640), (860, 760), (250, 1120), (840, 1180), (540, 1330))):
            tw = 0.5 + 0.5 * math.sin(T * 6 + k * 1.3)
            emo(c, "✨", ex, ey, 70, a * (1 - sal) * tw, 0, 0.7 + 0.4 * tw)
    # lección
    s, a = pop(T, 48.8, 0.45)
    if a > 0:
        g = cairo.RadialGradient(540, 660, 0, 540, 660, 260)
        g.add_color_stop_rgba(0, 1, 0.9, 0.4, 0.45 * a)
        g.add_color_stop_rgba(1, 1, 0.9, 0.4, 0)
        c.set_source(g)
        c.paint()
        emo(c, "💡", 540, 660, 170, a, math.sin(T * 3) * 0.08, s)
        x = eo(pr(T, 48.95, 0.3))
        with tf(c, 540, 830, 1, 0, x):
            txt(c, "RECUERDA ESTO:", 0, 0, 66, BLANCO, borde=10, bcol=OSCURO)
    x = eo(pr(T, 50.2, 0.35))
    if x > 0:
        with tf(c, 540, 930 + (1 - x) * 40, 1, 0, x):
            txt(c, "SI NO LO NECESITABAS…", 0, 0, 62, AMARILLO, borde=10, bcol=OSCURO, maxw=1000)
    s, a = pop(T, 51.7, 0.4)
    if a > 0:
        gris = pr(T, 52.4, 0.4)
        with tf(c, 540, 1080, s, 0, a):
            box(c, 0, 0, 780, 130, 65, lerpc(VERDE, hx("#6b7280"), gris), sombra=0.35)
            txt(c, "AHORRASTE 20 €", 0, 0, 66, OSCURO, sombra=0)
            tachar(c, -360, 360, 0, eo(pr(T, 52.4, 0.35)), hx("#e63946"), 16)
        q = pop(T, 52.6, 0.3)
        emo(c, "❌", 900, 1060, 110, q[1], 0, q[0])
    s, a = pop(T, 53.2, 0.4)
    if a > 0:
        sh = math.sin(T * 70) * 8 * (1 - pr(T, 53.2, 0.4))
        with tf(c, 540 + sh, 1265, lerp(1.6, 1, eo(pr(T, 53.2, 0.25))) if s > 0 else 0, -0.03, a):
            box(c, 0, 0, 800, 140, 70, ROJO, sombra=0.35)
            txt(c, "GASTASTE 20 €", 0, 0, 76, BLANCO, sombra=0)


# ---------- final
LISTA = [("☕", "Café diario"), ("🛵", "Comida a domicilio"), ("📱", "Suscripciones"),
         ("🛒", "Súper sin lista"), ("🏷️", "Comprar por oferta")]
COMENTARIOS = [(62.0, "Yo el 1", "☕", 230, 1030), (62.4, "El 3 sin duda", "😅", 760, 1140),
               (62.8, "¡TODOS!", "💀", 300, 1250), (63.1, "El 4…", "🛒", 790, 1330)]


def titular(c, T, t0, t1, linea1, linea2=None, y=400):
    x = eo(pr(T, t0, 0.35)) * (1 - eo(pr(T, t1, 0.25)))
    if x <= 0:
        return
    with tf(c, 540, y + (1 - x) * 50, 1, 0, x):
        txt(c, linea1, 0, 0, 84, BLANCO, borde=12, bcol=OSCURO, maxw=980)
        if linea2:
            txt(c, linea2, 0, 100, 64, AMARILLO, borde=10, bcol=OSCURO, maxw=980)


def sc_final(c, T):
    # A: sé sincero
    fa = eo(pr(T, 57.3, 0.3))
    s, a = pop(T, 55.1, 0.45)
    if a > 0 and fa < 1:
        with tf(c, 540, 740, s * (1 - fa * 0.3), -0.04, a * (1 - fa)):
            txt(c, "SÉ SINCERO", 0, 0, 140, AMARILLO, borde=16, bcol=OSCURO, maxw=1000)
        q = pop(T, 56.25, 0.4)
        with tf(c, 540 + math.sin(T * 3) * 40, 1010, 1, 0, 1 - fa):
            emo(c, "👀", 0, 0, 230, q[1], 0, q[0] * (1 if (T * 2.2) % 3 > 0.12 else 0.85))
    # B: lista
    titular(c, T, 57.44, 61.0, "¿CUÁL TE ROBA MÁS?")
    sal = eo(pr(T, 60.95, 0.3))
    if T > 57.4 and sal < 1:
        hl = int((T - 58.6) / 0.45) % 5 if 58.6 < T < 60.95 else -1
        for k, (ch, nom) in enumerate(LISTA):
            x = eob(pr(T, 57.5 + k * 0.15, 0.4))
            if x <= 0:
                continue
            y = 610 + k * 150
            act = k == hl
            with tf(c, 540 + (1 - x) * (-700 if k % 2 else 700), y, (1.06 if act else 1.0), 0, 1 - sal):
                box(c, 0, 0, 880, 124, 62, (1, 1, 1, 0.24 if act else 0.12), sombra=0.15,
                    borde=AMARILLO if act else (1, 1, 1, 0.25), bw=6 if act else 3)
                c.arc(-375, 0, 46, 0, 2 * math.pi)
                src(c, AMARILLO)
                c.fill()
                txt(c, str(k + 1), -375, 2, 58, OSCURO, sombra=0)
                emo(c, ch, -270, 0, 66)
                txt(c, nom, -205, 0, 50, BLANCO, al="l", sombra=0.3)
    # C: comentarios
    titular(c, T, 61.1, 63.35, "ESCRIBE EL NÚMERO", "EN COMENTARIOS")
    fc = eo(pr(T, 63.35, 0.35))
    if T > 61.1:
        x = eob(pr(T, 61.2, 0.45))
        y = lerp(800, 560, fc)
        sc_ = lerp(1, 0.8, fc)
        with tf(c, 540, y + (1 - x) * 300, sc_, 0, cl(x * 2) * (1 - fc * 0.6)):
            box(c, 0, 0, 920, 190, 40, BLANCO, sombra=0.35)
            c.arc(-370, 0, 56, 0, 2 * math.pi)
            src(c, hx("#dfe3ee"))
            c.fill()
            emo(c, "🙂", -370, 0, 70)
            txt(c, "Tú", -290, -48, 30, hx("#8a8aa0"), font=BOLD, al="l", sombra=0)
            frase = "El número 3, sin duda"
            n = int(len(frase) * pr(T, 61.7, 1.1))
            w = txt(c, frase[:n], -290, 12, 46, hx("#1a1a2e"), font=BOLD, al="l", sombra=0)
            if n == len(frase):
                q = pop(T, 62.85, 0.3)
                emo(c, "😅", -290 + w + 50, 10, 54, q[1], 0, q[0])
            elif (T * 3) % 1 < 0.6:
                c.rectangle(-290 + w + 4, -14, 5, 52)
                src(c, hx("#1a1a2e"))
                c.fill()
            emo(c, "❤️", 395, 0, 48)
        for t0, frase, ch, cx, cy in COMENTARIOS:
            q = pop(T, t0, 0.35)
            if q[1] <= 0 or fc >= 1:
                continue
            with tf(c, cx, cy - (T - t0) * 25, q[0], 0, q[1] * (1 - fc)):
                w = ancho(c, frase, 40, BOLD) + 120
                box(c, 0, 0, w, 84, 42, (1, 1, 1, 0.92), sombra=0.25)
                txt(c, frase, -w / 2 + 30, 0, 40, hx("#1a1a2e"), font=BOLD, al="l", sombra=0)
                emo(c, ch, w / 2 - 45, 0, 44)
    # D: compartir
    titular(c, T, 63.4, 99, "Y COMPARTE ESTE VÍDEO", y=330)
    s, a = pop(T, 63.55, 0.5)
    if a > 0:
        lat = 1 + 0.06 * math.sin(T * 6)
        for k in range(3):
            f = ((T * 0.8 + k / 3) % 1)
            c.arc(540, 900, 150 + f * 140, 0, 2 * math.pi)
            src(c, (1, 0.82, 0.25, 0.35 * (1 - f) * a))
            c.set_line_width(6)
            c.stroke()
        with tf(c, 540, 900, s * lat, 0, a):
            c.arc(0, 12, 150, 0, 2 * math.pi)
            src(c, (0, 0, 0, 0.35))
            c.fill()
            c.arc(0, 0, 150, 0, 2 * math.pi)
            src(c, AMARILLO)
            c.fill()
            flecha_compartir(c, OSCURO)
        x = eo(pr(T, 64.3, 0.35))
        with tf(c, 540, 1125, 1, 0, x):
            txt(c, "con esa persona que…", 0, 0, 58, BLANCO, borde=10, bcol=OSCURO)
    s, a = pop(T, 65.5, 0.45)
    if a > 0:
        with tf(c, 540, 1300, s, -0.02, a):
            c.arc(-330, 0, 70, 0, 2 * math.pi)
            src(c, BLANCO)
            c.fill()
            emo(c, "😩", -330, 0, 96)
            box(c, 70, 0, 680, 120, 40, BLANCO, sombra=0.3)
            c.move_to(-268, 0)
            c.line_to(-250, -24)
            c.line_to(-250, 24)
            c.close_path()
            src(c, BLANCO)
            c.fill()
            txt(c, "«No llego a fin de mes»", 70, 0, 46, hx("#1a1a2e"), font=BOLD, sombra=0, maxw=620)
    s, a = pop(T, 67.75, 0.4)
    if a > 0:
        emo(c, "😂", 190, 860, 130, a, 0.2 + math.sin(T * 8) * 0.1, s)


SCENE_FNS = [sc_intro, sc_gancho, sc_cafe, sc_domicilio, sc_suscripciones, sc_super, sc_oferta, sc_final]


# ------------------------------------------------------------------ subtítulos karaoke
def trozos():
    out, cur = [], []
    for i, w in enumerate(PALABRAS):
        cur.append(w)
        sig = PALABRAS[i + 1] if i + 1 < len(PALABRAS) else None
        corta = (w["w"][-1] in ".,?!:" or len(cur) >= 4 or sum(len(x["w"]) + 1 for x in cur) > 18
                 or (sig and sig["s"] - w["e"] > 0.35))
        if corta or sig is None:
            out.append(cur)
            cur = []
    res = []
    for k, ch in enumerate(out):
        fin = out[k + 1][0]["s"] if k + 1 < len(out) else ch[-1]["e"] + 1.0
        fin = min(fin, ch[-1]["e"] + 0.7)
        res.append((ch[0]["s"] - 0.05, fin, ch))
    return res


TROZOS = trozos()


def subtitulos(c, T):
    if T < 2.85:
        return
    for t0, t1, ch in TROZOS:
        if t0 <= T < t1:
            break
    else:
        return
    size = 76
    palabras = [w["w"].upper() for w in ch]
    esp = ancho(c, " ", size)
    ws = [ancho(c, p, size) for p in palabras]
    total = sum(ws) + esp * (len(ws) - 1)
    lineas = [list(range(len(ws)))]
    if total > 960:
        mitad = total / 2
        acc, corte = 0, 1
        for i, w in enumerate(ws):
            acc += w + esp
            if acc >= mitad:
                corte = max(1, i + (1 if acc - mitad < w / 2 else 0))
                break
        lineas = [list(range(corte)), list(range(corte, len(ws)))]
    s = eob(pr(T, t0, 0.18)) * 0.15 + 0.85
    with tf(c, 540, 1530, s, 0, cl(pr(T, t0, 0.08) * 1.0)):
        for li, idx in enumerate(lineas):
            if not idx:
                continue
            lw = sum(ws[i] for i in idx) + esp * (len(idx) - 1)
            x = -lw / 2
            y = (li - (len(lineas) - 1) / 2) * size * 1.15
            for i in idx:
                w = ch[i]
                sig = ch[i + 1]["s"] if i + 1 < len(ch) else w["e"] + 0.3
                act = w["s"] <= T < max(sig, w["s"] + 0.1)
                hecho = T >= w["s"]
                col = AMARILLO if act else (BLANCO if hecho else (1, 1, 1, 0.85))
                k = 1 + 0.12 * (1 - eo(pr(T, w["s"], 0.15))) if act else 1
                with tf(c, x + ws[i] / 2, y, k):
                    txt(c, palabras[i], 0, 0, size, col, borde=14, bcol=(0.05, 0.03, 0.12), sombra=0.5)
                x += ws[i] + esp


def barrido(c, T):
    for t0 in (11.2, 20.5, 29.0, 38.0, 45.9):
        p = pr(T, t0 - 0.28, 0.5)
        if 0 < p < 1:
            x = lerp(-900, W + 900, eio(p))
            c.move_to(x - 300, 0)
            c.line_to(x + 300, 0)
            c.line_to(x - 100, H)
            c.line_to(x - 700, H)
            c.close_path()
            src(c, AMARILLO)
            c.fill()
            c.move_to(x + 330, 0)
            c.line_to(x + 420, 0)
            c.line_to(x + 20, H)
            c.line_to(x - 70, H)
            c.close_path()
            src(c, BLANCO)
            c.fill()


def frame(n):
    T = n / FPS
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    fondo(c, T)
    i, t0, t1 = escena_de(T)
    ent = eo(pr(T, t0, 0.3)) if i > 0 else 1
    sal = ei(pr(T, t1 - 0.25, 0.25)) if t1 < FIN else 0
    a = ent * (1 - sal)
    s = lerp(0.93, 1, ent) * (1 + 0.1 * sal)
    with tf(c, W / 2, H / 2, s, 0, a):
        c.translate(-W / 2, -H / 2)
        SCENE_FNS[i](c, T)
    progreso(c, T)
    subtitulos(c, T)
    barrido(c, T)
    surf.flush()
    return bytes(surf.get_data())


# ------------------------------------------------------------------ audio
def sfx_eventos():
    ev = [(0.02, "golpe"), (0.34, "whoosh"), (1.32, "whoosh"), (1.94, "pop"), (2.5, "caja"),
          (2.92, "whoosh"), (2.97, "ding"), (3.05, "caja"), (4.95, "bajada"), (7.45, "pop"), (7.85, "tin"),
          (8.8, "whoosh")]
    ev += [(8.82 + k * 0.17, "pop") for k in range(5)]
    ev += [(10.55, "sello")]
    for t0 in (11.2, 20.5, 29.0, 38.0, 45.9):
        ev += [(t0 - 0.3, "whoosh"), (t0 + 0.08, "golpe")]
    ev += [(11.8, "pop"), (13.74, "pop"), (14.5, "pop")]
    ev += [(16.05 + i * 0.09, "tic") for i in range(22)]
    ev += [(18.45, "caja"), (19.62, "golpe")]
    ev += [(20.9, "moto"), (22.2, "pop"), (23.6, "whoosh"), (24.24, "tic2"), (25.14, "tic2"), (25.88, "tic2"),
           (26.64, "caja"), (27.5, "ding"), (27.94, "pop")]
    ev += [(29.3, "whoosh")] + [(s[0], "ding") for s in SUSC] + [(36.0, "golpe"), (36.75, "pop")]
    ev += [(38.3, "whoosh"), (40.2, "pop"), (40.32, "pop"), (40.9, "pop"), (41.12, "pop")]
    ev += [(41.94 + i * 0.16 + 0.35, "plop") for i in range(len(ITEMS))]
    ev += [(44.5, "whoosh"), (44.75, "golpe")]
    ev += [(46.1, "whoosh"), (47.75, "brillo"), (48.8, "ding"), (50.2, "pop"), (51.7, "pop"), (52.4, "sello"),
           (53.2, "golpe")]
    ev += [(55.1, "whoosh"), (56.25, "pop"), (57.44, "whoosh")] + [(57.5 + k * 0.15, "pop") for k in range(5)]
    ev += [(61.1, "whoosh")] + [(61.7 + k * 0.1, "tecla") for k in range(11)] + [(62.85, "pop")]
    ev += [(t, "pop") for t, *_ in COMENTARIOS]
    ev += [(63.4, "whoosh"), (63.55, "golpe"), (65.5, "pop"), (67.75, "ding")]
    return ev


def sintetiza(nombre, rng):
    def t(d):
        return np.arange(int(d * SR)) / SR
    if nombre == "pop":
        x = t(0.09)
        f = 500 + 900 * x / 0.09
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 40) * 0.5
    if nombre == "plop":
        x = t(0.12)
        f = 900 - 500 * x / 0.12
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 30) * 0.35
    if nombre in ("tic", "tic2", "tecla"):
        x = t(0.03)
        n = rng.standard_normal(len(x))
        n = np.diff(n, prepend=0)
        g = {"tic": 0.18, "tic2": 0.35, "tecla": 0.2}[nombre]
        return n * np.exp(-x * 200) * g
    if nombre == "whoosh":
        x = t(0.45)
        n = rng.standard_normal(len(x))
        k = int(SR * 0.002)
        n = np.convolve(n, np.ones(k) / k, mode="same")
        env = np.sin(np.pi * x / 0.45) ** 2
        return n * env * 0.9
    if nombre == "golpe":
        x = t(0.4)
        f = 150 * np.exp(-x * 9) + 45
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)
        n = rng.standard_normal(len(x)) * np.exp(-x * 40) * 0.3
        return (s + n) * 0.8
    if nombre == "sello":
        x = t(0.3)
        s = np.sin(2 * np.pi * 90 * x) * np.exp(-x * 15)
        n = np.convolve(rng.standard_normal(len(x)), np.ones(20) / 20, "same") * np.exp(-x * 25) * 3
        return (s + n) * 0.7
    if nombre == "ding":
        x = t(0.8)
        return (np.sin(2 * np.pi * 1318 * x) + 0.5 * np.sin(2 * np.pi * 1976 * x)) * np.exp(-x * 6) * 0.22
    if nombre == "tin":
        x = t(0.5)
        return (np.sin(2 * np.pi * 2600 * x) + 0.4 * np.sin(2 * np.pi * 3900 * x)) * np.exp(-x * 10) * 0.18
    if nombre == "brillo":
        x = t(0.9)
        out = np.zeros(len(x))
        for k, fq in enumerate((1568, 1976, 2349, 3136)):
            d = int(k * 0.07 * SR)
            xx = x[: len(x) - d]
            out[d:] += np.sin(2 * np.pi * fq * xx) * np.exp(-xx * 7) * 0.12
        return out
    if nombre == "caja":
        x = t(0.9)
        clic = rng.standard_normal(len(x)) * np.exp(-x * 120) * 0.3
        d = int(0.06 * SR)
        xx = x[: len(x) - d]
        campana = np.zeros(len(x))
        campana[d:] = sum(np.sin(2 * np.pi * fq * xx) * a for fq, a in ((2093, 0.5), (2637, 0.35), (3136, 0.25))) * np.exp(-xx * 5)
        return (clic + campana * 0.35) * 0.9
    if nombre == "bajada":
        x = t(2.3)
        f = 900 * np.exp(-x * 0.9) + 120
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 - x / 2.3) * 0.12
    if nombre == "moto":
        x = t(1.0)
        f = 70 + 40 * np.sin(np.pi * x)
        s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR))
        s = np.convolve(s, np.ones(30) / 30, "same")
        return s * np.sin(np.pi * x) * 0.12
    return np.zeros(1)


def musica(dur, rng):
    n = int(dur * SR)
    out = np.zeros(n)
    bpm = 100
    beat = 60 / bpm
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    acordes = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 60], [55, 59, 62, 65]]  # Am7 Fmaj7 C G7
    total_beats = int(dur / beat) + 1
    for b in range(total_beats):
        t0 = b * beat
        i0 = int(t0 * SR)
        acorde = acordes[(b // 4) % 4]
        compas = b % 4
        def add(sig, off=0.0):
            s = i0 + int(off * SR)
            if s >= n:
                return
            e = min(n, s + len(sig))
            out[s:e] += sig[: e - s]
        if compas == 0:  # pad
            x = np.arange(int(4 * beat * SR)) / SR
            env = np.minimum(1, x / 0.3) * np.minimum(1, (4 * beat - x) / 0.4)
            pad = sum(np.sin(2 * np.pi * f(m) * x) + 0.25 * np.sin(2 * np.pi * f(m) * 1.003 * 2 * x) for m in acorde)
            add(pad * env * 0.025)
        # bajo
        x = np.arange(int(beat * 0.9 * SR)) / SR
        if compas in (0, 2, 3):
            nota = acorde[0] - 12 if compas != 3 else acorde[2] - 24
            add(np.sin(2 * np.pi * f(nota) * x) * np.exp(-x * 2.5) * 0.16)
        # arpegio en corcheas
        for h in range(2):
            x = np.arange(int(beat / 2 * SR)) / SR
            m = acorde[(compas * 2 + h) % 4] + 12
            tri = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f(m) * x))
            add(tri * np.exp(-x * 9) * 0.05, h * beat / 2)
        if t0 < 2.8 or t0 > dur - 2.5:
            continue
        # batería
        x = np.arange(int(0.3 * SR)) / SR
        if compas in (0, 2) or (compas == 1 and b % 8 == 5):
            fr = 110 * np.exp(-x * 25) + 45
            add(np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-x * 10) * 0.35, 0.0 if compas != 1 else beat / 2)
        if compas in (1, 3):
            nz = np.diff(rng.standard_normal(len(x)), prepend=0)
            add(nz * np.exp(-x * 22) * 0.07)
        for h in range(2):
            xh = np.arange(int(0.05 * SR)) / SR
            nz = np.diff(np.diff(rng.standard_normal(len(xh)), prepend=0), prepend=0)
            add(nz * np.exp(-xh * 90) * (0.02 if h else 0.012), h * beat / 2)
    fi = int(1.5 * SR)
    out[-fi:] *= np.linspace(1, 0, fi)
    return out


def audio(ruta_wav):
    rng = np.random.default_rng(3)
    voz = np.frombuffer(subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", os.path.join(AQUI, "voz.mp3"), "-ac", "1", "-ar", str(SR),
         "-f", "f32le", "-"], capture_output=True, check=True).stdout, dtype=np.float32).astype(float)
    n = int(DUR * SR)
    mezcla = np.zeros(n)
    voz = voz[:n]
    voz = voz / (np.abs(voz).max() + 1e-9) * 0.9
    mezcla[: len(voz)] += voz
    # música con «ducking» bajo la voz
    m = musica(DUR, rng)
    env = np.abs(np.pad(voz, (0, n - len(voz))))
    k = int(0.15 * SR)
    env = np.convolve(env, np.ones(k) / k, "same")
    duck = 1 - 0.55 * np.clip(env / 0.06, 0, 1)
    mezcla += m * duck * 0.55
    for t0, nombre in sfx_eventos():
        s = sintetiza(nombre, rng) * 0.6
        i0 = int(max(0, t0) * SR)
        e = min(n, i0 + len(s))
        mezcla[i0:e] += s[: e - i0]
    mezcla = mezcla / (np.abs(mezcla).max() + 1e-9) * 0.95
    import wave
    with wave.open(ruta_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mezcla * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main
def main():
    args = sys.argv[1:]
    desde = hasta = None
    if "--desde" in args:
        i = args.index("--desde")
        desde = float(args[i + 1])
        del args[i:i + 2]
    if "--hasta" in args:
        i = args.index("--hasta")
        hasta = float(args[i + 1])
        del args[i:i + 2]
    salida = args[0] if args else os.path.join(AQUI, "..", "gastos_pequenos.mp4")
    f0 = int((desde or 0) * FPS)
    f1 = int((hasta or DUR) * FPS)
    wav = salida + ".wav"
    audio(wav)
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-ss", str(f0 / FPS), "-t", str((f1 - f0) / FPS), "-i", wav,
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
           "-movflags", "+faststart", "-shortest", salida]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, b in enumerate(pool.imap(frame, range(f0, f1), chunksize=4)):
            ff.stdin.write(b)
            if k % 150 == 0:
                print(f"  fotograma {f0 + k}/{f1}", flush=True)
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    print("Listo:", os.path.abspath(salida))


if __name__ == "__main__":
    main()
