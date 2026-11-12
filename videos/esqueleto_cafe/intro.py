import subprocess, numpy as np, os, sys, wave
from PIL import Image, ImageDraw, ImageFont, ImageFilter
S=os.environ.get("TRABAJO", os.path.dirname(os.path.abspath(__file__))); F=sys.argv[1]; OUT=sys.argv[2]
W,H,FPS=1080,1920,30; DUR=4.3; N=int(DUR*FPS)
GOLD=(241,194,90); B="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# fondo: clip dramático del propio vídeo (meses después)
raw=subprocess.run(["ffmpeg","-v","error","-ss","47.5","-t",str(DUR+0.1),"-i",F,"-vf","fps=30,crop=720:1280:180:290,scale=1080:1920:flags=lanczos,gblur=sigma=2","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
fr=np.frombuffer(raw,np.uint8).reshape(-1,H,W,3)
# viñeta
yy,xx=np.mgrid[0:H,0:W]; d=np.sqrt(((xx-W/2)/(W/2))**2+((yy-H*0.45)/(H/2))**2)
vig=np.clip(1-0.55*d**1.6,0.15,1)[...,None]
subs=[(0.20,1.55,"¿Qué le pasaría a tu cuerpo"),(1.55,2.75,"si tomas café todos los días,"),(2.75,3.95,"durante treinta días?")]
def font(s): return ImageFont.truetype(B,s)
def ease(t): t=min(max(t,0),1); return 1-(1-t)**3
def pop(t):  # escala con rebote
    t=min(max(t,0),1); return 1+0.25*np.sin(t*np.pi)*(1-t) if t<1 else 1
def txt(img,text,f,cx,cy,color,scale=1,alpha=1,stroke=6):
    if alpha<=0: return
    tmp=Image.new("RGBA",(W,400),(0,0,0,0)); d=ImageDraw.Draw(tmp)
    d.text((W/2,200),text,font=f,fill=color+(255,),anchor="mm",stroke_width=stroke,stroke_fill=(0,0,0,255))
    if scale!=1: tmp=tmp.resize((int(W*scale),int(400*scale)),Image.LANCZOS)
    if alpha<1: tmp.putalpha(tmp.getchannel("A").point(lambda v:int(v*alpha)))
    img.alpha_composite(tmp,(int(cx-tmp.width/2),int(cy-tmp.height/2)))
pipe=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r","30","-i","-",
     "-i",os.path.join(S,"intro_audio.wav"),"-c:v","libx264","-pix_fmt","yuv420p","-preset","medium","-crf","18",
     "-c:a","aac","-b:a","192k","-ar","44100","-ac","1","-shortest",OUT],stdin=subprocess.PIPE)
for i in range(N):
    t=i/FPS
    base=fr[min(i,len(fr)-1)].astype(np.float32)
    z=1.0+0.10*t/DUR
    im=Image.fromarray(base.astype(np.uint8)).resize((int(W*z),int(H*z)),Image.BILINEAR)
    l=(im.width-W)//2; tp=(im.height-H)//2; im=im.crop((l,tp,l+W,tp+H))
    a=np.asarray(im,np.float32)*vig*0.62
    # sacudida al aparecer "30 DÍAS"
    img=Image.fromarray(a.astype(np.uint8)).convert("RGBA")
    if 0.7<t<0.95:
        k=int(14*np.sin((t-0.7)*90)); img=img.transform(img.size,Image.AFFINE,(1,0,k,0,1,0))
    # titular
    txt(img,"¿QUÉ PASARÍA",font(92),W/2,430,(255,255,255),pop((t-0.0)/0.35),ease(t/0.2),7)
    txt(img,"SI TOMAS CAFÉ",font(92),W/2,545,(255,255,255),pop((t-0.25)/0.35),ease((t-0.25)/0.2),7)
    txt(img,"30 DÍAS?",font(190),W/2,740,GOLD,pop((t-0.7)/0.4)*(1+0.03*np.sin(t*6)),ease((t-0.7)/0.15),9)
    d=ImageDraw.Draw(img); lw=int(260*ease((t-1.0)/0.4))
    if lw>0: d.rectangle((W/2-lw,862,W/2+lw,870),fill=GOLD+(255,))
    for a0,a1,s in subs:
        if a0<=t<a1: txt(img,s,font(46),W/2,1686,(255,255,255),1,1,5)
    # fundido a negro al final (el original empieza en negro)
    fo=max(0,(t-(DUR-0.35))/0.35)
    out=np.asarray(img.convert("RGB"),np.float32)*(1-fo)
    pipe.stdin.write(out.astype(np.uint8).tobytes())
pipe.stdin.close(); pipe.wait()
