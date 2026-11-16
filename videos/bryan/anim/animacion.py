"""Vídeo animado de Bryan (personaje que habla e interactúa con el vídeo).

Uso:
  python3 videos/bryan/anim/animacion.py videos/bryan_animado.json [--rapido] [--solo 0-10]

Si el guion tiene "audio", se usa esa voz y cada escena empieza en su "inicio" (segundos).
Si no, se genera la voz con Piper. La boca de Bryan se mueve con el volumen de la voz y los
subtítulos tipo karaoke salen de faster-whisper (si está instalado).
"""
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(REPO, "video"))
from arte import *  # noqa
import make_video as mv  # noqa

FPS = 30
SR = mv.SR
TRANS = 0.5

# ================================================================ utilidades de animación
def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back(x):
    x = clamp(x)
    c1 = 1.9
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def pop(u, t0, d=0.4):
    if u < t0:
        return 0.0
    return back((u - t0) / d)


_cache_txt = {}


def txt(texto, size, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0), black=True):
    key = (texto, size, fill, stroke, stroke_fill, black)
    if key not in _cache_txt:
        f = fuente(size, black)
        d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lineas = texto.split("\n")
        anchos = [d0.textlength(l, font=f) for l in lineas]
        lh = int(size * 1.12)
        w = int(max(anchos) + stroke * 2 + 10)
        h = int(lh * len(lineas) + stroke * 2 + size * 0.3)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i, l in enumerate(lineas):
            d.text(((w - anchos[i]) / 2, stroke + i * lh), l, font=f, fill=fill, stroke_width=stroke,
                   stroke_fill=stroke_fill)
        _cache_txt[key] = im
    return _cache_txt[key]


def emoji(ch, size):
    key = ("emoji", ch, size)
    if key not in _cache_txt:
        f = ImageFont.truetype(FONT_EMOJI, 109)
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox() or (0, 0, 1, 1)).resize((size, size), Image.LANCZOS)
        _cache_txt[key] = im
    return _cache_txt[key]


def pegar(fr, spr, cx, cy, escala=1.0, alpha=1.0, rot=0.0, esc_x=None):
    if escala <= 0.01 or alpha <= 0.01:
        return
    ex = escala if esc_x is None else esc_x
    if abs(ex - 1) > 0.01 or abs(escala - 1) > 0.01:
        spr = spr.resize((max(1, int(spr.width * abs(ex))), max(1, int(spr.height * escala))), Image.BILINEAR)
    if rot:
        spr = spr.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 0.99:
        a = spr.split()[3].point(lambda v: int(v * alpha))
        spr = spr.copy()
        spr.putalpha(a)
    fr.paste(spr, (int(cx - spr.width / 2), int(cy - spr.height / 2)), spr)


def tarjeta(w, h, fill=(255, 255, 255), radio=30, borde=None, sombra=True):
    key = ("card", w, h, fill, radio, borde, sombra)
    if key not in _cache_txt:
        pad = 30 if sombra else 0
        im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        if sombra:
            s = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(s).rounded_rectangle([pad + 6, pad + 14, pad + w + 6, pad + h + 14], radius=radio, fill=(0, 0, 0, 140))
            im = s.filter(ImageFilter.GaussianBlur(12))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radio, fill=fill,
                            outline=borde[0] if borde else None, width=borde[1] if borde else 0)
        _cache_txt[key] = im
    return _cache_txt[key]


def pastilla(texto, size, fill, color=(255, 255, 255)):
    key = ("pill", texto, size, fill, color)
    if key not in _cache_txt:
        t = txt(texto, size, color)
        c = tarjeta(t.width + size, int(size * 1.6), fill, radio=int(size * 0.8))
        c = c.copy()
        c.paste(t, ((c.width - t.width) // 2, (c.height - t.height) // 2 + 2), t)
        _cache_txt[key] = c
    return _cache_txt[key]


def humo(fr, x0, y0, u, dur_vida=1.4, n=8, seed=0, color=(150, 150, 150), dx=-60, desde=0.0, hasta=1e9, tam=40):
    d = ImageDraw.Draw(fr, "RGBA")
    rnd = random.Random(seed)
    for i in range(n):
        nac = desde + i * dur_vida / n + rnd.uniform(0, 0.1)
        if u < nac:
            continue
        age = (u - nac) % dur_vida
        if u - age > hasta:
            continue
        q = age / dur_vida
        r = tam * (0.4 + 1.6 * q)
        x = x0 + dx * q * 3 + rnd.uniform(-20, 20)
        y = y0 - 90 * q - rnd.uniform(0, 40) * q
        a = int(150 * (1 - q))
        d.ellipse([x - r, y - r, x + r, y + r], fill=color + (a,))


def chispas(fr, x0, y0, u, n=30, seed=1, color=(255, 200, 60), vida=0.6, spread=1.0):
    d = ImageDraw.Draw(fr, "RGBA")
    rnd = random.Random(seed)
    for i in range(n):
        nac = rnd.uniform(0, vida)
        age = (u + nac) % vida
        vx = rnd.uniform(-500, 500) * spread
        vy = rnd.uniform(-700, -150)
        x = x0 + vx * age
        y = y0 + vy * age + 900 * age * age
        l = 0.03
        x2, y2 = x - vx * l, y - (vy + 1800 * age) * l
        a = int(255 * (1 - age / vida))
        d.line([(x, y), (x2, y2)], fill=color + (a,), width=4)


def confeti(fr, u, n=90, seed=3, desde=0.0):
    if u < desde:
        return
    d = ImageDraw.Draw(fr, "RGBA")
    rnd = random.Random(seed)
    cols = [ROJO, ORO, (255, 255, 255), (40, 170, 255), (60, 220, 120)]
    for i in range(n):
        x0 = rnd.uniform(0, W)
        vel = rnd.uniform(250, 500)
        off = rnd.uniform(0, 2400)
        y = (off + (u - desde) * vel) % (H + 200) - 100
        x = x0 + math.sin((u - desde) * rnd.uniform(1, 3) + i) * 50
        a = (u - desde) * rnd.uniform(3, 8) + i
        w, h = 18, 9 * abs(math.cos(a))
        c = cols[i % len(cols)]
        pts = [(x + math.cos(a) * w - math.sin(a) * h, y + math.sin(a) * w + math.cos(a) * h)]
        pts = [(x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
               for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
        d.polygon(pts, fill=c + (230,))


def engranaje(r, dientes, color):
    key = ("gear", r, dientes, color)
    if key not in _cache_txt:
        k = 2
        R = r * k
        im = Image.new("RGBA", (int(R * 2.5), int(R * 2.5)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = im.width / 2
        for i in range(dientes):
            a = i * 2 * math.pi / dientes
            pts = []
            for da, rr in ((-0.12, 0.95), (-0.08, 1.2), (0.08, 1.2), (0.12, 0.95)):
                pts.append((c + math.cos(a + da * 2) * R * rr, c + math.sin(a + da * 2) * R * rr))
            d.polygon(pts, fill=color)
        d.ellipse([c - R, c - R, c + R, c + R], fill=color)
        d.ellipse([c - R * .4, c - R * .4, c + R * .4, c + R * .4], fill=(0, 0, 0, 0))
        _cache_txt[key] = im.resize((im.width // k, im.height // k), Image.LANCZOS)
    return _cache_txt[key]


def llamas(fr, x, y, u, fuerza=1.0, seed=0):
    if fuerza <= 0:
        return
    capa = Image.new("RGB", (360, 200))
    d = ImageDraw.Draw(capa)
    rnd = random.Random(int(u * 30) + seed)
    for i in range(14):
        l = rnd.uniform(80, 260) * fuerza
        yy = 100 + rnd.uniform(-20, 20)
        d.ellipse([340 - l, yy - 22 * fuerza, 340, yy + 22 * fuerza], fill=(255, rnd.randint(80, 160), 20))
    d.ellipse([250, 82, 345, 118], fill=(255, 240, 180))
    capa = brillo(capa, capa, 12)
    m = capa.convert("L").point(lambda v: min(255, v * 2))
    fr.paste(capa, (int(x - 340), int(y - 100)), m)


# ================================================================ Bryan con poses por tiempo
def dibujar_bryan(fr, ctx, x, y, poses, escala=0.8, mirar=(0.3, 0.0), excitado=0.5, salto=0.0, gesto=0.6):
    u, dur, t = ctx["u"], ctx["dur"], ctx["t"]
    p = u / dur
    actual, previa, t0 = poses[0][1], poses[0][1], 0.0
    for i, (pp, pose) in enumerate(poses):
        if p >= pp:
            previa = poses[i - 1][1] if i > 0 else pose
            actual, t0 = pose, pp * dur
    mezcla = clamp((u - t0) / 0.3)
    objeto = actual if actual in ("llave", "carpeta", "portatil", "pistola", "movil", "lupa") else None
    if objeto is None and mezcla < 0.5 and previa in ("llave", "carpeta", "portatil", "pistola", "movil", "lupa"):
        objeto = previa
    spr, ax, ay = bryan_sprite(t, previa, actual, mezcla, ctx["habla"], mirar, excitado, objeto, salto,
                               escala, gesto)
    fr.paste(spr, (int(x - ax), int(y - ay)), spr)


def fondo_pan(nombre, desplaz):
    bg = fondos()[nombre]
    x = int(clamp(80 + desplaz, 0, bg.width - W))
    return bg.crop((x, 0, x + W, H)).copy(), x


def titulo_parte(fr, u, num, nombre, y=470):
    s = pop(u, 0.1)
    pegar(fr, pastilla(f"PARTE {num}", 44, ROJO), W / 2, y - 80, s)
    pegar(fr, txt(nombre, 92, (255, 255, 255), 10), W / 2, y + 20, pop(u, 0.25))


# ================================================================ ESCENAS
def esc_intro(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, _ = fondo_pan("calle", -60 + 120 * p)
    fr.paste(bg)
    car_x = 650
    cough = 1 if (u % 2.2) < 0.35 else 0
    reb = math.sin(u * 60) * 3 * cough
    pegar_coche(fr, car_x, 1420, 0, color=(130, 132, 128), oxido=True, rebote=reb)
    humo(fr, car_x + 330, 1330, u, n=6, seed=2, color=(120, 120, 120), dx=10, tam=34)
    humo(fr, car_x - 400, 1440, u, n=5, seed=7, color=(70, 70, 75), dx=-50, tam=30)
    pegar(fr, txt("DE CHATARRA", 110, (255, 255, 255), 12), W / 2, 210, pop(u, 0.2))
    pegar(fr, txt("A COHETE", 140, ROJO, 12, (255, 255, 255)), W / 2, 350, pop(u, 0.55), rot=3 * math.sin(u * 3))
    # etiquetas de precio
    sw = math.sin(u * 2.5) * 6
    s1 = pop(u, 0.10 * dur)
    pegar(fr, pastilla("1.500 €", 80, (255, 255, 255), (20, 20, 20)), 760, 640, s1, rot=sw)
    if p > 0.48:
        pegar(fr, txt("↓", 90, (255, 255, 255), 6), 760, 760, pop(u, 0.48 * dur))
        s2 = pop(u, 0.52 * dur, 0.5)
        pegar(fr, pastilla("¿6.000 €?", 92, ORO, (30, 20, 0)), 760, 890, s2 * (1 + 0.05 * math.sin(u * 8)), rot=-sw)
        pegar(fr, txt("EN 30 DÍAS", 54, (255, 255, 255), 6), 760, 1010, pop(u, 0.6 * dur))
    # Bryan entra andando
    entra = ease_out(u / 1.1)
    bx = lerp(-260, 220, entra)
    salto = abs(math.sin(u * 11)) * 25 * (1 - entra)
    dibujar_bryan(fr, ctx, bx, 1730, [(0, "normal"), (0.1, "senala_der"), (0.45, "encoge"), (0.72, "pulgar")],
                  salto=salto, mirar=(0.6 if p < 0.7 else 0.0, 0.1))


def esc_diagnostico(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, ox = fondo_pan("taller", -40 + 80 * p)
    fr.paste(bg)
    neon = neon_bs(apagado=(u % 3.7) < 0.12)
    fr.paste(neon, (int(160 - (ox - 80) * 0.5), 130), neon)
    titulo_parte(fr, u, 1, "DIAGNÓSTICO", 500)
    cough = 1 if (u % 2.6) < 0.3 else 0
    pegar_coche(fr, 650, 1420, 0, color=(130, 132, 128), oxido=True, rebote=math.sin(u * 60) * 3 * cough)
    humo(fr, 650 - 400, 1440, u, n=5, seed=4, color=(70, 70, 75), dx=-50, tam=28)
    # hoja de diagnóstico
    cx, cy = 770, 900
    s = pop(u, 0.08 * dur, 0.5)
    if s > 0:
        card = tarjeta(500, 520, (250, 248, 240), 26).copy()
        d = ImageDraw.Draw(card)
        d.text((60, 45), "INFORME", font=fuente(46), fill=(30, 30, 30))
        items = [("Óxido", 0.17), ("Embrague", 0.28), ("230.000 km", 0.39), ("Olor a quemado", 0.52)]
        for i, (it, pt) in enumerate(items):
            yy = 120 + i * 78
            d.text((60, yy), it, font=fuente(40, False), fill=(50, 50, 55))
            d.line([(60, yy + 58), (470, yy + 58)], fill=(220, 215, 205), width=2)
        if p > 0.68:
            d.text((60, 440), "Motor: ¡TIENE ALMA!", font=fuente(38), fill=(20, 140, 60))
        pegar(fr, card, cx, cy, s)
        for i, (it, pt) in enumerate(items):
            ss = pop(u, pt * dur, 0.3)
            if ss:
                pegar(fr, txt("✗", 70, (230, 30, 40), 4, (255, 255, 255)), cx + 170, cy - 112 + i * 78,
                      ss * (2 - ss) if ss < 1 else ss, rot=-12)
        if p > 0.68:
            lat = 1 + 0.15 * abs(math.sin(u * 7))
            pegar(fr, emoji("❤️", 70), cx + 205, cy + 205, pop(u, 0.68 * dur) * lat)
    dibujar_bryan(fr, ctx, 220, 1730, [(0, "carpeta"), (0.66, "pulgar")], mirar=(0.7, -0.2) if p < 0.66 else (0, 0))


def esc_mecanica(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, ox = fondo_pan("taller", 40 - 80 * p)
    fr.paste(bg)
    neon = neon_bs()
    fr.paste(neon, (int(160 - (ox - 80) * 0.5), 130), neon)
    titulo_parte(fr, u, 2, "MECÁNICA", 500)
    sube = ease(u / 0.9) if p < 0.78 else 1 - back((u - 0.78 * dur) / 0.5)
    car_y = 1420 - 170 * sube
    shake = (math.sin(u * 70) * 6) if 0.78 < p < 0.92 else 0
    d = ImageDraw.Draw(fr)
    for lx in (650 - 225, 650 + 230):  # brazos del elevador
        d.rectangle([lx - 14, min(car_y + 60, 1499), lx + 14, 1500], fill=(240, 190, 20))
        d.rectangle([lx - 60, 1495, lx + 60, 1515], fill=(60, 60, 64))
    pegar_coche(fr, 650 + shake, car_y, 0, color=(130, 132, 128), oxido=True)
    if 0.05 < p < 0.75:
        chispas(fr, 650 + 60 * math.sin(u * 2), car_y + 130, u, n=26, seed=5)
    # checklist
    for i, (nombre, pt) in enumerate((("EMBRAGUE", 0.14), ("ACEITE + FILTROS", 0.23), ("TURBO", 0.33))):
        s = pop(u, pt * dur)
        pegar(fr, pastilla("✓ " + nombre, 46, (30, 160, 80)), 760, 690 + i * 100, s)
    g = engranaje(50, 10, (200, 205, 215, 255))
    pegar(fr, g, 120, 470, pop(u, 0.2), rot=u * 90)
    pegar(fr, engranaje(34, 8, (240, 190, 20, 255)), 205, 410, pop(u, 0.3), rot=-u * 130)
    # tres noches sin dormir
    if 0.45 < p < 0.78:
        q = (p - 0.45) / 0.33
        capa = Image.new("RGBA", (W, H), (5, 10, 40, int(120 * math.sin(q * math.pi))))
        fr.paste(capa, (0, 0), capa)
        noche = min(3, int(q * 3) + 1)
        pegar(fr, emoji("🌙", 120), 880, 1050, pop(u, 0.45 * dur))
        pegar(fr, txt(f"NOCHE {noche}", 70, (255, 255, 255), 8), 860, 1170, 1 + 0.1 * math.sin(u * 10))
    if p > 0.8:
        s = pop(u, 0.8 * dur, 0.3)
        pegar(fr, txt("¡BRRRUM!", 130, ORO, 12, (60, 20, 0)), 700 + math.sin(u * 50) * 8, 1110, s, rot=6)
        humo(fr, 650 - 400, 1440, u, n=10, seed=9, color=(90, 90, 95), dx=-80, desde=0.8 * dur, tam=36)
    dibujar_bryan(fr, ctx, 210, 1730, [(0, "llave"), (0.45, "encoge"), (0.8, "brazos_arriba")],
                  mirar=(0.7, 0.2) if p < 0.45 else (0, 0), salto=40 * abs(math.sin(u * 8)) if p > 0.82 else 0)


def esc_pintura(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, _ = fondo_pan("pintura", -30 + 60 * p)
    fr.paste(bg)
    titulo_parte(fr, u, 3, "CHAPA Y PINTURA", 480)
    cx, cy, s = 660, 1420, 0.8
    pegar_coche(fr, cx, cy, 0, color=(130, 132, 128), oxido=True)
    q = ease((p - 0.15) / 0.55)
    rojo, ax, ay = coche_sprite(ROJO, False, False, False, s)
    corte = int(rojo.width * q)
    if corte > 0:
        parte = rojo.crop((0, 0, corte, rojo.height))
        fr.paste(parte, (int(cx - ax), int(cy - ay)), parte)
    if 0.12 < p < 0.72:
        nx = cx - ax + corte
        d = ImageDraw.Draw(fr, "RGBA")
        rnd = random.Random(int(u * 30))
        for _ in range(70):
            y = rnd.uniform(cy - 170, cy + 80)
            x = nx + rnd.uniform(-30, 60)
            r = rnd.uniform(3, 12)
            d.ellipse([x - r, y - r, x + r, y + r], fill=ROJO + (rnd.randint(60, 180),))
        niebla = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(niebla).ellipse([nx - 160, cy - 260, nx + 160, cy + 120], fill=ROJO + (70,))
        niebla = niebla.filter(ImageFilter.GaussianBlur(40))
        fr.paste(niebla, (0, 0), niebla)
    if 0.1 < p < 0.74:
        barra = Image.new("RGBA", (620, 150), (0, 0, 0, 0))
        db = ImageDraw.Draw(barra)
        db.text((0, 0), f"PINTANDO... {int(q * 100)}%", font=fuente(50), fill=(30, 30, 35))
        db.rounded_rectangle([0, 80, 620, 130], radius=25, fill=(60, 60, 70))
        db.rounded_rectangle([0, 80, max(50, int(620 * q)), 130], radius=25, fill=ROJO)
        pegar(fr, barra, W / 2 + 60, 860, pop(u, 0.1 * dur))
        pegar(fr, emoji("🎨", 110), 160, 860, pop(u, 0.12 * dur), rot=10 * math.sin(u * 3))
    if p > 0.72:
        rnd = random.Random(4)
        for i in range(8):
            x = cx + rnd.uniform(-380, 380)
            y = cy + rnd.uniform(-170, 40)
            f = (u * 2 + i * 0.37) % 1
            pegar(fr, txt("✦", 60, (255, 255, 255)), x, y, math.sin(f * math.pi))
        pegar(fr, pastilla("ROJO BRYAN", 64, ROJO), 760, 900, pop(u, 0.74 * dur), rot=-4)
        pegar(fr, txt("ANTES → AHORA", 48, (30, 30, 30)), 760, 1010, pop(u, 0.8 * dur))
    dibujar_bryan(fr, ctx, 200, 1730, [(0, "normal"), (0.1, "pistola"), (0.74, "senala_der")], mirar=(0.8, 0.1))


def curva(rpm, pico):
    return pico * math.sin(clamp((rpm - 1000) / 4200) * math.pi * 0.62) ** 0.8


def esc_repro(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    shake = math.sin(u * 80) * 5 if 0.45 < p < 0.9 else 0
    bg, ox = fondo_pan("banco", 0)
    fr.paste(bg, (int(shake), 0))
    # pantalla: gráfica de potencia
    x0, y0, x1, y1 = 190 - ox + 40, 380, 1050 - ox - 40, 820
    d = ImageDraw.Draw(fr)
    for i in range(5):
        yy = y1 - i * (y1 - y0) / 4
        d.line([(x0, yy), (x1, yy)], fill=(30, 50, 80), width=2)
    d.text((x0, y0 - 40), "BANCO DE POTENCIA", font=fuente(34), fill=(120, 200, 255))
    prog = clamp((p - 0.25) / 0.5)
    def puntos(pico, hasta):
        pts = []
        for i in range(int(60 * hasta) + 1):
            rpm = 1000 + 5000 * i / 60
            pts.append((x0 + (x1 - x0) * i / 60, y1 - (y1 - y0) * curva(rpm, pico) / 180))
        return pts
    if p > 0.15:
        pts = puntos(105, clamp((p - 0.15) / 0.2))
        if len(pts) > 1:
            d.line(pts, fill=(150, 150, 160), width=6)
    if prog > 0:
        pts = puntos(150, prog)
        if len(pts) > 1:
            d.line(pts, fill=(255, 60, 80), width=9)
    cv = int(lerp(105, 150, ease((p - 0.45) / 0.25))) if p > 0.3 else 105
    col = (255, 255, 255) if cv < 150 else ORO
    pegar(fr, txt(f"{cv} CV", 120, col, 10, (0, 0, 0)), (x0 + x1) / 2 + 120, y0 + 130, pop(u, 0.3 * dur))
    titulo_parte(fr, u, 4, "LA REPRO", 160)
    # coche en los rodillos
    vel = 200 + 2400 * ease((p - 0.4) / 0.3)
    giro = vel * u
    pegar_coche(fr, 570 + shake, 1343, giro, color=ROJO, aleron=True, llanta=(45, 45, 50),
                rebote=math.sin(u * 50) * 2 if p > 0.45 else 0)
    if p > 0.5:
        f = 0.6 + 0.4 * math.sin(u * 23) if (u % 1.3) < 0.7 else 0
        llamas(fr, 570 - 0.8 * 480 + shake, 1343 + 0.8 * 67, u, f)
    if p > 0.72:
        pegar(fr, txt("+45 CV", 150, ORO, 14, (80, 20, 0)), 520, 1050, pop(u, 0.72 * dur, 0.35) * (1 + 0.04 * math.sin(u * 12)),
              rot=-6)
    dibujar_bryan(fr, ctx, 900, 1800, [(0, "portatil"), (0.72, "brazos_arriba")], escala=0.72, mirar=(-0.6, -0.4),
                  salto=40 * abs(math.sin(u * 8)) if p > 0.74 else 0)


COMENTARIOS = [
    ("Laura", "La A es puro arte"), ("Dani", "B!!! más caballos"), ("Iker", "Bryan haz la B"),
    ("Sofi", "A sin dudarlo"), ("Marco", "B y a quemar rueda"), ("Nerea", "Negro mate 😍"),
    ("Hugo", "Downpipe ya"), ("Alba", "A, que se venda caro"), ("Pol", "BBBBBB"),
]


def burbuja(nombre, texto):
    key = ("bub", nombre, texto)
    if key not in _cache_txt:
        t1 = txt(nombre, 30, (120, 120, 130), black=False)
        t2 = txt(texto.replace(" 😍", ""), 38, (20, 20, 20), black=False)
        w = max(t1.width, t2.width) + 120
        c = tarjeta(w, 110, (255, 255, 255), 30).copy()
        d = ImageDraw.Draw(c)
        col = [ROJO, ORO, (40, 140, 255), (40, 180, 90)][hash(nombre) % 4]
        d.ellipse([45, 52, 105, 112], fill=col)
        d.text((62, 58), nombre[0], font=fuente(36), fill=(255, 255, 255))
        c.paste(t1, (118, 38), t1)
        c.paste(t2, (118, 72), t2)
        _cache_txt[key] = c
    return _cache_txt[key]


def esc_votacion(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, _ = fondo_pan("votacion", 30 * math.sin(u * 0.8))
    fr.paste(bg)
    # rayos girando en el lado activo
    lado = "A" if p < 0.36 else ("B" if p < 0.62 else "AB")
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    for centro, col, activo in (((300, 560), (255, 200, 40), "A" in lado), ((300, 1300), (60, 140, 255), "B" in lado)):
        if not activo:
            continue
        for i in range(12):
            a = u * 0.6 + i * math.pi / 6
            dc.polygon([centro, (centro[0] + math.cos(a) * 1600, centro[1] + math.sin(a) * 1600),
                        (centro[0] + math.cos(a + 0.12) * 1600, centro[1] + math.sin(a + 0.12) * 1600)], fill=col + (28,))
    fr.paste(capa, (0, 0), capa)
    pegar(fr, txt("¡DECIDES TÚ!", 110, (255, 255, 255), 12, ROJO), W / 2, 150, pop(u, 0.1), rot=2 * math.sin(u * 4))
    # Opción A
    pa = 1.0 if "A" in lado else 0.45
    pegar(fr, txt("A", 250, ORO, 14, (0, 0, 0)), 150, 470, pop(u, 0.06 * dur) * (1 + 0.08 * math.sin(u * 8) * (lado == "A")),
          alpha=pa)
    if u > 0.06 * dur:
        pegar_coche(fr, 650, 640, u * 30 if lado == "A" else 0, s=0.6, color=(34, 34, 38), mate=True, llanta=(220, 175, 40),
                    r_mult=1.12)
    pegar(fr, txt("NEGRO MATE\n+ LLANTAS 19\"", 50, (255, 255, 255), 6), 650, 820, pop(u, 0.12 * dur), alpha=pa)
    # Opción B
    pb = 1.0 if "B" in lado else 0.45
    pegar(fr, txt("B", 250, (70, 150, 255), 14, (0, 0, 0)), 150, 1210,
          pop(u, 0.36 * dur) * (1 + 0.08 * math.sin(u * 8) * (lado == "B")), alpha=pb)
    if u > 0.36 * dur:
        pegar_coche(fr, 600, 1260, u * 400 if lado == "B" else 0, s=0.6, color=ROJO, aleron=True, llanta=(45, 45, 50))
        if lado == "B" and (u % 1.0) < 0.5:
            llamas(fr, 600 - 0.6 * 480, 1260 + 0.6 * 67, u, 0.7)
    pegar(fr, txt("STAGE 2 · 180+ CV", 50, (255, 255, 255), 6), 560, 1430, pop(u, 0.42 * dur), alpha=pb)
    # encuesta en directo
    if p > 0.6:
        s = pop(u, 0.6 * dur)
        va = 50 + 12 * math.sin(u * 1.7) + 6 * math.sin(u * 4.1)
        barra = Image.new("RGBA", (640, 70), (0, 0, 0, 0))
        db = ImageDraw.Draw(barra)
        db.rounded_rectangle([0, 0, 640, 70], radius=35, fill=(70, 150, 255))
        db.rounded_rectangle([0, 0, int(640 * va / 100), 70], radius=35, fill=ORO)
        db.text((24, 12), f"A {int(va)}%", font=fuente(40), fill=(30, 20, 0))
        db.text((470, 12), f"{100 - int(va)}% B", font=fuente(40), fill=(255, 255, 255))
        pegar(fr, barra, 380, 1000, s)
    # comentarios que suben
    if p > 0.62:
        for i, (nom, texto) in enumerate(COMENTARIOS):
            nac = 0.62 * dur + i * 0.55
            age = u - nac
            if age < 0 or age > 3.0:
                continue
            y = 1700 - age * 260
            a = min(1, age * 4, (3 - age) * 1.5)
            pegar(fr, burbuja(nom, texto), 330 + (i % 2) * 60, y, min(1, back(age / 0.3)), alpha=a)
    dibujar_bryan(fr, ctx, 880, 1790, [(0, "normal"), (0.06, "senala_arriba_izq"), (0.36, "senala_izq"),
                                       (0.62, "encoge"), (0.78, "movil")], escala=0.72, mirar=(-0.7, -0.3))


def tarjeta_socio():
    key = "socio"
    if key not in _cache_txt:
        c = tarjeta(560, 340, (200, 20, 40), 30, borde=(ORO, 6)).copy()
        d = ImageDraw.Draw(c)
        d.ellipse([60, 70, 200, 210], fill=(255, 255, 255))
        d.text((88, 108), "BS", font=fuente(60), fill=ROJO)
        d.text((225, 70), "BRYAN SPORT", font=fuente(40), fill=(255, 255, 255))
        d.text((225, 118), "CLUB", font=fuente(40), fill=ORO)
        d.text((225, 180), "SOCIO Nº 0001", font=fuente(28, False), fill=(255, 230, 230))
        d.rounded_rectangle([60, 250, 530, 330], radius=16, fill=(255, 255, 255))
        d.text((90, 268), "TU NOMBRE AQUÍ", font=fuente(38), fill=(40, 40, 40))
        _cache_txt[key] = c
    return _cache_txt[key]


def esc_club(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, _ = fondo_pan("club", 0)
    fr.paste(bg)
    # focos
    luz = Image.new("RGB", (W, H))
    dl = ImageDraw.Draw(luz)
    for i, (sx, fase) in enumerate(((80, 0), (1000, 2))):
        a = math.sin(u * 1.3 + fase) * 0.35 + (0.25 if i == 0 else -0.25)
        tx = sx + math.sin(a) * 1700
        dl.polygon([(sx - 20, 0), (sx + 20, 0), (tx + 260, 1700), (tx - 260, 1700)], fill=(70, 60, 40))
    fr.paste(brillo(fr, luz, 25))
    confeti(fr, u, 80)
    # logo del club girando
    s = pop(u, 0.15, 0.6)
    giro = math.cos(clamp(u / 1.2) * math.pi * 4) if u < 1.2 else 1
    logo = tarjeta_socio()
    if p < 0.3:
        circ = Image.new("RGBA", (360, 360), (0, 0, 0, 0))
        dc = ImageDraw.Draw(circ)
        dc.ellipse([10, 10, 350, 350], fill=ORO)
        dc.ellipse([30, 30, 330, 330], fill=ROJO)
        dc.text((92, 110), "BS", font=fuente(130), fill=(255, 255, 255))
        pegar(fr, circ, W / 2, 520, s, esc_x=s * giro)
        pegar(fr, txt("BRYAN SPORT\nCLUB", 100, (255, 255, 255), 10, ROJO), W / 2, 850, pop(u, 0.5))
    else:
        pegar(fr, txt("BRYAN SPORT CLUB", 80, (255, 255, 255), 10, ROJO), W / 2, 260, 1)
        pegar(fr, pastilla("SÍGUEME = ENTRAS", 54, ORO, (40, 20, 0)), W / 2, 380, pop(u, 0.3 * dur))
    # carnet de socio que vuela a la luna trasera del coche
    llega = 0.66 * dur
    car_x = lerp(1500, 660, ease_out((u - 0.6 * dur) / 0.9)) if p > 0.6 else None
    if 0.3 < p:
        sc = pop(u, 0.3 * dur, 0.5)
        flip = math.cos(clamp((u - 0.3 * dur) / 0.8) * math.pi * 2)
        if p < 0.66:
            pegar(fr, logo, 650, 690, sc, esc_x=sc * flip, rot=-3)
        elif u < llega + 0.6:
            q = ease((u - llega) / 0.6)
            pegar(fr, logo, lerp(650, car_x - 60 * 0.8, q), lerp(690, 1420 - 110 * 0.8, q), lerp(1, 0.18, q))
    if 0.45 < p < 0.66:
        pegar(fr, pastilla("Comenta: CLUB + tu ciudad", 46, (255, 255, 255), (20, 20, 20)), 640, 1020,
              pop(u, 0.45 * dur))
    if car_x is not None:
        giro = (car_x - 660) * 0.5
        pegar_coche(fr, car_x, 1420, giro, s=0.8, color=ROJO, aleron=True, llanta=(200, 200, 210))
        if u > llega + 0.5:
            # pegatina con los nombres de los socios
            pg = tarjeta(150, 46, (255, 255, 255), 10, sombra=False).copy()
            ImageDraw.Draw(pg).text((14, 10), "SOCIOS BS", font=fuente(26), fill=ROJO)
            pegar(fr, pg, car_x - 60 * 0.8, 1420 - 112 * 0.8, pop(u, llega + 0.5))
            pegar(fr, txt("TU NOMBRE AQUÍ ↓", 52, ORO, 6), car_x + 60, 1150, pop(u, llega + 0.7))
    # público
    d = ImageDraw.Draw(fr)
    rnd = random.Random(8)
    for i in range(16):
        x = i * 72 + rnd.uniform(-10, 10)
        y = 1800 - abs(math.sin(u * 6 + i)) * 25
        d.ellipse([x - 40, y - 40, x + 40, y + 40], fill=(15, 8, 10))
        d.rounded_rectangle([x - 60, y + 30, x + 60, y + 200], radius=40, fill=(15, 8, 10))
        if i % 4 == 1:
            d.rounded_rectangle([x + 30, y - 110, x + 60, y - 60], radius=6, fill=(255, 255, 230))
    dibujar_bryan(fr, ctx, 210, 1660, [(0, "brazos_arriba"), (0.3, "senala_der"), (0.45, "movil"), (0.62, "senala_der"),
                                       (0.85, "pulgar")], escala=0.74, mirar=(0.6, 0),
                  salto=30 * abs(math.sin(u * 8)) if p < 0.2 else 0)


def esc_cierre(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    p = u / dur
    bg, _ = fondo_pan("calle", 60 - 60 * p)
    fr.paste(bg)
    pegar_coche(fr, 560, 1420, 0, color=ROJO, aleron=True, llanta=(45, 45, 50))
    if (u % 1.6) < 0.5:
        llamas(fr, 560 - 0.8 * 480, 1420 + 0.8 * 67, u, 0.8)
    alt = int(u * 2) % 2
    pegar(fr, txt("¿", 150, (255, 255, 255), 12), 290, 300, pop(u, 0.1))
    pegar(fr, txt("A", 190, ORO, 12), 430, 300, pop(u, 0.15) * (1.15 if alt == 0 else 1))
    pegar(fr, txt("o", 120, (255, 255, 255), 10), 560, 320, pop(u, 0.2))
    pegar(fr, txt("B", 190, (70, 150, 255), 12), 690, 300, pop(u, 0.25) * (1.15 if alt == 1 else 1))
    pegar(fr, txt("?", 150, (255, 255, 255), 12), 810, 300, pop(u, 0.3))
    pegar(fr, pastilla("PARTE 5 · MUY PRONTO", 52, ROJO), W / 2, 500, pop(u, 0.25 * dur))
    # botón de seguir con un dedo que lo pulsa
    toca = 0.45 * dur
    seguido = u > toca
    boton = pastilla("✓ SIGUIENDO" if seguido else "+ SEGUIR", 60, (70, 70, 80) if seguido else ROJO)
    sb = pop(u, 0.3 * dur) * (0.9 if abs(u - toca) < 0.1 else 1)
    pegar(fr, boton, 540, 760, sb)
    if 0.32 * dur < u < toca + 0.6:
        q = ease((u - 0.32 * dur) / (toca - 0.32 * dur))
        pegar(fr, emoji("👆", 130), lerp(900, 580, q), lerp(1100, 840, q), 1)
    if seguido:
        for i in range(8):
            age = u - toca - i * 0.06
            if 0 < age < 1.2:
                a = i * math.pi / 4
                pegar(fr, emoji("❤️", 50), 540 + math.cos(a) * age * 300, 760 + math.sin(a) * age * 300 - age * 80,
                      1, alpha=1 - age / 1.2)
    dibujar_bryan(fr, ctx, 870, 1790, [(0, "saluda"), (0.3, "senala_arriba_izq"), (0.65, "saluda")], escala=0.74,
                  mirar=(-0.3, -0.2))
    # fundido final con el logo
    if u > dur - 0.8:
        q = clamp((u - (dur - 0.8)) / 0.6)
        capa = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * q)))
        fr.paste(capa, (0, 0), capa)
        pegar(fr, txt("BRYAN SPORT", 110, ROJO, 8, (255, 255, 255)), W / 2, H / 2, q)


ESCENAS = {
    "intro": esc_intro, "diagnostico": esc_diagnostico, "mecanica": esc_mecanica, "pintura": esc_pintura,
    "repro": esc_repro, "votacion": esc_votacion, "club": esc_club, "cierre": esc_cierre,
}

# ================================================================ transición y subtítulos
def transicion(fr, q):
    """q de 0 a 1; en 0.5 la pantalla está cubierta."""
    d = ImageDraw.Draw(fr)
    x0 = lerp(-2300, 1700, q)
    wd, sk = 1900, 400
    def banda(a, b, col):
        d.polygon([(x0 + a, 0), (x0 + b, 0), (x0 + b - sk, H), (x0 + a - sk, H)], fill=col)
    banda(-140, -40, ROJO)
    banda(-40, 0, (255, 255, 255))
    banda(0, wd, (14, 14, 18))
    banda(wd, wd + 40, (255, 255, 255))
    banda(wd + 40, wd + 160, ROJO)
    if 0.35 < q < 0.65:
        s = math.sin((q - 0.35) / 0.3 * math.pi)
        pegar(fr, txt("BS", 260, ROJO, 10, (255, 255, 255)), W / 2, H / 2, s)


def grupos_subtitulos(palabras):
    grupos, act = [], []
    for w in palabras:
        largo = sum(len(x["txt"].strip()) + 1 for x in act) + len(w["txt"].strip())
        if act and (len(act) >= 4 or largo > 22 or w["ini"] - act[-1]["fin"] > 0.45):
            grupos.append(act)
            act = []
        act.append(w)
        if w["txt"].rstrip().endswith((".", ",", "?", "!", ":")):
            grupos.append(act)
            act = []
    if act:
        grupos.append(act)
    return grupos


def dibujar_subs(fr, t, grupos, y=1815):
    for i, g in enumerate(grupos):
        fin = min(g[-1]["fin"] + 0.25, grupos[i + 1][0]["ini"] if i + 1 < len(grupos) else 1e9)
        if g[0]["ini"] - 0.05 <= t < fin:
            f = fuente(64)
            d0 = ImageDraw.Draw(fr)
            textos = [w["txt"].strip().upper() for w in g]
            anchos = [d0.textlength(x + " ", font=f) for x in textos]
            total = sum(anchos)
            s = min(1, back((t - g[0]["ini"] + 0.05) / 0.2))
            capa = Image.new("RGBA", (int(total + 40), 110), (0, 0, 0, 0))
            dc = ImageDraw.Draw(capa)
            x = 20
            for w, tx, an in zip(g, textos, anchos):
                activo = w["ini"] <= t < w["fin"] + 0.05
                col = ORO if activo else (255, 255, 255)
                dc.text((x, 15), tx, font=f, fill=col, stroke_width=9, stroke_fill=(0, 0, 0))
                x += an
            if capa.width > W - 40:
                r = (W - 40) / capa.width
                capa = capa.resize((W - 40, int(capa.height * r)), Image.LANCZOS)
            pegar(fr, capa, W / 2, y, s)
            return


# ================================================================ audio
def sintetizar_sfx(tipo):
    n = lambda s: int(s * SR)
    rng = np.random.default_rng(abs(hash(tipo)) % 1000)
    if tipo == "whoosh":
        L = n(0.55)
        t = np.arange(L) / SR
        ruido = rng.standard_normal(L)
        env = np.sin(np.pi * t / t[-1]) ** 2
        # filtro paso bajo móvil sencillo
        out = np.zeros(L)
        acc = 0
        for i in range(L):
            a = 0.02 + 0.25 * env[i]
            acc += a * (ruido[i] - acc)
            out[i] = acc
        return out * env * 0.9
    if tipo == "pop":
        t = np.arange(n(0.12)) / SR
        return np.sin(2 * np.pi * (500 + 4000 * t) * t) * np.exp(-t * 35) * 0.5
    if tipo == "sello":
        t = np.arange(n(0.25)) / SR
        return (np.sin(2 * np.pi * 90 * t) * np.exp(-t * 18) + rng.standard_normal(len(t)) * np.exp(-t * 60) * 0.5) * 0.6
    if tipo in ("motor", "brrum"):
        dur = 3.2 if tipo == "motor" else 1.4
        t = np.arange(n(dur)) / SR
        f = 45 + 110 * np.clip(np.sin(np.pi * t / dur * 0.9), 0, 1) ** 1.5
        fase = 2 * np.pi * np.cumsum(f) / SR
        saw = sum(np.sin(k * fase) / k for k in range(1, 12))
        env = np.minimum(1, t / 0.1) * np.minimum(1, (dur - t) / 0.4)
        return (np.tanh(saw * 1.8) * 0.35 + rng.standard_normal(len(t)) * 0.04) * env
    if tipo == "ding":
        t = np.arange(n(0.6)) / SR
        return (np.sin(2 * np.pi * 1320 * t) + 0.5 * np.sin(2 * np.pi * 1980 * t)) * np.exp(-t * 7) * 0.3
    if tipo == "aplauso":
        t = np.arange(n(2.5)) / SR
        r = rng.standard_normal(len(t))
        clap = (rng.random(len(t)) < 0.004).astype(float)
        clap = np.convolve(clap, np.exp(-np.arange(400) / 60), mode="same")
        env = np.minimum(1, t / 0.2) * np.minimum(1, (2.5 - t) / 1.0)
        return (clap * r * 0.6 + r * 0.05) * env
    if tipo == "spray":
        t = np.arange(n(2.0)) / SR
        r = rng.standard_normal(len(t))
        r = r - np.concatenate([[0], r[:-1]]) * 0.9
        env = np.minimum(1, t / 0.1) * np.minimum(1, (2.0 - t) / 0.3)
        return r * env * 0.08
    return np.zeros(1)


SFX_SEG = {}  # efectos por escena con tiempo en segundos desde el inicio de la escena
POST = []  # capas extra que se dibujan sobre cada escena: f(fr, ctx, escena)


def eventos_sfx(escenas):
    ev = []
    P = {
        "intro": [(0.10, "pop"), (0.52, "pop")],
        "diagnostico": [(0.08, "pop"), (0.17, "sello"), (0.28, "sello"), (0.39, "sello"), (0.52, "sello"), (0.68, "ding")],
        "mecanica": [(0.14, "pop"), (0.23, "pop"), (0.33, "pop"), (0.8, "brrum")],
        "pintura": [(0.15, "spray"), (0.40, "spray"), (0.74, "ding")],
        "repro": [(0.3, "pop"), (0.45, "motor"), (0.72, "ding")],
        "votacion": [(0.06, "pop"), (0.36, "pop"), (0.6, "pop")],
        "club": [(0.05, "aplauso"), (0.3, "pop"), (0.66, "ding")],
        "cierre": [(0.15, "pop"), (0.45, "pop"), (0.46, "ding")],
    }
    for e in escenas:
        if e is not escenas[0]:
            ev.append((e["ini"] - 0.28, "whoosh", 0.7))
        for pp, tipo in P.get(e["tipo"], []):
            ev.append((e["ini"] + pp * e["dur"], tipo, 0.6))
        for seg, tipo in SFX_SEG.get(e["tipo"], []):
            ev.append((e["ini"] + seg, tipo, 0.6))
    return ev


def musica_beat(dur, bpm=96):
    L = int(dur * SR)
    out = np.zeros(L)
    beat = 60 / bpm
    rng = np.random.default_rng(1)
    t_k = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 120 * np.exp(-t_k * 25)) * t_k) * np.exp(-t_k * 9)
    t_s = np.arange(int(0.18 * SR)) / SR
    snare = rng.standard_normal(len(t_s)) * np.exp(-t_s * 22) * 0.35 + np.sin(2 * np.pi * 190 * t_s) * np.exp(-t_s * 30) * 0.3
    t_h = np.arange(int(0.05 * SR)) / SR
    hat = rng.standard_normal(len(t_h))
    hat = (hat - np.concatenate([[0], hat[:-1]])) * np.exp(-t_h * 90) * 0.12
    bajo_notas = [45, 45, 41, 41, 48, 48, 43, 43]  # La, Fa, Do, Sol
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    def add(sig, pos):
        i = int(pos * SR)
        if i >= L:
            return
        e = min(L, i + len(sig))
        out[i:e] += sig[: e - i]
    nb = int(dur / beat) + 1
    for b in range(nb):
        pos = b * beat
        add(kick * 0.8, pos)
        if b % 4 == 2:
            add(kick * 0.5, pos + beat * 0.5)
        if b % 2 == 1:
            add(snare, pos)
        add(hat, pos + beat * 0.5)
        add(hat * 0.6, pos)
        m = bajo_notas[(b // 2) % len(bajo_notas)]
        t_b = np.arange(int(beat * SR * 0.9)) / SR
        bajo = np.tanh(np.sin(2 * np.pi * f(m) * t_b) * 2) * np.exp(-t_b * 3) * 0.22
        add(bajo, pos)
    pad = mv.music(dur, "epica") * 0.8
    out = out[:L] + pad[:L]
    fade = int(1.5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out * 0.55


def preparar(guion_path):
    g = json.load(open(guion_path))
    base = os.path.dirname(os.path.abspath(guion_path))
    tmp = tempfile.mkdtemp(prefix="bryan_")
    escenas = [dict(e) for e in g["escenas"]]
    if g.get("audio"):
        src = os.path.join(base, g["audio"])
        wav = os.path.join(tmp, "voz_in.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(SR), wav], check=True)
        voz = mv.read_wav(wav)
        total = len(voz) / SR + g.get("cola", 1.2)
        for i, e in enumerate(escenas):
            e["ini"] = float(e["inicio"])
            e["fin"] = float(escenas[i + 1]["inicio"]) if i + 1 < len(escenas) else total
            e["dur"] = e["fin"] - e["ini"]
        voz = np.concatenate([voz, np.zeros(int((total - len(voz) / SR) * SR) + SR)])
    else:
        partes, cur = [], 0.0
        for i, e in enumerate(escenas):
            w = os.path.join(tmp, f"v{i}.wav")
            d = mv.tts(e["voz"], "es", g.get("velocidad_voz", 160), w, g.get("voz_modelo", mv.DEFAULT_PIPER))
            data = mv.read_wav(w)
            lead = 0.45 if i else 0.6
            e["ini"] = cur
            e["dur"] = lead + d + 0.55
            e["fin"] = cur + e["dur"]
            partes.append((cur + lead, data))
            cur = e["fin"]
        total = cur + 0.6
        escenas[-1]["fin"] = total
        escenas[-1]["dur"] = total - escenas[-1]["ini"]
        voz = np.zeros(int(total * SR) + SR)
        for t0, data in partes:
            i = int(t0 * SR)
            voz[i:i + len(data)] += data
    voz_wav = os.path.join(tmp, "voz.wav")
    mv.write_wav(voz_wav, voz)
    # envolvente para la boca
    hop = SR // FPS
    nfr = int(total * FPS) + 2
    env = np.array([np.sqrt(np.mean(voz[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(voz) else 0 for i in range(nfr)])
    ref = np.percentile(env[env > 1e-4], 90) if np.any(env > 1e-4) else 1
    env = np.clip(env / ref, 0, 1.2)
    env = np.where(env < 0.12, 0, env)
    # palabras para subtítulos
    palabras = transcribir(voz_wav, base, g, escenas)
    return dict(g=g, escenas=escenas, total=total, voz=voz, env=env, palabras=palabras, tmp=tmp, base=base)


def transcribir(voz_wav, base, g, escenas):
    cache = os.path.join(base, os.path.splitext(g.get("salida", "salida.mp4"))[0] + "_palabras.json")
    firma = [e.get("voz", "") for e in escenas] + [g.get("audio")]
    if os.path.exists(cache):
        c = json.load(open(cache))
        if c.get("firma") == firma:
            return c["palabras"]
    palabras = []
    try:
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from faster_whisper import WhisperModel
        modelo = WhisperModel(g.get("whisper", "small"), device="cpu", compute_type="int8")
        voz = mv.read_wav(voz_wav)
        idx = np.arange(0, len(voz), SR / 16000)
        voz16 = np.interp(idx, np.arange(len(voz)), voz).astype(np.float32)
        segs, _ = modelo.transcribe(voz16, language="es", word_timestamps=True, vad_filter=True,
                                    initial_prompt="Bryan Sport, repro, stage, downpipe, intercooler, CV.")
        for s in segs:
            for w in s.words:
                palabras.append({"txt": w.word, "ini": w.start, "fin": w.end})
    except Exception as ex:  # sin whisper: reparto uniforme
        print("Sin faster-whisper, subtítulos aproximados:", ex)
        for e in escenas:
            ws = e.get("voz", "").split()
            t0, t1 = e["ini"] + 0.5, e["fin"] - 0.5
            for i, w in enumerate(ws):
                palabras.append({"txt": w, "ini": t0 + (t1 - t0) * i / len(ws), "fin": t0 + (t1 - t0) * (i + 0.9) / len(ws)})
    palabras = alinear(palabras, escenas)
    json.dump({"firma": firma, "palabras": palabras}, open(cache, "w"), ensure_ascii=False, indent=0)
    return palabras


def _norm(w):
    import unicodedata
    w = unicodedata.normalize("NFD", w.lower())
    return "".join(c for c in w if c.isalnum())


def alinear(palabras, escenas):
    """Usa el texto exacto del guion con los tiempos de whisper (corrige palabras mal oídas)."""
    import difflib
    guion = [w for e in escenas for w in e.get("voz", "").split()]
    if not guion or not palabras:
        return palabras
    a = [_norm(w) for w in guion]
    b = [_norm(w["txt"]) for w in palabras]
    tiempos = [None] * len(guion)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            pw = palabras[blk.b + k]
            tiempos[blk.a + k] = (pw["ini"], pw["fin"])
    # interpolar los huecos entre anclas
    i = 0
    n = len(guion)
    while i < n:
        if tiempos[i] is not None:
            i += 1
            continue
        j = i
        while j < n and tiempos[j] is None:
            j += 1
        t0 = tiempos[i - 1][1] if i > 0 else palabras[0]["ini"]
        t1 = tiempos[j][0] if j < n else palabras[-1]["fin"]
        if t1 <= t0:
            t1 = t0 + 0.3 * (j - i)
        pesos = [len(guion[k]) + 2 for k in range(i, j)]
        tot = sum(pesos)
        acc = t0
        for k, pz in zip(range(i, j), pesos):
            d = (t1 - t0) * pz / tot
            tiempos[k] = (acc, acc + d * 0.9)
            acc += d
        i = j
    return [{"txt": w, "ini": t[0], "fin": t[1]} for w, t in zip(guion, tiempos)]


def mezclar_audio(st):
    total = st["total"]
    L = int(total * SR)
    voz = st["voz"][:L]
    voz = np.concatenate([voz, np.zeros(max(0, L - len(voz)))])
    sfx = np.zeros(L)
    for t0, tipo, vol in eventos_sfx(st["escenas"]):
        s = sintetizar_sfx(tipo) * vol
        i = int(max(0, t0) * SR)
        e = min(L, i + len(s))
        if e > i:
            sfx[i:e] += s[: e - i]
    mus = musica_beat(total) * st["g"].get("volumen_musica", 1.0)
    # bajar la música cuando habla (ducking)
    env = np.abs(voz)
    k = int(0.25 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    duck = 1 - 0.55 * np.clip(env / (np.percentile(env, 95) + 1e-9), 0, 1)
    mix_ = voz * st["g"].get("volumen_voz", 1.0) + mus[:L] * duck + sfx * 0.8
    mix_ = mix_ / max(1.0, np.max(np.abs(mix_)) / 0.97)
    out = os.path.join(st["tmp"], "mezcla.wav")
    mv.write_wav(out, mix_)
    return out


# ================================================================ render
ST = None


def frame(i):
    st = ST
    t = i / FPS
    escenas = st["escenas"]
    idx = 0
    for j, e in enumerate(escenas):
        if t >= e["ini"]:
            idx = j
    e = escenas[idx]
    ctx = {"t": t, "u": t - e["ini"], "dur": e["dur"], "habla": float(st["env"][min(i, len(st["env"]) - 1)])}
    fr = Image.new("RGB", (W, H))
    ESCENAS[e["tipo"]](fr, ctx)
    for f in POST:
        f(fr, ctx, e)
    dibujar_subs(fr, t, st["grupos"])
    for j, e2 in enumerate(escenas[1:], 1):
        q = (t - (e2["ini"] - TRANS / 2)) / TRANS
        if 0 <= q <= 1:
            transicion(fr, q)
    return fr


def render_trozo(args):
    a, b, ruta = args
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                          "-pix_fmt", "yuv420p", ruta], stdin=subprocess.PIPE)
    for i in range(a, b):
        p.stdin.write(frame(i).tobytes())
        if (i - a) % 300 == 0:
            print(f"  fotograma {i}", flush=True)
    p.stdin.close()
    p.wait()
    return ruta


def main():
    global ST
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("guion")
    ap.add_argument("--solo", help="rango de segundos, p. ej. 0-10")
    ap.add_argument("--procesos", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    st = preparar(a.guion)
    st["grupos"] = grupos_subtitulos(st["palabras"])
    fondos()  # precalcular antes de repartir el trabajo
    ST = st
    nfr = int(st["total"] * FPS)
    f0, f1 = 0, nfr
    if a.solo:
        s0, s1 = map(float, a.solo.split("-"))
        f0, f1 = int(s0 * FPS), min(nfr, int(s1 * FPS))
    print(f"Duración {st['total']:.1f}s · escenas:", ", ".join(f"{e['tipo']}@{e['ini']:.1f}" for e in st["escenas"]))
    n = max(1, a.procesos)
    cortes = [f0 + (f1 - f0) * k // n for k in range(n + 1)]
    trozos = [(cortes[k], cortes[k + 1], os.path.join(st["tmp"], f"t{k}.mp4")) for k in range(n)]
    with Pool(n) as pool:
        rutas = pool.map(render_trozo, trozos)
    lista = os.path.join(st["tmp"], "lista.txt")
    open(lista, "w").write("".join(f"file '{r}'\n" for r in rutas))
    audio = mezclar_audio(st)
    salida = os.path.join(st["base"], st["g"].get("salida", "salida.mp4"))
    if a.solo:
        salida = salida.replace(".mp4", f"_prueba.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-ss", str(f0 / FPS),
                    "-t", str((f1 - f0) / FPS), "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", salida], check=True)
    print("Vídeo listo:", salida)


if __name__ == "__main__":
    main()
