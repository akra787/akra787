"""Lista de planos de «El último tren de la noche», anclados a las frases de la narración.

Cada plano: (frase de anclaje, función, kwargs, opciones). Opciones: trans ('corte'|'negro'|'fundido'),
amb (sonido ambiente), tension (0..1 para la música), sfx [(segundos desde el inicio del plano, nombre, ganancia)].
"""
import json
import math
import os
import re
import subprocess
import unicodedata

import cairo
import numpy as np

from motor import (AQUI, FPS, H, HOR, KH, MAQ, SANS, TITULO, W, cl, eio, ei, eo, fbm1, hash1, hx, lerp, lerpc, lgrad, mul,
                   parpadeo, pr, rect, resplandor, rgrad, rr, src, ss, texto, tf, cono_luz)
from personajes import (ANCIANA, BRYAN, GUARDIA, HOMBRE, MADRE, NINA, SOMBRA, busto, cara, figura, figura_perfil,
                        osito, silueta)
from escenarios import Cam, anden, tren3d, vagon, persona3d, billboard
import insertos as ins

# ===================================================================== tiempos
PAL = json.load(open(os.path.join(AQUI, "palabras.json")))


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


PN = [norm(p["w"]) for p in PAL]
_cursor = [0]


def buscar(frase, desde=None):
    toks = [norm(t) for t in frase.split() if norm(t)]
    i0 = _cursor[0] if desde is None else desde
    for i in range(i0, len(PN) - len(toks) + 1):
        if PN[i:i + len(toks)] == toks:
            return i
    raise ValueError(f"No encuentro la frase: {frase!r} desde {i0}")


# envolvente de la voz para mover la boca
def _envolvente():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(AQUI, "voz.wav"), "-ac", "1", "-ar", "24000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 24000 // FPS
    n = len(x) // hop
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    rms = rms / (np.percentile(rms, 98) + 1e-6)
    return np.clip(rms, 0, 1)


ENV = _envolvente()
DUR_VOZ = len(ENV) / FPS


def boca(T):
    i = int(T * FPS)
    if 0 <= i < len(ENV):
        v = ENV[i]
        return cl((v - 0.12) * 1.4) * (0.75 + 0.25 * math.sin(T * 31))
    return 0.0


def parpadeo_ojos(T, semilla=0.0, cada=3.7):
    ph = (T + hash1(semilla) * cada) % (cada + hash1(math.floor((T + semilla * 7) / cada)) * 1.5)
    if ph < 0.13:
        return abs(ph - 0.065) / 0.065
    return 1.0


# ===================================================================== utilidades de plano
def camara(t, d, a, b=None, e=ss, **fijos):
    k = e(cl(t / d)) if d > 0 else 1.0
    b = b or {}
    kw = {key: (lerp(a[key], b.get(key, a[key]), k) if not isinstance(a[key], tuple)
                else tuple(lerp(u, v, k) for u, v in zip(a[key], b.get(key, a[key])))) for key in a}
    kw.update(fijos)
    return Cam(**kw)


def borroso(c, dibujar, factor=5):
    """Dibuja un fondo a baja resolución y lo escala: desenfoque de profundidad barato."""
    w, h = W // factor + 2, H // factor + 2
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cc = cairo.Context(s)
    cc.scale(1 / factor, 1 / factor)
    dibujar(cc)
    c.save()
    c.scale(factor, factor)
    pat = cairo.SurfacePattern(s)
    pat.set_filter(cairo.FILTER_GOOD)
    c.set_source(pat)
    c.paint()
    c.restore()


VAGON_GENTE = []

CAM_VAGON = dict(x=0.0, y=1.35, z=0.3, f=820, niebla=(0.02, 0.03, 0.035), densidad=0.03)


def fondo_escena(c, T, tipo, extra=None):
    extra = extra or {}
    if tipo == "vagon":
        vagon(c, Cam(x=0.0, y=1.3, z=extra.get("z", 2.0), yaw=extra.get("yaw", 0.0), f=820,
                     niebla=(0.02, 0.03, 0.035), densidad=0.03), T, luces=extra.get("luces", 1.0),
              rojo=extra.get("rojo", 0.0), luz_col=extra.get("luz_col"), apagado=extra.get("apagado", False),
              velocidad=extra.get("vel", 1.0))
    elif tipo == "anden":
        anden(c, Cam(x=-1.5, y=1.6, z=extra.get("z", -1), yaw=extra.get("yaw", 0.25)), T,
              luces=extra.get("luces", 1.0), tren=extra.get("tren"), mañana=extra.get("mañana", 0.0))
    elif tipo == "oscuro":
        anden(c, Cam(x=-1.5, y=1.6, z=2, yaw=0.1, niebla=(0.01, 0.012, 0.014), densidad=0.08), T, oscuro=True,
              luces=0, farola=(10.0, -2.5), reloj=False, panel=False, maquina=False, nombre="")
    elif tipo == "fantasma":
        anden(c, Cam(x=1.0, y=1.6, z=8, yaw=-1.5, niebla=(0.06, 0.03, 0.03), densidad=0.09), T, viejo=1.0,
              rojo=0.7, nombre="SAN MIGUEL", luces=0.6, maquina=False, panel=False, reloj=False)
    elif tipo == "tunel":
        ins.ventana_tunel(c, 0.0, T, 1.0, vel=0.6, marco=False)
    elif tipo == "negro":
        c.rectangle(0, 0, W, H)
        src(c, hx("#020304"))
        c.fill()
    elif tipo == "cctv":
        c.rectangle(0, 0, W, H)
        c.set_source(lgrad(0, 0, 0, H, [(0, hx("#0a1830")), (1, hx("#03060c"))]))
        c.fill()
        for i in range(3):
            for j in range(3):
                rr(c, 60 + i * 330, 300 + j * 300, 300, 260, 10)
                src(c, hx("#3c6a8c", 0.6))
                c.fill()


def p_busto(c, t, T, d, spec=BRYAN, fondo="vagon", fondo_kw=None, expr="neutral", x=None, y=None, r=230,
            zoom=(1.0, 1.08), mira=(0.0, 0.0), giro=0.0, habla=False, estados=(), luz=1.0, sacudida=0.0,
            parpado=True, rim=hx("#cfe8ff"), lagrimas=0.0, inclina=0.0, pelo_cara=0.0, vaho=0.0, alfa=1.0,
            mezcla=None, calido=0.0, giro_fin=None, mira_fin=None, fx_extra=None, aliento=0.0):
    """Primer plano de un personaje con fondo desenfocado. estados: [(t0, {param: valor})]."""
    r = r * KH
    if y is None:
        y = H * (0.45 if HOR else 0.42)
    if x is None:
        # en panorámico: plano/contraplano, Bryan a la izquierda y los demás a la derecha (salvo planos detalle)
        x = W / 2 if (not HOR or r > 300) else W * (0.4 if spec["nombre"] == "bryan" else 0.6)
    kw = dict(expr=expr, mira=mira, giro=giro, lagrimas=lagrimas, inclina=inclina, pelo_cara=pelo_cara)
    for t0, cambios in estados:
        if t >= t0:
            kw.update(cambios)
    if giro_fin is not None:
        kw["giro"] = lerp(giro, giro_fin, ss(t / d))
    if mira_fin is not None:
        k = ss(t / d)
        kw["mira"] = (lerp(mira[0], mira_fin[0], k), lerp(mira[1], mira_fin[1], k))
    borroso(c, lambda cc: fondo_escena(cc, T, fondo, fondo_kw))
    # oscurecer el fondo para separar
    c.rectangle(0, 0, W, H)
    src(c, (0, 0, 0, 0.35))
    c.fill()
    z = lerp(zoom[0], zoom[1], ss(t / d))
    deriva = fbm1(T * 0.25, 3.1) * 12
    with tf(c, x + deriva, y, s=z, a=alfa):
        def dib(spec_, a=1.0):
            with tf(c, 0, 0, a=a):
                busto(c, 0, 0, r, spec_, T=T, expr=kw["expr"], mira=kw["mira"],
                      habla=boca(T) if kw.get("habla", habla) else 0.0, giro=kw["giro"],
                      parp=parpadeo_ojos(T, hash1(len(spec_["nombre"]))) if parpado else 1.0, lagrimas=kw["lagrimas"],
                      inclina=kw["inclina"], pelo_cara=kw["pelo_cara"], sacudida=sacudida)
        if mezcla:
            k = ss(cl((t - mezcla[1]) / mezcla[2]))
            dib(spec, 1 - k)
            dib(mezcla[0], k)
        else:
            dib(spec)
        # luz de contorno
        c.save()
        c.set_operator(cairo.OPERATOR_ADD)
        c.arc(-r * 1.2, -r * 0.8, r * 1.6, 0, 2 * math.pi)
        c.set_source(rgrad(-r * 1.2, -r * 0.8, 0, r * 1.6, [(0, mul(rim, 1, 0.18 * luz)), (1, mul(rim, 1, 0))]))
        c.fill()
        c.restore()
        if aliento > 0:
            for k in range(6):
                ph = (T * 0.6 + k / 6) % 1.0
                a = aliento * (1 - ph) * cl(math.sin(T * 1.6) + 0.3)
                c.arc(r * 0.05 + ph * r * 0.5, r * 0.75 - ph * r * 0.3, r * (0.12 + ph * 0.5), 0, 2 * math.pi)
                src(c, (0.85, 0.9, 0.95, 0.08 * a))
                c.fill()
    # luz lateral dramática: la mitad derecha cae en sombra
    c.set_source(lgrad(0, 0, W, 0, [(0, (0, 0, 0, 0.0)), (0.5, (0, 0, 0, 0.12)), (1, (0, 0, 0, 0.6))]))
    c.paint()
    c.set_source(lgrad(0, 0, 0, H, [(0, (0, 0, 0, 0.35)), (0.3, (0, 0, 0, 0.0)), (0.8, (0, 0, 0, 0.1)),
                                    (1, (0, 0, 0, 0.6))]))
    c.paint()
    if calido > 0:
        resplandor(c, W * 0.75, H * 0.2, 900, hx("#ffcf8a"), 0.6 * calido)
    fx = dict(niebla=0.15, luz=luz)
    if fx_extra:
        fx.update(fx_extra)
    return fx


def p_vagon(c, t, T, d, a, b=None, gente=(), fx_extra=None, **kw):
    cam = camara(t, d, dict(CAM_VAGON, **a), b)
    if callable(gente):
        gente = gente(t, d, T)
    vagon(c, cam, T, gente=[dict(g) for g in gente], **kw)
    fx = dict(niebla=0.12, luz=0.88)
    if fx_extra:
        fx.update(fx_extra)
    return fx


def p_anden(c, t, T, d, a, b=None, fx_extra=None, tren_mov=None, gente_fn=None, **kw):
    base = dict(x=-2.0, y=1.65, z=-3, yaw=0.12, pitch=0.03)
    cam = camara(t, d, dict(base, **a), b)
    if tren_mov:
        kw["tren"] = tren_mov(t, d)
    if gente_fn:
        kw["gente"] = gente_fn(t, d, T)
    anden(c, cam, T, **kw)
    fx = dict(niebla=0.45)
    if fx_extra:
        fx.update(fx_extra)
    return fx


def p_insert(c, t, T, d, fn, fx_extra=None, **kw):
    fx = fn(c, t, T, d, **kw) or {}
    if fx_extra:
        fx.update(fx_extra)
    return fx


# ===================================================================== insertos propios
def brazo_agarre(c, t, T, d):
    borroso(c, lambda cc: fondo_escena(cc, T, "fantasma"))
    c.rectangle(0, 0, W, H)
    src(c, (0, 0, 0, 0.4))
    c.fill()
    # brazo de Bryan (manga granate) cruzando
    with tf(c, 0, H * 0.55, r=-0.15 if not HOR else -0.08, s=0.8 if HOR else 1.0):
        rr(c, -300, -170, W + 600, 340, 150)
        src(c, BRYAN["torso"])
        c.fill_preserve()
        c.set_source(lgrad(0, -170, 0, 170, [(0, mul(BRYAN["torso_luz"], 1, 0.5)), (1, (0, 0, 0, 0.5))]))
        c.fill()
    k = eo(pr(t, 0.05, 0.25))
    piel = ANCIANA["piel"]
    with tf(c, W * 0.55, H * 0.55 - 120 * (0.8 if HOR else 1) - (1 - k) * 600, r=0.1, s=0.8 if HOR else 1.0):
        rr(c, -120, -900, 240, 800, 100)
        src(c, ANCIANA["torso"])
        c.fill()
        # mano huesuda
        c.save()
        c.scale(1, 1.1)
        c.arc(0, -40, 120, 0, 2 * math.pi)
        c.restore()
        src(c, piel)
        c.fill()
        for i in range(4):
            xx = -105 + i * 70
            c.move_to(xx, 0)
            c.curve_to(xx - 10, 90, xx + 5, 150, xx + 20, 175)
            c.set_line_width(42)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            src(c, piel)
            c.stroke()
            c.move_to(xx - 3, 90)
            c.line_to(xx + 15, 95)
            c.set_line_width(4)
            src(c, mul(ANCIANA["piel_sombra"], 1, 0.7))
            c.stroke()
        for i in range(4):
            xx = -105 + i * 70
            c.arc(xx + 20, 173, 12, 0, 2 * math.pi)
            src(c, hx("#c9c0b8"))
            c.fill()
        # venas
        c.set_line_width(5)
        src(c, hx("#8a97a8", 0.6))
        c.move_to(-40, -150)
        c.curve_to(-20, -80, -60, -30, -40, 30)
        c.move_to(30, -150)
        c.curve_to(50, -60, 20, -20, 40, 40)
        c.stroke()
    return dict(niebla=0.2, sacudida=10 * (1 - pr(t, 0.2, 0.4)) * (t > 0.2), rojo=0.15)


def manos_unen(c, t, T, d):
    c.rectangle(0, 0, W, H)
    c.set_source(lgrad(0, 0, W, 0, [(0, hx("#05080a")), (1, hx("#3a2a18"))]))
    c.fill()
    resplandor(c, W * 0.85, H * 0.45, 900, hx("#ffcf8a"), 0.9)
    k = ss(pr(t, 0.2, d * 0.7))
    # mano de la madre desde la derecha
    with tf(c, W * 0.95 - k * 30, H * 0.47):
        rr(c, 0, -110, 700, 220, 100)
        src(c, MADRE["torso"])
        c.fill()
        c.save(); c.scale(1.2, 0.85); c.arc(-60, 0, 110, 0, 2 * math.pi); c.restore()
        src(c, MADRE["piel"])
        c.fill()
        for i in range(4):
            c.move_to(-120, -60 + i * 40)
            c.line_to(-280, -80 + i * 45)
            c.set_line_width(36)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            src(c, MADRE["piel"])
            c.stroke()
    # mano de Bryan desde la izquierda
    with tf(c, lerp(-200, W * 0.32, k), H * 0.53):
        rr(c, -800, -120, 800, 240, 110)
        src(c, BRYAN["torso"])
        c.fill()
        c.save(); c.scale(1.2, 0.85); c.arc(60, 0, 110, 0, 2 * math.pi); c.restore()
        src(c, BRYAN["piel"])
        c.fill()
        for i in range(4):
            c.move_to(120, -60 + i * 40)
            c.line_to(280, -70 + i * 42)
            c.set_line_width(38)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            src(c, BRYAN["piel"])
            c.stroke()
    if k > 0.95:
        resplandor(c, W * 0.55, H * 0.5, 500, hx("#fff2d0"), (k - 0.95) * 20 * 0.5)
    return dict(niebla=0.2, gradacion=0.3, niebla_color=(0.6, 0.5, 0.35))


def sala_cctv(c, t, T, d):
    c.rectangle(0, 0, W, H)
    src(c, hx("#04070c"))
    c.fill()
    z = 1 + 0.08 * t / d
    with tf(c, W / 2, H * (0.45 if HOR else 0.4), s=z * (0.8 if HOR else 1)):
        for i in range(3):
            for j in range(3):
                x, y = -480 + i * 330, -420 + j * 290
                rr(c, x, y, 300, 260, 12)
                src(c, hx("#14181c"))
                c.fill()
                rr(c, x + 14, y + 14, 272, 205, 6)
                src(c, mul(hx("#6f8f9a"), 0.35 + 0.2 * hash1(i * 3 + j + math.floor(T * 2) * 0.0)))
                c.fill()
                # mini escena
                c.save()
                rr(c, x + 14, y + 14, 272, 205, 6)
                c.clip()
                for k in range(4):
                    c.move_to(x + 150, y + 60)
                    c.line_to(x + 14 + k * 90, y + 220)
                c.set_line_width(3)
                src(c, (0.9, 0.95, 1, 0.25))
                c.stroke()
                if i == 1 and j == 1:
                    rect(c, x + 160, y + 90, 110, 100, hx("#c9d6da", 0.5))
                src(c, (0, 0, 0, 0.2))
                for yy in range(0, 210, 6):
                    c.rectangle(x + 14, y + 14 + yy, 272, 2)
                c.fill()
                c.restore()
                texto(c, f"CAM 0{i + j * 3 + 1}", x + 24, y + 245, MAQ, 22, hx("#9fd0e0", 0.8), ancla=0)
    resplandor(c, W / 2, H * 0.4, 900, hx("#7fb8ff"), 0.35)
    # guardia y hombre de espaldas, en silueta
    if HOR:
        figura(c, W * 0.2, H * 1.3, 1100, GUARDIA, T=T, espalda=True, ilum=0.4)
        figura(c, W * 0.82, H * 1.32, 1150, HOMBRE, T=T, espalda=True, ilum=0.4)
    else:
        figura(c, W * 0.32, H * 1.12, 1300, GUARDIA, T=T, espalda=True, ilum=0.4)
        figura(c, W * 0.78, H * 1.15, 1350, HOMBRE, T=T, espalda=True, ilum=0.4)
    c.rectangle(0, H * 0.62, W, H * 0.38)
    c.set_source(lgrad(0, H * 0.62, 0, H, [(0, (0, 0, 0, 0.0)), (1, (0, 0, 0, 0.75))]))
    c.fill()
    return dict(niebla=0.1, gradacion=0.6)


def cctv_anden(fase, t, d, T):
    """Contenido para la cámara de seguridad del andén."""
    def dib(c):
        cam = Cam(x=-3.2, y=4.2, z=-2.0, yaw=0.32, pitch=-0.32, f=760)
        tr = None
        gente = []
        if fase == "llega":
            tr = dict(z=lerp(55, 3.5, eo(cl(t / max(0.1, d - 0.5)))), puertas=0.0, luz=1.0)
        elif fase == "abre":
            tr = dict(z=3.5, puertas=ss(cl(t / 1.2)), luz=1.0)
            gente = [dict(x=-1.6, z=7.0, spec=BRYAN, kw=dict(espalda=True))]
        else:
            tr = dict(z=3.5, puertas=1.0, luz=1.0)
            k = ss(cl(t / max(0.5, d * 0.8)))
            gente = [dict(x=lerp(-1.6, -0.1, k), z=7.0, spec=BRYAN, kw=dict(espalda=True, paso=T * 1.6))]
        anden(c, cam, 2.0 + T, tren=tr, gente=gente, luces=1.0)
    return dib


REFLEJO = (0.66, 0.33) if HOR else (0.68, 0.4)


def cctv_reflejo(t, d, T, sonrisa=False):
    def dib(c):
        c.rectangle(0, 0, W, H)
        src(c, hx("#8e979c"))
        c.fill()
        # ventana del tren vista de cerca desde el andén
        VX, VY, VW, VH = (180, 70, W - 360, 800) if HOR else (100, 420, W - 200, 1000)
        rr(c, VX, VY, VW, VH, 30)
        src(c, hx("#dfe8ea"))
        c.fill()
        if HOR:
            figura(c, W * 0.38, H * 1.55, 1500, BRYAN, T=T, espalda=True)
        else:
            figura(c, W * 0.42, 2350, 1850, BRYAN, T=T, espalda=True)
        c.save()
        rr(c, VX, VY, VW, VH, 30)
        c.clip()
        a = 0.35 + 0.25 * ss(cl(t / d))
        with tf(c, W * REFLEJO[0], H * REFLEJO[1], a=a):
            busto(c, 0, 0, 150 * (0.85 if HOR else 1), ANCIANA, T=T, expr="inquietante" if sonrisa else "serio",
                  mira=(-0.5, 0.2))
        c.restore()
        rr(c, VX, VY, VW, VH, 30)
        c.set_line_width(24)
        src(c, hx("#5a6468"))
        c.stroke()
    return dib


def p_cctv(c, t, T, d, contenido, zoom=(1.0, 1.0), foco=(0.5, 0.5), pixel=0, hora=None):
    z = lerp(zoom[0], zoom[1], ss(cl(t / d)))
    fx = ins.cctv(c, t, T, d, contenido(t, d, T), zoom=z, foco=foco, hora=hora)
    if pixel:
        fx["pixel"] = int(lerp(1, pixel, ss(cl(t / d))))
    return fx


def foto_fecha(c, t, T, d):
    c.rectangle(0, 0, W, H)
    src(c, hx("#0b0906"))
    c.fill()
    z = 1.6 + 0.2 * t / d
    with tf(c, W * 0.5, H * 0.5, s=z):
        ins.foto_accidente(c, -120, -180, 760, 520, T)
        texto(c, "14-11-1996", -120, 125, "Courier Prime", 52, hx("#c0392b"), negrita=True)
    resplandor(c, W * 0.5, -100, 1100, hx("#ffd9a0"), 0.4)
    return dict(niebla=0.2, niebla_color=(0.4, 0.35, 0.3))


def movil_fecha(c, t, T, d):
    fx = ins.movil(c, 10.0, T, d)
    c.rectangle(0, 0, W, H)
    src(c, (0, 0, 0, 0.55))
    c.fill()
    k = eo(pr(t, 0.2, 0.6))
    with tf(c, W / 2, H * 0.47, s=lerp(0.8, 1.0, k), a=k):
        rr(c, -380, -200, 760, 400, 30)
        src(c, hx("#0d1418", 0.92))
        c.fill()
        texto(c, "1996", -170, 50, TITULO, 170, hx("#c0392b"))
        texto(c, "→", 0, 40, SANS, 90, hx("#cfe0e8"))
        texto(c, "2026", 170, 50, TITULO, 170, hx("#e8eef0"))
        texto(c, "30 AÑOS", 0, 150, TITULO, 64, hx("#9fb3bd"), espaciado=10)
    return fx


def puerta_desde_dentro(c, t, T, d, bryan=True, cam_a=None, cam_b=None, gente_fn=None, avance=0.0, **kw):
    """Andén visto desde la puerta abierta del vagón, con el marco y Bryan de espaldas."""
    ca = dict(x=1.2, y=1.6, z=8.0, yaw=-1.57, niebla=(0.06, 0.03, 0.03), densidad=0.08, pitch=0.0)
    ca.update(cam_a or {})
    cam = camara(t, d, ca, cam_b)
    gente = gente_fn(t, d, T) if gente_fn else []
    anden(c, cam, T, gente=gente, **kw)
    # marco de la puerta
    PX, PY, PW, PH = (W * 0.2, 30, W * 0.6, H - 60) if HOR else (70, 170, W - 140, 1640)
    c.rectangle(0, 0, W, H)
    rr(c, PX, PY, PW, PH, 18)
    c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    src(c, hx("#151a1c"))
    c.fill()
    c.set_fill_rule(cairo.FILL_RULE_WINDING)
    if HOR:  # pared interior del vagón a los lados de la puerta, con barras
        for xx in (PX - 60, PX + PW + 40):
            rect(c, xx, 0, 20, H, hx("#8f9a9d", 0.35))
    rr(c, PX, PY, PW, PH, 18)
    c.set_line_width(10)
    src(c, hx("#3a4448"))
    c.stroke()
    rect(c, PX, PY + PH - 50, PW, 50, hx("#2a3236"))
    if bryan:
        k = ss(cl(t / d)) * avance
        if HOR:
            figura(c, W * 0.44, H * (1.42 - 0.05 * k), 1250 * (1 - 0.15 * k), BRYAN, T=T, espalda=True)
        else:
            figura(c, W * 0.42, H * (1.25 - 0.05 * k), 1700 * (1 - 0.15 * k), BRYAN, T=T, espalda=True)
    return dict(niebla=0.35, niebla_color=(0.35, 0.25, 0.25))


def morph_madre(c, t, T, d):
    return p_busto(c, t, T, d, spec=ANCIANA, fondo="vagon", fondo_kw=dict(luz_col=hx("#ffd6a0")), expr="dulce",
                   mezcla=(MADRE, d * 0.15, d * 0.6), calido=0.6, rim=hx("#ffd6a0"), zoom=(1.05, 1.15))


def fantasmas_cerca(c, t, T, d):
    borroso(c, lambda cc: fondo_escena(cc, T, "fantasma"))
    c.rectangle(0, 0, W, H)
    src(c, (0, 0, 0, 0.3))
    c.fill()
    palido = dict(SOMBRA, piel=hx("#a9b0b2"), piel_sombra=hx("#5c6466"), torso=hx("#1a1f21"))
    z = lerp(1.0, 1.12, ss(t / d))
    pos = (((W * 0.24, H * 0.42, 170), (W * 0.76, H * 0.4, 160), (W * 0.5, H * 0.5, 210)) if HOR else
           ((W * 0.2, H * 0.4, 170), (W * 0.8, H * 0.36, 160), (W * 0.5, H * 0.47, 210)))
    for k, (x, y, r) in enumerate(pos):
        with tf(c, W / 2 + (x - W / 2) * z, y, s=z):
            busto(c, 0, 0, r * KH * (1.15 if HOR else 1), palido, T=T, expr="neutral", respira=0)
    return dict(niebla=0.55, niebla_color=(0.3, 0.22, 0.22), rojo=0.2, luz=0.6 + 0.4 * parpadeo(T, 2.2))


def nina_levanta(c, t, T, d):
    k = ss(pr(t, d * 0.35, d * 0.5))
    return p_busto(c, t, T, d, spec=NINA, fondo="fantasma", r=200, x=W / 2, y=H * 0.4, expr="neutral",
                   pelo_cara=lerp(1.0, 0.3, k), mira=(0, lerp(0.6, -0.1, k)), inclina=lerp(0.25, 0.0, k),
                   zoom=(1.0, 1.15), rim=hx("#ff9a8a"), parpado=False,
                   fx_extra=dict(niebla=0.5, niebla_color=(0.3, 0.22, 0.22), rojo=0.2))


def nina_nombre(c, t, T, d):
    fx = p_busto(c, t, T, d, spec=NINA, fondo="fantasma", r=380, x=W / 2, y=H * 0.36, expr="neutral", pelo_cara=0.3,
                 zoom=(1.1, 1.25), parpado=False, rim=hx("#ff9a8a"),
                 fx_extra=dict(niebla=0.4, niebla_color=(0.3, 0.22, 0.22), rojo=0.25))
    # la niña susurra «Bryan…»
    k = pr(t, 0.25, 0.4)
    habla = 0.35 * math.sin(cl((t - 0.25) / 0.9) * math.pi) if 0.25 < t < 1.15 else 0.0
    if habla > 0:
        with tf(c, W / 2, H * 0.36, s=lerp(1.1, 1.25, ss(t / d))):
            busto(c, 0, 0, 380 * KH, NINA, T=T, habla=habla, pelo_cara=0.3, parp=1.0)
    a = k * (1 - pr(t, d - 0.5, 0.5))
    texto(c, "«Bryan…»", W / 2 + (hash1(math.floor(T * 15)) - 0.5) * 8, H * (0.73 if HOR else 0.64), "Noto Serif",
          96 * (0.85 if HOR else 1),
          hx("#f1d6d0", a * 0.95))
    fx["glitch"] = 0.3 if 0.2 < t < 0.6 else 0
    fx["aberracion"] = 4
    return fx


def nina_camina(c, t, T, d, cerca=False):
    def gente(t_, d_, T_):
        if cerca:
            x = lerp(-1.3, -0.4, t_ / d_)
            zc = 5.5
        else:
            x = lerp(-3.7, -1.6, t_ / d_)
            zc = 8.0
        g = [dict(x=x, z=zc, spec=NINA, alto=1.2,
                  kw=dict(brazos="peluche", peluche=True, pelo_cara=1.0, paso=T_ * 1.1))]
        for k, (xx, dz) in enumerate(((-3.5, -1.6), (-3.3, 1.5), (-2.4, 2.3), (-3.6, 0.6), (-2.2, -2.2))):
            g.append(dict(x=xx, z=zc + dz, tipo="silueta", semilla=k, ojos=0.7, alto=1.75))
        return g
    fx = puerta_desde_dentro(c, t, T, d, bryan=False, gente_fn=gente, viejo=1.0, rojo=0.7, nombre="SAN MIGUEL",
                             luces=0.55, maquina=False, panel=False, reloj=False,
                             cam_a=dict(z=5.5 if cerca else 8.0, x=1.2 if not cerca else 0.9,
                                        y=1.6 if not cerca else 1.15, pitch=0.0 if not cerca else -0.1),
                             cam_b=dict(x=0.9 if not cerca else 0.4))
    fx["rojo"] = 0.15
    return fx


def andén_gente(t, d, T):
    g = []
    for k, (xx, zz) in enumerate(((-1.6, 7.2), (-2.4, 8.9), (-1.9, 9.8), (-3.1, 6.6), (-3.5, 9.4), (-2.7, 7.6),
                                  (-3.6, 8.0), (-1.4, 8.4))):
        g.append(dict(x=xx, z=zz, tipo="silueta", semilla=k, ojos=0.8, alto=1.6 + 0.3 * hash1(k)))
    return g


# ===================================================================== lista de planos
# Atajos
B, A = BRYAN, ANCIANA
VAG = "vagon"
CALIDO = hx("#ffd6a0")


def P(ancla, funcion, opciones=None, **kw):
    return (ancla, funcion, kw, opciones or {})


def anden_mov_bryan_camina(t, d, T):
    z = lerp(3.0, 7.5, t / d)
    return [dict(x=-1.8, z=z, tipo="perfil", spec=B, kw=dict(modo="camina", fase=T * 0.9))]


def tren_llega(t, d):
    k = eo(cl(t / max(0.1, d * 0.85)))
    return dict(z=lerp(70, 3.5, k), puertas=0.0, luz=1.0, faro=1.0)


def tren_sale(t, d):
    return dict(z=lerp(3.5, 30, ei(cl(t / d))), puertas=0.0, luz=1.0, faro=0.0)


def tren_sale_calido(t, d):
    return dict(z=lerp(3.5, 40, ei(cl(t / d))), puertas=0.0, luz=1.0, faro=0.0, ventanas_col=hx("#ffd9a0"))


def solo_bryan(x=-1.5, z=8.0, **kw):
    return lambda t, d, T: [dict(x=x, z=z, spec=B, kw=dict(dict(giro=math.sin(T * 0.7) * 0.6, mira=(math.sin(T * 0.7) * 0.6, 0)), **kw))]


PLANOS = [
    # ------------------------------------------------------------------ título y gancho
    P("El último tren de la noche", p_insert, dict(amb="tunel", tension=0.35, sfx=[(0.0, "riser", 0.7)]),
      fn=ins.titulo_tunel),
    P("Nunca debí subir", p_anden, dict(trans="negro", amb="anden", tension=0.45, sfx=[(0.0, "impacto", 0.9)]),
      a=dict(x=-1.0, y=1.2, z=-1.0, yaw=0.18), b=dict(z=1.0),
      tren_mov=lambda t, d: dict(z=lerp(68, 52, t / d), puertas=0, luz=0.6, faro=1.0),
      gente_fn=lambda t, d, T: [dict(x=-0.9, z=3.0, spec=B, kw=dict(espalda=True))],
      fx_extra=dict(luz=0.8)),
    P("Eran las 3:17", p_insert, dict(amb="anden", tension=0.3, sfx=[(0.0, "tictac", 0.6)]), fn=ins.reloj_cerca),
    P("cuando llegué a la estación", p_anden, dict(amb="anden"),
      a=dict(x=3.0, y=1.5, z=5.0, yaw=-1.5708, pitch=0.0), b=dict(z=6.5),
      gente_fn=anden_mov_bryan_camina),
    P("Estaba completamente solo", p_anden, dict(amb="anden", tension=0.35),
      a=dict(x=-2.0, y=3.8, z=1.0, pitch=-0.3, yaw=0.08), b=dict(z=-3.0, y=4.1),
      gente_fn=solo_bryan(x=-1.8, z=8.5)),
    P("Las luces parpadeaban", p_anden, dict(amb="zumbido", tension=0.35, sfx=[(0.2, "chispazo", 0.6)]),
      a=dict(x=-1.6, y=2.4, z=2.0, pitch=0.42, yaw=-0.1), b=dict(z=3.0),
      fx_extra=dict(luz=1.0)),
    P("el zumbido de las máquinas", p_anden, dict(amb="maquina"),
      a=dict(x=-1.0, y=1.4, z=6.0, yaw=-0.85), b=dict(z=6.6, yaw=-0.75)),
    P("Había perdido el último tren", p_anden, dict(amb="anden", tension=0.3),
      a=dict(x=1.6, y=1.2, z=6.2, yaw=-1.5708), b=dict(x=1.1),
      gente_fn=lambda t, d, T: [dict(x=-3.55, y=0.0, z=6.1, spec=B,
                                     kw=dict(sentado=True, brazos="regazo", expr="triste", mira=(0, 0.5)))]),
    P("Pero entonces ocurrió algo extraño", p_busto, dict(amb="anden", tension=0.55, sfx=[(0.3, "glitch", 0.7)]),
      fondo="anden", expr="neutral", mira=(0, 0.4), mira_fin=(0.1, -0.7), zoom=(1.0, 1.15),
      fx_extra=dict(glitch=0.0)),
    P("En la pantalla apareció", p_insert, dict(amb="anden", tension=0.6, sfx=[(0.2, "pitido", 0.6)]),
      fn=ins.panel_salidas, fase="nuevo"),
    P("Destino: desconocido", p_insert, dict(amb="anden", tension=0.65, sfx=[(0.1, "teclas", 0.5)]),
      fn=ins.panel_salidas, fase="destino", zoom=0.12),
    P("Y lo más inquietante", p_insert, dict(amb="anden", tension=0.7), fn=ins.panel_salidas, fase="hora",
      zoom=0.2),
    P("marcaba las 3:17", p_insert, dict(amb="silencio", tension=0.2, sfx=[(0.35, "impacto", 1.0)]),
      fn=ins.reloj_cerca, parado=True),
    P("Justo en ese momento", p_anden, dict(amb="tren_llega", tension=0.6),
      a=dict(x=-1.6, y=1.5, z=-2.0, yaw=0.16), b=dict(z=-1.0), tren_mov=tren_llega),
    P("las puertas del tren se abrieron", p_anden, dict(amb="tren_parado", tension=0.55,
                                                        sfx=[(0.25, "puertas_abren", 0.9)]),
      a=dict(x=-3.95, y=1.6, z=6.0, yaw=1.5708), b=dict(x=-3.7),
      tren_mov=lambda t, d: dict(z=3.5 - 6.5 * 0 + 0.0, puertas=ss(cl((t - 0.25) / 1.1)), luz=1.0, faro=0.0),
      gente_fn=lambda t, d, T: [dict(x=-2.5, z=6.4, spec=B, kw=dict(espalda=True))]),
    P("No sé por qué subí", p_anden, dict(amb="tren_parado", tension=0.5),
      a=dict(x=-3.95, y=1.6, z=6.0, yaw=1.5708), b=dict(x=-3.4),
      tren_mov=lambda t, d: dict(z=3.5, puertas=1.0, luz=1.0, faro=0.0),
      gente_fn=lambda t, d, T: [dict(x=lerp(-2.5, -0.2, ss(t / d)), z=6.4, spec=B,
                                     kw=dict(espalda=True, paso=T * 1.7))]),
    P("Quizá porque estaba cansado", p_busto, dict(amb="tren_parado", tension=0.4),
      fondo="anden", fondo_kw=dict(tren=dict(z=-5, puertas=1.0, luz=1.0), yaw=0.9), expr="triste",
      mira=(0.3, 0.3), rim=hx("#e8f8ff"), zoom=(1.0, 1.06)),
    P("O quizá porque aquel tren", p_anden, dict(amb="tren_parado", tension=0.7, sfx=[(0.0, "drone_sube", 0.7)]),
      a=dict(x=2.15, y=0.6, z=-7.0, yaw=0.0, pitch=0.08), b=dict(z=-2.6, y=1.4),
      tren_mov=lambda t, d: dict(z=0.0, puertas=0.0, luz=0.8, faro=0.7)),

    # ------------------------------------------------------------------ escena 2: el vagón vacío
    P("Cuando entré", p_vagon, dict(trans="negro", amb="vagon_parado", tension=0.35),
      a=dict(z=0.4), b=dict(z=1.2),
      gente=[dict(x=0.0, z=5.0, spec=B, kw=dict(giro=0.0))]),
    P("Ni pasajeros", p_vagon, dict(amb="vagon_parado", tension=0.35), a=dict(z=3.0, yaw=-0.35), b=dict(yaw=0.35)),
    P("El vagón estaba iluminado", p_vagon, dict(amb="zumbido", tension=0.4, sfx=[(0.3, "chispazo", 0.5)]),
      a=dict(z=4.0, y=1.4, pitch=0.75), b=dict(z=5.0)),
    P("Me senté junto a una ventana", p_vagon, dict(amb="vagon_parado", tension=0.35),
      a=dict(x=-0.9, y=1.25, z=6.0, yaw=1.5708, f=760), b=dict(x=-0.6),
      gente=[dict(x=1.25, y=0.46, z=6.0, spec=B, alto=1.75, kw=dict(sentado=True, brazos="movil",
                                                                    mira=(0, 0.6), expr="neutral"))]),
    P("Sin cobertura", p_insert, dict(amb="vagon_parado", tension=0.4, sfx=[(0.3, "error_movil", 0.6)]),
      fn=ins.movil),
    P("Entonces, las puertas comenzaron a cerrarse", p_vagon,
      dict(amb="vagon_parado", tension=0.45, sfx=[(0.0, "pitidos_puerta", 0.7), (1.4, "puertas_cierran", 0.9)]),
      a=dict(x=0.6, y=1.3, z=4.7, yaw=-1.5708, f=700), puertas=1.0),
    P("Y justo antes de que el tren arrancara", p_busto, dict(amb="vagon_parado", tension=0.6),
      fondo=VAG, expr="neutral", estados=[(2.4, dict(expr="miedo", mira=(0.6, 0)))], zoom=(1.0, 1.12)),
    P("No deberías haber subido", p_vagon, dict(amb="silencio", tension=0.8, sfx=[(0.0, "susurro", 0.8)]),
      a=dict(z=6.0, y=1.3), b=dict(z=8.5),
      gente=[dict(x=0.0, y=0.46, z=16.4, spec=A, alto=1.6,
                  kw=dict(sentado=True, brazos="regazo", expr="serio", ilum=0.25))],
      luces=0.35, fx_extra=dict(luz=0.6)),
    P("Me giré rápidamente", p_vagon, dict(amb="vagon_parado", tension=0.7, sfx=[(0.0, "whoosh", 0.8)]),
      a=dict(z=5.0, yaw=2.6), b=dict(yaw=0.0),
      gente=[dict(x=0.0, y=0.46, z=16.4, spec=A, alto=1.6, kw=dict(sentado=True, brazos="regazo", expr="serio"))]),
    P("Era una anciana sentada", p_vagon, dict(amb="vagon_parado", tension=0.6),
      a=dict(z=6.0), b=dict(z=10.0, y=1.2),
      gente=[dict(x=0.0, y=0.46, z=16.4, spec=A, alto=1.6, kw=dict(sentado=True, brazos="regazo", expr="serio"))]),
    P("No la había visto al entrar", p_busto, dict(amb="vagon_parado", tension=0.55),
      fondo=VAG, expr="miedo", mira=(0.2, 0.0), giro=0.15),
    P("Tenía la piel muy pálida", p_busto, dict(amb="vagon_parado", tension=0.6),
      spec=A, fondo=VAG, fondo_kw=dict(z=10), expr="serio", zoom=(1.0, 1.12), parpado=False),
    P("una mirada que parecía atravesarme", p_busto, dict(amb="vagon_parado", tension=0.75,
                                                          sfx=[(0.2, "drone_sube", 0.6)]),
      spec=A, fondo=VAG, expr="serio", r=520, y=H * 0.47, zoom=(1.0, 1.2), parpado=False),
    P("Intenté sonreír", p_busto, dict(amb="vagon_parado", tension=0.5),
      fondo=VAG, expr="sonrisa", mira=(0.4, 0.0)),
    P("¿Perdone?", p_busto, dict(amb="vagon_parado", tension=0.5),
      fondo=VAG, expr="miedo", mira=(0.4, 0.0), habla=True),
    P("La mujer se inclinó lentamente", p_busto, dict(amb="vagon_parado", tension=0.7),
      spec=A, fondo=VAG, fondo_kw=dict(z=10, luces=0.7), expr="serio", zoom=(0.9, 1.45), parpado=False,
      inclina=0.0, fx_extra=dict(luz=0.85)),
    P("Si ves a alguien fuera del tren", p_busto, dict(amb="vagon_parado", tension=0.85),
      spec=A, fondo=VAG, fondo_kw=dict(z=10, luces=0.6, rojo=0.4), expr="serio", r=560, y=H * 0.44,
      zoom=(1.0, 1.15), habla=True, parpado=False, rim=hx("#ff8a7a"), fx_extra=dict(rojo=0.12, luz=0.85)),
    P("Después volvió a quedarse en silencio", p_vagon, dict(amb="vagon_parado", tension=0.4),
      a=dict(x=-0.4, z=2.0, y=1.3, yaw=0.05), b=dict(z=3.0),
      gente=[dict(x=1.15, y=0.46, z=7.0, tipo="perfil", spec=B, kw=dict(modo="sentado", voltear=True)),
             dict(x=0.0, y=0.46, z=16.4, spec=A, alto=1.6, kw=dict(sentado=True, brazos="regazo", expr="serio"))]),

    # ------------------------------------------------------------------ escena 3: las estaciones imposibles
    P("El tren comenzó a avanzar", p_anden, dict(trans="negro", amb="tren_arranca", tension=0.5),
      a=dict(x=-1.0, y=1.4, z=-2.0, yaw=0.2), b=dict(z=-1.0), tren_mov=tren_sale),
    P("Al principio todo parecía normal", p_vagon, dict(amb="tren_marcha", tension=0.35),
      a=dict(x=-0.8, y=1.25, z=6.0, yaw=1.5708, f=740, roll=0.0), b=dict(x=-0.6), velocidad=1.0,
      gente=[dict(x=1.25, y=0.46, z=6.0, spec=B, kw=dict(sentado=True, brazos="regazo", expr="neutral"))]),
    P("Pero después de unos minutos", p_busto, dict(amb="tren_marcha", tension=0.45),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="neutral", giro=0.0, giro_fin=0.7, mira=(0, 0), mira_fin=(0.8, 0)),
    P("no estábamos pasando por ninguna estación", p_insert, dict(amb="tren_marcha", tension=0.55),
      fn=ins.ventana_tunel),
    P("Las paredes del túnel", p_insert, dict(amb="tren_marcha", tension=0.6), fn=ins.ventana_tunel, zoom=1.35,
      marco=False),
    P("Había luces rojas en el techo", p_insert, dict(amb="tren_marcha", tension=0.75), fn=ins.ventana_tunel,
      rojo=1.0),
    P("veía siluetas inmóviles", p_insert, dict(amb="tren_marcha", tension=0.9, sfx=[(0.1, "susurros", 0.7)]),
      fn=ins.ventana_tunel, rojo=1.0, siluetas=1.0, zoom=1.1, vel=0.8),
    P("Entonces el tren se detuvo", p_vagon, dict(amb="frenazo", tension=0.8, sfx=[(0.0, "frenazo", 0.9)]),
      a=dict(z=1.0), b=dict(z=1.4), luces=0.8, velocidad=0.0,
      fx_extra=dict(sacudida=14)),
    P("Las puertas se abrieron", p_vagon, dict(amb="silencio_tunel", tension=0.8,
                                               sfx=[(0.1, "puertas_abren", 0.9)]),
      a=dict(x=0.6, y=1.3, z=4.7, yaw=-1.5708, f=700), b=dict(x=0.2), puertas=1.0, velocidad=0.0,
      luces=0.7),
    P("En el cartel de la estación", p_insert, dict(amb="silencio_tunel", tension=0.85,
                                                    sfx=[(0.3, "impacto", 0.7)]),
      fn=ins.cartel_san_miguel),
    P("SAN MIGUEL", p_insert, dict(amb="silencio_tunel", tension=0.9, sfx=[(0.0, "impacto", 0.8)]),
      fn=ins.cartel_san_miguel, fx_extra=dict(aberracion=3)),
    P("Me levanté para mirar mejor", puerta_desde_dentro, dict(amb="silencio_tunel", tension=0.8),
      viejo=1.0, rojo=0.7, nombre="SAN MIGUEL", luces=0.55, maquina=False, panel=False, reloj=False, avance=1.0),
    P("En el andén había varias personas", puerta_desde_dentro, dict(amb="silencio_tunel", tension=0.85),
      bryan=False, viejo=1.0, rojo=0.7, nombre="SAN MIGUEL", luces=0.55, maquina=False, panel=False, reloj=False,
      gente_fn=andén_gente, cam_b=dict(x=0.7)),
    P("Todas estaban mirando hacia el tren", fantasmas_cerca, dict(amb="silencio_tunel", tension=0.9,
                                                                   sfx=[(0.0, "drone_sube", 0.6)])),
    P("Una niña comenzó a caminar", nina_camina, dict(amb="caja_musica", tension=0.85)),
    P("Tenía un vestido blanco", nina_camina, dict(amb="caja_musica", tension=0.9), cerca=True),
    P("Cuando estuvo a pocos metros", nina_levanta, dict(amb="caja_musica", tension=0.95)),
    P("Y dijo mi nombre", nina_nombre, dict(amb="silencio", tension=0.2, sfx=[(0.15, "susurro", 1.0),
                                                                              (0.1, "impacto", 0.6)])),
    P("Me quedé helado", p_busto, dict(amb="silencio", tension=0.6),
      fondo="fantasma", expr="terror", parpado=False, aliento=1.0, zoom=(1.05, 1.18), rim=hx("#ff9a8a"),
      fx_extra=dict(niebla=0.3, niebla_color=(0.3, 0.22, 0.22))),
    P("La anciana me agarró del brazo", brazo_agarre, dict(amb="silencio_tunel", tension=0.9,
                                                           sfx=[(0.25, "agarre", 0.9)])),
    P("¡No respondas!", p_busto, dict(amb="silencio_tunel", tension=1.0, sfx=[(0.0, "impacto", 1.0)]),
      spec=A, fondo="fantasma", expr="enfado", habla=True, sacudida=1.0, r=300, zoom=(1.1, 1.2),
      rim=hx("#ff8a7a"), fx_extra=dict(rojo=0.06, aberracion=4)),
    P("Las puertas se cerraron de golpe", p_vagon, dict(amb="silencio_tunel", tension=0.9,
                                                        sfx=[(0.05, "golpe_puertas", 1.0)]),
      a=dict(x=0.6, y=1.3, z=4.7, yaw=-1.5708, f=700), puertas=0.0, velocidad=0.0,
      fx_extra=dict(sacudida=22)),
    P("Y el tren volvió a arrancar", p_insert, dict(amb="tren_arranca", tension=0.7),
      fn=ins.ventana_tunel, rojo=0.8, siluetas=1.0, vel=0.5),

    # ------------------------------------------------------------------ escena 4: la verdad de la anciana
    P("Me aparté de la anciana", p_vagon, dict(trans="negro", amb="tren_marcha", tension=0.5),
      a=dict(x=0.0, y=1.3, z=1.0), b=dict(z=2.2),
      gente=[dict(x=-1.15, y=0.46, z=5.6, tipo="perfil", spec=B, kw=dict(modo="sentado", expr="miedo")),
             dict(x=1.15, y=0.46, z=6.0, tipo="perfil", spec=A, alto=1.6,
                  kw=dict(modo="sentado", voltear=True, expr="serio"))]),
    P("¿Qué demonios está pasando aquí?", p_busto, dict(amb="tren_marcha", tension=0.6),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="enfado", habla=True, giro=0.25, sacudida=0.3),
    P("Ella me miró durante varios segundos", p_busto, dict(amb="tren_marcha", tension=0.65),
      spec=A, fondo=VAG, fondo_kw=dict(yaw=-1.5), expr="serio", parpado=False, zoom=(1.0, 1.15), giro=-0.2),
    P("Después comenzó a hablar", p_busto, dict(amb="tren_marcha", tension=0.6),
      spec=A, fondo=VAG, fondo_kw=dict(yaw=-1.5), expr="serio", giro=-0.2, habla=True, zoom=(1.08, 1.2)),
    P("Me reí nerviosamente", p_busto, dict(amb="tren_marcha", tension=0.45),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="sonrisa", giro=0.25, sacudida=0.4),
    P("Pensé que estaba loca", p_busto, dict(amb="tren_marcha", tension=0.45),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="neutral", giro=0.25, giro_fin=-0.3, mira=(0.3, 0), mira_fin=(-0.6, 0.2)),
    P("Pero entonces continuó", p_busto, dict(amb="tren_marcha", tension=0.6),
      spec=A, fondo=VAG, fondo_kw=dict(yaw=-1.5, luces=0.7), expr="serio", giro=-0.2, habla=True, r=280,
      zoom=(1.0, 1.1)),
    P("Hace treinta años, un tren desapareció", p_insert, dict(amb="tren_marcha", tension=0.7,
                                                               sfx=[(0.0, "papel", 0.6)]), fn=ins.periodico),
    P("Nunca encontraron al conductor", p_anden, dict(amb="tren_marcha", tension=0.75),
      a=dict(x=2.15, y=1.2, z=-4.0, yaw=0.0, pitch=0.02), b=dict(z=-1.6, y=1.5),
      tren_mov=lambda t, d: dict(z=0.0, puertas=0.0, luz=0.3, faro=0.2), luces=0.4,
      fx_extra=dict(luz=0.7)),
    P("Solo encontraron los billetes", p_insert, dict(amb="tren_marcha", tension=0.7), fn=ins.billetes),
    P("Sentí un escalofrío", p_busto, dict(amb="tren_marcha", tension=0.6, sfx=[(0.2, "escalofrio", 0.7)]),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="miedo", sacudida=0.7, aliento=1.0),
    P("¿Y qué tiene que ver eso conmigo?", p_busto, dict(amb="tren_marcha", tension=0.6),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="miedo", habla=True, giro=0.25),
    P("La anciana bajó la mirada", p_busto, dict(amb="tren_marcha", tension=0.65),
      spec=A, fondo=VAG, fondo_kw=dict(yaw=-1.5), expr="triste", mira=(0, 0.2), mira_fin=(0, 0.9), giro=-0.2),
    P("Porque todos los que suben", p_busto, dict(amb="tren_marcha", tension=0.8),
      spec=A, fondo=VAG, fondo_kw=dict(yaw=-1.5, luces=0.5), expr="serio", habla=True, giro=-0.15, mira=(0, 0.6),
      r=300, zoom=(1.0, 1.12), fx_extra=dict(luz=0.85)),
    P("Todos creen que todavía están vivos", p_busto, dict(amb="tren_marcha", tension=0.95,
                                                          sfx=[(0.0, "drone_sube", 0.9)]),
      spec=A, fondo=VAG, fondo_kw=dict(yaw=-1.5, luces=0.4), expr="serio", habla=True, mira=(0, 0.6),
      mira_fin=(0, 0), r=560, y=H * 0.46, zoom=(1.0, 1.25), parpado=False, fx_extra=dict(luz=0.8)),
    P("No pude responder", p_busto, dict(amb="silencio", tension=0.4),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="shock", parpado=False),
    P("Entonces miré mis manos", p_insert, dict(amb="tren_marcha", tension=0.55), fn=ins.manos, corte=0.0),
    P("Tenía un pequeño corte", p_insert, dict(amb="tren_marcha", tension=0.7), fn=ins.manos, corte=1.0,
      zoom=(1.0, 1.9)),
    P("Pero no había sangre", p_insert, dict(amb="latidos", tension=0.85, sfx=[(0.1, "impacto", 0.5)]),
      fn=ins.manos, corte=1.0, zoom=(2.4, 2.7), fx_extra=dict(luz=0.85)),
    P("Intenté recordar", p_busto, dict(amb="latidos", tension=0.75, sfx=[(0.5, "glitch", 0.6)]),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="miedo", mira=(-0.3, -0.5), zoom=(1.0, 1.1),
      fx_extra=dict(glitch=0.15)),
    P("Y de repente me di cuenta", p_busto, dict(amb="latidos", tension=0.85),
      fondo=VAG, fondo_kw=dict(yaw=1.5, luces=0.5), expr="terror", zoom=(1.05, 1.3), parpado=False,
      fx_extra=dict(luz=0.8)),
    P("No recordaba absolutamente nada", p_vagon, dict(amb="tren_marcha", tension=0.6),
      a=dict(x=0.0, y=1.5, z=4.5), b=dict(z=0.5, y=1.7), luces=0.45,
      gente=[dict(x=-1.15, y=0.46, z=7.0, tipo="perfil", spec=B, kw=dict(modo="sentado", expr="triste"))],
      fx_extra=dict(luz=0.75)),

    # ------------------------------------------------------------------ escena 5: el pasajero del túnel
    P("El tren comenzó a perder velocidad", p_insert, dict(trans="negro", amb="tren_frena", tension=0.6),
      fn=ins.ventana_tunel, vel=0.45),
    P("Las luces se apagaron", p_vagon, dict(amb="silencio", tension=0.7, sfx=[(0.3, "apagon", 1.0)]),
      a=dict(x=0.0, y=1.3, z=1.0), apagado=True, velocidad=0.3,
      gente=[dict(x=1.15, y=0.46, z=6.0, tipo="perfil", spec=A, alto=1.6,
                  kw=dict(modo="sentado", voltear=True, expr="serio"))],
      fx_extra=dict(luz=0.25)),
    P("Cuando volvieron", p_vagon, dict(amb="tren_marcha", tension=0.8, sfx=[(0.0, "chispazo", 0.8)]),
      a=dict(x=0.0, y=1.3, z=1.0), b=dict(z=1.3), velocidad=0.4),
    P("Su asiento estaba vacío", p_vagon, dict(amb="tren_marcha", tension=0.8),
      a=dict(x=-0.6, y=1.0, z=4.2, yaw=0.9), b=dict(x=-0.2, z=4.8), velocidad=0.4),
    P("Me levanté y caminé", p_vagon, dict(amb="tren_marcha", tension=0.65),
      a=dict(x=0.0, y=1.5, z=1.0), b=dict(z=3.0), velocidad=0.4,
      gente=lambda t, d, T: [dict(x=0.0, z=lerp(4.0, 8.0, t / d), spec=B, kw=dict(espalda=True, paso=T * 1.5))]),
    P("Entonces escuché tres golpes", p_busto, dict(amb="silencio", tension=0.5),
      fondo=VAG, expr="miedo", mira=(0.7, 0.0), parpado=False, zoom=(1.0, 1.1)),
    P("Toc", p_insert, dict(amb="silencio", tension=0.8, sfx=[(0.22, "golpe_cristal", 1.0)]),
      fn=ins.ventana_tunel, vel=0.35, golpes=(0.22,), fx_extra=dict(sacudida=10)),
    P("Toc", p_insert, dict(amb="silencio", tension=0.85, sfx=[(0.22, "golpe_cristal", 1.0)]),
      fn=ins.ventana_tunel, vel=0.35, golpes=(0.22,), zoom=1.12, fx_extra=dict(sacudida=12)),
    P("Toc", p_insert, dict(amb="silencio", tension=0.9, sfx=[(0.22, "golpe_cristal", 1.0)]),
      fn=ins.ventana_tunel, vel=0.35, golpes=(0.22,), zoom=1.25, fx_extra=dict(sacudida=14)),
    P("Miré hacia fuera", p_busto, dict(amb="tren_marcha", tension=0.7),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="miedo", giro=0.0, giro_fin=0.75, mira=(0, 0), mira_fin=(0.9, 0)),
    P("Había un hombre corriendo", p_insert, dict(amb="tren_marcha", tension=0.9, sfx=[(0.0, "pasos_corre", 0.7)]),
      fn=ins.ventana_tunel, vel=0.6, doble=dict(alto=900, dy=-200)),
    P("Llevaba la misma ropa que yo", p_insert, dict(amb="tren_marcha", tension=0.9),
      fn=ins.ventana_tunel, vel=0.6, doble=dict(alto=1500, dy=380)),
    P("Tenía mi cara", p_busto, dict(amb="tren_marcha", tension=0.9, sfx=[(0.0, "impacto", 0.5)]),
      fondo="tunel", expr="terror", r=210, zoom=(1.0, 1.05), sacudida=0.6, parpado=False,
      fx_extra=dict(niebla=0.3)),
    P("Mi pelo", p_busto, dict(amb="tren_marcha", tension=0.92, sfx=[(0.0, "impacto", 0.5)]),
      fondo="tunel", expr="terror", r=300, y=H * 0.47, zoom=(1.0, 1.05), sacudida=0.6, parpado=False),
    P("Mis ojos", p_busto, dict(amb="tren_marcha", tension=0.95, sfx=[(0.0, "impacto", 0.6)]),
      fondo="tunel", expr="terror", r=620, y=H * 0.5, zoom=(1.0, 1.06), sacudida=0.6, parpado=False),
    P("Pero su expresión era de auténtico terror", p_busto, dict(amb="tren_marcha", tension=0.95),
      fondo="tunel", expr="terror", r=330, sacudida=1.2, habla=False, zoom=(1.0, 1.1),
      fx_extra=dict(aberracion=3)),
    P("Golpeaba el cristal", p_insert, dict(amb="tren_marcha", tension=1.0,
                                            sfx=[(0.1, "golpe_cristal", 0.7), (0.6, "golpe_cristal", 0.75),
                                                 (1.1, "golpe_cristal", 0.8), (1.6, "golpe_cristal", 0.8),
                                                 (2.1, "golpe_cristal", 0.85), (2.6, "golpe_cristal", 0.9)]),
      fn=ins.ventana_tunel, vel=0.6, doble=dict(alto=1500, dy=380, mano=1.0, habla=1.0),
      golpes=(0.1, 0.6, 1.1, 1.6, 2.1, 2.6), fx_extra=dict(sacudida=6)),
    P("Me acerqué lentamente", p_busto, dict(amb="tren_marcha", tension=0.8),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="miedo", giro=0.7, mira=(0.9, 0), zoom=(0.9, 1.35)),
    P("Y entonces pude leer sus labios", p_busto, dict(amb="latidos", tension=0.9),
      fondo="tunel", expr="neutral", r=900, y=H * 0.5 - 0.68 * 900 * KH, habla=True, parpado=False, zoom=(1.0, 1.08)),
    P("¡NO BAJES!", p_insert, dict(amb="silencio", tension=1.0, sfx=[(0.0, "impacto", 1.0), (0.0, "grito", 0.6)]),
      fn=ins.ventana_tunel, vel=0.6, doble=dict(alto=1500, dy=380, mano=1.0, habla=1.0, expr="terror"),
      letrero=1.0, luz_int=0.5, fx_extra=dict(sacudida=18, aberracion=6, rojo=0.08)),
    P("Retrocedí horrorizado", p_busto, dict(amb="tren_marcha", tension=0.85),
      fondo=VAG, fondo_kw=dict(yaw=1.5), expr="terror", zoom=(1.3, 0.85), sacudida=0.8, parpado=False),
    P("En ese instante, el tren frenó", p_vagon, dict(amb="frenazo", tension=0.9, sfx=[(0.0, "frenazo", 1.0)]),
      a=dict(z=1.0, roll=0.0), b=dict(z=0.4), velocidad=0.2, rojo=0.3, fx_extra=dict(sacudida=24)),
    P("Las puertas comenzaron a abrirse", p_vagon, dict(amb="silencio_tunel", tension=0.8,
                                                        sfx=[(0.1, "puertas_abren", 0.8)]),
      a=dict(x=0.6, y=1.3, z=4.7, yaw=-1.5708, f=700), puertas=0.6, velocidad=0.0, luces=0.7),
    P("Y una voz por megafonía", p_insert, dict(amb="silencio_tunel", tension=0.8, sfx=[(0.2, "estatica", 0.6)]),
      fn=ins.megafonia),
    P("Próxima parada", p_insert, dict(amb="silencio_tunel", tension=0.9, sfx=[(0.0, "ding_dong", 0.8)]),
      fn=ins.megafonia, texto_on=1.0),

    # ------------------------------------------------------------------ escena 6: el descubrimiento
    P("Las puertas se abrieron", puerta_desde_dentro, dict(trans="negro", amb="oscuro", tension=0.8),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, banco=False,
      cam_a=dict(niebla=(0.01, 0.012, 0.014)), avance=0.6),
    P("Al otro lado había un andén", puerta_desde_dentro, dict(amb="oscuro", tension=0.85),
      bryan=False, oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, banco=False,
      cam_a=dict(niebla=(0.01, 0.012, 0.014)), cam_b=dict(x=0.5)),
    P("Solo una farola", p_anden, dict(amb="oscuro", tension=0.75),
      a=dict(x=-1.0, y=1.6, z=0.0, yaw=-0.1, niebla=(0.01, 0.012, 0.014), densidad=0.07), b=dict(z=2.0),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, farola=(10.0, -2.5)),
    P("Y debajo de ella había un cartel", p_anden, dict(amb="oscuro", tension=0.8),
      a=dict(x=-1.4, y=1.6, z=3.0, yaw=-0.12, niebla=(0.01, 0.012, 0.014), densidad=0.07), b=dict(z=6.0),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, farola=(10.0, -2.5),
      cartel_farola=lambda c, cam, fx_, fz, T: billboard(c, cam, (fx_ + 0.5, 0.9, fz), 1.0,
                                                         lambda x, y, px: ins.cartel_accidente(c, x, y - px * 0.5,
                                                                                               px / 300, 1.0, 0.9))),
    P("Decía", p_insert, dict(amb="oscuro", tension=0.9, sfx=[(0.6, "impacto", 0.9)]),
      fn=lambda c, t, T, d: (ins.fondo(c, hx("#050607")), cono_luz(c, W / 2, 0, 200, 1500, H, hx("#ffd9a0"), 1.0),
                             ins.cartel_accidente(c, W / 2, H * 0.5, 1.12 + 0.05 * t / d),
                             dict(niebla=0.4, niebla_color=(0.4, 0.35, 0.3)))[-1]),
    P("Me acerqué lentamente", p_anden, dict(amb="oscuro", tension=0.8, sfx=[(0.0, "pasos", 0.6)]),
      a=dict(x=-1.6, y=1.7, z=1.0, yaw=-0.1, niebla=(0.01, 0.012, 0.014), densidad=0.07), b=dict(z=2.5),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, farola=(10.0, -2.5),
      gente_fn=lambda t, d, T: [dict(x=-1.8, z=lerp(4.0, 7.5, t / d), spec=B, kw=dict(espalda=True, paso=T * 1.4))]),
    P("Debajo del cartel había una fotografía", p_insert, dict(amb="oscuro", tension=0.75),
      fn=lambda c, t, T, d: (ins.fondo(c, hx("#070605")),
                             ins.foto_accidente(c, W / 2 + lerp(120, -120, ss(t / d)), H * 0.47,
                                                900 * (1.0 + 0.25 * t / d), 620 * (1.0 + 0.25 * t / d), T),
                             resplandor(c, W / 2, -100, 1100, hx("#ffd9a0"), 0.5),
                             dict(niebla=0.25, niebla_color=(0.4, 0.35, 0.3)))[-1]),
    P("Varias ambulancias", p_insert, dict(amb="oscuro", tension=0.75),
      fn=lambda c, t, T, d: (ins.fondo(c, hx("#070605")),
                             ins.foto_accidente(c, W / 2 + 380, H * 0.38, 1700, 1170, T),
                             dict(niebla=0.25, niebla_color=(0.4, 0.35, 0.3)))[-1]),
    P("Y decenas de personas", p_insert, dict(amb="oscuro", tension=0.8),
      fn=lambda c, t, T, d: (ins.fondo(c, hx("#070605")),
                             ins.foto_accidente(c, W / 2 + lerp(300, -300, ss(t / d)), H * 0.2, 1900, 1300, T),
                             dict(niebla=0.25, niebla_color=(0.4, 0.35, 0.3)))[-1]),
    P("Miré la fecha", p_insert, dict(amb="oscuro", tension=0.8), fn=foto_fecha),
    P("Era exactamente treinta años antes", p_insert, dict(amb="oscuro", tension=0.85,
                                                           sfx=[(0.3, "impacto", 0.6)]), fn=movil_fecha),
    P("Entonces vi algo que me dejó", p_busto, dict(amb="silencio", tension=0.7),
      fondo="oscuro", expr="shock", rim=hx("#ffd9a0"), zoom=(1.0, 1.15), parpado=False,
      fx_extra=dict(niebla=0.3, niebla_color=(0.4, 0.35, 0.3))),
    P("Entre las fotografías de las víctimas", p_insert, dict(amb="oscuro", tension=0.85),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=0.25 * ss(t / d))),
    P("La misma ropa", p_insert, dict(amb="latidos", tension=0.9, sfx=[(0.0, "impacto", 0.5)]),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=lerp(0.4, 0.65, ss(t / d)))),
    P("La misma cara", p_insert, dict(amb="latidos", tension=0.95, sfx=[(0.0, "impacto", 0.6)]),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=lerp(0.75, 0.95, ss(t / d)))),
    P("Y debajo de mi fotografía", p_insert, dict(amb="latidos", tension=0.95),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=1.0)),
    P("El mío", p_insert, dict(amb="silencio", tension=1.0, sfx=[(0.0, "impacto", 1.0)]),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=1.0, revela_nombre=1.0),
      fx_extra=dict(aberracion=4)),
    P("Con una fecha de fallecimiento", p_insert, dict(amb="latidos", tension=0.95),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=1.0, revela_nombre=1.0)),
    P("14 de noviembre de 1996", p_insert, dict(amb="silencio", tension=1.0, sfx=[(0.0, "impacto", 1.0)]),
      fn=lambda c, t, T, d: ins.tablon_victimas(c, t, T, d, foco=1.0, revela_nombre=1.0, revela_fecha=1.0),
      fx_extra=dict(aberracion=5, rojo=0.15)),
    P("Entonces recordé el accidente", p_busto, dict(amb="latidos", tension=0.9),
      fondo="oscuro", expr="miedo", rim=hx("#ffd9a0"), estados=[(1.0, dict(expr="terror"))], zoom=(1.0, 1.2),
      fx_extra=dict(glitch=0.2)),
    P("El ruido", p_insert, dict(amb="caos", tension=1.0, sfx=[(0.0, "estruendo", 1.0)]),
      fn=ins.flashback, fase="ruido"),
    P("Los cristales rompiéndose", p_insert, dict(amb="caos", tension=1.0, sfx=[(0.0, "cristales", 1.0)]),
      fn=ins.flashback, fase="cristales"),
    P("Los gritos", p_insert, dict(amb="caos", tension=1.0, sfx=[(0.0, "gritos", 0.9)]),
      fn=ins.flashback, fase="gritos"),
    P("Y después… nada", p_insert, dict(amb="nada", tension=0.0), fn=ins.flashback, fase="nada"),
    P("Yo no había perdido el último tren", p_anden, dict(trans="negro", amb="oscuro", tension=0.35),
      a=dict(x=-1.4, y=1.7, z=3.0, yaw=-0.12, niebla=(0.01, 0.012, 0.014), densidad=0.07), b=dict(z=4.5),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, farola=(10.0, -2.5),
      gente_fn=lambda t, d, T: [dict(x=-2.0, z=9.6, spec=B, kw=dict(expr="triste", mira=(0, 0.6)))]),
    P("Yo había muerto en aquel accidente", p_busto, dict(amb="oscuro", tension=0.45),
      fondo="oscuro", expr="triste", rim=hx("#ffd9a0"), lagrimas=0.8, mira=(0, 0.4), alfa=0.8,
      fx_extra=dict(niebla=0.45, niebla_color=(0.4, 0.35, 0.3))),

    # ------------------------------------------------------------------ escena 7: el final
    P("De repente, escuché la voz de la anciana", p_busto, dict(trans="corte", amb="oscuro", tension=0.5,
                                                                sfx=[(0.3, "susurro", 0.5)]),
      fondo="oscuro", expr="miedo", lagrimas=0.5, giro=0.0, giro_fin=-0.6, mira=(0, 0), mira_fin=(-0.8, 0),
      rim=hx("#ffd9a0")),
    P("Ya puedes descansar", p_vagon, dict(amb="calido", tension=0.15),
      a=dict(x=0.0, y=1.4, z=1.0), b=dict(z=3.0), luz_col=CALIDO, velocidad=0.0,
      gente=[dict(x=0.0, z=15.0, spec=A, alto=1.62, kw=dict(expr="dulce"))],
      fx_extra=dict(niebla=0.3, niebla_color=(0.6, 0.5, 0.35), gradacion=0.4)),
    P("Me giré", p_busto, dict(amb="calido", tension=0.2),
      fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="miedo", lagrimas=0.5, giro=-0.6, giro_fin=0.0,
      rim=hx("#ffd6a0"), calido=0.4),
    P("Estaba al final del vagón", p_vagon, dict(amb="calido", tension=0.2),
      a=dict(x=0.0, y=1.4, z=3.0), b=dict(z=8.0), luz_col=CALIDO, velocidad=0.0,
      gente=[dict(x=0.0, z=15.0, spec=A, alto=1.62, kw=dict(expr="dulce"))],
      fx_extra=dict(niebla=0.35, niebla_color=(0.6, 0.5, 0.35), gradacion=0.4)),
    P("Pero esta vez no parecía una anciana", p_busto, dict(amb="calido", tension=0.15),
      spec=A, fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="dulce", calido=0.5, rim=hx("#ffd6a0"),
      fx_extra=dict(gradacion=0.4)),
    P("Su rostro había cambiado", morph_madre, dict(amb="calido", tension=0.1, sfx=[(0.2, "brillo", 0.7)])),
    P("Era mucho más joven", p_busto, dict(amb="calido", tension=0.05),
      spec=MADRE, fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="dulce", calido=0.6, rim=hx("#ffd6a0"),
      fx_extra=dict(gradacion=0.4)),
    P("Y entonces la reconocí", p_busto, dict(amb="calido", tension=0.05),
      fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="triste", lagrimas=0.7, calido=0.5, rim=hx("#ffd6a0"),
      zoom=(1.0, 1.12), fx_extra=dict(gradacion=0.4)),
    P("Era mi madre", p_busto, dict(amb="calido", tension=0.0),
      spec=MADRE, fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="dulce", calido=0.8, rim=hx("#ffd6a0"),
      r=300, zoom=(1.0, 1.1), fx_extra=dict(gradacion=0.3)),
    P("La mujer que había muerto", p_insert, dict(amb="calido", tension=0.0), fn=ins.foto_madre),
    P("Tenía los ojos llenos de lágrimas", p_busto, dict(amb="calido", tension=0.0),
      spec=MADRE, fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="triste", lagrimas=1.0, calido=0.7,
      rim=hx("#ffd6a0"), r=320, zoom=(1.0, 1.1), fx_extra=dict(gradacion=0.3)),
    P("Llevo treinta años esperándote", p_busto, dict(amb="calido", tension=0.0),
      spec=MADRE, fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="dulce", lagrimas=1.0, calido=0.7, habla=True,
      rim=hx("#ffd6a0"), r=320, zoom=(1.1, 1.16), fx_extra=dict(gradacion=0.3)),
    P("Intenté acercarme", p_anden, dict(amb="calido", tension=0.3, sfx=[(1.6, "pitidos_puerta", 0.5)]),
      a=dict(x=-3.95, y=1.6, z=6.0, yaw=1.5708, niebla=(0.01, 0.012, 0.014), densidad=0.06), b=dict(x=-3.7),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, banco=False,
      tren_mov=lambda t, d: dict(z=3.5, puertas=lerp(1.0, 0.45, ss(pr(t, d * 0.4, d * 0.6))), luz=1.0, faro=0.0,
                                 ventanas_col=hx("#ffd9a0")),
      gente_fn=lambda t, d, T: [dict(x=lerp(-2.5, -1.3, ss(t / d)), z=6.4, spec=B,
                                     kw=dict(espalda=True, paso=T * 1.3))],
      fx_extra=dict(gradacion=0.4)),
    P("Ella extendió la mano", p_vagon, dict(amb="calido", tension=0.1),
      a=dict(x=0.0, y=1.45, z=3.5), b=dict(z=5.0), luz_col=CALIDO, velocidad=0.0,
      gente=[dict(x=0.0, z=8.0, spec=MADRE, alto=1.62, kw=dict(expr="dulce", brazos="extiende", mano_ext=1.0,
                                                               lagrimas=0.8))],
      fx_extra=dict(niebla=0.35, niebla_color=(0.6, 0.5, 0.35), gradacion=0.4)),
    P("Ven conmigo", manos_unen, dict(amb="calido", tension=0.0)),
    P("Y por primera vez en toda la noche", p_busto, dict(amb="calido", tension=0.0),
      fondo=VAG, fondo_kw=dict(luz_col=CALIDO), expr="dulce", lagrimas=0.6, calido=0.9, rim=hx("#ffd6a0"),
      estados=[(3.0, dict(expr="sonrisa"))], zoom=(1.0, 1.1), fx_extra=dict(gradacion=0.3)),
    P("El tren arrancó", p_anden, dict(amb="tren_arranca", tension=0.15),
      a=dict(x=-3.2, y=1.5, z=6.0, yaw=0.9, niebla=(0.01, 0.012, 0.014), densidad=0.05), b=dict(yaw=0.5),
      oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, tren_mov=tren_sale_calido),
    P("Las luces se apagaron", p_insert, dict(amb="nada", tension=0.0, sfx=[(0.1, "apagon", 0.7)]),
      fn=lambda c, t, T, d: (ins.fondo(c, hx("#000000")),
                             resplandor(c, W / 2, H * 0.47, 300 * (1 - pr(t, 0, 0.8)) + 1, hx("#ffd9a0"),
                                        1 - pr(t, 0, 0.8)), dict(niebla=0.0))[-1]),
    P("Y todo quedó en silencio", p_insert, dict(amb="nada", tension=0.0),
      fn=lambda c, t, T, d: (ins.fondo(c, hx("#000000")), dict(niebla=0.0, grano=0.02))[-1]),

    # ------------------------------------------------------------------ última escena: giro final
    P("A la mañana siguiente", p_anden, dict(trans="negro", amb="anden_dia", tension=0.15),
      a=dict(x=-2.2, y=1.65, z=-3.0, yaw=0.12), b=dict(z=-1.5), mañana=1.0, luces=1.0,
      gente_fn=lambda t, d, T: [dict(x=-2.4, z=7.5, spec=GUARDIA, kw=dict(giro=0.3, mira=(0.4, 0))),
                                dict(x=-1.4, z=7.2, spec=HOMBRE, kw=dict(giro=-0.4, mira=(-0.5, 0),
                                                                         habla=boca(T)))],
      fx_extra=dict(niebla=0.25, gradacion=0.7)),
    P("y preguntó al trabajador", p_anden, dict(amb="anden_dia", tension=0.15),
      a=dict(x=-0.6, y=1.6, z=4.0, yaw=-0.35), b=dict(z=4.6), mañana=1.0, luces=1.0,
      gente_fn=lambda t, d, T: [dict(x=-2.4, z=7.5, spec=GUARDIA, kw=dict(giro=0.3, mira=(0.4, 0))),
                                dict(x=-1.4, z=7.2, spec=HOMBRE, kw=dict(giro=-0.4, mira=(-0.5, 0),
                                                                         habla=boca(T)))],
      fx_extra=dict(niebla=0.25, gradacion=0.7)),
    P("El trabajador negó con la cabeza", p_busto, dict(amb="anden_dia", tension=0.15),
      spec=GUARDIA, fondo="anden", fondo_kw=dict(mañana=1.0), expr="serio", giro=0.0,
      estados=[(0.3 + k * 0.28, dict(giro=0.45 * (-1) ** k)) for k in range(6)] + [(2.0, dict(giro=0.0))],
      fx_extra=dict(gradacion=0.7)),
    P("Pero cuando revisaron las cámaras", sala_cctv, dict(amb="sala", tension=0.4)),
    P("A las 3:17, un tren había entrado", p_cctv, dict(amb="sala", tension=0.5),
      contenido=lambda t, d, T: cctv_anden("llega", t, d, T)),
    P("Las puertas se habían abierto", p_cctv, dict(amb="sala", tension=0.55),
      contenido=lambda t, d, T: cctv_anden("abre", t, d, T), hora="03:17:41"),
    P("Y un hombre había subido", p_cctv, dict(amb="sala", tension=0.6),
      contenido=lambda t, d, T: cctv_anden("sube", t, d, T), hora="03:17:46"),
    P("El trabajador amplió la imagen", p_cctv, dict(amb="sala", tension=0.65, sfx=[(0.1, "zoom_digital", 0.6)]),
      contenido=lambda t, d, T: cctv_anden("sube", t + 2.5, d, T), zoom=(1.0, 2.2), foco=(0.47, 0.55),
      pixel=4, hora="03:17:48"),
    P("Era yo", p_cctv, dict(amb="silencio", tension=0.6, sfx=[(0.0, "impacto", 0.6)]),
      contenido=lambda t, d, T: cctv_anden("sube", 3.0, d, T), zoom=(2.6, 2.8), foco=(0.47, 0.55), pixel=6,
      hora="03:17:48"),
    P("Entonces observó algo todavía más extraño", p_busto, dict(amb="sala", tension=0.75),
      spec=GUARDIA, fondo="cctv", expr="miedo", rim=hx("#7fb8ff"), zoom=(1.0, 1.15),
      fx_extra=dict(gradacion=0.6)),
    P("En el reflejo de la ventana", p_cctv, dict(amb="sala", tension=0.85, sfx=[(0.5, "drone_sube", 0.7)]),
      contenido=lambda t, d, T: cctv_reflejo(t, d, T), zoom=(1.0, 1.3), foco=REFLEJO, pixel=3,
      hora="03:17:52"),
    P("Sonriendo", p_cctv, dict(amb="silencio", tension=0.95, sfx=[(0.0, "impacto", 0.9)]),
      contenido=lambda t, d, T: cctv_reflejo(d, d, T, sonrisa=True), zoom=(2.2, 2.5), foco=REFLEJO,
      pixel=4, hora="03:17:53"),
    P("Y antes de que la grabación terminara", p_cctv, dict(amb="sala", tension=0.85),
      contenido=lambda t, d, T: cctv_reflejo(d, d, T, sonrisa=True), zoom=(1.0, 1.0), pixel=2,
      hora="03:17:55"),
    P("la cámara captó algo escrito", p_insert, dict(amb="tren_marcha", tension=0.9),
      fn=lambda c, t, T, d: ins.cristal_escrito(c, t, T, d, progreso=0.18 * ss(t / d))),
    P("UNO MÁS PARA EL PRÓXIMO VIAJE", p_insert, dict(amb="tren_marcha", tension=1.0,
                                                      sfx=[(0.0, "impacto", 0.8), (0.0, "chirrido_dedo", 0.7)]),
      fn=lambda c, t, T, d: ins.cristal_escrito(c, t, T, d, progreso=lerp(0.18, 1.0, eo(cl(t / max(0.5, d - 0.6)))))),
    P("FIN", p_insert, dict(trans="negro", amb="nada", tension=0.3, sfx=[(0.2, "impacto", 0.7)]), fn=ins.fin),
]


# ===================================================================== resolución de tiempos
def resolver():
    planos = []
    _cursor[0] = 0
    for ancla, fn, kw, op in PLANOS:
        i = buscar(ancla)
        _cursor[0] = i + 1
        t0 = 0.0 if not planos else max(PAL[i]["s"] - 0.18, planos[-1]["t0"] + 0.3)
        planos.append(dict(t0=t0, fn=fn, kw=kw, op=op, ancla=ancla, idx=i))
    fin_total = DUR_VOZ + 3.0
    for k, p in enumerate(planos):
        p["t1"] = planos[k + 1]["t0"] if k + 1 < len(planos) else fin_total
    return planos, fin_total


PLANOS_T, DURACION = resolver()


# ===================================================================== subtítulos
def _frases():
    """Agrupa las palabras en bloques cortos para los subtítulos."""
    bloques = []
    lineas = []
    actual = []
    for p in PAL:
        if p["nl"] and actual:
            lineas.append(actual)
            actual = []
        actual.append(p)
    if actual:
        lineas.append(actual)
    for ln in lineas:
        txt = " ".join(w["w"] for w in ln)
        letras = [ch for ch in txt if ch.isalpha()]
        if letras and sum(ch.isupper() for ch in letras) / len(letras) > 0.8 and len(ln) > 1:
            continue  # carteles que ya se leen en pantalla
        if ln[0]["escena"] == 0 or txt.strip() in ("FIN.",):
            continue
        dialogo = txt.startswith("—") or txt.startswith("«")
        grupo = []
        for w in ln:
            grupo.append(w)
            largo = len(" ".join(x["w"] for x in grupo))
            if len(grupo) >= 5 or largo > 24 or w["w"][-1] in ",.:;?!…" and len(grupo) >= 2:
                bloques.append((grupo, dialogo))
                grupo = []
        if grupo:
            if bloques and len(grupo) == 1 and bloques[-1][0][-1]["nl"] is False and len(bloques[-1][0]) < 4 \
                    and bloques[-1][0][0] in ln:
                bloques[-1] = (bloques[-1][0] + grupo, dialogo)
            else:
                bloques.append((grupo, dialogo))
    out = []
    for k, (g, dl) in enumerate(bloques):
        s = g[0]["s"] - 0.08
        e = g[-1]["e"] + 0.35
        if k + 1 < len(bloques):
            e = min(e, bloques[k + 1][0][0]["s"] - 0.1)
        out.append(dict(s=s, e=max(e, s + 0.4), palabras=g, dialogo=dl))
    return out


FRASES = _frases()


def subtitulos(c, T):
    for f in FRASES:
        if f["s"] <= T <= f["e"]:
            ws = f["palabras"]
            txt = " ".join(w["w"] for w in ws)
            tam = 56 if HOR else 64
            fuente_ = "Inter"
            c.select_font_face(fuente_, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            c.set_font_size(tam)
            total = c.text_extents(txt).x_advance
            esp = c.text_extents(" ").x_advance
            if total > W - 120:
                tam = tam * (W - 120) / total
                c.set_font_size(tam)
                total = c.text_extents(txt).x_advance
                esp = c.text_extents(" ").x_advance
            a_in = cl((T - f["s"]) / 0.15)
            a_out = cl((f["e"] - T) / 0.15)
            alfa = min(a_in, a_out)
            x = W / 2 - total / 2
            y = H * (0.9 if HOR else 0.775)
            rojo = "BAJES" in txt
            col_base = hx("#ff5b4f") if rojo else (hx("#cfe6ff") if f["dialogo"] else hx("#f4f6f7"))
            for w in ws:
                ancho = c.text_extents(w["w"]).x_advance
                dicha = T >= w["s"] - 0.05
                a = alfa * (1.0 if dicha else 0.32)
                c.move_to(x, y)
                c.text_path(w["w"])
                c.set_line_width(9)
                c.set_line_join(cairo.LINE_JOIN_ROUND)
                src(c, (0, 0, 0, 0.75 * a))
                c.stroke_preserve()
                src(c, mul(col_base, 1, a))
                c.fill()
                x += ancho + esp
            return
