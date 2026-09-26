"""Gera as texturas finais para o SketchUp (cor já tratada, 1024 px) e
recortes de folhagem das árvores.  python3 sk_textures.py <assets> <treetex> <saida>"""
import sys, os, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

A, TT, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
TEX = A + '/tex'
rng = np.random.default_rng(1)


def src(folder):
    return glob.glob(f'{TEX}/{folder}/*_Color.jpg')[0]


def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def proc(name, path, sat=1.0, val=1.0, tint=None, size=1024):
    im = Image.open(path).convert('RGB').resize((size, size), Image.LANCZOS)
    if sat != 1.0 or val != 1.0:
        h, s, v = [np.asarray(c, dtype=float) for c in im.convert('HSV').split()]
        s = np.clip(s * sat, 0, 255); v = np.clip(v * val, 0, 255)
        im = Image.merge('HSV', [Image.fromarray(x.astype(np.uint8)) for x in (h, s, v)]).convert('RGB')
    if tint:
        a = srgb2lin(np.asarray(im, dtype=float) / 255) * np.array(tint)
        im = Image.fromarray((lin2srgb(a) * 255).astype(np.uint8))
    im.save(f'{OUT}/{name}.jpg', quality=90)


SPEC = {  # nome: (pasta ambientCG, saturação, valor, tint)
    'areia': ('Ground079S', 0.75, 1.25, None), 'asfalto': ('Asphalt025C', 0.8, 0.8, None),
    'calcada': ('Concrete031', 0.6, 1.25, None), 'concreto': ('Concrete034', 1, 1, (0.86, 0.86, 0.84)),
    'concreto_arq': ('Concrete031', 0.5, 1.3, None), 'estipe_jeriva': ('Concrete031', 0.3, 0.55, None),
    'galvanizado': ('Metal032', 1, 1, (0.75, 0.76, 0.78)), 'grama': ('Grass004', 1.3, 0.75, None),
    'jatoba': ('Wood066', 1.1, 0.95, None), 'lote': ('Grass001', 1.1, 0.9, None),
    'meio_fio': ('Concrete034', 1, 1, (0.82, 0.82, 0.8)), 'palco': ('Concrete034', 1, 1, (0.46, 0.25, 0.16)),
    'palete': ('Wood058', 1, 1, None), 'pedrisco': ('Gravel041', 1, 1, None),
    'solo_mata': ('Ground037', 1.1, 0.45, None), 'terra_casca': ('Ground037', 0.4, 0.45, None),
}
for n, (f, s, v, t) in SPEC.items():
    proc(n, src(f), s, v, t)
# ciclovia: concreto escovado pintado de vermelho
bw = np.asarray(Image.open(src('Concrete034')).convert('L').resize((1024, 1024)), dtype=float) / 255
t = np.clip((bw - 0.3) / 0.6, 0, 1)[..., None]
col = srgb2lin(np.array([0.30, 0.025, 0.02])) * 0 + np.array([0.30, 0.025, 0.02]) * (1 - t) + np.array([0.62, 0.07, 0.05]) * t
Image.fromarray((lin2srgb(col) * 255).astype(np.uint8)).save(f'{OUT}/ciclovia.jpg', quality=90)
# texturas geradas (paver, piso tátil) e decalques
for n in ('paver_claro', 'paver_escuro', 'tatil_alerta', 'tatil_direcional'):
    Image.open(f'{TEX}/gen/{n}_color.jpg').convert('RGB').resize((1024, 1024)).save(f'{OUT}/{n}.jpg', quality=90)
Image.open(f'{TEX}/logo.png').save(f'{OUT}/logo.png')
Image.open(f'{TEX}/gen/pictograma_bici.png').save(f'{OUT}/pictograma.png')


# telas metálicas com transparência (ladrilho de 0,50 x 0,50 m)
def wire(name, sx, sy, rgb, w_px=3, N=512, size_m=0.5):
    im = Image.new('RGBA', (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    px = N / size_m
    x = 0.0
    while x < size_m - 1e-6:
        d.rectangle((x * px, 0, x * px + w_px, N), fill=(*rgb, 255)); x += sx
    y = 0.0
    while y < size_m - 1e-6:
        d.rectangle((0, y * px, N, y * px + w_px), fill=(*rgb, 255)); y += sy
    im.save(f'{OUT}/{name}.png')


wire('tela_gradil', 0.05, 0.25, (18, 70, 36), 4)
wire('tela_alambrado', 0.05, 0.05, (165, 170, 172), 3)
wire('rede_esporte', 0.05, 0.05, (235, 235, 235), 2)

# recortes de folhagem ("cachos") a partir das árvores renderizadas
info = {}
for f in sorted(glob.glob(f'{TT}/*_a.png')):
    sp = os.path.basename(f)[:-6]
    crops = []
    for view in ('a', 'b'):
        im = Image.open(f'{TT}/{sp}_{view}.png').convert('RGBA')
        a = np.asarray(im)[..., 3] / 255.0
        H, W = a.shape
        c = int(W * 0.22)
        tries = 0
        while len([k for k in crops if k[0] == view]) < 3 and tries < 4000:
            tries += 1
            x, y = rng.integers(0, W - c), rng.integers(0, int(H * 0.7) - c)
            cov = a[y:y + c, x:x + c].mean()
            core = a[y + c // 4:y + 3 * c // 4, x + c // 4:x + 3 * c // 4].mean()
            edge = np.concatenate([a[y, x:x + c], a[y + c - 1, x:x + c], a[y:y + c, x], a[y:y + c, x + c - 1]]).mean()
            if 0.45 < cov < 0.8 and core > 0.7 and edge < 0.35:
                crops.append((view, x, y))
        for k, (v, x, y) in enumerate([k for k in crops if k[0] == view]):
            cr = im.crop((x, y, x + c, y + c)).resize((512, 512), Image.LANCZOS)
            # borda suave para não mostrar o quadrado do recorte
            m = Image.new('L', (512, 512), 0)
            ImageDraw.Draw(m).ellipse((20, 20, 492, 492), fill=255)
            m = m.filter(ImageFilter.GaussianBlur(28))
            al = np.minimum(np.asarray(cr)[..., 3], np.asarray(m))
            cr.putalpha(Image.fromarray(al.astype(np.uint8)))
            cr.save(f'{OUT}/folhagem_{sp}_{v}{k}.png')
    info[sp] = len(crops)
json.dump(info, open(f'{OUT}/folhagem.json', 'w'))
print('ok', info)
