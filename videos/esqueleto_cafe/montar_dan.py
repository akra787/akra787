"""Monta la voz de ElevenLabs (un solo MP3 con todas las frases) sobre el vídeo del esqueleto."""
import json, subprocess, sys, os, numpy as np
sys.path.insert(0, "/home/user/akra787/video")
from make_video import SR, music, read_wav, write_wav
D = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open("/home/user/akra787/videos/esqueleto_cafe/doblaje_dan.json"))
W = json.load(open(f"{D}/dan/words.json"))
dan = read_wav(f"{D}/dan/dan.wav")
ORIG = "/root/.claude/uploads/c7e159d6-421a-5d83-9bff-eafdc3fad062/84ae2e63-esqueleto_cafe.mp4"
# trozos con voz (envolvente 10 ms)
h = 441; r = np.array([np.sqrt((dan[i:i+h]**2).mean()) for i in range(0, len(dan), h)]); on = r > 0.01
def cut_points(t0, t1):
    """inicio/fin reales de la voz entre t0 y t1 (s), según la envolvente."""
    i0, i1 = int(t0*100), min(int(t1*100), len(on))
    idx = np.where(on[i0:i1])[0]
    return (i0+idx[0])/100 - 0.03, (i0+idx[-1])/100 + 0.06
DUR = 4.3 + 74.7
out = np.zeros(int(DUR*SR) + SR)
tmp = f"{D}/dan/tmp.wav"; tmp2 = f"{D}/dan/tmp2.wav"
L = spec["lineas"]
# frase de cada palabra
wline = []
for i, l in enumerate(L): wline += [i]*len(l["texto"].split())
# trozos de voz separados por pausas >= 0.25 s
segs = []; st = None
for j, v in enumerate(on):
    if v and st is None: st = j
    if not v and st is not None: segs.append([st, j]); st = None
if st is not None: segs.append([st, len(on)])
mg = []
for a, b in segs:
    if mg and a - mg[-1][1] < 25: mg[-1][1] = b
    else: mg.append([a, b])
mg = [x for x in mg if x[1]-x[0] > 8]
lines = {}
for a, b in mg:
    t0 = a/100; j = min(range(len(W)), key=lambda q: abs(W[q][0]-t0))
    li = wline[j]; lines.setdefault(li, [a/100, b/100]); lines[li][1] = b/100
for i, l in enumerate(L):
    a0, a1 = lines[i]; a0 -= 0.03; a1 += 0.06
    seg = dan[int(a0*SR):int(a1*SR)]
    slot = l["fin"] - l["inicio"]
    sp = 1.1 if i == 0 else min(1.25, max(1.0, len(seg)/SR/slot))
    if sp > 1.0:
        write_wav(tmp, seg)
        subprocess.run(["ffmpeg","-y","-v","error","-i",tmp,"-af",f"atempo={sp:.3f}",tmp2],check=True)
        seg = read_wav(tmp2)
    st = 0.1 if i == 0 else l["inicio"]
    s0 = int(st*SR); out[s0:s0+len(seg)] += seg
    print(f"{st:6.2f}s x{sp:.2f} {len(seg)/SR:.2f}/{slot:.2f}  {l['texto']}")
out = out[:int(DUR*SR)]
# música suave
m = music(DUR, "tranquila"); out[:len(m)] += m[:len(out)] * 0.3
# efectos de la intro
sfx = read_wav(f"{D}/intro_sfx.wav"); out[:len(sfx)] += sfx * 0.8
# efectos originales: caída de la taza hasta el final de esa parte
subprocess.run(["ffmpeg","-y","-v","error","-i",ORIG,"-vn","-ac","1","-ar",str(SR),f"{D}/dan/orig.wav"],check=True)
orig = read_wav(f"{D}/dan/orig.wav")
for a0, a1 in [(58.6, 68.35)]:
    s, e = int((a0+4.3)*SR), int((a1+4.3)*SR); o0 = int(a0*SR)
    f = int(0.15*SR); fade = np.ones(e-s); fade[:f] = np.linspace(0,1,f); fade[-f:] = np.linspace(1,0,f)
    out[s:e] = out[s:e]*(1-fade) + orig[o0:o0+e-s]*fade
out = out / max(1.0, np.abs(out).max()/0.92)
write_wav(f"{D}/dan/audio_final.wav", out)
