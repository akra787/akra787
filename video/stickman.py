"""Stickman animado y elementos de interacción (encuestas, preguntas para comentarios).

Se dibuja todo con Pillow sobre el fotograma. Lo usa make_video.py con las claves de escena
`personaje`, `encuesta` y `pregunta`.
"""
import math

from PIL import Image, ImageDraw

BLANCO = (255, 255, 255, 255)
CAFE = (120, 72, 40, 255)
ROJO = (230, 60, 60, 255)


def _ik(sx, sy, tx, ty, a, b, flip):
    """Codo/rodilla para un miembro de dos segmentos (longitudes a, b) que va de S a T."""
    dx, dy = tx - sx, ty - sy
    d = max(1e-6, min(math.hypot(dx, dy), a + b - 1e-3))
    base = math.atan2(dy, dx)
    cos_ang = max(-1, min(1, (a * a + d * d - b * b) / (2 * a * d)))
    ang = base + (math.acos(cos_ang) if flip else -math.acos(cos_ang))
    ex, ey = sx + a * math.cos(ang), sy + a * math.sin(ang)
    # el extremo se queda en T si está a alcance; si no, se estira en la dirección de T
    ux, uy = dx / max(math.hypot(dx, dy), 1e-6), dy / max(math.hypot(dx, dy), 1e-6)
    return (ex, ey), (sx + ux * d, sy + uy * d) if math.hypot(dx, dy) > a + b else (tx, ty)


def taza(d, x, y, s, tachada=False, t=0.0):
    """Taza de café centrada en (x, y) con tamaño s."""
    w, h = s, s * 0.85
    d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], int(s * 0.12), fill=BLANCO)
    d.rectangle([x - w / 2 + s * 0.1, y - h / 2 + s * 0.08, x + w / 2 - s * 0.1, y - h / 2 + s * 0.22], fill=CAFE)
    d.arc([x + w / 2 - s * 0.15, y - h * 0.25, x + w / 2 + s * 0.35, y + h * 0.25], -90, 90, fill=BLANCO,
          width=max(3, int(s * 0.1)))
    if not tachada:  # vapor
        for k in (-1, 0, 1):
            pts = []
            for j in range(12):
                yy = y - h / 2 - s * 0.1 - j * s * 0.05
                xx = x + k * s * 0.25 + math.sin(j * 0.7 + t * 4 + k) * s * 0.06
                pts.append((xx, yy))
            d.line(pts, fill=(255, 255, 255, 140), width=max(2, int(s * 0.05)))
    else:
        r = s * 0.85
        lw = max(5, int(s * 0.12))
        d.ellipse([x - r, y - r, x + r, y + r], outline=ROJO, width=lw)
        d.line([x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7], fill=ROJO, width=lw)


def _rayo(d, x, y, s, color=(255, 214, 0, 255)):
    pts = [(x, y - s), (x - s * 0.45, y + s * 0.1), (x - s * 0.05, y + s * 0.1), (x - s * 0.2, y + s),
           (x + s * 0.45, y - s * 0.15), (x + s * 0.05, y - s * 0.15), (x + s * 0.25, y - s)]
    d.polygon(pts, fill=color)


def _estrella(d, x, y, r, color=(255, 214, 0, 255)):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    d.polygon(pts, fill=color)


def _engranaje(d, x, y, r, ang, color):
    pts = []
    for i in range(32):
        a = ang + i * 2 * math.pi / 32
        rr = r if (i // 2) % 2 == 0 else r * 0.78
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    d.polygon(pts, fill=color)
    d.ellipse([x - r * 0.3, y - r * 0.3, x + r * 0.3, y + r * 0.3], fill=(40, 40, 40, 255))


def _figura(d, cx, base, H, t, pose, color, objeto, grosor=1.0):
    """Dibuja el stickman de pie con los pies en (cx, base) y altura H."""
    lw = max(6, int(H * 0.035 * grosor))
    bob = 0.0
    lean = 0.0
    if pose == "energia":
        bob = abs(math.sin(t * 5)) * H * 0.12
    elif pose in ("saludo", "feliz", "señalar", "beber"):
        bob = abs(math.sin(t * 2.5)) * H * 0.015
    elif pose == "dolor":
        lean = math.sin(t * 1.5) * H * 0.02
    base_y = base - bob
    hip = (cx + lean * 0.3, base_y - H * 0.45)
    neck = (cx + lean, base_y - H * 0.78)
    r = H * 0.1
    head = (neck[0], neck[1] - r * 1.05)
    sh = (neck[0], neck[1] + H * 0.04)
    A = H * 0.16
    L = H * 0.235

    # objetivos de manos (respecto al hombro) y pies (respecto a la cadera), en unidades de H
    lh, rh = (-0.12, 0.3), (0.12, 0.3)
    lf, rf = (-0.11, 0.45), (0.11, 0.45)
    cara = "sonrisa"
    if pose == "saludo":
        rh = (0.24 + 0.05 * math.sin(t * 8), -0.22)
        lh = (-0.14, 0.27)
    elif pose == "beber":
        k = (math.sin(t * 1.6) + 1) / 2
        rh = (0.07 + 0.12 * (1 - k), -0.06 + 0.3 * (1 - k))
        lh = (-0.14, 0.27)
    elif pose == "dolor":
        lh, rh = (-0.1, -0.15), (0.1, -0.15)
        lf, rf = (-0.07, 0.45), (0.07, 0.45)
        cara = "triste"
    elif pose == "pensando":
        rh = (0.03, -0.09)
        lh = (-0.15, 0.2)
        cara = "neutra"
    elif pose == "energia":
        air = abs(math.sin(t * 5))
        lh, rh = (-0.28, -0.22), (0.28, -0.22)
        lf, rf = (-0.11 - 0.09 * air, 0.43), (0.11 + 0.09 * air, 0.43)
        cara = "abierta"
    elif pose == "feliz":
        sw = 0.04 * math.sin(t * 6)
        lh, rh = (-0.24 + sw, -0.26), (0.24 - sw, -0.26)
    elif pose == "señalar":
        rh = (0.24, 0.24 + 0.03 * math.sin(t * 6))
        lh = (-0.14, 0.27)

    def limb(start, rel, a, b, flip):
        tgt = (start[0] + rel[0] * H, start[1] + rel[1] * H)
        e, end = _ik(start[0], start[1], tgt[0], tgt[1], a, b, flip)
        d.line([start, e, end], fill=color, width=lw, joint="curve")
        for p in (e, end):
            d.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=color)
        return end

    limb(hip, lf, L, L, False)
    limb(hip, rf, L, L, True)
    d.line([hip, neck], fill=color, width=lw)
    codos_fuera = pose in ("dolor", "energia", "feliz")
    left_hand = limb(sh, lh, A, A, not codos_fuera)
    right_hand = limb(sh, rh, A, A, codos_fuera)

    # cabeza y cara
    d.ellipse([head[0] - r, head[1] - r, head[0] + r, head[1] + r], outline=color, width=lw)
    ex, ey, er = r * 0.38, head[1] - r * 0.15, max(3, r * 0.12)
    ink = color
    if cara == "dormido":
        for sx in (-1, 1):
            d.line([head[0] + sx * ex - er * 1.5, ey, head[0] + sx * ex + er * 1.5, ey], fill=ink, width=max(3, lw // 2))
    else:
        for sx in (-1, 1):
            d.ellipse([head[0] + sx * ex - er, ey - er, head[0] + sx * ex + er, ey + er], fill=ink)
    mw = r * 0.45
    my = head[1] + r * 0.35
    if cara == "sonrisa":
        d.arc([head[0] - mw, my - mw * 0.7, head[0] + mw, my + mw * 0.5], 20, 160, fill=ink, width=max(3, lw // 2))
    elif cara == "triste":
        d.arc([head[0] - mw, my, head[0] + mw, my + mw], 200, 340, fill=ink, width=max(3, lw // 2))
    elif cara == "abierta":
        d.ellipse([head[0] - mw * 0.5, my - mw * 0.3, head[0] + mw * 0.5, my + mw * 0.5], fill=ink)
    else:
        d.line([head[0] - mw * 0.6, my + mw * 0.1, head[0] + mw * 0.6, my + mw * 0.1], fill=ink, width=max(3, lw // 2))

    # extras según la pose
    if pose == "dolor":
        for k, sx in enumerate((-1, 1)):
            ph = (t * 3 + k) % 1
            x0 = head[0] + sx * r * (1.5 + 0.3 * ph)
            pts = [(x0 + sx * j * r * 0.12, head[1] - r * 0.9 + j * r * 0.28 * (1 if j % 2 else -0.2)) for j in range(5)]
            d.line(pts, fill=(255, 214, 0, int(255 * (1 - ph * 0.5))), width=max(3, lw // 2))
    elif pose == "pensando":
        bx, by = head[0] + r * 2.2, head[1] - r * 2.4
        for k, rr in enumerate((0.15, 0.25)):
            d.ellipse([head[0] + r * (1.0 + k * 0.6) - r * rr, head[1] - r * (1.1 + k * 0.6) - r * rr,
                       head[0] + r * (1.0 + k * 0.6) + r * rr, head[1] - r * (1.1 + k * 0.6) + r * rr], fill=BLANCO)
        d.ellipse([bx - r * 1.3, by - r * 1.0, bx + r * 1.3, by + r * 1.0], fill=BLANCO)
        _engranaje(d, bx - r * 0.45, by + r * 0.05, r * 0.55, t * 1.5, (90, 90, 90, 255))
        _engranaje(d, bx + r * 0.5, by - r * 0.15, r * 0.4, -t * 2.0, (255, 170, 0, 255))
    elif pose == "energia":
        for k, (ox, oy) in enumerate(((-0.4, -0.75), (0.4, -0.7), (-0.42, -0.35), (0.42, -0.3))):
            s = H * 0.06 * (1 + 0.2 * math.sin(t * 6 + k))
            _rayo(d, cx + ox * H, base - H + (oy + 1) * H * 0.9 - bob * 0.5, s)
    elif pose == "feliz":
        for k in range(6):
            a = t * 1.2 + k * math.pi / 3
            rr = H * (0.45 + 0.04 * math.sin(t * 3 + k))
            _estrella(d, head[0] + rr * math.cos(a), head[1] + H * 0.15 + rr * 0.6 * math.sin(a),
                      H * 0.035 * (1 + 0.3 * math.sin(t * 5 + k)))

    if objeto in ("taza", "taza_tachada"):
        s = H * 0.11
        hx, hy = right_hand if pose in ("beber", "saludo") else left_hand
        if pose in ("saludo", "señalar"):
            hx, hy = left_hand
        if objeto == "taza_tachada":  # al lado, no en la mano
            hx, hy, s = cx - H * 0.42, base - H * 0.55, H * 0.15
        taza(d, hx, hy - s * 0.2, s, tachada=(objeto == "taza_tachada"), t=t)


def dormido(img, cx, base, H, t, color):
    """Stickman tumbado en una cama, con Z que suben."""
    d = ImageDraw.Draw(img, "RGBA")
    bw, bh = H * 1.25, H * 0.12
    d.rounded_rectangle([cx - bw / 2, base - bh, cx + bw / 2, base], int(bh * 0.3), fill=(70, 90, 160, 255))
    d.rectangle([cx - bw / 2, base - bh * 2.2, cx - bw / 2 + bh * 0.4, base + bh * 0.6], fill=(150, 110, 70, 255))
    d.rectangle([cx + bw / 2 - bh * 0.4, base - bh * 1.5, cx + bw / 2, base + bh * 0.6], fill=(150, 110, 70, 255))
    d.ellipse([cx - bw / 2 + bh * 0.4, base - bh * 1.9, cx - bw / 2 + bh * 2.6, base - bh * 0.7], fill=(170, 185, 225, 255))
    lw = max(6, int(H * 0.035))
    r = H * 0.1
    breath = math.sin(t * 1.8) * H * 0.008
    hx, hy = cx - bw / 2 + bh * 1.4, base - bh - r * 0.9
    neck = (hx + r * 1.05, hy + r * 0.25)
    hip = (neck[0] + H * 0.33, neck[1] + breath)
    d.line([neck, hip], fill=color, width=lw)
    for k in (-1, 1):
        d.line([hip, (hip[0] + H * 0.22, hip[1] + k * H * 0.015), (hip[0] + H * 0.44, hip[1] + k * H * 0.02)],
               fill=color, width=lw, joint="curve")
    d.line([(neck[0] + H * 0.04, neck[1]), (neck[0] + H * 0.17, neck[1] + H * 0.03 + breath),
            (neck[0] + H * 0.28, neck[1] - H * 0.01 + breath)], fill=color, width=lw, joint="curve")
    # manta
    d.rounded_rectangle([neck[0] + H * 0.08, base - bh - H * 0.05 + breath, cx + bw / 2 - bh * 0.4, base - bh * 0.6],
                        int(H * 0.03), fill=(110, 140, 220, 255))
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=None, outline=color, width=lw)
    for sx in (-1, 1):
        d.line([hx + sx * r * 0.38 - r * 0.15, hy - r * 0.1, hx + sx * r * 0.38 + r * 0.15, hy - r * 0.1],
               fill=color, width=max(3, lw // 2))
    d.arc([hx - r * 0.3, hy + r * 0.15, hx + r * 0.3, hy + r * 0.5], 20, 160, fill=color, width=max(3, lw // 2))
    from make_video import font  # import tardío para no crear dependencia circular al cargar
    for k in range(3):
        ph = (t * 0.5 + k / 3) % 1
        f = font(int(H * (0.07 + 0.05 * ph)))
        d.text((hx + r * 0.8 + ph * H * 0.35, hy - r * 1.5 - ph * H * 0.45), "Z", font=f,
               fill=(255, 255, 255, int(255 * (1 - ph))))
    # luna
    mx, my, mr = cx + bw * 0.42, base - H * 0.95, H * 0.1
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 236, 160, 255))


def dibujar_personaje(img, spec, t, w, h):
    if isinstance(spec, str):
        spec = {"pose": spec}
    H = h * spec.get("altura", 0.3)
    cx = w * spec.get("x", 0.5)
    base = h * spec.get("y", 0.74)
    color = tuple(int(spec.get("color", "#ffffff").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    appear = min(1.0, t / 0.5)
    if spec.get("pose") == "dormido":
        dormido(img, cx, base, H, t, color)
        return
    d = ImageDraw.Draw(img, "RGBA")
    by = base + (1 - appear) * H * 0.2
    if spec.get("contorno", True):  # contorno oscuro para que se vea sobre fotos
        capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _figura(ImageDraw.Draw(capa), cx, by, H, t, spec.get("pose", "saludo"), (0, 0, 0, 200), None, grosor=2.2)
        img.paste(capa, (0, 0), capa)
    _figura(d, cx, by, H, t, spec.get("pose", "saludo"), color, spec.get("objeto"))


def _burbuja(d, x, y, s, color):
    """Icono de comentario (bocadillo)."""
    d.rounded_rectangle([x, y, x + s, y + s * 0.75], int(s * 0.2), fill=color)
    d.polygon([(x + s * 0.2, y + s * 0.7), (x + s * 0.2, y + s), (x + s * 0.5, y + s * 0.7)], fill=color)
    for k in range(3):
        cxk = x + s * (0.27 + k * 0.23)
        d.ellipse([cxk - s * 0.06, y + s * 0.31, cxk + s * 0.06, y + s * 0.43], fill=(30, 30, 30, 255))


def dibujar_encuesta(img, spec, t, w, h, font):
    """Opciones A/B/C… que aparecen una a una, para que la gente comente su letra."""
    d = ImageDraw.Draw(img, "RGBA")
    ops = spec.get("opciones", [])
    y = h * spec.get("y", 0.36)
    bw = w * 0.78
    bh = h * 0.068
    gap = h * 0.018
    f = font(int(min(w, h) * 0.05))
    fl = font(int(min(w, h) * 0.05))
    accent = (255, 204, 0, 255)
    for i, op in enumerate(ops):
        a = max(0.0, min(1.0, (t - 0.4 - i * 0.35) / 0.4))
        if a <= 0:
            continue
        sc = 0.85 + 0.15 * a
        x0 = (w - bw * sc) / 2
        yy = y + i * (bh + gap)
        resalta = spec.get("resaltar_ciclo", True) and int((t - 0.4 - len(ops) * 0.35) / 1.0) % len(ops) == i \
            and t > 0.4 + len(ops) * 0.35
        fill = (255, 255, 255, int(235 * a)) if not resalta else (255, 236, 150, int(245 * a))
        d.rounded_rectangle([x0, yy, x0 + bw * sc, yy + bh], int(bh * 0.4), fill=fill)
        rr = bh * 0.36
        bx, by = x0 + bh * 0.55, yy + bh / 2
        d.ellipse([bx - rr, by - rr, bx + rr, by + rr], fill=accent)
        letra = chr(65 + i)
        tw = d.textlength(letra, font=fl)
        d.text((bx - tw / 2, by - fl.size * 0.6), letra, font=fl, fill=(30, 30, 30, int(255 * a)))
        d.text((bx + rr + bh * 0.35, by - f.size * 0.62), op, font=f, fill=(30, 30, 30, int(255 * a)))
    if spec.get("llamada"):
        _llamada(d, spec["llamada"], t - 0.4 - len(ops) * 0.35, w, y + len(ops) * (bh + gap) + h * 0.015, font)


def _llamada(d, texto, t, w, y, font, ancho=0.86):
    """Banda tipo «Comenta…» con icono de bocadillo y latido."""
    if t <= 0:
        return
    a = min(1.0, t / 0.4)
    pulse = 1 + 0.04 * math.sin(t * 6)
    f = font(int(w * 0.045 * pulse))
    from make_video import wrap
    lines = wrap(d, texto, f, w * ancho - w * 0.2)
    lh = f.size * 1.2
    bh = lh * len(lines) + w * 0.05
    bw = min(w * ancho, max(d.textlength(l, font=f) for l in lines) + w * 0.2)
    x0 = (w - bw) / 2
    d.rounded_rectangle([x0, y, x0 + bw, y + bh], int(w * 0.03), fill=(255, 64, 100, int(240 * a)))
    s = w * 0.08
    _burbuja(d, x0 + w * 0.035, y + (bh - s) / 2, s, (255, 255, 255, int(255 * a)))
    for i, line in enumerate(lines):
        d.text((x0 + w * 0.15, y + w * 0.025 + i * lh), line, font=f, fill=(255, 255, 255, int(255 * a)))


def dibujar_pregunta(img, spec, t, w, h, font):
    """Pregunta a los seguidores para que respondan en comentarios."""
    if isinstance(spec, str):
        spec = {"texto": spec}
    d = ImageDraw.Draw(img, "RGBA")
    _llamada(d, spec["texto"], t - spec.get("retraso", 0.6), w, h * spec.get("y", 0.3), font)
