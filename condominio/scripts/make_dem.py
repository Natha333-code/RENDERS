"""Gera o modelo digital de terreno (MDT) a partir das curvas de nível do DWG.
Uso: python3 make_dem.py geo.json saida_dir
geo.json vem de extract_geo.py (polilinhas por layer, com elevação)."""
import sys, json, math
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter, distance_transform_edt
from scipy.spatial import cKDTree

geo = json.load(open(sys.argv[1])); out = sys.argv[2]
CURVAS = ('C-TOPO-MAJR', 'C-TOPO-MINR', 'TOPO_Aux_Superficie')
RES = 1.0  # m por pixel

pts = []
for l in CURVAS:
    for o in geo.get(l, []):
        if o['z'] < 100: continue
        p = np.array(o['p'])
        seg = np.hypot(*np.diff(p, axis=0).T)
        s = np.r_[0, np.cumsum(seg)]
        t = np.arange(0, s[-1], 1.0)  # um ponto a cada 1 m
        q = np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1]), np.full(len(t), o['z'])]
        pts.append(q)
P = np.vstack(pts)
P = P[(P[:, 0] > 382800) & (P[:, 0] < 383800) & (P[:, 1] > 6851900) & (P[:, 1] < 6852900)]
# remove duplicados (curvas repetidas em layers diferentes)
P = np.unique(np.round(P, 1), axis=0)
print('pontos', len(P), 'z', P[:, 2].min(), P[:, 2].max(), flush=True)

x0, y0 = np.floor(P[:, :2].min(0) / 10) * 10
x1, y1 = np.ceil(P[:, :2].max(0) / 10) * 10
nx, ny = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
gx, gy = np.meshgrid(x0 + np.arange(nx) * RES, y0 + np.arange(ny) * RES)
Z = griddata(P[:, :2], P[:, 2], (gx, gy), method='linear')
# distância até a curva mais próxima -> máscara de confiabilidade
d, _ = cKDTree(P[:, :2]).query(np.c_[gx.ravel(), gy.ravel()], k=1, workers=-1)
D = d.reshape(Z.shape)
valid = ~np.isnan(Z) & (D < 40)
# preenche fora da área levantada com o vizinho válido mais próximo (só p/ o entorno)
idx = distance_transform_edt(~valid, return_distances=False, return_indices=True)
Zf = Z.copy(); Zf[~valid] = Z[tuple(i[~valid] for i in idx)]
Zf = np.where(np.isnan(Zf), np.nanmin(Z), Zf)
# suaviza só o necessário para tirar o "terraceamento" do TIN
Zs = gaussian_filter(Zf, 1.5)
# fora da área levantada, suaviza bem mais (entorno genérico)
far = distance_transform_edt(~valid) * RES
w = np.clip(far / 60, 0, 1)
Zs = Zs * (1 - w) + gaussian_filter(Zf, 12) * w
np.save(f'{out}/mdt.npy', Zs.astype(np.float32))
np.save(f'{out}/mdt_valido.npy', valid)
json.dump(dict(x0=float(x0), y0=float(y0), res=RES, nx=nx, ny=ny,
               zmin=float(Zs[valid].min()), zmax=float(Zs[valid].max())), open(f'{out}/mdt.json', 'w'))
print('grade', nx, ny, 'z', Zs[valid].min(), Zs[valid].max())
