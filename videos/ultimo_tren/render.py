#!/usr/bin/env python3
"""Renderiza «El último tren de la noche».

Uso:
  python3 render.py                      # vídeo completo -> ../ultimo_tren.mp4
  python3 render.py --muestras 3,40,95   # PNG de esos segundos en ./muestras/
  python3 render.py --desde 100 --hasta 130 --salida prueba.mp4
"""
import argparse
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor import AQUI, FPS, H, W, a_numpy, a_superficie, cl, fbm1, posproceso, superficie  # noqa: E402
import planos as PL  # noqa: E402


def plano_en(T):
    for k, p in enumerate(PL.PLANOS_T):
        if p["t0"] <= T < p["t1"]:
            return k
    return len(PL.PLANOS_T) - 1


def dibujar_plano(k, T):
    p = PL.PLANOS_T[k]
    t, d = T - p["t0"], p["t1"] - p["t0"]
    s, c = superficie()
    fx = p["fn"](c, t, T, d, **p["kw"]) or {}
    return s, dict(fx), t, d


def fotograma(i):
    T = i / FPS
    k = plano_en(T)
    s, fx, t, d = dibujar_plano(k, T)
    p = PL.PLANOS_T[k]
    # transiciones
    negro = fx.get("negro", 0.0)
    if p["op"].get("trans") == "negro" and k > 0:
        negro = max(negro, 1 - cl(t / 0.55))
    if k + 1 < len(PL.PLANOS_T) and PL.PLANOS_T[k + 1]["op"].get("trans") == "negro":
        negro = max(negro, cl((t - (d - 0.4)) / 0.4))
    if k == 0:
        negro = max(negro, 1 - cl(t / 1.0))
    if T > PL.DURACION - 1.5:
        negro = max(negro, cl((T - (PL.DURACION - 1.5)) / 1.4))
    fx["negro"] = negro
    arr = a_numpy(s)
    arr = posproceso(arr, T, i, fx)
    # temblor de cámara
    sac = fx.get("sacudida", 0)
    if sac:
        amp = sac * max(0.2, 1 - t / 1.4)
        dx = int(fbm1(T * 9, 1.0) * amp)
        dy = int(fbm1(T * 9, 2.0) * amp)
        arr = np.roll(np.roll(arr, dx, axis=1), dy, axis=0)
    s2 = a_superficie(np.clip(arr, 0, 1))
    import cairo
    c2 = cairo.Context(s2)
    PL.subtitulos(c2, T)
    s2.flush()
    buf = np.ndarray((H, W, 4), np.uint8, s2.get_data())
    return buf[..., [2, 1, 0]].tobytes()


def una(T):
    i = int(T * FPS)
    raw = fotograma(i)
    ruta = os.path.join(AQUI, "muestras", f"m_{T:07.2f}.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                    "-i", "-", ruta], input=raw, check=True)
    return ruta


def trozo(args):
    i0, i1, ruta = args
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", ruta], stdin=subprocess.PIPE)
    for i in range(i0, i1):
        ff.stdin.write(fotograma(i))
        if (i - i0) % 240 == 0:
            print(f"  {ruta}: {i - i0}/{i1 - i0}", flush=True)
    ff.stdin.close()
    ff.wait()
    return ruta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestras")
    ap.add_argument("--desde", type=float, default=0.0)
    ap.add_argument("--hasta", type=float)
    ap.add_argument("--salida", default=os.path.join(AQUI, "..", "ultimo_tren.mp4"))
    ap.add_argument("--procesos", type=int, default=4)
    ap.add_argument("--sin-audio", action="store_true")
    a = ap.parse_args()
    if a.muestras:
        os.makedirs(os.path.join(AQUI, "muestras"), exist_ok=True)
        tiempos = [float(x) for x in a.muestras.split(",")]

        with Pool(a.procesos) as pool:
            for r in pool.map(una, tiempos):
                print(r)
        return
    hasta = a.hasta if a.hasta is not None else PL.DURACION
    i0, i1 = int(a.desde * FPS), int(hasta * FPS)
    n = a.procesos
    tmp = os.path.join(AQUI, "_trozos")
    os.makedirs(tmp, exist_ok=True)
    cortes = [i0 + (i1 - i0) * k // n for k in range(n + 1)]
    tareas = [(cortes[k], cortes[k + 1], os.path.join(tmp, f"t{k:02d}.mp4")) for k in range(n)]
    print(f"Renderizando {i1 - i0} fotogramas ({(i1 - i0) / FPS:.1f} s) en {n} procesos…")
    with Pool(n) as pool:
        rutas = pool.map(trozo, tareas)
    lista = os.path.join(tmp, "lista.txt")
    with open(lista, "w") as f:
        for r in rutas:
            f.write(f"file '{r}'\n")
    video = os.path.join(tmp, "video.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", video],
                   check=True)
    audio = os.path.join(AQUI, "mezcla.wav")
    if a.sin_audio or not os.path.exists(audio):
        os.replace(video, a.salida)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-ss", str(a.desde), "-t", str(hasta - a.desde),
                        "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", a.salida], check=True)
    print("Listo:", a.salida)


if __name__ == "__main__":
    main()
