"""El piloto misterioso de la serie: casco negro con visera bajada, ojos verdes encendidos,
brazos cruzados, luz de contorno y aura de energía verde. Dibujado con Pillow + numpy."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

K = 3
CW, CH = 820, 1120
GREEN = (0, 255, 136)


def S(pts):
    return [(x * K, y * K) for x, y in pts]


def catmull(pts, n=10):
    out = []
    P = pts + pts[:3]
    for i in range(len(pts)):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for k in range(n):
            s = k / n
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * s + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * s * s
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * s ** 3) for j in (0, 1)))
    return out


TORSO = [(410, 392), (575, 404), (690, 455), (742, 548), (748, 720), (722, 920), (690, 1130), (130, 1130),
         (98, 920), (72, 720), (78, 548), (130, 455), (245, 404)]
HELMET = (290, 96, 530, 392)


def vgrad(w, h, c1, c2, p0=0.0, p1=1.0):
    y = np.clip((np.linspace(0, 1, h)[:, None] - p0) / (p1 - p0), 0, 1)
    c = np.array(c1) * (1 - y) + np.array(c2) * y
    a = np.zeros((h, w, 4), np.uint8)
    a[..., :3] = c[:, None, :]
    a[..., 3] = 255
    return Image.fromarray(a, "RGBA")


def fill(im, mask, src):
    im.paste(src, (0, 0), mask)


@lru_cache(maxsize=2)
def base():
    """Cuerpo sin ojos (cacheado): devuelve (imagen, máscara de silueta)."""
    w, h = CW * K, CH * K
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    m_body = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m_body).polygon(S(catmull(TORSO, 12)), fill=255)
    fill(im, m_body, vgrad(w, h, (34, 38, 40), (8, 9, 10), 0.3, 0.95))
    d = ImageDraw.Draw(im)
    # paneles del mono: hombros verdes oscuros y franjas brillantes
    for sgn in (-1, 1):
        x0 = 410 + sgn * 70
        x1 = 410 + sgn * 300
        d.line(S([(x0, 410), (410 + sgn * 210, 432), (x1, 520)]), fill=(0, 120, 64), width=26 * K, joint="curve")
        d.line(S([(x0, 404), (410 + sgn * 210, 426), (x1, 512)]), fill=(0, 230, 120), width=5 * K, joint="curve")
        # costura brazo / torso
        d.line(S([(410 + sgn * 222, 470), (410 + sgn * 232, 600), (410 + sgn * 226, 700)]), fill=(0, 0, 0), width=5 * K,
               joint="curve")
        d.line(S([(410 + sgn * 216, 470), (410 + sgn * 226, 600), (410 + sgn * 220, 700)]), fill=(52, 58, 60),
               width=2 * K, joint="curve")
    # cuello alto
    d.rounded_rectangle(S([(330, 352), (490, 430)]), 30 * K, fill=(14, 15, 16), outline=(0, 0, 0), width=4 * K)
    d.line(S([(338, 396), (482, 396)]), fill=(0, 200, 110), width=3 * K)
    # emblema en el pecho
    d.ellipse(S([(520, 500), (588, 568)]), outline=(0, 230, 120), width=4 * K)
    d.text((554 * K, 534 * K), "30", fill=(0, 230, 120), anchor="mm",
           font=__import__("PIL.ImageFont", fromlist=["x"]).truetype(
               "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf", 30 * K))
    # brazos cruzados: antebrazo inferior y superior
    lower = [(668, 772), (230, 708)]
    upper = [(150, 740), (585, 676)]
    for seg, shade in ((lower, (20, 22, 24)), (upper, (30, 33, 35))):
        d.line(S(seg), fill=(0, 0, 0), width=136 * K)
        for p in seg:
            r = 68 * K
            d.ellipse((p[0] * K - r, p[1] * K - r, p[0] * K + r, p[1] * K + r), fill=(0, 0, 0))
        d.line(S(seg), fill=shade, width=122 * K)
        for p in seg:
            r = 61 * K
            d.ellipse((p[0] * K - r, p[1] * K - r, p[0] * K + r, p[1] * K + r), fill=shade)
        # brillo superior del antebrazo
        (ax, ay), (bx, by) = seg
        d.line(S([(ax, ay - 46), (bx, by - 46)]), fill=(64, 70, 72), width=6 * K)
        # puño del guante + franja verde
        cx, cy = seg[1] if seg is upper else seg[1]
    # guante visible (mano del brazo superior asomando sobre el bíceps derecho)
    gx, gy = 600, 674
    d.ellipse(S([(gx - 58, gy - 52), (gx + 58, gy + 52)]), fill=(0, 0, 0))
    d.ellipse(S([(gx - 50, gy - 45), (gx + 50, gy + 45)]), fill=(26, 28, 30))
    for i in range(3):
        d.arc(S([(gx - 30 + i * 22, gy - 34), (gx - 8 + i * 22, gy - 10)]), 200, 340, fill=(0, 220, 116), width=3 * K)
    # puño de la manga
    for (px, py) in ((540, 682), (268, 712)):
        d.line(S([(px, py - 58), (px + 6, py + 58)]), fill=(0, 170, 92), width=10 * K)
    # casco
    m_h = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m_h).ellipse(S([HELMET[:2], HELMET[2:]]), fill=255)
    hel = vgrad(w, h, (46, 50, 54), (6, 7, 8), 0.06, 0.35)
    fill(im, m_h, hel)
    d = ImageDraw.Draw(im)
    d.ellipse(S([HELMET[:2], HELMET[2:]]), outline=(0, 0, 0), width=5 * K)
    # reflejo especular del casco
    d.arc(S([(318, 120), (470, 270)]), 200, 255, fill=(150, 160, 168), width=7 * K)
    d.arc(S([(330, 130), (460, 260)]), 205, 235, fill=(220, 228, 234), width=3 * K)
    # filete verde central
    d.line(S([(410, 98), (410, 180)]), fill=(0, 220, 116), width=6 * K)
    # visera bajada
    vis = [(304, 222), (330, 192), (410, 182), (490, 192), (516, 222), (510, 296), (470, 318), (350, 318), (310, 296)]
    m_v = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m_v).polygon(S(catmull(vis, 8)), fill=255)
    fill(im, m_v, vgrad(w, h, (4, 30, 22), (0, 0, 0), 0.17, 0.29))
    d = ImageDraw.Draw(im)
    d.line(S(catmull(vis, 8) + [catmull(vis, 8)[0]]), fill=(0, 0, 0), width=6 * K)
    # reflejo verde horizontal en la visera
    d.line(S([(318, 212), (500, 212)]), fill=(0, 140, 80), width=3 * K)
    # mentonera y tomas de aire
    for i in (-1, 0, 1):
        d.rounded_rectangle(S([(410 + i * 34 - 10, 336), (410 + i * 34 + 10, 368)]), 6 * K, fill=(0, 0, 0))
    for sx in (300, 520):
        d.ellipse(S([(sx - 14, 246), (sx + 14, 274)]), fill=(70, 76, 80), outline=(0, 0, 0), width=3 * K)

    out = im.resize((CW, CH), Image.LANCZOS)
    sil = out.getchannel("A")
    # luz de contorno: verde a la izquierda, blanca-verdosa a la derecha
    rimL = ImageChops.subtract(sil, ImageChops.offset(sil, 7, 2))
    rimR = ImageChops.subtract(sil, ImageChops.offset(sil, -6, 2))
    for rm, col in ((rimL, GREEN), (rimR, (180, 255, 220))):
        lay = Image.new("RGBA", (CW, CH), col + (0,))
        lay.putalpha(rm.filter(ImageFilter.GaussianBlur(1.5)))
        out.alpha_composite(lay)
    return out, sil


@lru_cache(maxsize=32)
def figure(eye_q, glint_q):
    """eye_q 0..8 intensidad de los ojos; glint_q −1 (sin destello) o 0..15 posición del destello."""
    im, sil = base()
    im = im.copy()
    e = eye_q / 8
    if e > 0:
        lay = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        # ojos rasgados y ceñudos tras la visera
        for sgn in (-1, 1):
            cx = 410 + sgn * 46
            pts = [(cx - sgn * 30, 262), (cx + sgn * 34, 246), (cx + sgn * 30, 258), (cx - sgn * 26, 274)]
            d.polygon(pts, fill=GREEN + (int(255 * e),))
        glow = lay.filter(ImageFilter.GaussianBlur(14))
        for _ in range(2):
            im.alpha_composite(glow)
        core = lay.copy()
        ImageDraw.Draw(core)
        im.alpha_composite(lay)
        dd = ImageDraw.Draw(im)
        for sgn in (-1, 1):
            cx = 410 + sgn * 46
            dd.line([(cx - sgn * 22, 264), (cx + sgn * 26, 252)], fill=(230, 255, 240, int(255 * e)), width=3)
    if glint_q >= 0:
        # destello que barre la visera
        p = glint_q / 15
        x = 290 + p * 260
        lay = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        ImageDraw.Draw(lay).polygon([(x - 18, 180), (x + 8, 180), (x - 22, 320), (x - 48, 320)], fill=(255, 255, 255, 150))
        vm = Image.new("L", (CW, CH), 0)
        ImageDraw.Draw(vm).ellipse((300, 182, 520, 322), fill=255)
        lay.putalpha(ImageChops.multiply(lay.getchannel("A"), vm))
        im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(2)))
    return im


# ------------------------------------------------------------ aura
_AURA = {}


def _aura_static():
    if not _AURA:
        _, sil = base()
        q = 4
        small = sil.resize((CW // q, CH // q), Image.BILINEAR)
        m = np.asarray(small, np.float32) / 255
        dil = np.asarray(small.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10)), np.float32) / 255
        far = np.asarray(small.filter(ImageFilter.GaussianBlur(26)), np.float32) / 255
        rng = np.random.default_rng(5)
        hgt = CH // q * 3
        n = np.zeros((hgt, CW // q), np.float32)
        for sc, amp in ((3, 0.45), (7, 0.35), (16, 0.2)):
            r = rng.random((hgt // (sc * 3) + 2, CW // q // sc + 2)).astype(np.float32)
            n += amp * np.asarray(Image.fromarray((r * 255).astype(np.uint8)).resize((CW // q, hgt), Image.BICUBIC),
                                  np.float32) / 255
        _AURA.update(m=m, dil=dil, far=far, noise=n, q=q)
    return _AURA


def aura(t, power=1.0):
    A = _aura_static()
    q = A["q"]
    h, w = A["m"].shape
    off = int(t * 140 / q) % (A["noise"].shape[0] - h)
    nz = A["noise"][A["noise"].shape[0] - h - off: A["noise"].shape[0] - off]
    off2 = int(t * 90 / q) % (A["noise"].shape[0] - h)
    nz2 = A["noise"][off2: off2 + h, ::-1]
    flame = np.clip((nz * 0.6 + nz2 * 0.4) * 1.8 - 0.55, 0, 1) ** 1.3
    edge = np.clip(A["dil"] - A["m"] * 0.85, 0, 1)
    val = (edge * (0.4 + 1.6 * flame) + A["far"] * 0.35 * flame) * power
    val = np.clip(val, 0, 1)
    rgb = np.zeros((h, w, 4), np.uint8)
    core = np.clip(val * 1.4 - 0.6, 0, 1)
    rgb[..., 0] = (core * 200).astype(np.uint8)
    rgb[..., 1] = (np.clip(val * 1.3, 0, 1) * 255).astype(np.uint8)
    rgb[..., 2] = (90 + core * 140).clip(0, 255).astype(np.uint8)
    rgb[..., 3] = (val * 235).astype(np.uint8)
    return Image.fromarray(rgb, "RGBA").filter(ImageFilter.GaussianBlur(1.6)).resize((CW, CH), Image.BICUBIC)


@lru_cache(maxsize=1)
def rays(size=1600):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    for i in range(18):
        a = i / 18 * 2 * math.pi
        wdt = 0.05 + 0.04 * (i % 3)
        d.polygon([(c, c), (c + math.cos(a - wdt) * c, c + math.sin(a - wdt) * c),
                   (c + math.cos(a + wdt) * c, c + math.sin(a + wdt) * c)], fill=(0, 255, 136, 34))
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size, size), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(size / 6))
    im.putalpha(ImageChops.multiply(im.getchannel("A"), m))
    return im.filter(ImageFilter.GaussianBlur(6))


@lru_cache(maxsize=1)
def fog(w=1080, h=520):
    rng = np.random.default_rng(9)
    im = Image.new("RGBA", (w * 2, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x = rng.uniform(0, w * 2)
        y = rng.uniform(h * 0.35, h)
        rx, ry = rng.uniform(150, 380), rng.uniform(50, 120)
        d.ellipse((x - rx, y - ry, x + rx, y + ry), fill=(150, 210, 180, int(rng.uniform(18, 40))))
    im = im.filter(ImageFilter.GaussianBlur(40))
    # que sea cíclico
    a = np.asarray(im).copy()
    return Image.fromarray(a, "RGBA")
