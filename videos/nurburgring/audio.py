#!/usr/bin/env python3
"""Banda sonora del vídeo Nürburgring: música electrónica generada + efectos + voz.

Uso: python3 audio.py  → mezcla.wav (en esta carpeta)
"""
import os
import subprocess
import wave

import numpy as np
from scipy import signal

AQUI = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DUR = 124.6
BPM = 120
BEAT = 60 / BPM
rng = np.random.default_rng(3)
N = int(DUR * SR)


def leer_voz():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(AQUI, "voz.mp3"), "-f", "f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    v = np.frombuffer(raw, np.float32).astype(np.float64)
    out = np.zeros(N)
    out[:min(N, len(v))] = v[:N]
    return out


def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    e = np.exp(-t / d)
    na = max(1, int(a * SR))
    e[:na] *= np.linspace(0, 1, na)
    return e


def lp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def bp(x, f1, f2, order=2):
    b, a = signal.butter(order, [f1 / (SR / 2), f2 / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def add(buf, snd, t):
    i = int(t * SR)
    if i >= len(buf) or i + len(snd) <= 0:
        return
    s = snd[: max(0, len(buf) - i)]
    buf[i:i + len(s)] += s


def nota(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ------------------------------------------------------------ instrumentos
def kick():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(n, 0.001, 0.16) * 1.0 + rng.normal(0, 1, n) * env(n, 0.0005, 0.004) * 0.25


def clap():
    n = int(0.3 * SR)
    x = bp(rng.normal(0, 1, n), 900, 5000)
    e = env(n, 0.001, 0.09)
    for k in (0.0, 0.011, 0.022):
        e += np.roll(env(n, 0.0005, 0.008), int(k * SR)) * 0.6
    return x * e * 0.45


def hat(op=False):
    n = int((0.25 if op else 0.06) * SR)
    return hp(rng.normal(0, 1, n), 7000) * env(n, 0.0005, 0.08 if op else 0.018) * 0.22


def saw(f, n, det=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in (-det, 0, det) if det else (0,):
        out += 2 * ((t * f * (1 + d)) % 1) - 1
    return out / (3 if det else 1)


def bajo(m, dur):
    n = int(dur * SR)
    x = saw(nota(m), n) * 0.6 + np.sin(2 * np.pi * nota(m) * np.arange(n) / SR) * 0.7
    x = lp(x, 380)
    e = np.minimum(1, np.arange(n) / (0.005 * SR)) * np.exp(-np.arange(n) / SR / (dur * 0.9))
    return x * e * 0.55


def pad(ms, dur):
    n = int(dur * SR)
    x = sum(saw(nota(m), n, 0.006) for m in ms)
    x = lp(x, 1400)
    a = np.minimum(1, np.arange(n) / (0.6 * SR))
    r = np.minimum(1, (n - np.arange(n)) / (0.5 * SR))
    return x * a * r * 0.07


def pluck(m, dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sign(np.sin(2 * np.pi * nota(m) * t)) * 0.5 + saw(nota(m + 12), n) * 0.3
    return lp(x, 2600) * env(n, 0.002, 0.09) * 0.12


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.normal(0, 1, n)
    # barrido: mezcla de bandas cada vez más agudas
    lo, hi = hp(x, 300), hp(x, 3000)
    k = (t / dur) ** 2
    s = (lo * (1 - k) + hi * k) * k * 0.25
    f = 200 + 1600 * k
    s += np.sin(2 * np.pi * np.cumsum(f) / SR) * k * 0.06
    return s


def whoosh(dur=0.55, up=True):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.normal(0, 1, n)
    a, b = bp(x, 300, 1200), bp(x, 1500, 6000)
    k = t / dur if up else 1 - t / dur
    e = np.sin(np.pi * t / dur) ** 2
    return (a * (1 - k) + b * k) * e * 0.35


def impacto():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = 38 + 70 * np.exp(-t / 0.06)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.45)
    crack = lp(rng.normal(0, 1, n), 5000) * env(n, 0.0005, 0.05)
    tail = lp(rng.normal(0, 1, n), 900) * env(n, 0.01, 0.5) * 0.25
    return boom * 0.9 + crack * 0.35 + tail


def tick():
    n = int(0.03 * SR)
    return np.sin(2 * np.pi * 2400 * np.arange(n) / SR) * env(n, 0.0003, 0.006) * 0.25


def pop():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 500 + 900 * np.exp(-t / 0.02)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.04) * 0.25


def ding():
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1318.5 * t) + 0.6 * np.sin(2 * np.pi * 1975.5 * t)) * env(n, 0.002, 0.25) * 0.18


def glitch():
    n = int(0.35 * SR)
    x = np.sign(np.sin(2 * np.pi * 90 * np.arange(n) / SR)) * (rng.random(n) > 0.4)
    x = x * np.repeat(rng.random(n // 400 + 1) > 0.5, 400)[:n]
    return lp(x, 3000) * 0.12


# ------------------------------------------------------------ música
def musica():
    m = np.zeros(N)
    acordes = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]  # Am F C G
    compas = 4 * BEAT
    sin_bateria = [(15.1, 17.2), (76.1, 80.9), (119.5, 121.0)]
    intro_fin = 7.7

    def en(t, zonas):
        return any(a <= t < b for a, b in zonas)

    nb = int(DUR / BEAT)
    for i in range(nb):
        t = i * BEAT
        if t > 122.6:
            break
        bar = int(t // compas)
        raiz, triada = acordes[bar % 4]
        drums = t >= intro_fin and not en(t, sin_bateria)
        if i % 4 == 0:
            add(m, pad(triada, compas + 0.4), t)
        if drums:
            add(m, kick(), t)
            if i % 2 == 1:
                add(m, clap(), t)
        elif t < intro_fin and i % 2 == 0:
            add(m, kick() * 0.5, t)
        for k in range(2):
            tt = t + k * BEAT / 2
            if t >= intro_fin or k == 1:
                add(m, bajo(raiz - 12 + (12 if k == 1 else 0), BEAT / 2 * 0.95), tt)
        for k in range(4):
            if drums or t < intro_fin:
                add(m, hat(op=(k == 2 and drums)) * (1 if k % 2 else 0.6), t + k * BEAT / 4)
        if drums and (bar % 8) >= 4:
            arp = [triada[0] + 12, triada[1] + 12, triada[2] + 12, triada[1] + 24]
            for k in range(4):
                add(m, pluck(arp[(i * 4 + k) % 4]), t + k * BEAT / 4)
    # risers antes de los golpes grandes
    for t_hit, d in [(7.7, 3.0), (14.12, 2.4), (48.24, 2.0), (64.88, 2.0), (82.88, 1.7), (121.08, 1.5)]:
        add(m, riser(d), t_hit - d)
    # acorde final
    add(m, pad([57, 64, 69, 72], 3.5) * 2.5, 121.08)
    return m


def efectos():
    s = np.zeros(N)
    cortes = [7.7, 11.2, 15.1, 22.6, 29.8, 32.6, 38.0, 43.9, 48.1, 64.6, 76.1, 81.0, 92.0, 100.2, 108.4, 114.3]
    for c in cortes:
        add(s, whoosh(), c - 0.3)
    for t in [2.8, 14.12, 29.9, 49.8, 66.72, 76.3, 82.88, 106.96, 118.18, 121.08]:
        add(s, impacto(), t)
    for t in [15.86, 16.4, 17.26, 81.2]:
        add(s, glitch(), t)
    # contador 0→30
    for k in range(30):
        add(s, tick(), 7.9 + k * 0.022)
    # casillas del calendario, checklist, burbujas
    for k in range(30):
        add(s, tick() * 0.6, 24.8 + k * 0.055)
    for t in [38.28, 39.18, 40.44, 41.34]:
        add(s, pop() * 1.4, t)
    for t in [51.32, 52.32, 54.44, 57.18, 58.8, 61.46, 70.54, 71.84, 74.26]:
        add(s, pop(), t)
    for k in range(18):
        add(s, pop() * 0.6, 84.6 + k * 0.62)
    for t in [101.98, 102.9, 103.5]:
        add(s, ding(), t)
    for k in range(40):
        add(s, tick() * 0.5, 119.6 + k * 0.035)
    return s


def main():
    voz = leer_voz()
    mus = musica()
    sfx = efectos()
    # ducking: baja la música cuando habla la voz
    e = np.abs(voz)
    e = lp(e, 6)
    e = e / (e.max() + 1e-9)
    act = np.clip(e * 12, 0, 1)
    act = lp(act, 3)
    g = 1.0 - 0.55 * np.clip(act, 0, 1)
    mus = mus / (np.abs(mus).max() + 1e-9) * 0.42 * g
    sfx = sfx / (np.abs(sfx).max() + 1e-9) * 0.55
    voz = voz / (np.abs(voz).max() + 1e-9) * 0.92
    mix = voz + mus + sfx
    # fundido final
    nf = int(1.5 * SR)
    mix[-nf:] *= np.linspace(1, 0, nf)
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    mix = mix / np.abs(mix).max() * 0.97
    st = np.stack([mix, mix], 1)
    with wave.open(os.path.join(AQUI, "mezcla.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    print("mezcla.wav lista")


if __name__ == "__main__":
    main()
