"""Arte del vídeo animado de Bryan: fondos detallados, coche y personaje (todo dibujado en local con Pillow)."""
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

W, H = 1080, 1920
FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
ROJO = (225, 30, 50)
ORO = (255, 200, 40)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


@lru_cache(None)
def fuente(size, black=True):
    return ImageFont.truetype(FONT_BLACK if black else FONT_BOLD, size)


def gradiente(w, h, c1, c2, vertical=True):
    t = np.linspace(0, 1, h if vertical else w)
    arr = np.array(c1)[None, :] * (1 - t[:, None]) + np.array(c2)[None, :] * t[:, None]
    if vertical:
        arr = np.repeat(arr[:, None, :], w, axis=1)
    else:
        arr = np.repeat(arr[None, :, :], h, axis=0)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def brillo(img, capa, radio, fuerza=1.0):
    """Suma una capa RGB desenfocada (efecto neón / luz)."""
    g = capa.filter(ImageFilter.GaussianBlur(radio))
    if fuerza != 1.0:
        g = Image.eval(g, lambda v: int(min(255, v * fuerza)))
    return ImageChops.add(img, g)


# ================================================================ FONDOS
def fondo_calle(noche=True):
    bw = 1240
    if noche:
        im = gradiente(bw, H, (12, 8, 40), (120, 40, 90))
    else:
        im = gradiente(bw, H, (40, 70, 140), (255, 150, 90))
    d = ImageDraw.Draw(im)
    rnd = random.Random(5)
    for _ in range(160):
        x, y = rnd.uniform(0, bw), rnd.uniform(0, 800)
        r = rnd.choice([1, 1, 2])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
    luz = Image.new("RGB", (bw, H))
    ld = ImageDraw.Draw(luz)
    ld.ellipse([860, 180, 1000, 320], fill=(255, 240, 210))
    d.ellipse([860, 180, 1000, 320], fill=(255, 245, 225))
    im = brillo(im, luz, 40)
    d = ImageDraw.Draw(im)
    # skyline lejano
    x = 0
    while x < bw:
        w = rnd.randint(60, 140)
        h = rnd.randint(250, 650)
        d.rectangle([x, 1150 - h, x + w, 1150], fill=(30, 20, 60))
        x += w + rnd.randint(0, 10)
    # skyline cercano con ventanas
    x = -20
    ventanas = Image.new("RGB", (bw, H))
    vd = ImageDraw.Draw(ventanas)
    while x < bw:
        w = rnd.randint(110, 200)
        h = rnd.randint(180, 480)
        top = 1150 - h
        d.rectangle([x, top, x + w, 1150], fill=(18, 12, 38))
        if rnd.random() < 0.4:
            d.rectangle([x + w // 2 - 3, top - 60, x + w // 2 + 3, top], fill=(18, 12, 38))
            vd.ellipse([x + w // 2 - 6, top - 66, x + w // 2 + 6, top - 54], fill=(255, 40, 40))
        for wy in range(top + 20, 1130, 34):
            for wx in range(x + 14, x + w - 20, 30):
                if rnd.random() < 0.35:
                    c = rnd.choice([(255, 210, 120), (255, 230, 170), (120, 200, 255)])
                    d.rectangle([wx, wy, wx + 14, wy + 18], fill=c)
                    vd.rectangle([wx, wy, wx + 14, wy + 18], fill=tuple(v // 2 for v in c))
        x += w + rnd.randint(4, 30)
    im = brillo(im, ventanas, 8)
    d = ImageDraw.Draw(im)
    # acera y carretera mojada
    d.rectangle([0, 1150, bw, 1200], fill=(60, 55, 75))
    d.rectangle([0, 1200, bw, H], fill=(28, 26, 38))
    refl = im.crop((0, 600, bw, 1150)).transpose(Image.FLIP_TOP_BOTTOM).resize((bw, 720))
    refl = refl.filter(ImageFilter.GaussianBlur(6))
    mask = gradiente(bw, 720, (110, 110, 110), (0, 0, 0)).convert("L")
    im.paste(refl, (0, 1200), mask)
    d = ImageDraw.Draw(im)
    for xx in range(-100, bw, 260):
        d.polygon([(xx, 1640), (xx + 150, 1640), (xx + 140, 1660), (xx - 10, 1660)], fill=(230, 220, 160))
    # farolas
    luz = Image.new("RGB", (bw, H))
    ld = ImageDraw.Draw(luz)
    for fx in (120, 640, 1160):
        d.rectangle([fx - 7, 760, fx + 7, 1190], fill=(25, 25, 35))
        d.line([(fx, 765), (fx + 70, 750)], fill=(25, 25, 35), width=10)
        d.ellipse([fx + 50, 740, fx + 100, 770], fill=(255, 230, 160))
        ld.polygon([(fx + 60, 770), (fx + 90, 770), (fx + 230, 1200), (fx - 80, 1200)], fill=(70, 55, 25))
        ld.ellipse([fx + 30, 720, fx + 120, 790], fill=(255, 220, 140))
    im = brillo(im, luz, 30)
    return im


def _ladrillos(d, x0, y0, x1, y1, base, rnd):
    bh, bwid = 36, 90
    row = 0
    for y in range(y0, y1, bh):
        off = (bwid // 2) * (row % 2)
        for x in range(x0 - off, x1, bwid):
            c = tuple(max(0, min(255, v + rnd.randint(-14, 14))) for v in base)
            d.rectangle([x + 3, y + 3, x + bwid - 3, y + bh - 3], fill=c)
        row += 1


def _llave(d, x, y, s, c):
    d.rounded_rectangle([x - 8 * s, y, x + 8 * s, y + 120 * s], radius=6 * s, fill=c)
    d.ellipse([x - 22 * s, y - 30 * s, x + 22 * s, y + 10 * s], fill=c)
    d.rectangle([x - 8 * s, y - 34 * s, x + 8 * s, y - 12 * s], fill=(0, 0, 0, 0) if False else (40, 45, 55))


def fondo_taller():
    bw = 1240
    rnd = random.Random(11)
    im = Image.new("RGB", (bw, H), (30, 32, 40))
    d = ImageDraw.Draw(im)
    _ladrillos(d, 0, 0, bw, 1180, (70, 48, 44), rnd)
    # oscurecer arriba/abajo
    sombra = gradiente(bw, 1180, (0, 0, 0), (0, 0, 0))
    mask = gradiente(bw, 1180, (170, 170, 170), (40, 40, 40)).convert("L")
    im.paste(sombra, (0, 0), mask)
    d = ImageDraw.Draw(im)
    # panel de herramientas
    d.rounded_rectangle([60, 560, 560, 960], radius=10, fill=(60, 66, 76))
    for yy in range(580, 950, 28):
        for xx in range(80, 545, 28):
            d.ellipse([xx - 3, yy - 3, xx + 3, yy + 3], fill=(40, 44, 52))
    herr = (170, 178, 190)
    for i, xx in enumerate(range(110, 330, 45)):
        s = 0.7 + i * 0.12
        _llave(d, xx, 620, s * 0.9, herr)
    d.rectangle([360, 620, 380, 760], fill=(150, 90, 40))
    d.rounded_rectangle([335, 600, 405, 640], radius=8, fill=herr)
    for i, xx in enumerate(range(440, 540, 30)):
        d.rectangle([xx - 4, 700, xx + 4, 830], fill=herr)
        d.rounded_rectangle([xx - 10, 620, xx + 10, 705], radius=6, fill=[ROJO, (240, 200, 30), (40, 120, 220), (40, 170, 90)][i % 4])
    # estantería con neumáticos
    d.rectangle([700, 600, 1180, 615], fill=(90, 95, 105))
    d.rectangle([700, 880, 1180, 895], fill=(90, 95, 105))
    for xx in range(720, 1180, 110):
        for k, yy in enumerate([600, 880]):
            d.ellipse([xx, yy - 150, xx + 100, yy], fill=(20, 20, 22))
            d.ellipse([xx + 28, yy - 122, xx + 72, yy - 28], fill=(50, 50, 55))
    d.rectangle([700, 600, 712, 1180], fill=(80, 85, 95))
    d.rectangle([1168, 600, 1180, 1180], fill=(80, 85, 95))
    # barriles
    for bx, col in ((1010, (30, 90, 170)), (1110, ROJO)):
        d.rounded_rectangle([bx - 45, 1000, bx + 45, 1180], radius=8, fill=col)
        for yy in (1040, 1140):
            d.rectangle([bx - 45, yy, bx + 45, yy + 8], fill=tuple(v // 2 for v in col))
    # carro de herramientas
    d.rounded_rectangle([90, 990, 380, 1180], radius=12, fill=(190, 25, 40))
    for yy in range(1010, 1170, 40):
        d.rectangle([105, yy, 365, yy + 30], fill=(160, 18, 32))
        d.rectangle([200, yy + 12, 270, yy + 18], fill=(220, 220, 220))
    # suelo epoxi
    suelo = gradiente(bw, H - 1180, (70, 74, 84), (25, 26, 32))
    im.paste(suelo, (0, 1180))
    refl = im.crop((0, 700, bw, 1180)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(5))
    im.paste(refl, (0, 1180), gradiente(bw, 480, (70, 70, 70), (0, 0, 0)).convert("L"))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1176, bw, 1186], fill=(20, 20, 24))
    for xx in range(0, bw, 120):
        d.polygon([(xx, 1500), (xx + 60, 1500), (xx + 30, 1525), (xx - 30, 1525)], fill=(230, 180, 0))
    # lámparas fluorescentes con conos de luz
    luz = Image.new("RGB", (bw, H))
    ld = ImageDraw.Draw(luz)
    for lx in (300, 900):
        d.line([(lx - 120, 0), (lx - 120, 90)], fill=(20, 20, 20), width=4)
        d.line([(lx + 120, 0), (lx + 120, 90)], fill=(20, 20, 20), width=4)
        d.rounded_rectangle([lx - 170, 90, lx + 170, 115], radius=8, fill=(235, 245, 255))
        ld.polygon([(lx - 170, 115), (lx + 170, 115), (lx + 420, 1500), (lx - 420, 1500)], fill=(38, 42, 46))
        ld.rounded_rectangle([lx - 180, 80, lx + 180, 125], radius=10, fill=(200, 220, 255))
    im = brillo(im, luz, 35)
    return im


def neon_bs(apagado=False):
    """Letrero de neón BRYAN SPORT (capa RGBA con brillo)."""
    w, h = 760, 230
    capa = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(capa)
    col = (90, 20, 30) if apagado else (255, 50, 80)
    f = fuente(92)
    tw = d.textlength("BRYAN SPORT", font=f)
    d.text(((w - tw) / 2, 50), "BRYAN SPORT", font=f, fill=col)
    d.rounded_rectangle([20, 10, w - 20, h - 20], radius=30, outline=col, width=8)
    if not apagado:
        capa = brillo(capa, capa, 18, 1.6)
        capa = brillo(capa, capa, 4)
    alpha = capa.convert("L").point(lambda v: min(255, v * 2))
    out = capa.convert("RGBA")
    out.putalpha(alpha)
    return out


def fondo_pintura():
    bw = 1240
    im = gradiente(bw, H, (190, 200, 210), (120, 130, 140))
    d = ImageDraw.Draw(im)
    for xx in range(0, bw, 155):
        d.rectangle([xx, 0, xx + 6, 1180], fill=(150, 160, 170))
    for yy in range(140, 1180, 260):
        d.rectangle([0, yy, bw, yy + 4], fill=(160, 168, 178))
    luz = Image.new("RGB", (bw, H))
    ld = ImageDraw.Draw(luz)
    for lx in range(80, bw, 280):
        d.rounded_rectangle([lx, 30, lx + 200, 70], radius=6, fill=(255, 255, 255))
        ld.rounded_rectangle([lx - 20, 20, lx + 220, 80], radius=10, fill=(200, 200, 200))
    im = brillo(im, luz, 30)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1180, bw, H], fill=(85, 90, 98))
    for xx in range(0, bw, 40):
        d.line([(xx, 1180), (xx, H)], fill=(70, 75, 82), width=4)
    for yy in range(1180, H, 40):
        d.line([(0, yy), (bw, yy)], fill=(70, 75, 82), width=4)
    # plásticos de protección
    for px in (20, 1120):
        d.polygon([(px, 0), (px + 100, 0), (px + 120, 1180), (px - 20, 1180)], fill=(205, 215, 225))
    return im


def fondo_banco():
    bw = 1240
    im = gradiente(bw, H, (6, 8, 20), (14, 22, 45))
    d = ImageDraw.Draw(im)
    rnd = random.Random(3)
    for yy in range(0, 1180, 120):
        for xx in range(0, bw, 120):
            c = 16 + rnd.randint(0, 8)
            d.rectangle([xx + 4, yy + 4, xx + 116, yy + 116], fill=(c, c + 4, c + 14))
    luz = Image.new("RGB", (bw, H))
    ld = ImageDraw.Draw(luz)
    for yy in (180, 1160):
        ld.rectangle([0, yy, bw, yy + 8], fill=(0, 170, 255))
        d.rectangle([0, yy, bw, yy + 8], fill=(150, 230, 255))
    # pantalla grande (el contenido se dibuja en cada fotograma)
    d.rounded_rectangle([190, 330, 1050, 860], radius=20, fill=(10, 14, 22))
    ld.rounded_rectangle([180, 320, 1060, 870], radius=24, fill=(0, 60, 110))
    d.rectangle([0, 1180, bw, H], fill=(18, 20, 28))
    # rodillos
    for rx in (400, 900):
        d.rounded_rectangle([rx - 160, 1488, rx + 160, 1530], radius=20, fill=(60, 64, 72))
        ld.rectangle([rx - 160, 1530, rx + 160, 1540], fill=(0, 120, 200))
    im = brillo(im, luz, 25)
    d = ImageDraw.Draw(im)
    for xx in range(0, bw, 90):
        d.line([(xx, 1180), (xx * 1.4 - 250, H)], fill=(28, 30, 40), width=3)
    return im


def fondo_votacion():
    im = Image.new("RGB", (W + 160, H))
    a = gradiente(W + 160, H, (40, 32, 10), (8, 6, 2))
    b = gradiente(W + 160, H, (10, 30, 90), (2, 6, 25))
    mask = Image.new("L", (W + 160, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (W + 160, 0), (W + 160, 820), (0, 1100)], fill=255)
    im.paste(b, (0, 0))
    im.paste(a, (0, 0), mask)
    d = ImageDraw.Draw(im)
    d.line([(0, 1100), (W + 160, 820)], fill=(255, 255, 255), width=14)
    return im


def fondo_club():
    bw = 1240
    im = Image.new("RGB", (bw, H))
    d = ImageDraw.Draw(im)
    # telón
    for xx in range(0, bw, 60):
        for k in range(60):
            v = 0.55 + 0.45 * math.cos((k / 60) * math.pi * 2)
            d.line([(xx + k, 0), (xx + k, 1250)], fill=(int(150 * v), int(10 * v), int(25 * v)))
    sombra = Image.new("RGB", (bw, 1250))
    im.paste(sombra, (0, 0), gradiente(bw, 1250, (60, 60, 60), (200, 200, 200)).convert("L"))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1180, bw, H], fill=(25, 15, 15))
    d.rectangle([0, 1180, bw, 1210], fill=(90, 50, 30))
    for xx in range(0, bw, 90):
        d.rectangle([xx, 1210, xx + 86, 1260], fill=(70, 40, 24))
    return im


@lru_cache(None)
def fondos():
    return {
        "calle": fondo_calle(),
        "taller": fondo_taller(),
        "pintura": fondo_pintura(),
        "banco": fondo_banco(),
        "votacion": fondo_votacion(),
        "club": fondo_club(),
    }


# ================================================================ COCHE
CAR_BODY = [(-460, 90), (-470, 10), (-430, -30), (-250, -60), (-140, -170), (150, -175), (290, -70),
            (440, -45), (470, 10), (465, 90)]
WHEELS = (-280, 290)


@lru_cache(None)
def coche_sprite(color, oxido=False, aleron=False, mate=False, s=0.8):
    """Carrocería sin ruedas. Devuelve (RGBA, ancla_x, ancla_y) con ancla en el centro del eje."""
    k = 2  # supermuestreo
    S = s * k
    w, h = int(1000 * S), int(420 * S)
    cx, cy = w / 2, int(250 * S)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P = lambda pts: [(cx + x * S, cy + y * S) for x, y in pts]
    d.polygon(P(CAR_BODY), fill=color + (255,))
    # sombreado: degradado vertical dentro de la carrocería
    body_mask = im.split()[3]
    luz = gradiente(w, h, (255, 255, 255), (0, 0, 0))
    top = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    a = Image.eval(luz.convert("L"), lambda v: int(v * (0.18 if mate else 0.45)))
    top.putalpha(ImageChops.multiply(a, body_mask))
    im = Image.alpha_composite(im, top)
    d = ImageDraw.Draw(im)
    osc = tuple(max(0, c - 60) for c in color)
    d.polygon(P([(-460, 55), (465, 55), (465, 92), (-460, 92)]), fill=osc + (255,))
    # pasos de rueda
    for wx in WHEELS:
        d.pieslice(P([(wx - 112, -22), (wx + 112, 202)]), 180, 360, fill=(12, 12, 14, 255))
    # ventanas
    vid = (30, 42, 62, 255)
    d.polygon(P([(-120, -150), (-5, -155), (-5, -70), (-215, -65)]), fill=vid)
    d.polygon(P([(15, -155), (140, -155), (250, -72), (15, -70)]), fill=vid)
    if not mate:
        d.polygon(P([(-95, -146), (-55, -148), (-150, -70), (-185, -68)]), fill=(150, 175, 210, 160))
        d.polygon(P([(60, -150), (85, -150), (30, -72), (5, -72)]), fill=(150, 175, 210, 110))
        d.line(P([(-420, -22), (430, -32)]), fill=tuple(min(255, c + 90) for c in color) + (200,), width=int(5 * S))
    d.line(P([(5, -150), (5, 55)]), fill=osc + (255,), width=int(4 * S))
    d.line(P([(-250, -55), (-250, 55)]), fill=osc + (255,), width=int(3 * S))
    d.line(P([(280, -62), (280, 55)]), fill=osc + (255,), width=int(3 * S))
    for hx in (-120, 150):
        d.rounded_rectangle(P([(hx, -30), (hx + 50, -20)]), radius=int(3 * S), fill=osc + (255,))
    d.polygon(P([(250, -72), (290, -80), (300, -55), (265, -55)]), fill=osc + (255,))  # retrovisor
    d.ellipse(P([(415, -32), (468, 2)]), fill=(255, 245, 200, 255))
    d.rectangle(P([(-472, -18), (-448, 18)]), fill=(220, 20, 30, 255))
    d.rectangle(P([(440, 20), (470, 50)]), fill=(20, 20, 24, 255))  # rejilla
    d.rounded_rectangle(P([(-480, 60), (-430, 75)]), radius=int(5 * S), fill=(160, 160, 170, 255))  # escape
    if aleron:
        d.polygon(P([(-440, -55), (-480, -105), (-320, -110), (-300, -62)]), fill=(20, 20, 24, 255))
        d.polygon(P([(-210, -64), (380, -40), (380, -30), (-210, -54)]), fill=(255, 255, 255, 230))
    if oxido:
        rnd = random.Random(3)
        for _ in range(70):
            x, y = rnd.uniform(-430, 430), rnd.uniform(-40, 70)
            r = rnd.uniform(5, 24)
            d.ellipse(P([(x - r, y - r * .7), (x + r, y + r * .7)]),
                      fill=(rnd.randint(110, 150), rnd.randint(55, 75), 30, 255))
        d.line(P([(150, -20), (230, 40), (270, 20)]), fill=(20, 20, 20, 255), width=int(4 * S))
        d.polygon(P([(-200, -40), (-160, -45), (-170, 20)]), fill=(80, 80, 80, 255))
    im = im.resize((w // k, h // k), Image.LANCZOS)
    return im, cx / k, cy / k


@lru_cache(None)
def rueda_sprite(llanta, s=0.8, ang_q=0, r_mult=1.0):
    k = 2
    R = 92 * r_mult * s * k
    size = int(R * 2 + 30 * k)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    d.ellipse([c - R - 8 * k, c - R - 8 * k, c + R + 8 * k, c + R + 8 * k], fill=(14, 14, 14, 255))
    d.ellipse([c - R, c - R, c + R, c + R], fill=(28, 28, 30, 255))
    r2 = R * .64
    d.ellipse([c - r2, c - r2, c + r2, c + r2], fill=llanta + (255,))
    d.ellipse([c - r2 * .8, c - r2 * .8, c + r2 * .8, c + r2 * .8], fill=tuple(max(0, v - 70) for v in llanta) + (255,))
    for j in range(5):
        a = math.radians(ang_q + j * 72)
        d.line([(c, c), (c + math.cos(a) * r2 * .95, c + math.sin(a) * r2 * .95)], fill=llanta + (255,), width=int(16 * s * k))
    d.ellipse([c - 16 * s * k, c - 16 * s * k, c + 16 * s * k, c + 16 * s * k], fill=(80, 80, 85, 255))
    im = im.resize((size // k, size // k), Image.LANCZOS)
    return im


def pegar_coche(frame, x, y, giro, s=0.8, color=(130, 132, 128), oxido=False, aleron=False, mate=False,
                llanta=(190, 190, 200), r_mult=1.0, rebote=0.0, carroceria=None):
    """Pega el coche con el centro del eje en (x, y). giro = ángulo de rueda en grados."""
    # sombra
    sh = sombra_sprite(s)
    frame.paste((0, 0, 0), (int(x - sh.width / 2), int(y + 60 * s)), sh)
    q = int(round((giro % 72) / 3)) * 3
    for wx in WHEELS:
        rw = rueda_sprite(llanta, s, q, r_mult)
        frame.paste(rw, (int(x + wx * s - rw.width / 2), int(y + 90 * s - rw.height / 2)), rw)
    body = carroceria or coche_sprite(color, oxido, aleron, mate, s)
    im, ax, ay = body
    frame.paste(im, (int(x - ax), int(y - ay + rebote)), im)


@lru_cache(None)
def sombra_sprite(s):
    w, h = int(1100 * s), int(110 * s)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([40 * s, 20 * s, w - 40 * s, h - 20 * s], fill=190)
    return m.filter(ImageFilter.GaussianBlur(18 * s))


# ================================================================ BRYAN
PIEL = (226, 172, 128)
PIEL_OSC = (196, 140, 100)
SUDADERA = (215, 32, 48)
SUD_OSC = (165, 20, 35)
VAQUERO = (40, 62, 115)

# pose = (brazo izq [hombro, codo], brazo der [hombro, codo]); 0 = abajo, 90 = horizontal hacia fuera,
# 180 = arriba, negativo = hacia dentro (cruzando el cuerpo).
POSES = {
    "normal": ((12, 8), (12, 8)),
    "senala_der": ((12, 8), (95, 92)),
    "senala_izq": ((95, 92), (12, 8)),
    "senala_arriba_der": ((12, 8), (150, 165)),
    "senala_arriba_izq": ((150, 165), (12, 8)),
    "saluda": ((12, 8), (140, 170)),
    "pulgar": ((12, 8), (40, 155)),
    "brazos_arriba": ((155, 168), (155, 168)),
    "jarras": ((40, -45), (40, -45)),
    "llave": ((12, 8), (55, 125)),
    "carpeta": ((25, -85), (12, 8)),
    "portatil": ((22, -78), (22, -78)),
    "pistola": ((12, 8), (80, 100)),
    "movil": ((25, -85), (12, 8)),
    "encoge": ((45, -60), (45, -60)),
    "lupa": ((12, 8), (70, 135)),
    "piensa": ((12, 8), (35, 160)),
}


def _brazo(d, sx, sy, a1, a2, lado, k, sacudida=0):
    L1, L2 = 125 * k, 115 * k
    def dirv(a):
        r = math.radians(a)
        return lado * math.sin(r), math.cos(r)
    dx, dy = dirv(a1)
    ex, ey = sx + dx * L1, sy + dy * L1
    dx, dy = dirv(a2 + sacudida)
    hx, hy = ex + dx * L2, ey + dy * L2
    grosor = int(58 * k)
    for (x0, y0, x1, y1) in ((sx, sy, ex, ey), (ex, ey, hx, hy)):
        d.line([(x0, y0), (x1, y1)], fill=SUD_OSC, width=grosor + int(6 * k))
        d.line([(x0, y0), (x1, y1)], fill=SUDADERA, width=grosor)
        r = grosor / 2
        d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=SUDADERA)
    d.ellipse([sx - 30 * k, sy - 30 * k, sx + 30 * k, sy + 30 * k], fill=SUDADERA)
    # puño de la manga
    d.ellipse([hx - 31 * k, hy - 31 * k, hx + 31 * k, hy + 31 * k], fill=(240, 240, 240))
    return hx, hy, math.degrees(math.atan2(hy - ey, hx - ex))


def _mano(d, hx, hy, ang, k, tipo="mano"):
    r = 27 * k
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=PIEL)
    if tipo == "pulgar":
        d.rounded_rectangle([hx - 9 * k, hy - 60 * k, hx + 9 * k, hy - 5 * k], radius=int(9 * k), fill=PIEL)
    elif tipo == "dedo":
        a = math.radians(ang)
        fx, fy = hx + math.cos(a) * 52 * k, hy + math.sin(a) * 52 * k
        d.line([(hx, hy), (fx, fy)], fill=PIEL, width=int(17 * k))
        d.ellipse([fx - 8.5 * k, fy - 8.5 * k, fx + 8.5 * k, fy + 8.5 * k], fill=PIEL)


def bryan_sprite(t, pose_a, pose_b, mezcla, habla, mirar=(0.0, 0.0), excitado=0.0, objeto=None, salto=0.0,
                 escala=1.0, gesto=0.0):
    """Dibuja a Bryan. Devuelve (RGBA, ancla_x, ancla_y) con ancla entre los pies."""
    k = 2 * escala
    w, h = int(640 * k), int(1060 * k)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w / 2
    pies = h - 40 * k
    resp = math.sin(t * 2 * math.pi * 0.45) * 5 * k
    bote = -abs(math.sin(t * 9)) * 10 * k * habla
    oy = resp + bote - salto * k
    # piernas
    for lx in (-50, 50):
        d.rounded_rectangle([cx + lx * k - 36 * k, pies - 330 * k - salto * k * 0.3 + oy * 0.3, cx + lx * k + 36 * k,
                             pies - 30 * k], radius=int(20 * k), fill=VAQUERO)
        d.line([(cx + lx * k + 12 * k, pies - 300 * k), (cx + lx * k + 12 * k, pies - 60 * k)], fill=(55, 80, 140),
               width=int(4 * k))
        # zapatillas
        sx = cx + lx * k + (lx / 50) * 18 * k
        d.rounded_rectangle([sx - 62 * k, pies - 48 * k, sx + 62 * k, pies + 8 * k], radius=int(26 * k), fill=(245, 245, 245))
        d.rectangle([sx - 60 * k, pies - 2 * k, sx + 60 * k, pies + 8 * k], fill=(200, 200, 205))
        d.line([(sx - 30 * k, pies - 30 * k), (sx + 20 * k, pies - 20 * k)], fill=ROJO, width=int(8 * k))
    # torso (sudadera)
    tt, tb = pies - 640 * k + oy, pies - 300 * k + oy * 0.4
    d.rounded_rectangle([cx - 135 * k, tt, cx + 135 * k, tb], radius=int(60 * k), fill=SUDADERA)
    d.rounded_rectangle([cx - 135 * k, tb - 45 * k, cx + 135 * k, tb], radius=int(18 * k), fill=SUD_OSC)
    d.rounded_rectangle([cx - 80 * k, tb - 150 * k, cx + 80 * k, tb - 60 * k], radius=int(20 * k), fill=SUD_OSC)
    # capucha detrás del cuello y cordones
    d.ellipse([cx - 95 * k, tt - 30 * k, cx + 95 * k, tt + 60 * k], fill=SUD_OSC)
    d.line([(cx - 25 * k, tt + 40 * k), (cx - 30 * k, tt + 130 * k)], fill=(245, 245, 245), width=int(6 * k))
    d.line([(cx + 25 * k, tt + 40 * k), (cx + 30 * k, tt + 130 * k)], fill=(245, 245, 245), width=int(6 * k))
    # logo BS
    d.ellipse([cx - 52 * k, tt + 120 * k, cx + 52 * k, tt + 224 * k], fill=(255, 255, 255))
    f = fuente(int(52 * k))
    tw = d.textlength("BS", font=f)
    d.text((cx - tw / 2, tt + 140 * k), "BS", font=f, fill=SUDADERA)
    # cabeza
    hy = tt - 115 * k
    hr = 118 * k
    d.rectangle([cx - 40 * k, hy + 70 * k, cx + 40 * k, tt + 20 * k], fill=PIEL_OSC)  # cuello
    for ex in (-1, 1):
        d.ellipse([cx + ex * hr - 22 * k, hy - 10 * k, cx + ex * hr + 22 * k, hy + 45 * k], fill=PIEL_OSC)
    d.ellipse([cx - hr, hy - hr, cx + hr, hy + hr * 1.05], fill=PIEL)
    # pelo (lados degradados) y gorra
    d.chord([cx - hr - 2 * k, hy - hr - 4 * k, cx + hr + 2 * k, hy + hr * 0.5], 180, 360, fill=(45, 30, 22))
    d.chord([cx - hr - 8 * k, hy - hr - 30 * k, cx + hr + 8 * k, hy + hr * 0.25], 180, 360, fill=(22, 22, 26))
    d.rounded_rectangle([cx - hr - 8 * k, hy - 22 * k, cx + hr + 70 * k, hy + 2 * k], radius=int(12 * k), fill=ROJO)
    d.ellipse([cx - 6 * k, hy - hr - 36 * k, cx + 6 * k, hy - hr - 24 * k], fill=ROJO)
    f2 = fuente(int(40 * k))
    tw = d.textlength("BS", font=f2)
    d.text((cx - tw / 2, hy - 80 * k), "BS", font=f2, fill=(255, 255, 255))
    # ojos
    parpadeo = 1.0
    ph = (t * 0.31) % 1
    if ph < 0.035:
        parpadeo = 0.1
    mx, my = mirar
    for ex in (-42, 42):
        ox, oyy = cx + ex * k, hy + 32 * k
        ew, eh = 25 * k, 30 * k * parpadeo
        d.ellipse([ox - ew, oyy - eh, ox + ew, oyy + eh], fill=(255, 255, 255))
        if parpadeo > 0.5:
            px, py = ox + mx * 10 * k, oyy + my * 10 * k
            d.ellipse([px - 13 * k, py - 13 * k, px + 13 * k, py + 13 * k], fill=(55, 35, 20))
            d.ellipse([px - 7 * k, py - 7 * k, px + 7 * k, py + 7 * k], fill=(10, 10, 10))
            d.ellipse([px + 2 * k, py - 9 * k, px + 7 * k, py - 4 * k], fill=(255, 255, 255))
        cej = oyy - 44 * k - excitado * 14 * k
        inc = -6 * k * (1 if ex < 0 else -1) * (1 - excitado)
        d.line([(ox - 26 * k, cej + inc), (ox + 26 * k, cej - inc)], fill=(45, 30, 22), width=int(10 * k))
    # nariz
    d.arc([cx - 16 * k, hy + 50 * k, cx + 16 * k, hy + 80 * k], 0, 180, fill=PIEL_OSC, width=int(6 * k))
    # boca
    my0 = hy + 112 * k
    ab = clamp(habla)
    if ab > 0.08:
        bw_, bh_ = (34 + 10 * ab) * k, (8 + 34 * ab) * k
        d.ellipse([cx - bw_, my0 - bh_ * 0.4, cx + bw_, my0 + bh_], fill=(90, 20, 30))
        d.rectangle([cx - bw_ * 0.7, my0 - bh_ * 0.4, cx + bw_ * 0.7, my0 - bh_ * 0.4 + 9 * k], fill=(255, 255, 255))
        d.ellipse([cx - bw_ * 0.5, my0 + bh_ * 0.35, cx + bw_ * 0.5, my0 + bh_ * 0.95], fill=(230, 90, 100))
    else:
        d.arc([cx - 40 * k, my0 - 32 * k, cx + 40 * k, my0 + 18 * k], 20, 160, fill=(90, 30, 30), width=int(9 * k))
    # mejillas
    for ex in (-1, 1):
        d.ellipse([cx + ex * 72 * k - 18 * k, hy + 72 * k, cx + ex * 72 * k + 18 * k, hy + 92 * k], fill=(235, 140, 120))
    # brazos
    pa, pb = POSES[pose_a], POSES[pose_b]
    m = mezcla * mezcla * (3 - 2 * mezcla)
    sy = tt + 60 * k
    resultados = []
    for i, (lado, sx) in enumerate(((-1, cx - 128 * k), (1, cx + 128 * k))):
        a1 = lerp(pa[i][0], pb[i][0], m)
        a2 = lerp(pa[i][1], pb[i][1], m)
        sac = 0
        if pose_b in ("saluda",) and i == 1:
            sac = math.sin(t * 14) * 22 * m
        if pose_b == "brazos_arriba":
            sac = math.sin(t * 16 + i) * 10 * m
        if pose_b == "llave" and i == 1:
            sac = math.sin(t * 10) * 15 * m
        a1 += gesto * math.sin(t * 5 + i) * 8
        resultados.append(_brazo(d, sx, sy, a1, a2, lado, k, sac))
    # manos y objetos
    for i, (hx, hy2, ang) in enumerate(resultados):
        tipo = "mano"
        if pose_b.startswith("senala") and ((pose_b.endswith("der") and i == 1) or (pose_b.endswith("izq") and i == 0)):
            tipo = "dedo"
        if pose_b == "pulgar" and i == 1:
            tipo = "pulgar"
        _mano(d, hx, hy2, ang, k, tipo)
    if objeto:
        (lx, ly, _), (rx, ry, _) = resultados
        _objeto(d, objeto, lx, ly, rx, ry, k, t, cx, tt)
    im = im.resize((int(w / 2), int(h / 2)), Image.LANCZOS)
    return im, w / 4, pies / 2


def _objeto(d, obj, lx, ly, rx, ry, k, t, cx, tt):
    if obj == "llave":
        a = math.radians(-60 + math.sin(t * 10) * 15)
        ex, ey = rx + math.cos(a) * 150 * k, ry + math.sin(a) * 150 * k
        d.line([(rx, ry), (ex, ey)], fill=(185, 190, 200), width=int(22 * k))
        d.ellipse([ex - 32 * k, ey - 32 * k, ex + 32 * k, ey + 32 * k], fill=(185, 190, 200))
        d.ellipse([ex - 14 * k, ey - 14 * k, ex + 14 * k, ey + 14 * k], fill=(0, 0, 0, 0))
        _mano(d, rx, ry, 0, k)
    elif obj == "carpeta":
        d.rounded_rectangle([lx - 20 * k, ly - 150 * k, lx + 150 * k, ly + 60 * k], radius=int(8 * k), fill=(150, 105, 60))
        d.rectangle([lx - 5 * k, ly - 135 * k, lx + 135 * k, ly + 45 * k], fill=(250, 250, 245))
        for j in range(5):
            yy = ly - 110 * k + j * 30 * k
            d.line([(lx + 15 * k, yy), (lx + 115 * k, yy)], fill=(150, 150, 160), width=int(5 * k))
        d.rounded_rectangle([lx + 35 * k, ly - 160 * k, lx + 95 * k, ly - 135 * k], radius=int(6 * k), fill=(180, 180, 190))
        _mano(d, lx, ly, 0, k)
    elif obj == "portatil":
        x0, x1 = min(lx, rx) - 60 * k, max(lx, rx) + 60 * k
        y = min(ly, ry) - 10 * k
        d.polygon([(x0 + 20 * k, y - 170 * k), (x1 - 20 * k, y - 170 * k), (x1 - 30 * k, y), (x0 + 30 * k, y)], fill=(40, 44, 52))
        d.polygon([(x0 + 35 * k, y - 155 * k), (x1 - 35 * k, y - 155 * k), (x1 - 42 * k, y - 15 * k), (x0 + 42 * k, y - 15 * k)],
                  fill=(0, 140, 220))
        f = fuente(int(34 * k))
        tx = "REPRO"
        tw = d.textlength(tx, font=f)
        d.text(((x0 + x1) / 2 - tw / 2, y - 110 * k), tx, font=f, fill=(255, 255, 255))
        prog = (t * 0.6) % 1
        d.rectangle([x0 + 60 * k, y - 50 * k, x0 + 60 * k + (x1 - x0 - 120 * k) * prog, y - 35 * k], fill=(120, 255, 140))
        d.rectangle([x0, y, x1, y + 22 * k], fill=(70, 74, 84))
        _mano(d, lx, ly, 0, k)
        _mano(d, rx, ry, 0, k)
    elif obj == "pistola":
        d.rounded_rectangle([rx - 20 * k, ry - 40 * k, rx + 120 * k, ry + 5 * k], radius=int(10 * k), fill=(70, 75, 85))
        d.rectangle([rx + 110 * k, ry - 30 * k, rx + 160 * k, ry - 15 * k], fill=(180, 180, 190))
        d.rounded_rectangle([rx + 10 * k, ry - 120 * k, rx + 70 * k, ry - 40 * k], radius=int(10 * k), fill=(200, 30, 45))
        _mano(d, rx, ry, 0, k)
    elif obj == "lupa":
        a = math.radians(-50)
        ex, ey = rx + math.cos(a) * 110 * k, ry + math.sin(a) * 110 * k
        d.line([(rx, ry), (ex, ey)], fill=(90, 60, 30), width=int(20 * k))
        d.ellipse([ex - 62 * k, ey - 62 * k, ex + 62 * k, ey + 62 * k], fill=(60, 60, 70))
        d.ellipse([ex - 50 * k, ey - 50 * k, ex + 50 * k, ey + 50 * k], fill=(190, 225, 255))
        d.ellipse([ex - 30 * k, ey - 38 * k, ex - 10 * k, ey - 18 * k], fill=(255, 255, 255))
        _mano(d, rx, ry, 0, k)
    elif obj == "movil":
        d.rounded_rectangle([lx - 10 * k, ly - 150 * k, lx + 80 * k, ly + 20 * k], radius=int(14 * k), fill=(20, 20, 24))
        d.rounded_rectangle([lx - 2 * k, ly - 140 * k, lx + 72 * k, ly + 10 * k], radius=int(10 * k), fill=(255, 60, 90))
        _mano(d, lx, ly, 0, k)
