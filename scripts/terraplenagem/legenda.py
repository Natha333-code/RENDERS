"""Aplica título, legenda de corte/aterro e volumes sobre o render.

  python3 legenda.py render.png dem.npz saida.png
"""
import sys, json, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC, DEM, OUT = sys.argv[1:4]
vol = json.loads(str(np.load(DEM)['vol']))
im = Image.open(SRC).convert('RGBA')
W, H = im.size
k = W / 1920.0
F = '/usr/share/fonts/truetype/dejavu/'


def font(name, size):
    return ImageFont.truetype(F + name, int(size * k))


fB, fR, fS, fT = (font('DejaVuSans-Bold.ttf', 30), font('DejaVuSans.ttf', 19),
                  font('DejaVuSans.ttf', 16), font('DejaVuSans-Bold.ttf', 19))


def br(v):                      # 2207.3 -> "2.207"
    return f'{v:,.0f}'.replace(',', '.')


def panel(box, alpha=150, r=14):
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(box, radius=int(r * k), fill=(18, 20, 24, alpha))
    im.alpha_composite(lay)


def grad(d, x0, y0, w, h, stops):
    for i in range(int(w)):
        t = i / (w - 1)
        for (p0, c0), (p1, c1) in zip(stops[:-1], stops[1:]):
            if p0 <= t <= p1:
                u = (t - p0) / (p1 - p0)
                c = tuple(int(c0[j] + (c1[j] - c0[j]) * u) for j in range(3))
                break
        d.line([(x0 + i, y0), (x0 + i, y0 + h)], fill=c)


# ---------------- título (topo esquerdo)
m = int(28 * k)
panel((m, m, m + int(610 * k), m + int(98 * k)))
d = ImageDraw.Draw(im)
d.text((m + 22 * k, m + 14 * k), 'PLATO GERAL – RUA B', font=fB, fill=(255, 255, 255))
d.text((m + 22 * k, m + 56 * k), 'Terraplenagem · perspectiva a partir da Rua B', font=fR, fill=(215, 218, 222))

# ---------------- legenda (base esquerda)
pw, ph = int(700 * k), int(238 * k)
x0, y0 = m, H - m - ph
panel((x0, y0, x0 + pw, y0 + ph))
d = ImageDraw.Draw(im)
px, py = x0 + int(22 * k), y0 + int(18 * k)
bw, bh = int(250 * k), int(16 * k)
CUT = [(0, (238, 200, 128)), (0.35, (228, 122, 52)), (1, (160, 34, 26))]
FIL = [(0, (176, 214, 238)), (0.4, (78, 140, 216)), (1, (34, 62, 150))]
d.text((px, py), 'CORTE', font=fT, fill=(255, 255, 255))
d.text((px + bw + int(22 * k), py), 'ATERRO', font=fT, fill=(255, 255, 255))
gy = py + int(30 * k)
grad(d, px, gy, bw, bh, CUT)
grad(d, px + bw + int(22 * k), gy, bw, bh, FIL)
ty = gy + bh + int(5 * k)
for i, lab in enumerate(['0', '1', '2', '3,5 m']):
    x = px + [0, 1 / 3.5, 2 / 3.5, 1][i] * bw
    d.text((x - (0 if i == 0 else (int(40 * k) if i == 3 else int(4 * k))), ty), lab, font=fS, fill=(220, 220, 220))
for i, lab in enumerate(['0', '1', '2 m']):
    x = px + bw + int(22 * k) + [0, 0.5, 1][i] * bw
    d.text((x - (0 if i == 0 else (int(30 * k) if i == 2 else int(4 * k))), ty), lab, font=fS, fill=(220, 220, 220))

ly = ty + int(34 * k)
d.line([(px, ly + 9 * k), (px + 40 * k, ly + 9 * k)], fill=(255, 246, 215), width=max(2, int(4 * k)))
d.text((px + 52 * k, ly), 'Limite da superfície LandXML "PLATO GERAL – RUA B"', font=fS, fill=(235, 235, 235))
ly += int(28 * k)
d.line([(px, ly + 9 * k), (px + 40 * k, ly + 9 * k)], fill=(40, 30, 28), width=max(1, int(2 * k)))
d.text((px + 52 * k, ly), 'Isolinhas de altura de corte/aterro a cada 0,50 m', font=fS, fill=(235, 235, 235))
ly += int(36 * k)
d.text((px, ly), f'Plato ({br(vol["area_plato"])} m²):  corte ≈ {br(vol["corte_plato"])} m³   ·   '
       f'aterro ≈ {br(vol["aterro_plato"])} m³', font=fT, fill=(255, 255, 255))
ly += int(30 * k)
d.text((px, ly), 'Volumes estimados: terreno natural reconstruído das curvas e perfis do DWG.',
       font=fS, fill=(200, 203, 208))

# rótulo da via
tx, ty0 = int(1545 * k), int(600 * k)
tw = d.textlength('RUA B', font=fT)
panel((tx - tw / 2 - 14 * k, ty0 - 6 * k, tx + tw / 2 + 14 * k, ty0 + 28 * k), alpha=165, r=8)
d = ImageDraw.Draw(im)
d.text((tx - tw / 2, ty0), 'RUA B', font=fT, fill=(255, 255, 255))

im.convert('RGB').save(OUT, optimize=True)
print('ok', OUT)
