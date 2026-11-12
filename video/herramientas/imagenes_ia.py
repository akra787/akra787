"""Genera fotos realistas en local (sin GPU) con SD-Turbo, ~20-30 s por imagen.

Requiere: pip install torch diffusers transformers accelerate  (el modelo se baja de huggingface.co)
Uso:  HF_HUB_DISABLE_XET=1 python3 video/herramientas/imagenes_ia.py prompts.txt carpeta_salida [semilla]
prompts.txt: una línea por imagen, "nombre|prompt en inglés".
Se genera a 448x768 (vertical): en tamaños más altos el modelo duplica objetos.
"""
import os
import sys
import time

import torch
from diffusers import AutoPipelineForText2Image
from PIL import Image, ImageEnhance, ImageFilter

prompts, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 21
os.makedirs(out, exist_ok=True)
torch.set_num_threads(os.cpu_count() or 4)
pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=torch.float32)
pipe.set_progress_bar_config(disable=True)
for line in open(prompts, encoding="utf-8"):
    if "|" not in line:
        continue
    name, prompt = (x.strip() for x in line.split("|", 1))
    t = time.time()
    im = pipe(prompt, num_inference_steps=2, guidance_scale=0.0, width=448, height=768,
              generator=torch.Generator().manual_seed(seed)).images[0]
    # a tamaño de vídeo vertical (+15 % para el efecto Ken Burns), con algo de nitidez
    im = im.resize((1242, 2208), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=3, percent=80, threshold=2))
    ImageEnhance.Contrast(im).enhance(1.06).save(os.path.join(out, name + ".jpg"), quality=88)
    print(f"{name}: {time.time() - t:.0f} s", flush=True)
