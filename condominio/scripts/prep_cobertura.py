"""Cobertura do solo a partir da imagem aérea fornecida pelo cliente (vista de satélite).
Classes: 0 urbano/ruas, 1 mata, 2 campo/gramado, 3 lavoura/solo.
 - árvores da mata nas áreas de mata (inclusive dentro do terreno, fora das vias);
 - casas (volumes simples, cor do telhado tirada da imagem) nos bairros vizinhos;
 - textura de cor do chão por classe (para o material do terreno).
Georreferência: calibrada contra as ruas do OpenStreetMap (dados/osm_local.json, em
coordenadas locais UTM 22S SIRGAS 2000 – mesmo sistema do DWG, conferido com o KML):
1,322 m/px, sem rotação; pixel (PX0, PY0) = origem local (383400, 6852450).
Prédios e ruas do entorno vêm do OSM (© colaboradores do OpenStreetMap, ODbL).
Uso: python3 prep_cobertura.py imagem.png dados_dir"""
import sys, json
import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter, gaussian_filter
from shapely.geometry import Polygon, Point
from shapely import contains_xy

img, D = sys.argv[1], sys.argv[2]
A, PX0, PY0, LX0, LY0 = 1.32207, 342.669, 357.482, 0.0, 0.0
CORTE = 742                     # barra inferior da captura
rng = np.random.default_rng(5)

im = np.asarray(Image.open(img).convert('RGB')).astype(float)[:CORTE] / 255
sm = np.stack([uniform_filter(im[..., i], 3) for i in range(3)], -1)
r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
lum = 0.3 * r + 0.59 * g + 0.11 * b
cls = np.zeros(r.shape, np.uint8)
cls[lum < 0.27] = 1
cls[(g - r > 0.08) & (g > b + 0.02) & (lum >= 0.24) & (lum < 0.55)] = 2
cls[(r > g + 0.04) & (lum > 0.35)] = 3
# rótulos do mapa sobre a mata -> mata; trilha de terra na clareira -> campo
for (x0, x1, y0, y1, k) in ((355, 478, 500, 522, 1), (430, 478, 135, 205, 1), (398, 425, 235, 275, 1)):
    sub = cls[y0:y1, x0:x1]; sub[sub == 0] = k
sub = cls[175:300, 240:300]; sub[sub == 0] = 2
oh = np.stack([uniform_filter((cls == k).astype(float), 7) for k in range(4)], -1)
cls = oh.argmax(-1).astype(np.uint8)
H, W = cls.shape


def to_local(px, py):
    return LX0 + (np.asarray(px) - PX0) * A, LY0 - (np.asarray(py) - PY0) * A


def to_px(x, y):
    return PX0 + (np.asarray(x) - LX0) / A, PY0 - (np.asarray(y) - LY0) / A


xmin, ymax = to_local(0, 0); xmax, ymin = to_local(W, H)
J = json.load(open(f'{D}/cena_terreno.json'))
perim = Polygon(J['perimetro'])
vm = np.load(f'{D}/vias_mascara_1m.npy')
X1, Y1, R1 = J['x0_1m'], J['y0_1m'], J['res1']


def em_via(x, y, folga=4):
    c = np.round((x - X1) / R1).astype(int); rr = np.round((y - Y1) / R1).astype(int)
    out = np.zeros(len(x), bool)
    for dx in range(-folga, folga + 1, 2):
        for dy in range(-folga, folga + 1, 2):
            cc = np.clip(c + dx, 0, vm.shape[1] - 1); r2 = np.clip(rr + dy, 0, vm.shape[0] - 1)
            ok = (c + dx >= 0) & (c + dx < vm.shape[1]) & (rr + dy >= 0) & (rr + dy < vm.shape[0])
            out |= ok & vm[r2, cc]
    return out


# ---------------------------------------------------------------- OSM: ruas e prédios do entorno
from shapely.geometry import LineString
OSM = json.load(open(f'{D}/osm_local.json'))
LARG = {'primary': 10, 'secondary': 9, 'tertiary': 8, 'residential': 7, 'unclassified': 7,
        'living_street': 6, 'service': 4, 'track': 3}
ruas = [dict(p=o['p'], w=LARG[o['sub']], terra=o['sub'] == 'track') for o in OSM
        if o['k'] == 'highway' and o['sub'] in LARG]
from shapely.ops import unary_union
ruas_geom = unary_union([LineString(r['p']).buffer(r['w'] / 2) for r in ruas])
predios = []
for o in OSM:
    if o['k'] != 'building' or len(o['p']) < 4:
        continue
    pg = Polygon(o['p']).buffer(0)
    if pg.is_empty or pg.area < 12 or pg.intersects(perim):
        continue
    cx, cy = pg.centroid.x, pg.centroid.y
    qx, qy = to_px(cx, cy); qi, qj = int(qy), int(qx)
    if 0 <= qi < H and 0 <= qj < W:
        cor = im[max(qi - 1, 0):qi + 2, max(qj - 1, 0):qj + 2].reshape(-1, 3).mean(0)
        cor = np.clip(cor ** 2.2 * 1.1, 0.02, 0.8)
    else:
        cor = np.array(rng.choice([[0.35, 0.12, 0.08], [0.45, 0.45, 0.45], [0.25, 0.25, 0.27]]))
    alt = 3.0 if pg.area < 250 else (6.0 if pg.area < 900 else 9.0)
    if rng.random() < 0.15: alt *= 2
    ext = pg.exterior if pg.geom_type == 'Polygon' else max(pg.geoms, key=lambda g: g.area).exterior
    predios.append(dict(p=np.array(ext.coords).round(2).tolist(), h=alt, cor=[round(float(c), 3) for c in cor]))
pred_geom = unary_union([Polygon(pr['p']) for pr in predios]) if predios else Polygon()
fora_ruas = lambda x, y: ~contains_xy(ruas_geom.buffer(2.0), x, y)

# ---------------------------------------------------------------- mata (amostragem com espaçamento ~5 m)
n = int((xmax - xmin) * (ymax - ymin) / 18)
x = rng.uniform(xmin, xmax, n); y = rng.uniform(ymin, ymax, n)
px, py = to_px(x, y)
ci = np.clip(px.astype(int), 0, W - 1); ri = np.clip(py.astype(int), 0, H - 1)
mf = gaussian_filter((cls == 1).astype(float), 1.0)[ri, ci]
keep = rng.random(n) < np.clip((mf - 0.35) * 2.2, 0, 1)
x, y = x[keep], y[keep]
# grade de exclusão ~7 m (copas não se sobrepõem demais)
cell = 7.0
key = np.floor(x / cell).astype(np.int64) * 100000 + np.floor(y / cell).astype(np.int64)
_, first = np.unique(key, return_index=True)
x, y = x[first], y[first]
ok = ~em_via(x, y) & fora_ruas(x, y) & ~contains_xy(pred_geom.buffer(3), x, y)
x, y = x[ok], y[ok]
mata = np.c_[x, y]

# ---------------------------------------------------------------- casas
urb = uniform_filter((cls == 0).astype(float), 11)
casas = []
step = 12.0
for gy in np.arange(ymin + 6, ymax - 6, step):
    for gx in np.arange(xmin + 6, xmax - 6, step):
        hx, hy = gx + rng.uniform(-2.5, 2.5), gy + rng.uniform(-2.5, 2.5)
        qx, qy = to_px(hx, hy); qi, qj = int(qy), int(qx)
        if not (0 <= qi < H and 0 <= qj < W) or urb[qi, qj] < 0.62 or cls[qi, qj] != 0:
            continue
        if perim.buffer(60).contains(Polygon([(hx - 1, hy - 1), (hx + 1, hy - 1), (hx + 1, hy + 1)])):
            continue
        if rng.random() < 0.18:      # quintais
            continue
        # só onde o OSM não tem prédios mapeados, e fora das ruas
        if pred_geom.distance(Point(hx, hy)) < 15 or ruas_geom.distance(Point(hx, hy)) < 6:
            continue
        cor = im[max(qi - 1, 0):qi + 2, max(qj - 1, 0):qj + 2].reshape(-1, 3).mean(0)
        cor = np.clip(cor ** 2.2 * 1.1, 0.02, 0.8)        # sRGB -> linear aproximado
        casas.append([round(float(hx), 1), round(float(hy), 1), round(float(rng.uniform(7, 10)), 1),
                      round(float(rng.uniform(8, 13)), 1), 3.0 if rng.random() < 0.8 else 5.8,
                      round(float(rng.normal(0, 0.05)), 3), *[round(float(c), 3) for c in cor]])

# ---------------------------------------------------------------- textura do chão por classe
pal = np.array([[0.20, 0.21, 0.18], [0.05, 0.08, 0.03], [0.16, 0.20, 0.07], [0.40, 0.33, 0.20]])
tex = pal[cls]
tex = np.stack([gaussian_filter(tex[..., i], 1.2) for i in range(3)], -1)
Image.fromarray((np.clip(tex, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).save(f'{D}/cobertura.png')
np.save(f'{D}/cobertura_classes.npy', cls)

# árvores sintéticas do entorno: só fora da área da imagem
T = np.array(J['arvores'])
fora = ~((T[:, 0] > xmin) & (T[:, 0] < xmax) & (T[:, 1] > ymin) & (T[:, 1] < ymax))
Te = T[fora]
Te = Te[fora_ruas(Te[:, 0], Te[:, 1]) & ~contains_xy(pred_geom.buffer(3), Te[:, 0], Te[:, 1])]
J['arvores'] = Te.round(1).tolist() + mata.round(1).tolist()
J['casas'] = casas
J['predios'] = predios
J['ruas_osm'] = ruas
J['cobertura'] = dict(xmin=float(xmin), xmax=float(xmax), ymin=float(ymin), ymax=float(ymax))
json.dump(J, open(f'{D}/cena_terreno.json', 'w'))
print('mata', len(mata), 'entorno', int(fora.sum()), 'casas', len(casas), 'predios OSM', len(predios), 'ruas OSM', len(ruas),
      'extensão', [round(v) for v in (xmin, xmax, ymin, ymax)])
