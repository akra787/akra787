"""Planos 2D: insertos (reloj, panel, móvil, carteles, fotos, CCTV…) y la vista por la ventana del túnel."""
import math

import cairo

from motor import (H, MAQ, SANS, SERIF, TITULO, W, cl, eio, eo, fbm1, hash1, hx, lerp, lerpc, lgrad, mul, parpadeo,
                   pr, rect, resplandor, rgrad, rr, src, ss, texto, tf, cono_luz)
from personajes import (ANCIANA, BRYAN, MADRE, busto, cara, cabeza_perfil, figura, figura_perfil, osito, silueta)
from escenarios import reloj_estacion


def fondo(c, col):
    c.rectangle(0, 0, W, H)
    src(c, col)
    c.fill()


def lluvia_polvo(c, T, n=60, col=(0.8, 0.9, 1.0), alfa=0.25, semilla=0.0, vel=12):
    """Motas de polvo flotando en la luz."""
    for i in range(n):
        x = (hash1(i * 3.1 + semilla) * W + math.sin(T * 0.3 + i) * 30) % W
        y = (hash1(i * 7.7 + semilla) * H - T * vel * (0.5 + hash1(i))) % H
        r = 1 + 2.5 * hash1(i * 1.3)
        a = alfa * (0.5 + 0.5 * math.sin(T * 1.5 + i))
        c.arc(x, y, r, 0, 2 * math.pi)
        src(c, col + (a,))
        c.fill()


# ----------------------------------------------------------------- título
def titulo_tunel(c, t, T, d, texto_on=1.0):
    fondo(c, hx("#020304"))
    # paredes del túnel en perspectiva (anillos)
    cx, cy = W / 2, H * 0.47
    for k in range(18, 0, -1):
        z = k - (T * 1.5) % 1
        s = 900 / max(z, 0.3)
        a = cl(0.5 - z * 0.025)
        c.arc(cx, cy, s * 1.2, 0, 2 * math.pi)
        c.set_line_width(max(1, s * 0.05))
        src(c, (0.25, 0.32, 0.35, a * 0.5))
        c.stroke()
    # faro que se acerca
    k = ss(t / d)
    r = lerp(20, 260, k)
    flick = 0.85 + 0.15 * math.sin(T * 30)
    for dx in (-1, 1):
        resplandor(c, cx + dx * r * 0.9, cy + r * 0.6, r * 2.5, hx("#fff2d0"), 0.9 * flick)
        c.arc(cx + dx * r * 0.9, cy + r * 0.6, r * 0.12, 0, 2 * math.pi)
        src(c, hx("#fffaf0"))
        c.fill()
    if texto_on > 0:
        a = cl(pr(t, 0.2, 0.8)) * texto_on
        temb = (hash1(math.floor(T * 20)) - 0.5) * 6 * (1 - pr(t, 0.4, 1.2))
        texto(c, "EL ÚLTIMO TREN", W / 2 + temb, H * 0.24, TITULO, 170, hx("#e8eef0", a), espaciado=6,
              sombra=(0, 8, (0, 0, 0, 0.7 * a)))
        texto(c, "DE LA NOCHE", W / 2, H * 0.24 + 120, TITULO, 110, hx("#b8323a", a), espaciado=22)
        c.rectangle(W / 2 - 220 * a, H * 0.24 + 150, 440 * a, 3)
        src(c, hx("#b8323a", a * 0.8))
        c.fill()
    return dict(niebla=0.6, grano=0.06)


# ----------------------------------------------------------------- reloj
def reloj_cerca(c, t, T, d, parado=False):
    fondo(c, hx("#0b1013"))
    luz = parpadeo(T, 3.3, 1.0)
    # pared de azulejos desenfocada
    for i in range(12):
        for j in range(20):
            x, y = i * 100 - 20, j * 100 - 30
            rr(c, x + 4, y + 4, 92, 92, 6)
            src(c, mul(hx("#5b6b66"), 0.35 + 0.15 * hash1(i * 31 + j), 1))
            c.fill()
    resplandor(c, W * 0.3, -100, 900, hx("#d8f0ff"), 0.5 * luz)
    z = 1 + 0.06 * t / d
    with tf(c, W / 2, H * 0.47, s=z):
        reloj_estacion(c, 0, 0, 380, 3, 17, T, ilum=luz, segundos=0 if parado else (T * 1.0) % 60)
    return dict(niebla=0.25, luz=0.75 + 0.25 * luz)


# ----------------------------------------------------------------- panel de salidas
def panel_salidas(c, t, T, d, fase="normal", zoom=0.0):
    fondo(c, hx("#06090b"))
    z = 1 + 0.05 * t / d + zoom
    with tf(c, W / 2, H * 0.45, s=z):
        rr(c, -500, -420, 1000, 840, 24)
        src(c, hx("#151a1d"))
        c.fill()
        rr(c, -470, -390, 940, 780, 14)
        src(c, hx("#050505"))
        c.fill()
        ambar = hx("#ffb347")
        rojo = hx("#ff4636")
        texto(c, "PRÓXIMOS TRENES", -430, -320, MAQ, 46, mul(ambar, 1, 0.9), ancla=0, negrita=True)
        texto(c, "03:17", 430, -320, MAQ, 46, mul(ambar, 1, 0.9), ancla=1, negrita=True)
        c.rectangle(-430, -295, 860, 3)
        src(c, mul(ambar, 1, 0.4))
        c.fill()
        filas = [("L2", "CENTRO", "--:--", "CANCELADO"), ("L2", "CENTRO", "--:--", "CANCELADO")]
        for k, (l, dest, h, est) in enumerate(filas):
            y = -210 + k * 95
            texto(c, f"{l}  {dest:<10}{h}", -430, y, MAQ, 50, mul(ambar, 1, 0.55), ancla=0, negrita=True)
            texto(c, est, -430, y + 42, MAQ, 30, mul(ambar, 1, 0.35), ancla=0)
        if fase != "normal":
            # fila nueva que aparece con interferencias
            k = pr(t, 0.1, 0.6)
            gl = hash1(math.floor(T * 14)) > 0.75
            y = 40
            a = k * (0.4 if gl else 1.0)
            rr(c, -450, y - 70, 900, 330, 10)
            src(c, (0.3, 0.05, 0.03, 0.25 * k))
            c.fill()
            dx = (hash1(math.floor(T * 22)) - 0.5) * 30 if gl else 0
            texto(c, "??   ---------", -430 + dx, y, MAQ, 56, mul(rojo, 1, a), ancla=0, negrita=True)
            if fase in ("destino", "hora"):
                n = int(pr(t, 0.3, 1.2) * len("DESCONOCIDO")) if fase == "destino" else 11
                texto(c, "DESTINO:", -430, y + 95, MAQ, 56, mul(ambar, 1, k), ancla=0, negrita=True)
                texto(c, "DESCONOCIDO"[:n] + ("_" if fase == "destino" and math.sin(T * 10) > 0 else ""),
                      -430 + 290, y + 95, MAQ, 56, mul(rojo, 1, k), ancla=0, negrita=True)
            if fase == "hora":
                kk = pr(t, 0.4, 0.4)
                texto(c, "LLEGADA:", -430, y + 190, MAQ, 56, mul(ambar, 1, kk), ancla=0, negrita=True)
                bl = 0.55 + 0.45 * (math.sin(T * 6) > 0)
                texto(c, "03:17", -430 + 290, y + 190, MAQ, 56, mul(rojo, 1, kk * bl), ancla=0, negrita=True)
        # rejilla de LED
        c.set_line_width(2)
        src(c, (0, 0, 0, 0.35))
        for yy in range(-390, 390, 7):
            c.move_to(-470, yy)
            c.line_to(470, yy)
        c.stroke()
    resplandor(c, W / 2, H * 0.47, 700, hx("#ff8a3a"), 0.18)
    return dict(niebla=0.15, glitch=0.25 if (fase != "normal" and hash1(math.floor(T * 9)) > 0.8) else 0)


# ----------------------------------------------------------------- móvil
def movil(c, t, T, d):
    fondo(c, hx("#05080a"))
    k = eo(pr(t, 0, 0.6))
    with tf(c, W / 2, H * 0.52 + (1 - k) * 300, r=-0.06):
        # mano
        c.move_to(-260, 150)
        c.curve_to(-330, 350, -250, 700, -120, 900)
        c.line_to(260, 900)
        c.curve_to(300, 600, 300, 300, 250, 150)
        c.close_path()
        src(c, mul(BRYAN["piel"], 0.55))
        c.fill()
        rr(c, -230, -470, 460, 920, 60)
        src(c, hx("#0d0f10"))
        c.fill()
        rr(c, -210, -450, 420, 880, 44)
        src(c, hx("#1b2a33"))
        c.fill_preserve()
        c.set_source(lgrad(0, -450, 0, 430, [(0, hx("#2b4a5a")), (1, hx("#0d1820"))]))
        c.fill()
        texto(c, "03:17", 0, -230, SANS, 150, hx("#f2f6f8"), negrita=True)
        texto(c, "viernes, 14 de noviembre", 0, -160, SANS, 30, hx("#cfe0e8", 0.8))
        # barras sin señal
        for i in range(4):
            rect(c, -180 + i * 16, -415 - i * 7, 10, 10 + i * 7, hx("#ffffff", 0.25))
        texto(c, "✕", -100, -400, SANS, 26, hx("#ff5a4a"))
        kk = pr(t, 0.35, 0.3)
        with tf(c, 0, 40, s=lerp(0.85, 1.0, eo(kk)), a=kk):
            rr(c, -180, -70, 360, 150, 26)
            src(c, hx("#f1f4f5", 0.94))
            c.fill()
            texto(c, "Sin cobertura", 0, -5, SANS, 40, hx("#c0392b"), negrita=True)
            texto(c, "Solo llamadas de emergencia", 0, 45, SANS, 24, hx("#4b5a62"))
    resplandor(c, W / 2, H * 0.45, 600, hx("#7fc8ff"), 0.25)
    return dict(niebla=0.1)


# ----------------------------------------------------------------- ventana del túnel (vista lateral 2D)
def ventana_tunel(c, t, T, d, vel=1.0, rojo=0.0, siluetas=0.0, doble=None, golpes=(), marco=True, luz_int=1.0,
                  estacion=None, letrero=0.0, zoom=1.0, foco=(0.5, 0.5), reflejo=0.0):
    """Lo que se ve por la ventana. doble: dict(fase, expr, habla, mano) para el hombre que corre."""
    fondo(c, hx("#030405"))
    with tf(c, W * foco[0], H * foco[1], s=zoom):
        c.translate(-W * foco[0], -H * foco[1])
        desp = T * 900 * vel
        # pared del túnel: bloques húmedos con parallax
        for capa, (vk, y0, y1, colc) in enumerate(((0.35, 300, 1650, hx("#141a1a")), (1.0, 250, 1700, hx("#1f2725")))):
            ancho = 260 if capa else 400
            off = (desp * vk) % ancho
            for i in range(-1, W // ancho + 2):
                x = i * ancho - off
                n = int((desp * vk + x) // ancho)
                colb = mul(colc, 0.8 + 0.4 * hash1(n * 1.7 + capa))
                rect(c, x, y0, ancho - 6, y1 - y0, colb)
                # manchas de humedad y gotas
                if capa:
                    for g in range(3):
                        gx = x + 30 + hash1(n * 3 + g) * (ancho - 60)
                        gl = 200 + 500 * hash1(n * 5 + g)
                        c.set_source(lgrad(0, y0, 0, y0 + gl, [(0, hx("#4a5a55", 0.0)), (0.3, hx("#4a5a55", 0.35)),
                                                               (1, hx("#4a5a55", 0.0))]))
                        c.rectangle(gx, y0, 6 + 10 * hash1(n + g), gl)
                        c.fill()
                        gy = y0 + ((T * 220 + hash1(n * 9 + g) * 900) % gl)
                        c.arc(gx + 5, gy, 4, 0, 2 * math.pi)
                        src(c, hx("#b8d0d0", 0.5))
                        c.fill()
                    # cables tendidos a lo largo del túnel
                    for kc in range(2):
                        yc = 430 + kc * 46
                        c.move_to(x - 3, yc)
                        c.line_to(x + ancho + 3, yc + 2)
                    c.set_line_width(9)
                    src(c, hx("#080a0a"))
                    c.stroke()
                    # soporte
                    rect(c, x + ancho - 20, 400, 14, 110, hx("#2b3230"))
        # siluetas al otro lado de las vías
        if siluetas > 0:
            per = 1300
            off = (desp * 0.55) % per
            for i in range(-1, W // per + 2):
                x = i * per - off + 400
                n = int((desp * 0.55 + x) // per)
                if hash1(n * 2.3) < 0.75:
                    silueta(c, x, 1560, 700, col=(0.0, 0.0, 0.0, 0.92 * siluetas), T=T, semilla=n,
                            ojos=0.6 * siluetas * (hash1(n) > 0.5))
        # luces (rojas o cálidas) en el techo del túnel
        per = 700
        off = (desp * 1.0) % per
        col = lerpc(hx("#ffd9a0"), hx("#ff2a1f"), rojo)
        for i in range(-1, W // per + 2):
            x = i * per - off + 200
            rect(c, x - 40, 300, 80, 22, col)
            resplandor(c, x, 330, 520, col, 1.0)
            c.save()
            c.set_operator(cairo.OPERATOR_ADD)
            c.move_to(x - 40, 320)
            c.line_to(x + 40, 320)
            c.line_to(x + 260, 1700)
            c.line_to(x - 260, 1700)
            c.close_path()
            c.set_source(lgrad(0, 320, 0, 1700, [(0, mul(col, 1, 0.22)), (1, mul(col, 1, 0.0))]))
            c.fill()
            c.restore()
        if estacion:
            estacion(c, t, T)
        # el doble corriendo
        if doble:
            xd = W * 0.5 + doble.get("dx", 0)
            figura_perfil(c, xd, 1880 + doble.get("dy", 0), doble.get("alto", 1300), BRYAN, T=T, modo="corre",
                          fase=T * 1.6, expr=doble.get("expr", "terror"), habla=doble.get("habla", 0.0),
                          voltear=True, brazo_alzado=doble.get("mano", 0.0), golpe=doble.get("golpe", 0.0))
        # golpes de mano contra el cristal
        for tg in golpes:
            g = t - tg
            if 0 <= g < 1.2:
                a = cl(1 - g / 1.2)
                with tf(c, W * 0.52 + (hash1(tg) - 0.5) * 200, H * 0.42 + (hash1(tg + 1) - 0.5) * 200,
                        s=1.0 + 0.15 * (1 - eo(cl(g / 0.12)))):
                    mano_palma(c, a)
    if marco:
        # marco de la ventana y pared interior del vagón
        luz = luz_int * (1 - 0.65 * rojo)
        pared = lerpc(hx("#111517"), hx("#7f8b8e"), luz)
        c.rectangle(0, 0, W, H)
        rr(c, 70, 330, W - 140, 1150, 50)
        c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        src(c, pared)
        c.fill()
        c.set_fill_rule(cairo.FILL_RULE_WINDING)
        rr(c, 70, 330, W - 140, 1150, 50)
        c.set_line_width(26)
        src(c, mul(pared, 0.6))
        c.stroke()
        rr(c, 70, 330, W - 140, 1150, 50)
        c.set_line_width(6)
        src(c, mul(pared, 1.15))
        c.stroke()
        # reflejo del interior en el cristal
        c.save()
        rr(c, 70, 330, W - 140, 1150, 50)
        c.clip()
        c.set_source(lgrad(0, 330, W, 1480, [(0, (1, 1, 1, 0.05 * luz)), (0.45, (1, 1, 1, 0.0)),
                                             (0.55, (1, 1, 1, 0.07 * luz)), (0.6, (1, 1, 1, 0))]))
        c.paint()
        if reflejo > 0:
            cara(c, W * 0.3, H * 0.4, 160, ANCIANA, T, expr="inquietante", ilum=1.0)
            src(c, (0.03, 0.04, 0.05, 1 - reflejo * 0.35))
            c.paint()
        c.restore()
        # banco y respaldo
        rect(c, 0, 1560, W, 360, mul(hx("#2b4c5e"), 0.3 + 0.7 * luz))
        rect(c, 0, 1540, W, 30, mul(hx("#203845"), 0.3 + 0.7 * luz))
    if letrero > 0:
        # «¡NO BAJES!» vaho escrito
        a = letrero
        texto(c, "¡NO BAJES!", W / 2 + (hash1(math.floor(T * 30)) - 0.5) * 10, H * 0.36, TITULO, 210,
              hx("#ff3b30", a), espaciado=8, sombra=(0, 0, (0, 0, 0, 0)))
    return dict(niebla=0.2, rojo=0.1 * rojo)


def mano_palma(c, a=1.0, col=None, escala=1.0):
    """Palma apretada contra el cristal, vista desde dentro."""
    col = col or BRYAN["piel"]
    piel = lerpc(col, hx("#d8c8c0"), 0.35)
    with tf(c, 0, 0, s=escala):
        # vaho alrededor
        c.arc(0, -40, 300, 0, 2 * math.pi)
        c.set_source(rgrad(0, -40, 120, 300, [(0, hx("#dfe8ea", 0.3 * a)), (1, hx("#dfe8ea", 0))]))
        c.fill()
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        for ang, largo, ancho in ((-0.32, 190, 44), (-0.1, 225, 46), (0.1, 230, 46), (0.3, 200, 42)):
            dx = math.sin(ang) * 60
            c.move_to(dx, -60)
            c.line_to(dx + math.sin(ang) * largo, -60 - math.cos(ang) * largo)
            c.set_line_width(ancho)
            src(c, mul(piel, 1, a))
            c.stroke()
            # yema aplastada (más clara)
            c.arc(dx + math.sin(ang) * largo, -60 - math.cos(ang) * largo, ancho * 0.42, 0, 2 * math.pi)
            src(c, mul(hx("#efe2dc"), 1, 0.8 * a))
            c.fill()
        # pulgar
        c.move_to(-85, 40)
        c.line_to(-185, -50)
        c.set_line_width(48)
        src(c, mul(piel, 1, a))
        c.stroke()
        c.save()
        c.scale(1.0, 1.1)
        c.arc(0, 10, 115, 0, 2 * math.pi)
        c.restore()
        src(c, mul(piel, 1, a))
        c.fill_preserve()
        c.set_source(rgrad(0, 10, 10, 125, [(0, mul(hx("#f2e6e0"), 1, 0.6 * a)), (1, mul(piel, 0.8, 0.0))]))
        c.fill()
        # muñeca y manga
        rr(c, -95, 100, 190, 320, 60)
        src(c, mul(BRYAN["torso"], 0.8, a))
        c.fill()


# ----------------------------------------------------------------- carteles
def cartel_san_miguel(c, t, T, d):
    fondo(c, hx("#0a0806"))
    luz = parpadeo(T, 8.8, 1.3)
    # pared vieja
    for i in range(14):
        for j in range(22):
            x, y = i * 80 - 10 + (j % 2) * 40, j * 90
            rr(c, x + 3, y + 3, 74, 84, 4)
            src(c, mul(hx("#6c6a55"), (0.3 + 0.2 * hash1(i * 17 + j)) * luz))
            c.fill()
    z = 1.0 + 0.08 * t / d
    with tf(c, W / 2, H * 0.44, s=z, r=-0.03):
        rr(c, -480, -180, 960, 360, 30)
        src(c, mul(hx("#2a3a52"), 0.4 + 0.6 * luz))
        c.fill()
        rr(c, -455, -155, 910, 310, 20)
        c.set_line_width(10)
        src(c, mul(hx("#e8e2cf"), 0.4 + 0.6 * luz))
        c.stroke()
        texto(c, "SAN MIGUEL", 0, 10, TITULO, 190, mul(hx("#efe8d2"), 0.4 + 0.6 * luz), espaciado=10)
        texto(c, "1986", 0, 120, TITULO, 100, mul(hx("#d6453a"), 0.4 + 0.6 * luz), espaciado=30)
        # óxido
        for k in range(26):
            x, y = (hash1(k * 3.3) - 0.5) * 920, (hash1(k * 5.1) - 0.5) * 320
            r = 10 + 40 * hash1(k * 9.1)
            c.arc(x, y, r, 0, 2 * math.pi)
            c.set_source(rgrad(x, y, 0, r, [(0, hx("#5a2e14", 0.75)), (1, hx("#5a2e14", 0))]))
            c.fill()
    resplandor(c, W * 0.5, H * 0.15, 800, hx("#ff6a4a"), 0.35 * luz)
    return dict(niebla=0.45, niebla_color=(0.35, 0.3, 0.28), luz=0.6 + 0.4 * luz)


def cartel_accidente(c, cx, cy, s, a=1.0, luz=1.0):
    with tf(c, cx, cy, s=s, a=a):
        rr(c, -430, -140, 860, 280, 8)
        src(c, mul(hx("#d9d3c0"), luz))
        c.fill()
        rr(c, -410, -120, 820, 240, 4)
        c.set_line_width(6)
        src(c, mul(hx("#1a1a1a"), luz))
        c.stroke()
        texto(c, "ACCIDENTE FERROVIARIO", 0, -15, TITULO, 92, mul(hx("#1c1c1c"), luz), espaciado=4)
        texto(c, "14 DE NOVIEMBRE DE 1996", 0, 80, TITULO, 70, mul(hx("#8a1c1c"), luz), espaciado=6)


def foto_accidente(c, x, y, w, h, T=0.0, sepia=1.0):
    """Fotografía antigua: tren destrozado, ambulancias y mantas."""
    with tf(c, x, y):
        rect(c, -w / 2 - 14, -h / 2 - 14, w + 28, h + 60, hx("#e7e1d2"))
        c.save()
        c.rectangle(-w / 2, -h / 2, w, h)
        c.clip()
        rect(c, -w / 2, -h / 2, w, h, hx("#3b3a35"))
        c.set_source(lgrad(0, -h / 2, 0, h / 2, [(0, hx("#6d6a60")), (0.55, hx("#45433d")), (1, hx("#25241f"))]))
        c.paint()
        # vagón volcado
        with tf(c, -w * 0.05, h * 0.05, r=-0.35):
            rr(c, -w * 0.38, -h * 0.13, w * 0.76, h * 0.26, 12)
            src(c, hx("#8b8a82"))
            c.fill()
            for k in range(6):
                rect(c, -w * 0.33 + k * w * 0.11, -h * 0.08, w * 0.07, h * 0.08, hx("#1a1a18"))
            c.move_to(w * 0.38, -h * 0.13)
            c.line_to(w * 0.45, -h * 0.02)
            c.line_to(w * 0.36, h * 0.05)
            c.line_to(w * 0.42, h * 0.13)
            c.line_to(w * 0.3, h * 0.13)
            c.close_path()
            src(c, hx("#55544e"))
            c.fill()
        # ambulancias
        for k, ax in enumerate((-0.4, 0.3)):
            bx, by = w * ax, h * 0.3
            rr(c, bx - 60, by - 40, 120, 70, 8)
            src(c, hx("#cfccc2"))
            c.fill()
            rect(c, bx - 10, by - 30, 20, 50, hx("#5a5a52"))
            rect(c, bx - 25, by - 15, 50, 20, hx("#5a5a52"))
            resplandor(c, bx, by - 48, 60, hx("#ffffff"), 0.4 + 0.3 * math.sin(T * 6 + k))
        # mantas
        for k in range(7):
            bx = -w * 0.42 + k * w * 0.13
            by = h * 0.42
            c.save()
            c.translate(bx, by)
            c.scale(48, 16)
            c.arc(0, 0, 1, 0, 2 * math.pi)
            c.restore()
            src(c, hx("#b9b6aa"))
            c.fill()
        c.restore()
        # sepia + arañazos
        c.rectangle(-w / 2, -h / 2, w, h)
        src(c, hx("#704a1c", 0.22 * sepia))
        c.fill()
        c.set_line_width(1.5)
        src(c, hx("#ffffff", 0.25))
        for k in range(8):
            xx = (hash1(k * 4.4) - 0.5) * w
            c.move_to(xx, -h / 2)
            c.line_to(xx + 20 * (hash1(k) - 0.5), h / 2)
        c.stroke()


def foto_victima(c, x, y, s, spec, nombre="", fecha="", luz=1.0, es_bryan=False, T=0.0):
    with tf(c, x, y, s=s):
        rect(c, -110, -140, 220, 330, mul(hx("#e4dece"), luz))
        c.save()
        c.rectangle(-95, -125, 190, 230)
        c.clip()
        rect(c, -95, -125, 190, 230, mul(hx("#3d4247"), luz))
        busto(c, 0, -30, 52, spec, T=0, expr="neutral", parp=1.0, respira=0)
        src(c, hx("#5b3d1b", 0.25))
        c.paint()
        if luz < 1:
            src(c, (0, 0, 0, 1 - luz))
            c.paint()
        c.restore()
        if nombre:
            texto(c, nombre, 0, 145, TITULO, 52 if es_bryan else 44, mul(hx("#1a1a1a"), luz), espaciado=2)
        if fecha:
            texto(c, fecha, 0, 178, MAQ, 22, mul(hx("#7a1a1a"), luz), negrita=True)


def tablon_victimas(c, t, T, d, foco=0.0, revela_nombre=0.0, revela_fecha=0.0, luz=1.0):
    """Mosaico de fotografías de las víctimas; foco 0..1 acerca a la foto de Bryan."""
    fondo(c, hx("#050506"))
    import random
    rnd = random.Random(4)
    specs = []
    from personajes import GUARDIA, HOMBRE, NINA, SOMBRA
    paleta = [HOMBRE, GUARDIA, NINA, ANCIANA, MADRE, SOMBRA]
    z = lerp(1.0, 2.7, eio(foco))
    bx, by = 250, 1040  # foto de Bryan (centrada un poco por debajo para que se lea el nombre)
    nombres = ["LUIS", "MARTA", "ANA", "PEDRO", "ELENA", "JOSÉ", "CARMEN", "RAÚL", "SARA", "TOMÁS", "LUCÍA",
               "IVÁN", "ROSA", "DANI", "EVA", "JUAN"]
    with tf(c, W / 2, H * 0.5, s=z):
        c.translate(-W / 2 - (bx - W / 2) * eio(foco), -H * 0.5 - (by - H * 0.5) * eio(foco))
        rect(c, 30, 300, W - 60, 1300, mul(hx("#2a2118"), luz))
        for j in range(4):
            for i in range(4):
                if i == 0 and j == 1:
                    continue
                x, y = 160 + i * 250, 460 + j * 360
                rot = (rnd.random() - 0.5) * 0.1
                with tf(c, x, y, r=rot):
                    sp = dict(paleta[(i + j * 3) % len(paleta)])
                    if sp["nombre"] == "sombra":
                        sp = dict(HOMBRE, pelo=hx("#2a2018"), torso=hx("#3b4a3a"))
                    foto_victima(c, 0, 0, 1.0, sp, nombre=nombres[(i + j * 4) % 16], fecha="† 14·11·1996",
                                 luz=luz * 0.9)
                    c.arc(0, -150, 9, 0, 2 * math.pi)
                    src(c, hx("#9b2222"))
                    c.fill()
        with tf(c, 250, 980, r=-0.03):
            c.rectangle(-125, -150, 250, 370)
            src(c, (0, 0, 0, 0.5))
            c.fill()
            foto_victima(c, 0, 0, 1.0, BRYAN, nombre="BRYAN" if revela_nombre > 0.5 else "",
                         fecha="† 14·11·1996" if revela_fecha > 0.5 else "", luz=luz, es_bryan=True)
            c.arc(0, -150, 9, 0, 2 * math.pi)
            src(c, hx("#9b2222"))
            c.fill()
    resplandor(c, W * 0.5, -50, 1200, hx("#ffd9a0"), 0.35 * luz)
    return dict(niebla=0.25, niebla_color=(0.4, 0.35, 0.3))


# ----------------------------------------------------------------- manos
def manos(c, t, T, d, corte=1.0, zoom=(1.0, 1.0)):
    fondo(c, hx("#0b0f11"))
    z = lerp(zoom[0], zoom[1], ss(t / d))
    # el dedo con el corte (índice de la mano derecha) queda en el centro al acercarse
    fxp, fyp = W / 2 + 230 - 60 * 1, 1050 - 120 - 120
    c.save()
    c.translate(W / 2, H * 0.42)
    c.scale(z, z)
    c.translate(-(W / 2 + (fxp - W / 2) * cl((z - 1) / 1.5)), -(H * 0.42 + (fyp - H * 0.42) * cl((z - 1) / 1.5)))
    # rodillas/vaqueros desenfocados
    c.set_source(lgrad(0, 1100, 0, H, [(0, hx("#1b2232")), (1, hx("#0d1018"))]))
    c.rectangle(0, 1100, W, H)
    c.fill()
    temb = math.sin(T * 23) * 3
    piel = BRYAN["piel"]
    for lado in (-1, 1):
        with tf(c, W / 2 + lado * 230 + temb, 1050, sx=lado, r=0.15 * lado):
            # palma hacia arriba
            c.move_to(-150, 220)
            c.curve_to(-190, 40, -150, -120, -40, -130)
            c.curve_to(80, -140, 160, -60, 150, 80)
            c.curve_to(140, 180, 60, 260, -150, 220)
            c.close_path()
            src(c, piel)
            c.fill_preserve()
            c.set_source(rgrad(0, 0, 20, 220, [(0, (1, 1, 1, 0.08)), (1, (0, 0, 0, 0.35))]))
            c.fill()
            for k, (ax, l) in enumerate(((-120, 190), (-60, 240), (5, 250), (70, 215))):
                with tf(c, ax, -120, r=-0.05 * (k - 1.5)):
                    rr(c, -24, -l, 50, l + 20, 24)
                    src(c, piel)
                    c.fill_preserve()
                    c.set_source(lgrad(-24, 0, 26, 0, [(0, (0, 0, 0, 0.25)), (0.5, (0, 0, 0, 0)), (1, (0, 0, 0, 0.2))]))
                    c.fill()
                    for f in (0.35, 0.65):
                        c.move_to(-16, -l * f)
                        c.line_to(16, -l * f)
                    c.set_line_width(3)
                    src(c, mul(BRYAN["piel_sombra"], 1, 0.5))
                    c.stroke()
                    if lado == 1 and k == 1 and corte > 0:
                        # corte limpio, sin sangre: carne pálida
                        c.move_to(-18, -l * 0.5)
                        c.curve_to(-5, -l * 0.47, 6, -l * 0.55, 20, -l * 0.52)
                        c.set_line_width(7 * corte)
                        src(c, hx("#efe1da"))
                        c.stroke()
                        c.move_to(-18, -l * 0.5)
                        c.curve_to(-5, -l * 0.47, 6, -l * 0.55, 20, -l * 0.52)
                        c.set_line_width(2)
                        src(c, hx("#8f6e66"))
                        c.stroke()
            rr(c, 140, 20, 90, 45, 22)
            src(c, piel)
            c.fill()
            # puño de la sudadera
            rr(c, -190, 190, 360, 160, 40)
            src(c, BRYAN["torso"])
            c.fill()
    c.restore()
    resplandor(c, W / 2, 400, 900, hx("#d8f0ff"), 0.3)
    return dict(niebla=0.1)


# ----------------------------------------------------------------- periódico y billetes
def periodico(c, t, T, d):
    fondo(c, hx("#0c0a08"))
    z = 1.0 + 0.1 * t / d
    with tf(c, W / 2, H * 0.48, s=z, r=0.04):
        rect(c, -460, -700, 920, 1400, hx("#d7cdb3"))
        texto(c, "EL DIARIO DE LA CIUDAD", 0, -610, SERIF, 52, hx("#1b1a17"), negrita=True)
        texto(c, "Viernes, 15 de noviembre de 1996", 0, -565, SERIF, 26, hx("#3b3a35"))
        c.rectangle(-420, -545, 840, 4)
        src(c, hx("#1b1a17"))
        c.fill()
        texto(c, "DESAPARECE UN TREN", 0, -440, TITULO, 120, hx("#141310"), espaciado=2)
        texto(c, "CON TODOS SUS PASAJEROS", 0, -340, TITULO, 82, hx("#141310"), espaciado=2)
        foto_accidente(c, 0, -60, 760, 380, T)
        for k in range(14):
            y = 200 + k * 30
            ww = 820 if k % 5 != 4 else 500
            rect(c, -410, y, ww * (0.45 if k < 7 else 1) - (0 if k < 7 else 0), 10, hx("#6b675c", 0.7))
            if k < 7:
                rect(c, 20, y, 390, 10, hx("#6b675c", 0.7))
        texto(c, "«Solo encontraron los billetes»", -410, 650, SERIF, 32, hx("#5a1a1a"), ancla=0)
        src(c, hx("#704a1c", 0.18))
        c.rectangle(-460, -700, 920, 1400)
        c.fill()
    return dict(niebla=0.2, niebla_color=(0.4, 0.33, 0.25), gradacion=0.6)


def billetes(c, t, T, d):
    fondo(c, hx("#0d1012"))
    # suelo del vagón
    for k in range(0, H, 140):
        rect(c, 0, k, W, 4, hx("#1a1f22"))
    for i in range(9):
        x = 140 + hash1(i * 2.2) * 800
        y = 300 + hash1(i * 3.7) * 1300
        caida = eo(pr(t, i * 0.12, 0.8))
        rot = (hash1(i * 5.1) - 0.5) * 1.2 + (1 - caida) * 2
        with tf(c, x, y - (1 - caida) * 400, r=rot, a=caida):
            rr(c, -150, -70, 300, 140, 8)
            src(c, hx("#e3dcc7"))
            c.fill()
            rect(c, -150, -70, 300, 34, hx("#1f5560"))
            texto(c, "BILLETE SENCILLO", 0, -45, SANS, 20, hx("#f2f2f2"), negrita=True)
            texto(c, "14-11-1996", -130, 5, MAQ, 26, hx("#2a2a2a"), ancla=0, negrita=True)
            texto(c, "03:17", -130, 45, MAQ, 26, hx("#8a1c1c"), ancla=0, negrita=True)
            c.set_line_width(2)
            src(c, hx("#5a5a5a", 0.6))
            c.set_dash([6, 6])
            c.move_to(90, -36)
            c.line_to(90, 70)
            c.stroke()
            c.set_dash([])
    cono_luz(c, W / 2, 0, 200, 1200, H, hx("#d8f0ff"), 0.8)
    return dict(niebla=0.3)


# ----------------------------------------------------------------- megafonía
def megafonia(c, t, T, d, texto_on=0.0):
    fondo(c, hx("#cfd8da"))
    luz = parpadeo(T, 4.2, 1.2)
    c.set_source(lgrad(0, 0, 0, H, [(0, hx("#9aa6a9")), (1, hx("#4a5356"))]))
    c.paint()
    with tf(c, W / 2, H * 0.32, s=1.0 + 0.05 * t / d):
        c.arc(0, 0, 260, 0, 2 * math.pi)
        src(c, hx("#2a3033"))
        c.fill()
        for i in range(-9, 10):
            for j in range(-9, 10):
                if i * i + j * j < 80:
                    c.arc(i * 26, j * 26, 8, 0, 2 * math.pi)
        src(c, hx("#0b0d0e"))
        c.fill()
    with tf(c, W / 2, H * 0.68):
        rr(c, -470, -120, 940, 240, 16)
        src(c, hx("#0a0a0a"))
        c.fill()
        if texto_on > 0:
            msg = "PRÓXIMA PARADA:  DESTINO FINAL   ·   "
            off = (T * 260) % (len(msg) * 34)
            c.save()
            rr(c, -450, -100, 900, 200, 10)
            c.clip()
            for rep in range(3):
                texto(c, msg, -450 - off + rep * len(msg) * 34, 30, MAQ, 62, hx("#ff4636", texto_on), ancla=0,
                      negrita=True)
            c.restore()
    return dict(niebla=0.15, luz=0.55 + 0.45 * luz, aberracion=2)


# ----------------------------------------------------------------- flashback del accidente
def flashback(c, t, T, d, fase="ruido"):
    fondo(c, hx("#140504"))
    rnd_t = math.floor(T * 12)
    if fase in ("ruido", "cristales", "gritos"):
        # interior volcándose
        ang = math.sin(T * 7) * 0.25 + (0.6 if fase != "ruido" else 0.0) * eo(pr(t, 0, 0.5))
        with tf(c, W / 2, H / 2, r=ang, s=1.2):
            for k in range(6):
                y = -800 + k * 300
                rect(c, -900, y, 1800, 160, hx("#3a1a18", 0.6))
            rect(c, -900, -200, 1800, 400, hx("#e8d0c0", 0.25 + 0.25 * (hash1(rnd_t) > 0.5)))
            for k in range(5):
                x = -700 + k * 330
                c.move_to(x, -900)
                c.line_to(x, 900)
            c.set_line_width(30)
            src(c, hx("#8a8f92", 0.6))
            c.stroke()
    if fase == "cristales":
        for i in range(70):
            a = hash1(i * 1.7) * 2 * math.pi
            v = 400 + 1200 * hash1(i * 2.9)
            g = cl(t / 1.4)
            x = W / 2 + math.cos(a) * v * g
            y = H * 0.45 + math.sin(a) * v * g + 600 * g * g
            s = 10 + 50 * hash1(i * 4.2)
            with tf(c, x, y, r=T * 6 * (hash1(i) - 0.5) * 3):
                c.move_to(-s, -s * 0.3)
                c.line_to(s * 0.4, -s)
                c.line_to(s, s * 0.5)
                c.close_path()
                src(c, hx("#dff3ff", 0.8))
                c.fill_preserve()
                c.set_line_width(2)
                src(c, hx("#ffffff", 0.9))
                c.stroke()
        # grietas
        c.set_line_width(4)
        src(c, hx("#ffffff", 0.7))
        for i in range(12):
            a = i / 12 * 2 * math.pi + 0.2
            x, y = W / 2, H * 0.45
            c.move_to(x, y)
            for k in range(5):
                x += math.cos(a + (hash1(i * 7 + k) - 0.5)) * 140
                y += math.sin(a + (hash1(i * 7 + k) - 0.5)) * 140
                c.line_to(x, y)
            c.stroke()
    if fase == "gritos":
        for i in range(5):
            x = 150 + i * 200 + math.sin(T * 9 + i) * 20
            silueta(c, x, 1700 + (i % 2) * 80, 900, col=(0.05, 0.0, 0.0, 0.9), T=T, semilla=i,
                    ladeo=math.sin(T * 5 + i) * 0.2)
    fl = 1.0 if hash1(rnd_t * 3.3) > 0.6 else 0.0
    if fase == "nada":
        fondo(c, hx("#000000"))
        fl = 0
    return dict(rojo=0.55 if fase != "nada" else 0, luz=0.75 + 0.6 * fl, glitch=0.5 if fase != "nada" else 0,
                aberracion=6 if fase != "nada" else 0, niebla=0.0, sacudida=12 if fase != "nada" else 0)


# ----------------------------------------------------------------- foto madre (recuerdo)
def foto_madre(c, t, T, d):
    fondo(c, hx("#0a0907"))
    z = 1.0 + 0.08 * t / d
    with tf(c, W / 2, H * 0.47, s=z, r=-0.05):
        rect(c, -400, -470, 800, 980, hx("#ece6d6"))
        c.save()
        c.rectangle(-360, -430, 720, 760)
        c.clip()
        c.set_source(lgrad(0, -430, 0, 330, [(0, hx("#c9b590")), (1, hx("#7a8a6a"))]))
        c.paint()
        resplandor(c, 250, -330, 400, hx("#fff2c0"), 0.8)
        figura(c, -80, 330, 820, MADRE, T=0, expr="sonrisa", brazos="abajo")
        nino = dict(BRYAN, torso=hx("#c0392b"), torso_luz=hx("#e05a4a"), barba=0, capucha=False)
        figura(c, 170, 330, 470, nino, T=0, expr="sonrisa")
        src(c, hx("#704a1c", 0.25))
        c.paint()
        c.restore()
        texto(c, "mamá y yo · 1975", -330, 440, "Courier Prime", 34, hx("#2a2a5a"), ancla=0)
    return dict(niebla=0.1, gradacion=0.4, niebla_color=(0.5, 0.42, 0.3))


# ----------------------------------------------------------------- CCTV
def cctv(c, t, T, d, contenido, zoom=1.0, foco=(0.5, 0.5), sello="CAM 04", hora=None):
    """Imagen de cámara de seguridad: dibuja `contenido(c)` en blanco y negro con ruido y sello de hora."""
    fondo(c, hx("#000000"))
    c.save()
    with tf(c, W * foco[0], H * foco[1], s=zoom):
        c.translate(-W * foco[0], -H * foco[1])
        contenido(c)
    c.restore()
    # blanco y negro aproximado: capa de saturación
    c.save()
    c.set_operator(cairo.OPERATOR_HSL_SATURATION)
    src(c, (0.5, 0.5, 0.5, 1))
    c.paint()
    c.restore()
    src(c, (0.1, 0.25, 0.15, 0.12))
    c.paint()
    # líneas de escaneo
    src(c, (0, 0, 0, 0.18))
    for y in range(0, H, 6):
        c.rectangle(0, y, W, 2)
    c.fill()
    h = hora or f"03:17:{int(4 + t) % 60:02d}"
    texto(c, f"{sello}   14-11-2026", 60, 120, MAQ, 44, hx("#f2f2f2", 0.9), ancla=0, negrita=True)
    texto(c, h, 60, 175, MAQ, 44, hx("#f2f2f2", 0.9), ancla=0, negrita=True)
    if math.sin(T * 4) > 0:
        c.arc(W - 90, 105, 16, 0, 2 * math.pi)
        src(c, hx("#ff2a1f"))
        c.fill()
    texto(c, "REC", W - 120, 120, MAQ, 40, hx("#f2f2f2", 0.9), ancla=1, negrita=True)
    if zoom > 1.05:
        texto(c, f"ZOOM x{zoom:.1f}", 60, H - 120, MAQ, 40, hx("#f2f2f2", 0.8), ancla=0, negrita=True)
    return dict(grano=0.12, gradacion=0.0, glitch=0.15 if hash1(math.floor(T * 5)) > 0.85 else 0.0, niebla=0.0,
                vineta=0.6)


def cristal_escrito(c, t, T, d, progreso=1.0):
    """Cristal empañado del vagón con el mensaje escrito con el dedo."""
    fondo(c, hx("#06090a"))
    # luces del túnel tras el cristal
    for i in range(4):
        x = (i * 400 - T * 300) % (W + 400) - 200
        resplandor(c, x, H * 0.4, 300, hx("#ffd9a0"), 0.4)
    # vaho
    c.rectangle(80, 300, W - 160, 1300)
    src(c, hx("#b7c4c8", 0.55))
    c.fill()
    for i in range(160):
        x = 80 + hash1(i * 1.1) * (W - 160)
        y = 300 + hash1(i * 2.3) * 1300
        c.arc(x, y, 2 + 5 * hash1(i * 3.3), 0, 2 * math.pi)
        src(c, hx("#e8f0f2", 0.35))
        c.fill()
    lineas = ["UNO MÁS", "PARA EL", "PRÓXIMO", "VIAJE"]
    total = sum(len(l) for l in lineas)
    n = int(progreso * total + 0.5)
    for k, l in enumerate(lineas):
        vis = l[:max(0, min(len(l), n))]
        n -= len(l)
        if vis:
            y = 640 + k * 260
            # trazo "borrado" en el vaho: oscuro y con gotas
            texto(c, vis, W / 2 - 0 * len(vis), y, TITULO, 230, hx("#0a1012", 0.92), ancla=0.5 * len(vis) / len(l)
                  if False else 0.5, espaciado=6)
            for g in range(len(vis)):
                gx = W / 2 - len(l) * 60 + g * 120 + 40
                gl = 40 + 120 * hash1(k * 31 + g) * cl(progreso * 2)
                c.rectangle(gx, y + 5, 6, gl)
                src(c, hx("#0a1012", 0.7))
                c.fill()
    rr(c, 80, 300, W - 160, 1300, 40)
    c.set_line_width(40)
    src(c, hx("#5a6468"))
    c.stroke()
    return dict(niebla=0.2, grano=0.06)


def fin(c, t, T, d):
    fondo(c, hx("#000000"))
    a = pr(t, 0.3, 1.2)
    texto(c, "FIN", W / 2, H * 0.48, TITULO, 260, hx("#e8eef0", a), espaciado=30)
    c.rectangle(W / 2 - 160 * a, H * 0.48 + 50, 320 * a, 4)
    src(c, hx("#b8323a", a))
    c.fill()
    b = pr(t, 2.0, 1.5)
    texto(c, "¿Habrías subido?", W / 2, H * 0.6, SANS, 52, hx("#9aa6aa", b))
    return dict(niebla=0.3, grano=0.05)
