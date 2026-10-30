"""Prepara os dados do terreno para o Blender.
 - núcleo: MDT 1 m do levantamento (curvas do DWG), completado fora da área
   levantada pelo entorno sintético;
 - entorno: grade 8 m em 5 km x 5 km (colinas suaves, ilustrativo) para o horizonte;
 - perímetro do terreno e posições das árvores do entorno (mata ciliar/capões).
Uso: python3 prep_terrain.py geo.json mdt_dir saida_dir"""
import sys, json, math
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt, map_coordinates
from shapely.geometry import Polygon, Point

geo = json.load(open(sys.argv[1])); md = sys.argv[2]; out = sys.argv[3]
Z = np.load(f'{md}/mdt.npy').astype(np.float64)
V = np.load(f'{md}/mdt_valido.npy')
M = json.load(open(f'{md}/mdt.json'))
OX, OY = 383400.0, 6852450.0          # origem local da cena
rng = np.random.default_rng(7)

# ---------------------------------------------------------------- entorno 8 m
R8, HALF = 8.0, 2500.0
n8 = int(2 * HALF / R8) + 1
ax8 = -HALF + np.arange(n8) * R8
gx, gy = np.meshgrid(ax8, ax8)          # coordenadas locais
# MDT (coarse) amostrado na grade 8 m
ci = (gx + OX - M['x0']) / M['res']; ri = (gy + OY - M['y0']) / M['res']
inside = (ci >= 0) & (ci <= M['nx'] - 1) & (ri >= 0) & (ri <= M['ny'] - 1)
zc = map_coordinates(Z, [ri, ci], order=1, mode='nearest')
vc = map_coordinates(V.astype(float), [ri, ci], order=1, mode='constant') > 0.5
vc &= inside
# convolução normalizada: extensão suave das cotas da borda levantada
# cota típica da borda do levantamento (fundo dos vales ao redor do morro)
from scipy.ndimage import binary_erosion
edge = vc & ~binary_erosion(vc, iterations=2)
far_mean = float(np.median(zc[edge]))
base = np.full(zc.shape, far_mean)
for s in (60, 30, 15):   # extensão em multiescala a partir da borda
    num = gaussian_filter(np.where(vc, zc, 0), s); den = gaussian_filter(vc.astype(float), s)
    w = np.clip(den / 0.15, 0, 1)
    base = base * (1 - w) + (num / np.maximum(den, 1e-6)) * w
base = gaussian_filter(base, 4)


def fbm(shape, scales, amps):
    f = np.zeros(shape)
    for sc, a in zip(scales, amps):
        n = gaussian_filter(rng.standard_normal(shape), sc / R8)
        f += a * n / n.std()
    return f


noise = fbm(gx.shape, (90, 220, 500), (2.5, 9.0, 16.0))
dist = distance_transform_edt(~vc) * R8
wn = np.clip(dist / 250, 0, 1) ** 1.2
synth = base + noise * wn
H8 = np.where(vc, zc, synth)
# transição suave entre levantamento e entorno
blend = np.clip(dist / 40, 0, 1)
H8 = zc * (1 - blend) + synth * blend
H8 = np.where(vc, zc, H8)

# ---------------------------------------------------------------- núcleo 1 m
ny, nx = Z.shape
cx = M['x0'] - OX + np.arange(nx) * M['res']
cy = M['y0'] - OY + np.arange(ny) * M['res']
CX, CY = np.meshgrid(cx, cy)
sy = (CY + HALF) / R8; sx = (CX + HALF) / R8
syn1 = map_coordinates(H8, [sy, sx], order=3, mode='nearest')
d1 = distance_transform_edt(~V) * M['res']
b1 = np.clip(d1 / 40, 0, 1)
b1 = b1 * b1 * (3 - 2 * b1)
H1 = Z * (1 - b1) + syn1 * b1
# a grade grossa usa o núcleo onde ele existe (costura exata)
in1 = (gx >= cx[0]) & (gx <= cx[-1]) & (gy >= cy[0]) & (gy <= cy[-1])
H8[in1] = map_coordinates(H1, [(gy[in1] - cy[0]), (gx[in1] - cx[0])], order=1)

# borda do entorno 8 m converge para a cota média (encontra o horizonte)
de = np.minimum.reduce([gx + HALF, HALF - gx, gy + HALF, HALF - gy])
we = np.clip((de - 40) / 400, 0, 1); we = we * we * (3 - 2 * we)
H8 = H8 * we + far_mean * (1 - we)
# horizonte: 30 km, 100 m, ondulação suave, igual a far_mean junto ao entorno
R100, HF = 100.0, 15000.0
nf = int(2 * HF / R100) + 1
af = -HF + np.arange(nf) * R100
fx, fy = np.meshgrid(af, af)
nz = np.zeros(fx.shape)
for sc, a in ((600, 10), (1500, 25), (4000, 40)):
    n = gaussian_filter(rng.standard_normal(fx.shape), sc / R100); nz += a * n / n.std()
df = np.maximum(np.abs(fx), np.abs(fy))
wf = np.clip((df - HALF) / 1500, 0, 1)
HF_ = far_mean + nz * wf - 0.5 * (df < HALF)
np.save(f'{out}/terreno_100m.npy', HF_.astype(np.float32))

np.save(f'{out}/terreno_1m.npy', H1.astype(np.float32))
np.save(f'{out}/terreno_8m.npy', H8.astype(np.float32))
np.save(f'{out}/levantado_1m.npy', V)

# ---------------------------------------------------------------- perímetro
def loc(p): return [(x - OX, y - OY) for x, y in p]


per = [o for o in geo['URB-Perímetr'] if o['closed']][0]['p']
perim = Polygon(loc(per)).buffer(0)
lotes = [loc(o['p']) for o in geo['URB-Lotes']]
quadras = [loc(o['p']) for o in geo['URB-Quadras']]
calc = [dict(p=loc(o['p']), c=o['closed']) for o in geo['URB-Calçada']]

# ---------------------------------------------------------------- vegetação do entorno
# capões e mata ciliar: preferência por vales (cota abaixo da média local) e encostas
loc_mean = gaussian_filter(H8, 120 / R8)
valley = (loc_mean - H8)                      # >0 nos vales
patch = fbm(gx.shape, (120, 300), (1.0, 0.8))
score = valley / 6 + patch * 0.9
# sem árvores na área levantada (terreno natural real) e numa faixa de 40 m
excl_m = gaussian_filter(vc.astype(float), 5) > 0.02
dens = fbm(gx.shape, (35, 90), (1.0, 0.7))            # clareiras e bordas irregulares
trees = []
while len(trees) < 24000:
    x, y = rng.uniform(-HALF + 50, HALF - 50, 2)
    r, c = int((y + HALF) / R8), int((x + HALF) / R8)
    if excl_m[r, c]:
        continue
    p = np.clip((score[r, c] - 0.2) * 1.6, 0, 1) * np.clip(0.55 + 0.35 * dens[r, c], 0, 1)
    if rng.random() < p:
        trees.append((round(float(x), 1), round(float(y), 1)))
# árvores isoladas no campo (paisagem típica do planalto)
k = 0
while k < 700:
    x, y = rng.uniform(-HALF + 50, HALF - 50, 2)
    r, c = int((y + HALF) / R8), int((x + HALF) / R8)
    if excl_m[r, c]:
        continue
    trees.append((round(float(x), 1), round(float(y), 1))); k += 1

json.dump(dict(origem=[OX, OY], r8=R8, half=HALF, r100=R100, half100=HF, cota_base=far_mean, x0_1m=float(cx[0]), y0_1m=float(cy[0]), res1=M['res'],
               perimetro=list(perim.exterior.coords), lotes=lotes, quadras=quadras, calcadas=calc,
               arvores=trees, zmin=float(Z[V].min()), zmax=float(Z[V].max())),
          open(f'{out}/cena_terreno.json', 'w'))
print('arvores', len(trees), 'H8', H8.min(), H8.max(), 'H1', H1.min(), H1.max(),
      'area perimetro (ha)', perim.area / 1e4)
