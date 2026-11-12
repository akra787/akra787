import numpy as np, wave, os, subprocess
S=os.environ.get("TRABAJO", os.path.dirname(os.path.abspath(__file__))); SR=44100; DUR=4.3; n=int(SR*DUR)
v=np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",os.path.join(S,"intro_voz.wav"),"-ar",str(SR),"-ac","1","-f","s16le","-"],capture_output=True).stdout,np.int16)/32768
out=np.zeros(n); out[int(0.0*SR):int(0.0*SR)+len(v)]+=v[:n]*1.0
t=np.arange(n)/SR; rng=np.random.default_rng(1)
def boom(at,amp):
    tt=t-at; m=tt>=0; f=55*np.exp(-tt[m]*3)+38
    out[m]+=amp*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt[m]*3.5)
boom(0.0,0.45); boom(0.7,0.6)
# whoosh hacia el corte
w=rng.standard_normal(n); k=np.ones(40)/40; w=np.convolve(w,k,'same')
env=np.clip((t-3.3)/0.9,0,1)**2*(t<4.25); out+=w*env*0.35
# dron grave suave
out+=0.05*np.sin(2*np.pi*73.4*t)*np.clip(t/0.5,0,1)*np.clip((DUR-t)/0.4,0,1)
out=out/max(1,np.abs(out).max()/0.95)
with wave.open(os.path.join(S,"intro_audio.wav"),"wb") as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes((out*32767).astype(np.int16).tobytes())
