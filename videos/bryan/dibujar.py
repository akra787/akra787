"""Dibuja las ilustraciones del vídeo de Bryan (coche antes/después, taller, opciones A/B)."""
import random
from PIL import Image, ImageDraw, ImageFilter
import os
W, H = 1080, 1920
D = os.path.dirname(os.path.abspath(__file__))

def fondo(c1, c2):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    return im

def suelo(d, y=1420, color=(25, 25, 30)):
    d.rectangle([0, y, W, H], fill=color)
    for x in range(-200, W + 200, 140):
        d.line([(x, y), (x - 300, H)], fill=(45, 45, 52), width=3)

def coche(im, cx, cy, s, cuerpo, oxido=False, alerón=False, llantas=(180, 180, 190), brillo=True, ruedas_r=1.0):
    d = ImageDraw.Draw(im)
    P = lambda pts: [(cx + x * s, cy + y * s) for x, y in pts]
    # sombra
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).ellipse([cx - 470 * s, cy + 110 * s, cx + 470 * s, cy + 170 * s], fill=170)
    sh = sh.filter(ImageFilter.GaussianBlur(25))
    im.paste((0, 0, 0), mask=sh)
    d = ImageDraw.Draw(im)
    body = [(-460, 90), (-470, 10), (-430, -30), (-250, -60), (-140, -170), (150, -175), (290, -70),
            (440, -45), (470, 10), (465, 90)]
    d.polygon(P(body), fill=cuerpo)
    osc = tuple(max(0, c - 50) for c in cuerpo)
    d.polygon(P([(-460, 60), (465, 60), (465, 90), (-460, 90)]), fill=osc)
    d.polygon(P([(-120, -150), (0, -155), (0, -70), (-215, -65)]), fill=(40, 55, 75))
    d.polygon(P([(20, -155), (140, -155), (250, -72), (20, -70)]), fill=(40, 55, 75))
    if brillo:
        d.polygon(P([(-100, -145), (-60, -147), (-160, -70), (-190, -68)]), fill=(120, 140, 170))
        d.line(P([(-400, -20), (420, -30)]), fill=tuple(min(255, c + 60) for c in cuerpo), width=int(6 * s))
    d.line(P([(5, -150), (5, 80)]), fill=osc, width=int(5 * s))
    d.ellipse(P([(420, -30), (465, 0)]), fill=(255, 240, 180))
    d.rectangle(P([(-470, -15), (-445, 15)]), fill=(200, 20, 20))
    if alerón:
        d.polygon(P([(-430, -55), (-470, -95), (-330, -100), (-300, -60)]), fill=osc)
    if oxido:
        rnd = random.Random(3)
        for _ in range(60):
            x, y = rnd.uniform(-430, 430), rnd.uniform(-40, 80)
            r = rnd.uniform(5, 22)
            d.ellipse(P([(x - r, y - r * .7), (x + r, y + r * .7)]), fill=(rnd.randint(110, 150), rnd.randint(55, 75), 30))
        d.line(P([(150, -20), (230, 40), (270, 20)]), fill=(30, 30, 30), width=int(4 * s))
    for wx in (-280, 290):
        R = 92 * ruedas_r
        d.ellipse(P([(wx - R - 10, 90 - R - 10), (wx + R + 10, 90 + R + 10)]), fill=(15, 15, 15))
        d.ellipse(P([(wx - R, 90 - R), (wx + R, 90 + R)]), fill=(20, 20, 22))
        r2 = R * .62
        d.ellipse(P([(wx - r2, 90 - r2), (wx + r2, 90 + r2)]), fill=llantas)
        import math
        for k in range(5):
            a = k * 2 * math.pi / 5
            d.line(P([(wx, 90), (wx + math.cos(a) * r2, 90 + math.sin(a) * r2)]), fill=tuple(c - 60 for c in llantas), width=int(10 * s))
        d.ellipse(P([(wx - 14, 76), (wx + 14, 104)]), fill=(60, 60, 60))

def chispas(im, n, zona, color=(255, 200, 60), seed=1):
    d = ImageDraw.Draw(im); rnd = random.Random(seed)
    x0, y0, x1, y1 = zona
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        l = rnd.uniform(10, 40)
        d.line([(x, y), (x + l, y - l * .5)], fill=color, width=3)

def guardar(im, nombre):
    im.save(os.path.join(D, nombre), quality=92)

# 1. Coche destrozado (gancho / compra)
im = fondo((40, 40, 50), (90, 70, 60)); d = ImageDraw.Draw(im); suelo(d)
coche(im, 540, 1290, 1.05, (120, 125, 120), oxido=True, brillo=False)
guardar(im, "antes.jpg")
# 2. Taller (mecánica)
im = fondo((15, 20, 35), (30, 45, 70)); d = ImageDraw.Draw(im); suelo(d, color=(35, 35, 40))
d.rectangle([60, 1420, 1020, 1450], fill=(230, 180, 0))
for i in range(0, 960, 80):
    d.polygon([(60 + i, 1420), (100 + i, 1420), (70 + i, 1450), (30 + i, 1450)], fill=(20, 20, 20))
coche(im, 540, 1250, 1.05, (120, 125, 120), oxido=False, brillo=False)
chispas(im, 80, (300, 1100, 800, 1350))
guardar(im, "taller.jpg")
# 3. Pintura nueva
im = fondo((10, 10, 25), (60, 10, 30)); d = ImageDraw.Draw(im); suelo(d)
coche(im, 540, 1290, 1.05, (200, 20, 35), llantas=(200, 200, 210))
chispas(im, 50, (100, 900, 1000, 1400), color=(255, 255, 255), seed=7)
guardar(im, "despues.jpg")
# 4. Repro / banco de potencia
im = fondo((5, 5, 15), (10, 30, 60)); d = ImageDraw.Draw(im); suelo(d, color=(15, 15, 25))
for i in range(12):
    d.line([(0, 1350 + i * 8), (W, 1350 + i * 8)], fill=(0, 160 + i * 7, 255), width=2)
coche(im, 540, 1270, 1.05, (200, 20, 35), alerón=True, llantas=(40, 40, 45))
chispas(im, 70, (0, 1180, 120, 1330), color=(255, 120, 30), seed=4)
guardar(im, "repro.jpg")
# 5. Opción A (estética) / B (potencia): pantalla dividida
a = fondo((30, 30, 30), (5, 5, 5)); coche(a, 540, 1300, 1.05, (35, 35, 38), llantas=(200, 160, 40), ruedas_r=1.12)
b = fondo((0, 30, 70), (0, 5, 20)); coche(b, 540, 1300, 1.05, (200, 20, 35), alerón=True, llantas=(40, 40, 45))
chispas(b, 90, (0, 1150, 160, 1350), color=(255, 120, 30), seed=9)
im = Image.new("RGB", (W, H))
im.paste(a.crop((0, 0, W, H)).resize((W, H // 2)).crop((0, 0, W, H // 2)), (0, 0))
im.paste(b.resize((W, H // 2)), (0, H // 2))
im = Image.new("RGB", (W, H)); 
top = a.crop((0, 760, W, 1720)); bot = b.crop((0, 760, W, 1720))
im.paste(top, (0, 0)); im.paste(bot, (0, 960))
d = ImageDraw.Draw(im); d.rectangle([0, 952, W, 968], fill=(255, 210, 0))
guardar(im, "opciones.jpg")
# 6. Club de fans
im = fondo((60, 0, 0), (10, 0, 0)); d = ImageDraw.Draw(im)
for r in range(900, 100, -60):
    d.ellipse([540 - r, 1300 - r // 3, 540 + r, 1300 + r // 3], outline=(140, 20, 20), width=3)
coche(im, 540, 1320, 1.0, (200, 20, 35), alerón=True, llantas=(200, 200, 210))
chispas(im, 120, (0, 700, 1080, 1700), color=(255, 215, 0), seed=11)
guardar(im, "club.jpg")
print("ok")
