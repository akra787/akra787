#!/usr/bin/env python3
"""Cambia solo la voz de un vídeo: misma imagen, nueva locución con Piper.

Uso: python3 video/herramientas/doblar.py entrada.mp4 lineas.json salida.mp4

lineas.json: {"voz_modelo": "es_ES-davefx-medium", "voz_hablante": 0, "voz_efecto": "ia", "musica": "tranquila", "volumen_musica": 0.35,
              "lineas": [{"inicio": 0.5, "fin": 1.75, "texto": "Este es Pablo."}, ...]}
Cada frase se ajusta (velocidad) para que ocupe su hueco [inicio, fin] del vídeo original.
"""
import json, os, re, subprocess, sys, tempfile, wave
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from make_video import SR, VOZ_EFECTOS, music, piper_model, read_wav, write_wav, DEFAULT_PIPER


MAX_SCALE = 1.4  # como mucho un 40 % más lento que lo normal


def piper(text, model, scale, out, speaker=None):
    cmd = [sys.executable, "-m", "piper", "-m", model, "-f", out, "--length-scale", f"{scale:.3f}", "--sentence-silence", "0"]
    if speaker is not None:
        cmd += ["-s", str(speaker)]
    subprocess.run(cmd, input=text.encode(), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    a = read_wav(out)
    nz = np.where(np.abs(a) > 0.01)[0]  # recorta silencios al principio y al final
    return a[nz[0]:nz[-1] + 1] if len(nz) else a


def main(src, spec_path, dst):
    spec = json.load(open(spec_path, encoding="utf-8"))
    model = piper_model(spec.get("voz_modelo", DEFAULT_PIPER))
    if not model:
        raise SystemExit("No hay voz Piper instalada: ejecuta video/instalar.sh")
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", src]).decode())
    out = np.zeros(int(dur * SR) + SR)
    tmp = tempfile.mkdtemp()
    for i, l in enumerate(spec["lineas"]):
        slot = l["fin"] - l["inicio"]
        # trocea por signos de puntuación para meter pausas naturales entre trozos
        chunks = [c.strip() for c in re.split(r"(?<=[,.;:?!…])\s+", l["texto"]) if c.strip()]
        scale = 1.0
        for _ in range(4):
            parts = [piper(c, model, scale, os.path.join(tmp, f"{i}_{k}.wav"), spec.get("voz_hablante")) for k, c in enumerate(chunks)]
            speech = sum(len(a) for a in parts) / SR
            gaps = len(parts) - 1
            target = slot - min(0.45, 0.6 * gaps) * gaps  # tiempo de habla deseado
            ratio = speech / max(target, 0.3)
            if 0.93 <= ratio <= 1.03 or (ratio < 0.93 and scale >= MAX_SCALE):
                break
            scale = max(0.6, min(MAX_SCALE, scale / ratio))
        gap = max(0.12, (slot - speech) / gaps) if gaps else 0
        gap = min(gap, 0.8)
        a = np.concatenate(sum(([p, np.zeros(int(gap * SR))] for p in parts), [])[:-1] or [np.zeros(1)])
        if len(a) / SR > slot + 0.3:
            print(f"  aviso: la frase {i + 1} dura {len(a)/SR:.2f}s para un hueco de {slot:.2f}s")
        s0 = int(l["inicio"] * SR)
        out[s0:s0 + len(a)] += a[: len(out) - s0]
        print(f"  {l['inicio']:5.2f}s  vel x{1/scale:.2f}  {len(a)/SR:.2f}s/{slot:.2f}s  {l['texto']}")
    out = out[: int(dur * SR)]
    if spec.get("voz_efecto"):  # p. ej. "ia": más presencia y volumen, estilo vídeos de IA
        vin, vout = os.path.join(tmp, "voz.wav"), os.path.join(tmp, "voz_fx.wav")
        write_wav(vin, out / max(1.0, np.abs(out).max()))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vin, "-af",
                        VOZ_EFECTOS.get(spec["voz_efecto"], spec["voz_efecto"]), "-ac", "1", "-ar", str(SR), vout], check=True)
        v = read_wav(vout)
        out = np.zeros(len(out)); out[: min(len(v), len(out))] = v[: len(out)]
    if spec.get("musica", "tranquila") not in (None, False, "no"):
        m = music(dur, spec.get("musica", "tranquila"))
        out[: len(m)] += m[: len(out)] * spec.get("volumen_musica", 0.35)
    out = out / max(1.0, np.abs(out).max() / 0.9)
    awav = os.path.join(tmp, "audio.wav")
    write_wav(awav, out)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", awav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst],
                   check=True)
    print("Vídeo listo:", dst)


if __name__ == "__main__":
    main(*sys.argv[1:4])
