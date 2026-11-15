#!/usr/bin/env python3
"""Foto de perfil: el piloto misterioso en un marco marrón, fondo negro, Nürburgring detrás.

Uso: python3 perfil.py  → perfil.png (1080x1080)
"""
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import render
import sombra

AQUI = os.path.dirname(os.path.abspath(__file__))
S = 1080
C = S / 2
R_IN, R_OUT = 432, 520


def interior():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    # cielo verde oscuro del "Infierno Verde"
    y = np.linspace(0, 1, S)[:, None, None]
    sky = np.array([2, 10, 7]) * (1 - y) + np.array([0, 70, 38]) * y ** 1.4
    g = render.radial(S, S, C, 430, 520)[..., None] ** 1.5 * np.array([0, 120, 70])
    arr = np.clip(sky + g, 0, 255).astype(np.uint8)
    im = Image.fromarray(np.dstack([arr.repeat(S, 1) if arr.shape[1] == 1 else arr,
                                    np.full((S, S), 255, np.uint8)]), "RGBA")
    # circuito brillando detrás de la cabeza, como un halo
    tr = render.track_full(760, render.GREEN)
    im.alpha_composite(render.with_alpha(tr, 0.85), (int(C - 380), 50))
    # bosque de abetos (dos capas)
    rng = np.random.default_rng(4)
    for layer, (col, base, hmin, hmax) in enumerate((((4, 34, 20), 760, 120, 230), ((1, 14, 8), 830, 150, 280))):
        lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x = -40
        while x < S + 40:
            h = rng.uniform(hmin, hmax)
            w = h * 0.42
            d.polygon([(x, base - h), (x + w / 2, base), (x - w / 2, base)], fill=col + (255,))
            for k in (0.35, 0.6):
                d.polygon([(x, base - h * (1 - k) - 10), (x + w * (0.5 + k * 0.2), base - h * (0.5 - k * 0.5) + 30),
                           (x - w * (0.5 + k * 0.2), base - h * (0.5 - k * 0.5) + 30)], fill=col + (255,))
            x += rng.uniform(40, 80)
        d.rectangle((0, base - 4, S, S), fill=col + (255,))
        im.alpha_composite(lay)
    # niebla
    fog = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for _ in range(18):
        fx, fy = rng.uniform(0, S), rng.uniform(640, 860)
        fd.ellipse((fx - 260, fy - 50, fx + 260, fy + 50), fill=(140, 220, 180, 26))
    im.alpha_composite(fog.filter(ImageFilter.GaussianBlur(30)))
    # chispas
    d = ImageDraw.Draw(im)
    for _ in range(70):
        px, py = rng.uniform(80, S - 80), rng.uniform(80, 900)
        r = rng.uniform(1, 3.2)
        d.ellipse((px - r, py - r, px + r, py + r), fill=(120, 255, 190, int(rng.uniform(80, 220))))
    # el personaje
    sc = 0.98
    cy = 330 - 96 * sc + sombra.CH * sc / 2
    rays = sombra.rays()
    render.put(im, rays, C, 330 + 140 * sc, 0.8, 0.9, rot=8)
    render.put(im, sombra.aura(3.1, 1.6), C, cy, sc)
    render.put(im, sombra.figure(8, 4), C, cy, sc)
    # sombra interior junto al marco
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse((C - R_IN, C - R_IN, C + R_IN, C + R_IN), fill=255)
    inner = ImageChops.invert(m).filter(ImageFilter.GaussianBlur(30))
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sh.putalpha(ImageChops.multiply(inner, m).point(lambda v: min(255, int(v * 2.2))))
    im.alpha_composite(sh)
    im.putalpha(m)
    return im


def marco():
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    dx, dy = xx - C, yy - C
    r = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    u = np.clip((r - R_IN) / (R_OUT - R_IN), 0, 1)          # 0 dentro → 1 fuera
    # perfil de moldura: dos curvas redondeadas
    prof = np.sin(u * math.pi) * 0.7 + np.sin(u * math.pi * 3) * 0.12
    # luz desde arriba a la izquierda según la pendiente del perfil
    slope = np.cos(u * math.pi) * 0.7 + np.cos(u * math.pi * 3) * 0.36
    light = -np.cos(ang + math.pi * 0.75)                  # 1 arriba-izquierda
    shade = 0.62 + 0.38 * prof + 0.30 * slope * light
    # veta de la madera: anillos ondulados
    rng = np.random.default_rng(2)
    n = rng.random((64, 256)).astype(np.float32)
    n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC), np.float32) / 255
    grain = 0.5 + 0.5 * np.sin(r * 0.55 + n * 9 + np.sin(ang * 7) * 2.5)
    grain = grain ** 3
    base = np.array([122, 70, 36], np.float32)
    dark = np.array([58, 30, 13], np.float32)
    col = base * (1 - grain[..., None] * 0.45) + dark * grain[..., None] * 0.45
    col = col * shade[..., None]
    # brillo especular
    spec = np.clip(light, 0, 1) ** 6 * np.clip(prof, 0, 1) ** 4 * 90
    col = np.clip(col + spec[..., None] * np.array([1.0, 0.85, 0.6]), 0, 255)
    a = ((r >= R_IN - 1) & (r <= R_OUT + 1)).astype(np.float32)
    # bordes suaves
    a *= np.clip(r - R_IN + 1, 0, 1) * np.clip(R_OUT + 1 - r, 0, 1)
    im = Image.fromarray(np.dstack([col.astype(np.uint8), (a * 255).astype(np.uint8)]), "RGBA")
    d = ImageDraw.Draw(im)
    # filete dorado interior y borde exterior oscuro
    d.ellipse((C - R_IN - 4, C - R_IN - 4, C + R_IN + 4, C + R_IN + 4), outline=(214, 168, 92, 255), width=5)
    d.ellipse((C - R_IN - 9, C - R_IN - 9, C + R_IN + 9, C + R_IN + 9), outline=(40, 22, 10, 255), width=2)
    d.ellipse((C - R_OUT, C - R_OUT, C + R_OUT, C + R_OUT), outline=(30, 16, 8, 255), width=4)
    # remaches en los puntos cardinales
    for k in range(8):
        aa = k / 8 * 2 * math.pi - math.pi / 2
        rx, ry = C + math.cos(aa) * (R_IN + R_OUT) / 2, C + math.sin(aa) * (R_IN + R_OUT) / 2
        d.ellipse((rx - 11, ry - 11, rx + 11, ry + 11), fill=(70, 44, 20, 255))
        d.ellipse((rx - 8, ry - 8, rx + 8, ry + 8), fill=(200, 158, 90, 255))
        d.ellipse((rx - 5, ry - 6, rx + 1, ry), fill=(250, 226, 170, 255))
    return im


def main():
    render.init()
    out = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    # leve resplandor verde detrás del marco
    gl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse((C - R_OUT - 10, C - R_OUT - 10, C + R_OUT + 10, C + R_OUT + 10), fill=(0, 255, 136, 60))
    out.alpha_composite(gl.filter(ImageFilter.GaussianBlur(24)))
    # sombra del marco
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((C - R_OUT, C - R_OUT + 12, C + R_OUT, C + R_OUT + 12), fill=(0, 0, 0, 200))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    out.alpha_composite(interior())
    out.alpha_composite(marco())
    p = os.path.join(AQUI, "perfil.png")
    out.convert("RGB").save(p, optimize=True)
    print(p)


if __name__ == "__main__":
    main()
