#!/usr/bin/env python3
"""Vídeo animado "Tengo 30 días para llegar a Nürburgring" (vertical 1080x1920, 30 fps).

Uso:
    python3 audio.py                 # → mezcla.wav
    python3 render.py                # → ../nurburgring.mp4
    python3 render.py --frame 52.3   # → fotograma de prueba en /tmp
"""
import json
import math
import os
import random
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
DUR = 124.6
FD = "/usr/share/fonts/opentype/inter/"
FONTS = {
    "black": FD + "InterDisplay-Black.otf",
    "ital": FD + "Inter-BlackItalic.otf",
    "bold": FD + "InterDisplay-Bold.otf",
    "semi": FD + "Inter-SemiBold.otf",
    "mono": "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
}
WHITE = (245, 247, 250)
GREEN = (0, 255, 136)
RED = (255, 52, 64)
BLUE = (40, 140, 255)
GOLD = (255, 204, 40)
GREY = (150, 160, 170)
DARK = (8, 12, 11)


# ============================================================ utilidades
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, t0, d):
    return clamp((t - t0) / d) if d > 0 else float(t >= t0)


def e_out(p):
    return 1 - (1 - p) ** 3


def e_in(p):
    return p ** 3


def e_io(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def e_back(p, s=2.2):
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def lerp(a, b, p):
    return a + (b - a) * p


def mix(c1, c2, p):
    return tuple(int(lerp(a, b, p)) for a, b in zip(c1, c2))


@lru_cache(maxsize=256)
def font(name, size):
    return ImageFont.truetype(FONTS[name], size)


@lru_cache(maxsize=2048)
def txt(text, size, color=WHITE, fn="black", glow=0, stroke=0, stroke_col=(0, 0, 0), track=0, maxw=0, shadow=True):
    """Texto (multilínea centrado) como RGBA con glow y sombra opcionales."""
    if maxw:
        while size > 20:
            f = font(fn, size)
            wmax = max(f.getlength(l) + track * len(l) for l in text.split("\n"))
            if wmax <= maxw:
                break
            size -= 4
    f = font(fn, size)
    lines = text.split("\n")
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * 0.98)
    widths = [int(f.getlength(l) + track * max(0, len(l) - 1)) for l in lines]
    pad = max(glow * 2, stroke + 4, 12)
    w = max(widths) + pad * 2 + 8
    h = lh * len(lines) + pad * 2
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    def draw_lines(dr, col, sw=0, scol=None, off=(0, 0)):
        for i, l in enumerate(lines):
            x = (w - widths[i]) / 2 + off[0]
            y = pad + i * lh + off[1]
            if track:
                for ch in l:
                    dr.text((x, y), ch, font=f, fill=col, stroke_width=sw, stroke_fill=scol)
                    x += f.getlength(ch) + track
            else:
                dr.text((x, y), l, font=f, fill=col, stroke_width=sw, stroke_fill=scol)

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_lines(ImageDraw.Draw(sh), (0, 0, 0, 170), stroke, (0, 0, 0, 170), off=(0, size * 0.06))
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(size * 0.06)))
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_lines(ImageDraw.Draw(g), color + (255,), stroke)
        g = g.filter(ImageFilter.GaussianBlur(glow))
        out.alpha_composite(g)
        out.alpha_composite(g)
    draw_lines(d, color + (255,), stroke, stroke_col + (255,) if stroke else None)
    out.alpha_composite(lay)
    return out


_alpha_lut = {}


def with_alpha(img, a):
    if a >= 0.999:
        return img
    q = int(a * 50)
    lut = _alpha_lut.get(q)
    if lut is None:
        lut = _alpha_lut[q] = [int(v * q / 50) for v in range(256)]
    img = img.copy()
    img.putalpha(img.getchannel("A").point(lut))
    return img


def put(f, img, cx, cy, s=1.0, a=1.0, rot=0.0, anchor="c"):
    """Pega img centrada en (cx, cy) con escala, opacidad y giro."""
    if a <= 0.01 or s <= 0.01:
        return
    if abs(s - 1) > 0.004:
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
    if rot:
        img = img.rotate(rot, Image.BILINEAR, expand=True)
    img = with_alpha(img, a)
    if anchor == "c":
        x, y = int(cx - img.width / 2), int(cy - img.height / 2)
    elif anchor == "l":
        x, y = int(cx), int(cy - img.height / 2)
    else:
        x, y = int(cx - img.width), int(cy - img.height / 2)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(f.width, x + img.width), min(f.height, y + img.height)
    if x1 <= x0 or y1 <= y0:
        return
    f.alpha_composite(img.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def T(f, t, t0, text, size, y, col=WHITE, fn="black", x=W / 2, anim="pop", t1=None, glow=0, track=0,
      maxw=980, stroke=0, d=0.35, anchor="c"):
    """Elemento de texto con animación de entrada/salida."""
    if t < t0 or (t1 is not None and t > t1 + 0.25):
        return
    img = txt(text, size, col, fn, glow, stroke, (0, 0, 0), track, maxw)
    p = prog(t, t0, d)
    a = clamp(p * 3)
    s = 1.0
    dx = dy = 0
    if anim == "pop":
        s = 0.4 + 0.6 * e_back(p)
    elif anim == "slam":
        s = lerp(2.6, 1.0, e_out(prog(t, t0, 0.18)))
        a = clamp(prog(t, t0, 0.12) * 1.5)
    elif anim == "up":
        dy = (1 - e_out(p)) * 90
    elif anim == "left":
        dx = -(1 - e_out(p)) * 700
    elif anim == "right":
        dx = (1 - e_out(p)) * 700
    elif anim == "fade":
        pass
    if t1 is not None and t > t1:
        q = prog(t, t1, 0.25)
        a *= 1 - q
        s *= 1 + 0.1 * q
    put(f, img, x + dx, y + dy, s, a, anchor=anchor)


def chip(text, col, size=40, fg=(0, 0, 0), padx=30, pady=16, fn="black"):
    return _chip(text, col, size, fg, padx, pady, fn)


@lru_cache(maxsize=256)
def _chip(text, col, size, fg, padx, pady, fn):
    f = font(fn, size)
    tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    w, h = tw + padx * 2, asc + desc + pady * 2 - int(size * 0.2)
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # sombra
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((20, 28, 20 + w, 28 + h), h // 2 if h < 90 else 22, fill=(0, 0, 0, 160))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(im)
    skew = [(20 + 14, 20), (20 + w, 20), (20 + w - 14, 20 + h), (20, 20 + h)]
    d.polygon(skew, fill=col + (255,))
    d.text((20 + padx, 20 + pady - int(size * 0.12)), text, font=f, fill=fg + (255,))
    return im


# ============================================================ fondo
def radial(w, h, cx, cy, r):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return np.clip(1 - np.hypot(x - cx, y - cy) / r, 0, 1)


def make_static():
    st = {}
    base = np.zeros((H, W, 3), np.float32)
    base[:] = DARK
    g = radial(W, H, W / 2, H * 0.42, 1300) ** 1.6
    st["glow"] = g
    st["base"] = base
    vig = 1 - radial(W, H, W / 2, H / 2, 1250) ** 0.8
    v = Image.fromarray((np.clip(vig * 1.25, 0, 1) * 235).astype(np.uint8), "L")
    vi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vi.putalpha(v)
    st["vig"] = vi
    rng = np.random.default_rng(1)
    st["grain"] = []
    for k in range(6):
        n = rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint8)
        a = Image.fromarray(n, "L").resize((W, H), Image.NEAREST)
        im = Image.merge("RGBA", (a, a, a, Image.new("L", (W, H), 14)))
        st["grain"].append(im)
    # líneas de escaneo
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sl)
    for y in range(0, H, 4):
        d.line((0, y, W, y), fill=(0, 0, 0, 22))
    st["scan"] = sl
    return st


_BG = {}


def bg_image(tint):
    """Fondo base con resplandor del color de la escena (cacheado)."""
    if tint not in _BG:
        S = STATIC
        img = S["base"] + S["glow"][..., None] * np.array(tint, np.float32)[None, None] * 0.22
        _BG[tint] = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return _BG[tint]


def grid_floor(f, t, col, speed=1.0, y0=1180, alpha=0.5):
    """Suelo en perspectiva tipo circuito que avanza."""
    d = ImageDraw.Draw(f)
    hy = y0
    c = mix(DARK, col, 0.35 * alpha)
    for i in range(-12, 13):
        x_far = W / 2 + i * 40
        x_near = W / 2 + i * 380
        d.line((x_far, hy, x_near, H), fill=c, width=2)
    off = (t * speed * 1.6) % 1.0
    for k in range(14):
        z = (k + off) / 14
        y = hy + (H - hy) * z ** 2.2
        cc = mix(DARK, col, 0.5 * alpha * z)
        d.line((0, y, W, y), fill=cc, width=2 if z < 0.5 else 3)


SPEED = [(random.Random(i).random(), random.Random(i * 7 + 1).random(), random.Random(i * 13 + 5).random())
         for i in range(60)]


def speed_lines(f, t, col, dirx=-1, y_range=(500, 1400), strength=1.0, speed=1.0):
    d = ImageDraw.Draw(f)
    for a, b, c in SPEED:
        y = y_range[0] + a * (y_range[1] - y_range[0])
        L = 120 + 380 * b
        v = (1400 + 1800 * c) * speed
        x = ((c * 3000 + t * v) % (W + L * 2)) - L
        if dirx < 0:
            x = W - x
        cc = mix(DARK, col, (0.25 + 0.5 * b) * strength)
        d.line((x, y, x + L * (-dirx), y), fill=cc, width=2 if b < 0.6 else 3)


PART = [(random.Random(i * 3).random(), random.Random(i * 5 + 2).random(), random.Random(i * 11 + 3).random())
        for i in range(70)]


def particles(f, t, col, amount=1.0):
    d = ImageDraw.Draw(f)
    for i, (a, b, c) in enumerate(PART[: int(70 * amount)]):
        x = (a * W + math.sin(t * 0.7 + i) * 30) % W
        y = H - ((b * H + t * (40 + 90 * c)) % (H + 40))
        r = 1.5 + 3 * c
        cc = mix(DARK, col, 0.35 + 0.5 * c * (0.6 + 0.4 * math.sin(t * 3 + i)))
        d.ellipse((x - r, y - r, x + r, y + r), fill=cc)


# ============================================================ coches
def catmull(pts, n=12, closed=True):
    out = []
    P = pts + pts[:3] if closed else [pts[0]] + pts + [pts[-1]]
    rng_ = len(pts) if closed else len(pts) - 1
    for i in range(rng_):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for k in range(n):
            s = k / n
            s2, s3 = s * s, s * s * s
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * s + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * s2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * s3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * s + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * s2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * s3)
            out.append((x, y))
    return out


CARS = {
    # Audi A6 C5 (1997-2004): berlina larga, techo en arco muy redondeado
    "audi": dict(
        body=[(40, 280), (14, 262), (8, 222), (16, 186), (40, 168), (150, 156), (262, 146), (318, 106),
              (372, 70), (440, 52), (530, 46), (610, 54), (660, 70), (720, 108), (772, 146), (880, 160),
              (950, 172), (986, 192), (996, 228), (992, 262), (968, 282), (500, 286)],
        dlo=[(300, 140), (338, 104), (380, 76), (440, 60), (528, 55), (604, 61), (640, 74), (700, 112), (742, 140)],
        bpil=(498, 516), cpil=(300, 342), wheels=(208, 790), top=(196, 202, 210), bot=(92, 98, 108),
        seams=[338, 507, 732], handles=[392, 590], name="AUDI A6", sub="C5 · 1997–2004", accent=RED,
        spokes=6, lights="audi"),
    # BMW Serie 3 E46 (1998-2006): más compacto, capó largo, "Hofmeister kink" en la ventanilla trasera
    "bmw": dict(
        body=[(44, 280), (16, 262), (10, 224), (18, 190), (44, 170), (160, 160), (270, 150), (318, 112),
              (366, 76), (420, 58), (510, 52), (585, 58), (628, 72), (690, 112), (742, 148), (870, 160),
              (948, 170), (986, 190), (998, 226), (994, 262), (970, 282), (500, 286)],
        dlo=[(318, 142), (322, 120), (360, 86), (420, 66), (508, 60), (580, 65), (612, 76), (668, 114), (712, 142)],
        bpil=(482, 499), cpil=(318, 356), wheels=(204, 784), top=(70, 128, 230), bot=(14, 40, 110),
        seams=[352, 491, 704], handles=[380, 570], name="BMW E46", sub="SERIE 3 · 1998–2006", accent=BLUE,
        spokes=5, lights="bmw"),
}
CAR_W = 1000  # unidades
SS = 2        # supersampling


def _poly(pts, k):
    return [(x * k, y * k) for x, y in pts]


@lru_cache(maxsize=8)
def car_body(kind, silhouette=False):
    c = CARS[kind]
    k = SS
    w, h = CAR_W * k + 40 * k, 340 * k
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ox = 20 * k
    body = [(x * k + ox, y * k) for x, y in catmull(c["body"], 10)]
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(body, fill=255)
    wx = c["wheels"]
    md = ImageDraw.Draw(mask)
    for x in wx:  # pasos de rueda
        r = 84 * k
        md.ellipse((x * k + ox - r, 268 * k - r, x * k + ox + r, 268 * k + r), fill=0)
    if silhouette:
        sil = Image.new("RGBA", (w, h), (18, 22, 24, 255))
        im.paste(sil, (0, 0), mask)
        d = ImageDraw.Draw(im)
        d.line(body + [body[0]], fill=(90, 100, 105, 255), width=3 * k)
        for x in wx:
            r = 68 * k
            d.ellipse((x * k + ox - r, 268 * k - r, x * k + ox + r, 268 * k + r), fill=(12, 14, 16, 255),
                      outline=(90, 100, 105, 255), width=3 * k)
        return im.resize((w // k, h // k), Image.LANCZOS)
    # degradado de la carrocería
    g = np.zeros((h, w, 4), np.uint8)
    yy = np.linspace(0, 1, h)[:, None]
    top, bot = np.array(c["top"]), np.array(c["bot"])
    prof = np.clip((yy - 0.15) / 0.75, 0, 1)
    col = top * (1 - prof) + bot * prof
    # brillo en la línea de hombros
    hl = np.exp(-((yy - 0.52) / 0.025) ** 2) * 70 + np.exp(-((yy - 0.20) / 0.05) ** 2) * 40
    col = np.clip(col + hl, 0, 255)
    g[..., :3] = col[:, None, :].repeat(w, 1) if col.ndim == 2 else col
    g[..., 3] = 255
    grad = Image.fromarray(g, "RGBA")
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    # parte baja más oscura (faldón)
    low = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(low).rectangle((0, 246 * k, w, h), fill=(0, 0, 0, 110))
    lowm = ImageChops.multiply(mask, Image.new("L", (w, h), 255))
    im.alpha_composite(Image.composite(low, Image.new("RGBA", (w, h), (0, 0, 0, 0)), lowm))
    d = ImageDraw.Draw(im)
    # cristales
    dlo = [(x * k + ox, y * k) for x, y in catmull(c["dlo"], 8, closed=True)]
    gm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gm).polygon(dlo, fill=255)
    glass = np.zeros((h, w, 4), np.uint8)
    gy = np.linspace(0, 1, h)[:, None]
    gc = np.array([30, 38, 48]) * (1 - gy) + np.array([8, 10, 14]) * gy
    glass[..., :3] = gc[:, None, :].repeat(w, 1)
    glass[..., 3] = 255
    gim = Image.fromarray(glass, "RGBA")
    # reflejo diagonal
    rd = ImageDraw.Draw(gim)
    for i, (x0, wd) in enumerate([(420, 60), (520, 26), (640, 40)]):
        rd.polygon([((x0) * k + ox, 40 * k), ((x0 + wd) * k + ox, 40 * k), ((x0 + wd - 80) * k + ox, 150 * k),
                    ((x0 - 80) * k + ox, 150 * k)], fill=(70, 84, 100, 255))
    im.paste(gim, (0, 0), gm)
    d = ImageDraw.Draw(im)
    # pilares
    b0, b1 = c["bpil"]
    d.polygon([(b0 * k + ox, 52 * k), (b1 * k + ox, 52 * k), (b1 * k + ox, 145 * k), (b0 * k + ox, 145 * k)],
              fill=(10, 12, 14, 255))
    # moldura cromada de ventanillas
    d.line(dlo + [dlo[0]], fill=(30, 32, 36, 255), width=4 * k)
    d.line([(c["dlo"][0][0] * k + ox, 143 * k), (c["dlo"][-1][0] * k + ox, 143 * k)], fill=(170, 176, 184, 255), width=2 * k)
    # juntas de puertas
    for sx in c["seams"]:
        d.line([(sx * k + ox, 146 * k), (sx * k + ox - 4 * k, 262 * k)], fill=(0, 0, 0, 140), width=2 * k)
    d.line([(c["seams"][0] * k + ox, 262 * k), (c["seams"][2] * k + ox, 262 * k)], fill=(0, 0, 0, 120), width=2 * k)
    # manillas
    for hx in c["handles"]:
        d.rounded_rectangle((hx * k + ox, 170 * k, (hx + 46) * k + ox, 180 * k), 5 * k, fill=(0, 0, 0, 90))
        d.rounded_rectangle((hx * k + ox, 168 * k, (hx + 46) * k + ox, 176 * k), 4 * k, fill=(220, 225, 232, 160))
    # retrovisor
    mx = c["dlo"][-1][0] - 26
    d.polygon([(mx * k + ox, 128 * k), ((mx + 44) * k + ox, 124 * k), ((mx + 50) * k + ox, 146 * k),
               ((mx + 4) * k + ox, 150 * k)], fill=tuple(int(v * 0.8) for v in c["top"]) + (255,))
    # faros y pilotos
    if c["lights"] == "audi":
        d.polygon([(930 * k + ox, 176 * k), (985 * k + ox, 190 * k), (992 * k + ox, 210 * k), (935 * k + ox, 202 * k)],
                  fill=(235, 240, 250, 255))
        d.polygon([(10 * k + ox, 190 * k), (52 * k + ox, 176 * k), (60 * k + ox, 204 * k), (12 * k + ox, 214 * k)],
                  fill=(210, 20, 30, 255))
        d.line([(16 * k + ox, 200 * k), (54 * k + ox, 192 * k)], fill=(255, 140, 60, 255), width=3 * k)
    else:
        for i, x0 in enumerate((936, 962)):  # doble faro redondo bajo el cristal
            d.ellipse((x0 * k + ox, 180 * k, (x0 + 24) * k + ox, 204 * k), fill=(240, 244, 255, 255))
        d.ellipse((934 * k + ox, 178 * k, 990 * k + ox, 206 * k), outline=(200, 205, 215, 255), width=2 * k)
        d.polygon([(10 * k + ox, 196 * k), (60 * k + ox, 180 * k), (70 * k + ox, 206 * k), (12 * k + ox, 216 * k)],
                  fill=(200, 18, 28, 255))
        d.line([(14 * k + ox, 206 * k), (64 * k + ox, 194 * k)], fill=(255, 90, 70, 255), width=3 * k)
    # interior de los pasos de rueda
    for x in wx:
        r = 84 * k
        d.chord((x * k + ox - r, 268 * k - r, x * k + ox + r, 268 * k + r), 180, 360, fill=(6, 7, 8, 255))
        d.arc((x * k + ox - r, 268 * k - r, x * k + ox + r, 268 * k + r), 185, 355,
              fill=tuple(min(255, v + 40) for v in c["top"]) + (255,), width=3 * k)
    # línea de carácter
    d.line([(60 * k + ox, 206 * k), (950 * k + ox, 200 * k)], fill=(255, 255, 255, 40), width=2 * k)
    return im.resize((w // k, h // k), Image.LANCZOS)


@lru_cache(maxsize=4)
def wheel_base(kind):
    k = 4
    r = 70
    sz = r * 2 * k + 8
    im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = sz / 2
    d.ellipse((c - r * k, c - r * k, c + r * k, c + r * k), fill=(16, 16, 18, 255))
    d.ellipse((c - (r - 6) * k, c - (r - 6) * k, c + (r - 6) * k, c + (r - 6) * k), outline=(40, 40, 44, 255), width=2 * k)
    rr = 48
    d.ellipse((c - rr * k, c - rr * k, c + rr * k, c + rr * k), fill=(48, 50, 54, 255))
    d.ellipse((c - 34 * k, c - 34 * k, c + 34 * k, c + 34 * k), outline=(75, 78, 82, 255), width=3 * k)  # disco
    n = CARS[kind]["spokes"]
    for i in range(n):
        a = 2 * math.pi * i / n
        for off in ((-0.09, 0.09) if kind == "audi" else (-0.16, -0.03, 0.03, 0.16)[::2]):
            pass
        offs = [0.0] if kind == "audi" else [-0.11, 0.11]
        for o in offs:
            aa = a + o
            wdt = 0.16 if kind == "audi" else 0.07
            p = [(c + math.cos(aa - wdt) * 10 * k, c + math.sin(aa - wdt) * 10 * k),
                 (c + math.cos(aa - wdt * 0.45) * 46 * k, c + math.sin(aa - wdt * 0.45) * 46 * k),
                 (c + math.cos(aa + wdt * 0.45) * 46 * k, c + math.sin(aa + wdt * 0.45) * 46 * k),
                 (c + math.cos(aa + wdt) * 10 * k, c + math.sin(aa + wdt) * 10 * k)]
            d.polygon(p, fill=(200, 206, 214, 255))
            d.line(p[:2], fill=(240, 244, 250, 255), width=k)
    d.ellipse((c - rr * k, c - rr * k, c + rr * k, c + rr * k), outline=(215, 220, 228, 255), width=3 * k)
    d.ellipse((c - 13 * k, c - 13 * k, c + 13 * k, c + 13 * k), fill=(170, 176, 184, 255))
    d.ellipse((c - 6 * k, c - 6 * k, c + 6 * k, c + 6 * k), fill=(40, 42, 46, 255))
    return im.resize((int(sz / k * 1.13), int(sz / k * 1.13)), Image.LANCZOS)


@lru_cache(maxsize=256)
def wheel_rot(kind, ang_q):
    return wheel_base(kind).rotate(ang_q * 4, Image.BICUBIC)


@lru_cache(maxsize=4)
def car_shadow():
    im = Image.new("RGBA", (1100, 120), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((60, 30, 1040, 90), fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(16))


def draw_car(f, kind, cx, cy, scale=0.9, travel=0.0, flip=False, a=1.0, sil=False, glow=None, bob=0.0):
    """cx, cy: centro de la carrocería. travel: distancia recorrida (gira las ruedas)."""
    body = car_body(kind, sil)
    c = CARS[kind]
    lay = Image.new("RGBA", (body.width, body.height + 30), (0, 0, 0, 0))
    lay.alpha_composite(car_shadow().resize((body.width, 80)), (0, body.height - 70))
    ang = (-travel / 70 * 180 / math.pi) % 360
    for x in c["wheels"]:
        wim = wheel_rot(kind, int(ang / 4) % 90) if not sil else None
        if wim is not None:
            lay.alpha_composite(wim, (int(x + 20 - wim.width / 2), int(268 - wim.height / 2)))
    lay.alpha_composite(body, (0, int(bob)))
    if sil:
        for x in c["wheels"]:
            pass
    if flip:
        lay = lay.transpose(Image.FLIP_LEFT_RIGHT)
    if glow:
        gl = Image.new("RGBA", lay.size, glow + (0,))
        gl.putalpha(lay.getchannel("A").filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.8)))
        lay2 = Image.new("RGBA", (lay.width + 80, lay.height + 80), (0, 0, 0, 0))
        lay2.alpha_composite(gl, (40, 40))
        lay2.alpha_composite(lay, (40, 40))
        lay = lay2
    put(f, lay, cx, cy, scale, a)


# ============================================================ circuito
TRACK_PTS = [(0.62, 0.93), (0.40, 0.96), (0.22, 0.90), (0.10, 0.80), (0.13, 0.69), (0.05, 0.58), (0.10, 0.46),
             (0.21, 0.41), (0.17, 0.30), (0.26, 0.19), (0.37, 0.11), (0.48, 0.04), (0.57, 0.10), (0.52, 0.20),
             (0.61, 0.27), (0.73, 0.22), (0.81, 0.31), (0.75, 0.41), (0.86, 0.46), (0.95, 0.57), (0.88, 0.66),
             (0.79, 0.61), (0.73, 0.69), (0.83, 0.78), (0.79, 0.87)]


@lru_cache(maxsize=4)
def track_path(size):
    pts = catmull(TRACK_PTS, 16)
    m = 0.08 * size
    P = [(m + x * (size - 2 * m), m + y * (size - 2 * m)) for x, y in pts]
    L = [0.0]
    for i in range(1, len(P)):
        L.append(L[-1] + math.dist(P[i], P[i - 1]))
    return P, L


@lru_cache(maxsize=8)
def track_full(size, col):
    P, _ = track_path(size)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line(P + [P[0]], fill=col + (255,), width=int(size * 0.03), joint="curve")
    glow = im.filter(ImageFilter.GaussianBlur(size * 0.025))
    core = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(core)
    cd.line(P + [P[0]], fill=col + (255,), width=int(size * 0.014), joint="curve")
    cd.line(P + [P[0]], fill=(240, 255, 245, 255), width=max(2, int(size * 0.004)), joint="curve")
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(core)
    return out


@lru_cache(maxsize=4)
def track_ghost(size):
    P, _ = track_path(size)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).line(P + [P[0]], fill=(255, 255, 255, 40), width=int(size * 0.014), joint="curve")
    return im


def draw_track(f, cx, cy, size, p, col=GREEN, dot=True, a=1.0, ghost=True, t=0.0, rot=0.0):
    P, L = track_path(size)
    full = track_full(size, col)
    lay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if ghost:
        lay.alpha_composite(track_ghost(size))
    if p >= 0.999:
        lay.alpha_composite(full)
        idx = int((t * 0.08 % 1) * len(P))
    else:
        tot = L[-1] * p
        idx = 0
        while idx < len(L) - 1 and L[idx] < tot:
            idx += 1
        m = Image.new("L", (size, size), 0)
        if idx > 1:
            ImageDraw.Draw(m).line(P[: idx + 1], fill=255, width=int(size * 0.09), joint="curve")
        part = full.copy()
        part.putalpha(ImageChops.multiply(full.getchannel("A"), m))
        lay.alpha_composite(part)
    if dot and p > 0.01:
        x, y = P[min(idx, len(P) - 1)]
        d = ImageDraw.Draw(lay)
        for r, al in ((26, 50), (16, 110), (8, 255)):
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, al) if r == 8 else col + (al,))
    put(f, lay, cx, cy, 1.0, a, rot=rot)


# ============================================================ elementos
@lru_cache(maxsize=16)
def glass_card(w, h, col=(255, 255, 255), border=None, r=34):
    im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((30, 42, 30 + w, 42 + h), r, fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((30, 30, 30 + w, 30 + h), r, fill=(18, 24, 26, 225), outline=(border or (60, 70, 74)) + (255,),
                        width=3)
    d.rounded_rectangle((32, 32, 28 + w, 30 + h * 0.45), r, fill=(255, 255, 255, 8))
    return im


@lru_cache(maxsize=32)
def letter_badge(letter, col, size=260):
    im = Image.new("RGBA", (size + 120, size + 120), (0, 0, 0, 0))
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle((60, 60, 60 + size, 60 + size), size // 5, fill=col + (255,))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((60, 60, 60 + size, 60 + size), size // 5, fill=col + (255,))
    d.rounded_rectangle((60 + 10, 60 + 10, 60 + size - 10, 60 + size * 0.5), size // 6, fill=(255, 255, 255, 30))
    f = font("black", int(size * 0.78))
    tw = f.getlength(letter)
    asc, desc = f.getmetrics()
    d.text((60 + size / 2 - tw / 2, 60 + size / 2 - (asc + desc) / 2 + size * 0.02), letter, font=f, fill=(255, 255, 255, 255))
    return im


def hazard(f, y, h, t, a=1.0):
    lay = Image.new("RGBA", (W + 200, h), GOLD + (255,))
    d = ImageDraw.Draw(lay)
    off = int(t * 160) % 80
    for x in range(-200, W + 400, 80):
        d.polygon([(x + off, 0), (x + 40 + off, 0), (x + off - h + 40, h), (x + off - h, h)], fill=(15, 15, 15, 255))
    put(f, lay.crop((100, 0, 100 + W, h)), W / 2, y, 1, a)


def check_icon(size, col, p):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, size - 2, size - 2), size // 4, outline=col + (255,), width=5,
                        fill=col + (int(255 * p),) if p > 0 else None)
    if p > 0:
        pts = [(size * 0.24, size * 0.52), (size * 0.43, size * 0.70), (size * 0.78, size * 0.30)]
        q = e_out(p)
        if q < 0.5:
            e = (lerp(pts[0][0], pts[1][0], q * 2), lerp(pts[0][1], pts[1][1], q * 2))
            d.line([pts[0], e], fill=(0, 0, 0, 255), width=9)
        else:
            e = (lerp(pts[1][0], pts[2][0], (q - 0.5) * 2), lerp(pts[1][1], pts[2][1], (q - 0.5) * 2))
            d.line([pts[0], pts[1], e], fill=(0, 0, 0, 255), width=9, joint="curve")
    return im


AVAT = [(random.Random(i).random(), random.Random(i + 99).random(), random.Random(i + 199).random()) for i in range(40)]


@lru_cache(maxsize=64)
def avatar(i, size=86):
    a, b, c = AVAT[i % len(AVAT)]
    cols = [GREEN, RED, BLUE, GOLD, (190, 90, 255), (255, 130, 40), (0, 210, 220)]
    col = cols[int(a * len(cols))]
    im = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=mix((20, 24, 26), col, 0.55) + (255,), outline=col + (255,), width=6)
    d.ellipse((size * 0.62, size * 0.38, size * 1.38, size * 1.14), fill=(235, 238, 242, 255))
    d.chord((size * 0.34, size * 1.2, size * 1.66, size * 2.5), 180, 360, fill=(235, 238, 242, 255))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=255)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), m))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size * 2 - 1, size * 2 - 1), outline=col + (255,), width=6)
    return im.resize((size, size), Image.LANCZOS)


USERS = ["@piloto_88", "@ringlover", "@quattro_fan", "@e46_drift", "@laura.racing", "@mecanico_pro",
         "@vroom_vroom", "@infierno_verde", "@daniel_gt", "@track_day", "@carlos_m3", "@sofi.motor"]


@lru_cache(maxsize=64)
def comment(i, letter, text):
    col = RED if letter == "A" else BLUE
    w, h = 760, 150
    im = glass_card(w, h, border=col).copy()
    im.alpha_composite(avatar(i, 84), (30 + 26, 30 + 33))
    d = ImageDraw.Draw(im)
    d.text((30 + 130, 30 + 26), USERS[i % len(USERS)], font=font("semi", 30), fill=GREY + (255,))
    d.text((30 + 130, 30 + 70), text, font=font("black", 44), fill=WHITE + (255,))
    b = letter_badge(letter, col, 80)
    im.alpha_composite(b, (30 + w - 140, 30 + 35 - 60 + 0))
    return im


def stat_bar(f, x, y, w, label, val, p, col, t0, t):
    if t < t0:
        return
    q = e_out(prog(t, t0, 0.6))
    a = clamp(prog(t, t0, 0.2))
    put(f, txt(label, 40, WHITE, "black", 0, 0, (0, 0, 0), 2), x, y - 36, 1, a, anchor="l")
    d = ImageDraw.Draw(f)
    d.rounded_rectangle((x, y, x + w, y + 22), 11, fill=(34, 40, 44))
    if q > 0.02:
        d.rounded_rectangle((x, y, x + w * val * q, y + 22), 11, fill=col)
        d.rounded_rectangle((x, y, x + w * val * q, y + 8), 4, fill=mix(col, WHITE, 0.4))
    put(f, txt(f"{int(val * 100 * q)}", 40, col, "mono"), x + w, y - 36, 1, a, anchor="r")


def flash(f, a, col=(255, 255, 255)):
    if a > 0.01:
        f.alpha_composite(Image.new("RGBA", (W, H), col + (int(255 * clamp(a)),)))


def strike(f, x0, x1, y, p, col=RED, w=14):
    if p > 0:
        ImageDraw.Draw(f).line((x0, y, lerp(x0, x1, e_out(p)), y - 10 * e_out(p)), fill=col, width=w)


def glitch_text(f, t, img, x, y, amt):
    if amt <= 0.01:
        put(f, img, x, y)
        return
    r = random.Random(int(t * 30))
    off = int(amt * 18)
    rch = img.copy()
    rch.putalpha(rch.getchannel("A").point(lambda v: v // 2))
    put(f, Image.merge("RGBA", (rch.getchannel("R"), Image.new("L", rch.size, 0), Image.new("L", rch.size, 0),
                                rch.getchannel("A"))), x - off, y)
    put(f, Image.merge("RGBA", (Image.new("L", rch.size, 0), rch.getchannel("G"), rch.getchannel("B"),
                                rch.getchannel("A"))), x + off, y)
    # rebanadas desplazadas
    base = img.copy()
    for _ in range(int(3 * amt) + 1):
        y0 = r.randint(0, base.height - 10)
        hh = r.randint(6, 30)
        sl = base.crop((0, y0, base.width, min(base.height, y0 + hh)))
        base.paste((0, 0, 0, 0), (0, y0, base.width, min(base.height, y0 + hh)))
        base.paste(sl, (r.randint(-30, 30), y0))
    put(f, base, x + r.randint(-6, 6) * amt, y)


CONF = [(random.Random(i).random(), random.Random(i + 7).random(), random.Random(i + 17).random(),
         random.Random(i + 27).random()) for i in range(120)]


def confetti(f, t, t0, cols=(GREEN, RED, BLUE, GOLD, WHITE)):
    dt = t - t0
    if dt < 0 or dt > 3.5:
        return
    d = ImageDraw.Draw(f)
    for i, (a, b, c, e) in enumerate(CONF):
        ang = -math.pi / 2 + (a - 0.5) * 2.4
        v = 900 + 1500 * b
        x = W / 2 + math.cos(ang) * v * dt
        y = 900 + math.sin(ang) * v * dt + 1400 * dt * dt
        if y > H + 20:
            continue
        rot = dt * (6 + 10 * c) + e * 6
        s = 10 + 12 * c
        pts = [(x + math.cos(rot + q) * s, y + math.sin(rot + q) * s * 0.5) for q in (0, 1.9, math.pi, math.pi + 1.9)]
        d.polygon(pts, fill=cols[i % len(cols)])


# ============================================================ subtítulos
def load_words():
    w = json.load(open(os.path.join(AQUI, "palabras.json")))
    fix = {"Nurburgring.": "Nürburgring.", "Nurburgring,": "Nürburgring,", "Nurburgring?": "Nürburgring?",
           "jugemos": "juguemos", "¿Legaremos": "¿Llegaremos", "Decidís": "¡Decidís", "vosotros.": "vosotros.",
           "Pero,": "Pero…"}
    out = []
    for a, b, s in w:
        if s == "Título.":
            continue
        if s == "opción." and 49 < a < 50:
            out += [[a, 49.74, "opción"], [49.76, 50.2, "A."]]
            continue
        s = fix.get(s, s)
        out.append([a, b, s])
    for x in out:
        if x[2] == "vosotros." and 83 < x[0] < 84:
            x[2] = "vosotros!"
        if x[2] == "Nürburgring." and 14 < x[0] < 15:
            x[2] = "¡Nürburgring!"
        if x[2] == "Empieza":
            x[2] = "¡Empieza"
        if x[2] == "proyecto." and x[0] > 121:
            x[2] = "proyecto!"
    return out


def chunks(words):
    """Agrupa en bloques de ≤3 palabras, cortando en pausas y puntuación."""
    res, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = (len(cur) >= 3 or w[2][-1] in ".,?!…" or nxt is None or nxt[0] - w[1] > 0.35
               or sum(len(x[2]) for x in cur) > 16)
        if end:
            res.append(cur)
            cur = []
    return res


WORDS = load_words()
CHUNKS = chunks(WORDS)


def subtitles(f, t, y=1610, hide=()):
    for a, b in hide:
        if a <= t < b:
            return
    for i, ch in enumerate(CHUNKS):
        t0 = ch[0][0]
        t1 = ch[-1][1] + 0.25
        if i + 1 < len(CHUNKS):
            t1 = min(t1 + 0.3, CHUNKS[i + 1][0][0])
        if not (t0 - 0.05 <= t < t1):
            continue
        size = 74
        imgs = []
        for w in ch:
            act = w[0] - 0.03 <= t
            cur = act and (t < w[1] + 0.05 or w is ch[-1])
            col = GREEN if cur else WHITE if act else (200, 205, 210)
            imgs.append((txt(w[2].upper(), size, col, "black", 0, 7, (0, 0, 0), 0, 0, True), cur, w))
        gap = 18
        tw = sum(im.width - 32 for im, _, _ in imgs) + gap * (len(imgs) - 1)
        s0 = 1.0
        if tw > 1000:
            s0 = 1000 / tw
        x = W / 2 - tw * s0 / 2
        pin = e_back(prog(t, t0 - 0.05, 0.16))
        for im, cur, w in imgs:
            ww = (im.width - 32) * s0
            sc = s0 * (0.85 + 0.15 * pin)
            if cur:
                sc *= 1 + 0.08 * (1 - prog(t, w[0], 0.15))
            put(f, im, x + ww / 2, y, sc, clamp(pin * 2))
            x += ww + gap * s0
        return


# ============================================================ HUD
def hud(f, t):
    if t < 7.6:
        return
    a = clamp(prog(t, 7.6, 0.5))
    d = ImageDraw.Draw(f)
    m = 46
    L = 60
    c = mix(DARK, WHITE, 0.55 * a)
    for (x, y, sx, sy) in ((m, m + 40, 1, 1), (W - m, m + 40, -1, 1), (m, H - m - 60, 1, -1), (W - m, H - m - 60, -1, -1)):
        d.line((x, y, x + L * sx, y), fill=c, width=4)
        d.line((x, y, x, y + L * sy), fill=c, width=4)
    put(f, txt("PROYECTO NÜRBURGRING", 30, WHITE, "mono", 0, 0, (0, 0, 0), 3), m + 26, 150, 1, a * 0.9, anchor="l")
    # contador de días: el reto aún no ha empezado
    day = "DÍA 00/30" if t < 121.08 else "DÍA 01/30"
    put(f, txt(day, 30, GREEN, "mono", 0, 0, (0, 0, 0), 3), W - m - 26, 150, 1, a, anchor="r")
    # barra de progreso del vídeo
    d.rounded_rectangle((m + 26, 186, W - m - 26, 192), 3, fill=mix(DARK, WHITE, 0.15 * a))
    d.rounded_rectangle((m + 26, 186, m + 26 + (W - 2 * m - 52) * clamp(t / 122.1), 192), 3, fill=mix(DARK, GREEN, a))
    # punto REC parpadeante
    if int(t * 2) % 2 == 0:
        d.ellipse((m + 2, 140, m + 18, 156), fill=mix(DARK, RED, a))


# ============================================================ escenas
CUTS = [0, 7.7, 11.2, 15.1, 22.6, 29.8, 32.6, 38.0, 43.9, 48.1, 64.6, 76.1, 81.0, 92.0, 100.2, 108.4, 114.3, 121.0, DUR]


def sc_titulo(f, t):
    put(f, bg_image((20, 120, 70)), W / 2, H / 2)
    draw_track(f, W / 2, 940, 1000, 1.0, (20, 90, 55), dot=False, a=0.35 + 0.1 * math.sin(t), ghost=False,
               rot=t * 2 - 8)
    particles(f, t, GREEN, 0.6)
    put(f, chip("EPISODIO 1", GREEN, 36), W / 2, 330, 0.6 + 0.4 * e_back(prog(t, 0.05, 0.4)), clamp(prog(t, 0.05, 0.2)))
    out = 3.75
    T(f, t, 0.92, "TENGO", 92, 520, anim="up", t1=out)
    T(f, t, 1.28, "30 DÍAS", 240, 690, GREEN, glow=18, anim="slam", t1=out)
    T(f, t, 2.06, "PARA LLEGAR A", 84, 860, anim="up", t1=out)
    T(f, t, 2.8, "NÜRBURGRING", 150, 1000, WHITE, "ital", anim="slam", t1=out, glow=6)
    flash(f, 0.6 * (1 - prog(t, 2.8, 0.25)) if t >= 2.8 else 0)
    T(f, t, 3.86, "…Y VOSOTROS", 120, 560, anim="up")
    T(f, t, 4.64, "VAIS A ELEGIR", 120, 700, anim="up")
    T(f, t, 5.44, "EL COCHE", 210, 880, RED, "ital", anim="slam", glow=14)
    if t > 5.3:
        p = e_out(prog(t, 5.3, 0.7))
        draw_car(f, "audi", lerp(-500, 290, p), 1250, 0.5, travel=p * 800 + t * 300, sil=True)
        draw_car(f, "bmw", lerp(W + 500, W - 290, p), 1250, 0.5, travel=p * 800 + t * 300, sil=True, flip=True)
        for xx in (290, W - 290):
            T(f, t, 5.7 if xx < 500 else 5.85, "?", 170, 1205, GOLD, anim="pop", x=xx, glow=10)


def sc_30(f, t):
    put(f, bg_image((20, 140, 80)), W / 2, H / 2)
    grid_floor(f, t, GREEN, 1.4)
    particles(f, t, GREEN)
    lt = t - 7.7
    n = int(clamp((t - 7.88) / 0.68) * 30)
    # anillo de progreso
    d = ImageDraw.Draw(f)
    cx, cy, r = W / 2, 760, 330
    pr = e_out(prog(t, 7.75, 0.4))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=mix(DARK, WHITE, 0.12 * pr), width=18)
    if n > 0:
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * n / 30, fill=GREEN, width=18)
    for k in range(30):
        a = -math.pi / 2 + k / 30 * 2 * math.pi
        c = GREEN if k < n else mix(DARK, WHITE, 0.3)
        d.line((cx + math.cos(a) * (r + 30), cy + math.sin(a) * (r + 30), cx + math.cos(a) * (r + 48),
                cy + math.sin(a) * (r + 48)), fill=c, width=6)
    s = 1 + 0.12 * (1 - prog(t, 8.56, 0.25)) if t > 8.56 else 1
    put(f, txt(str(n), 330, GREEN if n == 30 else WHITE, "black", 20 if n == 30 else 0), cx, cy - 30, s * pr)
    T(f, t, 8.3, "DÍAS", 80, cy + 150, WHITE, track=14, anim="up")
    T(f, t, 9.2, "PARA PREPARAR", 74, 1260, anim="up")
    T(f, t, 9.6, "UN COCHE", 130, 1380, GOLD, "ital", anim="slam", glow=8)


def sc_track(f, t):
    put(f, bg_image((20, 160, 90)), W / 2, H / 2)
    particles(f, t, GREEN)
    p = e_io(prog(t, 11.2, 2.8))
    shake = 0
    draw_track(f, W / 2, 900, 920, p, GREEN, t=t, rot=lerp(-12, 0, e_out(prog(t, 11.2, 3))))
    T(f, t, 11.25, "UNO DE LOS CIRCUITOS", 70, 330, anim="up", t1=14.0)
    T(f, t, 12.02, "MÁS LOCOS", 150, 470, RED, "ital", anim="slam", t1=14.0, glow=10)
    T(f, t, 12.9, "DEL MUNDO", 70, 600, anim="up", t1=14.0)
    if t >= 14.12:
        T(f, t, 14.12, "NÜRBURGRING", 160, 420, WHITE, "ital", anim="slam", glow=10)
        T(f, t, 14.3, "NORDSCHLEIFE · 20,8 KM", 40, 540, GREEN, "mono", anim="fade", track=4)
        flash(f, 0.8 * (1 - prog(t, 14.12, 0.3)))


def sc_problema(f, t):
    put(f, bg_image((160, 30, 30)), W / 2, H / 2)
    particles(f, t, RED, 0.5)
    if t < 17.2:
        hz = e_out(prog(t, 15.15, 0.4))
        hazard(f, 330, 70, t, hz)
        hazard(f, 1380, 70, -t, hz)
        T(f, t, 15.18, "PERO…", 120, 650, anim="up")
        if t >= 15.86:
            g = 1 - prog(t, 15.86, 0.5) + (0.6 if 16.3 < t < 16.45 else 0)
            img = txt("HAY UN\nPROBLEMA", 170, RED, "ital", 14)
            s = lerp(1.6, 1, e_out(prog(t, 15.86, 0.2)))
            q = img.resize((int(img.width * s), int(img.height * s)), Image.BILINEAR) if s != 1 else img
            glitch_text(f, t, q, W / 2, 960, g)
            # señal de peligro
            pp = e_back(prog(t, 16.2, 0.4))
            if pp > 0:
                tri = Image.new("RGBA", (220, 200), (0, 0, 0, 0))
                ImageDraw.Draw(tri).polygon([(110, 6), (214, 194), (6, 194)], fill=GOLD + (255,))
                ImageDraw.Draw(tri).text((88, 52), "!", font=font("black", 120), fill=(0, 0, 0, 255))
                put(f, tri, W / 2, 1230, pp * 0.9)
    elif t < 20.6:
        T(f, t, 17.26, "TODAVÍA NO SÉ", 80, 380, anim="up")
        T(f, t, 18.8, "¿QUÉ COCHE?", 160, 520, GOLD, "ital", anim="slam", glow=10)
        for i, (kind, y) in enumerate((("audi", 860), ("bmw", 1200))):
            p = e_out(prog(t, 17.4 + i * 0.2, 0.6))
            jit = math.sin(t * 40 + i) * 3 if t > 18.8 else 0
            draw_car(f, kind, lerp(-600 if i == 0 else W + 600, W / 2, p) + jit, y, 0.82, travel=t * 400, sil=True,
                     flip=i == 1)
            T(f, t, 18.9 + i * 0.12, "?", 200, y - 20, GOLD, anim="pop", glow=12)
        if t > 19.2:
            st = chip("SIN DECIDIR", RED, 48, WHITE)
            put(f, st, W / 2, 1030, lerp(2.0, 1, e_out(prog(t, 19.2, 0.15))), clamp(prog(t, 19.2, 0.1)), rot=-6)
    else:
        T(f, t, 20.7, "Y LO VAIS A ELEGIR", 84, 560, anim="up")
        T(f, t, 21.76, "VOSOTROS", 190, 720, GREEN, "ital", anim="slam", glow=16)
        for i, (k, c) in enumerate((("A", RED), ("B", BLUE))):
            p = e_back(prog(t, 21.0 + i * 0.15, 0.5))
            put(f, letter_badge(k, c, 220), W / 2 + (-210 if i == 0 else 210), 1100, p)
        T(f, t, 21.3, "VS", 90, 1100, WHITE, "ital", anim="pop")
        draw_track(f, W / 2, 1100, 520, 1.0, (40, 70, 50), dot=False, a=0.3, ghost=False)


def sc_diferente(f, t):
    put(f, bg_image((30, 110, 90)), W / 2, H / 2)
    particles(f, t, GREEN, 0.6)
    T(f, t, 22.9, "QUIERO HACER", 74, 360, anim="up")
    T(f, t, 23.42, "ALGO DIFERENTE", 130, 480, GREEN, "ital", anim="slam", glow=10)
    # calendario de 30 días
    if t >= 24.6:
        cx, cy = W / 2, 1010
        card = glass_card(860, 640)
        put(f, card, cx, cy, 0.8 + 0.2 * e_back(prog(t, 24.6, 0.4)), clamp(prog(t, 24.6, 0.2)))
        if t > 24.75:
            put(f, txt("30 DÍAS · RETO", 40, GREY, "mono", 0, 0, (0, 0, 0), 4), cx, cy - 250, 1)
            d = ImageDraw.Draw(f)
            for k in range(30):
                tk = 24.8 + k * 0.055
                if t < tk:
                    continue
                r, c = divmod(k, 6)
                x = cx - 330 + c * 132
                y = cy - 170 + r * 100
                p = e_back(prog(t, tk, 0.25))
                hl = 26.0 < t and k == int(((t - 26.0) * 6) % 30)
                col = GREEN if k == 29 else (40, 52, 56)
                if hl:
                    col = mix(col, GREEN, 0.6)
                s = 54 * p
                d.rounded_rectangle((x + 58 - s, y + 40 - s * 0.72, x + 58 + s, y + 40 + s * 0.72), 12, fill=col)
                put(f, txt(str(k + 1), 34, (0, 0, 0) if k == 29 else WHITE, "bold", 0, 0, (0, 0, 0), 0, 0, False),
                    x + 58, y + 40, p)
        T(f, t, 27.14, "PREPARAR UN COCHE", 62, 1440, anim="up", t1=28.4)
        T(f, t, 28.54, "PARA ENFRENTARME AL MÍTICO…", 54, 1440, GOLD, anim="up")


def sc_infierno(f, t):
    put(f, bg_image((0, 255, 120)), W / 2, H / 2)
    particles(f, t, GREEN, 1.0)
    grid_floor(f, t, GREEN, 0.8, 1300, 0.7)
    p = e_out(prog(t, 29.8, 1.4))
    draw_track(f, W / 2, 950, 860, p, GREEN, t=t)
    T(f, t, 29.9, "NÜRBURGRING", 150, 360, WHITE, "ital", anim="slam", glow=8)
    flash(f, 0.7 * (1 - prog(t, 29.9, 0.3)), GREEN)
    if t > 30.96:
        T(f, t, 30.96, "EL INFIERNO", 120, 1420, GREEN, "ital", anim="up", glow=20)
        T(f, t, 31.4, "VERDE", 200, 1600 - 20, GREEN, "ital", anim="slam", glow=26)


def sc_solo(f, t):
    put(f, bg_image((60, 90, 140)), W / 2, H / 2)
    particles(f, t, BLUE, 0.5)
    if t < 34.3:
        T(f, t, 32.82, "NO QUIERO", 110, 760, anim="up")
        T(f, t, 33.3, "HACERLO", 110, 890, anim="up")
        T(f, t, 33.6, "SOLO", 240, 1070, RED, "ital", anim="slam", glow=10)
        strike(f, 300, 790, 1080, prog(t, 33.95, 0.25), WHITE, 18)
        # un único avatar solitario
        put(f, avatar(0, 140), W / 2, 500, e_back(prog(t, 32.9, 0.4)))
    else:
        # muchos avatares = la comunidad
        T(f, t, 34.42, "VOSOTROS", 160, 420, GREEN, "ital", anim="slam", glow=10)
        T(f, t, 35.22, "DECIDÍS CONMIGO", 84, 560, anim="up")
        T(f, t, 36.22, "CADA PASO", 140, 1380, GOLD, "ital", anim="slam", glow=8)
        T(f, t, 36.98, "DEL PROYECTO", 70, 1500, anim="up")
        for i in range(34):
            a, b, c = AVAT[i]
            ang = i * 2.399
            rad = 90 + 55 * math.sqrt(i) * 1.15
            x = W / 2 + math.cos(ang + t * 0.15) * rad
            y = 960 + math.sin(ang + t * 0.15) * rad * 0.62
            tk = 34.5 + i * 0.05
            p = e_back(prog(t, tk, 0.4))
            put(f, avatar(i, 70 + int(c * 40)), x, y, p)


def sc_checklist(f, t):
    put(f, bg_image((20, 120, 80)), W / 2, H / 2)
    particles(f, t, GREEN, 0.5)
    T(f, t, 38.0, "VOSOTROS DECIDÍS:", 70, 360, GREEN, track=2, anim="up")
    cx = W / 2
    put(f, glass_card(900, 820), cx, 900, 0.85 + 0.15 * e_out(prog(t, 38.0, 0.4)), clamp(prog(t, 38.0, 0.25)))
    items = [(38.28, "EL COCHE"), (39.18, "LAS MODIFICACIONES"), (40.44, "LAS MEJORAS"), (41.34, "TODO LO QUE HAGA FALTA")]
    for i, (tk, label) in enumerate(items):
        y = 620 + i * 185
        if t < tk - 0.2:
            continue
        a = clamp(prog(t, tk - 0.2, 0.25))
        dx = (1 - e_out(prog(t, tk - 0.2, 0.35))) * 120
        put(f, check_icon(96, GREEN, prog(t, tk + 0.15, 0.35)), 190 + dx, y, 1, a)
        put(f, txt(label, 58, WHITE, "black", 0, 0, (0, 0, 0), 0, 640), 270 + dx, y, 1, a, anchor="l")
        if i < 3:
            ImageDraw.Draw(f).line((160, y + 92, W - 160, y + 92), fill=(40, 50, 54), width=2)
    T(f, t, 42.46, "PARA LLEGAR HASTA ALLÍ", 64, 1440, GOLD, anim="up")
    if t > 42.8:
        # bandera a cuadros
        p = e_back(prog(t, 42.8, 0.4))
        fl = Image.new("RGBA", (160, 110), (0, 0, 0, 0))
        dd = ImageDraw.Draw(fl)
        for r in range(4):
            for c in range(6):
                dd.rectangle((c * 26, r * 26, c * 26 + 25, r * 26 + 25), fill=(WHITE if (r + c) % 2 else (10, 10, 10)) + (255,))
        put(f, fl, W / 2, 1300, p, rot=math.sin(t * 6) * 6)


def sc_hoy(f, t):
    put(f, bg_image((180, 140, 20)), W / 2, H / 2)
    speed_lines(f, t, GOLD, -1, (300, 1600), 0.7)
    if t < 46.0:
        T(f, t, 44.02, "Y HOY", 110, 700, anim="up")
        T(f, t, 44.42, "EMPIEZA", 190, 880, GOLD, "ital", anim="slam", glow=12)
        T(f, t, 45.24, "TODO", 260, 1090, WHITE, "ital", anim="slam", glow=6)
    else:
        T(f, t, 46.12, "TENEMOS", 90, 470, anim="up")
        T(f, t, 46.52, "2", 380, 720, GOLD, "ital", anim="slam", glow=20)
        T(f, t, 46.96, "CANDIDATOS", 120, 950, anim="up")
        for i, (k, c) in enumerate((("A", RED), ("B", BLUE))):
            p = e_out(prog(t, 46.6 + i * 0.12, 0.5))
            x = lerp(-300 if i == 0 else W + 300, W / 2 + (-220 if i == 0 else 220), p)
            put(f, letter_badge(k, c, 240), x, 1260, 1, rot=math.sin(t * 3 + i) * 4)


def option_scene(f, t, kind, t0, letter, col, tint, stats, chips, special_t, flip):
    put(f, bg_image(tint), W / 2, H / 2)
    c = CARS[kind]
    grid_floor(f, t, col, 1.8, 1180, 0.6)
    dirx = 1 if flip else -1
    speed_lines(f, t, col, dirx, (700, 1150), 0.8, 1.2)
    # cabecera
    T(f, t, t0, "OPCIÓN", 80, 330, anim="up", track=10)
    tb = t0 + (1.56 if letter == "A" else 1.1)
    if t >= tb:
        p = prog(t, tb, 0.22)
        put(f, letter_badge(letter, col, 230), W / 2, 520, lerp(2.5, 1, e_out(p)), clamp(p * 2))
        flash(f, 0.5 * (1 - prog(t, tb, 0.25)), col)
    # coche
    pe = e_out(prog(t, t0 + 0.4, 1.3))
    start = -700 if not flip else W + 700
    x = lerp(start, W / 2, pe)
    bob = math.sin(t * 9) * 1.2
    spec = special_t is not None and t > special_t
    draw_car(f, kind, x, 960, 0.98, travel=t * 520 + pe * 1600, flip=flip, glow=col if spec else None, bob=bob)
    if spec:
        # destellos alrededor del coche
        d = ImageDraw.Draw(f)
        for i in range(10):
            a, b, cc = AVAT[i + 5]
            ph = (t * 1.5 + a) % 1
            sx, sy = W / 2 + (a - 0.5) * 900, 860 + (b - 0.5) * 300
            s = 26 * math.sin(ph * math.pi)
            d.polygon([(sx, sy - s), (sx + s * 0.25, sy), (sx, sy + s), (sx - s * 0.25, sy)], fill=WHITE)
            d.polygon([(sx - s, sy), (sx, sy + s * 0.25), (sx + s, sy), (sx, sy - s * 0.25)], fill=WHITE)
    # nombre
    tn = t0 + 1.9
    T(f, t, tn, c["name"], 110, 1210, WHITE, "ital", anim="left" if not flip else "right", glow=0)
    T(f, t, tn + 0.15, c["sub"], 38, 1300, col, "mono", anim="fade", track=4)
    # estadísticas (las dos últimas) o, al final, una etiqueta grande
    act_chips = [ch for ch in chips if t >= ch[0]]
    if not act_chips:
        act = [s for s in stats if t >= s[0]][-2:]
        for i, (tk, label, val) in enumerate(act):
            y = 1400 + (i if len(act) == 2 else 0) * 110
            stat_bar(f, 160, y, 760, label, val, 0, col, tk, t)
    else:
        tk, label, ccol = act_chips[-1]
        p = e_back(prog(t, tk, 0.35))
        fg = (0, 0, 0) if ccol in (GOLD, GREEN, WHITE) else WHITE
        put(f, chip(label, ccol, 52, fg), W / 2, 1440, p)


def sc_a(f, t):
    stats = [(51.32, "CARÁCTER", 0.86), (52.32, "BUENA BASE", 0.80), (54.44, "POTENCIAL", 0.95),
             (57.18, "MÁQUINA DE CIRCUITO", 0.90)]
    chips = [(59.36, "NECESITA TRABAJO", GOLD), (61.46, "HAY QUE INVERTIR $", RED), (63.26, "TIENE ALGO ESPECIAL", GREEN)]
    option_scene(f, t, "audi", 48.24, "A", RED, (200, 30, 40), stats, chips, 63.2, False)


def sc_b(f, t):
    stats = [(67.62, "PROPUESTA DIFERENTE", 0.88), (70.54, "PERSONALIDAD", 0.90), (71.84, "POSIBILIDADES", 0.92),
             (74.26, "FACTOR SORPRESA", 0.97)]
    option_scene(f, t, "bmw", 64.88, "B", BLUE, (30, 90, 220), stats, [(999, "", WHITE)], None, True)


def sc_vs(f, t):
    put(f, bg_image((60, 60, 60)), W / 2, H / 2)
    p = e_out(prog(t, 76.1, 0.5))
    # mitades diagonales
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.polygon([(0, 0), (W, 0), (W, 900 - 120), (0, 900 + 120)], fill=mix(DARK, RED, 0.28) + (int(255 * p),))
    d.polygon([(0, 1020 + 120), (W, 1020 - 120), (W, H), (0, H)], fill=mix(DARK, BLUE, 0.28) + (int(255 * p),))
    f.alpha_composite(lay)
    speed_lines(f, t, RED, -1, (560, 860), 0.6)
    speed_lines(f, t + 3, BLUE, 1, (1080, 1380), 0.6)
    draw_car(f, "audi", lerp(-600, 470, e_out(prog(t, 76.15, 0.8))), 720, 0.8, travel=t * 500)
    draw_car(f, "bmw", lerp(W + 600, W - 470, e_out(prog(t, 76.25, 0.8))), 1240, 0.8, travel=t * 500, flip=True)
    put(f, chip("A · AUDI A6", RED, 40, WHITE), 240, 560, e_back(prog(t, 76.6, 0.3)))
    put(f, chip("B · BMW E46", BLUE, 40, WHITE), W - 240, 1430, e_back(prog(t, 76.7, 0.3)))
    # rayo VS
    if t > 76.3:
        q = prog(t, 76.3, 0.25)
        d = ImageDraw.Draw(f)
        r = random.Random(int(t * 20))
        pts = [(0, 960 + 120)]
        for k in range(1, 8):
            pts.append((W * k / 8, 960 + 120 - 240 * k / 8 + r.randint(-30, 30)))
        pts.append((W, 960 - 120))
        d.line(pts, fill=WHITE, width=8)
        d.line(pts, fill=GOLD, width=3)
        put(f, txt("VS", 230, WHITE, "ital", 24), W / 2, 960, lerp(3, 1, e_out(q)) * (1 + 0.03 * math.sin(t * 12)))
        flash(f, 0.6 * (1 - prog(t, 76.3, 0.3)))
    T(f, t, 77.2, "¿CUÁL MERECE VIAJAR", 74, 330, anim="up", t1=79.85)
    T(f, t, 79.94, "¿CUÁL VA A NÜRBURGRING?", 70, 330, GREEN, anim="pop", glow=6)


def sc_decidis(f, t):
    put(f, bg_image((20, 160, 90)), W / 2, H / 2)
    particles(f, t, GREEN, 0.7)
    if t < 84.4:
        T(f, t, 81.18, "AQUÍ NO DECIDO", 100, 640, anim="up", t1=82.6)
        if 81.88 <= t < 82.88:
            img = txt("YO", 260, WHITE, "ital")
            glitch_text(f, t, img, W / 2, 830, 1 - prog(t, 81.88, 0.4))
            strike(f, 380, 700, 840, prog(t, 82.3, 0.2), RED, 22)
        if t >= 82.88:
            T(f, t, 82.88, "¡DECIDÍS", 190, 820, GREEN, "ital", anim="slam", glow=16)
            T(f, t, 83.44, "VOSOTROS!", 190, 1020, GREEN, "ital", anim="slam", glow=16)
            confetti(f, t, 83.44)
            flash(f, 0.5 * (1 - prog(t, 82.88, 0.25)), GREEN)
    else:
        # dos tarjetas de voto
        for i, (tk, letter, col, kind, txt1) in enumerate(((84.48, "A", RED, "audi", "COMENTA  A"),
                                                         (87.96, "B", BLUE, "bmw", "COMENTA  B"))):
            if t < tk:
                continue
            y = 640 + i * 620
            p = e_out(prog(t, tk, 0.45))
            x = lerp(-W if i == 0 else 2 * W, W / 2, p)
            active = (t < 87.9) if i == 0 else True
            card = glass_card(940, 520, border=col)
            put(f, card, x, y, 1, 1 if active else 0.75)
            draw_car(f, kind, x - 150, y - 40, 0.5, travel=t * 300, flip=False)
            put(f, letter_badge(letter, col, 180), x + 320, y - 60, 1 + 0.06 * math.sin(t * 6))
            put(f, txt(txt1, 82, WHITE, "ital"), x, y + 160, 1)
            put(f, txt("SI QUIERES EL " + ("AUDI A6" if i == 0 else "BMW E46"), 34, col, "mono", 0, 0, (0, 0, 0), 3),
                x, y - 200, 1)
            # pulsador "escribiendo"
            if (t * 2) % 1 < 0.5 and t < tk + 3.0:
                ImageDraw.Draw(f).rectangle((x + 250, y + 125, x + 258, y + 195), fill=col)


COMMS = [(92.3, "A", "¡El Audi tiene carácter!"), (92.9, "B", "El E46 nació para curvas"),
         (93.5, "A", "A sin dudarlo"), (94.1, "B", "B B B B B"), (94.7, "A", "Equipo Audi A6"),
         (95.3, "B", "Chasis perfecto: B"), (95.9, "A", "Que vaya el A"), (96.5, "B", "¡Vamos con el BMW!"),
         (97.1, "A", "A, más especial"), (97.7, "B", "B al Infierno Verde"), (98.3, "A", "¡A!"),
         (98.9, "B", "E46 o nada")]


def sc_defended(f, t):
    put(f, bg_image((80, 60, 140)), W / 2, H / 2)
    T(f, t, 92.02, "DEFENDED", 150, 330, GOLD, "ital", anim="slam", glow=10)
    T(f, t, 93.08, "VUESTRA ELECCIÓN", 76, 450, anim="up")
    # cascada de comentarios
    for i, (tk, l, s) in enumerate(COMMS):
        if t < tk:
            continue
        age = t - tk
        y = 1450 - age * 260
        if y < 560:
            continue
        a = clamp(age * 4) * clamp((y - 560) / 150)
        x = W / 2 + (-50 if l == "A" else 50)
        put(f, comment(i, l, s), x, y, 0.8 + 0.2 * e_back(clamp(age * 3)), a)
    if t > 95.16:
        put(f, chip("¡30 DÍAS DE CONSECUENCIAS!", RED, 50, WHITE), W / 2, 1460,
            e_back(prog(t, 95.16, 0.35)), rot=2)
    if t > 97.68:
        d = ImageDraw.Draw(f)
        for k in range(30):
            p = prog(t, 97.68 + k * 0.04, 0.2)
            x = 105 + k * 29
            d.rounded_rectangle((x, 1530 - 20 * p, x + 22, 1540), 5, fill=mix(DARK, GREEN, p))


def sc_dolar(f, t):
    put(f, bg_image((30, 170, 80)), W / 2, H / 2)
    particles(f, t, GOLD, 0.6)
    if t < 104.5:
        # botón seguir
        p = e_back(prog(t, 100.42, 0.4))
        clicked = t > 100.95
        b = chip("SEGUIDO ✓" if False else ("SIGUIENDO" if clicked else "+ SEGUIR"), GREEN if clicked else WHITE, 64,
                 (0, 0, 0), 60, 24)
        put(f, b, W / 2, 470, p * (0.92 if 100.9 < t < 101.05 else 1))
        # cursor
        if 100.5 < t < 101.6:
            q = e_out(prog(t, 100.5, 0.4))
            cx, cy = lerp(W - 150, W / 2 + 120, q), lerp(700, 500, q)
            cur = Image.new("RGBA", (60, 80), (0, 0, 0, 0))
            ImageDraw.Draw(cur).polygon([(4, 4), (4, 64), (20, 50), (32, 76), (42, 70), (30, 46), (52, 46)],
                                        fill=WHITE + (255,), outline=(0, 0, 0, 255))
            put(f, cur, cx, cy)
        T(f, t, 100.68, "+1 SEGUIDOR", 120, 690, anim="up")
        T(f, t, 101.74, "= 1 $", 300, 920, GOLD, "ital", anim="slam", glow=24)
        # contador
        if t > 102.3:
            n = int(1 + (t - 102.3) ** 2.2 * 260)
            T(f, t, 102.3, "INVERTIDOS EN", 50, 1120, GREY, "mono", anim="fade", track=3)
            put(f, txt(f"${n:,}".replace(",", "."), 110, GREEN, "mono", 10), W / 2, 1220, 1)
        if t > 103.36:
            for i, (k, c) in enumerate((("A", RED), ("B", BLUE))):
                pp = e_back(prog(t, 103.4 + i * 0.12, 0.35))
                xx = W / 2 + (-230 if i == 0 else 230)
                put(f, letter_badge(k, c, 170), xx, 1420, pp)
            # monedas cayendo hacia los coches
            d = ImageDraw.Draw(f)
            for i in range(14):
                a, b, c = AVAT[i]
                ph = ((t - 103.36) * 1.3 + a) % 1
                xx = W / 2 + (-230 if i % 2 == 0 else 230) + (b - 0.5) * 120
                yy = lerp(1290, 1400, ph)
                d.ellipse((xx - 20, yy - 20, xx + 20, yy + 20), fill=GOLD, outline=(180, 130, 0), width=4)
    else:
        T(f, t, 104.62, "ESTO NO ES", 100, 560, anim="up")
        T(f, t, 105.62, "MI PROYECTO", 130, 720, anim="up")
        strike(f, 95, 300, 735, prog(t, 106.2, 0.2), RED, 18)
        if t > 106.96:
            for i in range(16):
                ang = i / 16 * 2 * math.pi + t * 0.3
                put(f, avatar(i, 64), W / 2 + math.cos(ang) * 490, 1120 + math.sin(ang) * 360,
                    0.8 * e_back(prog(t, 107.0 + i * 0.03, 0.3)), 0.7)
        T(f, t, 106.66, "ES", 100, 940, anim="up")
        T(f, t, 106.96, "NUESTRO", 230, 1120, GREEN, "ital", anim="slam", glow=20)
        T(f, t, 107.48, "PROYECTO", 110, 1290, anim="up")
        if t > 106.96:
            flash(f, 0.4 * (1 - prog(t, 106.96, 0.3)), GREEN)


def sc_manana(f, t):
    put(f, bg_image((40, 80, 120)), W / 2, H / 2)
    particles(f, t, WHITE, 0.4)
    # hoja de calendario
    p = e_back(prog(t, 108.5, 0.45))
    card = Image.new("RGBA", (300, 330), (0, 0, 0, 0))
    dd = ImageDraw.Draw(card)
    dd.rounded_rectangle((0, 0, 299, 329), 28, fill=WHITE + (255,))
    dd.rounded_rectangle((0, 0, 299, 100), 28, fill=RED + (255,))
    dd.rectangle((0, 60, 299, 100), fill=RED + (255,))
    dd.text((150, 52), "MAÑANA", font=font("black", 44), fill=(255, 255, 255, 255), anchor="mm")
    dd.text((150, 220), "1", font=font("black", 190), fill=(20, 20, 20, 255), anchor="mm")
    put(f, card, W / 2, 520, p, rot=math.sin(t * 2) * 3)
    T(f, t, 109.08, "RECUENTO DE VOTOS", 76, 790, anim="up")
    # barras A/B indecisas
    if t > 109.7:
        q = e_out(prog(t, 109.7, 0.5))
        v = 0.5 + 0.18 * math.sin(t * 3.1) * math.cos(t * 1.7)
        x0, x1, y = 120, W - 120, 940
        d = ImageDraw.Draw(f)
        mid = lerp(x0, x1, v)
        d.rounded_rectangle((x0, y, lerp(x0, mid, q), y + 70), 20, fill=RED)
        d.rounded_rectangle((lerp(x1, mid, q), y, x1, y + 70), 20, fill=BLUE)
        put(f, txt("A", 56, WHITE, "black"), x0 + 50, y + 35, q)
        put(f, txt("B", 56, WHITE, "black"), x1 - 50, y + 35, q)
        put(f, txt("?", 80, GOLD, "black", 8), mid, y + 35, q)
    if t > 110.4:
        T(f, t, 110.4, "¿QUÉ COCHE SERÁ", 66, 1130, anim="up")
        T(f, t, 112.22, "EL PROTAGONISTA?", 96, 1240, GOLD, "ital", anim="slam", glow=8)
        sp = (math.sin(t * 2.2) + 1) / 2
        draw_car(f, "audi", 290, 1440, 0.48, travel=t * 200, sil=sp < 0.5)
        draw_car(f, "bmw", W - 290, 1440, 0.48, travel=t * 200, sil=sp >= 0.5, flip=True)


def sc_final(f, t):
    put(f, bg_image((0, 200, 100)), W / 2, H / 2)
    particles(f, t, GREEN)
    speed_lines(f, t, GREEN, -1, (250, 1700), 0.5, 1.4)
    beats = [(114.54, 115.85, "30", "DÍAS", GREEN), (115.9, 116.88, "1", "COCHE", WHITE),
             (116.92, 118.1, "1", "OBJETIVO", GOLD)]
    for t0, t1, big, small, col in beats:
        if t0 <= t < t1:
            T(f, t, t0, big, 520, 820, col, "ital", anim="slam", glow=20)
            T(f, t, t0 + 0.1, small, 140, 1180, WHITE, "ital", anim="up")
            flash(f, 0.35 * (1 - prog(t, t0, 0.2)))
    if 118.1 <= t < 119.5:
        draw_track(f, W / 2, 900, 820, e_out(prog(t, 118.1, 1.0)), GREEN, t=t)
        T(f, t, 118.18, "NÜRBURGRING", 160, 420, WHITE, "ital", anim="slam", glow=12)
        flash(f, 0.6 * (1 - prog(t, 118.18, 0.3)), GREEN)
    if t >= 119.5:
        T(f, t, 119.56, "¿LLEGAREMOS", 130, 640, anim="up")
        T(f, t, 120.0, "A TIEMPO?", 170, 800, GOLD, "ital", anim="slam", glow=10)
        rem = max(0, 30 * 86400 - (t - 119.5) * 86400 / 40)
        dd, rr = divmod(int(rem), 86400)
        hh, rr = divmod(rr, 3600)
        mm, ss = divmod(rr, 60)
        put(f, txt(f"{dd:02d}:{hh:02d}:{mm:02d}:{ss:02d}", 110, RED, "mono", 12), W / 2, 1060,
            e_back(prog(t, 119.7, 0.3)))
        put(f, txt("DÍAS   HORAS   MIN   SEG", 30, GREY, "mono", 0, 0, (0, 0, 0), 6), W / 2, 1150,
            clamp(prog(t, 119.8, 0.3)))


def sc_end(f, t):
    put(f, bg_image((0, 255, 120)), W / 2, H / 2)
    grid_floor(f, t, GREEN, 2.5, 1250, 0.8)
    speed_lines(f, t, GREEN, -1, (300, 1700), 0.8, 2.0)
    particles(f, t, GREEN)
    T(f, t, 121.08, "¡EMPIEZA", 200, 560, GREEN, "ital", anim="slam", glow=20)
    T(f, t, 121.66, "EL PROYECTO!", 140, 740, WHITE, "ital", anim="slam", glow=8)
    flash(f, 0.9 * (1 - prog(t, 121.08, 0.35)))
    confetti(f, t, 121.2)
    p = e_out(prog(t, 121.2, 0.8))
    draw_car(f, "audi", lerp(-500, 300, p) + max(0, t - 123.2) * 900, 1080, 0.55, travel=t * 700)
    draw_car(f, "bmw", lerp(W + 500, W - 300, p) - max(0, t - 123.2) * 900, 1330, 0.55, travel=t * 700, flip=True)
    if t > 122.0:
        put(f, chip("COMENTA  A  o  B", GOLD, 60, (0, 0, 0), 40, 22), W / 2, 1560, e_back(prog(t, 122.0, 0.4)))
    if t > DUR - 0.9:
        f.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * prog(t, DUR - 0.9, 0.9)))))


SCENES = [sc_titulo, sc_30, sc_track, sc_problema, sc_diferente, sc_infierno, sc_solo, sc_checklist, sc_hoy,
          sc_a, sc_b, sc_vs, sc_decidis, sc_defended, sc_dolar, sc_manana, sc_final, sc_end]
WIPE_COL = [GREEN, GREEN, RED, GREEN, GREEN, BLUE, GREEN, GOLD, RED, BLUE, WHITE, GREEN, GOLD, GREEN, BLUE, GREEN, GREEN]
IMPACTS = [2.8, 14.12, 29.9, 49.8, 66.0, 76.3, 82.88, 106.96, 118.18, 121.08]
SUB_HIDE = [(0, 7.7), (14.0, 15.1), (29.85, 32.6), (114.4, 120.5), (121.0, DUR)]


def wipe(f, t):
    for i, c in enumerate(CUTS[1:-1]):
        p = (t - (c - 0.22)) / 0.44
        if 0 <= p <= 1:
            col = WIPE_COL[i % len(WIPE_COL)]
            x = lerp(-W * 1.6, W * 1.6, e_io(p))
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            sk = 700
            d.polygon([(x - 500, 0), (x + 500 + 0, 0), (x + 500 - sk, H), (x - 500 - sk, H)], fill=col + (255,))
            d.polygon([(x + 520, 0), (x + 600, 0), (x + 600 - sk, H), (x + 520 - sk, H)], fill=WHITE + (255,))
            d.polygon([(x - 620, 0), (x - 560, 0), (x - 560 - sk, H), (x - 620 - sk, H)], fill=col + (180,))
            f.alpha_composite(lay)


def render(t):
    f = Image.new("RGBA", (W, H), DARK + (255,))
    idx = 0
    for i in range(len(CUTS) - 1):
        if CUTS[i] <= t < CUTS[i + 1]:
            idx = i
    SCENES[min(idx, len(SCENES) - 1)](f, t)
    hud(f, t)
    subtitles(f, t, hide=SUB_HIDE)
    f.alpha_composite(STATIC["scan"])
    f.alpha_composite(STATIC["vig"])
    f.alpha_composite(STATIC["grain"][int(t * FPS) % 6])
    wipe(f, t)
    # temblor de cámara en los golpes
    sh = 0
    for ti in IMPACTS:
        if 0 <= t - ti < 0.4:
            sh = max(sh, 22 * (1 - (t - ti) / 0.4))
    out = f.convert("RGB")
    if sh > 0.5:
        r = random.Random(int(t * FPS))
        out = ImageChops.offset(out, int(r.uniform(-sh, sh)), int(r.uniform(-sh, sh)))
    return out


STATIC = None


def init():
    global STATIC
    STATIC = make_static()


def work(i):
    return render(i / FPS).tobytes()


def main():
    if "--frame" in sys.argv:
        init()
        tt = [float(x) for x in sys.argv[sys.argv.index("--frame") + 1].split(",")]
        for x in tt:
            render(x).save(f"/tmp/claude-0/-home-user-akra787/39331ca1-8318-5d14-b082-8a311a8e55b5/scratchpad/f_{x}.png")
        return
    out = os.path.join(AQUI, "..", "nurburgring.mp4")
    nframes = int(DUR * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", os.path.join(AQUI, "mezcla.wav"),
                           "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    with Pool(4, initializer=init) as pool:
        for i, b in enumerate(pool.imap(work, range(nframes), chunksize=8)):
            ff.stdin.write(b)
            if i % 300 == 0:
                print(f"{i}/{nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("listo:", out)


if __name__ == "__main__":
    main()
