#!/usr/bin/env python3
"""Cambia solo la voz de un vídeo usando una voz de ElevenLabs (misma imagen, nueva locución).

Uso: python3 video/herramientas/doblar_elevenlabs.py entrada.mp4 lineas.json salida.mp4

lineas.json: {"voz_elevenlabs": "Dan",              # nombre (se busca en tus voces y en la biblioteca) o voice_id
              "idioma": "es", "modelo": "eleven_multilingual_v2",
              "musica": "tranquila", "volumen_musica": 0.3,
              "conservar_original": [[63.0, 72.6]],  # tramos del audio original que se mantienen (efectos)
              "lineas": [{"inicio": 0.5, "fin": 1.75, "texto": "Día uno."}, ...]}

La clave de la API la añade el proxy del entorno (cabecera xi-api-key); fuera de él usa ELEVENLABS_API_KEY.
Cada frase se acelera un poco si no cabe en su hueco [inicio, fin] (como mucho x1.25).
"""
import json, os, subprocess, sys, tempfile, urllib.parse, urllib.request
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from make_video import SR, music, read_wav, write_wav

API = "https://api.elevenlabs.io"


def api(path, body=None, raw=False):
    headers = {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "proxy-injected"), "Content-Type": "application/json"}
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if raw else json.loads(data)


def find_voice(name, lang):
    if len(name) >= 20 and " " not in name:
        return name, name
    for v in api("/v1/voices")["voices"]:
        if v["name"].lower().split(" ")[0] == name.lower():
            return v["voice_id"], v["name"]
    q = urllib.parse.urlencode({"search": name, "language": lang, "page_size": 30})
    for v in api(f"/v1/shared-voices?{q}")["voices"]:
        if v["name"].lower().split(" ")[0].strip("-–") == name.lower():
            # hay que añadirla a "Mis voces" para poder usarla
            api(f"/v1/voices/add/{v['public_owner_id']}/{v['voice_id']}", {"new_name": v["name"]})
            return v["voice_id"], v["name"]
    raise SystemExit(f"No encuentro la voz «{name}» en ElevenLabs")


def tts(text, voice_id, model, out, prev=None, nxt=None):
    body = {"text": text, "model_id": model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.2, "use_speaker_boost": True}}
    if prev: body["previous_text"] = prev
    if nxt: body["next_text"] = nxt
    mp3 = api(f"/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128", body, raw=True)
    open(out + ".mp3", "wb").write(mp3)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out + ".mp3", "-ac", "1", "-ar", str(SR), out], check=True)


def trim(a):
    nz = np.where(np.abs(a) > 0.01)[0]
    return a[max(0, nz[0] - 200):nz[-1] + 1] if len(nz) else a


def tempo(path, factor, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-af", f"atempo={factor:.3f}", out], check=True)
    return read_wav(out)


def main(src, spec_path, dst):
    spec = json.load(open(spec_path, encoding="utf-8"))
    voice_id, vname = find_voice(spec.get("voz_elevenlabs", "Dan"), spec.get("idioma", "es"))
    model = spec.get("modelo", "eleven_multilingual_v2")
    print(f"Voz: {vname} ({voice_id})")
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", src]).decode())
    out = np.zeros(int(dur * SR) + SR)
    tmp = tempfile.mkdtemp()
    lineas = spec["lineas"]
    for i, l in enumerate(lineas):
        slot = l["fin"] - l["inicio"]
        w = os.path.join(tmp, f"{i}.wav")
        tts(l["texto"], voice_id, model, w,
            lineas[i - 1]["texto"] if i else None, lineas[i + 1]["texto"] if i + 1 < len(lineas) else None)
        a = trim(read_wav(w))
        speed = 1.0
        if len(a) / SR > slot:
            speed = min(1.25, len(a) / SR / slot)
            write_wav(w, a)
            a = trim(tempo(w, speed, os.path.join(tmp, f"{i}_t.wav")))
        if len(a) / SR > slot + 0.3:
            print(f"  aviso: la frase {i + 1} dura {len(a)/SR:.2f}s para un hueco de {slot:.2f}s")
        s0 = int(l["inicio"] * SR)
        out[s0:s0 + len(a)] += a[: len(out) - s0]
        print(f"  {l['inicio']:5.2f}s  vel x{speed:.2f}  {len(a)/SR:.2f}s/{slot:.2f}s  {l['texto']}")
    out = out[: int(dur * SR)]
    if spec.get("musica", "tranquila") not in (None, False, "no"):
        m = music(dur, spec.get("musica", "tranquila"))
        out[: len(m)] += m[: len(out)] * spec.get("volumen_musica", 0.3)
    if spec.get("conservar_original"):
        ow = os.path.join(tmp, "orig.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), ow], check=True)
        orig = read_wav(ow)
        for a0, a1 in spec["conservar_original"]:
            s, e = int(a0 * SR), min(int(a1 * SR), len(out), len(orig))
            fade = np.ones(e - s); f = min(int(0.15 * SR), (e - s) // 2)
            fade[:f] = np.linspace(0, 1, f); fade[-f:] = np.linspace(1, 0, f)
            out[s:e] = out[s:e] * (1 - fade) + orig[s:e] * fade
    out = out / max(1.0, np.abs(out).max() / 0.9)
    awav = os.path.join(tmp, "audio.wav")
    write_wav(awav, out)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", awav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst],
                   check=True)
    print("Vídeo listo:", dst)


if __name__ == "__main__":
    main(*sys.argv[1:4])
