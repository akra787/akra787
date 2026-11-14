"""Escenarios, personajes y escenas animadas del vídeo (importado por render.py)."""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from render_base import (W, H, AMARILLO, BLANCO, cl, pr, eo, eio, eob, pop, hexrgb, mezcla, sprite, texto,
                         texto_pop, ancho, caja, anillo, fuente)

PIEL = (255, 204, 77)
OSCURO = (30, 30, 38)
ENV = {}


def entorno(nombre):
    if nombre not in ENV:
        ENV[nombre] = CONSTRUCTORES[nombre]()
    return ENV[nombre]


# ------------------------------------------------------------------ personaje
def limb(d, p0, p1, w, col):
    d.line([p0, p1], fill=col, width=max(1, int(w)))
    r = w / 2
    for p in (p0, p1):
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col)


def persona(img, d, x, yp, e=1.0, camisa=(220, 80, 60), pantalon=(45, 62, 110), cara="😐", paso=None,
            sentado=False, espalda=False, pelo=(70, 45, 30), brazos=0.0, alpha=1.0, cara_rot=0.0, sombra=True,
            pie=0.0, mira=1):
    """Muñeco con cabeza emoji. yp = pies (de pie) o asiento (sentado). Devuelve posiciones útiles."""
    a = int(255 * alpha)
    c = lambda col: tuple(col[:3]) + (a,)
    if sombra and not sentado:
        d.ellipse((x - 115 * e, yp - 16 * e, x + 115 * e, yp + 16 * e), fill=(0, 0, 0, int(70 * alpha)))
    sw = math.sin(paso) * 0.42 if paso is not None else 0.0
    if not sentado:
        hip, sh, hy = yp - 190 * e, yp - 380 * e, yp - 468 * e
        for s, sg in ((-1, 1), (1, -1)):
            hx = x + s * 32 * e
            ang = sg * sw
            fx, fy = hx + math.sin(ang) * 185 * e, hip + math.cos(ang) * 185 * e
            if s == 1 and pie:
                fy -= pie * 22 * e
            limb(d, (hx, hip), (fx, fy), 60 * e, c(pantalon))
            dx = mira * 16 * e if paso is not None else s * 12 * e
            d.ellipse((fx - 30 * e + dx, fy - 6 * e, fx + 30 * e + dx, fy + 22 * e), fill=c(OSCURO))
    else:
        hip, sh, hy = yp, yp - 192 * e, yp - 282 * e
        for s in (-1, 1):
            k0, k1 = (x + s * 34 * e, hip), (x + s * 42 * e, hip + 50 * e)
            limb(d, k0, k1, 70 * e, c(pantalon))
            f = (x + s * 46 * e, hip + 175 * e)
            limb(d, k1, f, 58 * e, c(pantalon))
            d.ellipse((f[0] - 30 * e, f[1] - 4 * e, f[0] + 30 * e, f[1] + 24 * e), fill=c(OSCURO))
    manos = []
    hombros = [(x + s * 70 * e, sh + 22 * e) for s in (-1, 1)]
    caja(d, x - 74 * e, sh, x + 74 * e, hip + 26 * e, 46 * e, c(camisa))
    d.rectangle((x - 74 * e, hip - 4 * e, x + 74 * e, hip + 26 * e), fill=c(pantalon))
    for s, (hx, hy0) in zip((-1, 1), hombros):
        ang = 0.18 + brazos * 2.1 + (s * sw * 0.6 if paso is not None else 0)
        ex, ey = hx + s * math.sin(ang) * 168 * e, hy0 + math.cos(ang) * 168 * e
        limb(d, (hx, hy0), (ex, ey), 44 * e, c(camisa))
        d.ellipse((ex - 22 * e, ey - 22 * e, ex + 22 * e, ey + 22 * e), fill=c(PIEL))
        manos.append((ex, ey))
    d.rectangle((x - 20 * e, hy + 50 * e, x + 20 * e, sh + 10 * e), fill=c(mezcla(PIEL, (200, 140, 40), 0.3)))
    if espalda:
        for s in (-1, 1):
            d.ellipse((x + s * 80 * e - 18 * e, hy - 14 * e, x + s * 80 * e + 18 * e, hy + 22 * e), fill=c(PIEL))
        d.ellipse((x - 84 * e, hy - 84 * e, x + 84 * e, hy + 84 * e), fill=c(pelo))
        d.ellipse((x - 50 * e, hy - 70 * e, x + 10 * e, hy - 30 * e), fill=c(mezcla(pelo, (255, 255, 255), 0.15)))
    else:
        sprite(img, cara, x, hy, 172 * e, alpha=alpha, rot=cara_rot, sombra=False)
    return {"cabeza": (x, hy), "manos": manos, "pecho": (x, sh + 60 * e)}


def flecha_curva(d, p0, p1, alto, col, w=10, k=1.0):
    pts = []
    n = 30
    for i in range(int(n * k) + 1):
        u = i / n
        x = p0[0] + (p1[0] - p0[0]) * u
        y = p0[1] + (p1[1] - p0[1]) * u - math.sin(u * math.pi) * alto
        pts.append((x, y))
    if len(pts) > 1:
        d.line(pts, fill=col, width=w, joint="curve")
    if k >= 0.99:
        (x0, y0), (x1, y1) = pts[-3], pts[-1]
        ang = math.atan2(y1 - y0, x1 - x0)
        L = 34
        d.polygon([(x1 + math.cos(ang) * 10, y1 + math.sin(ang) * 10),
                   (x1 - math.cos(ang - 0.5) * L, y1 - math.sin(ang - 0.5) * L),
                   (x1 - math.cos(ang + 0.5) * L, y1 - math.sin(ang + 0.5) * L)], fill=col)


def ondas_bostezo(d, x, y, t, t0, size):
    if t0 <= t < t0 + 1.5:
        for i in range(3):
            f = ((t - t0) * 1.3 + i / 3) % 1
            anillo(d, x, y, size * (0.55 + 0.7 * f), (255, 215, 140, int(190 * (1 - f))), 6)


# ------------------------------------------------------------------ móvil (capa con giro)
def capa_movil(s, t, pantalla="feed", on=1.0):
    w, h = int(300 * s), int(600 * s)
    L = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    o = 6
    d.rounded_rectangle((0, 0, w + 11, h + 11), int(56 * s), fill=(18, 18, 24, 255))
    if pantalla == "dorso":
        d.rounded_rectangle((o, o, w + o, h + o), int(50 * s), fill=(48, 50, 64, 255))
        d.rounded_rectangle((o + 22 * s, o + 22 * s, o + 130 * s, o + 140 * s), int(30 * s), fill=(28, 30, 40, 255))
        for cx, cy in ((o + 52 * s, o + 52 * s), (o + 100 * s, o + 52 * s), (o + 52 * s, o + 106 * s)):
            d.ellipse((cx - 20 * s, cy - 20 * s, cx + 20 * s, cy + 20 * s), fill=(10, 10, 14, 255),
                      outline=(90, 90, 110, 255), width=max(1, int(4 * s)))
        d.ellipse((o + w / 2 - 34 * s, o + h / 2 - 34 * s, o + w / 2 + 34 * s, o + h / 2 + 34 * s),
                  fill=(70, 72, 90, 255))
        return L
    d.rounded_rectangle((o, o, w + o, h + o), int(50 * s), fill=(58, 58, 72, 255))
    pw, ph = w - 26 * s, h - 26 * s
    x0, y0 = o + 13 * s, o + 13 * s
    fondo = mezcla((12, 12, 18), (34, 48, 98), on)
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), int(40 * s), fill=fondo + (255,))
    d.rounded_rectangle((x0 + pw / 2 - 50 * s, y0 + 14 * s, x0 + pw / 2 + 50 * s, y0 + 40 * s), int(13 * s),
                        fill=(4, 4, 8, 255))
    if on < 0.05:
        return L
    if pantalla == "feed":
        scroll = (t * 170 * s) % (125 * s)
        top = y0 + 64 * s
        for i in range(6):
            y = top + i * 125 * s - scroll
            if y < top - 5 or y > y0 + ph - 105 * s:
                continue
            caja(d, x0 + 18 * s, y, x0 + pw - 18 * s, y + 100 * s, 16 * s, mezcla(fondo, (255, 255, 255), 0.16) + (255,))
            col = hexrgb(["#FF5C8A", "#4FE3D0", "#FFD640"][int((i + (t * 170 * s) // (125 * s))) % 3])
            d.ellipse((x0 + 30 * s, y + 20 * s, x0 + 90 * s, y + 80 * s), fill=mezcla(fondo, col, on) + (255,))
            caja(d, x0 + 106 * s, y + 28 * s, x0 + pw - 36 * s, y + 44 * s, 8 * s, mezcla(fondo, (255, 255, 255), 0.7) + (255,))
            caja(d, x0 + 106 * s, y + 56 * s, x0 + pw / 2 + 30 * s, y + 70 * s, 7 * s, mezcla(fondo, (255, 255, 255), 0.4) + (255,))
    elif pantalla == "video":
        caja(d, x0 + 10 * s, y0 + 120 * s, x0 + pw - 10 * s, y0 + 420 * s, 20 * s, (250, 225, 160, 255))
        cara = sprite_img("🥱", int(210 * s))
        L.paste(cara, (int(x0 + pw / 2 - cara.width / 2), int(y0 + 270 * s - cara.height / 2)), cara)
        caja(d, x0 + 20 * s, y0 + 440 * s, x0 + pw - 20 * s, y0 + 452 * s, 6 * s, (90, 90, 110, 255))
        caja(d, x0 + 20 * s, y0 + 440 * s, x0 + 20 * s + (pw - 40 * s) * ((t * 0.3) % 1), y0 + 452 * s, 6 * s,
             (255, 60, 80, 255))
    return L


def sprite_img(ch, size):
    from render_base import emoji
    return emoji(ch, max(8, int(round(size / 4) * 4)))


def pegar_movil(img, d, cx, cy, s, t, giro=0.0, pantalla="feed", on=1.0, rot=0.0, sombra=True):
    """giro: 0 = boca arriba, 1 = boca abajo (anima la vuelta)."""
    ang = giro * math.pi
    sx = abs(math.cos(ang))
    cara = "dorso" if math.cos(ang) < 0 else pantalla
    L = capa_movil(s, t, cara, on)
    nw = max(2, int(L.width * max(0.04, sx)))
    L = L.resize((nw, L.height), Image.BICUBIC)
    if rot:
        L = L.rotate(rot, resample=Image.BICUBIC, expand=True)
    if sombra:
        sh = Image.new("L", L.size, 0)
        sh.paste(L.getchannel("A").point(lambda v: int(v * 0.45)), (0, 0))
        img.paste((0, 0, 0), (int(cx - L.width / 2 + 18), int(cy - L.height / 2 + 26)), sh)
    img.paste(L, (int(cx - L.width / 2), int(cy - L.height / 2)), L)


# ------------------------------------------------------------------ entornos
def madera(w, h, tonos, ancho_tabla, vertical=True, seed=1):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a, b = (xx, yy) if vertical else (yy, xx)
    tabla = (a // ancho_tabla).astype(int)
    rng = np.random.default_rng(seed)
    desf = rng.uniform(0, 100, 200)
    veta = np.sin(b * 0.011 + desf[tabla % 200] + 2.2 * np.sin(a * 0.035 + desf[tabla % 200] * 0.3))
    base = np.array([hexrgb(tonos[i % len(tonos)]) for i in range(200)], np.float32)[tabla % 200]
    img = base * (0.9 + 0.07 * veta[..., None]) + rng.normal(0, 3, (h, w, 1))
    junta = (a % ancho_tabla) < 3
    img[junta] *= 0.62
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def gradiente(w, h, c1, c2):
    y = np.linspace(0, 1, h)[:, None, None]
    img = np.array(hexrgb(c1), float) * (1 - y) + np.array(hexrgb(c2), float) * y
    return Image.fromarray(np.broadcast_to(img, (h, w, 3)).astype(np.uint8))


def env_casa():
    WW = 2200
    img = Image.new("RGB", (WW, H), (95, 132, 173))
    d = ImageDraw.Draw(img, "RGBA")
    # salón
    for x in range(0, 1180, 90):
        d.rectangle((x, 0, x + 45, 1300), fill=(255, 255, 255, 14))
    d.rectangle((0, 1262, 1180, 1300), fill=(240, 236, 228, 255))
    # cocina
    d.rectangle((1180, 0, WW, 1300), fill=(246, 234, 200, 255))
    d.rectangle((1180, 860, WW, 1300), fill=(255, 248, 226, 255))
    for x in range(1180, WW, 72):
        d.line((x, 860, x, 1300), fill=(214, 200, 160, 255), width=3)
    for y in range(860, 1300, 72):
        d.line((1180, y, WW, y), fill=(214, 200, 160, 255), width=3)
    # suelos
    img.paste(madera(1180, H - 1300, ["#9a6139", "#a76a3f", "#8f5933", "#a2663c"], 70, vertical=False, seed=4),
              (0, 1300))
    for yy in range(1300, H, 110):
        for xx in range(1180, WW, 110):
            par = ((xx - 1180) // 110 + (yy - 1300) // 110) % 2
            d.rectangle((xx, yy, xx + 110, yy + 110), fill=(236, 232, 224, 255) if par else (120, 132, 148, 255))
    # sombra suave del suelo junto a la pared
    for i in range(30):
        d.line((0, 1300 + i, WW, 1300 + i), fill=(0, 0, 0, int(70 * (1 - i / 30))))
    # ventana con cortinas
    d.rectangle((110, 470, 470, 900), fill=(240, 240, 240, 255))
    cielo = gradiente(320, 390, "#5fb3ef", "#cdeeff")
    img.paste(cielo, (130, 490))
    for cx, cy, r in ((230, 600, 40), (275, 585, 52), (320, 605, 38), (390, 760, 30), (425, 750, 38)):
        d.ellipse((cx - r, cy - r * 0.7, cx + r, cy + r * 0.7), fill=(255, 255, 255, 235))
    d.rectangle((282, 490, 298, 880), fill=(240, 240, 240, 255))
    d.rectangle((130, 678, 450, 694), fill=(240, 240, 240, 255))
    d.rectangle((60, 430, 520, 450), fill=(120, 80, 50, 255))
    for x0 in (70, 420):
        caja(d, x0, 440, x0 + 90, 980, 30, (196, 62, 70, 255))
        for k in range(3):
            d.line((x0 + 22 + k * 24, 460, x0 + 22 + k * 24, 970), fill=(160, 40, 52, 255), width=5)
    # cuadro
    d.rectangle((620, 510, 880, 700), fill=(214, 168, 70, 255))
    d.rectangle((636, 526, 864, 684), fill=(170, 220, 245, 255))
    d.polygon([(636, 684), (720, 580), (790, 684)], fill=(80, 140, 100, 255))
    d.polygon([(700, 684), (790, 600), (864, 684)], fill=(60, 115, 85, 255))
    d.ellipse((800, 545, 840, 585), fill=(255, 210, 80, 255))
    # sofá
    caja(d, 250, 1000, 840, 1170, 46, (78, 138, 92, 255))
    for x0 in (275, 555):
        caja(d, x0, 1020, x0 + 260, 1150, 36, (92, 156, 106, 255))
    caja(d, 230, 1120, 860, 1250, 30, (88, 150, 102, 255))
    caja(d, 195, 1070, 300, 1262, 34, (66, 120, 80, 255))
    caja(d, 790, 1070, 895, 1262, 34, (66, 120, 80, 255))
    caja(d, 600, 1040, 700, 1120, 20, (240, 190, 70, 255))
    # lámpara de pie
    for g in range(10, 0, -1):
        r = 60 + g * 22
        d.ellipse((1000 - r, 760 - r, 1000 + r, 760 + r), fill=(255, 220, 140, 6))
    d.rectangle((995, 790, 1005, 1285), fill=(50, 50, 58, 255))
    d.ellipse((955, 1270, 1045, 1300), fill=(50, 50, 58, 255))
    d.polygon([(945, 700), (1055, 700), (1080, 800), (920, 800)], fill=(255, 214, 138, 255))
    # pared intermedia con el hueco de la puerta (vista en corte)
    d.rectangle((1150, 0, 1210, 700), fill=(60, 86, 120, 255))
    d.rectangle((1140, 690, 1220, 712), fill=(245, 245, 245, 255))
    d.rectangle((1150, 712, 1162, 1300), fill=(245, 245, 245, 255))
    d.polygon([(1210, 712), (1300, 742), (1300, 1272), (1210, 1300)], fill=(168, 105, 58, 255),
              outline=(110, 66, 36, 255))
    d.ellipse((1272, 990, 1292, 1010), fill=(255, 210, 90, 255))
    # cocina: armarios, encimera, nevera, tarro de galletas
    caja(d, 1360, 500, 1860, 770, 14, (255, 255, 255, 255), outline=(205, 205, 210, 255), w=4)
    for x in (1485, 1610, 1735):
        d.line((x, 500, x, 770), fill=(205, 205, 210, 255), width=4)
    for x in (1440, 1565, 1690, 1815):
        caja(d, x - 5, 700, x + 5, 750, 4, (150, 150, 160, 255))
    caja(d, 1360, 1065, 1860, 1300, 10, (255, 255, 255, 255), outline=(205, 205, 210, 255), w=4)
    for x in (1485, 1610, 1735):
        d.line((x, 1065, x, 1300), fill=(205, 205, 210, 255), width=4)
    d.rectangle((1340, 1040, 1880, 1072), fill=(100, 100, 112, 255))
    # tarro
    caja(d, 1560, 905, 1690, 1040, 26, (200, 235, 255, 150), outline=(150, 190, 220, 255), w=5)
    caja(d, 1572, 885, 1678, 912, 10, (196, 62, 70, 255))
    for cx, cy in ((1600, 1000), (1650, 995), (1625, 960), (1595, 950), (1660, 950)):
        d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=(205, 140, 70, 255))
        d.ellipse((cx - 6, cy - 8, cx + 2, cy), fill=(90, 50, 30, 255))
    # sartén colgada
    d.ellipse((1430, 890, 1520, 980), fill=(50, 50, 58, 255))
    d.rectangle((1470, 820, 1478, 892), fill=(50, 50, 58, 255))
    # nevera
    caja(d, 1930, 700, 2150, 1300, 24, (226, 234, 240, 255), outline=(180, 190, 200, 255), w=5)
    d.line((1930, 900, 2150, 900), fill=(180, 190, 200, 255), width=5)
    caja(d, 1950, 760, 1962, 860, 6, (150, 160, 170, 255))
    caja(d, 1950, 940, 1962, 1100, 6, (150, 160, 170, 255))
    return img


def env_mesa():
    img = madera(W, H, ["#b07a4c", "#a8703f", "#b98455", "#a36c3e", "#b27c4b"], 216, vertical=True, seed=7)
    d = ImageDraw.Draw(img, "RGBA")

    def pegar_rot(capa, cx, cy, rot):
        r = capa.rotate(rot, resample=Image.BICUBIC, expand=True)
        sh = Image.new("L", r.size, 0)
        sh.paste(r.getchannel("A").point(lambda v: int(v * 0.35)), (0, 0))
        img.paste((0, 0, 0), (int(cx - r.width / 2 + 16), int(cy - r.height / 2 + 22)), sh)
        img.paste(r, (int(cx - r.width / 2), int(cy - r.height / 2)), r)

    # libreta
    lib = Image.new("RGBA", (380, 500))
    ld = ImageDraw.Draw(lib)
    ld.rounded_rectangle((0, 0, 379, 499), 16, fill=(250, 248, 240, 255))
    for y in range(80, 500, 34):
        ld.line((20, y, 360, y), fill=(160, 190, 230, 255), width=2)
    ld.line((70, 0, 70, 499), fill=(235, 120, 120, 255), width=3)
    for y in range(30, 480, 40):
        ld.ellipse((-10, y, 14, y + 20), fill=(90, 90, 100, 255))
    pegar_rot(lib, 210, 640, 9)
    # bolígrafo
    pen = Image.new("RGBA", (340, 30))
    pd = ImageDraw.Draw(pen)
    pd.rounded_rectangle((0, 4, 300, 26), 10, fill=(40, 90, 200, 255))
    pd.polygon([(300, 4), (338, 15), (300, 26)], fill=(230, 220, 200, 255))
    pegar_rot(pen, 260, 980, -32)
    # portátil
    lap = Image.new("RGBA", (560, 400))
    lp = ImageDraw.Draw(lap)
    lp.rounded_rectangle((0, 0, 559, 399), 24, fill=(178, 182, 192, 255))
    for r in range(5):
        for c in range(12):
            lp.rounded_rectangle((30 + c * 42, 40 + r * 44, 30 + c * 42 + 34, 40 + r * 44 + 34), 6,
                                 fill=(60, 62, 72, 255))
    lp.rounded_rectangle((190, 270, 370, 380), 14, fill=(160, 164, 175, 255))
    pegar_rot(lap, 960, 520, -14)
    # taza (vista desde arriba)
    cx, cy = 880, 1150
    d.ellipse((cx - 110 + 14, cy - 110 + 20, cx + 110 + 14, cy + 110 + 20), fill=(0, 0, 0, 80))
    caja(d, cx + 80, cy - 30, cx + 160, cy + 30, 28, (245, 245, 245, 255))
    caja(d, cx + 100, cy - 14, cx + 140, cy + 14, 14, (176, 120, 80, 255))
    d.ellipse((cx - 105, cy - 105, cx + 105, cy + 105), fill=(250, 250, 250, 255))
    d.ellipse((cx - 82, cy - 82, cx + 82, cy + 82), fill=(92, 52, 28, 255))
    d.ellipse((cx - 50, cy - 60, cx - 10, cy - 30), fill=(150, 100, 60, 180))
    # planta (vista desde arriba)
    px, py = 150, 1270
    d.ellipse((px - 120 + 14, py - 120 + 20, px + 120 + 14, py + 120 + 20), fill=(0, 0, 0, 80))
    d.ellipse((px - 115, py - 115, px + 115, py + 115), fill=(196, 110, 70, 255))
    d.ellipse((px - 95, py - 95, px + 95, py + 95), fill=(92, 60, 40, 255))
    rng = random.Random(2)
    for i in range(9):
        ang = i * 0.7
        L = Image.new("RGBA", (220, 80))
        ImageDraw.Draw(L).ellipse((0, 0, 219, 79), fill=(60 + rng.randint(0, 40), 150 + rng.randint(0, 40), 70, 255))
        L = L.rotate(math.degrees(ang), resample=Image.BICUBIC, expand=True)
        img.paste(L, (int(px + math.cos(ang) * 70 - L.width / 2), int(py - math.sin(ang) * 70 - L.height / 2)), L)
    return img


def env_metro():
    img = Image.new("RGB", (W, H), (222, 229, 237))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, 0, W, 250), fill=(195, 205, 217, 255))
    caja(d, 60, 165, 1020, 205, 20, (255, 255, 250, 255))
    for g in range(6):
        d.rectangle((60, 205 + g * 6, 1020, 211 + g * 6), fill=(255, 255, 240, 30 - g * 5))
    d.rectangle((0, 262, W, 272), fill=(170, 178, 190, 255))
    cols = ["#ff6b6b", "#4fc3f7", "#ffd54f"]
    for i, x in enumerate((40, 380, 720)):
        caja(d, x, 300, x + 320, 385, 10, hexrgb(cols[i]) + (255,))
        caja(d, x + 20, 320, x + 180, 336, 6, (255, 255, 255, 220))
        caja(d, x + 20, 348, x + 130, 360, 6, (255, 255, 255, 160))
        d.ellipse((x + 230, 315, x + 290, 375), fill=(255, 255, 255, 200))
    for x0, x1 in ((50, 510), (570, 1030)):
        caja(d, x0, 405, x1, 775, 36, (150, 158, 170, 255))
    d.rectangle((0, 770, W, 1010), fill=(47, 95, 168, 255))
    for x in range(0, W, 180):
        d.line((x, 770, x, 1010), fill=(37, 78, 140, 255), width=4)
    caja(d, -20, 990, W + 20, 1080, 26, (59, 111, 192, 255))
    d.rectangle((0, 1075, W, 1160), fill=(36, 73, 127, 255))
    suelo = np.full((H - 1160, W, 3), (138, 146, 157), np.float32)
    suelo += np.random.default_rng(5).normal(0, 7, suelo.shape[:2])[..., None]
    img.paste(Image.fromarray(np.clip(suelo, 0, 255).astype(np.uint8)), (0, 1160))
    d.rectangle((0, 1160, W, 1185), fill=(90, 96, 106, 255))
    return img


def env_calle():
    img = gradiente(W, H, "#5cb6f0", "#d8f1ff")
    d = ImageDraw.Draw(img, "RGBA")
    rng = random.Random(9)
    x = -40
    while x < W:
        w = rng.randint(130, 230)
        top = rng.randint(360, 560)
        d.rectangle((x, top, x + w, 820), fill=(150, 180, 205, 255))
        for wy in range(top + 25, 800, 46):
            for wx in range(x + 18, x + w - 30, 40):
                d.rectangle((wx, wy, wx + 20, wy + 26), fill=(190, 215, 235, 255))
        x += w + rng.randint(-10, 20)
    pal = ["#e07a5f", "#3d405b", "#81b29a", "#f2cc8f", "#c97b84", "#6d6875", "#e9c46a"]
    x = -30
    i = 0
    while x < W:
        w = rng.randint(170, 260)
        top = rng.randint(470, 640)
        col = hexrgb(pal[i % len(pal)])
        d.rectangle((x, top, x + w, 830), fill=col + (255,))
        d.rectangle((x, top, x + w, top + 18), fill=mezcla(col, (0, 0, 0), 0.25) + (255,))
        for wy in range(top + 45, 760, 60):
            for wx in range(x + 22, x + w - 40, 52):
                lit = rng.random() < 0.3
                d.rectangle((wx, wy, wx + 30, wy + 38), fill=(255, 226, 140, 255) if lit else (170, 210, 240, 255))
                d.rectangle((wx - 3, wy + 38, wx + 33, wy + 43), fill=mezcla(col, (255, 255, 255), 0.4) + (255,))
        d.rectangle((x + w / 2 - 28, 760, x + w / 2 + 28, 830), fill=mezcla(col, (0, 0, 0), 0.45) + (255,))
        x += w
        i += 1
    d.rectangle((0, 820, W, 862), fill=(190, 182, 168, 255))
    d.rectangle((0, 862, W, 874), fill=(140, 134, 124, 255))
    d.rectangle((0, 874, W, 1062), fill=(74, 79, 87, 255))
    for x in range(560, 1060, 72):
        d.rectangle((x, 880, x + 40, 1056), fill=(240, 240, 240, 235))
    for x in range(-20, 540, 120):
        d.rectangle((x, 963, x + 70, 973), fill=(250, 250, 250, 220))
    d.rectangle((0, 1062, W, 1082), fill=(140, 134, 124, 255))
    d.rectangle((0, 1082, W, H), fill=(207, 199, 185, 255))
    for y in (1150, 1250, 1380, 1540, 1730):
        d.line((0, y, W, y), fill=(188, 180, 166, 255), width=4)
    for k in range(-6, 12):
        d.line((540 + k * 120, 1082, 540 + k * 220, H), fill=(188, 180, 166, 255), width=4)
    # poste del semáforo
    d.rectangle((140, 380, 162, 1110), fill=(60, 64, 72, 255))
    d.ellipse((115, 1095, 187, 1125), fill=(60, 64, 72, 255))
    return img


def env_noche():
    img = gradiente(W, H, "#050817", "#221c4d")
    d = ImageDraw.Draw(img, "RGBA")
    rng = random.Random(4)
    for _ in range(140):
        x, y, r = rng.random() * W, rng.random() * 900, rng.choice([1, 1, 2, 3])
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(80, 230)))
    glow = Image.new("RGBA", (W, H))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((880 - 170, 470 - 170, 880 + 170, 470 + 170), fill=(200, 200, 255, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(50))
    img.paste(glow, (0, 0), glow)
    d.ellipse((880 - 72, 470 - 72, 880 + 72, 470 + 72), fill=(246, 241, 210, 255))
    d.ellipse((840, 440, 868, 468), fill=(225, 220, 190, 255))
    d.ellipse((890, 495, 910, 515), fill=(225, 220, 190, 255))
    x = -20
    while x < W:
        w = rng.randint(120, 220)
        top = rng.randint(600, 820)
        d.rectangle((x, top, x + w, 1120), fill=(13, 15, 36, 255))
        for wy in range(top + 30, 1080, 54):
            for wx in range(x + 20, x + w - 30, 46):
                if rng.random() < 0.18:
                    d.rectangle((wx, wy, wx + 24, wy + 30), fill=(255, 215, 120, 255))
        x += w
    d.rectangle((0, 1110, W, H), fill=(28, 30, 48, 255))
    for y in (1180, 1290, 1440, 1640):
        d.line((0, y, W, y), fill=(38, 40, 62, 255), width=4)
    # arbustos
    for cx, cy, r, c in ((60, 1060, 150, (14, 40, 30)), (230, 1010, 170, (18, 50, 36)), (390, 1080, 120, (14, 40, 30)),
                         (120, 1150, 140, (20, 56, 40)), (320, 1170, 130, (16, 46, 34))):
        d.ellipse((cx - r, cy - r * 0.85, cx + r, cy + r * 0.85), fill=c + (255,))
    # farola + cono de luz
    luz = Image.new("RGBA", (W, H))
    ld = ImageDraw.Draw(luz)
    ld.polygon([(700, 520), (780, 520), (1060, 1290), (420, 1290)], fill=(255, 220, 140, 55))
    ld.ellipse((420, 1230, 1060, 1350), fill=(255, 220, 140, 70))
    luz = luz.filter(ImageFilter.GaussianBlur(18))
    img.paste(luz, (0, 0), luz)
    d.rectangle((842, 490, 858, 1290), fill=(40, 43, 60, 255))
    d.ellipse((820, 1275, 880, 1300), fill=(40, 43, 60, 255))
    d.line((850, 492, 760, 492), fill=(40, 43, 60, 255), width=14)
    d.polygon([(700, 500), (790, 500), (775, 525), (715, 525)], fill=(40, 43, 60, 255))
    d.ellipse((722, 512, 768, 540), fill=(255, 240, 190, 255))
    return img


CONSTRUCTORES = {"casa": env_casa, "mesa": env_mesa, "metro": env_metro, "calle": env_calle, "noche": env_noche}


def miniatura(nombre, w, h):
    key = f"mini_{nombre}_{w}_{h}"
    if key not in ENV:
        src = entorno(nombre)
        if nombre == "casa":
            box = (950, 560, 1650, 1540)
        elif nombre == "mesa":
            box = (130, 450, 950, 1600)
        elif nombre == "metro":
            box = (60, 360, 1020, 1700)
        elif nombre == "calle":
            box = (0, 300, 900, 1560)
        else:
            box = (300, 300, 1080, 1390)
        im = src.crop(box)
        bw, bh = im.size
        if bw / bh > w / h:
            nw = int(bh * w / h)
            im = im.crop(((bw - nw) // 2, 0, (bw - nw) // 2 + nw, bh))
        else:
            nh = int(bw * h / w)
            im = im.crop((0, (bh - nh) // 2, bw, (bh - nh) // 2 + nh))
        im = im.resize((w, h), Image.LANCZOS)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), int(min(w, h) * 0.12), fill=255)
        out = im.convert("RGBA")
        out.putalpha(mask)
        ENV[key] = out
    return ENV[key]


def rayos(d, t, cx, cy, col, n=16, alpha=22):
    for i in range(n):
        a0 = i * 2 * math.pi / n + t * 0.25
        a1 = a0 + math.pi / n
        R = 1800
        d.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R),
                   (cx + math.cos(a1) * R, cy + math.sin(a1) * R)], fill=col + (alpha,))


CONFETI = [(random.Random(i).random() * W, random.Random(i + 99).random(), random.Random(i + 7).uniform(150, 380),
            random.Random(i + 3).random() * 6.28, i % 5) for i in range(70)]
COLS_CONFETI = [(255, 92, 138), (79, 227, 208), (255, 214, 64), (182, 156, 255), (61, 220, 132)]


def confeti(d, t, t0):
    for x, y0, v, ph, c in CONFETI:
        y = (y0 * H * 1.2 - 200 + (t - t0) * v) % (H + 100) - 50
        xx = x + 30 * math.sin(t * 2 + ph)
        a = math.sin(t * 5 + ph)
        w, h = 22 * abs(a) + 4, 12
        d.polygon([(xx - w, y - h), (xx + w, y - h + 6), (xx + w, y + h), (xx - w, y + h - 6)], fill=COLS_CONFETI[c] + (230,))


# ------------------------------------------------------------------ escenas
GANCHO = [("casa", "🚪", "PUERTAS"), ("mesa", "📱", "MÓVIL"), ("metro", "🥱", "BOSTEZOS"),
          ("calle", "🚦", "SEMÁFOROS"), ("noche", "👀", "MIRADAS")]


def esc_intro(img, d, t, ac):
    rayos(d, t, W / 2, 700, AMARILLO, alpha=20)
    k = pop(t, 0.0, 0.5)
    rot = math.sin(t * 3) * 4
    lay = Image.new("RGBA", (720, 720))
    ImageDraw.Draw(lay).text((360, 360), "5", font=fuente(580), fill=AMARILLO, anchor="mm", stroke_width=24,
                             stroke_fill=(20, 10, 40))
    lay = lay.rotate(rot, resample=Image.BICUBIC)
    s = max(8, int(720 * k))
    lay = lay.resize((s, s), Image.BICUBIC)
    img.paste(lay, (int(W / 2 - s / 2), int(600 - s / 2)), lay)
    # mini escenas girando alrededor
    for i, (env, ch, _) in enumerate(GANCHO):
        t0 = 0.3 + i * 0.3
        if t < t0:
            continue
        kk = pop(t, t0, 0.4)
        ang = -math.pi / 2 + i * 2 * math.pi / 5 + t * 0.35
        x, y = W / 2 + math.cos(ang) * 400, 600 + math.sin(ang) * 380
        m = miniatura(env, 150, 150)
        m2 = m.resize((max(4, int(150 * kk)), max(4, int(150 * kk))))
        img.paste(m2, (int(x - m2.width / 2), int(y - m2.height / 2)), m2)
        sprite(img, ch, x + 50 * kk, y + 50 * kk, 80 * kk)
    texto_pop(d, "COSAS", W / 2, 1060, 130, t, 0.32)
    texto_pop(d, "COTIDIANAS", W / 2, 1185, 130, t, 0.72)
    texto_pop(d, "QUE TIENEN UNA", W / 2, 1305, 70, t, 1.44)
    if t >= 2.3:
        k2 = pop(t, 2.3, 0.4)
        tw = ancho("EXPLICACIÓN", 112) + 60
        caja(d, W / 2 - tw / 2 * k2, 1425 - 75 * k2, W / 2 + tw / 2 * k2, 1425 + 75 * k2, 30, AMARILLO + (255,))
        texto(d, "EXPLICACIÓN", W / 2, 1425, 112 * k2, (25, 12, 45), stroke=0)
        sprite(img, "😳", W / 2 + tw / 2 * k2 - 10, 1330, 170 * pop(t, 2.6, 0.45), rot=-12 + 6 * math.sin(t * 6))


def tarjeta_mini(img, d, env, ch, lab, x, y, w, h, k, alpha, ac, t, i, q=0.0):
    if k <= 0.02:
        return
    w2, h2 = int(w * k), int(h * k)
    m = miniatura(env, w, h)
    if (w2, h2) != (w, h):
        m = m.resize((max(4, w2), max(4, h2)), Image.BILINEAR)
    if alpha < 1:
        m = m.copy()
        m.putalpha(m.getchannel("A").point(lambda v: int(v * alpha)))
    caja(d, x - w2 / 2 - 8, y - h2 / 2 - 8, x + w2 / 2 + 8, y + h2 / 2 + 8, int(min(w2, h2) * 0.14),
         BLANCO + (int(255 * alpha),))
    img.paste(m, (int(x - w2 / 2), int(y - h2 / 2)), m)
    caja(d, x - w2 / 2, y + h2 / 2 - 64 * k, x + w2 / 2, y + h2 / 2, 0, (0, 0, 0, int(150 * alpha)))
    texto(d, lab, x, y + h2 / 2 - 32 * k, 38 * k, BLANCO, alpha=alpha, stroke=4)
    sprite(img, ch, x + w2 / 2 - 30 * k, y - h2 / 2 + 30 * k, 110 * k, alpha=alpha, rot=math.sin(t * 3 + i) * 10)
    if q > 0:
        sprite(img, "❓", x - w2 / 2 + 30 * k, y - h2 / 2 + 30 * k, 100 * q * k, alpha=alpha, rot=-15)


def esc_gancho(img, d, t, ac):
    rayos(d, t, W / 2, 800, ac, alpha=12)
    texto_pop(d, "APUESTO A QUE...", W / 2, 230, 84, t, 3.7)
    dim = pr(t, 9.4, 9.8)
    foco = eo(pr(t, 9.5, 10.2))
    if t >= 4.6:
        texto(d, "HACES ESTAS 5 COSAS", W / 2, 330, 58, ac, alpha=pr(t, 4.6, 4.9) * (1 - dim))
    pos = [(205, 640), (540, 640), (875, 640), (372, 1060), (708, 1060)]
    tiempos = [4.62, 4.88, 5.18, 5.6, 6.04]
    orden = [0, 1, 2, 3, 4]
    for i in orden:
        env, ch, lab = GANCHO[i]
        x, y = pos[i]
        t0 = tiempos[i]
        if t < t0:
            continue
        k = pop(t, t0, 0.4)
        y += math.sin(t * 2.5 + i) * 8
        alpha = 1 - dim if i < 4 else 1
        q = pop(t, 7.6 + i * 0.12, 0.3) if (t >= 7.6 and i < 4) else 0
        if i == 4:
            continue
        tarjeta_mini(img, d, env, ch, lab, x, y, 300, 380, k, alpha, ac, t, i, q)
    if t >= tiempos[4]:
        x0, y0 = pos[4]
        x = x0 + (W / 2 - x0) * foco
        y = y0 + (820 - y0) * foco + math.sin(t * 2.5 + 4) * 8
        s = 1 + 0.55 * foco
        q = pop(t, 7.6 + 4 * 0.12, 0.3) if t >= 7.6 else 0
        k = pop(t, tiempos[4], 0.4)
        tarjeta_mini(img, d, "noche", "👀", "MIRADAS", x, y, 300, 380, k * s, 1, ac, t, 4, q * (1 - foco))
    if 6.0 <= t < 9.5:
        texto_pop(d, "TODOS LOS DÍAS", W / 2, 1340, 92, t, 6.04, AMARILLO)
    if 7.45 <= t < 9.5:
        texto_pop(d, "...Y NO SABES POR QUÉ", W / 2, 1450, 62, t, 7.46)
    if t >= 9.6:
        texto_pop(d, "LA ÚLTIMA...", W / 2, 1300, 104, t, 9.6, AMARILLO)
        texto_pop(d, "¡SEGURO QUE TE HA PASADO!", W / 2, 1420, 56, t, 10.0)


def bocadillo(d, img, cx, cy, ch, k, contenido_alpha=1.0, ch2=None, k2=0.0):
    if k <= 0.02:
        return
    r = 110 * k
    for dx, dy, rr in ((-60, 120, 24), (-90, 165, 14)):
        d.ellipse((cx + dx * k - rr * k, cy + dy * k - rr * k, cx + dx * k + rr * k, cy + dy * k + rr * k),
                  fill=(255, 255, 255, 245))
    d.ellipse((cx - r, cy - r * 0.85, cx + r, cy + r * 0.85), fill=(255, 255, 255, 245))
    sprite(img, ch, cx, cy, 130 * k, alpha=contenido_alpha, sombra=False)
    if ch2 and k2 > 0:
        sprite(img, ch2, cx, cy, 130 * k2, sombra=False)


def casa_pos(t):
    px = 430 + 1180 * eio(pr(t, 12.55, 15.0))
    cam = max(0, min(2200 - W, px - 430))
    return px, cam


def esc_puerta(img, d, t, ac):
    px, cam = casa_pos(t)
    fondo = entorno("casa").crop((int(cam), 0, int(cam) + W, H))
    img.paste(fondo)
    sx = px - cam
    andando = 12.55 < t < 15.0
    confuso = t >= 15.05
    # bocadillo: galleta → se borra al cruzar la puerta → ❓
    cruz = cl((px - 1120) / 140)
    k2 = eob(cl((px - 1300) / 160))
    cara = "🤔" if confuso else ("😐" if cruz > 0.5 else "🙂")
    yp = 1460
    pers = persona(img, d, sx, yp, 1.0, camisa=(232, 90, 70), cara=cara, paso=t * 9.5 if andando else None,
                   brazos=0.55 * eo(pr(t, 15.1, 15.5)) if confuso else 0.0, mira=1)
    hx, hy = pers["cabeza"]
    bocadillo(d, img, hx + 150, hy - 190, "🍪", pop(t, 12.4, 0.4), contenido_alpha=1 - cruz, ch2="❓", k2=k2)
    if 0 < cruz < 1:
        for i in range(10):
            ang = i * 0.63 + t
            rr = 40 + 200 * cruz
            x, y = hx + 150 + math.cos(ang) * rr, hy - 190 + math.sin(ang) * rr * 0.6
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=AMARILLO + (int(255 * (1 - cruz)),))
    if t >= 15.0:
        texto_pop(d, "¿A QUÉ IBA YO?", W / 2, 500, 84, t, 15.05, AMARILLO)
    if t >= 13.0 and t < 15.0:
        a = pr(t, 13.0, 13.3) * (1 - pr(t, 14.6, 15.0))
        texto(d, "SALÓN", 230 - cam, 400, 56, BLANCO, alpha=a)
        texto(d, "COCINA", 1620 - cam, 400, 56, (60, 50, 30), alpha=a, stroke=0)
    # explicación (16.2+): fondo desenfocado + esquema
    f = pr(t, 16.1, 16.6)
    if f > 0:
        if "casa_blur" not in ENV:
            ENV["casa_blur"] = entorno("casa").crop((2200 - W, 0, 2200, H)).filter(
                ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.45))
        img.paste(Image.blend(img, ENV["casa_blur"], f))
        d2 = ImageDraw.Draw(img, "RGBA")
        kb = pop(t, 16.4, 0.45)
        sprite(img, "🧠", W / 2, 470, 230 * kb * (1 + 0.05 * math.sin(t * 6)), alpha=f)
        for i, (x, lab, ch, col, env) in enumerate([(275, "SALÓN", "🛋️", (80, 160, 255), "casa"),
                                                     (805, "COCINA", "🍳", (255, 140, 160), "casa")]):
            k = pop(t, 17.0 + i * 0.35, 0.35)
            caja(d2, x - 200 * k, 820 - 170 * k, x + 200 * k, 820 + 170 * k, 34, col + (int(90 * f),),
                 outline=col + (int(255 * f),), w=6)
            texto(d2, lab, x, 820 - 130 * k, 44 * k, BLANCO, alpha=f)
            sprite(img, ch, x - 110 * k, 850, 90 * k, alpha=f * 0.9)
        if t >= 17.9:
            sprite(img, "🚪", W / 2, 830, 170 * pop(t, 17.9, 0.35), alpha=f)
        if t >= 17.2:
            via = eio(pr(t, 18.4, 20.6))
            x = 275 + (805 - 275) * via
            y = 860 - math.sin(via * math.pi) * 130
            perdida = pr(t, 19.8, 21.0)
            sprite(img, "🍪", x + 40 * (1 - via), y, 120 * (1 - 0.5 * perdida), alpha=f * (1 - perdida))
            if t >= 20.6:
                sprite(img, "❓", 850, 860, 140 * pop(t, 20.6, 0.35), alpha=f, rot=-10)
        if t >= 20.1:
            kk = pop(t, 20.1, 0.3)
            tw = ancho("¡SOLO UN RATO!", 44) + 50
            caja(d2, W / 2 - tw / 2, 1085 - 34 * kk, W / 2 + tw / 2, 1085 + 34 * kk, 30, ac + (int(255 * f),))
            texto(d2, "¡SOLO UN RATO!", W / 2, 1085, 44 * kk, (15, 12, 25), stroke=0, alpha=f)


def vapor(d, t, cx, cy):
    for i in range(3):
        f = ((t * 0.5) + i / 3) % 1
        pts = [(cx - 30 + i * 30 + math.sin(f * 6 + j * 0.8 + i) * 16, cy - f * 220 - j * 22) for j in range(6)]
        d.line(pts, fill=(255, 255, 255, int(110 * math.sin(f * math.pi))), width=10, joint="curve")


def esc_movil(img, d, t, ac):
    img.paste(entorno("mesa"))
    vapor(d, t, 880, 1120)
    # giro: 0 boca arriba / 1 boca abajo
    if t < 24.1:
        giro = 1.0
    elif t < 25.4:
        giro = 1 - eio(pr(t, 24.1, 24.5))
    elif t < 27.3:
        giro = eio(pr(t, 25.4, 25.8))
    else:
        giro = 1 - eio(pr(t, 27.35, 27.65))
    levantado = (eo(pr(t, 24.1, 24.5)) * (1 - eo(pr(t, 25.4, 25.8))) if t < 27.3 else eo(pr(t, 27.35, 27.7)))
    explic = eio(pr(t, 28.4, 29.0))
    cx = 540 - 150 * explic
    cy = 880 - 20 * levantado
    s = 1.0 + 0.14 * levantado - 0.1 * explic
    if 27.65 <= t < 28.3:
        cx += math.sin(t * 70) * 7
    on = 1.0 if giro < 0.5 else 0.0
    pegar_movil(img, d, cx, cy, s, t, giro=giro, on=on, rot=-4 * (1 - explic))
    # mano que lo coge / lo deja
    def mano(t0, t1):
        return eo(pr(t, t0, t0 + 0.3)) * (1 - eo(pr(t, t1, t1 + 0.35)))
    m = max(mano(23.85, 25.85), mano(27.05, 28.5))
    if m > 0:
        sprite(img, "✋", cx + 150, cy + 270 + (1 - m) * 700, 230, rot=25)
    # bolsillo/apartado: icono «guardado»
    if 25.8 <= t < 27.3:
        texto_pop(d, "GUARDADO", 540, 1330, 70, t, 25.8, BLANCO)
    if 26.35 <= t < 27.35:
        k = pop(t, 26.35, 0.3)
        r = 400 * k
        d.ellipse((540 - r, 880 - r, 540 + r, 880 + r), outline=(255, 255, 255, 70), width=16)
        d.arc((540 - r, 880 - r, 540 + r, 880 + r), -90, -90 + 360 * pr(t, 26.45, 27.25), fill=AMARILLO + (255,),
              width=20)
        n = min(10, int(1 + 10 * pr(t, 26.45, 27.25)))
        caja(d, 540 - 150, 420 - 80 * k, 540 + 150, 420 + 80 * k, 40, (0, 0, 0, 200), outline=AMARILLO + (255,), w=5)
        texto(d, f"{n} s", 540, 420, 110 * k, AMARILLO, stroke=0)
    if 27.4 <= t < 28.6:
        texto_pop(d, "¡OTRA VEZ!", 540, 420, 100, t, 27.4, AMARILLO)
    if explic > 0:
        rx, ry = 820, 560
        k = pop(t, 29.3, 0.4)
        caja(d, rx - 150 * k, ry - 150 * k, rx + 150 * k, ry + 190 * k, 40, (0, 0, 0, int(140 * explic)))
        rot = (t * 140) % 360
        d.arc((rx - 110 * k, ry - 110 * k, rx + 110 * k, ry + 110 * k), rot, rot + 290, fill=ac + (255,), width=16)
        sprite(img, "🔁", rx, ry, 110 * k)
        texto(d, "HÁBITO", rx, ry + 155 * k, 46 * k, ac)
        if t >= 31.2:
            n = min(99, 1 + int((t - 31.2) * 9))
            kk = pop(t, 31.2, 0.3)
            bx, by = cx + 130 * s, cy - 290 * s
            d.ellipse((bx - 50 * kk, by - 50 * kk, bx + 50 * kk, by + 50 * kk), fill=(255, 59, 48, 255),
                      outline=BLANCO + (255,), width=5)
            texto(d, str(n), bx, by, 46 * kk, BLANCO, stroke=0)
        for ch, t0, x, y in (("🔔", 31.2, 820, 870), ("❤️", 31.6, 930, 1010), ("💬", 32.0, 760, 1060)):
            if t < t0:
                continue
            v = eo(pr(t, t0, t0 + 0.5))
            xx = cx + (x - cx) * v
            yy = cy + (y - cy) * v + math.sin(t * 4 + x) * 10
            sprite(img, ch, xx, yy, 130 * pop(t, t0, 0.4), rot=math.sin(t * 5 + x) * 10)


def esc_bostezo(img, d, t, ac):
    img.paste(entorno("metro"))
    # ventanillas: luces del túnel pasando
    rng = random.Random(1)
    for x0, x1 in ((66, 494), (586, 1014)):
        d.rounded_rectangle((x0, 421, x1, 759), 26, fill=(18, 24, 42, 255))
        for i in range(14):
            y = 440 + rng.random() * 300
            L = rng.uniform(80, 260)
            vel = rng.uniform(1600, 2600)
            x = x1 - ((t * vel + rng.random() * 3000) % 1600)
            a, b = max(x0 + 10, x), min(x1 - 10, x + L)
            if b > a:
                col = (255, 214, 120) if i % 3 else (120, 200, 255)
                d.line((a, y, b, y), fill=col + (int(rng.uniform(90, 200)),), width=rng.choice([3, 5, 8]))
        d.rounded_rectangle((x0, 421, x1, 759), 26, outline=(150, 158, 170, 255), width=8)
        d.line((x0 + 40, 440, x0 + 140, 740), fill=(255, 255, 255, 25), width=30)
    vaiven = math.sin(t * 2.2) * 5
    # tiempos de bostezo (inicio, fin) por pasajero
    bost = {0: [(34.6, 36.4)], 1: [(36.5, 38.3), (41.5, 43.0)], 2: [(38.7, 40.4)]}
    caras = {0: "😐", 1: "😐", 2: "😑"}
    pos = [(200, (220, 80, 70)), (540, (40, 170, 160)), (880, (130, 90, 200))]
    cabezas = []
    for i, (x, camisa) in enumerate(pos):
        cara = caras[i]
        for a, b in bost[i]:
            if a <= t < b:
                cara = "🥱"
        movil_mano = i == 1 and t >= 40.3
        p = persona(img, d, x, 1005 + vaiven * (0.6 + 0.2 * i), 0.95, camisa=camisa,
                    pantalon=[(50, 60, 90), (60, 60, 70), (40, 50, 80)][i], cara=cara, sentado=True,
                    brazos=0.32 if movil_mano else 0.0, cara_rot=math.sin(t * 3 + i) * 3 if cara == "🥱" else 0)
        cabezas.append(p["cabeza"])
        for a, b in bost[i]:
            ondas_bostezo(d, p["cabeza"][0], p["cabeza"][1], t, a, 150)
            if a <= t < a + 1.2:
                texto(d, "¡AAAH!", p["cabeza"][0], p["cabeza"][1] - 130, 46 * pop(t, a, 0.3), AMARILLO, stroke=6)
        if movil_mano:
            pegar_movil(img, d, x, 1010 + vaiven, 0.33, t, pantalla="video", rot=0, sombra=False)
    # barras verticales delante
    for x in (370, 710):
        d.rectangle((x - 13, 250, x + 13, H), fill=(196, 203, 212, 255))
        d.rectangle((x - 5, 250, x + 1, H), fill=(240, 244, 248, 255))
    # etiquetas
    if 35.0 <= t < 40.3:
        a = pr(t, 35.0, 35.3) * (1 - pr(t, 40.0, 40.3))
        texto(d, "TÚ", cabezas[1][0], 1195, 58, AMARILLO, alpha=a)
    if 35.4 <= t < 37.9:
        k = eo(pr(t, 35.4, 36.2))
        flecha_curva(d, (cabezas[0][0] + 60, cabezas[0][1] - 120), (cabezas[1][0] - 50, cabezas[1][1] - 120), 90,
                     ac + (255,), 10, k)
    if 38.2 <= t < 40.2:
        k = eo(pr(t, 38.2, 38.8))
        flecha_curva(d, (cabezas[1][0] + 50, cabezas[1][1] - 120), (cabezas[2][0] - 60, cabezas[2][1] - 120), 90,
                     ac + (255,), 10, k)
        texto_pop(d, "¡SE CONTAGIA!", W / 2, 420, 84, t, 38.4, AMARILLO)
    if t >= 40.4:
        # lupa sobre el móvil: un vídeo de alguien bostezando
        k = pop(t, 40.45, 0.4)
        bx, by, r = 230, 640, 130 * k
        d.line((bx + r * 0.6, by + r * 0.6, cabezas[1][0] - 20, 960), fill=(255, 255, 255, 180), width=5)
        d.ellipse((bx - r - 8, by - r - 8, bx + r + 8, by + r + 8), fill=BLANCO + (255,))
        d.ellipse((bx - r, by - r, bx + r, by + r), fill=(250, 225, 160, 255))
        sprite(img, "🥱", bx, by - 10 * k, 190 * k, sombra=False)
        d.polygon([(bx - 26 * k, by + 70 * k), (bx + 30 * k, by + 100 * k), (bx - 26 * k, by + 130 * k)],
                  fill=(255, 255, 255, 230))
        texto(d, "VÍDEO", bx, by + r + 36, 40 * k, BLANCO)
        texto(d, "TÚ", cabezas[1][0], 1195, 58, AMARILLO, alpha=pr(t, 40.5, 40.8))
    if t >= 41.9:
        texto_pop(d, "¿YA HAS BOSTEZADO?", W / 2, 420, 70, t, 41.9, AMARILLO)


COCHES = []
_r = random.Random(12)
_tt = 42.3
while _tt < 50.6:
    carril = len(COCHES) % 2
    COCHES.append((_tt, carril, _r.choice(["🚗", "🚙", "🚚", "🚕"]), _r.uniform(1100, 1500)))
    _tt += _r.uniform(0.45, 0.9)


def semaforo_coches(d, x, y, estado, t):
    caja(d, x - 78, y, x + 78, y + 420, 34, (32, 34, 40, 255), outline=(80, 84, 94, 255), w=6)
    for i, col in enumerate([(255, 60, 60), (255, 190, 40), (60, 220, 110)]):
        cy = y + 75 + i * 135
        on = estado == i
        if on:
            for g in range(5, 0, -1):
                r = 58 + g * 13
                d.ellipse((x - r, cy - r, x + r, cy + r), fill=col + (int(26 + 4 * math.sin(t * 6)),))
        d.ellipse((x - 54, cy - 54, x + 54, cy + 54), fill=(col if on else tuple(int(v * 0.22) for v in col)) + (255,))
        d.ellipse((x - 34, cy - 40, x - 6, cy - 20), fill=(255, 255, 255, 70 if on else 12))


def esc_semaforo(img, d, t, ac):
    img.paste(entorno("calle"))
    # nubes
    for i, (y, s, v) in enumerate(((180, 1.0, 22), (300, 0.7, 14), (120, 0.8, 30))):
        x = (i * 420 + t * v) % (W + 400) - 200
        for dx, dy, r in ((0, 0, 60), (55, -25, 70), (115, 0, 55), (60, 15, 60)):
            d.ellipse((x + dx * s - r * s, y + dy * s - r * s * 0.7, x + dx * s + r * s, y + dy * s + r * s * 0.7),
                      fill=(255, 255, 255, 230))
    verde = t >= 50.9
    # coches
    for t0, carril, ch, vel in COCHES:
        if verde and t0 > 50.5:
            continue
        dt = t - t0
        if dt < 0:
            continue
        if carril == 0:
            x, y, flip, size = W + 160 - dt * vel, 925, False, 220
        else:
            x, y, flip, size = -160 + dt * vel, 1005, True, 250
        if -200 < x < W + 200:
            for k in range(4):
                lx = x + (140 if not flip else -140) + (k * 30 if not flip else -k * 30)
                d.line((lx, y - 20 + k * 14, lx + (90 if not flip else -90), y - 20 + k * 14),
                       fill=(255, 255, 255, 90 - k * 18), width=5)
            sprite(img, ch, x, y, size, flip=flip)
    semaforo_coches(d, 151, 400, 2 if verde else 0, t)
    # semáforo peatonal + cuenta atrás
    caja(d, 92, 850, 210, 990, 18, (32, 34, 40, 255))
    col = (60, 220, 110) if verde else (255, 70, 70)
    hx, hy = 151, 900
    d.ellipse((hx - 12, hy - 34, hx + 12, hy - 10), fill=col + (255,))
    d.rounded_rectangle((hx - 16, hy - 8, hx + 16, hy + 40), 8, fill=col + (255,))
    if not verde:
        n = max(1, int(math.ceil(30 - max(0, t - 43.0) * 0.45)))
        caja(d, 92, 996, 210, 1060, 14, (10, 10, 12, 255))
        texto(d, f"{n:02d}", 151, 1028, 50, (255, 80, 80), stroke=0)
    # peatón
    if not verde:
        p = persona(img, d, 620, 1240, 1.08, camisa=(250, 150, 40), pantalon=(50, 70, 120), cara="😤",
                    pie=abs(math.sin(t * 9)) if t >= 43.3 else 0, cara_rot=math.sin(t * 14) * 4,
                    brazos=0.0)
        hx, hy = p["cabeza"]
        if t >= 44.7:
            texto_pop(d, "¡NO SE ACABA NUNCA!", W / 2, 1385, 62, t, 44.7, AMARILLO) if t < 47.0 else None
            sprite(img, "⌚", p["manos"][1][0] + 10, p["manos"][1][1] - 10, 80 * pop(t, 44.7, 0.3), sombra=False)
    else:
        f = eio(pr(t, 51.0, 51.85))
        x = 620 + 160 * f
        yp = 1240 - 330 * f
        e = 1.08 - 0.5 * f
        persona(img, d, x, yp, e, camisa=(250, 150, 40), pantalon=(50, 70, 120), cara="😌",
                paso=t * 10 if t > 51.0 else None, espalda=f > 0.15, pelo=(60, 40, 25))
        texto_pop(d, "¡POR FIN!", W / 2, 430, 96, t, 50.9, (90, 230, 120))
    # explicación: reloj bajo la lupa
    if t >= 47.0:
        a = pr(t, 47.0, 47.4)
        k = pop(t, 47.2, 0.4)
        cx, cy, r = 860, 540, 125 * k
        lento = 1 + 6 * pr(t, 48.4, 49.6)
        ang = (t - 47.0) * 90 / lento
        if not verde:
            d.ellipse((cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10), fill=(0, 0, 0, int(90 * a)))
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 250, 250, int(255 * a)), outline=ac + (int(255 * a),),
                      width=10)
            for i in range(12):
                an = i * math.pi / 6
                d.line((cx + math.cos(an) * r * 0.78, cy + math.sin(an) * r * 0.78, cx + math.cos(an) * r * 0.9,
                        cy + math.sin(an) * r * 0.9), fill=(40, 40, 50, int(255 * a)), width=5)
            an = math.radians((ang * 6) % 360 - 90)
            d.line((cx, cy, cx + math.cos(an) * r * 0.8, cy + math.sin(an) * r * 0.8), fill=(230, 40, 40, 255), width=7)
            d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=(30, 30, 40, 255))
            if t >= 49.3:
                sprite(img, "🔍", cx + 70, cy - 40, 240 * pop(t, 49.3, 0.4), rot=-15 + 6 * math.sin(t * 2))
            if t >= 50.1:
                texto_pop(d, "1 SEGUNDO = ∞", 870, cy + 200, 50, t, 50.1, AMARILLO)


def esc_mirada(img, d, t, ac):
    img.paste(entorno("noche"))
    # luciérnagas
    for i in range(12):
        x = (i * 97 + math.sin(t * 0.7 + i) * 40) % 460
        y = 900 + (i * 53) % 250 + math.cos(t + i) * 20
        a = int(120 + 120 * math.sin(t * 3 + i))
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(220, 255, 140, a))
    expl = pr(t, 57.0, 57.5)
    girado = t >= 55.55
    f = eio(pr(t, 52.0, 53.6))
    x = 560 + 180 * f
    yp = 1480 - 140 * f
    e = 1.15 - 0.1 * f
    andando = 52.0 < t < 53.6
    if girado:
        k = pop(t, 55.55, 0.3)
        temblor = math.sin(t * 40) * 6 * (1 - pr(t, 55.6, 56.4))
        p = persona(img, d, x + temblor, yp, e, camisa=(70, 110, 190), pantalon=(35, 38, 52), cara="😱",
                    brazos=0.45 * k)
    else:
        p = persona(img, d, x, yp, e, camisa=(70, 110, 190), pantalon=(35, 38, 52), espalda=True,
                    paso=t * 9 if andando else None, pelo=(50, 32, 22))
    hx, hy = p["cabeza"]
    if t >= 53.4:
        ka = pr(t, 53.4, 54.2)
        ex, ey = 230, 990
        for g in range(6, 0, -1):
            r = 40 + g * 18
            d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=(255, 240, 160, int(10 * ka)))
        parp = 0.15 if (t % 2.3) < 0.12 else 1
        im = sprite_img("👀", 150)
        im = im.resize((150, max(4, int(150 * parp))))
        if ka < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * ka)))
        img.paste(im, (int(ex - 75), int(ey - im.height / 2)), im)
        if not girado:
            for i in range(9):
                ff = ((t * 0.9) + i / 9) % 1
                xx = ex + 70 + (hx - 60 - ex - 70) * ff
                yy = ey - 20 + (hy - ey + 20) * ff
                d.ellipse((xx - 6, yy - 6, xx + 6, yy + 6), fill=(255, 240, 160, int(200 * ka * (1 - ff))))
    if 54.3 <= t < 55.5:
        texto_pop(d, "...", hx, hy - 180, 90, t, 54.3, BLANCO)
    if girado and t < 57.3:
        texto_pop(d, "¡!", hx, hy - 190, 140, t, 55.6, AMARILLO)
    if expl > 0:
        d.rectangle((0, 0, W, H), fill=(5, 4, 20, int(150 * expl)))
        cx, cy = min(hx, W - 380), hy
        k = pop(t, 57.4, 0.45)
        rad = 360 * k
        d.pieslice((cx - rad, cy - rad, cx + rad, cy + rad), 160, 380, fill=ac + (int(40 * expl),))
        for i in range(3):
            anillo(d, cx, cy, rad * (i + 1) / 3, ac + (int(90 * expl),), 3)
        bar = (t * 140) % 360
        d.pieslice((cx - rad, cy - rad, cx + rad, cy + rad), bar - 14, bar, fill=ac + (int(110 * expl),))
        sprite(img, "🧠", cx, cy, 150 * k, alpha=expl)
        if t >= 59.0:
            for i, (ang, rr) in enumerate([(200, 0.85), (165, 0.7), (230, 0.95), (190, 0.55)]):
                kk = pop(t, 59.0 + i * 0.2, 0.3)
                an = math.radians(ang + 8 * math.sin(t * 3 + i))
                x2, y2 = cx + math.cos(an) * rad * rr, cy + math.sin(an) * rad * rr
                d.ellipse((x2 - 16 * kk, y2 - 16 * kk, x2 + 16 * kk, y2 + 16 * kk), fill=AMARILLO + (255,))
                anillo(d, x2, y2, 28 + 20 * ((t * 2 + i / 4) % 1), AMARILLO + (150,), 3)
            texto(d, "MOVIMIENTOS", 260, cy - rad - 40, 44, AMARILLO, alpha=pr(t, 59.0, 59.3))
        if t >= 60.4:
            kk = pop(t, 60.4, 0.35)
            sx, sy = min(W - 90, cx + rad * 0.8), cy + 40
            sprite(img, "👂", sx, sy, 130 * kk)
            for i in range(3):
                ff = ((t * 1.4) + i / 3) % 1
                r = 70 + 140 * ff
                d.arc((sx - r, sy - r, sx + r, sy + r), 150, 230, fill=(255, 255, 255, int(200 * (1 - ff))), width=6)
            texto(d, "SONIDOS", min(W - 140, cx + 180), cy - rad - 40, 44, BLANCO, alpha=pr(t, 60.4, 60.7))
        if t >= 61.3:
            texto_pop(d, "...SIN DARTE CUENTA", W / 2, 1150, 62, t, 61.3)


def esc_final(img, d, t, ac):
    rayos(d, t, W / 2, 900, ac, alpha=16)
    confeti(d, t, 62.85)
    if t < 67.0:
        texto_pop(d, "AHORA DIME...", W / 2, 260, 0 if t >= 64.2 else 90, t, 63.1)
        texto_pop(d, "¿CUÁL HACES TÚ?", W / 2, 260, 100, t, 64.2, AMARILLO)
        for i, (env, ch, lab) in enumerate(GANCHO):
            t0 = 63.4 + i * 0.22
            if t < t0:
                continue
            k = eo(pr(t, t0, t0 + 0.4))
            y = 450 + i * 165
            x0 = 110 + (1 - k) * -700
            caja(d, x0, y - 70, x0 + 860, y + 70, 34, (0, 0, 0, 120), outline=ac + (200,), w=4)
            m = miniatura(env, 120, 120)
            img.paste(m, (int(x0 + 12), int(y - 60)), m)
            sprite(img, ch, x0 + 120, y + 40, 60, sombra=False)
            texto(d, lab, x0 + 175, y, 58, BLANCO, anchor="lm")
            caja(d, x0 + 740, y - 40, x0 + 820, y + 40, 16, (255, 255, 255, 40), outline=BLANCO + (220,), w=5)
            tc = 65.4 + i * 0.25
            if t >= tc:
                sprite(img, "✅", x0 + 780, y, 96 * pop(t, tc, 0.3), sombra=False)
    else:
        texto_pop(d, "Y CONFIESA...", W / 2, 260, 96, t, 67.2, AMARILLO)
        sacude = math.sin(t * 30) * 5 if 68.3 <= t < 69.0 else 0
        pegar_movil(img, d, W / 2 + sacude, 790, 0.92, t, pantalla="feed")
        if t >= 68.3:
            n = min(9, 1 + int((t - 68.3) * 2.6))
            k = pop(t, 68.3 + (n - 1) / 2.6, 0.25)
            caja(d, W / 2 - 210, 1120, W / 2 + 210, 1240, 40, (0, 0, 0, 210), outline=ac + (255,), w=5)
            texto(d, f"x{n}", W / 2 + 50, 1180, 92 * k, AMARILLO, stroke=0)
            sprite(img, "👀", W / 2 - 100, 1180, 92, sombra=False)
            texto(d, "¿CUÁNTAS VECES?", W / 2, 370, 64, BLANCO, alpha=pr(t, 68.3, 68.6))
        if t >= 70.2:
            k = pop(t, 70.2, 0.4)
            bob = math.sin(t * 8) * 12
            caja(d, W / 2 - 280 * k, 1335 - 60 * k, W / 2 + 280 * k, 1335 + 60 * k, 60, ac + (255,))
            texto(d, "COMENTA", W / 2 - 50, 1335, 70 * k, (15, 30, 20), stroke=0)
            sprite(img, "👇", W / 2 + 190, 1335 + bob, 100 * k)


ESCENAS = {"intro": esc_intro, "gancho": esc_gancho, "puerta": esc_puerta, "movil": esc_movil,
           "bostezo": esc_bostezo, "semaforo": esc_semaforo, "mirada": esc_mirada, "final": esc_final}


def camara(nombre, t, t0, t1):
    """(zoom, centro x, centro y) de la cámara de cada escena."""
    if nombre == "mirada":
        z = 1 + 0.14 * eio(pr(t, 53.0, 55.5)) - 0.14 * eio(pr(t, 56.6, 57.4))
        return z, 760, 900
    if nombre == "puerta":
        return 1 + 0.06 * eio(pr(t, 15.0, 16.0)) * (1 - pr(t, 16.0, 16.5)), 540, 1000
    if nombre in ("movil", "bostezo", "semaforo"):
        return 1.0 + 0.05 * pr(t, t0, t1), 540, 900
    return 1.0, W / 2, H / 2
