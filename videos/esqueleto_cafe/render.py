#!/usr/bin/env python3
"""Renderiza «Qué pasa si dejas el café» (videos/esqueleto_cafe.json) dibujando y animando cada escena en local.

Uso:  python3 videos/esqueleto_cafe/render.py [videos/esqueleto_cafe.json] [-o salida.mp4] [--solo N]
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "video"))
import make_video as mv  # noqa: E402
from personaje import (V, Pen, ang_vec, ease, lerp, make_mug, noise, paste_sprite, perp,  # noqa: E402
                       render_character, rotv, seg, unit)

W, H, FPS = 1080, 1920, 30
SR = mv.SR


# ====================================================================== utilidades de dibujo
def vgrad(stops, w=W, h=H):
    ys = np.linspace(0, 1, h)
    cols = np.stack([np.interp(ys, [s[0] for s in stops], [s[1][c] for s in stops]) for c in range(3)], -1)
    arr = np.broadcast_to(cols[:, None, :], (h, w, 3)).astype(np.uint8)
    return Image.fromarray(np.ascontiguousarray(arr), "RGB").convert("RGBA")


def big():
    img = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    return img, Pen(img, s=2)


def small(img):
    return img.resize((W, H), Image.LANCZOS)


def add_light(img, cx, cy, r, color, strength, sx=1.0, sy=1.0):
    a = np.asarray(img).astype(np.float32)
    y, x = np.mgrid[0:img.height, 0:img.width]
    d2 = ((x - cx) / (r * sx)) ** 2 + ((y - cy) / (r * sy)) ** 2
    g = np.exp(-d2 * 1.6) * strength
    a[..., :3] = a[..., :3] + (np.array(color, np.float32) - a[..., :3] * 0.35) * g[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def light_layer(cx, cy, r, color, alpha, sx=1.0, sy=1.0):
    y, x = np.mgrid[0:H, 0:W]
    d2 = ((x - cx) / (r * sx)) ** 2 + ((y - cy) / (r * sy)) ** 2
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = color
    out[..., 3] = np.clip(np.exp(-d2 * 1.6) * alpha * 255, 0, 255)
    return Image.fromarray(out, "RGBA")


def vignette(strength=0.55, r0=0.45, color=(0, 0, 0)):
    y, x = np.mgrid[0:H, 0:W]
    r = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H * 0.48) / (H * 0.6)) ** 2)
    a = np.clip((r - r0) / (1 - r0), 0, 1) ** 1.5 * strength
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = color
    out[..., 3] = np.clip(a * 255, 0, 255)
    return Image.fromarray(out, "RGBA")


def tone(img, mul=(1, 1, 1), add=(0, 0, 0)):
    a = np.asarray(img).astype(np.float32)
    a[..., :3] = a[..., :3] * np.array(mul, np.float32) + np.array(add, np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def soft_shadow(img, cx, cy, rx, ry, alpha=110, blur=14):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(0, 0, 0, alpha))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)))


MUGS = {}


def mug(w=90, fill=0.8, color=(238, 236, 230), stain=False):
    key = (w, round(fill, 2), color, stain)
    if key not in MUGS:
        MUGS[key] = make_mug(w, fill, color, stain)
    return MUGS[key]


def put_mug(img, pos, w=90, fill=0.8, color=(238, 236, 230), stain=False, angle=0.0, shadow=True):
    spr, an = mug(w, fill, color, stain)
    if shadow:
        soft_shadow(img, pos[0] + 4, pos[1] + w * 0.44, w * 0.62, w * 0.09, 120, 5)
    paste_sprite(img, spr, an, pos, 1, angle=angle)


def steam(img, x, y, t, scale=1.0, alpha=70, seed=0.0):
    lw, lh = int(170 * scale), int(300 * scale)
    lay = Image.new("RGBA", (lw, lh), (255, 255, 255, 0))
    d = ImageDraw.Draw(lay)
    for k in range(3):
        ph = (t * 0.55 + k * 0.33 + seed) % 1.0
        pts = []
        for j in range(16):
            f = j / 15
            yy = lh - 10 - f * (lh - 30) * (0.55 + 0.45 * ph)
            xx = lw / 2 + (k - 1) * 14 * scale + math.sin(f * 5.5 + t * 2.1 + k * 2.2 + seed) * (3 + f * 22) * scale
            pts.append((xx, yy))
        a = int(alpha * math.sin(ph * math.pi) ** 0.6)
        for j in range(len(pts) - 1):
            aa = int(a * (1 - j / len(pts)))
            d.line([pts[j], pts[j + 1]], fill=(255, 255, 255, aa), width=max(2, int(9 * scale)))
    lay = lay.filter(ImageFilter.GaussianBlur(6 * scale))
    img.alpha_composite(lay, (int(x - lw / 2), int(y - lh)))


def tiles(pen, x0, y0, x1, y1, tw, th, col, width=1.2, offset=True):
    y = y0
    row = 0
    while y < y1:
        pen.line([(x0, y), (x1, y)], col, width)
        x = x0 + (tw / 2 if (offset and row % 2) else 0)
        while x < x1:
            pen.line([(x, y), (x, min(y1, y + th))], col, width)
            x += tw
        y += th
        row += 1


def planks(pen, x0, y0, x1, y1, col, n=9, seed=1):
    rng = random.Random(seed)
    for i in range(n + 1):
        f = i / n
        xa = lerp(x0 + (x1 - x0) * 0.35, x0 - (x1 - x0) * 0.6, 0) if False else None
        # tablas que convergen hacia el fondo (perspectiva)
        xb = W / 2 + (f - 0.5) * W * 2.6
        xt = W / 2 + (f - 0.5) * W * 1.25
        pen.line([(xt, y0), (xb, y1)], col, 1.4)
        for _ in range(2):
            yy = rng.uniform(y0 + 20, y1)
            g = (yy - y0) / (y1 - y0)
            xa = lerp(W / 2 + (f - 0.5) * W * 1.25, xb, g)
            xn = lerp(W / 2 + (f + 1 / n - 0.5) * W * 1.25, W / 2 + (f + 1 / n - 0.5) * W * 2.6, g)
            pen.line([(xa, yy), (xn, yy)], col, 1.2)


# ====================================================================== poses
def finalize(p):
    p["down"] = perp(unit(p["hipR"] - p["hipL"]))
    return p


def seated(cx=540):
    return dict(head=V(cx, 470), head_rot=0.0, gaze=V(0, 0), N=V(cx, 655), shL=V(cx - 148, 678), shR=V(cx + 148, 678),
                elL=V(cx - 170, 900), elR=V(cx + 170, 900), wrL=V(cx - 165, 1100), wrR=V(cx + 165, 1100),
                handL=(92, 0.3, 1.0), handR=(88, 0.3, 1.0),
                P=V(cx, 1035), hipL=V(cx - 75, 1068), hipR=V(cx + 75, 1068), knL=V(cx - 88, 1168), knR=V(cx + 88, 1168),
                anL=V(cx - 84, 1455), anR=V(cx + 84, 1455), toeL=V(cx - 104, 1506), toeR=V(cx + 104, 1506))


def standing(cx=540):
    return dict(head=V(cx, 400), head_rot=0.0, gaze=V(0, 0), N=V(cx, 590), shL=V(cx - 150, 612), shR=V(cx + 150, 612),
                elL=V(cx - 168, 840), elR=V(cx + 168, 840), wrL=V(cx - 160, 1050), wrR=V(cx + 160, 1050),
                handL=(92, 0.3, 1.0), handR=(88, 0.3, 1.0),
                P=V(cx, 990), hipL=V(cx - 75, 1025), hipR=V(cx + 75, 1025), knL=V(cx - 70, 1310), knR=V(cx + 70, 1310),
                anL=V(cx - 65, 1600), anR=V(cx + 65, 1600), toeL=V(cx - 88, 1655), toeR=V(cx + 88, 1655))


# ====================================================================== escenas
class Scene:
    tint = (1.0, 1.0, 1.0)
    glass = (214, 232, 246)
    light = (-1.0, -0.4)
    over_mask = None
    fade_in = 0.3
    fade_out = 0.3
    fg = None

    def __init__(self, spec, dur, voice_dur, voice_at):
        self.spec, self.dur, self.vdur, self.vat = spec, dur, voice_dur, voice_at
        self.build()

    def build(self):
        self.bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        self.fg = None
        self.grade = vignette()

    def pose(self, t):
        return None

    def behind(self, img, t, p):
        pass

    def front(self, img, t, p):
        pass

    def camera(self, t):
        return 1.0, W / 2, H / 2

    def glass_strength(self, t):
        return 1.0

    def frame(self, t):
        img = self.bg.copy()
        self.behind(img, t, None)
        p = self.pose(t)
        if p is not None:
            p = finalize(p)
            self.behind_char(img, t, p)
            r, back, bones, front = render_character(p, self.tint, self.glass, self.light, self.glass_strength(t))
            char = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for lay in (back, bones, front):
                char.alpha_composite(lay, (max(0, r[0]), max(0, r[1])), (max(0, -r[0]), max(0, -r[1])))
            img.alpha_composite(char)
        if self.fg is not None:
            img.alpha_composite(self.fg)
        if p is not None and self.over_mask is not None:
            a = np.asarray(char).copy()
            a[..., 3] = (a[..., 3].astype(np.uint16) * self.over_mask // 255).astype(np.uint8)
            img.alpha_composite(Image.fromarray(a, "RGBA"))
        self.front(img, t, p)
        if self.grade is not None:
            img.alpha_composite(self.grade)
        z, cx, cy = self.camera(t)
        if z > 1.001:
            cw, ch = W / z, H / z
            x0 = min(max(0, cx - cw / 2), W - cw)
            y0 = min(max(0, cy - ch / 2), H - ch)
            img = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        img = img.convert("RGB")
        self.overlay(img, t)
        k = 1.0
        if self.fade_in:
            k = min(k, t / self.fade_in)
        if self.fade_out:
            k = min(k, (self.dur - t) / self.fade_out)
        k = max(0.0, min(1.0, k))
        if k < 1:
            img = Image.blend(Image.new("RGB", img.size), img, ease(k))
        return img

    def behind_char(self, img, t, p):
        pass

    # ------------------------------------------------------------ textos
    def overlay(self, img, t):
        d = ImageDraw.Draw(img, "RGBA")
        sp = self.spec
        if sp.get("etiqueta"):
            a = ease((t - 0.25) / 0.6)
            if a > 0:
                f1 = mv.font(54)
                f2 = mv.font(38, bold=False)
                txt = sp["etiqueta"]
                tw = d.textlength(txt, font=f1)
                y = 118
                d.text(((W - tw) / 2, y), txt, font=f1, fill=(244, 196, 92, int(255 * a)),
                       stroke_width=3, stroke_fill=(0, 0, 0, int(120 * a)))
                bw = 70 * a
                d.rounded_rectangle([W / 2 - bw, y + 76, W / 2 + bw, y + 80], 2, fill=(244, 196, 92, int(220 * a)))
                sub = sp.get("subetiqueta", "")
                tw2 = d.textlength(sub, font=f2)
                d.text(((W - tw2) / 2, y + 96), sub, font=f2, fill=(255, 255, 255, int(230 * a)),
                       stroke_width=2, stroke_fill=(0, 0, 0, int(140 * a)))
        if sp.get("voz") and self.vdur:
            self.subtitle(d, t)

    def subtitle(self, d, t):
        text = self.spec["voz"]
        parts, cur = [], ""
        for ch in text:
            cur += ch
            if ch in ".…?!":
                parts.append(cur.strip())
                cur = ""
        if cur.strip():
            parts.append(cur.strip())
        parts = [p for p in parts if p.strip(".… ")]
        lens = [len(p) + 6 for p in parts]
        tot = sum(lens)
        lt = t - self.vat
        if lt < -0.1 or lt > self.vdur + 0.5:
            return
        acc = 0
        cur = parts[-1]
        for p, L in zip(parts, lens):
            if lt < (acc + L) / tot * self.vdur:
                cur = p
                break
            acc += L
        f = mv.font(50)
        lines = mv.wrap(d, cur, f, W * 0.84)
        lh = 64
        y0 = 1690 - lh * len(lines) / 2
        for i, line in enumerate(lines):
            tw = d.textlength(line, font=f)
            d.text(((W - tw) / 2, y0 + i * lh), line, font=f, fill=(255, 255, 255, 255),
                   stroke_width=4, stroke_fill=(0, 0, 0, 200))


# ---------------------------------------------------------------- 1 · cocina, mañana
class S1(Scene):
    tint = (1.02, 0.99, 0.94)
    glass = (255, 240, 220)
    light = (-1.0, -0.5)

    def build(self):
        bg = vgrad([(0, (236, 228, 214)), (0.676, (224, 214, 198)), (0.677, (196, 168, 130)), (1, (156, 126, 92))])
        far, pen = big()
        # ventana
        pen.rect(50, 170, 480, 770, fill=(250, 248, 242, 255), r=4)
        far_sky = [(70, 190, 470, 750)]
        for (a, b, c, e) in far_sky:
            pen.rect(a, b, c, e, fill=(255, 250, 234, 255))
        for i, (x, y, r) in enumerate([(120, 700, 90), (230, 720, 70), (380, 690, 110), (300, 640, 60), (440, 730, 60)]):
            pen.circle((x, y), r, fill=(150, 178, 120, 150))
        pen.line([(265, 190), (265, 750)], (248, 246, 240, 255), 14)
        pen.line([(70, 470), (470, 470)], (248, 246, 240, 255), 14)
        # azulejos y armarios
        pen.rect(0, 770, 1080, 985, fill=(242, 238, 230, 255))
        tiles(pen, 0, 770, 1080, 985, 70, 35, (220, 214, 204, 255))
        pen.rect(560, 210, 1080, 640, fill=(246, 244, 240, 255))
        for x in (560, 820, 1080):
            pen.line([(x, 210), (x, 640)], (214, 210, 202, 255), 3)
        for x in (800, 840):
            pen.rect(x - 3, 560, x + 3, 610, fill=(90, 88, 84, 255))
        pen.rect(0, 980, 1080, 1004, fill=(228, 224, 218, 255))
        pen.rect(0, 1004, 1080, 1290, fill=(238, 236, 232, 255))
        for x in (0, 270, 540, 810, 1080):
            pen.line([(x, 1004), (x, 1290)], (210, 206, 198, 255), 3)
            pen.rect(x + 110, 1030, x + 160, 1036, fill=(90, 88, 84, 255))
        pen.rect(0, 1290, 1080, 1302, fill=(150, 140, 128, 255))
        # cafetera y planta del fondo
        pen.rect(840, 850, 950, 982, fill=(52, 52, 55, 255), r=10)
        pen.rect(860, 930, 930, 975, fill=(30, 30, 32, 255), r=4)
        pen.rect(90, 920, 170, 982, fill=(206, 196, 180, 255), r=6)
        for a in range(-60, 61, 20):
            c = V(130, 905) + ang_vec(a - 90) * 50
            pen.ellipse(c, 14, 40, fill=(88, 128, 82, 255), ang=a)
        # lámparas colgantes
        for x in (300, 780):
            pen.line([(x, 0), (x, 260)], (40, 40, 40, 255), 3)
            pen.poly([(x - 55, 310), (x - 20, 255), (x + 20, 255), (x + 55, 310)], (44, 44, 46, 255))
        far = small(far).filter(ImageFilter.GaussianBlur(3.5))
        bg.alpha_composite(far)
        bg = add_light(bg, 270, 470, 520, (255, 236, 200), 0.45)
        near, pen = big()
        planks(pen, 0, 1302, 1080, 1920, (140, 112, 80, 120), 10)
        # patas traseras de la mesa y silla
        for x in (150, 930):
            pen.rect(x - 5, 842, x + 5, 1350, fill=(40, 40, 42, 255))
        wood = (178, 134, 94, 255)
        pen.rect(418, 716, 662, 790, fill=wood, r=24)
        pen.rect(424, 724, 656, 732, fill=(196, 156, 116, 255), r=4)
        for x in (440, 640):
            pen.rect(x - 9, 760, x + 9, 1080, fill=wood)
        pen.rect(405, 1058, 675, 1092, fill=(160, 118, 80, 255), r=6)
        for x in (425, 655):
            pen.rect(x - 8, 1090, x + 8, 1500, fill=(150, 110, 74, 255))
        near = small(near)
        bg.alpha_composite(near)
        soft_shadow(bg, 540, 1508, 250, 34, 90, 16)
        soft_shadow(bg, 540, 1565, 520, 30, 60, 22)
        self.bg = bg
        # mesa de cristal y portátil (delante)
        fg, pen = big()
        pen.poly([(90, 838), (990, 838), (1050, 900), (30, 900)], (214, 236, 240, 70))
        pen.line([(90, 838), (990, 838)], (255, 255, 255, 120), 2)
        pen.rect(30, 900, 1050, 917, fill=(160, 200, 206, 190))
        pen.line([(30, 901), (1050, 901)], (255, 255, 255, 210), 2)
        for x in (56, 1024):
            pen.rect(x - 6, 917, x + 6, 1565, fill=(38, 38, 40, 255))
        pen.poly([(764, 856), (1008, 856), (1030, 884), (742, 884)], (196, 198, 202, 255))
        pen.rect(772, 636, 1004, 862, fill=(206, 208, 212, 255), r=12)
        pen.rect(772, 636, 1004, 862, outline=(170, 172, 176, 255), r=12, width=2)
        fg = small(fg)
        put_mug(fg, (180, 815), 70, 0.0, (232, 230, 224), stain=True)
        self.fg = fg
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon([(560, 834), (800, 834), (800, 918), (560, 918)], fill=255)
        self.over_mask = np.asarray(m.filter(ImageFilter.GaussianBlur(3))).astype(np.uint16)
        g = light_layer(150, 380, 900, (255, 238, 200), 0.18, 0.7, 1.2)
        g.alpha_composite(light_layer(760, 760, 150, (200, 225, 255), 0.25))
        g.alpha_composite(vignette(0.5))
        self.grade = g

    def pose(self, t):
        p = seated()
        lift = seg(t, 0.3, 3.0)
        p["wrL"] = lerp(V(398, 790), V(404, 622), lift) + V(0, 3 * math.sin(t * 1.3))
        p["elL"] = lerp(V(342, 905), V(348, 880), lift)
        p["handL"] = (-58, 0.62, 0.9)
        p["held"] = [(*mug(84, 0.8), p["wrL"] + V(46, -26), -4 + 3 * lift, "L")]
        p["elR"] = V(746, 868)
        p["wrR"] = V(706, 884)
        p["handR"] = (176, 0.2 + 0.08 * math.sin(t * 2.0), 1.0)
        p["head_rot"] = -2 + 3 * math.sin(t * 0.9)
        p["head"] = V(540, 470 + 2 * math.sin(t * 0.9))
        p["gaze"] = V(0.75, 0.42)
        p["breath"] = 0.012 * math.sin(t * 2 * math.pi / 3.4)
        self._mug = p["wrL"] + V(46, -26)
        return p

    def front(self, img, t, p):
        steam(img, self._mug[0] + 4, self._mug[1] - 30, t, 0.85, 75)

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.0 + 0.07 * f, 540, 860


# ---------------------------------------------------------------- 2 · cocina, día 3
class S2(Scene):
    tint = (0.96, 0.99, 1.04)
    glass = (210, 228, 250)
    light = (-0.6, -0.8)

    def build(self):
        bg = vgrad([(0, (210, 216, 222)), (0.70, (196, 202, 208)), (0.701, (150, 152, 156)), (1, (112, 114, 118))])
        far, pen = big()
        pen.rect(60, 210, 440, 820, fill=(236, 240, 246, 255), r=4)
        pen.rect(78, 228, 422, 802, fill=(226, 236, 246, 255))
        pen.line([(250, 228), (250, 802)], (236, 240, 246, 255), 12)
        pen.rect(0, 840, 1080, 1010, fill=(228, 232, 236, 255))
        tiles(pen, 0, 840, 1080, 1010, 64, 30, (200, 206, 212, 255))
        pen.rect(480, 200, 1080, 600, fill=(220, 224, 228, 255))
        for x in (480, 680, 880):
            pen.line([(x, 200), (x, 600)], (190, 196, 202, 255), 3)
            pen.rect(x + 160, 520, x + 166, 580, fill=(80, 82, 86, 255))
        pen.rect(0, 1000, 700, 1024, fill=(200, 204, 208, 255))
        pen.rect(0, 1024, 700, 1340, fill=(214, 218, 222, 255))
        for x in (0, 230, 460, 690):
            pen.line([(x, 1024), (x, 1340)], (182, 188, 194, 255), 3)
        pen.rect(130, 920, 200, 1000, fill=(170, 175, 180, 255), r=8)
        far = small(far).filter(ImageFilter.GaussianBlur(4))
        bg.alpha_composite(far)
        bg = add_light(bg, 250, 520, 480, (230, 240, 255), 0.35)
        near, pen = big()
        tiles(pen, 0, 1345, 1080, 1920, 150, 70, (128, 130, 134, 160), 1.4, offset=False)
        # encimera a la derecha
        pen.poly([(735, 965), (1080, 955), (1080, 1004), (725, 1004)], (232, 234, 236, 255))
        pen.rect(725, 1004, 1080, 1022, fill=(206, 208, 212, 255))
        pen.rect(735, 1022, 1080, 1650, fill=(236, 238, 240, 255))
        for y in (1022, 1330, 1650):
            pen.line([(735, y), (1080, y)], (196, 200, 204, 255), 3)
        pen.line([(908, 1022), (908, 1650)], (196, 200, 204, 255), 3)
        for (x, y) in ((880, 1060), (936, 1060), (880, 1370), (936, 1370)):
            pen.rect(x - 3, y, x + 3, y + 60, fill=(90, 92, 96, 255))
        near = small(near)
        bg.alpha_composite(near)
        soft_shadow(bg, 540, 1660, 200, 26, 110, 14)
        for (x, w, st) in ((812, 78, True), (1000, 74, True), (1050, 70, False)):
            put_mug(bg, (x, 985 - w * 0.44), w, 0.0, (228, 230, 232), stain=st)
        put_mug(bg, (908, 985 - 80 * 0.44), 80, 0.85, (60, 64, 70))
        self.cup2 = V(912, 985 - 80 * 0.44 - 30)
        self.bg = bg
        g = light_layer(240, 520, 700, (225, 238, 255), 0.12)
        g.alpha_composite(vignette(0.55))
        self.grade = g

    def pose(self, t):
        p = standing()
        drop = seg(t, 0.5, 4.5)
        p["head"] = V(522, 438 + 6 * drop)
        p["head_rot"] = -6 - 3 * drop
        p["gaze"] = V(-0.35 + 0.9 * seg(t, 2.6, 3.4), 0.85)
        p["N"] = V(534, 606 + 4 * drop)
        p["shL"] = V(390, 628 + 8 * drop)
        p["shR"] = V(680, 630 + 8 * drop)
        p["elL"] = V(366, 862 + 4 * drop)
        p["wrL"] = V(428, 935 + 6 * drop)
        p["handL"] = (-16, 0.66, 0.9)
        p["held"] = [(*mug(80, 0.0, (238, 236, 230), True), p["wrL"] + V(52, -12), 4, "L")]
        reach = seg(t, 1.0, 4.4)
        p["elR"] = lerp(V(728, 852), V(768, 842), reach)
        p["wrR"] = lerp(V(752, 960), V(856, 960), reach)
        p["handR"] = (lerp(40, 10, reach), lerp(0.18, 0.45, reach) + 0.04 * math.sin(t * 1.5), 1.0)
        p["breath"] = 0.01 * math.sin(t * 2 * math.pi / 4)
        return p

    def front(self, img, t, p):
        steam(img, self.cup2[0], self.cup2[1], t, 0.8, 60, 0.4)

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.06, 515 + 50 * f, 900


# ---------------------------------------------------------------- 3 · dormitorio, madrugada
class S3(Scene):
    tint = (0.86, 0.9, 1.04)
    glass = (170, 196, 240)
    light = (1.0, -0.3)

    def build(self):
        bg = vgrad([(0, (40, 50, 76)), (0.62, (30, 38, 60)), (0.621, (36, 32, 34)), (1, (24, 22, 24))])
        far, pen = big()
        pen.rect(40, 270, 340, 900, fill=(70, 86, 120, 255), r=4)
        pen.rect(56, 286, 324, 884, fill=(120, 146, 192, 255))
        pen.rect(56, 700, 324, 884, fill=(150, 168, 206, 255))
        pen.line([(190, 286), (190, 884)], (66, 80, 112, 255), 10)
        pen.line([(56, 585), (324, 585)], (66, 80, 112, 255), 10)
        # cabecero, almohadas y cama
        pen.rect(130, 800, 950, 1070, fill=(70, 78, 98, 255), r=18)
        for x in range(170, 950, 90):
            pen.line([(x, 812), (x, 1060)], (60, 66, 86, 255), 3)
        for x in (330, 740):
            pen.ellipse((x, 1010), 150, 46, fill=(196, 202, 216, 255))
        far = small(far).filter(ImageFilter.GaussianBlur(3))
        bg.alpha_composite(far)
        near, pen = big()
        pen.poly([(70, 1040), (1010, 1040), (1040, 1130), (40, 1130)], (176, 184, 202, 255))
        rng = random.Random(3)
        for _ in range(14):
            x, y = rng.uniform(80, 1000), rng.uniform(1048, 1118)
            pen.ellipse((x, y), rng.uniform(40, 110), rng.uniform(8, 18), fill=(150, 160, 182, 140), ang=rng.uniform(-15, 15))
            pen.ellipse((x + 10, y - 6), rng.uniform(30, 80), rng.uniform(5, 10), fill=(210, 216, 230, 120), ang=rng.uniform(-15, 15))
        pen.rect(40, 1130, 1040, 1230, fill=(196, 202, 216, 255))
        for x in range(80, 1040, 70):
            pen.line([(x, 1134), (x + rng.uniform(-14, 14), 1226)], (166, 174, 194, 255), 3)
        pen.rect(30, 1230, 1050, 1270, fill=(60, 44, 34, 255))
        planks(pen, 0, 1270, 1080, 1920, (20, 16, 16, 140), 9, 4)
        # mesita, despertador y lámpara
        pen.rect(830, 1060, 1060, 1430, fill=(78, 58, 44, 255), r=6)
        pen.rect(830, 1060, 1060, 1078, fill=(96, 72, 54, 255), r=4)
        pen.line([(840, 1220), (1050, 1220)], (56, 40, 30, 255), 3)
        pen.rect(930, 1140, 960, 1146, fill=(150, 130, 100, 255))
        pen.rect(845, 985, 960, 1060, fill=(22, 22, 26, 255), r=12)
        pen.rect(855, 997, 950, 1048, fill=(10, 10, 12, 255), r=6)
        pen.rect(1010, 1040, 1046, 1060, fill=(180, 170, 150, 255), r=4)
        pen.line([(1028, 1040), (1028, 930)], (170, 160, 140, 255), 5)
        pen.poly([(975, 940), (1080, 940), (1060, 845), (995, 845)], (255, 214, 160, 255))
        near = small(near)
        d = ImageDraw.Draw(near)
        d.text((862, 1000), "5:47", font=mv.font(38), fill=(255, 120, 60, 255))
        bg.alpha_composite(near)
        bg = add_light(bg, 1030, 900, 330, (255, 190, 120), 0.55)
        bg = add_light(bg, 190, 600, 420, (140, 170, 230), 0.25)
        soft_shadow(bg, 540, 1508, 220, 26, 120, 14)
        put_mug(bg, (990, 1060 - 30), 66, 0.85, (210, 205, 196))
        self.cup = V(992, 1060 - 56)
        self.bg = bg
        g = light_layer(1030, 900, 420, (255, 180, 110), 0.16)
        g.alpha_composite(light_layer(900, 1022, 80, (255, 110, 60), 0.18))
        g.alpha_composite(vignette(0.7, 0.35, (5, 8, 20)))
        self.grade = g

    def behind(self, img, t, p):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        pts = []
        for i in range(30):
            y = 250 + i * 24
            x = 300 + 18 * math.sin(i * 0.7 + t * 1.4) * (i / 30) + 8 * math.sin(t * 0.9)
            pts.append((x, y))
        right = [(x + 120 + 6 * math.sin(i * 1.3), y) for i, (x, y) in enumerate(pts)]
        d.polygon(pts + right[::-1], fill=(44, 56, 92, 255))
        for i in range(4):
            xs = [(x + 25 + i * 26 + 4 * math.sin(y * 0.02 + t), y) for x, y in pts]
            d.line(xs, fill=(34, 44, 74, 255), width=5)
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(2.5)))

    def pose(self, t):
        p = seated()
        sl = seg(t, 0.2, self.dur)
        p["head"] = V(522, 552 + 10 * sl)
        p["head_rot"] = -10 - 5 * sl
        p["gaze"] = V(-0.1, 0.9)
        p["N"] = V(534, 712 + 6 * sl)
        p["shL"] = V(398, 740 + 6 * sl)
        p["shR"] = V(676, 748 + 8 * sl)
        p["P"] = V(540, 1045)
        p["hipL"], p["hipR"] = V(465, 1078), V(615, 1078)
        p["knL"], p["knR"] = V(452, 1172), V(628, 1172)
        p["anL"], p["anR"] = V(456, 1458), V(624, 1458)
        p["toeL"], p["toeR"] = V(436, 1508), V(644, 1508)
        rub = math.sin(t * 2.3)
        p["elL"] = V(318, 610 + 6 * sl)
        p["wrL"] = V(434 + 13 * rub, 454 + 3 * math.sin(t * 4.6) + 10 * sl)
        p["handL"] = (-4 + 6 * rub, 0.38, 1.0)
        p["elR"] = V(704, 950)
        p["wrR"] = V(722 + 3 * math.sin(t * 0.8), 1152)
        p["handR"] = (94, 0.28, 1.0)
        p["breath"] = 0.012 * math.sin(t * 2 * math.pi / 4.5)
        return p

    def front(self, img, t, p):
        steam(img, self.cup[0], self.cup[1], t, 0.6, 45, 0.7)

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.06, 515 + 50 * f, 960


# ---------------------------------------------------------------- 4 · cafetera al amanecer
class S4(Scene):
    tint = (0.98, 0.97, 1.0)
    glass = (226, 222, 236)
    light = (1.0, -0.5)

    def build(self):
        bg = vgrad([(0, (150, 160, 178)), (0.70, (132, 140, 156)), (0.701, (110, 104, 100)), (1, (80, 74, 70))])
        far, pen = big()
        pen.rect(470, 220, 780, 720, fill=(226, 226, 232, 255), r=4)
        for i in range(20):
            f = i / 19
            c = tuple(int(lerp(a, b, f)) for a, b in zip((170, 190, 226), (255, 206, 168)))
            pen.rect(484, 234 + f * 468, 766, 234 + (i + 1) / 20 * 472, fill=c + (255,))
        pen.line([(625, 234), (625, 706)], (210, 210, 218, 255), 10)
        pen.rect(800, 360, 1080, 1345, fill=(70, 66, 70, 255))
        pen.rect(820, 380, 1080, 1345, fill=(34, 34, 42, 255))
        pen.rect(880, 1000, 1080, 1130, fill=(120, 124, 140, 255), r=10)
        pen.rect(900, 960, 1000, 1010, fill=(150, 154, 170, 255), r=10)
        pen.rect(0, 230, 330, 600, fill=(176, 182, 194, 255))
        pen.line([(165, 230), (165, 600)], (150, 156, 168, 255), 3)
        far = small(far).filter(ImageFilter.GaussianBlur(4))
        bg.alpha_composite(far)
        bg = add_light(bg, 625, 600, 380, (255, 214, 176), 0.4)
        near, pen = big()
        planks(pen, 0, 1345, 1080, 1920, (60, 54, 52, 120), 9, 7)
        pen.rect(0, 980, 440, 1000, fill=(214, 210, 204, 255))
        pen.rect(0, 1000, 440, 1018, fill=(170, 166, 160, 255))
        pen.rect(0, 1018, 430, 1650, fill=(96, 104, 112, 255))
        pen.line([(215, 1018), (215, 1650)], (76, 84, 92, 255), 3)
        for x in (195, 235):
            pen.rect(x - 3, 1060, x + 3, 1130, fill=(200, 200, 204, 255))
        # cafetera
        pen.rect(80, 640, 300, 985, fill=(46, 46, 50, 255), r=14)
        pen.rect(96, 600, 170, 700, fill=(150, 176, 196, 200), r=8)
        pen.rect(110, 760, 270, 812, fill=(60, 60, 66, 255), r=10)
        pen.rect(178, 812, 202, 834, fill=(150, 150, 156, 255), r=3)
        pen.rect(104, 968, 278, 986, fill=(160, 162, 168, 255), r=3)
        pen.circle((262, 690), 6, fill=(120, 220, 255, 255))
        pen.rect(110, 680, 230, 712, fill=(30, 30, 34, 255), r=4)
        near = small(near)
        bg.alpha_composite(near)
        bg = add_light(bg, 200, 760, 260, (255, 210, 150), 0.25, 1.4, 0.6)
        soft_shadow(bg, 565, 1660, 210, 26, 110, 14)
        self.bg = bg
        g = light_layer(625, 520, 650, (255, 214, 176), 0.12)
        g.alpha_composite(vignette(0.6))
        self.grade = g
        self.t_rel = 1.9

    def pose(self, t):
        p = standing(560)
        sh = 7 * math.sin(t * 0.85)
        p["head"] = V(474 + sh * 0.3, 472)
        p["head_rot"] = -14
        p["gaze"] = V(-0.75, 0.6)
        p["N"] = V(516 + sh * 0.4, 632)
        p["bend"] = V(-18, 0)
        p["shL"] = V(380 + sh * 0.4, 672)
        p["shR"] = V(664 + sh * 0.4, 642)
        p["P"] = V(562 + sh, 990)
        p["hipL"], p["hipR"] = V(487 + sh, 1025), V(637 + sh, 1025)
        p["knL"], p["knR"] = V(495 + sh * 0.5, 1310), V(632 + sh * 0.5, 1310)
        p["anL"], p["anR"] = V(500, 1600), V(628, 1600)
        p["toeL"], p["toeR"] = V(478, 1655), V(650, 1655)
        place = seg(t, 0.2, self.t_rel)
        back = seg(t, self.t_rel + 0.1, self.t_rel + 1.0)
        p["wrL"] = lerp(lerp(V(330, 936), V(240, 948), place), V(272, 925), back)
        p["elL"] = lerp(V(300, 850), V(282, 842), place)
        p["handL"] = (180, lerp(0.62, 0.25, back), 0.9)
        if t < self.t_rel:
            p["held"] = [(*mug(80, 0.0), p["wrL"] + V(-54, 0), 0, "L")]
        p["elR"] = V(602, 852)
        p["wrR"] = V(458, 984)
        p["handR"] = (182, 0.22, 1.0)
        p["breath"] = 0.01 * math.sin(t * 2 * math.pi / 4)
        return p

    def front(self, img, t, p):
        cup = V(186, 948)
        if t >= self.t_rel:
            lvl = seg(t, 2.4, self.dur - 0.5)
            put_mug(img, cup, 80, 0.05 + lvl * 0.8, shadow=False)
            if t > 2.2 and t < self.dur - 0.6:
                d = ImageDraw.Draw(img, "RGBA")
                top = V(190, 834)
                bot = V(190, 920)
                pts = [top + V(1.2 * math.sin(t * 30 + i), (bot[1] - top[1]) * i / 10) for i in range(11)]
                d.line([(x, y) for x, y in pts], fill=(70, 40, 20, 235), width=5)
            if t > 3.0:
                steam(img, 190, 905, t, 0.7, int(55 * seg(t, 3.0, 4.0)), 0.2)

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.0 + 0.06 * f, 470, 900


# ---------------------------------------------------------------- 5/6 · oficina
class Office(Scene):
    tint = (0.97, 0.99, 1.03)
    glass = (206, 224, 250)
    light = (-1.0, -0.3)
    second = False

    def build(self):
        bg = vgrad([(0, (206, 200, 192)), (0.69, (186, 180, 172)), (0.691, (150, 118, 86)), (1, (110, 84, 60))])
        far, pen = big()
        pen.rect(680, 200, 1040, 760, fill=(230, 232, 236, 255), r=4)
        pen.rect(696, 216, 1024, 744, fill=(236, 240, 244, 255))
        for y in range(226, 744, 22):
            pen.line([(696, y), (1024, y)], (206, 208, 212, 255), 7)
        pen.rect(40, 330, 420, 346, fill=(130, 100, 74, 255))
        rng = random.Random(5)
        x = 50
        while x < 400:
            w = rng.uniform(16, 30)
            h = rng.uniform(70, 110)
            c = rng.choice([(120, 60, 50), (60, 80, 110), (180, 160, 120), (70, 100, 80), (150, 140, 130)])
            pen.rect(x, 330 - h, x + w, 330, fill=c + (255,))
            x += w + 3
        pen.rect(820, 1000, 1060, 1325, fill=(170, 140, 110, 255))
        pen.rect(870, 880, 990, 1000, fill=(40, 40, 44, 255), r=10)
        pen.rect(890, 950, 970, 996, fill=(24, 24, 26, 255), r=4)
        far = small(far).filter(ImageFilter.GaussianBlur(4))
        bg.alpha_composite(far)
        bg = add_light(bg, 860, 480, 480, (255, 250, 240), 0.3)
        near, pen = big()
        planks(pen, 0, 1325, 1080, 1920, (110, 84, 60, 130), 9, 9)
        pen.rect(410, 630, 670, 1060, fill=(32, 32, 36, 255), r=60)
        pen.rect(424, 646, 656, 1044, fill=(44, 44, 50, 255), r=52)
        pen.rect(400, 1062, 680, 1100, fill=(30, 30, 34, 255), r=12)
        pen.rect(530, 1100, 550, 1400, fill=(70, 70, 76, 255))
        for a in (-160, -100, -20, 40, 100):
            e = V(540, 1420) + V(math.cos(math.radians(a)) * 170, math.sin(math.radians(a)) * 30 + 30)
            pen.line([V(540, 1410), e], (40, 40, 44, 255), 14)
            pen.circle(e + V(0, 16), 12, fill=(20, 20, 22, 255))
        near = small(near)
        bg.alpha_composite(near)
        soft_shadow(bg, 540, 1520, 300, 30, 90, 16)
        self.bg = bg
        fg, pen = big()
        pen.poly([(20, 838), (1060, 838), (1080, 905), (0, 905)], (178, 142, 106, 255))
        pen.rect(0, 905, 1080, 932, fill=(138, 106, 76, 255))
        pen.line([(0, 906), (1080, 906)], (204, 172, 136, 255), 2)
        for x in (36, 1044):
            pen.rect(x - 9, 932, x + 9, 1590, fill=(34, 34, 36, 255))
        # monitor principal (a la izquierda, girado hacia el personaje)
        pen.rect(206, 790, 236, 850, fill=(50, 50, 54, 255))
        pen.ellipse((221, 852), 70, 12, fill=(44, 44, 48, 255))
        scr = [(24, 530), (392, 586), (392, 806), (24, 862)]
        pen.poly(scr, (20, 20, 24, 255))
        self.scr = [(36, 546), (380, 596), (380, 796), (36, 846)]
        pen.poly(self.scr, (34, 46, 66, 255))

        def quad(u0, v0, u1, v1, col):
            q = self.scr

            def at(u, v):
                top = lerp(V(*q[0]), V(*q[1]), u)
                bot = lerp(V(*q[3]), V(*q[2]), u)
                return lerp(top, bot, v)
            pen.poly([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)], col)
        quad(0.04, 0.08, 0.55, 0.9, (226, 232, 240, 255))
        quad(0.6, 0.08, 0.96, 0.5, (90, 130, 190, 255))
        quad(0.6, 0.56, 0.96, 0.9, (220, 226, 236, 255))
        for i in range(8):
            quad(0.08, 0.16 + i * 0.09, 0.08 + (0.3 + 0.15 * ((i * 7) % 3)), 0.19 + i * 0.09, (150, 160, 176, 255))
        if self.second:
            pen.rect(866, 790, 892, 846, fill=(50, 50, 54, 255))
            pen.ellipse((879, 850), 60, 10, fill=(44, 44, 48, 255))
            s2 = [(700, 600), (1050, 560), (1050, 836), (700, 806)]
            pen.poly(s2, (20, 20, 24, 255))
            self.scr2 = [(712, 612), (1038, 574), (1038, 824), (712, 796)]
            pen.poly(self.scr2, (40, 54, 76, 255))
            pen.poly([(728, 630), (1020, 596), (1020, 700), (728, 720)], (210, 220, 234, 255))
            pen.rect(820, 868, 900, 884, fill=(20, 20, 22, 255), r=5)
            pen.rect(826, 870, 894, 882, fill=(120, 170, 240, 255), r=3)
        pen.poly([(436, 864), (660, 864), (672, 892), (424, 892)], (54, 54, 58, 255))
        for r in range(3):
            for c in range(12):
                x = 444 + c * 18 + r * 2
                pen.rect(x, 868 + r * 8, x + 13, 873 + r * 8, fill=(84, 84, 90, 255), r=1)
        fg = small(fg)
        cups = [(110, 860, 70), (318, 852, 66), (770, 858, 70), (990, 850, 72)] if not self.second else \
            [(110, 860, 70), (318, 852, 66), (990, 850, 72), (680, 846, 60)]
        for (x, y, w) in cups:
            put_mug(fg, (x, y - w * 0.3), w, 0.0, (232, 230, 226), stain=True)
        self.fg = fg
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon([(380, 832), (780, 832), (780, 912), (380, 912)], fill=255)
        self.over_mask = np.asarray(m.filter(ImageFilter.GaussianBlur(3))).astype(np.uint16)
        g = light_layer(300, 690, 420, (150, 190, 255), 0.18)
        g.alpha_composite(vignette(0.55))
        self.grade = g

    def front(self, img, t, p):
        a = int(18 + 14 * math.sin(t * 1.3) + 8 * math.sin(t * 3.1))
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lay).polygon(self.scr, fill=(200, 225, 255, max(0, a)))
        if self.second:
            ImageDraw.Draw(lay).polygon(self.scr2, fill=(200, 225, 255, max(0, a - 6)))
        img.alpha_composite(lay)
        if getattr(self, "_mug", None) is not None:
            steam(img, self._mug[0], self._mug[1] - 34, t, 0.8, 55, 0.3)


class S5(Office):
    def pose(self, t):
        p = seated()
        p["head"] = V(506, 492)
        p["head_rot"] = -9 + 2 * math.sin(t * 0.7)
        p["gaze"] = V(-0.85, 0.15)
        p["N"] = V(528, 662)
        p["shL"], p["shR"] = V(388, 690), V(672, 696)
        typing = 0.0 if 2.4 < t < 3.4 else 1.0
        tap = abs(math.sin(t * 8.5)) * typing
        p["elL"] = V(358, 886)
        p["wrL"] = V(444, 882 - 3 * tap)
        p["handL"] = (10, 0.33 + 0.16 * tap, 1.0)
        sip = seg(t, 3.0, 4.0) * (1 - seg(t, 4.9, 5.8))
        p["elR"] = lerp(V(738, 892), V(722, 830), sip)
        p["wrR"] = lerp(V(690, 802), V(612, 642), sip)
        p["handR"] = (196, 0.66, 0.9)
        m = p["wrR"] + V(-52, -14)
        p["held"] = [(*mug(100, 0.7), m, 6 - 10 * sip, "R")]
        self._mug = m
        p["breath"] = 0.01 * math.sin(t * 2 * math.pi / 4)
        return p

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.06, 570 - 50 * f, 920


class S6(Office):
    second = True

    def pose(self, t):
        p = seated()
        look = seg(t, 1.6, 2.6) * (1 - seg(t, 3.8, 4.8))
        p["head"] = V(530 - 14 * look, 488)
        p["head_rot"] = lerp(7, -7, look)
        p["gaze"] = V(lerp(0.85, -0.7, look), 0.12)
        p["N"] = V(536, 660)
        p["shL"], p["shR"] = V(392, 674), V(686, 672)
        p["elL"] = V(366, 874)
        p["wrL"] = V(452, 852 + 2 * math.sin(t * 1.1))
        p["handL"] = (12, 0.3 + 0.07 * noise(t, 1, 3.0), 1.1)
        p["elR"] = V(740, 884)
        p["wrR"] = V(692, 748)
        p["handR"] = (196, 0.66, 0.9)
        m = p["wrR"] + V(-52, -14)
        p["held"] = [(*mug(92, 0.5), m, 4, "R")]
        self._mug = m
        p["breath"] = 0.008 * math.sin(t * 2 * math.pi / 3)
        return p

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.06, 560 - 40 * f, 900


# ---------------------------------------------------------------- 7-10 · salón de noche
class Living(Scene):
    tint = (1.0, 0.93, 0.84)
    glass = (255, 214, 170)
    light = (1.0, -0.4)
    cup_on_table = True
    shards = False

    def build(self):
        bg = vgrad([(0, (58, 46, 40)), (0.65, (40, 32, 28)), (0.651, (44, 32, 26)), (1, (26, 20, 16))])
        far, pen = big()
        pen.rect(40, 300, 330, 880, fill=(30, 34, 46, 255), r=4)
        pen.rect(54, 314, 316, 866, fill=(18, 26, 46, 255))
        rng = random.Random(8)
        for _ in range(40):
            x, y = rng.uniform(60, 310), rng.uniform(600, 860)
            pen.circle((x, y), rng.uniform(2, 5), fill=(255, rng.randint(170, 230), 120, 200))
        pen.line([(185, 314), (185, 866)], (30, 34, 46, 255), 8)
        pen.rect(560, 320, 840, 560, fill=(30, 24, 20, 255), r=4)
        pen.rect(574, 334, 826, 546, fill=(96, 80, 64, 255))
        pen.circle((700, 440), 60, fill=(120, 100, 78, 255))
        far = small(far).filter(ImageFilter.GaussianBlur(3.5))
        bg.alpha_composite(far)
        near, pen = big()
        pen.ellipse((540, 1520), 560, 150, fill=(70, 52, 44, 255))
        pen.ellipse((540, 1520), 500, 120, outline=(90, 68, 54, 255), width=6)
        # lámpara de pie
        pen.ellipse((975, 1475), 70, 14, fill=(30, 26, 22, 255))
        pen.rect(970, 610, 980, 1475, fill=(40, 34, 28, 255))
        pen.poly([(905, 620), (1055, 620), (1030, 470), (930, 470)], (240, 170, 100, 255))
        # sofá
        sofa = (122, 106, 96, 255)
        pen.rect(40, 860, 1040, 1090, fill=sofa, r=30)
        pen.rect(60, 880, 540, 1080, fill=(132, 116, 104, 255), r=26)
        pen.rect(540, 880, 1020, 1080, fill=(132, 116, 104, 255), r=26)
        pen.rect(30, 940, 160, 1250, fill=(112, 96, 86, 255), r=26)
        pen.rect(920, 940, 1050, 1250, fill=(112, 96, 86, 255), r=26)
        pen.rect(150, 1066, 930, 1124, fill=(140, 124, 112, 255), r=14)
        pen.rect(150, 1118, 930, 1215, fill=(118, 102, 92, 255), r=8)
        pen.rect(40, 1215, 1040, 1245, fill=(70, 60, 54, 255), r=6)
        for x in (80, 1000):
            pen.rect(x - 8, 1245, x + 8, 1268, fill=(30, 24, 20, 255))
        near = small(near)
        bg.alpha_composite(near)
        bg = add_light(bg, 980, 560, 520, (255, 160, 80), 0.55)
        bg = add_light(bg, 190, 600, 300, (90, 120, 190), 0.15)
        soft_shadow(bg, 540, 1500, 200, 24, 120, 14)
        self.bg = bg
        fg, pen = big()
        pen.poly([(196, 1296), (704, 1296), (722, 1340), (178, 1340)], (88, 60, 42, 255))
        pen.line([(196, 1297), (704, 1297)], (130, 96, 70, 255), 2)
        pen.rect(178, 1340, 722, 1368, fill=(62, 42, 30, 255))
        for x in (200, 700):
            pen.rect(x - 9, 1368, x + 9, 1580, fill=(48, 32, 24, 255))
        fg = small(fg)
        soft_shadow(fg, 450, 1590, 300, 22, 90, 12)
        if self.cup_on_table:
            put_mug(fg, (598, 1286), 72, 0.6, (226, 222, 214))
        self.fg = fg
        g = light_layer(980, 600, 650, (255, 190, 120), 0.12)
        g.alpha_composite(vignette(0.78, 0.3, (8, 4, 2)))
        self.grade = g

    def base(self):
        p = seated()
        p["P"] = V(540, 1042)
        p["hipL"], p["hipR"] = V(465, 1074), V(615, 1074)
        p["knL"], p["knR"] = V(450, 1180), V(630, 1180)
        p["anL"], p["anR"] = V(446, 1480), V(634, 1480)
        p["toeL"], p["toeR"] = V(426, 1530), V(654, 1530)
        return p


SHARD_SEED = 11


def shard_state(tt):
    """Fragmentos de la taza: posición y ángulo de cada uno tt segundos después del impacto."""
    rng = random.Random(SHARD_SEED)
    out = []
    for i in range(15):
        vx = rng.uniform(-340, 340)
        vy = rng.uniform(-260, -60)
        depth = rng.uniform(-10, 70)
        size = rng.uniform(7, 19)
        spin = rng.uniform(-500, 500)
        n = rng.randint(3, 5)
        shape = [(rng.uniform(0.5, 1.0) * size, 2 * math.pi * j / n + rng.uniform(-0.3, 0.3)) for j in range(n)]
        T = rng.uniform(0.35, 0.7)
        tc = min(tt, T)
        f = tc / T
        x = vx * T * (1 - (1 - f) ** 2) / 2
        hop = max(0.0, -vy * tc - 0.5 * 2400 * tc * tc) if tt < T else 0.0
        y = depth * f - hop * 0.6
        ang = spin * T * (1 - (1 - f) ** 2) / 2
        out.append((x, y, ang, shape, size, rng.random()))
    return out


def draw_shards(img, origin, tt, alpha=1.0):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    sp = min(1.0, tt / 0.45) if tt > 0 else 0
    if sp > 0:
        rx, ry = 90 * sp, 20 * sp
        d.ellipse([origin[0] - rx, origin[1] + 8 - ry, origin[0] + rx, origin[1] + 8 + ry], fill=(40, 22, 12, int(210 * alpha)))
    for (x, y, ang, shape, size, r) in shard_state(tt):
        c = V(origin[0] + x, origin[1] + 6 + y)
        pts = [tuple(c + rotv(V(math.cos(a) * rr, math.sin(a) * rr * 0.6), ang)) for rr, a in shape]
        col = (236, 232, 222) if r > 0.3 else (200, 196, 188)
        d.polygon(pts, fill=col + (int(255 * alpha),), outline=(120, 110, 100, int(255 * alpha)))
    img.alpha_composite(lay)


class S7(Living):
    def pose(self, t):
        p = self.base()
        p["N"] = V(540, 640)
        p["shL"], p["shR"] = V(394, 652), V(686, 652)
        turn = seg(t, 0.5, 3.5)
        p["head"] = V(540 + 6 * turn, 456)
        p["head_rot"] = lerp(-3, 7, turn)
        p["gaze"] = V(0.25 + 0.2 * turn, 0.9)
        tr = lambda s: V(math.sin(t * 2 * math.pi * 7.3 + s) * 2.2, math.sin(t * 2 * math.pi * 6.1 + s * 2) * 1.8)
        p["elL"] = V(352, 876)
        p["wrL"] = V(392, 1040) + tr(0)
        p["handL"] = (74, 0.48 + 0.06 * math.sin(t * 2 * math.pi * 7.7), 1.25)
        p["elR"] = V(728, 876)
        p["wrR"] = V(690, 1040) + tr(1.3)
        p["handR"] = (106, 0.48 + 0.06 * math.sin(t * 2 * math.pi * 7.1 + 1), 1.25)
        p["knL"], p["anL"], p["toeL"] = V(448, 1196), V(438, 1500), V(418, 1556)
        p["knR"], p["anR"], p["toeR"] = V(632, 1160), V(648, 1424), V(668, 1462)
        p["breath"] = 0.016 * math.sin(t * 2 * math.pi / 2.6)
        return p

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.0 + 0.07 * f, 540, 900


class S8(Living):
    def pose(self, t):
        p = self.base()
        rise = seg(t, 0.3, 2.5)
        p["N"] = V(540, 652 - 4 * rise)
        p["shL"], p["shR"] = V(394, 670 - 6 * rise), V(686, 670 - 6 * rise)
        p["head"] = V(540, 492 - 12 * rise)
        p["head_rot"] = 0
        p["gaze"] = V(0, -0.05)
        p["pupil"] = 1.35
        place = seg(t, 0.0, 1.4)
        p["elL"] = lerp(V(360, 900), V(374, 902), place)
        p["wrL"] = lerp(V(390, 1040), V(470, 792), place)
        p["handL"] = (lerp(70, -26, place), 0.25 + 0.3 * seg(t, 1.5, 3.0) + 0.04 * math.sin(t * 9), 1.1)
        p["elR"] = V(722, 906)
        p["wrR"] = V(770, 1082)
        p["handR"] = (82, 0.36 + 0.1 * seg(t, 1.5, 3.0), 1.0)
        p["breath"] = 0.03 * math.sin(t * 2 * math.pi / 3.2) * seg(t, 0.8, 1.6)
        return p

    def camera(self, t):
        f = ease(t / self.dur)
        return 1.04 + 0.06 * f, 540, 820


class S9(Living):
    cup_on_table = False
    t_rel = 1.35
    g = 2600.0
    y0 = 1206.0
    floor = 1540.0

    def t_imp(self):
        return self.t_rel + math.sqrt(2 * (self.floor - self.y0) / self.g)

    def pose(self, t):
        p = self.base()
        lean = seg(t - self.t_rel, 0, 0.9) if t > self.t_rel else 0
        p["N"] = V(556 + 6 * lean, 664 + 4 * lean)
        p["shL"], p["shR"] = V(412 + 6 * lean, 682 + 4 * lean), V(700 + 6 * lean, 694 + 6 * lean)
        p["head"] = V(566 + 8 * lean, 500 + 8 * lean)
        p["head_rot"] = 8 + 5 * lean
        p["gaze"] = V(0.2, 0.3)
        p["pupil"] = 1.35
        p["elL"] = V(390, 904)
        p["wrL"] = V(484, 796)
        p["handL"] = (-24, 0.55, 1.1)
        p["elR"] = V(744 + 4 * lean, 906 + 6 * lean)
        p["wrR"] = V(790 + 4 * lean, 1122 + 14 * lean)
        opn = seg(t, 0.9, self.t_rel + 0.1)
        p["handR"] = (92, lerp(0.66, 0.04, opn), lerp(1.0, 1.4, opn))
        if t < self.t_rel:
            p["held"] = [(*mug(78, 0.4), p["wrR"] + V(0, 84), 0, "R")]
        p["breath"] = 0.02 * abs(math.sin(t * 2 * math.pi * 1.4))
        return p

    def front(self, img, t, p):
        ti = self.t_imp()
        if self.t_rel <= t < ti:
            dt = t - self.t_rel
            y = self.y0 + 0.5 * self.g * dt * dt
            put_mug(img, (792, y), 78, 0.4, angle=150 * dt * dt * 2, shadow=False)
        elif t >= ti:
            draw_shards(img, V(792, self.floor + 30), t - ti)

    def camera(self, t):
        sh = 0.0
        ti = self.t_imp()
        if t > ti:
            sh = 3.0 * math.exp(-(t - ti) * 9) * math.sin((t - ti) * 70)
        return 1.06, 560 + sh, 900 + sh


class S10(Living):
    cup_on_table = False
    fade_out = 0.0
    t_beat = 1.4

    def pose(self, t):
        p = self.base()
        p["N"] = V(548, 664)
        p["shL"], p["shR"] = V(404, 684), V(694, 690)
        p["head"] = V(550, 504)
        p["head_rot"] = 4
        p["gaze"] = V(0.05, 0.12)
        p["pupil"] = 1.4
        p["elL"], p["wrL"], p["handL"] = V(380, 906), V(374, 1112), (92, 0.14, 1.0)
        p["elR"], p["wrR"], p["handR"] = V(716, 908), V(724, 1114), (88, 0.14, 1.0)
        p["breath"] = 0.014 * math.sin(t * 2 * math.pi / 4.0)
        return p

    def glass_strength(self, t):
        return 1.0 + 0.7 * math.exp(-((t - self.t_beat) / 0.12) ** 2)

    def front(self, img, t, p):
        draw_shards(img, V(792, S9.floor + 30), 5.0)

    def camera(self, t):
        f = ease(t / self.dur) * 0.6 + 0.4 * (t / self.dur)
        return 1.0 + 0.3 * f, 548, 700


class S11(Scene):
    fade_in = 0.8
    fade_out = 0.6

    def build(self):
        self.bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        self.fg = None
        self.grade = None

    def overlay(self, img, t):
        d = ImageDraw.Draw(img, "RGBA")
        a = ease((t - 0.4) / 0.9)
        f = mv.font(74)
        lines = self.spec["titulo"].split("\n")
        y = 700
        for i, line in enumerate(lines):
            tw = d.textlength(line, font=f)
            col = (255, 255, 255) if i < len(lines) - 1 else (244, 196, 92)
            d.text(((W - tw) / 2, y + i * 100), line, font=f, fill=col + (int(255 * a),))
        a2 = ease((t - 1.6) / 0.9)
        bw = 90 * a2
        d.rounded_rectangle([W / 2 - bw, y + len(lines) * 100 + 25, W / 2 + bw, y + len(lines) * 100 + 30], 2, fill=(244, 196, 92, int(230 * a2)))
        f2 = mv.font(44, bold=False)
        tw = d.textlength(self.spec["texto"], font=f2)
        d.text(((W - tw) / 2, y + len(lines) * 100 + 65), self.spec["texto"], font=f2, fill=(230, 230, 230, int(255 * a2)))


CLASSES = {1: S1, 2: S2, 3: S3, 4: S4, 5: S5, 6: S6, 7: S7, 8: S8, 9: S9, 10: S10, 11: S11}


# ====================================================================== audio
def note_f(m):
    return 440 * 2 ** ((m - 69) / 12)


def ambient(dur, tension):
    """Pad oscuro y lento. tension(t) en [0,1] añade disonancia y graves."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [52, 55, 59]]
    L = 6.0
    for i in range(int(dur / L) + 2):
        t0 = i * L - 1.5
        a, b = max(0, int(t0 * SR)), min(n, int((t0 + L + 3) * SR))
        if a >= b:
            continue
        tt = t[a:b] - t0
        env = np.sin(np.clip(tt / (L + 3), 0, 1) * np.pi) ** 1.5
        for m in prog[i % 4]:
            f = note_f(m)
            out[a:b] += (np.sin(2 * np.pi * f * t[a:b]) + 0.5 * np.sin(2 * np.pi * f * 1.004 * t[a:b])
                         + 0.15 * np.sin(2 * np.pi * 2 * f * t[a:b])) * env * 0.035
    lfo = 0.7 + 0.3 * np.sin(2 * np.pi * t / 9)
    out += (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.4 * t)) * 0.05 * lfo
    tens = np.array([tension(x) for x in t[::441]])
    tens = np.interp(np.arange(n), np.arange(0, n, 441)[: len(tens)], tens)
    out += np.sin(2 * np.pi * note_f(58) * t) * 0.03 * tens * (0.6 + 0.4 * np.sin(2 * np.pi * t / 3.1))
    out += np.sin(2 * np.pi * 41.2 * t) * 0.09 * tens
    out *= np.minimum(1, t / 2.5)
    return out


def heartbeat(buf, t0, gain):
    for off, f, g in ((0.0, 52, 1.0), (0.26, 64, 0.7)):
        a = int((t0 + off) * SR)
        m = int(0.22 * SR)
        if a < 0 or a + m > len(buf):
            continue
        tt = np.arange(m) / SR
        env = (1 - np.exp(-tt * 300)) * np.exp(-tt * 22)
        buf[a:a + m] += np.sin(2 * np.pi * f * tt * (1 - 0.3 * tt)) * env * gain * g


def crash(buf, t0, gain=0.6):
    rng = np.random.default_rng(4)
    a = int(t0 * SR)
    m = int(1.2 * SR)
    tt = np.arange(m) / SR
    nz = rng.normal(0, 1, m)
    hp = np.diff(nz, prepend=0)
    s = hp * np.exp(-tt * 18) * 0.5 + nz * np.exp(-tt * 40) * 0.3
    for _ in range(26):
        st = rng.uniform(0, 0.5)
        f = rng.uniform(2500, 7000)
        e = np.exp(-np.clip(tt - st, 0, None) * rng.uniform(30, 60)) * (tt >= st)
        s += np.sin(2 * np.pi * f * tt) * e * rng.uniform(0.05, 0.2)
    s[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    e = min(len(buf), a + m)
    buf[a:e] += s[: e - a] * gain


def pour(buf, t0, t1, gain=0.06):
    rng = np.random.default_rng(2)
    a, b = int(t0 * SR), int(t1 * SR)
    nz = rng.normal(0, 1, b - a)
    br = np.cumsum(nz)
    br -= np.convolve(br, np.ones(400) / 400, mode="same")
    br /= (np.abs(br).max() + 1e-9)
    env = np.minimum(1, np.arange(b - a) / (0.2 * SR)) * np.minimum(1, (b - a - np.arange(b - a)) / (0.3 * SR))
    buf[a:b] += br * env * gain


def tick(buf, t0, t1, gain=0.05):
    x = t0
    while x < t1:
        a = int(x * SR)
        m = int(0.02 * SR)
        tt = np.arange(m) / SR
        if a + m < len(buf):
            buf[a:a + m] += np.sin(2 * np.pi * 3200 * tt) * np.exp(-tt * 400) * gain
        x += 1.0


# ====================================================================== montaje
def render_segment(args):
    sid, spec, dur, vdur, vat, out, frames = args
    random.seed(sid)
    sc = CLASSES[sid](spec, dur, vdur, vat)
    if frames:
        for t in frames:
            sc.frame(t).save(out.replace(".mp4", f"_{t:.1f}.png"))
        return out
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(dur * FPS))
    for i in range(n):
        ff.stdin.write(sc.frame(i / FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    print(f"  escena {sid} lista ({dur:.1f}s)", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion", nargs="?", default=os.path.join(ROOT, "videos", "esqueleto_cafe.json"))
    ap.add_argument("-o", "--salida")
    ap.add_argument("--solo", type=int, help="renderiza solo fotogramas de prueba de esta escena")
    ap.add_argument("--tiempos", default="1.0,3.0", help="tiempos de prueba (con --solo)")
    ap.add_argument("--dir", help="carpeta para fotogramas de prueba")
    a = ap.parse_args()
    spec = json.load(open(a.guion, encoding="utf-8"))
    out = a.salida or os.path.splitext(a.guion)[0] + ".mp4"
    tmp = tempfile.mkdtemp(prefix="esq_")
    try:
        voice_model = spec.get("voz_modelo", mv.DEFAULT_PIPER)
        speed = spec.get("velocidad_voz", 150)
        jobs, starts, vinfo = [], [], []
        t = 0.0
        for sc in spec["escenas"]:
            sid = sc["id"]
            vdur = 0.0
            wav = os.path.join(tmp, f"v{sid}.wav")
            if sc.get("voz") and not a.solo:
                vdur = mv.tts(sc["voz"], spec.get("idioma", "es"), speed, wav, voice_model)
            elif sc.get("voz"):
                vdur = 0.06 * len(sc["voz"])
            vat = {9: 0.3, 11: 1.0}.get(sid, 0.55)
            dur = {9: 4.4, 10: 5.6}.get(sid, max(5.4, vat + vdur + 1.1))
            jobs.append((sid, sc, dur, vdur, vat, os.path.join(tmp, f"s{sid:02d}.mp4"), None))
            starts.append(t)
            vinfo.append((wav, vdur, vat))
            t += dur
        total = t
        if a.solo:
            j = jobs[a.solo - 1]
            d = a.dir or tmp
            ts = [float(x) for x in a.tiempos.split(",")]
            render_segment((j[0], j[1], j[2], j[3], j[4], os.path.join(d, f"s{a.solo:02d}.mp4"), ts))
            return
        print(f"Duración total: {total:.1f}s; renderizando {len(jobs)} escenas…", flush=True)
        order = sorted(jobs, key=lambda j: -j[2])
        with Pool(min(4, os.cpu_count() or 2)) as pool:
            list(pool.imap_unordered(render_segment, order))
        lst = os.path.join(tmp, "lista.txt")
        with open(lst, "w") as fh:
            for j in jobs:
                fh.write(f"file '{j[5]}'\n")
        vid = os.path.join(tmp, "video.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid],
                       check=True)
        # ------------------------------------------------ audio
        buf = np.zeros(int((total + 0.5) * SR))
        voice = np.zeros_like(buf)
        for st, (wav, vdur, vat) in zip(starts, vinfo):
            if vdur:
                v = mv.read_wav(wav)
                a0 = int((st + vat) * SR)
                voice[a0:a0 + len(v)] += v[: len(buf) - a0]
        s = dict(zip([j[0] for j in jobs], starts))
        d = dict(zip([j[0] for j in jobs], [j[2] for j in jobs]))
        end10 = s[10] + d[10]

        def tension(x):
            return float(np.clip((x - s[5]) / (s[7] - s[5] + 1e-9), 0, 1) * 0.5 + np.clip((x - s[7]) / (s[9] - s[7]), 0, 1) * 0.5)
        amb = ambient(end10, tension)
        buf[: len(amb)] += amb * 0.9
        tick(buf, s[3] + 0.3, s[3] + d[3] - 0.3, 0.05)
        pour(buf, s[4] + 2.2, s[4] + d[4] - 0.6, 0.05)
        x, bpm = s[7] + 0.8, 98
        while x < s[9] + S9.t_rel + 0.4:
            g = 0.25 + 0.3 * (x - s[7]) / (s[9] - s[7] + 1)
            heartbeat(buf, x, g)
            bpm = min(132, bpm + 2.2)
            x += 60 / bpm * (1.35 if (x > s[8] and random.random() < 0.18) else 1.0)
        sc9 = S9(spec["escenas"][8], d[9], 0, 0)
        crash(buf, s[9] + sc9.t_imp(), 0.55)
        heartbeat(buf, s[10] + S10.t_beat, 0.75)
        buf[int(end10 * SR):] = 0
        tail = np.arange(len(buf) - int(s[11] * SR)) / SR
        buf[int(s[11] * SR):] += np.sin(2 * np.pi * 110 * tail) * 0.03 * np.minimum(1, tail / 2) * np.minimum(1, (d[11] - tail) / 1.5).clip(0)
        mix = buf * 0.8 + voice * 1.0
        peak = np.abs(mix).max() or 1
        mix = mix / peak * 0.92
        awav = os.path.join(tmp, "audio.wav")
        mv.write_wav(awav, mix[: int(total * SR)])
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", awav, "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
        print(f"Vídeo listo: {out} ({total:.1f}s)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
