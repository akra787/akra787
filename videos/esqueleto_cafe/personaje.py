"""Dibujo procedural del personaje: esqueleto color marfil dentro de un cuerpo de cristal.

Todo se dibuja en local con Pillow + numpy. Las coordenadas son las del lienzo final (1x);
los huesos se dibujan al doble de resolución y se reducen para suavizar los bordes.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

IVORY = (236, 226, 202)
BONE_DARK = (132, 114, 90)
BONE_LIGHT = (252, 247, 232)
CART = (226, 222, 210)


# ------------------------------------------------------------------ geometría
def V(x, y=None):
    if y is None:
        return np.array(x, float)
    return np.array([x, y], float)


def unit(v):
    n = np.hypot(v[0], v[1])
    return v / n if n > 1e-9 else np.array([1.0, 0.0])


def perp(u):
    return np.array([-u[1], u[0]])


def ang_vec(deg):
    a = math.radians(deg)
    return np.array([math.cos(a), math.sin(a)])


def rotv(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def seg(t, a, b):
    return ease((t - a) / (b - a))


def lerp(a, b, t):
    return a + (b - a) * t


def noise(t, seed=0.0, speed=1.0):
    """Ruido suave determinista en [-1, 1]."""
    t = t * speed
    return (math.sin(t * 2.31 + seed * 1.7) * 0.5 + math.sin(t * 3.97 + seed * 3.1) * 0.3
            + math.sin(t * 7.13 + seed * 5.3) * 0.2)


def catmull(pts, n=10):
    pts = [np.array(p, float) for p in pts]
    pts = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(n):
            t = j / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-2])
    return out


def bezier(a, c, b, t):
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t * t * b


# ------------------------------------------------------------------ lápiz
class Pen:
    """Dibuja con coordenadas del lienzo 1x sobre una imagen con escala s y origen off."""

    def __init__(self, img, s=1.0, off=(0, 0)):
        self.img = img
        self.d = ImageDraw.Draw(img, "RGBA" if img.mode == "RGBA" else None)
        self.s = s
        self.ox, self.oy = off

    def P(self, p):
        return ((p[0] - self.ox) * self.s, (p[1] - self.oy) * self.s)

    def W(self, w):
        return max(1, int(round(w * self.s)))

    def line(self, pts, fill, width):
        self.d.line([self.P(p) for p in pts], fill=fill, width=self.W(width), joint="curve")

    def poly(self, pts, fill, outline=None, width=1):
        self.d.polygon([self.P(p) for p in pts], fill=fill, outline=outline,
                       width=self.W(width) if outline else 0)

    def circle(self, c, r, fill=None, outline=None, width=1):
        x, y = self.P(c)
        r = r * self.s
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline,
                       width=self.W(width) if outline else 0)

    def ellipse(self, c, rx, ry, fill=None, ang=0.0, outline=None, width=1, n=56):
        pts = [np.array(c) + rotv(np.array([rx * math.cos(2 * math.pi * i / n), ry * math.sin(2 * math.pi * i / n)]), ang)
               for i in range(n)]
        if fill is not None:
            self.poly(pts, fill)
        if outline is not None:
            self.line(pts + [pts[0]], outline, width)

    def rect(self, x0, y0, x1, y1, fill=None, r=0, outline=None, width=1):
        box = [self.P((x0, y0)), self.P((x1, y1))]
        self.d.rounded_rectangle(box, radius=r * self.s, fill=fill, outline=outline,
                                 width=self.W(width) if outline else 0)

    def capsule(self, a, b, w, fill):
        self.line([a, b], fill, w)
        self.circle(a, w / 2, fill)
        self.circle(b, w / 2, fill)

    def text(self, xy, txt, font, fill):
        self.d.text(self.P(xy), txt, font=font, fill=fill)


# ------------------------------------------------------------------ huesos
def bone(pen, a, b, w, r1=None, r2=None, col=IVORY, o=2.0, hl=True):
    a, b = np.array(a, float), np.array(b, float)
    r1 = w * 0.75 if r1 is None else r1
    r2 = w * 0.75 if r2 is None else r2
    pen.capsule(a, b, w + 2 * o, BONE_DARK)
    pen.circle(a, r1 + o, BONE_DARK)
    pen.circle(b, r2 + o, BONE_DARK)
    pen.capsule(a, b, w, col)
    pen.circle(a, r1, col)
    pen.circle(b, r2, col)
    if hl and w > 5:
        u = unit(b - a)
        n = perp(u)
        L = np.hypot(*(b - a))
        if L > r1 + r2:
            pen.line([a + n * w * 0.2 + u * r1 * 0.7, b + n * w * 0.2 - u * r2 * 0.7], BONE_LIGHT, max(1.0, w * 0.22))


def curve_bone(pen, pts, w, col=IVORY, o=2.0, hl=True):
    pen.line(pts, BONE_DARK, w + 2 * o)
    pen.circle(pts[0], (w + 2 * o) / 2, BONE_DARK)
    pen.circle(pts[-1], (w + 2 * o) / 2, BONE_DARK)
    pen.line(pts, col, w)
    pen.circle(pts[0], w / 2, col)
    pen.circle(pts[-1], w / 2, col)
    if hl:
        pen.line([p + V(0, -w * 0.22) for p in pts[1:-1]], BONE_LIGHT, max(1.0, w * 0.25))


# ------------------------------------------------------------------ cráneo
def _shade_sprite(img, light=(-0.45, -0.6, 0.66), blur=10.0, amb=0.5, dif=0.62):
    """Sombreado pseudo-3D a partir del canal alfa (normales del alfa difuminado)."""
    a = np.asarray(img.getchannel("A"), float) / 255
    hgt = np.asarray(img.getchannel("A").filter(ImageFilter.GaussianBlur(blur)), float) / 255
    gy, gx = np.gradient(hgt)
    k = blur * 1.6
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(hgt)
    nn = np.sqrt(nx * nx + ny * ny + nz * nz)
    lx, ly, lz = light
    lam = np.clip((nx * lx + ny * ly + nz * lz) / nn, 0, 1)
    shade = amb + dif * lam
    rgb = np.asarray(img.convert("RGB"), float) * shade[..., None]
    out = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def make_skull(k=1.0):
    """Devuelve (sprite RGBA a 2x, origen en píxeles del sprite). Unidades locales = px 1x."""
    S = 4.0 * k
    x0, y0, wl, hl = -115, -135, 230, 290
    size = (int(wl * S), int(hl * S))
    base = Image.new("RGBA", size, IVORY + (0,))
    pen = Pen(base, s=S, off=(x0, y0))
    col = IVORY + (255,)
    pen.ellipse((0, -20), 74, 84, fill=col)
    pen.poly([(-72, -10), (72, -10), (68, 28), (52, 54), (-52, 54), (-68, 28)], col)
    pen.poly([(-46, 30), (46, 30), (42, 76), (-42, 76)], col)
    pen.poly([(-60, 34), (-54, 62), (-44, 78), (44, 78), (54, 62), (60, 34), (60, 70), (56, 92), (40, 112),
              (18, 122), (-18, 122), (-40, 112), (-56, 92), (-60, 70)], col)
    img = _shade_sprite(base, blur=12 * S / 4)
    pen = Pen(img, s=S, off=(x0, y0))
    # sienes y pómulos
    for s in (-1, 1):
        pen.ellipse((s * 64, 6), 12, 28, fill=(110, 90, 70, 55))
        pen.line(catmull([(s * 46, 42), (s * 60, 30), (s * 70, 16)], 6), (120, 100, 78, 120), 2.2)
        pen.line(catmull([(s * 44, 80), (s * 54, 64), (s * 60, 46)], 6), (120, 100, 78, 90), 1.6)
    # cejas (arcos superciliares)
    for s in (-1, 1):
        pts = [(s * 31 + 30 * math.cos(math.radians(a)), 10 + 29 * math.sin(math.radians(a))) for a in range(200, 341, 10)]
        pen.line(pts, BONE_LIGHT + (230,), 3.2)
    # órbitas
    for s in (-1, 1):
        c = (s * 31, 10)
        pen.circle(c, 27.5, fill=(96, 78, 60, 255))
        pen.circle(c, 25.5, fill=(34, 26, 22, 255))
    # nariz
    pen.poly([(0, 31), (-12, 47), (-10, 59), (-3, 57), (0, 53), (3, 57), (10, 59), (12, 47)], (40, 31, 26, 255))
    pen.line([(0, 40), (0, 56)], (150, 132, 108, 255), 1.6)
    # encías y dientes
    pen.poly([(-38, 66), (38, 66), (36, 73), (-36, 73)], (210, 196, 168, 255))
    pen.rect(-36, 80, 36, 84, fill=(40, 30, 25, 255), r=1.5)
    n = 10
    for row, (ya, yb) in enumerate(((70, 82.5), (82.5, 94))):
        for i in range(n):
            xa = -33 + i * 6.6
            dy = abs(i - (n - 1) / 2) * 0.55
            if row == 0:
                pen.rect(xa + 0.4, ya + dy, xa + 6.2, yb, fill=(248, 244, 230, 255), r=1.6,
                         outline=(150, 134, 110, 255), width=0.7)
            else:
                pen.rect(xa + 0.4, ya, xa + 6.2, yb - dy, fill=(244, 239, 224, 255), r=1.6,
                         outline=(150, 134, 110, 255), width=0.7)
    # línea de la mandíbula
    pen.line(catmull([(-56, 92), (-40, 112), (0, 122), (40, 112), (56, 92)], 8), (150, 130, 104, 160), 1.4)
    # globos oculares (esferas blancas con sombreado)
    eye = Image.new("RGBA", size, (240, 240, 236, 0))
    ep = Pen(eye, s=S, off=(x0, y0))
    for s in (-1, 1):
        ep.circle((s * 31, 10), 19.5, fill=(244, 243, 238, 255))
    eye = _shade_sprite(eye, light=(-0.4, -0.55, 0.73), blur=6 * S / 4, amb=0.42, dif=0.68)
    img.alpha_composite(eye)
    pen = Pen(img, s=S, off=(x0, y0))
    for s in (-1, 1):
        pen.circle((s * 31 - 8, 1), 4.0, fill=(255, 255, 255, 170))
    small = img.resize((int(wl * 2 * k), int(hl * 2 * k)), Image.LANCZOS)
    origin = (-x0 * 2 * k, -y0 * 2 * k)
    return small, origin


# ------------------------------------------------------------------ taza
def make_mug(w=90, fill=0.8, color=(238, 236, 230), stain=False):
    """Taza vista de lado. Devuelve (sprite 2x, ancla del centro del cuerpo en px del sprite)."""
    S = 4.0
    h = w * 0.88
    ox, oy = -w * 0.12, -h * 0.2
    Wd, Hd = int(w * 1.55 * S), int(h * 1.35 * S)
    img = Image.new("RGBA", (Wd, Hd), color + (0,))
    pen = Pen(img, s=S, off=(ox, oy))
    hc = tuple(int(c * 0.86) for c in color) + (255,)
    pen.ellipse((w * 1.0, h * 0.5), w * 0.25, h * 0.27, outline=hc, width=w * 0.1)
    pen.rect(0, h * 0.06, w, h, fill=color + (255,), r=w * 0.13)
    arr = np.asarray(img, float).copy()
    xs = (np.arange(Wd) / S + ox) / w
    f = 0.70 + 0.30 * np.sin(np.clip(xs, 0, 1) * math.pi) + 0.16 * np.exp(-((xs - 0.3) / 0.08) ** 2)
    arr[..., :3] = np.clip(arr[..., :3] * f[None, :, None], 0, 255)
    img = Image.fromarray(arr.astype(np.uint8), "RGBA")
    pen = Pen(img, s=S, off=(ox, oy))
    pen.ellipse((w / 2, h * 0.07), w / 2, h * 0.085, fill=tuple(min(255, c + 10) for c in color) + (255,))
    if fill > 0.05:
        pen.ellipse((w / 2, h * 0.08), w * 0.44, h * 0.062, fill=(58, 34, 20, 255))
        pen.ellipse((w * 0.53, h * 0.083), w * 0.3, h * 0.04, fill=(112, 72, 44, 255))
    else:
        pen.ellipse((w / 2, h * 0.08), w * 0.44, h * 0.062, fill=tuple(int(c * 0.72) for c in color) + (255,))
        if stain:
            pen.ellipse((w / 2, h * 0.09), w * 0.3, h * 0.035, fill=(120, 80, 50, 200))
    if stain:
        pen.line([(w * 0.62, h * 0.06), (w * 0.64, h * 0.2), (w * 0.6, h * 0.32)], (130, 85, 50, 150), w * 0.03)
    small = img.resize((int(Wd / 2), int(Hd / 2)), Image.LANCZOS)
    anchor = ((w / 2 - ox) * 2, (h / 2 - oy) * 2)
    return small, anchor


def paste_sprite(layer, sprite, anchor, pos, scale, angle=0.0, off=(0, 0)):
    """Pega un sprite (dibujado a 2x) en una capa con escala `scale` (1 = capa 1x, 2 = capa 2x)."""
    sp, an = sprite, anchor
    if scale != 2:
        f = scale / 2
        sp = sp.resize((max(1, int(sp.width * f)), max(1, int(sp.height * f))), Image.LANCZOS)
        an = (an[0] * f, an[1] * f)
    if abs(angle) > 0.01:
        sp = sp.rotate(-angle, resample=Image.BICUBIC, center=an, expand=False)
    x = int(round((pos[0] - off[0]) * scale - an[0]))
    y = int(round((pos[1] - off[1]) * scale - an[1]))
    tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    tmp.paste(sp, (x, y))
    layer.alpha_composite(tmp)


# ------------------------------------------------------------------ manos y pies
FINGERS = [(1.0, 0.95), (0.33, 1.0), (-0.33, 0.96), (-1.0, 0.8)]


def hand_points(wrist, ang, curl, spread, side, k=1.0):
    u = ang_vec(ang)
    nt = side * np.array([u[1], -u[0]])
    c = wrist + u * 12 * k
    segs = []
    for (o, lf) in FINGERS:
        base = c + nt * o * 14 * k + u * 6 * k
        d = unit(u + nt * math.tan(math.radians(o * 7 * spread)))
        mcp = base + d * 44 * lf * k
        pts = [base, mcp]
        p = mcp
        for L in (27, 18, 13):
            d = rotv(d, -side * curl * 38)
            p = p + d * L * lf * k * (1 - 0.32 * curl)
            pts.append(p)
        segs.append(pts)
    tb = c + nt * 19 * k - u * 2 * k
    dt = unit(u * 0.8 + nt * 0.55)
    pts = [tb]
    p = tb
    for L in (26, 19, 14):
        p = p + dt * L * k * (1 - 0.2 * curl)
        pts.append(p)
        dt = rotv(dt, side * curl * 30)
    segs.append(pts)
    return c, segs


def draw_hand(pen, wrist, ang, curl=0.3, spread=1.0, side=1, k=1.0):
    c, segs = hand_points(wrist, ang, curl, spread, side, k)
    u = ang_vec(ang)
    for i in range(4):
        pen.circle(wrist + u * (6 + (i % 2) * 9) * k + perp(u) * ((i // 2) * 2 - 1) * 7 * k, 7 * k, BONE_DARK)
    for i in range(4):
        pen.circle(wrist + u * (6 + (i % 2) * 9) * k + perp(u) * ((i // 2) * 2 - 1) * 7 * k, 5.6 * k, IVORY)
    widths = [6.5, 5.6, 4.8, 4.2]
    for pts in segs:
        for j in range(len(pts) - 1):
            w = widths[j] * k
            bone(pen, pts[j], pts[j + 1], w, w * 0.62, w * 0.62, o=1.4, hl=False)


def draw_foot(pen, ankle, toe, side, k=1.0):
    u = unit(toe - ankle)
    L = np.hypot(*(toe - ankle))
    n = perp(u)
    bone(pen, ankle - u * 4 * k + n * side * 2, ankle + u * 14 * k, 18 * k, 13 * k, 11 * k, o=1.6)
    for o in (-2, -1, 0, 1, 2):
        a = ankle + u * 18 * k + n * o * 6 * k
        b = ankle + u * L * 0.72 + n * o * 11 * k
        bone(pen, a, b, 5.5 * k, 3.5 * k, 3.8 * k, o=1.3, hl=False)
        c = b + unit(b - a) * L * 0.22
        bone(pen, b, c, 4.2 * k, 3 * k, 2.6 * k, o=1.2, hl=False)


# ------------------------------------------------------------------ pose
def pose_bbox(p, margin=150):
    pts = [p[k] for k in ("head", "N", "shL", "shR", "elL", "elR", "wrL", "wrR", "P", "hipL", "hipR",
                          "knL", "knR", "anL", "anR", "toeL", "toeR")]
    pts = np.array(pts)
    x0, y0 = pts.min(0) - margin
    x1, y1 = pts.max(0) + margin
    y0 -= 60
    return int(x0), int(y0), int(x1), int(y1)


def spine_points(p, n=24):
    a = p["P"] - p["down"] * 30
    b = p["N"]
    c = (a + b) / 2 + p.get("bend", V(0, 0))
    return [bezier(a, c, b, i / (n - 1)) for i in range(n)]


def torso_frame(p):
    sp = spine_points(p)
    D = unit(sp[len(sp) // 2] - p["N"])
    R = np.array([D[1], -D[0]])
    return R, D


def draw_ribcage(pen, p):
    k = p.get("k", 1.0)
    R, D = torso_frame(p)
    N = p["N"]
    sx = 1.0 + p.get("breath", 0.0)
    sy = 1.0 + p.get("breath", 0.0) * 0.4
    L = lambda x, y: N + R * x * sx * k + D * y * sy * k
    widths = [44, 58, 68, 76, 82, 86, 88, 86, 80, 70]
    # escápulas (detrás)
    # parte posterior de las costillas (más tenue)
    for i, w in enumerate(widths):
        y = 18 + i * 21
        for s in (-1, 1):
            pts = catmull([L(s * 10, y - 10), L(s * w * 0.6, y - 14), L(s * w * 0.97, y - 2)], 6)
            pen.line(pts, (196, 182, 156, 150), 5 * k)
    # costillas frontales
    for i, w in enumerate(widths):
        y = 18 + i * 21
        d = 26 + i * 2.6
        for s in (-1, 1):
            pts = catmull([L(s * w * 0.97, y - 4), L(s * w, y + 8), L(s * w * 0.8, y + d * 0.7),
                           L(s * w * 0.42, y + d), L(s * w * 0.22, y + d * 0.95)], 6)
            curve_bone(pen, pts, 7.2 * k, o=1.6)
            if i < 7:
                ys = 14 + i * 19
                cp = catmull([pts[-1], L(s * 12, ys + 12 + i * 1.2)], 4)
                pen.line(cp, (176, 168, 150, 255), 6.6 * k)
                pen.line(cp, CART + (255,), 4.4 * k)
            elif i < 9:
                cp = catmull([pts[-1], L(s * w * 0.3, y + d - 18), L(s * 26, 160)], 4)
                pen.line(cp, (176, 168, 150, 255), 6.0 * k)
                pen.line(cp, CART + (255,), 3.8 * k)
    # esternón
    st = [L(-11, 6), L(11, 6), L(14, 28), L(10, 34), L(10, 150), L(0, 172), L(-10, 150), L(-10, 34), L(-14, 28)]
    pen.poly(st, BONE_DARK + (255,))
    st2 = [L(-9, 8), L(9, 8), L(12, 28), L(8, 34), L(8, 148), L(0, 168), L(-8, 148), L(-8, 34), L(-12, 28)]
    pen.poly(st2, IVORY + (255,))
    pen.line([L(-3, 40), L(-3, 140)], BONE_LIGHT, 2.2 * k)
    # clavículas
    for s, sh in ((-1, p["shL"]), (1, p["shR"])):
        pts = catmull([L(s * 9, 4), L(s * 50, -6), L(s * 90, 2), sh + R * (-s) * 10 * k + D * (-4) * k], 6)
        curve_bone(pen, pts, 8.5 * k, o=1.8)


def draw_pelvis(pen, p):
    k = p.get("k", 1.0)
    P = p["P"]
    u = unit(p["hipR"] - p["hipL"])
    n = perp(u)
    hw = np.hypot(*(p["hipR"] - p["hipL"])) / 2
    for s in (-1, 1):
        H = p["hipL"] if s < 0 else p["hipR"]
        wing = [P + s * u * 22 * k - n * 52 * k, P + s * u * 70 * k - n * 70 * k, P + s * u * 104 * k - n * 52 * k,
                P + s * u * 110 * k - n * 22 * k, H + s * u * 12 * k - n * 12 * k, H - s * u * 6 * k + n * 4 * k,
                P + s * u * 26 * k + n * 12 * k]
        sm = catmull(wing + [wing[0]], 5)
        pen.poly(sm, BONE_DARK + (255,))
        pen.poly([q - (q - (P + s * u * 62 * k - n * 30 * k)) * 0.045 for q in sm], IVORY + (255,))
        pen.ellipse(P + s * u * 66 * k - n * 34 * k, 26 * k, 20 * k, fill=(150, 130, 100, 70), ang=-s * 15)
        pen.line(catmull(wing[:4], 5), BONE_LIGHT + (255,), 2.2 * k)
        # rama del pubis e isquion
        loop = [H - s * u * 4 * k + n * 6 * k, P + s * u * 18 * k + n * 62 * k, P + s * u * 6 * k + n * 84 * k,
                P + s * u * 30 * k + n * 104 * k, H + s * u * 2 * k + n * 52 * k, H + n * 18 * k]
        lp = catmull(loop + [loop[0]], 5)
        pen.line(lp, BONE_DARK + (255,), 13 * k)
        pen.line(lp, IVORY + (255,), 9.5 * k)
        pen.ellipse(P + s * u * 28 * k + n * 76 * k, 11 * k, 16 * k, fill=(60, 48, 38, 200), ang=-s * 20)
        pen.circle(H, 20 * k, outline=BONE_DARK + (255,), width=3.0 * k)
    # sacro
    sac = [P - n * 46 * k - u * 26 * k, P - n * 46 * k + u * 26 * k, P + n * 24 * k + u * 12 * k, P + n * 44 * k,
           P + n * 24 * k - u * 12 * k]
    pen.poly(sac, BONE_DARK + (255,))
    pen.poly([q + (P - n * 8 * k - q) * 0.1 for q in sac], (226, 214, 188, 255))
    for j in range(4):
        for s in (-1, 1):
            pen.circle(P - n * (34 - j * 15) * k + s * u * (13 - j * 2) * k, 3.2 * k, (110, 92, 72, 220))


def draw_spine(pen, p, lo=0.0, hi=1.0, wmin=20, wmax=36):
    k = p.get("k", 1.0)
    sp = spine_points(p, 26)
    n = len(sp)
    for i in range(n):
        f = i / (n - 1)
        if f < lo or f > hi:
            continue
        a = sp[max(0, i - 1)]
        b = sp[min(n - 1, i + 1)]
        u = unit(b - a)
        w = (wmax - (wmax - wmin) * f) * k
        pen.ellipse(sp[i], w / 2 + 1.6, 6.8 * k + 1.6, fill=BONE_DARK + (255,), ang=math.degrees(math.atan2(u[1], u[0])) + 90)
        pen.ellipse(sp[i], w / 2, 6.0 * k, fill=IVORY + (255,), ang=math.degrees(math.atan2(u[1], u[0])) + 90)
        if f < 0.35:
            nn = perp(u)
            pen.line([sp[i] - nn * w * 0.95, sp[i] + nn * w * 0.95], BONE_DARK + (255,), 4.6 * k)
            pen.line([sp[i] - nn * w * 0.9, sp[i] + nn * w * 0.9], IVORY + (255,), 2.8 * k)


def draw_neck(pen, p):
    k = p.get("k", 1.0)
    base = p["head"] + rotv(V(0, 92) * k, p.get("head_rot", 0))
    for i in range(7):
        f = (i + 0.5) / 7
        c = lerp(p["N"], base, f)
        u = unit(base - p["N"])
        pen.ellipse(c, 12 * k, 6.4 * k, fill=BONE_DARK + (255,), ang=math.degrees(math.atan2(u[1], u[0])) + 90)
        pen.ellipse(c, 10.5 * k, 5.2 * k, fill=IVORY + (255,), ang=math.degrees(math.atan2(u[1], u[0])) + 90)


def draw_arm(pen, p, s, pre_hand=None):
    k = p.get("k", 1.0)
    side = "L" if s < 0 else "R"
    sh, el, wr = p["sh" + side], p["el" + side], p["wr" + side]
    bone(pen, sh, el, 15 * k, 17 * k, 12 * k)
    u = unit(wr - el)
    n = perp(u)
    bone(pen, el + n * 5 * k, wr + n * 7 * k, 8 * k, 8 * k, 6 * k, o=1.7)
    bone(pen, el - n * 4 * k, wr - n * 5 * k, 7.5 * k, 9 * k, 5 * k, o=1.7)
    if pre_hand:
        pre_hand()
    h = p["hand" + side]
    draw_hand(pen, wr, h[0], curl=h[1], spread=h[2] if len(h) > 2 else 1.0, side=-s, k=k)


def draw_leg(pen, p, s):
    k = p.get("k", 1.0)
    side = "L" if s < 0 else "R"
    hip, kn, an, toe = p["hip" + side], p["kn" + side], p["an" + side], p["toe" + side]
    draw_foot(pen, an, toe, s, k)
    u = unit(an - kn)
    n = perp(u) * s
    bone(pen, kn + n * 14 * k, an + n * 9 * k, 7 * k, 7 * k, 7 * k, o=1.6)
    bone(pen, kn - n * 3 * k, an - n * 2 * k, 17 * k, 18 * k, 12 * k)
    uf = unit(kn - hip)
    nf = perp(uf) * s
    bone(pen, hip + nf * 6 * k, kn, 20 * k, 19 * k, 19 * k)
    pen.circle(kn + uf * 4 * k, 12 * k, BONE_DARK + (255,))
    pen.circle(kn + uf * 4 * k, 10 * k, (244, 236, 214, 255))


# ------------------------------------------------------------------ cuerpo de cristal
def glass_mask(p, region):
    k = p.get("k", 1.0)
    x0, y0, x1, y1 = region
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    pen = Pen(m, s=1, off=(x0, y0))
    hr = p.get("head_rot", 0)
    pen.ellipse(p["head"] + rotv(V(0, 6) * k, hr), 92 * k, 116 * k, fill=255, ang=hr)
    pen.capsule(p["head"] + rotv(V(0, 90) * k, hr), p["N"], 80 * k, 255)
    sp = spine_points(p, 20)
    prof = [(0.0, 60), (0.06, 130), (0.3, 128), (0.62, 104), (0.86, 124), (1.0, 118)]
    left, right = [], []
    for i, c in enumerate(sp[::-1]):
        f = i / (len(sp) - 1)
        w = np.interp(f, [a for a, _ in prof], [b for _, b in prof]) * k * (1 + p.get("breath", 0) * 0.6)
        a = sp[::-1][max(0, i - 1)]
        b = sp[::-1][min(len(sp) - 1, i + 1)]
        R = np.array([unit(b - a)[1], -unit(b - a)[0]])
        left.append(c + R * w)
        right.append(c - R * w)
    pen.poly(left + right[::-1], 255)
    for s in ("L", "R"):
        pen.capsule(p["N"] + V(0, 30) * k, p["sh" + s], 84 * k, 255)
        pen.capsule(p["sh" + s], p["el" + s], 68 * k, 255)
        pen.capsule(p["el" + s], p["wr" + s], 54 * k, 255)
        h = p["hand" + s]
        c, segs = hand_points(p["wr" + s], h[0], h[1], h[2] if len(h) > 2 else 1.0, -1 if s == "L" else 1, k)
        pen.circle(c + ang_vec(h[0]) * 22 * k, 30 * k, 255)
        for pts in segs:
            pen.line(pts, 255, 19 * k)
            pen.circle(pts[-1], 9.5 * k, 255)
        pen.capsule(p["hip" + s], p["kn" + s], 104 * k, 255)
        pen.capsule(p["kn" + s], p["an" + s], 74 * k, 255)
        pen.capsule(p["an" + s], p["toe" + s], 50 * k, 255)
    pen.capsule(p["hipL"], p["hipR"], 130 * k, 255)
    return m


def render_glass(mask, color=(214, 232, 246), light=(-1.0, -0.4), strength=1.0):
    M = np.asarray(mask.filter(ImageFilter.GaussianBlur(2.2)), float) / 255
    inner = np.asarray(mask.filter(ImageFilter.GaussianBlur(14)), float) / 255
    rim = np.clip((M - inner) * 2.4, 0, 1) * M
    lx, ly = light
    sh = np.roll(inner, (int(round(-ly * 12)), int(round(-lx * 12))), (0, 1))
    spec = np.clip((inner - sh) * 3.2, 0, 1) * M
    fill = (0.12 * M + 0.12 * (1 - inner) * M) * strength
    h, w = M.shape
    back = np.zeros((h, w, 4), np.uint8)
    back[..., :3] = color
    back[..., 3] = np.clip(fill * 255, 0, 255)
    front = np.zeros((h, w, 4), np.uint8)
    rc = np.array([min(255, c + 30) for c in color], float)
    front[..., :3] = np.clip(rc * (1 - spec[..., None] * 0.3) + 255 * spec[..., None] * 0.3, 0, 255)
    front[..., 3] = np.clip((rim * 0.5 + spec * 0.55) * 255 * strength, 0, 255)
    return Image.fromarray(back, "RGBA"), Image.fromarray(front, "RGBA")


SKULL = None


def draw_skull(layer, pen, p, off):
    global SKULL
    if SKULL is None:
        SKULL = make_skull()
    spr, org = SKULL
    k = p.get("k", 1.0)
    hr = p.get("head_rot", 0)
    paste_sprite(layer, spr, org, p["head"], 2, angle=hr, off=off)
    g = p.get("gaze", V(0, 0))
    for s in (-1, 1):
        c = p["head"] + rotv(V(s * 31, 10) * k, hr) + V(g[0], g[1]) * 7.5 * k
        pen.circle(c, 10.5 * k, (150, 104, 10, 255))
        pen.circle(c, 9.2 * k, (238, 182, 26, 255))
        pen.circle(c + V(-1, -1) * k, 6.6 * k, (255, 214, 60, 255))
        pen.circle(c, 4.6 * k * p.get("pupil", 1.0), (18, 12, 8, 255))
        pen.circle(c + V(-3.2, -3.4) * k, 1.8 * k, (255, 255, 255, 230))


def render_character(p, tint=(1.0, 1.0, 1.0), glass_color=(214, 232, 246), light=(-1.0, -0.4), glass_strength=1.0):
    """Devuelve (región, capa cristal detrás, capa huesos, capa cristal delante), todas 1x."""
    region = pose_bbox(p)
    x0, y0, x1, y1 = region
    w, h = x1 - x0, y1 - y0
    bl = Image.new("RGBA", (w * 2, h * 2), BONE_DARK + (0,))
    pen = Pen(bl, s=2, off=(x0, y0))
    for s in (-1, 1):
        draw_leg(pen, p, s)
    draw_spine(pen, p, 0.0, 0.42)
    draw_pelvis(pen, p)
    draw_spine(pen, p, 0.42, 1.0, 18, 26)
    draw_ribcage(pen, p)
    draw_neck(pen, p)
    held = p.get("held", [])
    order = p.get("arm_order", (-1, 1))
    if p.get("arms_behind_head"):
        for s in order:
            draw_arm(pen, p, s, _held_cb(bl, held, "L" if s < 0 else "R", (x0, y0)))
        draw_skull(bl, pen, p, (x0, y0))
    else:
        draw_skull(bl, pen, p, (x0, y0))
        for s in order:
            draw_arm(pen, p, s, _held_cb(bl, held, "L" if s < 0 else "R", (x0, y0)))
    bones = bl.resize((w, h), Image.LANCZOS)
    if tint != (1.0, 1.0, 1.0):
        a = np.asarray(bones).astype(float)
        a[..., :3] *= np.array(tint)
        bones = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    mask = glass_mask(p, region)
    back, front = render_glass(mask, glass_color, light, glass_strength)
    return region, back, bones, front


def _held_cb(layer, held, side, off):
    items = [h for h in held if h[4] == side]
    if not items:
        return None

    def cb():
        for spr, an, pos, ang, _ in items:
            paste_sprite(layer, spr, an, pos, 2, angle=ang, off=off)
    return cb
