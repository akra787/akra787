"""El Piloto: mascota de la serie "Proyecto Nürburgring".

Personaje de dibujos dibujado con Pillow: casco integral con la visera levantada, mono de carreras verde,
cejas expresivas y boca sincronizada con la voz. Poses: "point", "wheel", "thumbs".
"""
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

K = 3                      # supersampling
CW, CH = 700, 1000         # lienzo del personaje (px finales)
INK = (14, 18, 16)
SUIT = (0, 196, 108)
SUIT_D = (0, 140, 78)
WHITE = (244, 246, 248)
SKIN = (244, 192, 150)
SKIN_D = (214, 150, 112)
GLOVE = (28, 30, 34)
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"


def _s(*v):
    return [x * K for x in v]


def _arm(d, pts, ow=78, fw=60):
    P = [(x * K, y * K) for x, y in pts]
    d.line(P, fill=INK, width=ow * K, joint="curve")
    for p in (P[0], P[-1]) + tuple(P[1:-1]):
        r = ow * K / 2
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=INK)
    d.line(P, fill=SUIT, width=fw * K, joint="curve")
    for p in P[:-1]:
        r = fw * K / 2
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=SUIT)
    # costura brillante
    d.line(P, fill=(90, 236, 160), width=8 * K, joint="curve")


def _glove(d, x, y, kind, ang=0.0):
    """kind: fist | point | thumb | grip"""
    R = 44
    c = math.cos(ang)
    s = math.sin(ang)
    if kind == "point":
        # dedo índice hacia (ang)
        fx, fy = x + c * 70, y + s * 70
        d.line(_s(x, y, fx, fy), fill=INK, width=36 * K)
        d.ellipse(_s(fx - 18, fy - 18, fx + 18, fy + 18), fill=INK)
        d.line(_s(x, y, fx, fy), fill=GLOVE, width=22 * K)
        d.ellipse(_s(fx - 11, fy - 11, fx + 11, fy + 11), fill=GLOVE)
    if kind == "thumb":
        p0, p1 = (x - 14, y - 20), (x - 30, y - 86)
        for wdt, col in ((44, INK), (30, GLOVE)):
            d.line(_s(*p0, *p1), fill=col, width=wdt * K)
            for px, py in (p0, p1):
                r = wdt / 2
                d.ellipse(_s(px - r, py - r, px + r, py + r), fill=col)
    d.ellipse(_s(x - R - 7, y - R - 7, x + R + 7, y + R + 7), fill=INK)
    d.ellipse(_s(x - R, y - R, x + R, y + R), fill=GLOVE)
    # nudillos y brillo
    for i in range(3):
        kx = x - 22 + i * 22
        d.arc(_s(kx - 12, y - 30, kx + 12, y - 6), 200, 340, fill=(70, 74, 80), width=3 * K)
    d.ellipse(_s(x - 26, y - 34, x - 6, y - 20), fill=(90, 96, 104))
    if kind == "thumb":
        for i in range(3):
            d.line(_s(x + 6, y - 14 + i * 18, x + 40, y - 14 + i * 18), fill=(70, 74, 80), width=4 * K)
    # puño blanco
    d.arc(_s(x - R - 4, y - R - 4, x + R + 4, y + R + 4), 0, 0, fill=WHITE)


def _torso(d):
    # cuerpo (sale por abajo)
    d.rounded_rectangle(_s(150, 560, 550, 1150), 150 * K, fill=INK)
    d.rounded_rectangle(_s(160, 570, 540, 1150), 140 * K, fill=SUIT)
    # paneles laterales oscuros
    d.rounded_rectangle(_s(160, 700, 215, 1150), 30 * K, fill=SUIT_D)
    d.rounded_rectangle(_s(485, 700, 540, 1150), 30 * K, fill=SUIT_D)
    # franjas blancas de carreras
    for x in (250, 450):
        d.line(_s(x, 590, x, 1000), fill=WHITE, width=14 * K)
    # cremallera
    d.line(_s(350, 640, 350, 1000), fill=INK, width=6 * K)
    for y in range(650, 1000, 22):
        d.line(_s(342, y, 358, y), fill=(60, 66, 64), width=3 * K)
    # parche "30" en el pecho
    d.rounded_rectangle(_s(380, 690, 470, 760), 14 * K, fill=WHITE, outline=INK, width=4 * K)
    f = ImageFont.truetype(FONT, 50 * K)
    d.text((425 * K, 726 * K), "30", font=f, fill=SUIT_D, anchor="mm")
    # parche bandera a cuadros
    d.rounded_rectangle(_s(230, 690, 320, 760), 12 * K, fill=WHITE, outline=INK, width=4 * K)
    for r in range(3):
        for c in range(4):
            if (r + c) % 2:
                d.rectangle(_s(238 + c * 19, 698 + r * 19, 238 + c * 19 + 18, 698 + r * 19 + 18), fill=INK)
    # cuello
    d.rounded_rectangle(_s(255, 540, 445, 610), 30 * K, fill=INK)
    d.rounded_rectangle(_s(265, 548, 435, 600), 24 * K, fill=(36, 40, 40))


def _head(d, mouth, blink, wink, brow):
    cx, cy, R = 350, 330, 215
    # sombra del casco
    d.ellipse(_s(cx - R - 9, cy - R - 9, cx + R + 9, cy + R + 9), fill=INK)
    d.ellipse(_s(cx - R, cy - R, cx + R, cy + R), fill=(196, 204, 212))
    d.ellipse(_s(cx - R + 10, cy - R + 4, cx + R - 30, cy + R - 40), fill=WHITE)
    # franja verde central con filetes
    d.chord(_s(cx - R, cy - R, cx + R, cy + R), 250, 290, fill=SUIT)
    d.line(_s(cx - 74, cy - 200, cx - 60, cy - 120), fill=INK, width=4 * K)
    d.line(_s(cx + 74, cy - 200, cx + 60, cy - 120), fill=INK, width=4 * K)
    # brillo
    d.ellipse(_s(cx - 150, cy - 175, cx - 80, cy - 120), fill=(255, 255, 255))
    # abertura de la cara
    ox0, oy0, ox1, oy1 = cx - 150, cy - 95, cx + 150, cy + 70
    d.rounded_rectangle(_s(ox0 - 8, oy0 - 8, ox1 + 8, oy1 + 8), 66 * K, fill=INK)
    d.rounded_rectangle(_s(ox0, oy0, ox1, oy1), 60 * K, fill=SKIN)
    d.rounded_rectangle(_s(ox0, oy1 - 40, ox1, oy1), 30 * K, fill=SKIN_D)
    d.rounded_rectangle(_s(ox0, oy0, ox1, oy1 - 24), 60 * K, fill=SKIN)
    # visera levantada (ahumada)
    d.rounded_rectangle(_s(cx - 172, cy - 150, cx + 172, cy - 86), 34 * K, fill=INK)
    d.rounded_rectangle(_s(cx - 164, cy - 143, cx + 164, cy - 93), 28 * K, fill=(36, 52, 66))
    d.rounded_rectangle(_s(cx - 140, cy - 136, cx + 40, cy - 124), 6 * K, fill=(110, 140, 160))
    for sx in (cx - 180, cx + 180):
        d.ellipse(_s(sx - 16, cy - 134, sx + 16, cy - 102), fill=INK)
        d.ellipse(_s(sx - 9, cy - 127, sx + 9, cy - 109), fill=(150, 156, 162))
    # ojos
    ey = cy - 20
    for i, ex in enumerate((cx - 62, cx + 62)):
        closed = blink or (wink and i == 1)
        if closed:
            d.arc(_s(ex - 30, ey - 18, ex + 30, ey + 26), 200, 340, fill=INK, width=8 * K)
        else:
            d.ellipse(_s(ex - 33, ey - 39, ex + 33, ey + 39), fill=INK)
            d.ellipse(_s(ex - 27, ey - 33, ex + 27, ey + 33), fill=WHITE)
            d.ellipse(_s(ex - 15 + 4, ey - 15 + 4, ex + 15 + 4, ey + 17 + 4), fill=(40, 96, 70))
            d.ellipse(_s(ex - 9 + 4, ey - 9 + 4, ex + 9 + 4, ey + 11 + 4), fill=INK)
            d.ellipse(_s(ex - 6, ey - 8, ex + 4, ey + 2), fill=WHITE)
    # cejas (una levantada: carisma)
    lb = -14 * brow
    d.line(_s(cx - 98, ey - 52 + lb, cx - 60, ey - 66 + lb, cx - 28, ey - 56 + lb), fill=INK, width=15 * K,
           joint="curve")
    d.line(_s(cx + 28, ey - 52, cx + 64, ey - 58, cx + 98, ey - 48), fill=INK, width=15 * K, joint="curve")
    # coloretes y nariz
    for bx in (cx - 105, cx + 105):
        d.ellipse(_s(bx - 22, ey + 34, bx + 22, ey + 52), fill=(246, 150, 140))
    d.arc(_s(cx - 12, ey + 18, cx + 12, ey + 40), 20, 160, fill=SKIN_D, width=5 * K)
    # boca
    my = cy + 40
    if mouth < 0.15:
        # sonrisa ladeada
        d.arc(_s(cx - 60, my - 44, cx + 66, my + 6), 15, 160, fill=INK, width=9 * K)
        d.line(_s(cx + 56, my - 22, cx + 70, my - 30), fill=INK, width=7 * K)
    else:
        h = 14 + 30 * mouth
        d.chord(_s(cx - 54, my - 28, cx + 54, my - 28 + h * 2), 0, 180, fill=INK)
        d.chord(_s(cx - 46, my - 24, cx + 46, my - 24 + (h * 2 - 10)), 0, 180, fill=(120, 30, 40))
        d.chord(_s(cx - 44, my - 24 + h - 12, cx + 44, my - 24 + h + 12), 0, 180, fill=WHITE)
        if mouth > 0.5:
            d.ellipse(_s(cx - 24, my - 30 + h * 1.5, cx + 24, my - 30 + h * 2), fill=(230, 100, 110))
    # barbilla del casco: rejillas
    for i in (-1, 0, 1):
        d.rounded_rectangle(_s(cx + i * 40 - 12, cy + 120, cx + i * 40 + 12, cy + 160), 8 * K, fill=(60, 66, 72))


POSES = {
    # brazos (pantalla): lista de (puntos del brazo, guante, ángulo)
    "point": [([(200, 640), (100, 560), (90, 400)], "fist", 0),
              ([(500, 640), (600, 560), (610, 400)], "fist", 0)],
    "wheel": [([(200, 640), (180, 760), (250, 790)], "grip", 0),
              ([(500, 640), (520, 760), (450, 790)], "grip", 0)],
    "thumbs": [([(200, 640), (140, 790), (200, 900)], "fist", 0),
               ([(500, 640), (640, 600), (620, 440)], "thumb", 0)],
}


@lru_cache(maxsize=64)
def character(pose, mouth_q=0, blink=False, wheel_ang_q=0):
    im = Image.new("RGBA", (CW * K, CH * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    _torso(d)
    wink = pose == "thumbs"
    brow = 1.0 if pose in ("point", "thumbs") else 0.4
    arms = POSES[pose]
    behind = [a for a in arms if a[1] == "fist" and pose == "thumbs"]
    for pts, g, ang in behind:
        _arm(d, pts)
        _glove(d, pts[-1][0], pts[-1][1], g, ang)
    _head(d, mouth_q / 4, blink, wink, brow)
    if pose == "wheel":
        a = wheel_ang_q * 3 * math.pi / 180
        wx, wy, r = 350, 800, 135
        d.ellipse(_s(wx - r - 8, wy - r - 8, wx + r + 8, wy + r + 8), fill=INK)
        d.ellipse(_s(wx - r, wy - r, wx + r, wy + r), fill=(48, 52, 58))
        d.ellipse(_s(wx - r + 26, wy - r + 26, wx + r - 26, wy + r - 26), fill=INK)
        d.ellipse(_s(wx - r + 32, wy - r + 32, wx + r - 32, wy + r - 32), fill=(0, 0, 0, 0))
        for k in (0, 2 * math.pi / 3, 4 * math.pi / 3):
            aa = a + k + math.pi / 2
            d.line(_s(wx, wy, wx + math.cos(aa) * (r - 20), wy + math.sin(aa) * (r - 20)), fill=(48, 52, 58), width=26 * K)
        d.ellipse(_s(wx - 34, wy - 34, wx + 34, wy + 34), fill=INK)
        d.ellipse(_s(wx - 26, wy - 26, wx + 26, wy + 26), fill=SUIT)
        tx, ty = wx + math.cos(a - math.pi / 2) * (r - 12), wy + math.sin(a - math.pi / 2) * (r - 12)
        d.ellipse(_s(tx - 10, ty - 10, tx + 10, ty + 10), fill=(255, 204, 40))
    for pts, g, ang in arms:
        if (pts, g, ang) in behind:
            continue
        if pose == "wheel":
            a = wheel_ang_q * 3 * math.pi / 180
            hx, hy = pts[-1]
            dx, dy = hx - 350, hy - 800
            hx, hy = 350 + dx * math.cos(a) - dy * math.sin(a), 800 + dx * math.sin(a) + dy * math.cos(a)
            pts = pts[:-1] + [(hx, hy)]
        _arm(d, pts)
        _glove(d, pts[-1][0], pts[-1][1], "fist" if g == "grip" else g, ang)
    out = im.resize((CW, CH), Image.LANCZOS)
    # contorno de luz verde para separarlo del fondo
    a = out.getchannel("A").filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10))
    rim = Image.new("RGBA", out.size, (0, 255, 136, 0))
    rim.putalpha(a.point(lambda v: int(v * 0.55)))
    rim.alpha_composite(out)
    return rim
