#!/usr/bin/env python3
"""Diseño de sonido y mezcla de «El último tren de la noche».

Todo se sintetiza aquí con numpy/scipy: ambientes por plano (andén, vagón, tren en marcha, túnel…),
efectos sincronizados (golpes en el cristal, puertas, frenazos, impactos…), música oscura cuya
intensidad sigue la «tensión» de cada plano, silencios repentinos y la voz con reverberación ligera.
Salida: mezcla.wav (estéreo, 44,1 kHz, normalizada a −15 LUFS).
"""
import os
import subprocess
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planos as PL  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
SR = 44100
RNG = np.random.default_rng(1996)


# ===================================================================== utilidades
def t_(n):
    return np.arange(n) / SR


def ruido(n):
    return RNG.standard_normal(n).astype(np.float32)


def marron(n):
    x = np.cumsum(ruido(n))
    x = signal.lfilter([1, -1], [1, -0.995], x)
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def rosa(n):
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    x = signal.lfilter(b, a, ruido(n))
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def pb(x, f, orden=2):
    b, a = signal.butter(orden, min(f / (SR / 2), 0.99), "low")
    return signal.lfilter(b, a, x).astype(np.float32)


def pa(x, f, orden=2):
    b, a = signal.butter(orden, f / (SR / 2), "high")
    return signal.lfilter(b, a, x).astype(np.float32)


def pbanda(x, f1, f2, orden=2):
    b, a = signal.butter(orden, [f1 / (SR / 2), min(f2 / (SR / 2), 0.99)], "band")
    return signal.lfilter(b, a, x).astype(np.float32)


def env(n, ataque=0.01, caida=0.3, forma=3.0):
    t = t_(n)
    a = np.clip(t / max(ataque, 1e-4), 0, 1)
    d = np.exp(-np.maximum(t - ataque, 0) / max(caida, 1e-4) * forma / 3)
    return (a * d).astype(np.float32)


def norm(x, pico=1.0):
    m = np.abs(x).max()
    return (x / m * pico).astype(np.float32) if m > 0 else x


def seno(f, n, fase=0.0):
    if np.isscalar(f):
        return np.sin(2 * np.pi * f * t_(n) + fase).astype(np.float32)
    return np.sin(2 * np.pi * np.cumsum(f) / SR + fase).astype(np.float32)


def reverb_ir(seg=2.2, brillo=4000, semilla=0):
    n = int(seg * SR)
    r = np.random.default_rng(semilla)
    ir = r.standard_normal((2, n)).astype(np.float32) * np.exp(-t_(n) / (seg / 6.9))[None, :]
    ir = np.stack([pb(ir[0], brillo), pb(ir[1], brillo)])
    ir[:, :int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    return ir / np.abs(ir).sum(axis=1, keepdims=True) * 18


def con_reverb(x, mezcla=0.3, seg=2.2, brillo=4000):
    """x mono -> estéreo con reverberación."""
    ir = reverb_ir(seg, brillo)
    l = signal.fftconvolve(x, ir[0])[:len(x)]
    r = signal.fftconvolve(x, ir[1])[:len(x)]
    return np.stack([x * (1 - mezcla) + l * mezcla, x * (1 - mezcla) + r * mezcla]).astype(np.float32)


# ===================================================================== efectos
def sfx_impacto(n=None):
    n = int(3.5 * SR)
    t = t_(n)
    f = 55 * np.exp(-t * 1.2) + 28
    x = seno(f, n) * env(n, 0.005, 1.6) * 1.0
    x += pb(ruido(n), 900) * env(n, 0.002, 0.25) * 0.8
    x += pbanda(ruido(n), 60, 200) * env(n, 0.01, 1.2) * 0.6
    return norm(x, 0.95)


def sfx_riser():
    n = int(4.0 * SR)
    t = t_(n)
    k = (t / t[-1]) ** 2
    x = pbanda(ruido(n), 300, 6000) * k * 0.5
    x += seno(80 + 300 * k, n) * k * 0.4 + seno(81.5 + 304 * k, n) * k * 0.4
    return norm(x * np.minimum(1, (t[-1] - t) / 0.05), 0.8)


def sfx_tictac():
    n = int(6 * SR)
    x = np.zeros(n, np.float32)
    for k in range(6):
        i = int(k * SR)
        m = int(0.03 * SR)
        clic = pbanda(ruido(m), 2000, 6000) * env(m, 0.0005, 0.01)
        x[i:i + m] += clic * (1 if k % 2 == 0 else 0.7)
    return norm(x, 0.6)


def sfx_chispazo():
    n = int(0.9 * SR)
    x = np.zeros(n, np.float32)
    for k in range(9):
        i = int(RNG.uniform(0, 0.7) * SR)
        m = int(RNG.uniform(0.005, 0.05) * SR)
        x[i:i + m] += pa(ruido(m), 1500) * RNG.uniform(0.3, 1.0)
    x += seno(100, n) * 0.25 * (RNG.random(n) > 0.4)
    return norm(pb(x, 9000), 0.7)


def sfx_glitch():
    n = int(0.8 * SR)
    x = np.zeros(n, np.float32)
    base = pbanda(ruido(int(0.06 * SR)), 500, 5000)
    pos = 0
    while pos < n - len(base):
        rep = RNG.integers(1, 5)
        for _ in range(rep):
            if pos + len(base) >= n:
                break
            x[pos:pos + len(base)] += base * RNG.uniform(0.3, 1)
            pos += len(base) // RNG.integers(1, 4)
        pos += int(RNG.uniform(0.0, 0.05) * SR)
    x += seno(1000 + 3000 * (RNG.random(n) > 0.95), n) * 0.1
    return norm(x * env(n, 0.005, 0.7), 0.6)


def sfx_pitido():
    n = int(0.5 * SR)
    x = (seno(880, n) * 0.6 + seno(1320, n) * 0.2) * env(n, 0.005, 0.35)
    return norm(x, 0.5)


def sfx_teclas():
    n = int(1.6 * SR)
    x = np.zeros(n, np.float32)
    for k in range(11):
        i = int((0.25 + k * 0.1) * SR)
        m = int(0.02 * SR)
        x[i:i + m] += pbanda(ruido(m), 1500, 4000) * env(m, 0.001, 0.01)
    return norm(x, 0.5)


def sfx_puertas_abren():
    n = int(2.2 * SR)
    t = t_(n)
    hiss = pbanda(ruido(n), 2500, 9000) * env(n, 0.02, 0.5) * 0.6
    desl = pbanda(ruido(n), 150, 900) * np.clip(np.sin(np.pi * np.clip((t - 0.2) / 1.2, 0, 1)), 0, 1) * 0.5
    golpe = np.zeros(n, np.float32)
    i = int(1.4 * SR)
    m = int(0.3 * SR)
    golpe[i:i + m] = pb(ruido(m), 400) * env(m, 0.002, 0.08)
    return norm(hiss + desl + golpe, 0.75)


def sfx_puertas_cierran():
    n = int(1.6 * SR)
    hiss = pbanda(ruido(n), 2500, 9000) * env(n, 0.02, 0.3) * 0.5
    golpe = np.zeros(n, np.float32)
    i = int(0.7 * SR)
    m = int(0.6 * SR)
    golpe[i:i + m] = (pb(ruido(m), 300) * 1.2 + seno(70, m) * 0.6) * env(m, 0.002, 0.15)
    return norm(hiss + golpe, 0.85)


def sfx_golpe_puertas():
    n = int(2.0 * SR)
    x = (pb(ruido(n), 500) * 1.3 + seno(55, n) * 0.8 + pbanda(ruido(n), 1500, 5000) * 0.3) * env(n, 0.001, 0.3)
    return norm(x, 1.0)


def sfx_pitidos_puerta():
    n = int(1.6 * SR)
    x = np.zeros(n, np.float32)
    for k in range(4):
        i = int(k * 0.35 * SR)
        m = int(0.18 * SR)
        x[i:i + m] += (seno(1046, m) * 0.6 + seno(2093, m) * 0.15) * env(m, 0.004, 0.15)
    return norm(x, 0.5)


def sfx_error_movil():
    n = int(0.8 * SR)
    a = int(0.2 * SR)
    x = np.zeros(n, np.float32)
    x[:a] = seno(520, a) * env(a, 0.005, 0.15)
    x[int(0.25 * SR):int(0.25 * SR) + a] = seno(390, a) * env(a, 0.005, 0.15)
    return norm(x, 0.45)


def sfx_susurro(n=None, largo=1.6):
    n = int(largo * SR)
    t = t_(n)
    x = pbanda(ruido(n), 1200, 7000)
    # formantes que se mueven: sensación de palabra susurrada
    f1 = 700 + 500 * np.sin(2 * np.pi * 2.3 * t)
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(f1 / 400) / SR)
    x = x * mod * np.sin(np.pi * t / t[-1]) ** 2
    return norm(x, 0.55)


def sfx_susurros():
    n = int(3.5 * SR)
    x = np.zeros(n, np.float32)
    for k in range(6):
        s = sfx_susurro(largo=RNG.uniform(0.8, 1.6))
        i = int(RNG.uniform(0, 1.8) * SR)
        x[i:i + len(s)] += s * RNG.uniform(0.4, 1)
    return norm(x, 0.6)


def sfx_whoosh():
    n = int(0.9 * SR)
    t = t_(n)
    f = 400 + 3000 * np.sin(np.pi * t / t[-1])
    x = ruido(n)
    out = np.zeros(n, np.float32)
    for k in range(0, n, 2048):
        out[k:k + 2048] = pbanda(x[k:k + 2048], max(100, f[k] * 0.5), f[k] * 1.5, 1)
    return norm(out * np.sin(np.pi * t / t[-1]) ** 2, 0.7)


def sfx_drone_sube():
    n = int(4.5 * SR)
    t = t_(n)
    k = t / t[-1]
    x = sum(seno(f * (1 + 0.06 * k), n) for f in (110, 116.5, 164.8, 233)) * k ** 1.5
    x += pbanda(ruido(n), 2000, 8000) * k ** 3 * 0.4
    return norm(x * np.minimum(1, (t[-1] - t) / 0.3), 0.6)


def sfx_frenazo():
    n = int(3.2 * SR)
    t = t_(n)
    f = 2400 - 600 * t / t[-1] + 80 * np.sin(2 * np.pi * 7 * t)
    chirr = (seno(f, n) * 0.5 + seno(f * 1.51, n) * 0.25) * env(n, 0.05, 2.0)
    chirr *= 0.6 + 0.4 * (RNG.random(n) > 0.3)
    rum = pb(marron(n), 200) * env(n, 0.02, 2.5) * 1.5
    return norm(pb(chirr, 6000) + rum, 0.9)


def sfx_agarre():
    n = int(1.5 * SR)
    x = pbanda(ruido(n), 800, 4000) * env(n, 0.005, 0.15) * 0.8
    x += sfx_impacto()[:n] * 0.5
    return norm(x, 0.8)


def sfx_escalofrio():
    n = int(2.5 * SR)
    t = t_(n)
    x = sum(seno(f, n) * 0.2 for f in (2093, 2217, 3136, 3322)) * np.sin(np.pi * t / t[-1])
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)
    return norm(x, 0.35)


def sfx_apagon():
    n = int(2.0 * SR)
    t = t_(n)
    clunk = (pb(ruido(n), 300) * 1.2 + seno(45, n)) * env(n, 0.001, 0.2)
    caida = seno(120 * np.exp(-t * 2.2), n) * np.exp(-t * 1.5) * 0.5
    return norm(clunk + caida, 0.9)


def sfx_golpe_cristal():
    n = int(1.2 * SR)
    thud = (pb(ruido(n), 250) * 1.2 + seno(90, n) * 0.8) * env(n, 0.001, 0.09)
    vidrio = sum(seno(f, n) * a for f, a in ((1180, 0.3), (2650, 0.2), (4300, 0.1))) * env(n, 0.001, 0.25)
    return norm(thud + vidrio, 1.0)


def sfx_pasos_corre():
    n = int(4.0 * SR)
    x = np.zeros(n, np.float32)
    for k in range(int(4.0 / 0.19)):
        i = int(k * 0.19 * SR)
        m = int(0.08 * SR)
        if i + m < n:
            x[i:i + m] += pb(ruido(m), 1200) * env(m, 0.001, 0.03) * (0.7 + 0.3 * (k % 2))
    return norm(x, 0.5)


def sfx_pasos():
    n = int(4.0 * SR)
    x = np.zeros(n, np.float32)
    for k in range(6):
        i = int((0.2 + k * 0.62) * SR)
        m = int(0.15 * SR)
        x[i:i + m] += pbanda(ruido(m), 200, 2500) * env(m, 0.002, 0.05)
    return norm(con_reverb(x, 0.5, 2.5).mean(axis=0), 0.5)


def sfx_grito():
    n = int(1.6 * SR)
    t = t_(n)
    f0 = 280 + 120 * np.sin(np.pi * t / t[-1])
    x = sum(seno(f0 * h, n) / h for h in range(1, 9)) * (1 + 0.05 * ruido(n))
    x = pbanda(x, 500, 3000)
    x = pb(x, 1200)  # amortiguado: detrás del cristal
    return norm(x * np.sin(np.pi * t / t[-1]), 0.6)


def sfx_estatica():
    n = int(2.0 * SR)
    x = pbanda(ruido(n), 800, 5000) * (0.5 + 0.5 * (RNG.random(n) > 0.5)) * env(n, 0.05, 1.5)
    return norm(x, 0.4)


def sfx_ding_dong():
    n = int(2.5 * SR)
    x = np.zeros(n, np.float32)
    for k, f in enumerate((659, 523)):
        i = int(k * 0.55 * SR)
        m = n - i
        tono = sum(seno(f * h * (1 + 0.003 * h), m) / h ** 1.5 for h in (1, 2, 3, 4.2)) * env(m, 0.003, 1.2)
        x[i:] += tono
    x = np.tanh(x * 2.5) * 0.5  # distorsión de megafonía vieja
    return norm(pbanda(x, 300, 3500), 0.6)


def sfx_papel():
    n = int(1.4 * SR)
    x = pbanda(ruido(n), 1500, 8000) * (RNG.random(n) > 0.7) * np.sin(np.pi * t_(n) / (n / SR))
    return norm(x, 0.35)


def sfx_estruendo():
    n = int(3.0 * SR)
    x = (pb(marron(n), 400) * 1.5 + pbanda(ruido(n), 200, 3000) * 0.7) * env(n, 0.005, 1.5)
    x += sfx_impacto()[:n]
    for k in range(14):
        i = int(RNG.uniform(0, 2.2) * SR)
        m = int(0.2 * SR)
        x[i:i + m] += pbanda(ruido(m), 800, 5000) * env(m, 0.001, 0.08) * RNG.uniform(0.3, 0.9)
    return norm(np.tanh(x * 1.5), 1.0)


def sfx_cristales():
    n = int(2.6 * SR)
    x = pa(ruido(n), 3000) * env(n, 0.001, 0.3) * 0.8
    for k in range(60):
        i = int(abs(RNG.normal(0.15, 0.5)) * SR)
        m = int(0.25 * SR)
        if i + m < n:
            f = RNG.uniform(2500, 9000)
            x[i:i + m] += seno(f, m) * env(m, 0.0005, 0.06) * RNG.uniform(0.1, 0.5)
    return norm(x, 0.9)


def sfx_gritos():
    n = int(2.6 * SR)
    x = np.zeros(n, np.float32)
    for k in range(6):
        g = sfx_grito()
        g = signal.resample(g, int(len(g) * RNG.uniform(0.8, 1.25))).astype(np.float32)
        i = int(RNG.uniform(0, 0.8) * SR)
        m = min(len(g), n - i)
        x[i:i + m] += g[:m] * RNG.uniform(0.4, 1)
    return norm(con_reverb(x, 0.5, 1.5).mean(axis=0), 0.8)


def sfx_brillo():
    n = int(3.5 * SR)
    t = t_(n)
    x = sum(seno(f, n) * 0.2 * np.sin(np.pi * np.clip(t / t[-1] * 1.2 - k * 0.05, 0, 1))
            for k, f in enumerate((523, 659, 784, 988, 1175)))
    return norm(x, 0.4)


def sfx_zoom_digital():
    n = int(1.5 * SR)
    x = np.zeros(n, np.float32)
    for k in range(4):
        i = int(k * 0.3 * SR)
        m = int(0.07 * SR)
        x[i:i + m] += seno(1800 + k * 300, m) * env(m, 0.002, 0.05)
    return norm(x, 0.35)


def sfx_chirrido_dedo():
    n = int(4.5 * SR)
    t = t_(n)
    f = 1400 + 500 * np.sin(2 * np.pi * 0.9 * t) + 200 * np.sin(2 * np.pi * 3.1 * t)
    x = seno(f, n) * (0.4 + 0.6 * (np.sin(2 * np.pi * 1.7 * t) > -0.2)) * np.sin(np.pi * t / t[-1])
    return norm(pb(x, 4000), 0.3)


SFX = {k[4:]: v for k, v in globals().items() if k.startswith("sfx_")}


# ===================================================================== ambientes
def clacks(n, periodo=1.15, fuerza=1.0, vel=None):
    """Traqueteo de las ruedas en las juntas del raíl (ta-dum, ta-dum)."""
    x = np.zeros(n, np.float32)
    m = int(0.09 * SR)
    golpe = pb(ruido(m), 700) * env(m, 0.001, 0.03)
    pos = 0.0
    while True:
        p = periodo if vel is None else periodo / max(0.15, vel[min(int(pos * SR), n - 1)])
        for off in (0.0, 0.16):
            i = int((pos + off) * SR)
            if i + m < n:
                x[i:i + m] += golpe * fuerza
        pos += p
        if pos * SR >= n:
            break
    return x


def amb(tipo, n):
    t = t_(n)
    if tipo in ("silencio", "nada"):
        return np.zeros(n, np.float32) if tipo == "nada" else pb(rosa(n), 300) * 0.006
    if tipo == "tunel":
        return pb(marron(n), 300) * 0.25 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.11 * t)) + pb(rosa(n), 900) * 0.03
    if tipo in ("anden", "zumbido", "maquina"):
        hum = sum(seno(100 * h, n) / h ** 1.3 for h in range(1, 6)) * 0.012
        room = pb(rosa(n), 1500) * 0.05
        x = hum + room
        if tipo == "zumbido":
            x += sum(seno(100 * h, n) / h for h in range(1, 9)) * 0.035
            x += pa(ruido(n), 3000) * (RNG.random(n) > 0.9985) * 0.4
        if tipo == "maquina":
            x += (seno(60, n) * 0.06 + seno(120, n) * 0.04) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * t))
            x += pbanda(ruido(n), 200, 600) * 0.02
        return x
    if tipo == "tren_llega":
        k = (t / t[-1])
        rum = pb(marron(n), 250) * (0.1 + 0.9 * k ** 2) * 0.9
        cl = clacks(n, 0.5, 0.5) * k ** 2
        chirr = (seno(2600 - 500 * k, n) * 0.12 + seno(3900 - 700 * k, n) * 0.05) * np.clip((k - 0.6) / 0.2, 0, 1) \
            * np.clip((1 - k) / 0.1, 0, 1)
        return rum + cl + chirr
    if tipo in ("tren_parado", "vagon_parado"):
        return (seno(120, n) * 0.025 + seno(240, n) * 0.01 + pbanda(ruido(n), 300, 2000) * 0.04
                + pb(rosa(n), 400) * 0.06)
    if tipo == "tren_marcha":
        rum = pb(marron(n), 180) * 0.55 + pbanda(rosa(n), 200, 1200) * 0.05
        return rum * (0.9 + 0.1 * np.sin(2 * np.pi * 0.3 * t)) + clacks(n, 1.1, 0.35) + pb(rosa(n), 400) * 0.05
    if tipo == "tren_arranca":
        k = np.clip(t / min(t[-1], 4.0), 0, 1)
        rum = pb(marron(n), 180) * 0.55 * k
        return rum + clacks(n, 1.1, 0.35, vel=np.maximum(k, 0.15)) * k + seno(110 + 140 * k, n) * 0.03 * k
    if tipo == "tren_frena":
        k = 1 - 0.75 * np.clip(t / t[-1], 0, 1)
        return pb(marron(n), 180) * 0.5 * k + clacks(n, 1.1, 0.35, vel=k) + seno(2200, n) * 0.02 * (1 - k)
    if tipo == "frenazo":
        return pb(marron(n), 180) * 0.5 * np.exp(-t / 2)
    if tipo == "silencio_tunel":
        x = pb(marron(n), 200) * 0.07
        for k in range(int(t[-1] / 2.5) + 1):
            i = int((k * 2.5 + RNG.uniform(0, 1.5)) * SR)
            m = int(0.3 * SR)
            if i + m < n:
                x[i:i + m] += seno(RNG.uniform(1500, 2500) * np.exp(-t_(m) * 8), m) * env(m, 0.001, 0.04) * 0.1
        return x
    if tipo == "oscuro":
        x = pb(marron(n), 150) * 0.2 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t))
        for k in range(int(t[-1] / 5) + 1):
            i = int((k * 5 + RNG.uniform(0, 3)) * SR)
            m = int(1.2 * SR)
            if i + m < n:  # crujido metálico lejano
                f = RNG.uniform(300, 600)
                x[i:i + m] += seno(f + 40 * np.sin(2 * np.pi * 3 * t_(m)), m) * env(m, 0.3, 0.6) * 0.03
        return x
    if tipo == "caja_musica":
        notas = [69, 72, 76, 75, 72, 69, 68, 71, 74, 72, 69, 64]
        x = pb(marron(n), 200) * 0.06
        paso = 0.62
        for k in range(int(t[-1] / paso)):
            i = int(k * paso * SR)
            m = min(int(1.5 * SR), n - i)
            f = 440 * 2 ** ((notas[k % len(notas)] - 69) / 12) * (1 + 0.004 * np.sin(k))
            x[i:i + m] += (seno(f, m) * 0.6 + seno(f * 2.01, m) * 0.2 + seno(f * 4.2, m) * 0.08) * env(m, 0.002, 0.5)\
                * 0.12
        return x
    if tipo == "latidos":
        x = pb(marron(n), 120) * 0.08
        periodo = 0.82
        for k in range(int(t[-1] / periodo) + 1):
            for off, g in ((0.0, 1.0), (0.22, 0.7)):
                i = int((k * periodo + off) * SR)
                m = int(0.25 * SR)
                if i + m < n:
                    x[i:i + m] += seno(48, m) * env(m, 0.004, 0.08) * 0.5 * g
        return x
    if tipo == "caos":
        return np.tanh(pb(marron(n), 500) * 1.5 + pbanda(ruido(n), 300, 3000) * 0.2) * 0.5
    if tipo == "calido":
        acorde = [130.8, 164.8, 196.0, 246.9, 329.6]
        x = sum(seno(f * (1 + 0.002 * k), n) * (0.04 / (1 + k * 0.3)) * (0.75 + 0.25 * np.sin(2 * np.pi * (0.1 + k * 0.03) * t))
                for k, f in enumerate(acorde))
        return pb(x, 2500)
    if tipo == "anden_dia":
        x = pb(rosa(n), 2500) * 0.06 + sum(seno(100 * h, n) / h for h in range(1, 4)) * 0.006
        for k in range(int(t[-1] / 0.55)):
            i = int((k * 0.55 + RNG.uniform(0, 0.1)) * SR)
            m = int(0.1 * SR)
            if i + m < n and (k // 6) % 2 == 0:
                x[i:i + m] += pbanda(ruido(m), 300, 2500) * env(m, 0.002, 0.04) * 0.04
        return x
    if tipo == "sala":
        return pb(rosa(n), 1200) * 0.05 + seno(15700, n) * 0.004 + seno(60, n) * 0.01
    return np.zeros(n, np.float32)


# ===================================================================== música
def musica(n, tension):
    """Drones oscuros cuya intensidad sigue la tensión (curva por muestra)."""
    t = t_(n)
    base = (seno(55, n) * 0.5 + seno(55.3, n) * 0.4 + seno(82.4, n) * 0.25 + seno(110.4, n) * 0.12)
    base = pb(base, 400) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.05 * t))
    # cuerdas disonantes (diente de sierra filtrado) que aparecen con la tensión
    saw = sum(signal.sawtooth(2 * np.pi * f * t + RNG.uniform(0, 6)).astype(np.float32) for f in
              (233.1, 246.9, 349.2, 369.99, 466.2))
    saw = pbanda(saw, 300, 1800) * 0.05 * (0.85 + 0.15 * np.sin(2 * np.pi * 5.5 * t))
    alto = sum(seno(f, n) for f in (1864.7, 1975.5)) * 0.015 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.23 * t))
    pulso = np.zeros(n, np.float32)
    periodo = 0.75
    m = int(0.4 * SR)
    golpe = seno(41, m) * env(m, 0.005, 0.18) * 0.6
    for k in range(int(t[-1] / periodo)):
        i = int(k * periodo * SR)
        if i + m < n:
            pulso[i:i + m] += golpe
    ten = tension
    x = base * (0.25 + 0.55 * ten) + saw * ten ** 1.8 + alto * ten ** 2.5 + pulso * np.clip((ten - 0.7) / 0.3, 0, 1)
    return x.astype(np.float32)


# ===================================================================== mezcla
def main():
    dur = PL.DURACION
    n = int(dur * SR) + SR
    planos = PL.PLANOS_T

    # --- ambientes por plano con fundidos (cortes secos en los silencios)
    amb_bus = np.zeros(n, np.float32)
    fade = int(0.35 * SR)
    for k, p in enumerate(planos):
        tipo = p["op"].get("amb", "silencio")
        i0 = int(p["t0"] * SR)
        i1 = min(n, int(p["t1"] * SR))
        seco = tipo in ("silencio", "nada") or (k + 1 < len(planos) and
                                                planos[k + 1]["op"].get("amb") in ("silencio", "nada"))
        cola = int(0.03 * SR) if seco else fade
        a0 = max(0, i0 - (fade if tipo not in ("silencio", "nada") and k > 0 and
                          planos[k - 1]["op"].get("amb") not in ("silencio", "nada") else 0))
        seg = amb(tipo, i1 + cola - a0)
        e = np.ones(len(seg), np.float32)
        ent = i0 - a0
        if ent > 0:
            e[:ent] = np.linspace(0, 1, ent)
        e[-cola:] = np.linspace(1, 0, cola)
        m = min(len(seg), n - a0)
        amb_bus[a0:a0 + m] += (seg * e)[:m]

    # --- tensión suavizada
    ten = np.zeros(n, np.float32)
    for p in planos:
        ten[int(p["t0"] * SR):int(p["t1"] * SR)] = p["op"].get("tension", 0.3)
    ten = signal.lfilter([1 - 0.99997], [1, -0.99997], ten).astype(np.float32)  # ~0.75 s
    for p in planos:  # los silencios cortan también la música de golpe
        if p["op"].get("amb") == "nada":
            ten[int(p["t0"] * SR):int(p["t1"] * SR)] = 0
    mus = musica(n, ten)
    mudo = np.ones(n, np.float32)
    for p in planos:
        if p["op"].get("amb") in ("nada",):
            mudo[int(p["t0"] * SR):int(p["t1"] * SR)] = 0.0
        elif p["op"].get("amb") == "silencio":
            mudo[int(p["t0"] * SR):int(p["t1"] * SR)] = 0.35
    mudo = signal.lfilter([1 - 0.999], [1, -0.999], mudo).astype(np.float32)
    mus *= mudo

    # --- efectos
    sfx_bus = np.zeros(n, np.float32)
    cache = {}
    for p in planos:
        for off, nombre, g in p["op"].get("sfx", []):
            if nombre not in cache:
                cache[nombre] = SFX[nombre]()
            s = cache[nombre] if nombre in ("impacto",) else SFX[nombre]()
            i = int((p["t0"] + off) * SR)
            m = min(len(s), n - i)
            sfx_bus[i:i + m] += s[:m] * g

    # --- voz
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(AQUI, "voz.wav"), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    voz = np.frombuffer(raw, np.float32).copy()
    voz = np.pad(voz, (0, max(0, n - len(voz))))[:n]
    voz = pa(voz, 70)
    voz_st = con_reverb(voz, 0.10, 1.4, 3500)

    # envolvente de la voz para atenuar el resto (ducking)
    ev = np.abs(voz)
    ev = signal.lfilter([1 - 0.9995], [1, -0.9995], ev)
    ev = ev / (np.percentile(ev, 99) + 1e-9)
    duck = 1 - 0.6 * np.clip(ev * 1.5, 0, 1)

    # silencio absoluto: corta ambiente, música y colas de efectos casi de golpe
    puerta = np.ones(n, np.float32)
    for p in planos:
        if p["op"].get("amb") == "nada":
            puerta[int(p["t0"] * SR):int(p["t1"] * SR)] = 0.0
    puerta = signal.lfilter([1 - 0.995], [1, -0.995], puerta).astype(np.float32)

    amb_st = np.stack([amb_bus, np.roll(amb_bus, 331)]) * 0.30
    mus_st = con_reverb(mus, 0.4, 3.5, 2500) * 0.24
    sfx_st = con_reverb(sfx_bus, 0.25, 2.2, 6000) * 0.5
    fondo_ = ((amb_st + mus_st) * duck[None, :] + sfx_st * (0.55 + 0.45 * duck[None, :])) * puerta[None, :]
    habla = ev > 0.15
    def db(a):
        return 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-9)
    print(f"voz {db(voz_st[:, habla]):.1f} dB | fondo bajo la voz {db(fondo_[:, habla]):.1f} dB | "
          f"fondo sin voz {db(fondo_[:, ~habla]):.1f} dB")
    mezcla = voz_st * 1.0 + fondo_
    mezcla = np.tanh(mezcla * 0.9) / 0.9
    # fundido final
    fin = int(2.0 * SR)
    mezcla[:, -fin:] *= np.linspace(1, 0, fin)[None, :]
    tmp = os.path.join(AQUI, "_mezcla_bruta.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", tmp], input=mezcla.T.astype(np.float32).tobytes(), check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", "loudnorm=I=-15:TP=-1.5:LRA=14",
                    "-ar", str(SR), "-c:a", "pcm_s16le", os.path.join(AQUI, "mezcla.wav")], check=True)
    os.remove(tmp)
    print("mezcla.wav lista:", round(n / SR, 1), "s")


if __name__ == "__main__":
    main()
