"""Personajes dibujados con cairo: Bryan, la anciana/madre, la niña, el guardia y las sombras.

Convenciones: `cara()` dibuja una cabeza de frente centrada en (0,0) con radio 1 (se escala
fuera). `figura()` dibuja el cuerpo entero con los pies en (x, y) y una altura dada.
"""
import math

import cairo

from motor import (cl, ei, eo, fbm1, hash1, hx, lerp, lerpc, lgrad, mul, rgrad, rr, src, tf)

# ----------------------------------------------------------------- fichas
BRYAN = dict(
    nombre="bryan", piel=hx("#d9a98c"), piel_sombra=hx("#9c6a55"), pelo=hx("#231915"), pelo_luz=hx("#4a362b"),
    estilo_pelo="despeinado", ojos=hx("#3b2a20"), cejas=hx("#1d1410"), torso=hx("#6e1c28"), torso_luz=hx("#9a2c3a"),
    capucha=True, piernas=hx("#262e40"), zapatos=hx("#b9b9b4"), barba=0.22, labios=hx("#a0675a"),
)
ANCIANA = dict(
    nombre="anciana", piel=hx("#ddd6d0"), piel_sombra=hx("#9d9a9c"), pelo=hx("#e9e9ea"), pelo_luz=hx("#ffffff"),
    estilo_pelo="mono", ojos=hx("#b7c9d2"), cejas=hx("#c9c9c9"), torso=hx("#2c3533"), torso_luz=hx("#46524f"),
    chal=hx("#1c2120"), falda=hx("#252b2a"), zapatos=hx("#151515"), arrugas=1.0, labios=hx("#a28d8d"),
    ojos_brillo=0.6, boca_max=0.5,
)
MADRE = dict(ANCIANA, nombre="madre", piel=hx("#e6bea6"), piel_sombra=hx("#a8786a"), pelo=hx("#4a2e20"),
             pelo_luz=hx("#7a4c35"), estilo_pelo="suelto", ojos=hx("#5a4030"), cejas=hx("#3a2418"), arrugas=0.0,
             labios=hx("#b86f66"), ojos_brillo=0.0, boca_max=0.5)
NINA = dict(
    nombre="nina", piel=hx("#c9cfd3"), piel_sombra=hx("#6f777c"), ojeras=0.9, ojos_negros=True, pelo=hx("#0e0d0f"), pelo_luz=hx("#2a2629"),
    estilo_pelo="largo", ojos=hx("#0a0a0a"), cejas=hx("#111111"), torso=hx("#dcdcd8"), torso_luz=hx("#f4f4f0"),
    vestido=True, piernas=hx("#c9c6c4"), zapatos=hx("#2a2a2a"), labios=hx("#8c7a7a"),
)
GUARDIA = dict(
    nombre="guardia", piel=hx("#c8957a"), piel_sombra=hx("#8a5d4a"), pelo=hx("#3a3836"), pelo_luz=hx("#5a5856"),
    estilo_pelo="corto", ojos=hx("#2e2a26"), cejas=hx("#2a2622"), torso=hx("#1f2a3c"), torso_luz=hx("#33425c"),
    chaleco=hx("#a3aa36"), gorra=hx("#151d2b"), piernas=hx("#1a2232"), zapatos=hx("#111111"), barba=0.5,
    bigote=True, labios=hx("#8f5f52"),
)
HOMBRE = dict(
    nombre="hombre", piel=hx("#c79a82"), piel_sombra=hx("#8a6150"), pelo=hx("#5b5650"), pelo_luz=hx("#7c766f"),
    estilo_pelo="corto", ojos=hx("#2e2a26"), cejas=hx("#4a4540"), torso=hx("#5a5f66"), torso_luz=hx("#777d85"),
    abrigo=True, piernas=hx("#2a2c30"), zapatos=hx("#1a1a1a"), barba=0.1, labios=hx("#93665a"),
)
SOMBRA = dict(
    nombre="sombra", piel=hx("#8d9599"), piel_sombra=hx("#4d5558"), pelo=hx("#0b0d0e"), pelo_luz=hx("#1a1e20"),
    estilo_pelo="corto", ojos=hx("#000000"), cejas=hx("#0b0d0e"), torso=hx("#14191b"), torso_luz=hx("#1f2629"),
    abrigo=True, piernas=hx("#101415"), zapatos=hx("#080808"), labios=hx("#3a3f42"), sin_rostro=True,
)


def sombrear(c, x0, y0, x1, y1, fuerza=0.45, col=(0, 0, 0)):
    """Rellena el camino actual con un degradado de sombra (sin consumirlo)."""
    c.set_source(lgrad(x0, y0, x1, y1, [(0, col + (0,)), (1, col + (fuerza,))]))
    c.fill_preserve()


def borde_luz(c, col, ancho, alfa):
    c.set_line_width(ancho)
    src(c, mul(col, 1, alfa))
    c.stroke_preserve()


# ----------------------------------------------------------------- cara de frente
def _ojo(c, x, y, spec, abierto, mira, expr, lado, giro):
    sx = 1 - 0.35 * max(0, giro * lado)  # el ojo del lado al que gira se estrecha
    rx, ry = 0.2 * sx, 0.135
    miedo = expr in ("miedo", "terror", "shock")
    if miedo:
        ry *= 1.25
        rx *= 1.05
    ry *= abierto
    with tf(c, x, y, sx=1, sy=1):
        if ry < 0.012:
            c.move_to(-rx, 0)
            c.curve_to(-rx * 0.4, 0.03, rx * 0.4, 0.03, rx, 0)
            c.set_line_width(0.035)
            src(c, mul(spec["cejas"], 1, 0.9))
            c.stroke()
            return
        # cuenca sombreada
        c.save()
        c.scale(rx * 1.35, ry * 1.6 + 0.04)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        src(c, mul(spec["piel_sombra"], 0.9 if not spec.get("ojeras") else 0.5, spec.get("ojeras", 0.35)))
        c.fill()
        # esclerótica
        c.save()
        c.scale(rx, ry)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        src(c, hx("#0b0b0d") if spec.get("ojos_negros") else (hx("#efeae4") if spec["nombre"] != "sombra" else hx("#202020")))
        c.fill_preserve()
        c.save()
        c.clip()
        # iris
        ir = 0.095 if not miedo else 0.075
        ix, iy = mira[0] * rx * 0.55, mira[1] * ry * 0.5
        c.arc(ix, iy, ir, 0, 2 * math.pi)
        src(c, spec["ojos"])
        c.fill()
        if spec.get("ojos_brillo", 0) > 0:
            c.arc(ix, iy, ir * 0.9, 0, 2 * math.pi)
            c.set_source(rgrad(ix, iy, 0, ir, [(0, hx("#e8f6ff", 0.9 * spec["ojos_brillo"])),
                                                (1, hx("#9fc4d8", 0.0))]))
            c.fill()
        c.arc(ix, iy, ir * (0.45 if not miedo else 0.32), 0, 2 * math.pi)
        src(c, hx("#050505"))
        c.fill()
        c.arc(ix - ir * 0.35, iy - ir * 0.4, ir * 0.22, 0, 2 * math.pi)
        src(c, hx("#ffffff", 0.85))
        c.fill()
        # párpado superior proyecta sombra
        c.rectangle(-rx, -ry, 2 * rx, ry * 0.45)
        src(c, (0, 0, 0, 0.18))
        c.fill()
        c.restore()
        # línea del párpado
        c.save()
        c.scale(rx, ry)
        c.arc(0, 0, 1, math.pi * 1.05, math.pi * 1.95)
        c.restore()
        c.set_line_width(0.04)
        src(c, mul(spec["cejas"], 0.8, 0.95))
        c.stroke()


def _ceja(c, x, y, spec, expr, lado):
    ang = {"neutral": 0.0, "miedo": -0.28, "terror": -0.38, "shock": -0.3, "triste": -0.35, "serio": 0.12,
           "enfado": 0.3, "sonrisa": -0.05, "inquietante": 0.18, "dulce": -0.15}.get(expr, 0.0)
    alto = {"miedo": -0.06, "terror": -0.1, "shock": -0.12, "triste": -0.02}.get(expr, 0.0)
    with tf(c, x, y + alto, r=-ang * lado):
        c.move_to(-0.2, 0.02)
        c.curve_to(-0.08, -0.06, 0.08, -0.06, 0.21, 0.0)
        c.set_line_width(0.058 if spec["nombre"] in ("bryan", "guardia") else 0.045)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        src(c, spec["cejas"])
        c.stroke()


def _boca(c, x, y, spec, expr, habla):
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    labio = spec.get("labios", hx("#9a6a5c"))
    abre = habla * spec.get("boca_max", 1.0)
    if expr in ("terror", "shock"):
        abre = max(abre, 0.65 if expr == "terror" else 0.4)
    if abre > 0.05:
        w, h = 0.2 + 0.05 * abre, 0.05 + 0.2 * abre
        c.save()
        c.translate(x, y + h * 0.3)
        c.scale(w, h)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        src(c, hx("#2a0f10"))
        c.fill_preserve()
        c.set_line_width(0.03)
        src(c, labio)
        c.stroke()
        if abre > 0.3:  # dientes
            c.rectangle(x - w * 0.6, y + h * 0.3 - h * 0.95, w * 1.2, h * 0.28)
            src(c, hx("#d8d2c8", 0.8))
            c.fill()
        return
    curva = {"sonrisa": 0.08, "dulce": 0.05, "inquietante": 0.1, "triste": -0.05, "miedo": -0.03,
             "serio": -0.01, "enfado": -0.04}.get(expr, 0.0)
    ancho = 0.22 if expr != "inquietante" else 0.3
    c.move_to(x - ancho, y - curva * 0.3)
    c.curve_to(x - ancho * 0.4, y + curva, x + ancho * 0.4, y + curva, x + ancho, y - curva * 0.3)
    c.set_line_width(0.045)
    src(c, mul(labio, 0.7))
    c.stroke()
    if expr == "inquietante":  # sonrisa demasiado amplia
        c.move_to(x - ancho * 0.8, y + 0.0)
        c.curve_to(x - ancho * 0.3, y + 0.09, x + ancho * 0.3, y + 0.09, x + ancho * 0.8, y + 0.0)
        c.set_line_width(0.02)
        src(c, hx("#d8d2c8", 0.6))
        c.stroke()


def _pelo_detras(c, spec, giro):
    e = spec["estilo_pelo"]
    src(c, spec["pelo"])
    if e == "largo":
        c.move_to(-1.05, -0.4)
        c.curve_to(-1.25, 0.6, -1.15, 1.9, -0.9, 2.6)
        c.line_to(0.9, 2.6)
        c.curve_to(1.15, 1.9, 1.25, 0.6, 1.05, -0.4)
        c.close_path()
        c.fill()
    elif e == "suelto":
        c.move_to(-1.0, -0.5)
        c.curve_to(-1.3, 0.3, -1.2, 1.1, -0.85, 1.55)
        c.line_to(0.85, 1.55)
        c.curve_to(1.2, 1.1, 1.3, 0.3, 1.0, -0.5)
        c.close_path()
        c.fill()
    elif e == "mono":
        c.arc(0.0 - giro * 0.2, -1.12, 0.42, 0, 2 * math.pi)
        c.fill_preserve()
        c.set_source(rgrad(-0.1, -1.25, 0, 0.45, [(0, hx("#ffffff", 0.5)), (1, hx("#a9a9a9", 0.0))]))
        c.fill()


def _pelo_delante(c, spec, giro, T):
    e = spec["estilo_pelo"]
    p, pl = spec["pelo"], spec["pelo_luz"]
    g = giro * 0.18
    if e == "despeinado":
        c.move_to(-0.98, 0.05)
        c.curve_to(-1.1, -0.7, -0.75, -1.25, 0.0 + g, -1.25)
        c.curve_to(0.8, -1.28, 1.12, -0.75, 0.98, 0.05)
        # flequillo en mechones
        c.line_to(0.86, -0.32)
        c.line_to(0.66, -0.42 + 0.02 * math.sin(T * 2))
        c.line_to(0.55, -0.28)
        c.line_to(0.32 + g, -0.5)
        c.line_to(0.12 + g, -0.33)
        c.line_to(-0.1 + g, -0.56)
        c.line_to(-0.3 + g, -0.36)
        c.line_to(-0.5 + g, -0.52)
        c.line_to(-0.66, -0.3)
        c.line_to(-0.86, -0.4)
        c.close_path()
        src(c, p)
        c.fill_preserve()
        c.set_source(lgrad(0, -1.3, 0, -0.3, [(0, mul(pl, 1, 0.9)), (0.5, mul(pl, 1, 0.0))]))
        c.fill()
        # mechones de brillo
        c.set_line_width(0.03)
        src(c, mul(pl, 1.2, 0.6))
        for k in range(4):
            xx = -0.6 + k * 0.38 + g
            c.move_to(xx, -1.12)
            c.curve_to(xx + 0.1, -0.95, xx + 0.08, -0.75, xx + 0.15, -0.6)
            c.stroke()
    elif e == "corto":
        c.move_to(-0.95, -0.1)
        c.curve_to(-1.05, -0.85, -0.6, -1.2, 0.0 + g, -1.18)
        c.curve_to(0.6, -1.2, 1.05, -0.85, 0.95, -0.1)
        c.curve_to(0.85, -0.55, 0.5, -0.72, 0.0 + g, -0.7)
        c.curve_to(-0.5, -0.72, -0.85, -0.55, -0.95, -0.1)
        c.close_path()
        src(c, p)
        c.fill()
    elif e == "mono":
        c.move_to(-0.95, -0.15)
        c.curve_to(-1.0, -0.95, -0.55, -1.18, 0.0 + g, -1.16)
        c.curve_to(0.55, -1.18, 1.0, -0.95, 0.95, -0.15)
        c.curve_to(0.8, -0.6, 0.4, -0.78, 0.0 + g, -0.8)
        c.curve_to(-0.4, -0.78, -0.8, -0.6, -0.95, -0.15)
        c.close_path()
        src(c, p)
        c.fill_preserve()
        c.set_line_width(0.02)
        src(c, hx("#b8b8b8", 0.6))
        for k in range(6):
            xx = -0.75 + k * 0.3 + g
            c.move_to(xx * 0.3 + g, -1.12)
            c.curve_to(xx * 0.7, -1.0, xx, -0.8, xx * 1.1, -0.4)
        c.stroke()
        c.new_path()
    elif e in ("suelto", "largo"):
        c.move_to(-1.0, 0.4)
        c.curve_to(-1.15, -0.8, -0.6, -1.22, 0.05 + g, -1.2)
        c.curve_to(0.7, -1.2, 1.15, -0.8, 1.0, 0.4)
        c.curve_to(0.85, -0.3, 0.55, -0.7, 0.15 + g, -0.72)
        c.curve_to(-0.2 + g, -0.5, -0.7, -0.45, -1.0, 0.4)
        c.close_path()
        src(c, p)
        c.fill_preserve()
        c.set_source(lgrad(0, -1.2, 0, 0.2, [(0, mul(pl, 1, 0.7)), (1, mul(pl, 1, 0.0))]))
        c.fill()


def cara(c, x, y, r, spec, T=0.0, expr="neutral", mira=(0.0, 0.0), abierto=1.0, habla=0.0, giro=0.0,
         luz=(-0.6, -0.8), ilum=1.0, cuello=True, lagrimas=0.0, sangre_sin=False, pelo_cara=0.0):
    """Cabeza de frente. r = medio ancho de la cabeza en px."""
    piel, ps = spec["piel"], spec["piel_sombra"]
    with tf(c, x, y, s=r):
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        _pelo_detras(c, spec, giro)
        if cuello:
            c.move_to(-0.38, 0.6)
            c.line_to(-0.42, 1.75)
            c.line_to(0.42, 1.75)
            c.line_to(0.38, 0.6)
            c.close_path()
            src(c, ps)
            c.fill()
            c.move_to(-0.38, 0.95)
            c.curve_to(-0.2, 1.15, 0.2, 1.15, 0.38, 0.95)
            c.line_to(0.38, 0.6)
            c.line_to(-0.38, 0.6)
            c.close_path()
            src(c, (0, 0, 0, 0.25))
            c.fill()
        # orejas
        for lado in (-1, 1):
            ox = lado * (0.93 - 0.12 * max(0, giro * lado))
            c.save()
            c.translate(ox, 0.05)
            c.scale(0.14, 0.24)
            c.arc(0, 0, 1, 0, 2 * math.pi)
            c.restore()
            src(c, ps)
            c.fill()
        # forma de la cabeza
        g = giro * 0.08
        c.move_to(0 + g, -1.15)
        c.curve_to(0.62 + g, -1.15, 0.97, -0.75, 0.95, -0.05)
        c.curve_to(0.93, 0.45, 0.66, 0.92, 0.12 + g * 3, 1.08)
        c.curve_to(0.05 + g * 3, 1.1, -0.05 + g * 3, 1.1, -0.12 + g * 3, 1.08)
        c.curve_to(-0.66, 0.92, -0.93, 0.45, -0.95, -0.05)
        c.curve_to(-0.97, -0.75, -0.62 + g, -1.15, 0 + g, -1.15)
        c.close_path()
        src(c, piel)
        c.fill_preserve()
        # sombreado direccional
        lx, ly = luz
        c.set_source(lgrad(lx * 1.0, ly * 1.0, -lx * 1.0, -ly * 0.6, [(0, (1, 1, 1, 0.10)), (0.45, (0, 0, 0, 0)),
                                                                      (1, mul(ps, 0.6, 0.75))]))
        c.fill_preserve()
        # barba incipiente
        if spec.get("barba", 0) > 0:
            c.save()
            c.clip_preserve()
            c.set_source(rgrad(g * 3, 0.85, 0.1, 0.75, [(0, mul(spec["pelo"], 1, spec["barba"])),
                                                         (1, mul(spec["pelo"], 1, 0))]))
            c.rectangle(-1, 0.3, 2, 1)
            c.fill()
            c.restore()
        c.new_path()
        # rasgos desplazados por el giro
        fx = giro * 0.28
        # mejillas
        for lado in (-1, 1):
            c.arc(fx + lado * 0.5, 0.42, 0.22, 0, 2 * math.pi)
            c.set_source(rgrad(fx + lado * 0.5, 0.42, 0, 0.22, [(0, hx("#d07a6a", 0.12 if spec["nombre"] != "anciana" else 0.03)),
                                                                (1, hx("#d07a6a", 0))]))
            c.fill()
        # arrugas
        if spec.get("arrugas", 0) > 0:
            c.set_line_width(0.018)
            src(c, mul(ps, 0.8, 0.55 * spec["arrugas"]))
            for k in range(3):
                c.move_to(fx - 0.35, -0.62 + k * 0.08)
                c.curve_to(fx - 0.1, -0.66 + k * 0.08, fx + 0.1, -0.66 + k * 0.08, fx + 0.35, -0.62 + k * 0.08)
            for lado in (-1, 1):
                c.move_to(fx + lado * 0.6, 0.0)
                c.line_to(fx + lado * 0.68, 0.06)
                c.move_to(fx + lado * 0.58, 0.08)
                c.line_to(fx + lado * 0.66, 0.15)
                c.move_to(fx + lado * 0.2, 0.4)
                c.curve_to(fx + lado * 0.3, 0.6, fx + lado * 0.28, 0.7, fx + lado * 0.32, 0.8)
            c.stroke()
        if spec.get("sin_rostro"):
            c.arc(fx - 0.33, 0.05, 0.13, 0, 2 * math.pi)
            c.arc(fx + 0.33, 0.05, 0.13, 0, 2 * math.pi)
            src(c, (0, 0, 0, 0.75))
            c.fill()
        else:
            for lado in (-1, 1):
                _ojo(c, fx + lado * 0.36, 0.02, spec, abierto, mira, expr, lado, giro)
                _ceja(c, fx + lado * 0.37, -0.3, spec, expr, lado)
            # nariz
            c.move_to(fx + 0.02, 0.12)
            c.curve_to(fx + 0.1 + giro * 0.1, 0.32, fx + 0.12 + giro * 0.1, 0.42, fx + 0.02, 0.45)
            c.set_line_width(0.035)
            src(c, mul(ps, 0.85, 0.8))
            c.stroke()
            c.arc(fx - 0.06, 0.45, 0.04, 0, 2 * math.pi)
            c.arc(fx + 0.1, 0.45, 0.04, 0, 2 * math.pi)
            src(c, mul(ps, 0.6, 0.5))
            c.fill()
            if spec.get("bigote"):
                c.move_to(fx - 0.25, 0.6)
                c.curve_to(fx - 0.1, 0.52, fx + 0.1, 0.52, fx + 0.25, 0.6)
                c.curve_to(fx + 0.1, 0.58, fx - 0.1, 0.58, fx - 0.25, 0.6)
                c.set_line_width(0.07)
                src(c, spec["pelo"])
                c.stroke()
            _boca(c, fx, 0.68, spec, expr, habla)
            if lagrimas > 0:
                for lado in (-1, 1):
                    yy = 0.14 + 0.55 * lagrimas
                    c.move_to(fx + lado * 0.36, 0.12)
                    c.curve_to(fx + lado * 0.4, 0.3, fx + lado * 0.38, yy - 0.1, fx + lado * 0.4, yy)
                    c.set_line_width(0.035)
                    src(c, hx("#cfe6f2", 0.65))
                    c.stroke()
                    c.arc(fx + lado * 0.4, yy, 0.03, 0, 2 * math.pi)
                    src(c, hx("#eaf6ff", 0.8))
                    c.fill()
        _pelo_delante(c, spec, giro, T)
        if pelo_cara > 0:  # mechones de pelo lacio que tapan la cara (niña)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            for k in range(-10, 11):
                xx = k * 0.095
                largo = (0.2 + 2.2 * abs(xx) ** 1.1 + 0.2 * hash1(k * 3.1)) * pelo_cara * 1.6
                c.move_to(xx * 0.9, -0.85)
                c.curve_to(xx * 1.05, -0.4, xx * 1.1 + 0.03 * math.sin(T + k), -0.4 + largo * 0.6,
                           xx * 1.12, -0.6 + largo)
                c.set_line_width(0.13)
                src(c, spec["pelo"])
                c.stroke()
        if ilum < 1:
            c.arc(0, 0, 1.6, 0, 2 * math.pi)
            src(c, (0, 0, 0, 1 - ilum))
            c.fill()


# ----------------------------------------------------------------- cabeza de perfil (mira a la derecha)
def cabeza_perfil(c, x, y, r, spec, T=0.0, expr="neutral", abierto=1.0, habla=0.0, mira_y=0.0):
    piel, ps = spec["piel"], spec["piel_sombra"]
    with tf(c, x, y, s=r):
        if spec["estilo_pelo"] in ("largo", "suelto"):
            src(c, spec["pelo"])
            c.move_to(-0.2, -1.0)
            c.curve_to(-1.2, -0.9, -1.1, 0.8, -0.8, 1.6 if spec["estilo_pelo"] == "suelto" else 2.5)
            c.line_to(0.0, 1.0)
            c.close_path()
            c.fill()
        # cuello
        c.move_to(-0.35, 0.55)
        c.line_to(-0.4, 1.7)
        c.line_to(0.3, 1.7)
        c.line_to(0.28, 0.7)
        c.close_path()
        src(c, ps)
        c.fill()
        # cráneo + perfil facial
        c.move_to(-0.1, -1.12)
        c.curve_to(0.55, -1.15, 0.9, -0.7, 0.88, -0.25)   # frente
        c.curve_to(0.9, -0.1, 0.95, 0.02, 1.08, 0.18)      # nariz
        c.curve_to(1.1, 0.25, 1.0, 0.3, 0.92, 0.32)
        c.curve_to(0.95, 0.45, 0.93, 0.55, 0.9, 0.62)      # labios
        c.curve_to(0.92, 0.75, 0.82, 0.95, 0.55, 1.0)      # barbilla
        c.curve_to(0.3, 1.02, 0.0, 0.85, -0.3, 0.6)        # mandíbula
        c.curve_to(-0.85, 0.5, -1.0, -0.2, -0.9, -0.55)
        c.curve_to(-0.75, -1.0, -0.45, -1.12, -0.1, -1.12)
        c.close_path()
        src(c, piel)
        c.fill_preserve()
        c.set_source(lgrad(1.0, 0, -0.9, 0, [(0, (1, 1, 1, 0.08)), (0.5, (0, 0, 0, 0)), (1, mul(ps, 0.6, 0.7))]))
        c.fill()
        if spec.get("barba", 0) > 0:
            c.move_to(0.9, 0.62)
            c.curve_to(0.92, 0.75, 0.82, 0.95, 0.55, 1.0)
            c.curve_to(0.3, 1.02, 0.0, 0.85, -0.3, 0.6)
            c.line_to(0.2, 0.45)
            c.close_path()
            src(c, mul(spec["pelo"], 1, spec["barba"] * 0.8))
            c.fill()
        # oreja
        c.save()
        c.translate(-0.25, 0.05)
        c.scale(0.16, 0.24)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        src(c, ps)
        c.fill()
        # ojo
        miedo = expr in ("miedo", "terror", "shock")
        ey = -0.02
        if abierto < 0.1:
            c.move_to(0.48, ey)
            c.line_to(0.7, ey + 0.02)
            c.set_line_width(0.04)
            src(c, spec["cejas"])
            c.stroke()
        else:
            c.save()
            c.translate(0.6, ey)
            c.scale(0.13, 0.12 * abierto * (1.25 if miedo else 1))
            c.arc(0, 0, 1, 0, 2 * math.pi)
            c.restore()
            src(c, hx("#efeae4"))
            c.fill()
            c.arc(0.67, ey + mira_y * 0.04, 0.06 if not miedo else 0.045, 0, 2 * math.pi)
            src(c, spec["ojos"])
            c.fill()
            c.arc(0.68, ey + mira_y * 0.04, 0.03, 0, 2 * math.pi)
            src(c, hx("#050505"))
            c.fill()
        # ceja
        a = {"miedo": -0.25, "terror": -0.35, "triste": -0.3, "serio": 0.1}.get(expr, 0.0)
        with tf(c, 0.6, -0.25 - (0.06 if miedo else 0), r=a):
            c.move_to(-0.15, 0.02)
            c.curve_to(-0.05, -0.04, 0.08, -0.04, 0.16, 0.0)
            c.set_line_width(0.06)
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            src(c, spec["cejas"])
            c.stroke()
        # boca
        ab = max(habla, 0.5 if expr == "terror" else 0.0)
        if ab > 0.05:
            c.save()
            c.translate(0.86, 0.52)
            c.scale(0.08, 0.04 + 0.1 * ab)
            c.arc(0, 0, 1, 0, 2 * math.pi)
            c.restore()
            src(c, hx("#2a0f10"))
            c.fill()
        else:
            c.move_to(0.78, 0.5)
            c.line_to(0.92, 0.48)
            c.set_line_width(0.03)
            src(c, mul(spec.get("labios", ps), 0.7))
            c.stroke()
        # pelo
        e = spec["estilo_pelo"]
        src(c, spec["pelo"])
        if e == "despeinado":
            c.move_to(0.75, -0.45)
            c.line_to(0.85, -0.7)
            c.curve_to(0.7, -1.2, 0.0, -1.35, -0.55, -1.05)
            c.curve_to(-1.0, -0.8, -1.05, -0.2, -0.75, 0.25)
            c.line_to(-0.45, 0.1)
            c.line_to(-0.4, -0.3)
            c.line_to(0.1, -0.55)
            c.line_to(0.35, -0.42)
            c.line_to(0.5, -0.6)
            c.close_path()
            c.fill()
        elif e == "mono":
            c.move_to(0.8, -0.5)
            c.curve_to(0.7, -1.25, -0.3, -1.3, -0.8, -0.7)
            c.curve_to(-1.0, -0.4, -0.9, 0.0, -0.7, 0.2)
            c.line_to(-0.4, -0.3)
            c.curve_to(0.0, -0.6, 0.4, -0.7, 0.8, -0.5)
            c.close_path()
            c.fill()
            c.arc(-0.75, -0.75, 0.38, 0, 2 * math.pi)
            c.fill()
        elif e in ("corto",):
            c.move_to(0.8, -0.55)
            c.curve_to(0.7, -1.2, -0.3, -1.3, -0.8, -0.7)
            c.curve_to(-0.98, -0.4, -0.92, 0.0, -0.75, 0.2)
            c.line_to(-0.45, -0.25)
            c.curve_to(0.0, -0.6, 0.4, -0.7, 0.8, -0.55)
            c.close_path()
            c.fill()
        else:
            c.move_to(0.8, -0.45)
            c.curve_to(0.75, -1.25, -0.3, -1.35, -0.85, -0.75)
            c.curve_to(-1.05, -0.4, -1.0, 0.2, -0.7, 0.6)
            c.line_to(-0.35, -0.2)
            c.curve_to(0.0, -0.55, 0.45, -0.6, 0.8, -0.45)
            c.close_path()
            c.fill()
        if spec.get("gorra"):
            c.move_to(-0.9, -0.55)
            c.curve_to(-0.85, -1.35, 0.7, -1.4, 0.82, -0.6)
            c.line_to(1.3, -0.52)
            c.line_to(1.25, -0.42)
            c.line_to(-0.9, -0.45)
            c.close_path()
            src(c, spec["gorra"])
            c.fill()


# ----------------------------------------------------------------- piezas del cuerpo
def _extremidad(c, x0, y0, x1, y1, x2, y2, w0, w1, col, luz_col=None):
    """Brazo/pierna de dos segmentos como trazo grueso redondeado."""
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.move_to(x0, y0)
    c.line_to(x1, y1)
    c.set_line_width(w0)
    src(c, col)
    c.stroke()
    c.move_to(x1, y1)
    c.line_to(x2, y2)
    c.set_line_width(w1)
    c.stroke()
    if luz_col:
        c.move_to(x0 - w0 * 0.25, y0)
        c.line_to(x1 - w0 * 0.25, y1)
        c.line_to(x2 - w1 * 0.25, y2)
        c.set_line_width(w1 * 0.25)
        src(c, luz_col)
        c.stroke()


def _mano(c, x, y, r, spec, ang=0.0):
    with tf(c, x, y, s=r, r=ang):
        c.save()
        c.scale(0.8, 1.0)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        src(c, spec["piel"])
        c.fill_preserve()
        src(c, mul(spec["piel_sombra"], 1, 0.35))
        c.fill()


def _ik(x0, y0, x2, y2, l1, l2, flex=1):
    """Codo/rodilla por cinemática inversa de dos segmentos."""
    dx, dy = x2 - x0, y2 - y0
    d = max(1e-3, min(math.hypot(dx, dy), l1 + l2 - 1e-3))
    a = math.atan2(dy, dx)
    cb = cl((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1)
    b = math.acos(cb) * flex
    return x0 + l1 * math.cos(a + b), y0 + l1 * math.sin(a + b)


# ----------------------------------------------------------------- figura de frente
def figura(c, x, y, alto, spec, T=0.0, expr="neutral", mira=(0, 0), habla=0.0, giro=0.0, parp=1.0,
           brazos="abajo", respira=1.0, luz_borde=None, ilum=1.0, sentado=False, peluche=False,
           pelo_cara=0.0, lagrimas=0.0, inclina=0.0, mano_ext=0.0, sacudida=0.0, espalda=False, paso=None):
    """Persona de frente (o de espaldas). (x, y) = pies (o asiento si `sentado`)."""
    u = alto / 7.4          # alto de una cabeza
    hr = u * 0.6            # radio de la cabeza (algo estilizada)
    resp = math.sin(T * 1.6) * 0.012 * respira
    temblor = sacudida * math.sin(T * 41) * u * 0.03
    bob = 0.0
    if paso is not None:
        bob = -abs(math.sin(paso * math.pi)) * u * 0.12
        temblor += math.sin(paso * math.pi) * u * 0.06
    with tf(c, x + temblor, y + bob):
        if sentado:
            cadera_y = 0.0
            hombros_y = -u * 2.7 * (1 + resp)
        else:
            cadera_y = -u * 3.6
            hombros_y = cadera_y - u * 2.65 * (1 + resp)
        cabeza_y = hombros_y - u * 1.08
        anch_h = u * 1.05 if spec["nombre"] != "nina" else u * 0.75
        anch_c = u * 0.75 if spec["nombre"] != "nina" else u * 0.55
        torso = spec["torso"]
        tl = spec["torso_luz"]
        piern = spec.get("piernas", spec.get("falda", torso))
        c.save()
        c.translate(0, cadera_y)
        c.rotate(inclina)
        c.translate(0, -cadera_y)
        # ---- piernas
        if sentado:
            for lado in (-1, 1):
                kx, ky = lado * u * 0.45, u * 0.35
                _extremidad(c, lado * u * 0.4, 0, kx * 1.05, ky + u * 0.1, lado * u * 0.42, ky + u * 1.9,
                            u * 0.55, u * 0.42, piern)
                with tf(c, lado * u * 0.45, ky + u * 1.95):
                    rr(c, -u * 0.28, -u * 0.12, u * 0.56, u * 0.26, u * 0.1)
                    src(c, spec["zapatos"])
                    c.fill()
        elif spec.get("falda") or spec.get("vestido"):
            pass
        else:
            for lado in (-1, 1):
                _extremidad(c, lado * u * 0.4, cadera_y, lado * u * 0.42, cadera_y + u * 1.8, lado * u * 0.45,
                            -u * 0.15, u * 0.6, u * 0.48, piern)
                rr(c, lado * u * 0.45 - u * 0.32, -u * 0.25, u * 0.64, u * 0.28, u * 0.12)
                src(c, spec["zapatos"])
                c.fill()
        # ---- falda / vestido
        if spec.get("falda") or spec.get("vestido"):
            col = spec.get("falda", torso)
            bajo = 0 if not sentado else u * 1.4
            c.move_to(-anch_c * 0.95, cadera_y - u * 0.3)
            c.curve_to(-anch_c * 1.1, cadera_y + u * 1.5, -anch_c * 1.5, bajo - u * 0.6, -anch_c * 1.55,
                       bajo - u * (0.35 if spec.get("vestido") else 0.15))
            c.line_to(anch_c * 1.55, bajo - u * (0.35 if spec.get("vestido") else 0.15))
            c.curve_to(anch_c * 1.5, bajo - u * 0.6, anch_c * 1.1, cadera_y + u * 1.5, anch_c * 0.95,
                       cadera_y - u * 0.3)
            c.close_path()
            src(c, col)
            c.fill_preserve()
            sombrear(c, -anch_c * 1.5, 0, anch_c * 1.5, 0, 0.5)
            c.new_path()
            if spec.get("vestido"):
                for lado in (-1, 1):
                    _extremidad(c, lado * u * 0.25, bajo - u * 0.4, lado * u * 0.25, bajo - u * 0.2, lado * u * 0.27,
                                -u * 0.1 + (bajo if sentado else 0), u * 0.28, u * 0.25, spec["piernas"])
                    rr(c, lado * u * 0.27 - u * 0.18, -u * 0.18 + (bajo if sentado else 0), u * 0.36, u * 0.2, u * 0.08)
                    src(c, spec["zapatos"])
                    c.fill()
            else:
                for lado in (-1, 1):
                    rr(c, lado * u * 0.35 - u * 0.25, -u * 0.2 + bajo * 0.95, u * 0.5, u * 0.22, u * 0.1)
                    src(c, spec["zapatos"])
                    c.fill()
        # ---- capucha (detrás)
        if spec.get("capucha"):
            c.move_to(-anch_h * 0.85, hombros_y + u * 0.15)
            c.curve_to(-anch_h * 0.9, hombros_y - u * 0.55, anch_h * 0.9, hombros_y - u * 0.55, anch_h * 0.85,
                       hombros_y + u * 0.15)
            c.close_path()
            src(c, mul(torso, 0.7))
            c.fill()
        # ---- torso
        largo = (cadera_y - hombros_y) + (u * 0.55 if spec.get("abrigo") else u * 0.2)
        c.move_to(-anch_h, hombros_y + u * 0.25)
        c.curve_to(-anch_h, hombros_y - u * 0.05, -anch_h * 0.6, hombros_y - u * 0.12, -u * 0.25, hombros_y - u * 0.1)
        c.line_to(u * 0.25, hombros_y - u * 0.1)
        c.curve_to(anch_h * 0.6, hombros_y - u * 0.12, anch_h, hombros_y - u * 0.05, anch_h, hombros_y + u * 0.25)
        c.line_to(anch_c * 1.05, hombros_y + largo)
        c.line_to(-anch_c * 1.05, hombros_y + largo)
        c.close_path()
        src(c, torso)
        c.fill_preserve()
        c.set_source(lgrad(-anch_h, 0, anch_h, 0, [(0, mul(tl, 1, 0.55)), (0.45, mul(tl, 1, 0.0)),
                                                   (1, (0, 0, 0, 0.45))]))
        c.fill_preserve()
        c.set_source(lgrad(0, hombros_y, 0, hombros_y + largo, [(0, (0, 0, 0, 0)), (1, (0, 0, 0, 0.35))]))
        c.fill()
        if spec.get("capucha") and not espalda:
            # bolsillo canguro y cordones
            rr(c, -anch_c * 0.75, hombros_y + largo * 0.62, anch_c * 1.5, largo * 0.28, u * 0.15)
            c.set_line_width(u * 0.04)
            src(c, (0, 0, 0, 0.35))
            c.stroke()
            for lado in (-1, 1):
                c.move_to(lado * u * 0.18, hombros_y + u * 0.05)
                c.line_to(lado * u * 0.2 + math.sin(T * 1.3 + lado) * u * 0.03, hombros_y + u * 0.85)
                c.set_line_width(u * 0.05)
                src(c, hx("#d8d0c8", 0.9))
                c.stroke()
        if spec.get("chal"):
            c.move_to(-anch_h * 1.02, hombros_y + u * 0.2)
            c.curve_to(-anch_h * 0.6, hombros_y - u * 0.25, anch_h * 0.6, hombros_y - u * 0.25, anch_h * 1.02,
                       hombros_y + u * 0.2)
            c.line_to(anch_h * 0.75, hombros_y + u * 1.3)
            c.line_to(0, hombros_y + u * 1.7)
            c.line_to(-anch_h * 0.75, hombros_y + u * 1.3)
            c.close_path()
            src(c, spec["chal"])
            c.fill_preserve()
            sombrear(c, -anch_h, 0, anch_h, 0, 0.4)
            c.new_path()
            # broche
            c.arc(0, hombros_y + u * 0.55, u * 0.08, 0, 2 * math.pi)
            src(c, hx("#8f8a7a"))
            c.fill()
        if spec.get("abrigo"):
            c.move_to(0, hombros_y)
            c.line_to(0, hombros_y + largo)
            c.set_line_width(u * 0.04)
            src(c, (0, 0, 0, 0.5))
            c.stroke()
            for lado in (-1, 1):
                c.move_to(lado * u * 0.05, hombros_y - u * 0.05)
                c.line_to(lado * u * 0.45, hombros_y + u * 0.7)
                c.line_to(lado * u * 0.05, hombros_y + u * 1.0)
            c.set_line_width(u * 0.04)
            c.stroke()
        if spec.get("chaleco"):
            for lado in (-1, 1):
                c.move_to(lado * u * 0.2, hombros_y - u * 0.05)
                c.line_to(lado * anch_h * 0.92, hombros_y + u * 0.2)
                c.line_to(lado * anch_c * 1.0, hombros_y + largo * 0.85)
                c.line_to(lado * u * 0.2, hombros_y + largo * 0.85)
                c.close_path()
            src(c, spec["chaleco"])
            c.fill()
            c.rectangle(-anch_c * 1.0, hombros_y + largo * 0.55, anch_c * 2.0, u * 0.12)
            src(c, hx("#e8ecef", 0.85))
            c.fill()
        # ---- brazos
        for lado in (-1, 1):
            sx, sy = lado * anch_h * 0.9, hombros_y + u * 0.2
            if brazos == "abajo":
                hx_, hy_ = lado * (anch_h * 1.05), hombros_y + u * 2.6
            elif brazos == "regazo":
                hx_, hy_ = lado * u * 0.35, (u * 0.2 if sentado else cadera_y + u * 0.1)
            elif brazos == "peluche":
                hx_, hy_ = lado * u * 0.25, hombros_y + u * 1.6
            elif brazos == "movil":
                hx_, hy_ = (lado * u * 0.3, hombros_y + u * 1.4) if lado < 0 else (u * 0.1, hombros_y + u * 1.25)
            elif brazos == "extiende" and lado == 1:
                k = mano_ext
                hx_, hy_ = lerp(anch_h * 1.05, anch_h * 2.6, k), lerp(hombros_y + u * 2.6, hombros_y + u * 0.9, k)
            elif brazos == "agarra" and lado == -1:
                hx_, hy_ = -anch_h * 2.4, hombros_y + u * 1.2
            elif brazos == "cristal":
                hx_, hy_ = lado * u * 0.8, hombros_y - u * 0.6 - (u * 0.3 * math.sin(T * 9) if lado > 0 else 0)
            else:
                hx_, hy_ = lado * (anch_h * 1.05), hombros_y + u * 2.6
            ex, ey = _ik(sx, sy, hx_, hy_, u * 1.25, u * 1.2, flex=-lado if brazos != "abajo" else lado * 0.15)
            manga = mul(torso, 0.92)
            _extremidad(c, sx, sy, ex, ey, hx_, hy_, u * 0.48, u * 0.4, manga,
                        luz_col=mul(tl, 1, 0.35) if lado < 0 else None)
            _mano(c, hx_, hy_ + u * 0.1, u * 0.2, spec)
        if peluche:
            osito(c, 0, hombros_y + u * 1.7, u * 0.75, T)
        c.restore()
        # ---- cabeza
        with tf(c, 0, cadera_y, r=inclina):
            pass
        hxp = math.sin(inclina) * (cadera_y - cabeza_y) * -1
        if espalda:
            with tf(c, hxp, cabeza_y, s=hr):
                c.rectangle(-0.38, 0.5, 0.76, 1.2)
                src(c, spec["piel_sombra"])
                c.fill()
                for lado in (-1, 1):
                    c.save(); c.translate(lado * 0.93, 0.05); c.scale(0.14, 0.24); c.arc(0, 0, 1, 0, 2 * math.pi)
                    c.restore()
                    src(c, spec["piel_sombra"])
                    c.fill()
                c.save(); c.scale(0.97, 1.15); c.arc(0, -0.02, 1, 0, 2 * math.pi); c.restore()
                src(c, spec["pelo"])
                c.fill_preserve()
                c.set_source(rgrad(-0.3, -0.5, 0.1, 1.2, [(0, mul(spec["pelo_luz"], 1, 0.6)), (1, (0, 0, 0, 0.3))]))
                c.fill()
                if spec.get("capucha"):
                    c.move_to(-0.9, 1.0); c.curve_to(-1.1, 1.9, 1.1, 1.9, 0.9, 1.0); c.close_path()
                    src(c, mul(spec["torso"], 0.8)); c.fill()
        else:
            cara(c, hxp, cabeza_y, hr, spec, T, expr=expr, mira=mira, abierto=parp, habla=habla, giro=giro,
                 ilum=ilum, cuello=True, pelo_cara=pelo_cara, lagrimas=lagrimas)
        if spec.get("gorra"):
            with tf(c, hxp, cabeza_y, s=hr):
                c.move_to(-1.02, -0.35)
                c.curve_to(-1.05, -1.4, 1.05, -1.4, 1.02, -0.35)
                c.close_path()
                src(c, spec["gorra"])
                c.fill()
                c.save()
                c.translate(0, -0.32)
                c.scale(1.15, 0.2)
                c.arc(0, 0, 1, 0, math.pi)
                c.restore()
                src(c, mul(spec["gorra"], 0.7))
                c.fill()
                c.arc(0, -0.85, 0.15, 0, 2 * math.pi)
                src(c, hx("#c9b25a"))
                c.fill()
        if ilum < 1:
            pass
        if luz_borde:
            pass


def osito(c, x, y, r, T=0.0, sucio=0.5):
    marron, oscuro = hx("#6b4a33"), hx("#3d2a1d")
    with tf(c, x, y, s=r, r=math.sin(T * 0.7) * 0.05):
        for lx in (-0.45, 0.45):
            c.arc(lx, 0.55, 0.28, 0, 2 * math.pi)
        src(c, marron)
        c.fill()
        c.save()
        c.scale(0.55, 0.62)
        c.arc(0, 0.35, 1, 0, 2 * math.pi)
        c.restore()
        src(c, marron)
        c.fill()
        c.arc(0, -0.45, 0.42, 0, 2 * math.pi)
        c.fill()
        for lx in (-0.33, 0.33):
            c.arc(lx, -0.78, 0.15, 0, 2 * math.pi)
            src(c, marron)
            c.fill()
            c.arc(lx, -0.78, 0.08, 0, 2 * math.pi)
            src(c, oscuro)
            c.fill()
        c.arc(-0.14, -0.5, 0.05, 0, 2 * math.pi)
        c.arc(0.14, -0.5, 0.05, 0, 2 * math.pi)
        src(c, hx("#050505"))
        c.fill()
        # un ojo descosido
        c.move_to(0.1, -0.55)
        c.line_to(0.2, -0.45)
        c.set_line_width(0.03)
        src(c, hx("#d8d0c0"))
        c.stroke()
        c.arc(0, -0.33, 0.12, 0, 2 * math.pi)
        src(c, hx("#a88a6a"))
        c.fill()
        c.arc(0, -0.37, 0.04, 0, 2 * math.pi)
        src(c, oscuro)
        c.fill()


# ----------------------------------------------------------------- figura de perfil (mira a la derecha)
def figura_perfil(c, x, y, alto, spec, T=0.0, modo="pie", fase=0.0, expr="neutral", habla=0.0, parp=1.0,
                  voltear=False, brazo_alzado=0.0, mira_y=0.0, golpe=0.0):
    """modo: 'pie', 'camina', 'corre', 'sentado'. fase: ciclo de paso en vueltas."""
    u = alto / 7.4
    hr = u * 0.6
    with tf(c, x, y, sx=-1 if voltear else 1):
        ciclo = fase * 2 * math.pi
        rebote = 0.0
        amp_p, amp_b = 0.0, 0.0
        if modo == "camina":
            amp_p, amp_b, rebote = 0.45, 0.35, abs(math.sin(ciclo)) * u * 0.08
        elif modo == "corre":
            amp_p, amp_b, rebote = 0.55, 0.8, abs(math.sin(ciclo)) * u * 0.18
        incl = 0.18 if modo == "corre" else (0.04 if modo == "camina" else 0.0)
        if modo == "sentado":
            cad_x, cad_y = 0.0, 0.0
        else:
            cad_x, cad_y = 0.0, -u * 3.6 - rebote
        hom_x = cad_x + math.sin(incl) * u * 2.6
        hom_y = cad_y - math.cos(incl) * u * 2.6
        torso, tl = spec["torso"], spec["torso_luz"]
        piern = spec.get("piernas", torso)

        def pierna(ph, oscura):
            col = mul(piern, 0.7 if oscura else 1.0)
            if modo == "sentado":
                kx, ky = cad_x + u * 1.6, cad_y - u * 0.05
                fx_, fy_ = kx + u * 0.1, ky + u * 1.85
            else:
                sw = math.sin(ph) * amp_p
                fx_ = cad_x + math.sin(sw) * u * 3.4
                lift = max(0.0, math.cos(ph)) * u * (0.5 if modo == "corre" else 0.25)
                fy_ = -lift
                kx, ky = _ik(cad_x, cad_y, fx_, fy_, u * 1.8, u * 1.8, flex=-1)
            _extremidad(c, cad_x, cad_y, kx, ky, fx_, fy_, u * 0.6, u * 0.46, col)
            rr(c, fx_ - u * 0.2, fy_ - u * 0.22, u * 0.68, u * 0.27, u * 0.1)
            src(c, mul(spec["zapatos"], 0.7 if oscura else 1))
            c.fill()

        def brazo(ph, oscuro):
            col = mul(torso, 0.65 if oscuro else 0.95)
            if brazo_alzado > 0 and not oscuro:
                hx_ = hom_x + u * 1.9
                hy_ = hom_y - u * 0.2 - brazo_alzado * u * 0.4 + golpe * u * 0.0
                hx_ += golpe * u * 0.35
            elif modo == "sentado":
                hx_, hy_ = hom_x + u * 1.2, cad_y - u * 0.15
            else:
                sw = math.sin(ph) * amp_b
                rad = u * (1.75 if modo == "corre" else 2.3)
                hx_ = hom_x + math.sin(sw) * rad
                hy_ = hom_y + math.cos(sw) * rad
            ex, ey = _ik(hom_x, hom_y, hx_, hy_, u * 1.25, u * 1.2, flex=1)
            _extremidad(c, hom_x, hom_y, ex, ey, hx_, hy_, u * 0.45, u * 0.38, col)
            _mano(c, hx_, hy_, u * 0.19, spec)

        brazo(ciclo + math.pi, True)
        pierna(ciclo + math.pi, True)
        # torso
        c.save()
        c.translate(cad_x, cad_y)
        c.rotate(incl)
        largo = u * 2.75
        c.move_to(-u * 0.45, u * 0.25)
        c.curve_to(-u * 0.6, -largo * 0.5, -u * 0.45, -largo, -u * 0.05, -largo - u * 0.05)
        c.curve_to(u * 0.45, -largo, u * 0.6, -largo * 0.6, u * 0.5, u * 0.25)
        c.close_path()
        src(c, torso)
        c.fill_preserve()
        c.set_source(lgrad(-u * 0.6, 0, u * 0.6, 0, [(0, (0, 0, 0, 0.45)), (0.6, (0, 0, 0, 0)),
                                                     (1, mul(tl, 1, 0.5))]))
        c.fill()
        if spec.get("capucha"):
            c.move_to(-u * 0.5, -largo + u * 0.1)
            c.curve_to(-u * 0.95, -largo + u * 0.3, -u * 0.8, -largo + u * 0.9, -u * 0.45, -largo + u * 0.8)
            c.close_path()
            src(c, mul(torso, 0.75))
            c.fill()
        c.restore()
        pierna(ciclo, False)
        cabeza_perfil(c, hom_x + u * 0.12, hom_y - u * 1.0, hr, spec, T, expr=expr, abierto=parp, habla=habla,
                      mira_y=mira_y)
        brazo(ciclo, False)


def silueta(c, x, y, alto, col=(0.02, 0.03, 0.035, 1.0), T=0.0, semilla=0.0, ojos=0.0, ladeo=0.0):
    """Silueta humana inmóvil (sombras al otro lado de las vías)."""
    u = alto / 7.4
    bal = math.sin(T * 0.4 + semilla) * 0.004
    with tf(c, x, y, r=bal + ladeo):
        c.move_to(-u * 0.95, -u * 5.9)
        c.curve_to(-u * 1.1, -u * 4.0, -u * 0.9, -u * 1.0, -u * 0.6, 0)
        c.line_to(u * 0.6, 0)
        c.curve_to(u * 0.9, -u * 1.0, u * 1.1, -u * 4.0, u * 0.95, -u * 5.9)
        c.curve_to(u * 0.6, -u * 6.25, -u * 0.6, -u * 6.25, -u * 0.95, -u * 5.9)
        c.close_path()
        src(c, col)
        c.fill()
        c.rectangle(-u * 0.2, -u * 6.5, u * 0.4, u * 0.5)
        c.fill()
        c.save()
        c.translate(0, -u * 6.85)
        c.scale(u * 0.42, u * 0.52)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        c.fill()
        if ojos > 0:
            for lx in (-0.16, 0.16):
                c.arc(lx * u, -u * 6.85, u * 0.055, 0, 2 * math.pi)
                src(c, hx("#dfe9ee", ojos))
                c.fill()


def busto(c, x, y, r, spec, T=0.0, expr="neutral", mira=(0, 0), habla=0.0, giro=0.0, parp=1.0, ilum=1.0,
          lagrimas=0.0, pelo_cara=0.0, inclina=0.0, respira=1.0, luz=(-0.6, -0.8), sacudida=0.0):
    """Primer plano: cabeza (radio r) y hombros. (x, y) = centro de la cabeza."""
    resp = math.sin(T * 1.6) * 0.02 * respira
    tem = sacudida * math.sin(T * 47) * r * 0.04
    torso, tl = spec["torso"], spec["torso_luz"]
    with tf(c, x + tem, y, r=inclina):
        hy = r * (1.3 + resp)
        ancho = r * (2.6 if spec["nombre"] != "nina" else 1.9)
        if spec.get("capucha"):
            c.move_to(-r * 1.25, hy + r * 0.2)
            c.curve_to(-r * 1.4, hy - r * 0.9, r * 1.4, hy - r * 0.9, r * 1.25, hy + r * 0.2)
            c.close_path()
            src(c, mul(torso, 0.6))
            c.fill()
        c.move_to(-ancho, hy + r * 3.5)
        c.curve_to(-ancho, hy + r * 0.6, -ancho * 0.8, hy + r * 0.05, -r * 0.5, hy - r * 0.05)
        c.line_to(r * 0.5, hy - r * 0.05)
        c.curve_to(ancho * 0.8, hy + r * 0.05, ancho, hy + r * 0.6, ancho, hy + r * 3.5)
        c.close_path()
        src(c, torso)
        c.fill_preserve()
        c.set_source(lgrad(-ancho, 0, ancho, 0, [(0, mul(tl, 1, 0.5)), (0.45, mul(tl, 1, 0.0)), (1, (0, 0, 0, 0.5))]))
        c.fill_preserve()
        c.set_source(lgrad(0, hy, 0, hy + r * 3.5, [(0, (0, 0, 0, 0)), (1, (0, 0, 0, 0.5))]))
        c.fill()
        if spec.get("capucha"):
            for lado in (-1, 1):
                c.move_to(lado * r * 0.3, hy + r * 0.1)
                c.line_to(lado * r * 0.34 + math.sin(T * 1.3 + lado) * r * 0.04, hy + r * 1.6)
                c.set_line_width(r * 0.08)
                src(c, hx("#d8d0c8", 0.9))
                c.stroke()
        if spec.get("chal"):
            c.move_to(-ancho * 0.95, hy + r * 0.5)
            c.curve_to(-ancho * 0.6, hy - r * 0.2, ancho * 0.6, hy - r * 0.2, ancho * 0.95, hy + r * 0.5)
            c.line_to(ancho * 0.6, hy + r * 2.4)
            c.line_to(0, hy + r * 3.0)
            c.line_to(-ancho * 0.6, hy + r * 2.4)
            c.close_path()
            src(c, spec["chal"])
            c.fill()
            c.arc(0, hy + r * 0.9, r * 0.13, 0, 2 * math.pi)
            src(c, hx("#8f8a7a"))
            c.fill()
        if spec.get("chaleco"):
            for lado in (-1, 1):
                c.move_to(lado * r * 0.4, hy)
                c.line_to(lado * ancho * 0.85, hy + r * 0.4)
                c.line_to(lado * ancho * 0.9, hy + r * 3.5)
                c.line_to(lado * r * 0.4, hy + r * 3.5)
                c.close_path()
            src(c, spec["chaleco"])
            c.fill()
        if spec.get("abrigo"):
            for lado in (-1, 1):
                c.move_to(lado * r * 0.1, hy)
                c.line_to(lado * r * 0.8, hy + r * 1.3)
                c.line_to(lado * r * 0.1, hy + r * 1.9)
            c.set_line_width(r * 0.07)
            src(c, (0, 0, 0, 0.5))
            c.stroke()
        cara(c, 0, 0, r, spec, T, expr=expr, mira=mira, abierto=parp, habla=habla, giro=giro, luz=luz,
             ilum=1.0, cuello=True, lagrimas=lagrimas, pelo_cara=pelo_cara)
        if spec.get("gorra"):
            with tf(c, 0, 0, s=r):
                c.move_to(-1.02, -0.35)
                c.curve_to(-1.05, -1.4, 1.05, -1.4, 1.02, -0.35)
                c.close_path()
                src(c, spec["gorra"])
                c.fill()
                c.save(); c.translate(0, -0.32); c.scale(1.15, 0.2); c.arc(0, 0, 1, 0, math.pi); c.restore()
                src(c, mul(spec["gorra"], 0.7))
                c.fill()
        if ilum < 1:
            c.rectangle(-ancho * 1.2, -r * 2, ancho * 2.4, r * 8)
            src(c, (0, 0, 0, 1 - ilum))
            c.fill()
