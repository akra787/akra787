"""Motor de dibujo para «El último tren de la noche».

Utilidades de cairo, curvas de animación, ruido, y el posproceso cinematográfico
(gradación fría, niebla, grano, viñeta, parpadeo, aberración cromática).
"""
import math
import os
from contextlib import contextmanager

import cairo
import numpy as np

FORMATO = os.environ.get("FORMATO", "horizontal")
W, H, FPS = (1920, 1080, 24) if FORMATO == "horizontal" else (1080, 1920, 24)
HOR = W > H
KH = 0.6 if HOR else 1.0      # escala de personajes/objetos diseñados para el lienzo vertical
FCAM = 1.28 if HOR else 1.0   # focal de las cámaras 3D (panorámico: objetivo algo más largo)
AQUI = os.path.dirname(os.path.abspath(__file__))

TITULO = "Bebas Neue"
SANS = "Inter"
MAQ = "Courier Prime"
SERIF = "Noto Serif"


# ----------------------------------------------------------------- matemáticas
def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def pr(T, t0, d):
    """Progreso 0→1 de T entre t0 y t0+d."""
    return cl((T - t0) / d) if d > 0 else float(T >= t0)


def eo(x):
    return 1 - (1 - x) ** 3


def ei(x):
    return x ** 3


def eio(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ss(x):
    x = cl(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def lerpc(c1, c2, t):
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def hx(c, a=1.0):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


def mul(col, k, a=None):
    return (col[0] * k, col[1] * k, col[2] * k, col[3] if a is None else a)


def hash1(n):
    """Pseudoaleatorio determinista en [0,1)."""
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


def ruido1(x, semilla=0.0):
    """Ruido 1D suave (value noise) en [-1,1]."""
    i = math.floor(x)
    f = x - i
    a = hash1(i + semilla * 57.0)
    b = hash1(i + 1 + semilla * 57.0)
    u = f * f * (3 - 2 * f)
    return (a + (b - a) * u) * 2 - 1


def fbm1(x, semilla=0.0, oct=3):
    v, amp, fr = 0.0, 0.5, 1.0
    for k in range(oct):
        v += amp * ruido1(x * fr, semilla + k * 3.1)
        amp *= 0.5
        fr *= 2.03
    return v / 0.875


def parpadeo(T, semilla=0.0, intensidad=1.0, base=1.0):
    """Factor de luz de un fluorescente viejo: casi siempre encendido, con cortes."""
    v = base
    # microvibración
    v -= 0.04 * intensidad * (0.5 + 0.5 * math.sin(T * 2 * math.pi * 9.7 + semilla))
    # cortes rápidos esporádicos
    n = fbm1(T * 1.7, semilla)
    if n > 0.55:
        k = (n - 0.55) / 0.45
        tick = hash1(math.floor(T * 18) + semilla * 13)
        if tick < 0.35 + 0.5 * k:
            v -= intensidad * (0.45 + 0.5 * k)
    return cl(v, 0.05, 1.2)


# ----------------------------------------------------------------- cairo
def src(c, col):
    if len(col) == 4:
        c.set_source_rgba(*col)
    else:
        c.set_source_rgb(*col)


@contextmanager
def tf(c, x=0, y=0, s=1.0, r=0.0, a=1.0, sx=1.0, sy=1.0):
    c.save()
    c.translate(x, y)
    if r:
        c.rotate(r)
    fx, fy = s * sx, s * sy
    c.scale(fx if abs(fx) > 1e-4 else 1e-4, fy if abs(fy) > 1e-4 else 1e-4)
    grp = a < 0.999
    if grp:
        c.push_group()
    try:
        yield
    finally:
        if grp:
            c.pop_group_to_source()
            c.paint_with_alpha(max(0.0, a))
        c.restore()


def rr(c, x, y, w, h, r):
    r = max(0.01, min(r, w / 2, h / 2))
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()


def rect(c, x, y, w, h, col):
    c.rectangle(x, y, w, h)
    src(c, col)
    c.fill()


def lgrad(x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for o, col in stops:
        g.add_color_stop_rgba(o, *(col if len(col) == 4 else col + (1,)))
    return g


def rgrad(cx, cy, r0, r1, stops, cx1=None, cy1=None):
    g = cairo.RadialGradient(cx if cx1 is None else cx1, cy if cy1 is None else cy1, r0, cx, cy, r1)
    for o, col in stops:
        g.add_color_stop_rgba(o, *(col if len(col) == 4 else col + (1,)))
    return g


def resplandor(c, x, y, r, col, fuerza=1.0):
    """Halo de luz aditivo."""
    c.save()
    c.set_operator(cairo.OPERATOR_ADD)
    c.set_source(rgrad(x, y, 0, r, [(0, mul(col, 1, 0.55 * fuerza)), (0.25, mul(col, 1, 0.22 * fuerza)),
                                    (1, mul(col, 1, 0))]))
    c.arc(x, y, r, 0, 2 * math.pi)
    c.fill()
    c.restore()


def cono_luz(c, x, y, ancho_arriba, ancho_abajo, alto, col, fuerza=1.0):
    """Cono de luz volumétrico hacia abajo."""
    c.save()
    c.set_operator(cairo.OPERATOR_ADD)
    c.move_to(x - ancho_arriba / 2, y)
    c.line_to(x + ancho_arriba / 2, y)
    c.line_to(x + ancho_abajo / 2, y + alto)
    c.line_to(x - ancho_abajo / 2, y + alto)
    c.close_path()
    c.set_source(lgrad(x, y, x, y + alto, [(0, mul(col, 1, 0.30 * fuerza)), (0.6, mul(col, 1, 0.08 * fuerza)),
                                           (1, mul(col, 1, 0))]))
    c.fill()
    c.restore()


def fuente(c, nombre, tam, negrita=False):
    c.select_font_face(nombre, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if negrita else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(tam)


def texto(c, s, x, y, nombre, tam, col, ancla=0.5, negrita=False, espaciado=0.0, sombra=None):
    """Escribe texto con ancla horizontal (0 izq, 0.5 centro, 1 der); y = línea base."""
    fuente(c, nombre, tam, negrita)
    if espaciado:
        anchos = [c.text_extents(ch).x_advance for ch in s]
        total = sum(anchos) + espaciado * (len(s) - 1)
    else:
        total = c.text_extents(s).x_advance
    x0 = x - total * ancla
    if sombra:
        texto(c, s, x + sombra[0], y + sombra[1], nombre, tam, sombra[2], ancla, negrita, espaciado)
    src(c, col)
    if espaciado:
        xx = x0
        for ch, a in zip(s, anchos):
            c.move_to(xx, y)
            c.show_text(ch)
            xx += a + espaciado
    else:
        c.move_to(x0, y)
        c.show_text(s)
    return total


def ancho_texto(c, s, nombre, tam, negrita=False):
    fuente(c, nombre, tam, negrita)
    return c.text_extents(s).x_advance


# ----------------------------------------------------------------- posproceso
_CACHE = {}


def _ruido2d(h, w, escala, semilla):
    rng = np.random.default_rng(semilla)
    gh, gw = max(2, h // escala + 2), max(2, w // escala + 2)
    g = rng.random((gh, gw)).astype(np.float32)
    ys = np.linspace(0, gh - 1.001, h)
    xs = np.linspace(0, gw - 1.001, w)
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    cc = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (cc * (1 - fx) + d * fx) * fy


def textura_niebla():
    if "niebla" not in _CACHE:
        h, w = H // 2, W  # se dibuja a media resolución vertical y se repite
        n = 0.55 * _ruido2d(h, w, 180, 1) + 0.3 * _ruido2d(h, w, 70, 2) + 0.15 * _ruido2d(h, w, 25, 3)
        n = (n - n.min()) / (n.max() - n.min())
        n = np.clip((n - 0.25) / 0.75, 0, 1) ** 1.6
        # hacerla repetible en horizontal mezclando bordes
        n2 = np.concatenate([n, n], axis=1)
        _CACHE["niebla"] = n2.astype(np.float32)
    return _CACHE["niebla"]


def vineta():
    if "vineta" not in _CACHE:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        dx = (x - W / 2) / (W / 2)
        dy = (y - H / 2) / (H / 2)
        d = np.sqrt(dx * dx * 1.0 + dy * dy * 0.75)
        v = 1 - np.clip((d - 0.55) / 0.85, 0, 1) ** 1.5 * 0.85
        _CACHE["vineta"] = v[..., None].astype(np.float32)
    return _CACHE["vineta"]


def grano(i):
    if "grano" not in _CACHE:
        rng = np.random.default_rng(7)
        _CACHE["grano"] = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    g = _CACHE["grano"][i % 6]
    g = np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)
    return g[..., None]


def posproceso(arr, T, fi, fx):
    """arr: float32 HxWx3 en [0,1] (RGB). fx: dict con efectos del plano."""
    # niebla
    nb = fx.get("niebla", 0.0)
    if nb > 0:
        tex = textura_niebla()
        off = int((T * fx.get("niebla_vel", 18)) % W)
        capa = tex[:, off:off + W]
        capa = np.repeat(capa, 2, axis=0)[:H]
        # más densa abajo
        perfil = np.linspace(fx.get("niebla_arriba", 0.35), 1.0, H, dtype=np.float32)[:, None]
        k = (capa * perfil * nb)[..., None]
        colf = np.array(fx.get("niebla_color", (0.55, 0.68, 0.75)), np.float32)
        arr = arr * (1 - k * 0.55) + colf * k * 0.55
    # luz global (parpadeo)
    luz = fx.get("luz", 1.0)
    if luz != 1.0:
        arr = arr * luz
    # gradación fría: sombras azul-verdosas, luces ligeramente frías
    gr = fx.get("gradacion", 1.0)
    if gr > 0:
        lum = arr.mean(axis=2, keepdims=True)
        sombra = np.array((0.02, 0.05, 0.08), np.float32)
        arr = arr * (1 - 0.12 * gr) + sombra * (1 - lum) * 0.5 * gr + lum * np.array((0.0, 0.03, 0.06), np.float32) * gr
        # desaturar un poco
        arr = arr * (1 - 0.18 * gr) + lum * 0.18 * gr
    # tinte rojo (alarma)
    rojo = fx.get("rojo", 0.0)
    if rojo > 0:
        lum = arr.mean(axis=2, keepdims=True)
        arr = arr * (1 - rojo) + lum * np.array((1.6, 0.25, 0.25), np.float32) * rojo
    # aberración cromática
    ab = int(fx.get("aberracion", 0))
    if ab:
        out = arr.copy()
        out[:, ab:, 0] = arr[:, :-ab, 0]
        out[:, :-ab, 2] = arr[:, ab:, 2]
        arr = out
    # interferencia (líneas horizontales desplazadas)
    gl = fx.get("glitch", 0.0)
    if gl > 0:
        rng = np.random.default_rng(fi)
        for _ in range(int(3 + 10 * gl)):
            y0 = rng.integers(0, H - 40)
            hh = rng.integers(4, int(10 + 80 * gl))
            sh = int(rng.normal(0, 40 * gl))
            arr[y0:y0 + hh] = np.roll(arr[y0:y0 + hh], sh, axis=1)
    # pixelado (zoom digital de CCTV)
    px = int(fx.get("pixel", 0))
    if px > 1:
        hh, ww = H // px, W // px
        peq = arr[:hh * px, :ww * px].reshape(hh, px, ww, px, 3).mean(axis=(1, 3))
        arr = np.repeat(np.repeat(peq, px, axis=0), px, axis=1)
        if arr.shape[0] < H or arr.shape[1] < W:
            arr = np.pad(arr, ((0, H - arr.shape[0]), (0, W - arr.shape[1]), (0, 0)), mode="edge")
    # viñeta
    arr = arr * (1 - fx.get("vineta", 1.0) * (1 - vineta()))
    # grano
    gk = fx.get("grano", 0.035)
    if gk > 0:
        arr = arr + grano(fi) * gk * (0.6 + 0.4 * (1 - arr.mean(axis=2, keepdims=True)))
    # fundido a negro
    neg = fx.get("negro", 0.0)
    if neg > 0:
        arr = arr * (1 - neg)
    return arr


def superficie():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return s, cairo.Context(s)


def a_numpy(s):
    buf = np.ndarray((H, W, 4), np.uint8, s.get_data())
    # cairo ARGB32 en little-endian = BGRA
    return buf[..., [2, 1, 0]].astype(np.float32) / 255.0


def a_superficie(arr):
    a = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8)
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    buf = np.ndarray((H, W, 4), np.uint8, s.get_data())
    buf[..., 0] = a[..., 2]
    buf[..., 1] = a[..., 1]
    buf[..., 2] = a[..., 0]
    buf[..., 3] = 255
    s.mark_dirty()
    return s
