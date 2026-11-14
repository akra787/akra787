#!/usr/bin/env python3
"""Miniaturas «NO DEBÍ SUBIR»: vertical 1080x1920 y horizontal 1280x720."""
import math
import os
import sys

import cairo
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor import AQUI, H, TITULO, W, a_numpy, a_superficie, hx, mul, posproceso, resplandor, superficie, texto  # noqa
from escenarios import Cam, anden  # noqa: E402
from personajes import ANCIANA, BRYAN, busto, figura  # noqa: E402

SALIDA = os.path.join(AQUI, "..")


def escena():
    s, c = superficie()
    cam = Cam(x=-3.4, y=1.5, z=6.4, yaw=1.5708, niebla=(0.01, 0.015, 0.02), densidad=0.06)
    anden(c, cam, 1.3, oscuro=True, luces=0, nombre="", maquina=False, panel=False, reloj=False, banco=False,
          tren=dict(z=3.5, puertas=1.0, luz=1.0, faro=0.0))
    # la anciana asomada dentro del vagón, sonriendo
    # oscurecer la chapa del tren: solo brilla la puerta
    c.rectangle(0, 0, W, H)
    g = cairo.RadialGradient(W * 0.55, H * 0.52, 150, W * 0.55, H * 0.52, 900)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.75)
    c.set_source(g)
    c.fill()
    with tf_a(c, 0.95):
        figura(c, W * 0.6, H * 0.69, 760, ANCIANA, T=0.0, expr="inquietante", mira=(-0.4, 0.0))
    # Bryan de espaldas, a un lado
    figura(c, W * 0.27, H * 1.08, 1250, BRYAN, T=0.0, espalda=True)
    arr = a_numpy(s)
    arr = posproceso(arr, 1.0, 2, dict(niebla=0.35, grano=0.05, vineta=1.2, gradacion=1.0))
    return a_superficie(np.clip(arr, 0, 1))


class tf_a:
    def __init__(self, c, a):
        self.c, self.a = c, a

    def __enter__(self):
        self.c.push_group()

    def __exit__(self, *e):
        self.c.pop_group_to_source()
        self.c.paint_with_alpha(self.a)


def rotulo(c, cx, y, tam, ancho_max):
    texto(c, "NO DEBÍ", cx, y, TITULO, tam, hx("#f4f6f7"), espaciado=6, sombra=(0, 10, (0, 0, 0, 0.85)),
          negrita=True)
    for k in range(3):
        texto(c, "SUBIR", cx, y + tam * 1.05, TITULO, tam * 1.35, hx("#ff2a2a", 0.18), espaciado=10, negrita=True)
    texto(c, "SUBIR", cx, y + tam * 1.05, TITULO, tam * 1.35, hx("#e0262f"), espaciado=10, negrita=True,
          sombra=(0, 10, (0, 0, 0, 0.85)))


def main():
    base = escena()
    # ---- vertical
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(s)
    c.set_source_surface(base)
    c.paint()
    c.rectangle(0, 0, W, H * 0.42)
    c.set_source(cairo.LinearGradient(0, 0, 0, H * 0.42))
    g = cairo.LinearGradient(0, 0, 0, H * 0.42)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.85)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.0)
    c.set_source(g)
    c.fill()
    resplandor(c, W / 2, 330, 520, hx("#e0262f"), 0.35)
    rotulo(c, W / 2, 330, 230, W)
    s.write_to_png(os.path.join(SALIDA, "ultimo_tren_miniatura_vertical.png"))
    # ---- horizontal: recorte de la escena + rótulo a la izquierda
    hw, hh = 1280, 720
    s2 = cairo.ImageSurface(cairo.FORMAT_ARGB32, hw, hh)
    c2 = cairo.Context(s2)
    c2.rectangle(0, 0, hw, hh)
    c2.set_source_rgb(0.01, 0.015, 0.02)
    c2.fill()
    esc = hh / (H * 0.5)
    c2.save()
    c2.translate(hw - W * esc + 40, -H * 0.2 * esc)
    c2.scale(esc, esc)
    c2.set_source_surface(base)
    c2.paint()
    c2.restore()
    g = cairo.LinearGradient(0, 0, hw * 0.75, 0)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.95)
    g.add_color_stop_rgba(0.55, 0, 0, 0, 0.7)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.0)
    c2.rectangle(0, 0, hw, hh)
    c2.set_source(g)
    c2.fill()
    resplandor(c2, 330, 330, 380, hx("#e0262f"), 0.3)
    rotulo(c2, 330, 300, 190, 600)
    s2.write_to_png(os.path.join(SALIDA, "ultimo_tren_miniatura.png"))
    print("miniaturas listas")


if __name__ == "__main__":
    main()
