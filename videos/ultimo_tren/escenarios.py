"""Escenarios: mini motor 3D (polígonos con niebla por profundidad) y decorados.

Mundo en metros: x lateral (+ derecha), y altura, z profundidad (+ hacia delante).
"""
import math

import cairo

from motor import (FCAM, H, KH, MAQ, SANS, TITULO, W, cl, fbm1, hash1, hx, lerp, lerpc, lgrad, mul, parpadeo, rgrad,
                   resplandor, rr, src, texto, tf)
from personajes import figura, figura_perfil, silueta


class Cam:
    def __init__(self, x=0.0, y=1.6, z=0.0, yaw=0.0, pitch=0.0, f=900.0, roll=0.0,
                 niebla=(0.05, 0.07, 0.08), densidad=0.045):
        self.x, self.y, self.z, self.yaw, self.pitch, self.f, self.roll = x, y, z, yaw, pitch, f * FCAM, roll
        self.niebla, self.densidad = niebla, densidad
        self.cy, self.sy = math.cos(yaw), math.sin(yaw)
        self.cp, self.sp = math.cos(pitch), math.sin(pitch)

    def vista(self, p):
        x, y, z = p[0] - self.x, p[1] - self.y, p[2] - self.z
        x, z = x * self.cy - z * self.sy, x * self.sy + z * self.cy
        y, z = y * self.cp - z * self.sp, y * self.sp + z * self.cp
        return x, y, z

    def pantalla(self, v):
        return W / 2 + self.f * v[0] / v[2], H / 2 - self.f * v[1] / v[2]

    def proy(self, p):
        v = self.vista(p)
        if v[2] < 0.05:
            return None
        return self.pantalla(v) + (v[2],)

    def escala(self, p):
        v = self.vista(p)
        return self.f / v[2] if v[2] > 0.05 else 0

    def fog(self, col, z):
        e = math.exp(-max(0.0, z) * self.densidad)
        return lerpc(self.niebla + (col[3] if len(col) == 4 else 1.0,), col if len(col) == 4 else col + (1,), e)


CERCA = 0.12


def _recorta(vs):
    out = []
    n = len(vs)
    for i in range(n):
        a, b = vs[i], vs[(i + 1) % n]
        ia, ib = a[2] >= CERCA, b[2] >= CERCA
        if ia:
            out.append(a)
        if ia != ib:
            t = (CERCA - a[2]) / (b[2] - a[2])
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, CERCA))
    return out


def poli(c, cam, pts, col, sombra=0.0, borde=None, ancho=1.0, emisivo=False):
    """Rellena un polígono 3D. Devuelve la z media (o None si no se ve)."""
    vs = _recorta([cam.vista(p) for p in pts])
    if len(vs) < 3:
        return None
    zm = sum(v[2] for v in vs) / len(vs)
    pp = [cam.pantalla(v) for v in vs]
    c.move_to(*pp[0])
    for p in pp[1:]:
        c.line_to(*p)
    c.close_path()
    colr = col if emisivo else cam.fog(col, zm)
    if sombra:
        colr = mul(colr, 1 - sombra)
    src(c, colr)
    if borde:
        c.fill_preserve()
        src(c, cam.fog(borde, zm))
        c.set_line_width(ancho)
        c.stroke()
    else:
        c.fill()
    return zm


def linea3(c, cam, a, b, col, ancho_m):
    va, vb = cam.vista(a), cam.vista(b)
    if va[2] < CERCA and vb[2] < CERCA:
        return
    if va[2] < CERCA:
        t = (CERCA - va[2]) / (vb[2] - va[2])
        va = tuple(va[i] + (vb[i] - va[i]) * t for i in range(3))
    if vb[2] < CERCA:
        t = (CERCA - vb[2]) / (va[2] - vb[2])
        vb = tuple(vb[i] + (va[i] - vb[i]) * t for i in range(3))
    zm = (va[2] + vb[2]) / 2
    c.move_to(*cam.pantalla(va))
    c.line_to(*cam.pantalla(vb))
    c.set_line_width(max(0.6, cam.f * ancho_m / zm))
    src(c, cam.fog(col, zm))
    c.stroke()


def caja(c, cam, x0, x1, y0, y1, z0, z1, col, caras="todas"):
    """Caja alineada a los ejes; dibuja las caras visibles desde la cámara."""
    cx, cy, cz = cam.x, cam.y, cam.z
    fs = []
    if cz < z0:
        fs.append(([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], 0.0))
    if cz > z1:
        fs.append(([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], 0.1))
    if cx < x0:
        fs.append(([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], 0.25))
    if cx > x1:
        fs.append(([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], 0.25))
    if cy > y1:
        fs.append(([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], -0.1))
    if cy < y0:
        fs.append(([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], 0.35))
    for pts, sh in fs:
        poli(c, cam, pts, mul(col, 1 - sh) if sh >= 0 else lerpc(col, (1, 1, 1, col[3]), -sh))


def brillo3(c, cam, p, radio_m, col, fuerza=1.0):
    pr_ = cam.proy(p)
    if not pr_:
        return
    r = cam.f * radio_m / pr_[2]
    if r < 0.5:
        return
    resplandor(c, pr_[0], pr_[1], r, col, fuerza * math.exp(-pr_[2] * cam.densidad * 0.6))


def tubo3(c, cam, x, y, z0, z1, col, luz=1.0, eje="z", halo=1.9, fuerza=0.9, charco=0.0, suelo_y=0.0):
    """Fluorescente: barra emisiva + halo."""
    if eje == "z":
        a, b = (x, y, z0), (x, y, z1)
    else:
        a, b = (z0, y, x), (z1, y, x)
    k = cl(luz)
    linea3(c, cam, a, b, lerpc(hx("#1a2224"), col, k), 0.09)
    if k > 0.05:
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 0.05, (a[2] + b[2]) / 2)
        brillo3(c, cam, m, halo, col, fuerza * k)
        if charco > 0:
            pr_ = cam.proy((m[0], suelo_y, m[2]))
            if pr_:
                sc = cam.f / pr_[2]
                ry = max(0.15, abs(cam.y - suelo_y)) / max(1.0, pr_[2]) * 1.0
                c.save()
                c.translate(pr_[0], pr_[1])
                c.scale(sc * 1.6, sc * 1.6 * cl(ry, 0.05, 0.6))
                c.arc(0, 0, 1, 0, 2 * math.pi)
                c.restore()
                c.set_source(rgrad(pr_[0], pr_[1], 0, sc * 1.6, [(0, mul(col, 1, 0.22 * k * charco)),
                                                                 (1, mul(col, 1, 0))]))
                c.fill()


def billboard(c, cam, p, alto_m, dibujar):
    """Dibuja un elemento 2D (personaje) en el punto 3D p (pies) con su altura en metros."""
    pr_ = cam.proy(p)
    if not pr_:
        return None
    px = cam.f * alto_m / pr_[2]
    if px < 2:
        return None
    zf = pr_[2]
    c.push_group()
    dibujar(pr_[0], pr_[1], px)
    c.pop_group_to_source()
    c.paint()
    # niebla sobre el personaje: velo con el color de la niebla
    e = 1 - math.exp(-zf * cam.densidad)
    if e > 0.02:
        c.push_group()
        dibujar(pr_[0], pr_[1], px)
        patron = c.pop_group()
        src(c, cam.niebla + (e,))
        c.mask(patron)
    return pr_


def cielo(c, col):
    c.rectangle(0, 0, W, H)
    src(c, col)
    c.fill()


# =================================================================== ANDÉN
AZULEJO = hx("#a9b8ad")
AZULEJO_OSC = hx("#6f7f78")
SUELO_AND = hx("#4a4f52")
AMARILLO = hx("#b9a23c")
FOSO = hx("#121618")
CARRIL = hx("#7c878d")
TECHO = hx("#1c2326")
LUZ_FRIA = hx("#d8f0ff")


def anden(c, cam, T, nombre="ALAMEDA", luces=1.0, semilla=0.0, viejo=0.0, rojo=0.0, tren=None, gente=(),
          largo=70.0, maquina=True, reloj=True, panel=True, oscuro=False, farola=None, cartel_farola=None,
          banco=True, mañana=0.0):
    """Andén de metro en perspectiva. tren: dict(z=frente, puertas=0..1, luz=interior)."""
    col_luz = lerpc(LUZ_FRIA, hx("#ff4a3a"), rojo)
    if mañana:
        col_luz = lerpc(col_luz, hx("#fff4e0"), mañana)
    az = lerpc(AZULEJO, hx("#7d8a72"), viejo)
    if oscuro:
        az = mul(az, 0.25)
    cielo(c, cam.niebla + (1,))
    paso = 2.5
    # fondo: boca del túnel y pared final
    zf = largo
    poli(c, cam, [(-4, 0, zf), (0, 0, zf), (0, 4.6, zf), (-4, 4.6, zf)], mul(az, 0.55))
    poli(c, cam, [(0, -1.2, zf), (4.3, -1.2, zf), (4.3, 4.6, zf), (0, 4.6, zf)], mul(az, 0.5))
    arco = [(0.2 + 3.9 * (0.5 - 0.5 * math.cos(a)), 2.4 + 1.5 * math.sin(a), zf - 0.01)
            for a in [k * math.pi / 12 for k in range(13)]]
    poli(c, cam, [(4.1, -1.2, zf - 0.01), (4.1, 2.4, zf - 0.01)] + arco[::-1][1:] + [(0.2, -1.2, zf - 0.01)],
         hx("#020303"), emisivo=True)
    z = zf
    while z > cam.z - paso:
        z0, z1 = max(z - paso, cam.z - 1), z
        i = int(z0 / paso)
        # techo
        poli(c, cam, [(-4, 4.6, z0), (4.3, 4.6, z0), (4.3, 4.6, z1), (-4, 4.6, z1)], TECHO)
        # pared del fondo (al otro lado de las vías)
        poli(c, cam, [(4.3, -1.2, z0), (4.3, 4.6, z0), (4.3, 4.6, z1), (4.3, -1.2, z1)], az)
        poli(c, cam, [(4.29, -1.2, z0), (4.29, 0.6, z0), (4.29, 0.6, z1), (4.29, -1.2, z1)], mul(az, 0.55))
        poli(c, cam, [(4.28, 3.2, z0), (4.28, 3.45, z0), (4.28, 3.45, z1), (4.28, 3.2, z1)],
             lerpc(hx("#2c5f6e"), hx("#5a3a2a"), viejo))
        # pared izquierda
        poli(c, cam, [(-4, 0, z0), (-4, 4.6, z0), (-4, 4.6, z1), (-4, 0, z1)], mul(az, 0.85))
        poli(c, cam, [(-3.99, 3.2, z0), (-3.99, 3.45, z0), (-3.99, 3.45, z1), (-3.99, 3.2, z1)],
             lerpc(hx("#2c5f6e"), hx("#5a3a2a"), viejo))
        # foso y vías
        poli(c, cam, [(0, -1.2, z0), (4.3, -1.2, z0), (4.3, -1.2, z1), (0, -1.2, z1)], FOSO)
        poli(c, cam, [(0, -1.2, z0), (0, 0, z0), (0, 0, z1), (0, -1.2, z1)], hx("#23292b"))
        for k in range(int(z0), int(z1) + 1, 1):
            if z0 <= k < z1:
                poli(c, cam, [(0.6, -1.19, k), (3.7, -1.19, k), (3.7, -1.19, k + 0.25), (0.6, -1.19, k + 0.25)],
                     hx("#2a2420"))
        # suelo del andén (baldosas alternas)
        poli(c, cam, [(-4, 0, z0), (0, 0, z0), (0, 0, z1), (-4, 0, z1)],
             SUELO_AND if i % 2 else mul(SUELO_AND, 0.93))
        poli(c, cam, [(-0.65, 0.002, z0), (-0.4, 0.002, z0), (-0.4, 0.002, z1), (-0.65, 0.002, z1)], AMARILLO)
        poli(c, cam, [(-0.2, 0.003, z0), (0, 0.003, z0), (0, 0.003, z1), (-0.2, 0.003, z1)], hx("#8b9195"))
        z -= paso
    for xr in (1.2, 1.35, 2.85, 3.0):
        linea3(c, cam, (xr, -1.08, max(cam.z, 0)), (xr, -1.08, zf), CARRIL, 0.06)
    # carteles en la pared del fondo
    for zc in range(6, int(zf), 14):
        cartel_pared(c, cam, 4.27, zc, nombre, viejo, T, semilla + zc)
    # anuncios desvaídos
    for zc in range(13, int(zf), 14):
        cara_anuncio(c, cam, 4.27, zc, viejo, semilla + zc)
    # luces de techo
    for k, zl in enumerate(range(2, int(zf), 5)):
        for xl in (-2.0, 2.2):
            lz = luces * parpadeo(T, semilla + k * 3.7 + xl, intensidad=0.8 + 0.6 * (k % 3 == 1)) if not oscuro else 0
            tubo3(c, cam, xl, 4.5, zl, zl + 1.4, col_luz, luz=lz, charco=1.0 if xl < 0 else 0.0)
    # mobiliario
    if banco:
        for zb in (5.0, 17.0):
            caja(c, cam, -3.9, -3.3, 0, 0.45, zb, zb + 2.2, hx("#3d4d55"))
            caja(c, cam, -3.98, -3.85, 0.45, 1.05, zb, zb + 2.2, hx("#34434a"))
    if maquina:
        caja(c, cam, -3.95, -3.05, 0, 1.95, 9.0, 10.0, hx("#1f2a30"))
        pp = [(-3.04, 0.6, 9.1), (-3.04, 0.6, 9.9), (-3.04, 1.85, 9.9), (-3.04, 1.85, 9.1)]
        k = parpadeo(T * 0.7, semilla + 99, 0.5) * luces if not oscuro else 0.0
        poli(c, cam, pp, lerpc(hx("#0a1a20"), hx("#7fd8f0"), k * 0.85), emisivo=True)
        for r_ in range(4):
            yy = 0.8 + r_ * 0.27
            for cc in range(3):
                zz = 9.2 + cc * 0.24
                poli(c, cam, [(-3.03, yy, zz), (-3.03, yy, zz + 0.15), (-3.03, yy + 0.16, zz + 0.15),
                              (-3.03, yy + 0.16, zz)],
                     [hx("#c0392b"), hx("#e1b12c"), hx("#2e86de"), hx("#10ac84")][(r_ + cc) % 4], emisivo=False)
        brillo3(c, cam, (-3.0, 1.2, 9.5), 1.6, hx("#7fd8f0"), 0.7 * k)
    if reloj:
        p = cam.proy((-1.2, 3.75, 7.0))
        if p:
            reloj_estacion(c, p[0], p[1], cam.f * 0.32 / p[2], 3, 17, T, ilum=0.9 if not oscuro else 0.2)
    if panel:
        p = cam.proy((-1.2, 3.75, 12.0))
        if p:
            s = cam.f / p[2]
            with tf(c, p[0], p[1], s=s / 400):
                rr(c, -400, -90, 800, 180, 10)
                src(c, hx("#0b0d0e"))
                c.fill()
                for fila in range(3):
                    texto(c, ["L2  CENTRO      --:--", "L2  CENTRO      --:--", "??  ---------   03:17"][fila],
                          -360, -40 + fila * 52, MAQ, 44, hx("#ffb347", 0.85 if fila < 2 else
                                                              0.5 + 0.5 * (hash1(math.floor(T * 6)) > 0.3)),
                          ancla=0, negrita=True)
    if farola is not None:
        fz, fx_ = farola
        caja(c, cam, fx_ - 0.07, fx_ + 0.07, 0, 3.6, fz - 0.07, fz + 0.07, hx("#15191b"))
        caja(c, cam, fx_ - 0.07, fx_ + 0.55, 3.55, 3.65, fz - 0.07, fz + 0.07, hx("#15191b"))
        lk = parpadeo(T, semilla + 7, 0.5)
        brillo3(c, cam, (fx_ + 0.5, 3.45, fz), 2.8, hx("#ffd9a0"), 1.2 * lk)
        # charco de luz en el suelo
        pr_ = cam.proy((fx_ + 0.5, 0.0, fz))
        if pr_:
            s = cam.f / pr_[2]
            c.save()
            c.translate(pr_[0], pr_[1])
            c.scale(s * 2.2, s * 2.2 * 0.35 * (cam.y / 1.6))
            c.arc(0, 0, 1, 0, 2 * math.pi)
            c.restore()
            c.set_source(rgrad(pr_[0], pr_[1], 0, s * 2.2, [(0, hx("#ffd9a0", 0.45 * lk)), (1, hx("#ffd9a0", 0))]))
            c.fill()
        # cono
        top = cam.proy((fx_ + 0.5, 3.45, fz))
        bot = cam.proy((fx_ + 0.5, 0.0, fz))
        if top and bot:
            s = cam.f / bot[2]
            c.save()
            c.set_operator(cairo.OPERATOR_ADD)
            c.move_to(top[0] - 0.1 * s, top[1])
            c.line_to(top[0] + 0.1 * s, top[1])
            c.line_to(bot[0] + 1.9 * s, bot[1])
            c.line_to(bot[0] - 1.9 * s, bot[1])
            c.close_path()
            c.set_source(lgrad(0, top[1], 0, bot[1], [(0, hx("#ffd9a0", 0.28 * lk)), (1, hx("#ffd9a0", 0.03 * lk))]))
            c.fill()
            c.restore()
        if cartel_farola:
            cartel_farola(c, cam, fx_, fz, T)
    if tren:
        tren3d(c, cam, T, **tren)
    for g in sorted(gente, key=lambda g: -g["z"]):
        persona3d(c, cam, g, T)


def persona3d(c, cam, g, T):
    tipo = g.get("tipo", "figura")
    alto = g.get("alto", 1.75)

    def dib(x, y, px):
        if tipo == "silueta":
            silueta(c, x, y, px, T=T, semilla=g.get("semilla", 0), ojos=g.get("ojos", 0.0), ladeo=g.get("ladeo", 0))
        elif tipo == "perfil":
            figura_perfil(c, x, y, px, g["spec"], T=T, **g.get("kw", {}))
        else:
            figura(c, x, y, px, g["spec"], T=T, **g.get("kw", {}))
    billboard(c, cam, (g["x"], g.get("y", 0.0), g["z"]), alto, dib)


def cartel_pared(c, cam, x, z, nombre, viejo, T, semilla):
    pts = [(x, 1.7, z), (x, 1.7, z + 3.2), (x, 2.5, z + 3.2), (x, 2.5, z)]
    poli(c, cam, pts, lerpc(hx("#1e4a7a"), hx("#3b3a33"), viejo), borde=hx("#e8e8e8"), ancho=2)
    p0, p1 = cam.proy((x, 2.1, z)), cam.proy((x, 2.1, z + 3.2))
    if p0 and p1 and p1[0] < p0[0]:
        p0, p1 = p1, p0
    if p0 and p1:
        # texto en perspectiva aproximada: escala por la distancia media
        s0, s1 = cam.f / p0[2], cam.f / p1[2]
        cx_, cy_ = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        largo = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        with tf(c, cx_, cy_, r=ang):
            c.save()
            c.scale(largo / 600, (s0 + s1) / 2 * 0.5 / 70)
            texto(c, nombre, 0, 24, TITULO, 76, cam.fog(hx("#f2f2f2", 1.0 - 0.3 * viejo), (p0[2] + p1[2]) / 2),
                  espaciado=8)
            c.restore()


def cara_anuncio(c, cam, x, z, viejo, semilla):
    pts = [(x, 1.0, z), (x, 1.0, z + 2.0), (x, 2.9, z + 2.0), (x, 2.9, z)]
    base = [hx("#5e6e78"), hx("#6c5a52"), hx("#4f6458")][int(hash1(semilla) * 3)]
    poli(c, cam, pts, mul(base, 0.8 - 0.3 * viejo), borde=hx("#222a2e"), ancho=3)


def reloj_estacion(c, x, y, r, hh, mm, T, ilum=1.0, segundos=None):
    with tf(c, x, y, s=r):
        c.move_to(0, -1.15)
        c.line_to(0, -2.2)
        c.set_line_width(0.06)
        src(c, hx("#151a1c"))
        c.stroke()
        c.arc(0, 0, 1.08, 0, 2 * math.pi)
        src(c, hx("#151a1c"))
        c.fill()
        c.arc(0, 0, 1.0, 0, 2 * math.pi)
        src(c, mul(hx("#e8ece6"), 0.35 + 0.65 * ilum))
        c.fill()
        for k in range(60):
            a = k * math.pi / 30
            l = 0.18 if k % 5 == 0 else 0.07
            c.move_to(math.sin(a) * 0.9, -math.cos(a) * 0.9)
            c.line_to(math.sin(a) * (0.9 - l), -math.cos(a) * (0.9 - l))
            c.set_line_width(0.07 if k % 5 == 0 else 0.025)
            src(c, hx("#1a1a1a"))
            c.stroke()
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        for ang, l, w in (((hh % 12 + mm / 60) / 12 * 2 * math.pi, 0.5, 0.1), (mm / 60 * 2 * math.pi, 0.75, 0.07)):
            c.move_to(-math.sin(ang) * 0.12, math.cos(ang) * 0.12)
            c.line_to(math.sin(ang) * l, -math.cos(ang) * l)
            c.set_line_width(w)
            src(c, hx("#111111"))
            c.stroke()
        sg = (T % 60) if segundos is None else segundos
        a = math.floor(sg) / 60 * 2 * math.pi
        c.move_to(-math.sin(a) * 0.2, math.cos(a) * 0.2)
        c.line_to(math.sin(a) * 0.82, -math.cos(a) * 0.82)
        c.set_line_width(0.03)
        src(c, hx("#b3261e"))
        c.stroke()
        c.arc(0, 0, 0.06, 0, 2 * math.pi)
        src(c, hx("#b3261e"))
        c.fill()
        c.arc(0, 0, 1.0, 0, 2 * math.pi)
        c.set_source(rgrad(-0.3, -0.4, 0.1, 1.0, [(0, hx("#ffffff", 0.18)), (1, hx("#000000", 0.25))]))
        c.fill()


# =================================================================== TREN (exterior)
CHAPA = hx("#8e979c")


def tren3d(c, cam, T, z=0.0, puertas=0.0, luz=1.0, largo=40.0, faro=1.0, x0=0.3, x1=4.0, ventanas_col=None,
           cabina_vacia=True):
    """Tren sobre las vías; frente en z, cola en z+largo. Cara lateral en x=x0 (hacia el andén)."""
    y0, y1 = -1.0, 3.0
    inter = ventanas_col or lerpc(hx("#1a2225"), hx("#e6f4f8"), luz)
    # cara frontal (visible si la cámara está delante)
    if cam.z < z:
        poli(c, cam, [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], mul(CHAPA, 0.75))
        poli(c, cam, [(x0 + 0.4, 1.0, z - 0.01), (x1 - 0.4, 1.0, z - 0.01), (x1 - 0.5, 2.4, z - 0.01),
                      (x0 + 0.5, 2.4, z - 0.01)], hx("#05080a"))
        poli(c, cam, [(x0, 0.2, z - 0.01), (x1, 0.2, z - 0.01), (x1, 0.45, z - 0.01), (x0, 0.45, z - 0.01)],
             hx("#1f5560"))
        for xf in (x0 + 0.6, x1 - 0.6):
            p = cam.proy((xf, -0.2, z - 0.02))
            if p:
                s = cam.f / p[2]
                c.arc(p[0], p[1], 0.17 * s, 0, 2 * math.pi)
                src(c, lerpc(hx("#ff2a1f"), hx("#fffbe8"), faro))
                c.fill()
                if faro > 0.05:
                    resplandor(c, p[0], p[1], 2.2 * s * faro + 1, hx("#fff6d8"), 1.3 * faro)
                else:
                    resplandor(c, p[0], p[1], 0.9 * s + 1, hx("#ff2a1f"), 1.0)
        p = cam.proy(((x0 + x1) / 2, 2.75, z - 0.02))
        if p:
            s = cam.f / p[2]
            with tf(c, p[0], p[1], s=s / 100):
                rr(c, -110, -22, 220, 44, 6)
                src(c, hx("#0a0a0a"))
                c.fill()
                texto(c, "SIN SERVICIO" if hash1(math.floor(T * 2)) > 0.5 else "· · · · ·", 0, 13, MAQ, 34,
                      hx("#ff6a3a", 0.9), negrita=True)
    # cara lateral en tramos
    paso = 2.0
    zz = z + largo
    while zz > z:
        a, b = max(z, zz - paso), zz
        if b > cam.z - 1:
            poli(c, cam, [(x0, y0, a), (x0, y0, b), (x0, y1, b), (x0, y1, a)], CHAPA)
            poli(c, cam, [(x0 - 0.01, 0.15, a), (x0 - 0.01, 0.15, b), (x0 - 0.01, 0.35, b), (x0 - 0.01, 0.35, a)],
                 hx("#1f5560"))
            poli(c, cam, [(x0 - 0.01, y1 - 0.25, a), (x0 - 0.01, y1 - 0.25, b), (x0 - 0.01, y1, b),
                          (x0 - 0.01, y1, a)], mul(CHAPA, 0.8))
        zz -= paso
    # ventanas y puertas (de atrás hacia delante)
    for k in range(int(largo // 6.5), -1, -1):
        zp = z + 2.2 + k * 6.5
        if zp + 1.4 > z + largo:
            continue
        # ventanas entre puertas
        zv = zp + 1.9
        if zv + 3.6 < z + largo:
            pts = [(x0 - 0.02, 1.05, zv), (x0 - 0.02, 1.05, zv + 3.6), (x0 - 0.02, 2.35, zv + 3.6),
                   (x0 - 0.02, 2.35, zv)]
            poli(c, cam, pts, inter, emisivo=luz > 0.3, borde=hx("#2a3236"), ancho=3)
        # puerta doble
        ap = puertas * 0.62
        hueco = [(x0 - 0.015, -0.95, zp - ap), (x0 - 0.015, -0.95, zp + 1.4 + ap),
                 (x0 - 0.015, 2.5, zp + 1.4 + ap), (x0 - 0.015, 2.5, zp - ap)]
        if puertas > 0.01:
            poli(c, cam, [(x0 - 0.015, -0.95, zp), (x0 - 0.015, -0.95, zp + 1.4), (x0 - 0.015, 2.5, zp + 1.4),
                          (x0 - 0.015, 2.5, zp)], lerpc(hx("#0d1214"), hx("#f2fbff"), luz), emisivo=True)
        for lado, (za, zb) in enumerate(((zp - ap, zp + 0.7 - ap), (zp + 0.7 + ap, zp + 1.4 + ap))):
            poli(c, cam, [(x0 - 0.03, -0.95, za), (x0 - 0.03, -0.95, zb), (x0 - 0.03, 2.5, zb),
                          (x0 - 0.03, 2.5, za)], mul(CHAPA, 0.88), borde=hx("#3a4246"), ancho=2)
            poli(c, cam, [(x0 - 0.04, 1.1, za + 0.12), (x0 - 0.04, 1.1, zb - 0.12), (x0 - 0.04, 2.25, zb - 0.12),
                          (x0 - 0.04, 2.25, za + 0.12)], inter, emisivo=luz > 0.3)
        if puertas > 0.05 and luz > 0.2:
            brillo3(c, cam, (x0 - 0.3, 0.8, zp + 0.7), 2.5, hx("#e6f8ff"), 0.6 * luz * puertas)
        _ = hueco


# =================================================================== VAGÓN (interior)
PARED_V = hx("#9aa7aa")
ASIENTO = hx("#24404f")
SUELO_V = hx("#3a4044")


def vagon(c, cam, T, luces=1.0, semilla=0.0, velocidad=1.0, gente=(), puertas=0.0, rojo=0.0, fuera="tunel",
          largo=18.0, luz_col=None, puertas_z=(4.0, 12.0), fondo_puerta=True, apagado=False):
    """Interior del vagón mirando hacia +z. Bancos longitudinales a ambos lados."""
    col_luz = luz_col or lerpc(hx("#e8f6ff"), hx("#ff5a4a"), rojo)
    kk = 0.0 if apagado else luces
    pared = lerpc(mul(PARED_V, 0.15), PARED_V, cl(0.25 + 0.75 * kk))
    asiento = lerpc(mul(ASIENTO, 0.2), ASIENTO, cl(0.25 + 0.75 * kk))
    suelo = lerpc(mul(SUELO_V, 0.3), SUELO_V, cl(0.3 + 0.7 * kk))
    techo = lerpc(mul(PARED_V, 0.08), mul(PARED_V, 0.5), cl(0.2 + 0.8 * kk))
    cielo(c, hx("#020304"))
    X, Y = 1.45, 2.25
    zf = largo
    # pared del fondo con puerta al siguiente vagón
    poli(c, cam, [(-X, 0, zf), (X, 0, zf), (X, Y, zf), (-X, Y, zf)], mul(pared, 0.9))
    if fondo_puerta:
        poli(c, cam, [(-0.45, 0, zf - 0.01), (0.45, 0, zf - 0.01), (0.45, 2.0, zf - 0.01), (-0.45, 2.0, zf - 0.01)],
             mul(pared, 0.7), borde=hx("#59646a"), ancho=3)
        poli(c, cam, [(-0.3, 1.1, zf - 0.02), (0.3, 1.1, zf - 0.02), (0.3, 1.85, zf - 0.02), (-0.3, 1.85, zf - 0.02)],
             hx("#030506"), emisivo=True)
    paso = 1.5
    z = zf
    while z > cam.z - paso:
        a, b = max(z - paso, cam.z - 0.5), z
        i = int(a / paso)
        poli(c, cam, [(-X, 0, a), (X, 0, a), (X, 0, b), (-X, 0, b)], suelo if i % 2 else mul(suelo, 0.95))
        poli(c, cam, [(-X, Y, a), (X, Y, a), (X, Y, b), (-X, Y, b)], techo)
        for lado in (-1, 1):
            xw = lado * X
            en_puerta = any(pz - 0.1 <= (a + b) / 2 <= pz + 1.5 for pz in puertas_z)
            # pared baja, ventana, pared alta
            poli(c, cam, [(xw, 0, a), (xw, 0, b), (xw, 0.95, b), (xw, 0.95, a)], mul(pared, 0.82))
            poli(c, cam, [(xw, 1.9, a), (xw, 1.9, b), (xw, Y, b), (xw, Y, a)], mul(pared, 0.9))
            if not en_puerta:
                ventana3d(c, cam, xw, a, b, T, velocidad, fuera, semilla, kk)
            else:
                poli(c, cam, [(xw, 0.95, a), (xw, 0.95, b), (xw, 1.9, b), (xw, 1.9, a)], mul(pared, 0.82))
        z -= paso
    # puertas
    for pz in puertas_z:
        for lado in (-1, 1):
            xw = lado * (X - 0.01)
            ap = puertas * 0.6
            if puertas > 0.01:
                poli(c, cam, [(xw, 0, pz), (xw, 0, pz + 1.4), (xw, 2.0, pz + 1.4), (xw, 2.0, pz)],
                     hx("#020303"), emisivo=True)
            for za, zb in ((pz - ap, pz + 0.7 - ap), (pz + 0.7 + ap, pz + 1.4 + ap)):
                poli(c, cam, [(xw, 0, za), (xw, 0, zb), (xw, 2.0, zb), (xw, 2.0, za)], mul(pared, 0.75),
                     borde=hx("#5d686e"), ancho=2)
                poli(c, cam, [(xw * 0.999, 0.9, za + 0.12), (xw * 0.999, 0.9, zb - 0.12), (xw * 0.999, 1.85, zb - 0.12),
                              (xw * 0.999, 1.85, za + 0.12)], hx("#06090a"), emisivo=True)
            # piloto de puerta
            p = cam.proy((xw, 2.08, pz + 0.7))
            if p:
                on = puertas > 0 and math.sin(T * 12) > 0
                c.arc(p[0], p[1], max(1.5, cam.f * 0.035 / p[2]), 0, 2 * math.pi)
                src(c, hx("#ff3b30") if on else hx("#4a1a18"))
                c.fill()
                if on:
                    resplandor(c, p[0], p[1], cam.f * 0.3 / p[2], hx("#ff3b30"), 0.8)
            # barras
            linea3(c, cam, (lado * 0.75, 0, pz - 0.25), (lado * 0.75, Y, pz - 0.25), hx("#b9c2c6"), 0.035)
            linea3(c, cam, (lado * 0.75, 0, pz + 1.65), (lado * 0.75, Y, pz + 1.65), hx("#b9c2c6"), 0.035)
    # bancos (de atrás hacia delante)
    tramos = []
    zs = [0.0] + [v for pz in puertas_z for v in (pz - 0.4, pz + 1.8)] + [zf - 0.2]
    for k in range(0, len(zs), 2):
        tramos.append((zs[k], zs[k + 1]))
    for za, zb in sorted(tramos, key=lambda t: -t[0]):
        for lado in (-1, 1):
            xa, xb = (lado * X, lado * 0.98) if lado < 0 else (0.98, X)
            caja(c, cam, min(xa, xb), max(xa, xb), 0.0, 0.46, za, zb, asiento)
            xr = lado * (X - 0.05)
            poli(c, cam, [(xr, 0.46, za), (xr, 0.46, zb), (xr, 0.98, zb), (xr, 0.98, za)], mul(asiento, 0.85))
    # barra horizontal superior
    for lado in (-1, 1):
        linea3(c, cam, (lado * 0.9, 1.95, max(cam.z, 0)), (lado * 0.9, 1.95, zf), hx("#aeb8bc"), 0.03)
    # luces del techo
    for k, zl in enumerate(range(1, int(zf), 3)):
        lz = 0 if apagado else luces * parpadeo(T, semilla + k * 5.1, intensidad=0.9 if k % 3 == 2 else 0.4)
        for xl in (-0.55, 0.55):
            tubo3(c, cam, xl, Y - 0.02, zl, zl + 1.6, col_luz, luz=lz, halo=0.8, fuerza=0.35, charco=0.6)
    for g in sorted(gente, key=lambda g: -g["z"]):
        persona3d(c, cam, g, T)


def ventana3d(c, cam, xw, a, b, T, velocidad, fuera, semilla, luz):
    pts = [(xw, 0.98, a + 0.08), (xw, 0.98, b - 0.08), (xw, 1.87, b - 0.08), (xw, 1.87, a + 0.08)]
    vs = _recorta([cam.vista(p) for p in pts])
    if len(vs) < 3:
        return
    pp = [cam.pantalla(v) for v in vs]
    c.save()
    c.move_to(*pp[0])
    for p in pp[1:]:
        c.line_to(*p)
    c.close_path()
    c.clip_preserve()
    base = {"tunel": hx("#05080a"), "rojo": hx("#1a0505"), "parado": hx("#070a0b"),
            "manana": hx("#8a9aa0")}.get(fuera, hx("#05080a"))
    src(c, base)
    c.fill()
    # luces del túnel que pasan
    if velocidad > 0.01 and fuera in ("tunel", "rojo"):
        xs = [p[0] for p in pp]
        ys = [p[1] for p in pp]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        col = hx("#ff3b2f") if fuera == "rojo" else hx("#ffe6b0")
        fase = (T * velocidad * 1.3 + semilla + a * 0.37) % 1.0
        xx = lerp(x1 + 40, x0 - 40, fase) if xw > 0 else lerp(x0 - 40, x1 + 40, fase)
        c.set_source(lgrad(xx - 60, 0, xx + 60, 0, [(0, mul(col, 1, 0)), (0.5, mul(col, 1, 0.55)), (1, mul(col, 1, 0))]))
        c.rectangle(x0, y0, x1 - x0, y1 - y0)
        c.fill()
    # reflejo del interior
    src(c, (0.8, 0.9, 0.95, 0.06 * luz))
    c.paint()
    c.restore()
    poli(c, cam, pts, (0, 0, 0, 0), borde=hx("#59646a"), ancho=3)
