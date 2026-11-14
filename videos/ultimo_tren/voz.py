#!/usr/bin/env python3
"""Limpia la locución y genera los tiempos por palabra del guion.

1. Quita de `voz_original.mp3` las cabeceras leídas («Escena 2. El vagón vacío. Cero cuarenta a…»),
   ajustando cada corte al silencio real y dejando una pausa dramática entre escenas.
2. Alinea el texto del guion (`guion.txt`) con las palabras de Whisper (`whisper.json`) para tener
   subtítulos con la ortografía correcta y tiempos ya en la línea temporal recortada.

Salida: `voz.wav` (44.1 kHz mono) y `palabras.json` [{w, s, e, escena}].
"""
import difflib
import json
import os
import re
import subprocess
import unicodedata

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
SR = 44100

# (inicio de la cabecera, fin de la cabecera, pausa que queda) en segundos del audio original,
# tomados de Whisper; se afinan con la envolvente de volumen.
CORTES = [
    (2.30, 7.26, 1.10),     # Escena 1. El gancho. 0:00 a 0:40
    (60.38, 65.52, 1.60),   # Escena 2. El vagón vacío. 0:40 a 1:35
    (131.30, 137.28, 1.60),  # Escena 3. Las estaciones imposibles. 1:35 a 2:35
    (211.70, 215.46, 1.60),  # La verdad de la anciana. 2:35 a 3:40
    (284.98, 288.70, 1.60),  # El pasajero del túnel. 3:40 a 4:40
    (352.30, 355.70, 1.60),  # El descubrimiento. 4:40 a 5:35
    (435.28, 438.96, 1.70),  # El final. 5:35 a 6:10
    (491.12, 493.36, 2.20),  # Última escena. Giro final.
]


def cargar(ruta):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", ruta, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def silencios(x, umbral_db=-42, minimo=0.10):
    hop = int(SR * 0.01)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-9))
    quieto = db < umbral_db
    regiones, i = [], 0
    while i < n:
        if quieto[i]:
            j = i
            while j < n and quieto[j]:
                j += 1
            if (j - i) * 0.01 >= minimo:
                regiones.append((i * 0.01, j * 0.01))
            i = j
        else:
            i += 1
    return regiones


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", s)


def main():
    x = cargar(os.path.join(AQUI, "voz_original.mp3"))
    sil = silencios(x)
    piezas, mapa = [], []  # mapa: (ini_orig, fin_orig, desplazamiento)
    pos, t_nuevo = 0.0, 0.0
    for a, b, pausa in CORTES:
        # fin real de la voz anterior: inicio del silencio que empieza justo antes de la cabecera
        cand = [s for s in sil if s[0] <= a + 0.05 and s[1] >= a - 0.05]
        fin_voz = cand[0][0] if cand else a - 0.3
        cand = [s for s in sil if s[0] <= b + 0.15 and s[1] >= b - 0.05]
        ini_voz = cand[-1][1] if cand else b + 0.3
        corte_a = fin_voz + 0.10
        corte_b = max(ini_voz - 0.06, corte_a)
        # siguiente palabra: el final del silencio que sigue a la cabecera
        sig = [s for s in sil if s[0] >= b - 0.25]
        if sig:
            corte_b = max(sig[0][1] - 0.06, corte_a)
        piezas.append(x[int(pos * SR):int(corte_a * SR)])
        mapa.append((pos, corte_a, t_nuevo - pos))
        t_nuevo += corte_a - pos
        hueco = max(0.0, pausa - 0.16)
        piezas.append(np.zeros(int(hueco * SR), np.float32))
        t_nuevo += hueco
        pos = corte_b
        print(f"corte {a:7.2f}-{b:7.2f}  ->  quita {corte_a:7.2f}-{corte_b:7.2f}")
    piezas.append(x[int(pos * SR):])
    mapa.append((pos, len(x) / SR, t_nuevo - pos))
    y = np.concatenate(piezas)
    # final: deja 1 s de cola
    y = np.concatenate([y, np.zeros(SR, np.float32)])
    pico = np.abs(y).max()
    y = y / pico * 0.89
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s16le", os.path.join(AQUI, "voz.wav")], input=y.astype(np.float32).tobytes(),
                   check=True)
    print(f"duración voz: {len(y) / SR:.2f} s (original {len(x) / SR:.2f} s)")

    def a_nuevo(t):
        for i0, i1, d in mapa:
            if i0 - 0.2 <= t <= i1 + 0.2:
                return t + d
        return None

    # ---------- alineación del guion
    ww = json.load(open(os.path.join(AQUI, "whisper.json")))
    wh = []
    for w in ww:
        tn = a_nuevo((w["s"] + w["e"]) / 2)
        if tn is None:
            continue
        d = w["s"] + (a_nuevo(w["s"]) if a_nuevo(w["s"]) is not None else tn) - w["s"]
        e = w["e"] + (a_nuevo(w["e"]) if a_nuevo(w["e"]) is not None else tn) - w["e"]
        for parte in w["w"].strip().split():
            wh.append({"n": norm(parte), "s": d, "e": e})
    guion = []
    escena = 0
    for linea in open(os.path.join(AQUI, "guion.txt"), encoding="utf-8"):
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("#"):
            escena += 1
            continue
        for k, tok in enumerate(linea.split()):
            guion.append({"w": tok, "escena": escena, "inicio_linea": k == 0})
    # expandir números del guion a como se pronuncian para casar con whisper
    habla = {"3:17": ["tres", "diecisiete"], "1986": ["1986"], "1996": ["1996"], "14": ["14"]}
    gn, gi = [], []
    for i, g in enumerate(guion):
        base = re.sub(r"[«»—.,:;!¡?¿…\"]", "", g["w"]) if g["w"] != "3:17" and "3:17" not in g["w"] else "3:17"
        for p in habla.get(base, [norm(g["w"])]):
            gn.append(norm(p))
            gi.append(i)
    sm = difflib.SequenceMatcher(a=gn, b=[w["n"] for w in wh], autojunk=False)
    t_ini = [None] * len(guion)
    t_fin = [None] * len(guion)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            gidx = gi[blk.a + k]
            w = wh[blk.b + k]
            t_ini[gidx] = w["s"] if t_ini[gidx] is None else min(t_ini[gidx], w["s"])
            t_fin[gidx] = w["e"] if t_fin[gidx] is None else max(t_fin[gidx], w["e"])
    # interpolar los que no casaron
    n = len(guion)
    conocidos = [i for i in range(n) if t_ini[i] is not None]
    for i in range(n):
        if t_ini[i] is None:
            prev = max([k for k in conocidos if k < i], default=None)
            nxt = min([k for k in conocidos if k > i], default=None)
            a = t_fin[prev] if prev is not None else 0.0
            b = t_ini[nxt] if nxt is not None else a + 0.6
            np_ = (nxt if nxt is not None else n) - (prev if prev is not None else -1)
            f = (i - (prev if prev is not None else -1)) / np_
            t_ini[i] = a + (b - a) * f
            t_fin[i] = t_ini[i] + max(0.12, (b - a) / np_)
            print("interpolada:", guion[i]["w"], round(t_ini[i], 2))
    sal = [{"w": g["w"], "s": round(t_ini[i], 3), "e": round(t_fin[i], 3), "escena": g["escena"],
            "nl": g["inicio_linea"]} for i, g in enumerate(guion)]
    json.dump(sal, open(os.path.join(AQUI, "palabras.json"), "w"), ensure_ascii=False, indent=0)
    print(len(sal), "palabras alineadas")


if __name__ == "__main__":
    main()
