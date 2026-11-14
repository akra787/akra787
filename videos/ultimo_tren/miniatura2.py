#!/usr/bin/env python3
"""Miniatura llamativa para YouTube: «NO DEBÍ SUBIR».

Bryan aterrado en primer plano, la anciana sonriendo pegada al cristal detrás de él (con círculo y flecha
rojos), el reloj 3:17 y texto enorme con contorno. Salida: 1280x720 (YouTube) y 1920x1080.
"""
import math
import os
import sys

os.environ["FORMATO"] = "horizontal"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cairo  # noqa: E402
import numpy as np  # noqa: E402

from motor import (AQUI, H, TITULO, W, a_numpy, a_superficie, hx, lgrad, mul, posproceso, resplandor, rgrad,  # noqa
                   rr, src, superficie, tf)
from escenarios import Cam, vagon  # noqa: E402
from personajes import ANCIANA, BRYAN, busto, cara  # noqa: E402

SALIDA = os.path.join(AQUI, "..")


def texto_contorno(c, s, x, y, tam, relleno, contorno=(0, 0, 0, 1), grosor=18, ancla=0.0, rot=0.0, brillo=None):
    c.save()
    c.translate(x, y)
    c.rotate(rot)
    c.select_font_face(TITULO, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(tam)
    ext = c.text_extents(s)
    x0 = -ext.x_advance * ancla
    if brillo:
        for k in range(4):
            c.move_to(x0, 0)
            c.text_path(s)
            c.set_line_width(grosor + 30 - k * 6)
            c.set_line_join(cairo.LINE_JOIN_ROUND)
            src(c, brillo[:3] + (0.12,))
            c.stroke()
    # sombra
    c.move_to(x0 + 10, 12)
    c.text_path(s)
    c.set_line_width(grosor)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    src(c, (0, 0, 0, 0.6))
    c.stroke_preserve()
    c.fill()
    c.move_to(x0, 0)
    c.text_path(s)
    c.set_line_width(grosor)
    src(c, contorno)
    c.stroke_preserve()
    src(c, relleno)
    c.fill()
    c.restore()
    return ext.x_advance


def main():
    s, c = superficie()
    # --- fondo: interior del vagón con luz roja de emergencia
    cam = Cam(x=0.3, y=1.3, z=1.0, yaw=0.25, f=820, niebla=(0.03, 0.01, 0.012), densidad=0.05)
    vagon(c, cam, 2.0, luces=0.55, rojo=0.85, velocidad=1.0, fuera="rojo")
    c.rectangle(0, 0, W, H)
    src(c, (0, 0, 0, 0.35))
    c.fill()

    # --- ventana detrás de Bryan con la anciana pegada al cristal
    vx, vy, vw, vh = 960, 90, 560, 520
    rr(c, vx, vy, vw, vh, 40)
    src(c, hx("#05080a"))
    c.fill()
    c.save()
    rr(c, vx, vy, vw, vh, 40)
    c.clip()
    # luces del túnel
    for k in range(3):
        resplandor(c, vx + 80 + k * 220, vy + 40, 160, hx("#ff3b2f"), 0.6)
    resplandor(c, vx + 300, vy + 230, 330, hx("#9fe0ff"), 0.55)
    busto(c, vx + 300, vy + 230, 125, ANCIANA, T=0.0, expr="inquietante", mira=(-0.7, 0.15))
    # ojos que brillan
    for dx in (-0.36, 0.36):
        ex = vx + 300 + (dx + (-0.7) * 0.0) * 125
        resplandor(c, ex - 0.04 * 125, vy + 230 + 3, 55, hx("#d8f6ff"), 1.2)
    # vaho y reflejo en el cristal
    c.set_source(lgrad(vx, vy, vx + vw, vy + vh, [(0, (1, 1, 1, 0.10)), (0.4, (1, 1, 1, 0.0)),
                                                   (0.55, (1, 1, 1, 0.08)), (0.6, (1, 1, 1, 0))]))
    c.paint()
    # huellas de manos en el vaho
    for hx_, hy_ in ((vx + 110, vy + 360), (vx + 470, vy + 330)):
        c.arc(hx_, hy_, 46, 0, 2 * math.pi)
        src(c, (0.85, 0.9, 0.95, 0.10))
        c.fill()
    c.restore()
    rr(c, vx, vy, vw, vh, 40)
    c.set_line_width(22)
    src(c, hx("#3a4246"))
    c.stroke()

    # --- Bryan aterrado en primer plano (izquierda-centro)
    with tf(c, 560, 470, r=-0.06):
        resplandor(c, 0, 0, 520, hx("#ff2a1f"), 0.35)
        busto(c, 0, 0, 255, BRYAN, T=0.3, expr="terror", mira=(0.75, -0.05), giro=0.18, parp=1.0)
        # gotas de sudor
        for gx, gy, gr in ((-170, -120, 13), (190, -60, 11), (-205, 40, 9)):
            c.save()
            c.translate(gx, gy)
            c.scale(1, 1.5)
            c.arc(0, 0, gr, 0, 2 * math.pi)
            c.restore()
            src(c, (0.85, 0.95, 1.0, 0.75))
            c.fill()
    # luz de contorno roja en el lado derecho de la cara
    c.save()
    c.set_operator(cairo.OPERATOR_ADD)
    resplandor(c, 820, 380, 260, hx("#ff3b2f"), 0.35)
    c.restore()

    # --- posproceso (gradación, grano leve, viñeta)
    arr = a_numpy(s)
    arr = posproceso(arr, 1.0, 3, dict(niebla=0.15, niebla_color=(0.3, 0.05, 0.05), grano=0.025, vineta=0.9,
                                       gradacion=0.4))
    # más contraste y saturación para que destaque en la lista de vídeos
    m = arr.mean(axis=2, keepdims=True)
    arr = np.clip((arr - 0.5) * 1.18 + 0.5, 0, 1)
    arr = np.clip(m + (arr - m) * 1.35, 0, 1)
    s2 = a_superficie(arr)
    c2 = cairo.Context(s2)

    # --- círculo y flecha rojos señalando a la anciana
    cx, cy, rc = vx + 300, vy + 235, 175
    c2.set_line_cap(cairo.LINE_CAP_ROUND)
    for ancho, col in ((26, (0, 0, 0, 0.5)), (16, hx("#ff1e1e"))):
        c2.save()
        c2.translate(cx, cy)
        c2.scale(1.0, 1.08)
        c2.arc(0, 0, rc, 0.2, 2 * math.pi - 0.05)
        c2.restore()
        c2.set_line_width(ancho)
        src(c2, col)
        c2.stroke()
    # flecha curva desde abajo a la derecha
    for ancho, col in ((30, (0, 0, 0, 0.5)), (20, hx("#ff1e1e"))):
        c2.move_to(1790, 820)
        c2.curve_to(1850, 660, 1780, 520, cx + rc + 40, cy + 70)
        c2.set_line_width(ancho)
        src(c2, col)
        c2.stroke()
        # punta
        ax, ay = cx + rc + 30, cy + 60
        c2.move_to(ax - 10, ay - 55)
        c2.line_to(ax - 30, ay + 10)
        c2.line_to(ax + 45, ay + 25)
        c2.close_path()
        src(c2, col)
        c2.fill()

    # --- texto enorme
    texto_contorno(c2, "NO DEBÍ", 60, 830, 230, hx("#ffffff"), grosor=20, rot=-0.04)
    texto_contorno(c2, "SUBIR", 70, 1035, 260, hx("#ffd400"), grosor=22, rot=-0.04, brillo=hx("#ff2a1f"))

    # --- reloj digital 03:17
    with tf(c2, 250, 125, r=-0.05):
        rr(c2, -190, -85, 380, 150, 18)
        src(c2, (0.02, 0.02, 0.02, 0.92))
        c2.fill_preserve()
        c2.set_line_width(6)
        src(c2, hx("#ff1e1e"))
        c2.stroke()
        resplandor(c2, 0, -10, 230, hx("#ff1e1e"), 0.5)
        c2.select_font_face("Courier Prime", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c2.set_font_size(120)
        e = c2.text_extents("03:17")
        c2.move_to(-e.x_advance / 2, 30)
        src(c2, hx("#ff3b30"))
        c2.show_text("03:17")

    s2.write_to_png(os.path.join(SALIDA, "ultimo_tren_miniatura_1080p.png"))
    # versión 1280x720 para YouTube
    peq = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1280, 720)
    cp = cairo.Context(peq)
    cp.scale(1280 / W, 720 / H)
    pat = cairo.SurfacePattern(s2)
    pat.set_filter(cairo.FILTER_BEST)
    cp.set_source(pat)
    cp.paint()
    peq.write_to_png(os.path.join(SALIDA, "ultimo_tren_miniatura.png"))
    print("miniatura lista")


if __name__ == "__main__":
    main()
