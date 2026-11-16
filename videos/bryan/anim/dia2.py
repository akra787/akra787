"""Bryan Sport · Día 2: empieza la transformación.

Uso: python3 videos/bryan/anim/dia2.py videos/bryan_dia2.json
Reutiliza el motor de animacion.py (Bryan, coche, subtítulos, audio) y añade escenas nuevas.
Los tiempos de cada animación están en segundos desde el inicio de la escena (sincronizados con la voz).
"""
import math
import os
import random
import sys
from functools import lru_cache

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import animacion as A  # noqa
from animacion import *  # noqa
from arte import *  # noqa
from PIL import Image, ImageDraw, ImageFilter

AZUL = (70, 150, 255)


# ================================================================ utilidades
def bryan_s(fr, ctx, x, y, poses_seg, **kw):
    """Como dibujar_bryan pero con las poses en segundos."""
    dur = ctx["dur"]
    dibujar_bryan(fr, ctx, x, y, [(s / dur, p) for s, p in poses_seg], **kw)


def ventana(u, a, b, fade=0.3):
    """1 dentro de [a, b], con fundidos de entrada y salida."""
    if u < a or u > b + fade:
        return 0.0
    return min(1.0, (u - a) / fade, (b + fade - u) / fade)


def poly_parcial(d, pts, f, col, w):
    if f <= 0 or len(pts) < 2:
        return
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg) * clamp(f)
    out = [pts[0]]
    for i, L in enumerate(seg):
        if total >= L:
            out.append(pts[i + 1])
            total -= L
        else:
            q = total / L if L else 0
            out.append((lerp(pts[i][0], pts[i + 1][0], q), lerp(pts[i][1], pts[i + 1][1], q)))
            break
    d.line(out, fill=col, width=w, joint="curve")


def punto_en(pts, f):
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg) * (f % 1)
    for i, L in enumerate(seg):
        if total <= L:
            q = total / L if L else 0
            return lerp(pts[i][0], pts[i + 1][0], q), lerp(pts[i][1], pts[i + 1][1], q)
        total -= L
    return pts[-1]


def nube(w, h):
    key = ("nube", w, h)
    if key not in A._cache_txt:
        im = Image.new("RGBA", (w + 80, h + 140), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        rnd = random.Random(2)
        for i in range(14):
            a = i / 14 * 2 * math.pi
            x = 40 + w / 2 + math.cos(a) * w * 0.42
            y = 40 + h / 2 + math.sin(a) * h * 0.38
            r = rnd.uniform(0.18, 0.26) * min(w, h) + 20
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))
        d.ellipse([40 + w * 0.1, 40 + h * 0.1, 40 + w * 0.9, 40 + h * 0.9], fill=(255, 255, 255, 255))
        for cx, cy, r in ((70, h + 60, 22), (40, h + 105, 13)):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
        A._cache_txt[key] = im
    return A._cache_txt[key]


def esquina_dia2(fr, ctx, e):
    if e["tipo"] != "portada":
        pegar(fr, pastilla("DÍA 2", 34, ROJO), 95, 48)


A.POST.append(esquina_dia2)


# ================================================================ fondos nuevos
def fondo_garaje_casa():
    bw = 1240
    rnd = random.Random(21)
    im = gradiente(bw, H, (168, 152, 128), (98, 88, 76))
    arr = np.array(im).astype(np.int16)
    arr += np.random.default_rng(1).integers(-6, 7, arr.shape[:2])[:, :, None]
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    # zócalo
    d.rectangle([0, 1100, bw, 1180], fill=(120, 105, 90))
    # puerta seccional medio abierta con la calle al atardecer
    gx0, gx1, gy0, gy1 = 760, 1220, 360, 1180
    exterior = gradiente(gx1 - gx0, gy1 - gy0, (255, 150, 90), (255, 210, 150))
    im.paste(exterior, (gx0, gy0))
    d.rectangle([gx0, 1000, gx1, 1180], fill=(70, 70, 78))
    for bx in range(gx0 + 20, gx1, 120):
        d.ellipse([bx, 930, bx + 110, 1040], fill=(60, 120, 60))
    d.polygon([(gx0 + 150, 1000), (gx0 + 230, 880), (gx0 + 310, 1000)], fill=(80, 60, 70))
    for y in range(gy0, 770, 68):
        d.rectangle([gx0, y, gx1, y + 64], fill=(222, 222, 216))
        d.rectangle([gx0, y + 60, gx1, y + 64], fill=(180, 180, 175))
        d.rectangle([gx0 + 20, y + 14, gx1 - 20, y + 50], outline=(200, 200, 195), width=3)
    d.rectangle([gx0 - 18, gy0 - 18, gx0, gy1], fill=(80, 72, 64))
    d.rectangle([gx1, gy0 - 18, gx1 + 18, gy1], fill=(80, 72, 64))
    d.rectangle([gx0 - 18, gy0 - 18, gx1 + 18, gy0], fill=(80, 72, 64))
    # bici colgada
    for wx in (150, 400):
        d.ellipse([wx - 95, 210, wx + 95, 400], outline=(30, 30, 34), width=10)
        d.ellipse([wx - 10, 295, wx + 10, 315], fill=(160, 160, 170))
    d.line([(150, 305), (260, 220), (400, 305), (300, 305), (150, 305)], fill=(30, 140, 200), width=12)
    d.line([(260, 220), (300, 305)], fill=(30, 140, 200), width=12)
    d.line([(250, 200), (280, 200)], fill=(20, 20, 20), width=12)
    d.line([(380, 210), (420, 190)], fill=(20, 20, 20), width=8)
    for hx in (150, 400):
        d.line([(hx, 120), (hx, 210)], fill=(60, 60, 60), width=4)
    # estanterías de madera
    for sy in (560, 760):
        d.rectangle([40, sy, 640, sy + 22], fill=(150, 105, 60))
        d.rectangle([40, sy + 22, 640, sy + 30], fill=(110, 75, 40))
    latas = [(70, 560, (200, 40, 40)), (140, 560, (40, 90, 200)), (210, 560, (230, 200, 40)), (330, 560, (240, 240, 240)),
             (90, 760, (60, 160, 80)), (160, 760, (200, 120, 40))]
    for lx, ly, col in latas:
        d.rounded_rectangle([lx, ly - 80, lx + 55, ly], radius=6, fill=col)
        d.rectangle([lx, ly - 80, lx + 55, ly - 70], fill=(170, 170, 175))
        d.rectangle([lx + 6, ly - 55, lx + 49, ly - 30], fill=(250, 250, 245))
    for i, (bx, lab) in enumerate(((260, "NAVIDAD"), (430, "TRASTOS"))):
        d.rectangle([bx, 760 - 110, bx + 150, 760], fill=(190, 150, 100))
        d.line([(bx, 760 - 80), (bx + 150, 760 - 80)], fill=(160, 120, 80), width=4)
        d.text((bx + 14, 760 - 60), lab, font=fuente(26), fill=(90, 60, 30))
    for sx in range(420, 600, 34):
        d.rounded_rectangle([sx, 480, sx + 26, 560], radius=8, fill=rnd.choice([(30, 30, 30), ROJO, (240, 240, 240)]))
        d.rectangle([sx + 8, 470, sx + 18, 482], fill=(90, 90, 90))
    # banco de trabajo
    d.rectangle([40, 960, 660, 1000], fill=(140, 95, 55))
    d.rectangle([40, 1000, 660, 1012], fill=(100, 65, 35))
    for lx in (60, 620):
        d.rectangle([lx, 1000, lx + 22, 1180], fill=(100, 65, 35))
    d.rectangle([90, 900, 190, 960], fill=(70, 75, 85))  # tornillo de banco
    d.rectangle([110, 870, 170, 900], fill=(90, 95, 105))
    d.rounded_rectangle([420, 905, 540, 960], radius=10, fill=(40, 40, 46))  # radio
    d.ellipse([435, 915, 470, 950], fill=(90, 90, 100))
    d.rectangle([480, 920, 525, 930], fill=(120, 220, 255))
    d.rounded_rectangle([580, 915, 620, 960], radius=6, fill=(240, 240, 235))  # taza
    d.text((588, 925), "BS", font=fuente(18), fill=ROJO)
    for bx, col, lab in ((90, (210, 175, 120), "COCHE"), (320, (200, 160, 110), "PIEZAS")):
        d.rectangle([bx, 1060, bx + 190, 1180], fill=col)
        d.text((bx + 30, 1100), lab, font=fuente(28), fill=(90, 60, 30))
    # póster y calendario
    d.rectangle([680, 430, 740, 520], fill=(250, 250, 245))
    d.rectangle([680, 430, 740, 450], fill=ROJO)
    d.text((690, 470), "16", font=fuente(30), fill=(30, 30, 30))
    # suelo de hormigón
    suelo = gradiente(bw, H - 1180, (128, 124, 118), (70, 68, 66))
    im.paste(suelo, (0, 1180))
    d = ImageDraw.Draw(im)
    for _ in range(9):
        x, y = rnd.uniform(0, bw), rnd.uniform(1250, 1800)
        d.line([(x, y), (x + rnd.uniform(-120, 120), y + rnd.uniform(10, 80))], fill=(95, 92, 88), width=3)
    d.ellipse([820, 1590, 1060, 1640], fill=(70, 66, 64))
    d.line([(0, 1180), (bw, 1180)], fill=(60, 55, 50), width=6)
    # bombilla colgante con luz cálida
    luz = Image.new("RGB", (bw, H))
    ld = ImageDraw.Draw(luz)
    d.line([(560, 0), (560, 250)], fill=(30, 30, 30), width=4)
    d.rectangle([548, 240, 572, 262], fill=(60, 60, 60))
    d.ellipse([536, 255, 584, 310], fill=(255, 240, 190))
    ld.ellipse([480, 200, 640, 360], fill=(255, 210, 120))
    ld.polygon([(530, 300), (590, 300), (1050, 1700), (70, 1700)], fill=(45, 36, 18))
    im = brillo(im, luz, 45)
    return im


def fondo_plano():
    bw = 1240
    im = gradiente(bw, H, (18, 62, 128), (8, 30, 72))
    d = ImageDraw.Draw(im)
    for x in range(0, bw, 40):
        d.line([(x, 0), (x, H)], fill=(40, 90, 160) if x % 200 else (70, 125, 200), width=1 if x % 200 else 2)
    for y in range(0, H, 40):
        d.line([(0, y), (bw, y)], fill=(40, 90, 160) if y % 200 else (70, 125, 200), width=1 if y % 200 else 2)
    x0 = 640
    d.rectangle([x0, H - 330, x0 + 480, H - 190], outline=(150, 200, 255), width=3)
    d.line([(x0, H - 270), (x0 + 480, H - 270)], fill=(150, 200, 255), width=2)
    d.text((x0 + 20, H - 318), "BRYAN SPORT · PROYECTO STAGE 2", font=fuente(26), fill=(170, 210, 255))
    d.text((x0 + 20, H - 255), "ESCALA 1:10   ·   HOJA 2/5", font=fuente(24, False), fill=(150, 190, 240))
    return im


@lru_cache(None)
def fondos2():
    return {"garaje": fondo_garaje_casa(), "plano": fondo_plano(), "tarde": fondo_calle(noche=False)}


def fondo2(nombre, desplaz):
    bg = fondos2()[nombre]
    x = int(clamp(80 + desplaz, 0, bg.width - W))
    return bg.crop((x, 0, x + W, H)).copy(), x


def gato(fr, x, y, u):
    """Gato dormilón en la estantería; mueve la cola y parpadea."""
    d = ImageDraw.Draw(fr)
    c = (40, 36, 40)
    a = math.sin(u * 2.2) * 0.6
    cola = [(x + 50, y - 10)]
    for i in range(1, 8):
        cola.append((x + 50 + i * 12, y - 10 - math.sin(i * 0.5 + a) * i * 7))
    d.line(cola, fill=c, width=12, joint="curve")
    d.ellipse([x - 60, y - 60, x + 60, y], fill=c)
    d.ellipse([x - 85, y - 95, x - 25, y - 35], fill=c)
    d.polygon([(x - 85, y - 80), (x - 80, y - 115), (x - 63, y - 90)], fill=c)
    d.polygon([(x - 50, y - 90), (x - 35, y - 115), (x - 28, y - 78)], fill=c)
    abre = 0 if (u % 4.0) < 0.2 else 6
    for ex in (-70, -45):
        d.ellipse([x + ex - 6, y - 70 - abre / 2, x + ex + 6, y - 70 + abre / 2], fill=(140, 220, 90))


# ================================================================ sprites nuevos
@lru_cache(None)
def llanta_deportiva(r, ang_q):
    k = 2
    R = r * k
    size = int(R * 2.3)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    d.ellipse([c - R, c - R, c + R, c + R], fill=(20, 20, 22, 255))  # neumático
    for i in range(36):  # dibujo del neumático
        a = math.radians(i * 10 + ang_q)
        d.line([(c + math.cos(a) * R * 0.93, c + math.sin(a) * R * 0.93), (c + math.cos(a) * R, c + math.sin(a) * R)],
               fill=(45, 45, 48, 255), width=int(6 * k))
    r2 = R * 0.74
    d.ellipse([c - r2, c - r2, c + r2, c + r2], fill=(225, 30, 50, 255))  # labio rojo
    r3 = r2 * 0.93
    d.ellipse([c - r3, c - r3, c + r3, c + r3], fill=(30, 30, 34, 255))
    # pinza de freno
    d.pieslice([c - r3 * 0.85, c - r3 * 0.85, c + r3 * 0.85, c + r3 * 0.85], 200, 260, fill=(255, 210, 40, 255))
    d.ellipse([c - r3 * 0.7, c - r3 * 0.7, c + r3 * 0.7, c + r3 * 0.7], fill=(110, 110, 118, 255))  # disco
    for i in range(10):  # radios dobles
        a = math.radians(ang_q + i * 36)
        for da in (-4, 4):
            b = a + math.radians(da)
            d.line([(c + math.cos(b) * r3 * 0.2, c + math.sin(b) * r3 * 0.2), (c + math.cos(b) * r3 * 0.97, c + math.sin(b) * r3 * 0.97)],
                   fill=(15, 15, 18, 255), width=int(9 * k))
            d.line([(c + math.cos(b) * r3 * 0.2, c + math.sin(b) * r3 * 0.2), (c + math.cos(b) * r3 * 0.95, c + math.sin(b) * r3 * 0.95)],
                   fill=(70, 70, 78, 255), width=int(4 * k))
    d.ellipse([c - r3 * 0.24, c - r3 * 0.24, c + r3 * 0.24, c + r3 * 0.24], fill=(20, 20, 22, 255))
    f = fuente(int(r3 * 0.22))
    tw = d.textlength("BS", font=f)
    d.text((c - tw / 2, c - r3 * 0.14), "BS", font=f, fill=(225, 30, 50, 255))
    return im.resize((size // k, size // k), Image.LANCZOS)


@lru_cache(None)
def baquet(alto=480):
    k = 2
    s = alto / 520 * k
    im = Image.new("RGBA", (int(400 * s), int(530 * s)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P = lambda pts: [(x * s, y * s) for x, y in pts]
    negro, rojo = (28, 28, 32, 255), (205, 25, 40, 255)
    d.rounded_rectangle(P([(110, 0), (290, 135)]), radius=int(40 * s), fill=negro)
    d.polygon(P([(55, 110), (345, 110), (370, 300), (335, 470), (65, 470), (30, 300)]), fill=negro)
    d.polygon(P([(120, 130), (280, 130), (295, 300), (272, 440), (128, 440), (105, 300)]), fill=rojo)
    for yy in range(170, 430, 40):
        d.line(P([(125, yy), (275, yy)]), fill=(170, 15, 30, 255), width=int(4 * s))
    d.rounded_rectangle(P([(45, 425), (355, 525)]), radius=int(30 * s), fill=negro)
    d.rounded_rectangle(P([(105, 438), (295, 505)]), radius=int(20 * s), fill=rojo)
    for hx in (150, 250):
        d.rounded_rectangle(P([(hx - 22, 70), (hx + 22, 110)]), radius=int(10 * s), fill=(10, 10, 12, 255))
    # arneses
    for hx, bx in ((150, 185), (250, 215)):
        d.line(P([(hx, 100), (bx, 360)]), fill=(240, 40, 50, 255), width=int(26 * s))
    for x0, x1 in ((90, 185), (310, 215)):
        d.line(P([(x0, 470), (x1, 380)]), fill=(240, 40, 50, 255), width=int(24 * s))
    d.ellipse(P([(165, 345), (235, 415)]), fill=(200, 205, 215, 255))
    d.ellipse(P([(182, 362), (218, 398)]), fill=(140, 145, 155, 255))
    f = fuente(int(40 * s))
    tw = d.textlength("BS", font=f)
    d.text((200 * s - tw / 2, 18 * s), "BS", font=f, fill=(255, 255, 255, 255))
    return im.resize((im.width // k, im.height // k), Image.LANCZOS)


def tarjeta_notificacion():
    key = "notif"
    if key not in A._cache_txt:
        c = tarjeta(760, 150, (255, 255, 255), 34).copy()
        d = ImageDraw.Draw(c)
        for i in range(40):
            col = mix((255, 160, 40), (210, 40, 160), i / 40)
            d.ellipse([60 + i * 0.4, 52 + i * 0.4, 160 - i * 0.4, 152 - i * 0.4], outline=col, width=3)
        d.ellipse([70, 62, 150, 142], fill=(40, 40, 50))
        d.text((92, 74), "R", font=fuente(52), fill=(255, 255, 255))
        d.text((185, 62), "rubettos", font=fuente(42), fill=(20, 20, 20))
        d.text((185, 112), "empezó a seguirte", font=fuente(32, False), fill=(110, 110, 120))
        d.rounded_rectangle([600, 85, 760, 130], radius=14, fill=(40, 120, 255))
        d.text((625, 90), "Seguir", font=fuente(30), fill=(255, 255, 255))
        A._cache_txt[key] = c
    return A._cache_txt[key]


def pegatina(texto, ancho=300):
    key = ("peg", texto, ancho)
    if key not in A._cache_txt:
        h = int(ancho * 0.36)
        im = Image.new("RGBA", (ancho + 20, h + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([10, 10, ancho + 10, h + 10], radius=int(h * 0.3), fill=(255, 255, 255), outline=ROJO, width=6)
        f1 = fuente(int(h * 0.26))
        f2 = fuente(int(h * 0.4))
        for txt_, f, y, col in (("BRYAN SPORT CLUB", f1, h * 0.14, (40, 40, 40)), (texto, f2, h * 0.45, ROJO)):
            tw = d.textlength(txt_, font=f)
            d.text((10 + (ancho - tw) / 2, 10 + y), txt_, font=f, fill=col)
        A._cache_txt[key] = im
    return A._cache_txt[key]


def ranura(texto, ancho=300):
    key = ("ran", texto, ancho)
    if key not in A._cache_txt:
        h = int(ancho * 0.36)
        im = Image.new("RGBA", (ancho + 20, h + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i in range(0, 2 * (ancho + h), 26):  # borde discontinuo
            pts = []
            for j in (i, i + 14):
                if j < ancho:
                    pts.append((10 + j, 10))
                elif j < ancho + h:
                    pts.append((10 + ancho, 10 + j - ancho))
                elif j < 2 * ancho + h:
                    pts.append((10 + ancho - (j - ancho - h), 10 + h))
                else:
                    pts.append((10, 10 + h - (j - 2 * ancho - h)))
            d.line(pts, fill=(255, 255, 255), width=5)
        f = fuente(int(h * 0.36))
        tw = d.textlength(texto, font=f)
        d.text((10 + (ancho - tw) / 2, 10 + h * 0.3), texto, font=f, fill=ORO, stroke_width=3, stroke_fill=(0, 0, 0))
        A._cache_txt[key] = im
    return A._cache_txt[key]


def persiana(fr, abierta):
    """Persiana metálica que sube (abierta de 0 a 1)."""
    bajo = int(H * (1 - ease(abierta)))
    if bajo <= 0:
        return
    d = ImageDraw.Draw(fr)
    for y in range(bajo - 3000, bajo, 46):
        if y + 46 < 0:
            continue
        d.rectangle([0, y, W, y + 46], fill=(150, 155, 162))
        d.rectangle([0, y + 32, W, y + 46], fill=(118, 122, 130))
        d.line([(0, y + 4), (W, y + 4)], fill=(185, 190, 196), width=3)
    d.rectangle([0, bajo - 30, W, bajo], fill=(90, 92, 98))
    d.rounded_rectangle([W / 2 - 90, bajo - 70, W / 2 + 90, bajo - 40], radius=10, fill=(60, 60, 66))


# ================================================================ ESCENAS
def esc_portada(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    bg, _ = fondo2("garaje", 0)
    fr.paste(bg)
    pegar_coche(fr, 640, 1430, 0, color=ROJO, aleron=True, llanta=(45, 45, 50))
    bryan_s(fr, ctx, 210, 1730, [(0, "brazos_arriba")], salto=30 * abs(math.sin(u * 7)))
    s = pop(u, 0.6, 0.5)
    pegar(fr, txt("DÍA 2", 260, ROJO, 16, (255, 255, 255)), W / 2, 520, s, rot=-4 + math.sin(u * 3) * 2)
    pegar(fr, pastilla("¡EMPIEZA LA TRANSFORMACIÓN!", 50, (20, 20, 24)), W / 2, 760, pop(u, 1.4))
    chispas(fr, W / 2, 560, u, n=30, seed=3, color=ORO) if u > 0.8 else None
    persiana(fr, clamp((u - 0.15) / 1.0))


def esc_gancho(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    bg, _ = fondo_pan("club", 0)
    fr.paste(bg)
    luz = Image.new("RGB", (W, H))
    dl = ImageDraw.Draw(luz)
    for i, (sx, fase) in enumerate(((80, 0), (1000, 2))):
        a = math.sin(u * 1.5 + fase) * 0.35 + (0.25 if i == 0 else -0.25)
        tx = sx + math.sin(a) * 1700
        dl.polygon([(sx - 20, 0), (sx + 20, 0), (tx + 260, 1700), (tx - 260, 1700)], fill=(70, 60, 40))
    fr.paste(brillo(fr, luz, 25))
    gana = 2.7
    if u > gana:
        confeti(fr, u, 90, desde=gana)
    # panel de resultados
    vr = ventana(u, 0.0, 8.8)
    if vr > 0:
        pegar(fr, txt("RESULTADOS", 110, (255, 255, 255), 12, ROJO), W / 2, 200, pop(u, 0.1) * vr)
        q = ease((u - 0.3) / 2.3)
        card = tarjeta(860, 420, (255, 255, 255), 30).copy()
        d = ImageDraw.Draw(card)
        for i, (lab, pct, col) in enumerate((("A · NEGRO MATE", 32, ORO), ("B · STAGE 2", 68, AZUL))):
            y = 70 + i * 180
            d.text((70, y), lab, font=fuente(44), fill=(30, 30, 30))
            d.rounded_rectangle([70, y + 62, 830, y + 130], radius=34, fill=(230, 230, 236))
            w_ = int(760 * pct / 100 * q)
            if w_ > 40:
                d.rounded_rectangle([70, y + 62, 70 + w_, y + 130], radius=34, fill=col)
            d.text((70 + max(w_, 40) + 14 if w_ < 640 else 70 + w_ - 150, y + 72), f"{int(pct * q)}%", font=fuente(44),
                   fill=(30, 30, 30) if w_ < 640 else (255, 255, 255))
        pegar(fr, card, W / 2, 560, pop(u, 0.2, 0.5) * vr)
        if u > gana:
            s = pop(u, gana, 0.35)
            pegar(fr, txt("¡GANA LA B!", 120, (255, 255, 255), 12, (30, 80, 200)), W / 2, 870,
                  (2.2 - 1.2 * s if s < 1 else 1) * vr, rot=-8)
    if 3.8 < u < 5.4:
        pegar(fr, pastilla("TOCA CUMPLIR 🤝".replace(" 🤝", ""), 70, ROJO), W / 2, 1040, pop(u, 3.8))
        pegar(fr, emoji("🤝", 120), W / 2 + 330, 1040, pop(u, 3.95), rot=10 * math.sin(u * 8))
    # el coche entra como una máquina
    if u > 5.0:
        q = ease_out((u - 5.0) / 1.2)
        cx = lerp(1500, 720, q)
        pegar_coche(fr, cx, 1430, (cx - 720) * 0.6, color=ROJO, aleron=True, llanta=(45, 45, 50))
        if (u % 0.9) < 0.45 and u > 6.2:
            llamas(fr, cx - 0.8 * 480, 1430 + 0.8 * 67, u, 1.0)
        if 7.6 < u < 9.4:
            pegar(fr, txt("MODO MÁQUINA", 104, ORO, 12, (70, 20, 0)), W / 2 + math.sin(u * 40) * 5 * (u < 8.6), 1080,
                  pop(u, 7.6, 0.35) * ventana(u, 7.6, 9.1), rot=4)
    # se enciende el neón del taller
    if u > 9.3:
        on = (u - 9.3) > 0.5 or int(u * 20) % 3 == 0
        neon = neon_bs(apagado=not on)
        pegar(fr, neon, W / 2, 420, pop(u, 9.3, 0.3))
        pegar(fr, txt("HOY EMPIEZA EL TRABAJO", 62, (255, 255, 255), 8), W / 2, 590, pop(u, 9.8))
    # público
    d = ImageDraw.Draw(fr)
    for i in range(16):
        x = i * 72
        y = 1820 - abs(math.sin(u * 7 + i)) * (30 if u > gana else 8)
        d.ellipse([x - 40, y - 40, x + 40, y + 40], fill=(15, 8, 10))
        d.rounded_rectangle([x - 60, y + 30, x + 60, y + 200], radius=40, fill=(15, 8, 10))
    bryan_s(fr, ctx, 200, 1700, [(0, "saluda"), (2.6, "brazos_arriba"), (5.0, "senala_der"), (9.5, "pulgar")],
            escala=0.74, salto=40 * abs(math.sin(u * 8)) if gana < u < 4.6 else 0, mirar=(0.5, -0.2))


def esc_garaje(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    bg, ox = fondo2("garaje", -50 + 100 * u / dur)
    fr.paste(bg)
    gato(fr, 520 - (ox - 80), 760 - 112, u)
    if (u % 5.3) < 0.06:  # parpadeo de la bombilla
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 60))
        fr.paste(capa, (0, 0), capa)
    # motas de polvo en la luz
    d = ImageDraw.Draw(fr, "RGBA")
    rnd = random.Random(5)
    for i in range(40):
        x = 560 - (ox - 80) + rnd.uniform(-300, 300) + math.sin(u * 0.7 + i) * 30
        y = (rnd.uniform(300, 1600) - u * rnd.uniform(5, 25)) % 1400 + 300
        r = rnd.uniform(1.5, 3.5)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 240, 200, 120))
    pegar_coche(fr, 680, 1430, 0, color=ROJO, aleron=True, llanta=(45, 45, 50))
    pegar(fr, pastilla("🏠".replace("🏠", "") + "EL GARAJE DE CASA", 58, ROJO), W / 2, 170, pop(u, 0.3) * (1 - ventana(u, 5.6, 99) * 0))
    pegar(fr, emoji("🏠", 90), W / 2 - 370, 165, pop(u, 0.45))
    # herramientas que saltan
    va = ventana(u, 2.6, 5.4)
    for i, (em, x) in enumerate((("🔧", 620), ("🔨", 740), ("🪛", 860), ("⚙️", 980))):
        s = pop(u, 2.7 + i * 0.18)
        if s and va:
            pegar(fr, emoji(em, 110), x, 620 - abs(math.sin(u * 5 + i)) * 30, s * va)
    if va:
        pegar(fr, txt("NUESTRAS HERRAMIENTAS", 44, (255, 255, 255), 7), 790, 740, pop(u, 2.9) * va)
    # nube de pensamiento: taller pro ✗ → imaginación
    vn = ventana(u, 5.6, 12.0)
    if vn:
        n = nube(560, 330)
        bx, by = 520, 700
        pegar(fr, n, bx, by, pop(u, 5.6) * vn)
        if u < 8.3:
            pegar(fr, txt("TALLER PRO", 70, (40, 40, 40)), bx + 20, by - 20, pop(u, 5.8) * vn)
            if u > 6.6:
                pegar(fr, txt("✗", 240, (230, 30, 40), 6, (255, 255, 255)), bx + 20, by - 30, pop(u, 6.6, 0.3) * vn)
        else:
            lat = 1 + 0.08 * math.sin(u * 10)
            pegar(fr, emoji("💡", 130), bx - 140, by - 20, pop(u, 8.3) * lat * vn)
            pegar(fr, txt("IMAGINACIÓN\n+ GANAS", 56, (40, 40, 40)), bx + 70, by - 20, pop(u, 8.5) * vn)
    if 10.6 < u < 12.3:
        pegar(fr, txt("¡PROYECTAZO!", 120, ORO, 12, (80, 30, 0)), W / 2, 1080, pop(u, 10.6, 0.35), rot=-5)
        for i in range(6):
            a = i * math.pi / 3 + u
            pegar(fr, emoji("✨", 60), W / 2 + math.cos(a) * 420, 1080 + math.sin(a) * 120, pop(u, 10.7 + i * 0.05))
    # revisión con la lupa
    vr_ = ventana(u, 12.3, 15.2)
    if vr_:
        for i, (lab, x, y) in enumerate((("Ruedas ✓", 480, 1180), ("Frenos ✓", 760, 1160), ("Motor ✓", 960, 1220))):
            pegar(fr, pastilla(lab, 40, (30, 160, 80)), x, y, pop(u, 12.5 + i * 0.6) * vr_)
    # el plan
    if u > 15.3:
        card = tarjeta(470, 420, (250, 250, 245), 20, borde=((60, 60, 70), 6)).copy()
        dc = ImageDraw.Draw(card)
        dc.text((70, 55), "EL PLAN", font=fuente(48), fill=ROJO)
        items = ("Revisión", "Downpipe", "Intercooler", "Calibración")
        for i, it in enumerate(items):
            if u > 15.5 + i * 0.35:
                hecho = i == 0
                dc.text((70, 130 + i * 70), ("✓ " if hecho else f"{i + 1}. ") + it, font=fuente(40, False),
                        fill=(30, 140, 60) if hecho else (40, 40, 50))
        pegar(fr, card, 770, 760, pop(u, 15.3, 0.5), rot=-2)
    if u > 17.6:
        q = clamp((u - 17.6) / 1.4)
        pegar(fr, emoji("🚀", 140), 920, lerp(1150, 980, ease(q)), pop(u, 17.6), rot=-20)
        pegar(fr, pastilla("¡ESTO PROMETE!", 64, ROJO), W / 2 + 60, 1130, pop(u, 17.7))
    bryan_s(fr, ctx, 200, 1730, [(0, "saluda"), (2.6, "senala_der"), (5.6, "piensa"), (8.3, "brazos_arriba"),
                                 (10.6, "pulgar"), (12.3, "lupa"), (15.3, "carpeta"), (17.6, "pulgar")],
            escala=0.78, mirar=(0.6, -0.3) if 5.6 < u < 12 else (0.6, 0.1),
            salto=30 * abs(math.sin(u * 8)) if 8.3 < u < 9.4 else 0)


# coche en planos: piezas en coordenadas del coche (mirando a la derecha)
DOWNPIPE = [(330, 12), (348, 60), (300, 96), (100, 102), (-200, 102), (-440, 86), (-500, 68)]
AIRE = [(560, 40), (480, 40), (440, 40), (418, -42), (330, -45), (305, -18)]


def esc_stage2(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    bg, _ = fondo2("plano", 30 * math.sin(u * 0.2))
    fr.paste(bg)
    cx, cy, s = 560, 1060, 0.95
    P = lambda pts: [(cx + x * s, cy + y * s) for x, y in pts]
    capa = Image.new("RGB", (W, 700))
    oy = cy - 400
    dc = ImageDraw.Draw(capa)
    Q = lambda pts: [(x, y - oy) for x, y in P(pts)]
    blanco = (200, 230, 255)
    prog = clamp((u - 0.2) / 2.8)
    poly_parcial(dc, Q(CAR_BODY + [CAR_BODY[0]]), prog, blanco, 5)
    poly_parcial(dc, Q([(-120, -150), (-5, -155), (-5, -70), (-215, -65), (-120, -150)]), prog * 1.2 - 0.2, blanco, 4)
    poly_parcial(dc, Q([(15, -155), (140, -155), (250, -72), (15, -70), (15, -155)]), prog * 1.2 - 0.2, blanco, 4)
    for wx in WHEELS:
        pts = [(wx + math.cos(a / 20 * math.pi) * 92, 90 + math.sin(a / 20 * math.pi) * 92) for a in range(41)]
        poly_parcial(dc, Q(pts), prog * 1.3 - 0.3, blanco, 5)
        pts = [(wx + math.cos(a / 20 * math.pi) * 55, 90 + math.sin(a / 20 * math.pi) * 55) for a in range(41)]
        poly_parcial(dc, Q(pts), prog * 1.3 - 0.3, blanco, 3)
    if prog > 0.6:
        dc.rectangle(Q([(250, -60), (420, 40)])[0] + Q([(250, -60), (420, 40)])[1], outline=blanco, width=3)
        tx, ty = Q([(330, -10)])[0]
        dc.ellipse([tx - 22 * s, ty - 22 * s, tx + 22 * s, ty + 22 * s], outline=ORO, width=4)
    # downpipe
    fase_dp = ventana(u, 6.0, 12.0, 0.4)
    fase_ic = ventana(u, 12.2, 18.4, 0.4)
    col_dp = mix((120, 160, 200), (255, 140, 30), fase_dp)
    poly_parcial(dc, Q(DOWNPIPE), clamp((u - 2.0) / 1.5), col_dp, 10 if fase_dp else 6)
    # intercooler
    col_ic = mix((120, 160, 200), (60, 220, 255), fase_ic)
    if u > 3.0:
        x0, y0 = Q([(430, -2)])[0]
        x1, y1 = Q([(482, 86)])[0]
        dc.rectangle([x0, y0, x1, y1], outline=col_ic, width=6 if fase_ic else 4)
        for fx in range(int(x0) + 8, int(x1), 9):
            dc.line([(fx, y0 + 4), (fx, y1 - 4)], fill=col_ic, width=2)
        poly_parcial(dc, Q(AIRE[2:]), 1, col_ic, 6)
    # partículas de gases y de aire
    dcr = ImageDraw.Draw(capa)
    if fase_dp:
        rapido = 1.0 + 1.8 * ease((u - 10.6) / 1.0)
        for i in range(26):
            x, y = punto_en(Q(DOWNPIPE), (u * 0.35 * rapido + i / 26))
            r = 8
            dcr.ellipse([x - r, y - r, x + r, y + r], fill=(255, 170 - (i % 3) * 30, 40))
    if fase_ic:
        for i in range(22):
            x, y = punto_en(Q(AIRE), (u * 0.4 + i / 22))
            calor = clamp(i / 22 * 0)  # el aire sale frío
            r = 7
            dcr.ellipse([x - r, y - r, x + r, y + r], fill=(120, 220, 255))
    capa = brillo(capa, capa, 10)
    m = capa.convert("L").point(lambda v: min(255, v * 3))
    fr.paste(capa, (0, oy), m)
    # textos
    pegar(fr, txt("PREPARANDO", 80, (255, 255, 255), 8, (10, 40, 90)), W / 2, 170, pop(u, 0.2))
    pegar(fr, txt("LA STAGE 2", 130, ORO, 12, (10, 40, 90)), W / 2, 290, pop(u, 4.6, 0.4), rot=-3)
    vd = ventana(u, 6.2, 12.0)
    if vd:
        card = tarjeta(620, 200, (255, 140, 30), 26).copy()
        d = ImageDraw.Draw(card)
        d.text((60, 50), "DOWNPIPE", font=fuente(64), fill=(255, 255, 255))
        d.text((60, 138), "+ flujo de gases de escape", font=fuente(34, False), fill=(60, 25, 0))
        pegar(fr, card, W / 2, 520, pop(u, 6.2) * vd)
        if u > 10.6:
            humo(fr, cx - 500 * s, cy + 68 * s, u, n=10, seed=4, color=(190, 210, 235), dx=-90, desde=10.6, tam=34)
            pegar(fr, txt("MÁS FLUJO →", 54, (255, 200, 120), 6), 300, 1270, pop(u, 10.8) * vd)
    vi = ventana(u, 12.4, 18.4)
    if vi:
        card = tarjeta(620, 200, (40, 180, 230), 26).copy()
        d = ImageDraw.Draw(card)
        d.text((60, 50), "INTERCOOLER", font=fuente(64), fill=(255, 255, 255))
        d.text((60, 138), "aire de admisión más fresco", font=fuente(34, False), fill=(0, 40, 70))
        pegar(fr, card, W / 2 - 60, 520, pop(u, 12.4) * vi)
        # termómetro
        temp = int(lerp(65, 35, ease((u - 15.0) / 1.6)))
        tm = Image.new("RGBA", (160, 420), (0, 0, 0, 0))
        dt = ImageDraw.Draw(tm)
        dt.rounded_rectangle([55, 20, 105, 330], radius=25, fill=(240, 245, 250))
        dt.ellipse([30, 300, 130, 400], fill=(240, 245, 250))
        colt = mix((60, 180, 255), (255, 60, 60), (temp - 35) / 30)
        alto = lerp(320, 60, (temp - 20) / 50)
        dt.rounded_rectangle([67, alto, 93, 340], radius=13, fill=colt)
        dt.ellipse([42, 312, 118, 388], fill=colt)
        pegar(fr, tm, 960, 700, pop(u, 13.0) * vi)
        pegar(fr, txt(f"{temp}°C", 64, (255, 255, 255), 7), 800, 760, pop(u, 13.2) * vi)
        if u > 15.6:
            for i in range(4):
                pegar(fr, emoji("❄️", 60), 820 + i * 60, 640 + math.sin(u * 3 + i) * 20, pop(u, 15.6 + i * 0.1) * vi)
    # calibración: mapa de la centralita
    vc = ventana(u, 18.6, 26.8)
    if vc:
        q = clamp((u - 18.8) / 6.5)
        card = tarjeta(820, 520, (16, 22, 34), 26, borde=((80, 140, 220), 4)).copy()
        d = ImageDraw.Draw(card)
        d.text((60, 50), "CALIBRACIÓN ECU", font=fuente(48), fill=(120, 200, 255))
        for fi in range(5):
            for co in range(9):
                base = 0.25 + 0.6 * (co / 8) * (fi / 4) ** 0.6
                v = clamp(base + 0.2 * q * math.sin(co * 0.7 + fi) + 0.05 * math.sin(u * 4 + co + fi))
                col = mix((40, 90, 220), (60, 210, 120), v * 2) if v < 0.5 else mix((60, 210, 120), (240, 60, 50), v * 2 - 1)
                x0, y0 = 70 + co * 80, 130 + fi * 56
                d.rectangle([x0, y0, x0 + 74, y0 + 50], fill=col)
                d.text((x0 + 12, y0 + 10), f"{int(v * 99):02d}", font=fuente(26, False), fill=(10, 10, 20))
        d.rounded_rectangle([70, 440, 790, 480], radius=20, fill=(40, 50, 70))
        d.rounded_rectangle([70, 440, 70 + max(40, int(720 * q)), 480], radius=20, fill=(120, 255, 150))
        d.text((640, 395), f"{int(q * 100)}%", font=fuente(34), fill=(255, 255, 255))
        pegar(fr, card, W / 2, 640, pop(u, 18.6, 0.45) * vc)
        for i, lab in enumerate(("Sensores ✓", "Temperaturas ✓", "Presión turbo ✓", "Seguridad ✓")):
            s_ = pop(u, 21.9 + i * 0.9)
            if s_:
                pegar(fr, pastilla(lab, 40, (30, 160, 80)), 790, 1340 + i * 85, s_ * vc)
    if u > 27.0:
        pegar(fr, pastilla("⚡ POTENCIA".replace("⚡ ", ""), 80, ROJO), W / 2, 560, pop(u, 27.1), rot=-3)
        pegar(fr, emoji("⚡", 110), W / 2 - 300, 560, pop(u, 27.2))
        pegar(fr, txt("+", 120, (255, 255, 255), 8), W / 2, 690, pop(u, 28.0))
        pegar(fr, pastilla("FIABILIDAD", 80, (30, 160, 80)), W / 2, 820, pop(u, 28.6), rot=3)
        pegar(fr, emoji("🛡️", 110), W / 2 + 330, 820, pop(u, 28.7))
    bryan_s(fr, ctx, 160, 1810, [(0, "senala_der"), (6.2, "carpeta"), (12.4, "senala_arriba_der"), (18.6, "portatil"),
                                 (27.0, "brazos_arriba")], escala=0.62, mirar=(0.6, -0.4),
            salto=25 * abs(math.sin(u * 8)) if u > 27.1 else 0)


def esc_decision(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    bg, _ = fondo_pan("votacion", 30 * math.sin(u * 0.8))
    fr.paste(bg)
    ta, tb, tm = 6.0, 12.2, 17.9
    lado = "" if u < ta else ("A" if u < tb else ("B" if u < tm else "AB"))
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dcap = ImageDraw.Draw(capa)
    for centro, col, activo in (((300, 560), ORO, "A" in lado), ((300, 1300), AZUL, "B" in lado)):
        if activo:
            for i in range(12):
                a = u * 0.6 + i * math.pi / 6
                dcap.polygon([centro, (centro[0] + math.cos(a) * 1600, centro[1] + math.sin(a) * 1600),
                              (centro[0] + math.cos(a + 0.12) * 1600, centro[1] + math.sin(a + 0.12) * 1600)], fill=col + (28,))
    fr.paste(capa, (0, 0), capa)
    pegar(fr, txt("¡SIGUIENTE DECISIÓN!", 86, (255, 255, 255), 10, ROJO), W / 2, 140, pop(u, 0.3), rot=2 * math.sin(u * 4))
    # pregunta inicial
    vq = ventana(u, 3.4, 5.9)
    if vq:
        pegar(fr, txt("¿QUÉ LE\nHACEMOS\nAHORA?", 130, (255, 255, 255), 12, (0, 0, 0)), W / 2 - 80, 800, pop(u, 3.4) * vq,
              rot=math.sin(u * 3) * 3)
        for i in range(3):
            pegar(fr, txt("?", 110, ORO, 8), 160 + i * 330, 470 + math.sin(u * 4 + i) * 30, pop(u, 4.4 + i * 0.1) * vq,
                  rot=15 * math.sin(u * 2 + i))
    # opción A: llantas deportivas
    if u > ta:
        pa = 1.0 if "A" in lado else 0.45
        pegar(fr, txt("A", 230, ORO, 14, (0, 0, 0)), 130, 420, pop(u, ta) * (1 + 0.08 * math.sin(u * 8) * (lado == "A")), alpha=pa)
        q = int(round(((u - ta) * 220) % 36 / 3)) * 3 if lado == "A" else 0
        ll = llanta_deportiva(170, q)
        x = lerp(1300, 560, ease_out((u - ta) / 0.8))
        pegar(fr, ll, x, 590, alpha=pa)
        pegar(fr, txt("LLANTAS\nDEPORTIVAS", 66, (255, 255, 255), 8), 860, 470, pop(u, ta + 1.5), alpha=pa)
        if u > 10.8:
            pegar(fr, pastilla("+ AGRESIVO", 48, ROJO), 860, 640, pop(u, 10.8), alpha=pa, rot=-4)
            pegar(fr, emoji("😈", 80), 1010, 560, pop(u, 11.0), alpha=pa)
    # opción B: baquets
    if u > tb:
        pb = 1.0 if "B" in lado else 0.45
        pegar(fr, txt("B", 230, AZUL, 14, (0, 0, 0)), 130, 1140, pop(u, tb) * (1 + 0.08 * math.sin(u * 8) * (lado == "B")), alpha=pb)
        y = lerp(2300, 1300, ease_out((u - tb - 0.5) / 0.8)) if u > tb + 0.5 else 2300
        pegar(fr, baquet(470), 420, y, alpha=pb, rot=math.sin(u * 2) * 2)
        pegar(fr, txt("BAQUETS", 74, (255, 255, 255), 8), 790, 900, pop(u, tb + 1.0), alpha=pb)
        if u > 16.6:
            pegar(fr, pastilla("ESTILO RACING", 46, AZUL), 790, 1000, pop(u, 16.6), alpha=pb, rot=4)
            pegar(fr, emoji("🏁", 80), 980, 880, pop(u, 16.8), alpha=pb)
    if u > tm:
        s = pop(u, tm, 0.35)
        pegar(fr, txt("¡VOSOTROS\nMANDÁIS!", 92, (255, 255, 255), 10, ROJO), 390, 1600, s * (1 + 0.04 * math.sin(u * 10)), rot=-5)
    bryan_s(fr, ctx, 880, 1790, [(0, "senala_der"), (3.4, "encoge"), (4.4, "piensa"), (ta, "senala_arriba_izq"),
                                 (tb, "senala_izq"), (tm, "brazos_arriba")], escala=0.7, mirar=(-0.6, -0.3))


CIUDADES = ["SEVILLA", "VALENCIA", "BILBAO", "MÁLAGA", "ZARAGOZA", "VIGO", "MURCIA", "GRANADA", "ALICANTE", "OVIEDO"]


def esc_rubettos(fr, ctx):
    u, dur = ctx["u"], ctx["dur"]
    bg, _ = fondo2("tarde", -40 + 80 * u / dur)
    fr.paste(bg)
    # cámara: zoom a la luna trasera para la pegatina
    zin = ease((u - 5.4) / 0.8) * (1 - ease((u - 12.6) / 0.8))
    s = round(lerp(0.8, 1.3, zin) / 0.02) * 0.02
    sale = ease((u - 28.6) / 1.6) if u > 28.6 else 0
    car_x = lerp(640, 760, zin) + sale * 1400
    car_y = lerp(1430, 1470, zin)
    if sale:
        llamas(fr, car_x - s * 480, car_y + s * 67, u, 1.0)
    pegar_coche(fr, car_x, car_y, sale * 900, s=s, color=ROJO, aleron=True, llanta=(45, 45, 50))
    vent = (car_x - 62 * s, car_y - 110 * s)  # centro de la luna trasera
    puerta = (car_x - 120 * s, car_y + 5 * s)
    # notificación de rubettos
    vn = ventana(u, 1.0, 6.6, 0.4)
    if vn:
        y = lerp(-120, 300, ease_out((u - 1.0) / 0.6))
        pegar(fr, tarjeta_notificacion(), W / 2, y, 1, alpha=vn)
        if u > 4.0:
            pegar(fr, burbuja("rubettos", "¡Represento al CLUB MADRID!"), W / 2 + 40, 480, pop(u, 4.0) * vn)
    # la pegatina vuela a la luna
    if u > 7.0:
        q = ease((u - 7.0) / 0.9)
        esc = lerp(1.0, 0.36 * s / 0.8 * 0.95, q)
        x = lerp(W / 2, vent[0], q)
        yy = lerp(700, vent[1], q) - math.sin(q * math.pi) * 200
        if sale < 0.05:
            pegar(fr, pegatina("MADRID"), x, yy, esc, rot=(1 - q) * 360)
        if u > 7.9 and zin > 0.3:
            for i in range(8):
                f = (u * 1.5 + i * 0.13) % 1
                a = i * math.pi / 4
                pegar(fr, txt("✦", 46, (255, 255, 255)), vent[0] + math.cos(a) * 130 * f, vent[1] + math.sin(a) * 80 * f,
                      1 - f)
    if 9.2 < u < 12.6:
        pegar(fr, txt("MADRID YA TIENE\nSU SITIO", 92, (255, 255, 255), 10, ROJO), W / 2, 620, pop(u, 9.2))
        pegar(fr, emoji("📍", 110), vent[0], vent[1] - 150 - abs(math.sin(u * 5)) * 40, pop(u, 9.3))
    # club: si me sigues, eres del club
    vc = ventana(u, 12.8, 17.5)
    if vc:
        pegar(fr, txt("BRYAN SPORT CLUB", 86, (255, 255, 255), 10, ROJO), W / 2, 300, pop(u, 12.8) * vc)
        toca = 14.0
        boton = pastilla("✓ SIGUIENDO" if u > toca else "+ SEGUIR", 64, (70, 70, 80) if u > toca else ROJO)
        pegar(fr, boton, W / 2, 470, pop(u, 13.0) * vc * (0.9 if abs(u - toca) < 0.1 else 1))
        if 13.2 < u < toca + 0.5:
            q = ease((u - 13.2) / (toca - 13.2))
            pegar(fr, emoji("👆", 120), lerp(900, 580, q), lerp(800, 540, q))
        if u > toca:
            pegar(fr, pastilla("= YA ERES DEL CLUB", 54, ORO, (40, 20, 0)), W / 2, 610, pop(u, toca + 0.3) * vc)
            for i in range(8):
                age = u - toca - i * 0.06
                if 0 < age < 1.2:
                    a = i * math.pi / 4
                    pegar(fr, emoji("❤️", 50), W / 2 + math.cos(a) * age * 300, 470 + math.sin(a) * age * 300 - age * 80,
                          1, alpha=1 - age / 1.2)
    # comentarios con ciudades
    if 17.6 < u < 23.4:
        for i, ciudad in enumerate(CIUDADES[:8]):
            nac = 17.7 + i * 0.6
            age = u - nac
            if 0 < age < 3.0:
                yv = 1500 - age * 280
                a = min(1, age * 4, (3 - age) * 1.5, (23.4 - u) * 3)
                nombres = ["lucia_gt", "dani.rs", "iker_tdi", "sofi.motor", "marcos_06", "nerea.gti", "hugo_bs", "alba.r"]
                pegar(fr, burbuja(nombres[i], f"¡{ciudad.title()} presente!"), 600 + (i % 2) * 180, yv,
                      min(1, back(age / 0.3)), alpha=a)
        pegar(fr, txt("TU CIUDAD EN COMENTARIOS", 60, (255, 255, 255), 8), W / 2, 230, pop(u, 17.7))
        if u > 20.3:
            pegar(fr, pastilla("VOTA A", 64, ORO, (40, 20, 0)), W / 2 - 200, 360, pop(u, 20.3), rot=-4)
            pegar(fr, pastilla("o B", 64, AZUL), W / 2 + 200, 360, pop(u, 20.5), rot=4)
    # ¿quizás tu ciudad sea la siguiente?
    if 23.2 < u < 27.1:
        if u < 25.6:
            ciudad = CIUDADES[int(u * 12) % len(CIUDADES)]
            r = ranura(ciudad, 240)
        else:
            r = ranura("¿TU CIUDAD?", 240)
        pegar(fr, r, puerta[0], puerta[1], pop(u, 23.2) * (1.12 if 25.6 < u < 25.8 else 1))
        pegar(fr, txt("¿LA SIGUIENTE?", 84, ORO, 10, (60, 20, 0)), 680, 1060, pop(u, 23.5), rot=-3)
        pegar(fr, txt("↓", 90, (255, 255, 255), 8), puerta[0], 1240, pop(u, 23.7))
    # despedida
    if u > 27.1:
        pegar(fr, txt("NOS VEMOS EN EL", 70, (255, 255, 255), 8), W / 2, 300, pop(u, 27.1))
        pegar(fr, txt("PRÓXIMO\nCAPÍTULO", 130, ROJO, 12, (255, 255, 255)), W / 2, 480, pop(u, 27.4), rot=-3)
        for x, sg in ((130, 1), (950, -1)):
            pegar(fr, emoji("🏁", 150), x, 760, pop(u, 27.6), rot=sg * 15 * math.sin(u * 9))
    bryan_s(fr, ctx, 200, 1730, [(0, "saluda"), (1.0, "movil"), (5.4, "senala_der"), (9.2, "pulgar"), (12.8, "senala_arriba_der"),
                                 (17.6, "brazos_arriba"), (20.2, "senala_arriba_der"), (23.2, "senala_der"), (27.1, "saluda")],
            escala=0.78, mirar=(0.6, -0.2), salto=30 * abs(math.sin(u * 8)) if 17.6 < u < 18.8 else 0)
    if u > dur - 0.9:
        q = clamp((u - (dur - 0.9)) / 0.6)
        capa = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * q)))
        fr.paste(capa, (0, 0), capa)
        pegar(fr, txt("BRYAN SPORT", 110, ROJO, 8, (255, 255, 255)), W / 2, H / 2 - 40, q)
        pegar(fr, txt("DÍA 3 · MUY PRONTO", 54, (255, 255, 255)), W / 2, H / 2 + 80, q)


A.ESCENAS.update({"portada": esc_portada, "gancho": esc_gancho, "garaje": esc_garaje, "stage2": esc_stage2,
                  "decision": esc_decision, "rubettos": esc_rubettos})
A.SFX_SEG.update({
    "portada": [(0.15, "whoosh"), (0.6, "sello"), (1.4, "pop")],
    "gancho": [(0.2, "pop"), (2.7, "sello"), (2.75, "aplauso"), (3.8, "pop"), (5.0, "brrum"), (7.6, "pop"), (9.3, "ding")],
    "garaje": [(0.3, "pop"), (2.7, "pop"), (2.9, "pop"), (3.1, "pop"), (5.6, "pop"), (6.6, "sello"), (8.3, "ding"),
               (10.6, "pop"), (12.5, "pop"), (13.1, "pop"), (13.7, "pop"), (15.3, "pop"), (17.6, "whoosh")],
    "stage2": [(4.6, "sello"), (6.2, "pop"), (10.6, "motor"), (12.4, "pop"), (15.0, "ding"), (18.6, "pop"),
               (21.9, "pop"), (22.8, "pop"), (23.7, "pop"), (24.6, "pop"), (27.1, "sello"), (28.6, "sello")],
    "decision": [(0.3, "pop"), (3.4, "pop"), (6.0, "whoosh"), (6.0, "pop"), (10.8, "pop"), (12.2, "whoosh"), (12.2, "pop"),
                 (16.6, "pop"), (17.9, "sello"), (18.0, "aplauso")],
    "rubettos": [(1.0, "ding"), (4.0, "pop"), (7.0, "whoosh"), (7.9, "sello"), (9.2, "pop"), (13.0, "pop"), (14.0, "ding"),
                 (17.7, "pop"), (20.3, "pop"), (20.5, "pop"), (23.2, "pop"), (25.6, "ding"), (27.1, "pop"), (28.6, "motor")],
})

if __name__ == "__main__":
    fondos2()
    A.main()
