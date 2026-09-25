"""Gera texturas procedurais sem emenda:
 - paver holandês 10x20 cm assentado em espinha-de-peixe (claro e escuro)
 - piso tátil de alerta e direcional (concreto amarelo)
Saída em assets/tex/gen/.  Uso: python3 gen_textures.py <pasta_saida>"""
import sys, os
import numpy as np
from PIL import Image, ImageFilter

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)


def normal_from_height(h, strength):
    gy, gx = np.gradient(h)
    n = np.dstack((-gx * strength, gy * strength, np.ones_like(h)))
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8))


def save(prefix, alb, rough, h, strength):
    Image.fromarray(np.clip(alb * 255, 0, 255).astype(np.uint8)).save(f'{OUT}/{prefix}_color.jpg', quality=93)
    Image.fromarray(np.clip(rough * 255, 0, 255).astype(np.uint8)).save(f'{OUT}/{prefix}_rough.jpg', quality=93)
    normal_from_height(h, strength).save(f'{OUT}/{prefix}_normal.png')


def herringbone(prefix, base, var, px_cell=51, cells=40):
    """cells x cells células de 10 cm (textura cobre cells/10 m)."""
    N = px_cell * cells
    idx = np.full((N, N), -1, np.int32)
    lx = np.zeros((N, N), np.float32)   # distância até a borda (px) p/ chanfro
    bricks = []
    for i in range(cells):
        for j in range(cells):
            if (i - j) % 4 == 0:
                bricks.append((i, j, 2, 1))
            if (i - j) % 4 == 3:
                bricks.append((i, j, 1, 2))
    yy, xx = np.mgrid[0:N, 0:N]
    cellx = xx // px_cell
    celly = yy // px_cell
    # mapa célula -> tijolo
    cmap = -np.ones((cells, cells), np.int32)
    for b, (i, j, w, hh) in enumerate(bricks):
        for dx in range(w):
            for dy in range(hh):
                cmap[(j + dy) % cells, (i + dx) % cells] = b
    idx = cmap[celly, cellx]
    # coordenadas locais dentro do tijolo para chanfro
    bi = np.array([b[0] for b in bricks]); bj = np.array([b[1] for b in bricks])
    bw = np.array([b[2] for b in bricks]); bh = np.array([b[3] for b in bricks])
    ox = (xx - bi[idx] * px_cell) % N
    oy = (yy - bj[idx] * px_cell) % N
    W = bw[idx] * px_cell; H = bh[idx] * px_cell
    d = np.minimum.reduce([ox, oy, W - 1 - ox, H - 1 - oy]).astype(np.float32)
    joint = 1.6
    bevel = 5.0
    h = np.clip((d - joint) / bevel, 0, 1)
    h = h * (0.9 + 0.1 * rng.random(len(bricks))[idx])
    # cor por tijolo + ruído fino
    tint = 1 + var * rng.standard_normal(len(bricks))[idx]
    noise = np.array(Image.fromarray((rng.random((N // 4, N // 4)) * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)) / 255.0
    fine = rng.random((N, N)) * 0.06 - 0.03
    alb = np.dstack([base[c] * tint * (0.94 + 0.12 * noise) + fine for c in range(3)])
    jmask = (d < joint)[..., None]
    alb = np.where(jmask, np.array(base) * 0.55, alb)       # areia nas juntas
    rough = np.where(d < joint, 0.95, 0.78 + 0.1 * noise)
    save(prefix, alb, rough, h + 0.02 * noise, 6.0)


# paver cinza claro e escuro (sRGB ~ linear aproximado nas texturas)
herringbone('paver_claro', (0.66, 0.65, 0.62), 0.045)
herringbone('paver_escuro', (0.36, 0.36, 0.37), 0.05)


def tatil(prefix, kind, N=1024, tile_m=0.4):
    """Piso tátil 40x40 cm (textura = 1 placa)."""
    yy, xx = (np.mgrid[0:N, 0:N] + 0.5) / N * tile_m
    h = np.zeros((N, N), np.float32)
    if kind == 'alerta':
        s = tile_m / 6
        cx = (np.floor(xx / s) + 0.5) * s; cy = (np.floor(yy / s) + 0.5) * s
        r = np.hypot(xx - cx, yy - cy)
        h = np.clip(1 - (r / 0.0125) ** 2, 0, 1) ** 0.5
    else:
        s = tile_m / 4
        u = (xx % s) - s / 2
        h = np.clip(1 - (np.abs(u) / 0.0175) ** 4, 0, 1)
    edge = np.minimum.reduce([xx, yy, tile_m - xx, tile_m - yy])
    grout = edge < 0.002
    base = np.array((0.78, 0.60, 0.10))
    noise = rng.random((N, N)) * 0.05
    alb = np.dstack([base[c] * (0.95 + noise) for c in range(3)])
    alb[grout] = (0.35, 0.33, 0.30)
    rough = 0.7 + noise
    save(prefix, alb, rough, h, 6.0 if kind == 'alerta' else 12.0)


tatil('tatil_alerta', 'alerta')
tatil('tatil_direcional', 'direcional')
print('ok')


# --- pictograma de bicicleta + seta (sinalização horizontal da ciclovia)
from PIL import ImageDraw
W, H = 1500, 492          # 2,50 x 0,82 m
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
white = (235, 235, 230, 255)
lw = 26
# bicicleta (vista lateral) à esquerda
r = 120
c1, c2 = (190, 300), (560, 300)
for c in (c1, c2):
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=white, width=lw)
seat, crank, head = (300, 110), (370, 300), (520, 120)
d.line([c1, crank, (300, 150), c1], fill=white, width=lw)
d.line([crank, (500, 160), (300, 150)], fill=white, width=lw)
d.line([(500, 160), c2], fill=white, width=lw)
d.line([(500, 160), head, (560, 100)], fill=white, width=lw)
d.line([(250, 110), (350, 110)], fill=white, width=lw + 6)
# seta à direita
d.rectangle((860, 215, 1230, 285), fill=white)
d.polygon([(1230, 130), (1430, 250), (1230, 370)], fill=white)
im = im.filter(ImageFilter.GaussianBlur(1.2))
im.save(f'{OUT}/pictograma_bici.png')
print('pictograma ok')
