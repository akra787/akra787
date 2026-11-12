#!/usr/bin/env python3
"""Generador de vídeos a partir de un guion JSON.

Uso:
    python3 video/make_video.py guion.json [-o salida.mp4]

Todo funciona sin conexión: Pillow + numpy dibujan los fotogramas,
espeak-ng pone la voz, numpy genera la música y ffmpeg monta el MP4.
Ver video/README.md para el formato del guion.
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FORMATS = {"vertical": (1080, 1920), "horizontal": (1920, 1080), "cuadrado": (1080, 1080)}
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation"]
SR = 44100


# ---------------------------------------------------------------- utilidades
def font(size, bold=True):
    names = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def gradient(w, h, c1, c2, angle=90):
    c1, c2 = np.array(hex_rgb(c1), float), np.array(hex_rgb(c2), float)
    y, x = np.mgrid[0:h, 0:w]
    a = math.radians(angle)
    t = (x * math.cos(a) + y * math.sin(a))
    t = (t - t.min()) / (t.max() - t.min() + 1e-9)
    arr = c1 + (c2 - c1) * t[..., None]
    return Image.fromarray(arr.astype(np.uint8))


def wrap(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            test = (cur + " " + word).strip()
            if draw.textlength(test, font=fnt) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def cover(img, w, h):
    """Escala y recorta una imagen para cubrir w x h."""
    s = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def ease(t):
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- audio
PIPER_DIR = os.environ.get("PIPER_VOCES", "/opt/piper-voces")
DEFAULT_PIPER = "es_ES-davefx-medium"


def piper_model(name):
    if not name or name in ("espeak", "robot"):
        return None
    p = name if name.endswith(".onnx") else os.path.join(PIPER_DIR, name + ".onnx")
    return p if os.path.exists(p) and os.path.exists(p + ".json") else None


def tts(text, lang, voice_speed, out_wav, voice=DEFAULT_PIPER):
    """Voz sin conexión: Piper (realista) si el modelo está instalado, si no espeak-ng.
    Devuelve duración en segundos."""
    if not text.strip():
        return 0.0
    model = piper_model(voice)
    if model:
        # length_scale > 1 = más lento; 150 ppm es la velocidad normal
        scale = max(0.5, min(2.0, 150 / max(voice_speed, 1)))
        subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", out_wav, "--length-scale", f"{scale:.2f}"],
                       input=text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            return 0.0
        subprocess.run([exe, "-v", lang, "-s", str(voice_speed), "-w", out_wav, text], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(out_wav) as w:
        return w.getnframes() / w.getframerate()


def music(duration, mood, seed=7):
    """Música de fondo sencilla generada con numpy (acordes + arpegio)."""
    rng = random.Random(seed)
    prog = {
        "alegre": [[60, 64, 67], [67, 71, 74], [69, 72, 76], [65, 69, 72]],
        "epica": [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
        "tranquila": [[62, 65, 69], [58, 62, 65], [60, 64, 67], [57, 60, 64]],
    }.get(mood, None) or [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]]
    bpm = {"alegre": 112, "epica": 80, "tranquila": 70}.get(mood, 90)
    beat = 60 / bpm
    bar = beat * 4
    n = int(duration * SR)
    out = np.zeros(n)
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    t_bar = np.arange(int(bar * SR)) / SR
    env_pad = np.minimum(1, t_bar / 0.4) * np.minimum(1, (bar - t_bar) / 0.4)
    i = 0
    pos = 0
    while pos < n:
        chord = prog[i % len(prog)]
        seg = sum(np.sin(2 * np.pi * f(m) * t_bar) + 0.3 * np.sin(2 * np.pi * f(m) * 2 * t_bar) for m in chord) * env_pad * 0.06
        seg += np.sin(2 * np.pi * f(chord[0] - 12) * t_bar) * env_pad * 0.08
        # arpegio en corcheas
        step = int(beat / 2 * SR)
        tt = np.arange(step) / SR
        for k in range(8):
            m = chord[rng.choice([0, 1, 2])] + 12
            note = np.sin(2 * np.pi * f(m) * tt) * np.exp(-tt * 6) * 0.07
            s = k * step
            seg[s:s + step] += note[: max(0, min(step, len(seg) - s))]
        e = min(n, pos + len(seg))
        out[pos:e] += seg[: e - pos]
        pos += len(seg)
        i += 1
    fade = int(min(2, duration / 4) * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def read_wav(path):
    with wave.open(path) as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        idx = np.arange(0, len(data), sr / SR)
        data = np.interp(idx, np.arange(len(data)), data)
    return data


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- escenas
class Scene:
    def __init__(self, spec, size, base_dir, defaults):
        self.s = {**defaults, **spec}
        self.w, self.h = size
        self.base_dir = base_dir
        self.bg = self._background()
        self.particles = [(random.random(), random.random(), random.uniform(2, 7), random.uniform(0.02, 0.08))
                          for _ in range(40)] if self.s.get("particulas", True) else []

    def _background(self):
        s, w, h = self.s, self.w, self.h
        pad = 1.15  # margen para el efecto Ken Burns
        W, H = int(w * pad), int(h * pad)
        if s.get("imagen"):
            p = s["imagen"] if os.path.isabs(s["imagen"]) else os.path.join(self.base_dir, s["imagen"])
            img = cover(Image.open(p).convert("RGB"), W, H)
            dark = s.get("oscurecer", 0.35)
            if dark:
                img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), dark)
            return img
        cols = s.get("fondo", ["#1e3c72", "#2a5298"])
        if isinstance(cols, str):
            cols = [cols, cols]
        return gradient(W, H, cols[0], cols[1], s.get("angulo", 90))

    def frame(self, t, dur):
        s, w, h = self.s, self.w, self.h
        p = t / max(dur, 1e-6)
        # Ken Burns: zoom suave y desplazamiento
        z = 1 + 0.12 * ease(p) if s.get("zoom", "in") == "in" else 1.12 - 0.12 * ease(p)
        cw, ch = int(w * 1.15 / z), int(h * 1.15 / z)
        cw, ch = max(cw, w), max(ch, h)
        ox = (self.bg.width - cw) * (0.5 + 0.3 * (p - 0.5) * (1 if s.get("pan", "derecha") == "derecha" else -1))
        oy = (self.bg.height - ch) / 2
        img = self.bg.crop((int(ox), int(oy), int(ox) + cw, int(oy) + ch)).resize((w, h), Image.BILINEAR)
        d = ImageDraw.Draw(img, "RGBA")

        for (px, py, r, sp) in self.particles:
            y = (py - t * sp) % 1.0
            x = px + 0.01 * math.sin(t + py * 10)
            d.ellipse([x * w - r, y * h - r, x * w + r, y * h + r], fill=(255, 255, 255, 70))

        appear = ease(min(1, t / 0.6))
        accent = hex_rgb(s.get("acento", "#ffcc00"))
        color = hex_rgb(s.get("color_texto", "#ffffff"))
        unit = min(w, h)
        y = h * s.get("posicion_y", 0.38)

        if s.get("titulo"):
            f = font(int(unit * s.get("tam_titulo", 0.085)))
            lines = wrap(d, s["titulo"], f, w * 0.86)
            lh = f.size * 1.18
            total = lh * len(lines)
            y0 = y - total / 2 + (1 - appear) * 60
            for i, line in enumerate(lines):
                tw = d.textlength(line, font=f)
                x = (w - tw) / 2
                a = int(255 * appear)
                d.text((x + 4, y0 + i * lh + 4), line, font=f, fill=(0, 0, 0, int(a * 0.6)))
                d.text((x, y0 + i * lh), line, font=f, fill=color + (a,))
            bar_w = w * 0.25 * ease(min(1, max(0, (t - 0.3) / 0.6)))
            by = y0 + total + 20
            d.rounded_rectangle([(w - bar_w) / 2, by, (w + bar_w) / 2, by + 10], 5, fill=accent + (255,))
            y = by + 60

        if s.get("texto"):
            a2 = ease(min(1, max(0, (t - 0.4) / 0.6)))
            f = font(int(unit * s.get("tam_texto", 0.05)), bold=False)
            lines = wrap(d, s["texto"], f, w * 0.82)
            lh = f.size * 1.3
            for i, line in enumerate(lines):
                tw = d.textlength(line, font=f)
                d.text(((w - tw) / 2 + 3, y + i * lh + 3), line, font=f, fill=(0, 0, 0, int(150 * a2)))
                d.text(((w - tw) / 2, y + i * lh), line, font=f, fill=color + (int(255 * a2),))

        if s.get("subtitulos", True) and s.get("voz"):
            f = font(int(unit * 0.04))
            words = s["voz"].split()
            # muestra un bloque de palabras sincronizado aprox. con la locución
            speak = s.get("_voice_dur") or dur
            chunk = 6
            nblocks = max(1, math.ceil(len(words) / chunk))
            bi = min(nblocks - 1, int(t / max(speak, 1e-6) * nblocks))
            if t <= speak + 0.3:
                text = " ".join(words[bi * chunk:(bi + 1) * chunk])
                lines = wrap(d, text, f, w * 0.85)
                lh = f.size * 1.25
                yb = h * 0.82 - lh * len(lines) / 2
                for i, line in enumerate(lines):
                    tw = d.textlength(line, font=f)
                    x0 = (w - tw) / 2
                    d.rounded_rectangle([x0 - 18, yb + i * lh - 8, x0 + tw + 18, yb + i * lh + f.size + 14], 12,
                                        fill=(0, 0, 0, 160))
                    d.text((x0, yb + i * lh), line, font=f, fill=(255, 255, 255, 255))

        if s.get("marca"):
            f = font(int(unit * 0.03))
            d.text((40, 40), s["marca"], font=f, fill=(255, 255, 255, 180))
        return img


# ---------------------------------------------------------------- montaje
def build(script_path, out_path=None):
    with open(script_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    base_dir = os.path.dirname(os.path.abspath(script_path))
    size = FORMATS.get(spec.get("formato", "vertical"), FORMATS["vertical"])
    if "resolucion" in spec:
        size = tuple(spec["resolucion"])
    fps = spec.get("fps", 30)
    lang = spec.get("idioma", "es")
    speed = spec.get("velocidad_voz", 150)
    voice_model = spec.get("voz_modelo", DEFAULT_PIPER)
    trans = spec.get("transicion", 0.5)
    if not out_path:
        out_path = spec.get("salida") or os.path.splitext(os.path.basename(script_path))[0] + ".mp4"
        if not os.path.isabs(out_path):  # relativo al JSON del guion
            out_path = os.path.join(base_dir, out_path)
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    random.seed(spec.get("semilla", 1))

    defaults = {k: spec[k] for k in ("fondo", "acento", "color_texto", "marca", "subtitulos", "particulas") if k in spec}
    tmp = tempfile.mkdtemp(prefix="vid_")
    try:
        scenes, durs, voice = [], [], np.zeros(0)
        for i, sc in enumerate(spec["escenas"]):
            vdur = 0.0
            if sc.get("voz"):
                wav = os.path.join(tmp, f"v{i}.wav")
                vdur = tts(sc["voz"], sc.get("idioma", lang), sc.get("velocidad_voz", speed), wav,
                           sc.get("voz_modelo", voice_model))
            dur = sc.get("duracion") or max(3.0, vdur + 0.8)
            sc = {**sc, "_voice_dur": vdur}
            scenes.append(Scene(sc, size, base_dir, defaults))
            durs.append(dur)
            seg = np.zeros(int(dur * SR))
            if vdur:
                v = read_wav(os.path.join(tmp, f"v{i}.wav"))[: len(seg) - int(0.2 * SR)]
                seg[int(0.2 * SR):int(0.2 * SR) + len(v)] = v
            voice = np.concatenate([voice, seg])
        total = sum(durs)

        audio = np.zeros(int(total * SR) + SR)
        audio[: len(voice)] += voice * spec.get("volumen_voz", 1.0)
        if spec.get("musica_archivo"):
            mp = os.path.join(base_dir, spec["musica_archivo"])
            mwav = os.path.join(tmp, "m.wav")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp, "-ac", "1", "-ar", str(SR), mwav], check=True)
            m = read_wav(mwav)
            m = np.tile(m, math.ceil(len(audio) / max(len(m), 1)))[: len(audio)]
            audio += m * spec.get("volumen_musica", 0.25)
        elif spec.get("musica", "alegre") not in (None, False, "no", "ninguna"):
            m = music(total + 1, spec.get("musica", "alegre"))
            audio[: len(m)] += m * spec.get("volumen_musica", 1.0) * (0.6 if voice.any() else 1.0)
        audio = audio[: int(total * SR)]
        peak = np.abs(audio).max() or 1
        audio = audio / peak * 0.9 if peak > 0.9 else audio
        awav = os.path.join(tmp, "audio.wav")
        write_wav(awav, audio)

        w, h = size
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
               "-r", str(fps), "-i", "-", "-i", awav, "-c:v", "libx264", "-preset", spec.get("preset", "medium"),
               "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", out_path]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        starts = np.cumsum([0] + durs[:-1])
        nframes = int(total * fps)
        for fi in range(nframes):
            t = fi / fps
            i = int(np.searchsorted(starts, t, side="right") - 1)
            lt = t - starts[i]
            img = scenes[i].frame(lt, durs[i])
            # fundido cruzado con la siguiente escena
            if trans and i + 1 < len(scenes) and lt > durs[i] - trans:
                a = ease((lt - (durs[i] - trans)) / trans)
                nxt = scenes[i + 1].frame(0, durs[i + 1])
                img = Image.blend(img, nxt, a)
            # fundido de entrada / salida del vídeo
            if t < 0.5 or t > total - 0.7:
                k = min(t / 0.5, (total - t) / 0.7, 1)
                img = Image.blend(Image.new("RGB", img.size), img, max(0, k))
            ff.stdin.write(img.tobytes())
            if fi % (fps * 5) == 0:
                print(f"  {t:5.1f}s / {total:.1f}s", file=sys.stderr)
        ff.stdin.close()
        if ff.wait() != 0:
            raise SystemExit("ffmpeg falló")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Vídeo listo: {out_path} ({total:.1f}s, {w}x{h})")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("guion", help="archivo JSON con el guion")
    ap.add_argument("-o", "--salida", help="ruta del MP4 de salida")
    a = ap.parse_args()
    build(a.guion, a.salida)
