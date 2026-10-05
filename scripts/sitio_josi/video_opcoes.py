"""Vídeo alternando as duas opções de divisão da gleba (Sítio Josi), só a viewport.

  python3 video_opcoes.py OPÇÃO_01.pdf OPÇÃO_02.pdf saida.mp4

Recorta o quadro da viewport de cada PDF (Civil 3D, A1 paisagem), sem o carimbo,
e alterna 01 -> 02 -> 01 ... com fusão suave. Requer pymupdf, pillow, imageio-ffmpeg.
"""
import sys, subprocess, numpy as np, pymupdf, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

PDF1, PDF2, OUT = sys.argv[1:4]
# quadro da viewport em pontos (página exibida 1684 x 1191), com 1,5 pt para tirar a moldura
X0, Y0, X1, Y1 = 72.7, 21.3, 1166.6, 1169.2
H = 1600; W = int(round(H * (X1 - X0) / (Y1 - Y0) / 2)) * 2
FPS, HOLD, FADE, CICLOS = 30, 3.0, 1.0, 2


def viewport(pdf):
    p = pymupdf.open(pdf)[0]; z = 4.0
    pix = p.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    return im.crop((int(X0 * z), int(Y0 * z), int(X1 * z), int(Y1 * z))).resize((W, H), Image.LANCZOS)


def rotulo(im, txt):
    im = im.copy(); d = ImageDraw.Draw(im)
    f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 44)
    tw = d.textlength(txt, font=f); x, y = W - tw - 60, 40
    d.rounded_rectangle((x - 22, y - 14, x + tw + 22, y + 62), radius=12, fill=(40, 44, 52))
    d.text((x, y), txt, font=f, fill=(255, 255, 255))
    return np.asarray(im, dtype=np.float32)


A = rotulo(viewport(PDF1), 'OPÇÃO 01'); B = rotulo(viewport(PDF2), 'OPÇÃO 02')
cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
       '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT]
pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)


def put(fr):
    pr.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())


seq = [A, B] * CICLOS + [A]
for k, (a, b) in enumerate(zip(seq[:-1], seq[1:])):
    for _ in range(int(HOLD * FPS)):
        put(a)
    for i in range(int(FADE * FPS)):
        t = (i + 1) / (FADE * FPS); t = t * t * (3 - 2 * t)
        put(a * (1 - t) + b * t)
for _ in range(int(HOLD * FPS)):
    put(seq[-1])
pr.stdin.close(); pr.wait()
print('ok', OUT, W, H)
