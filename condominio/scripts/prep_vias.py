"""Vias do condomínio a partir do DWG (URB-Calçada = meio-fio, URB-Quadras = alinhamento).
 pista   = área interna ao meio-fio (C5 + trecho de acesso C0/C6) menos as ilhas;
 passeio = faixa entre meio-fio e alinhamento das quadras (1,5 m);
 canteiros = pequenos polígonos fechados de meio-fio dentro da pista.
Ajusta o terreno sob as vias (greide suavizado, taludes de concordância) e
gera triângulos para o Blender.
Uso: python3 prep_vias.py geo.json dados_dir"""
import sys, json
import numpy as np
from shapely.geometry import Polygon, LineString, MultiPolygon, box
from shapely.ops import unary_union
from shapely import constrained_delaunay_triangles
from scipy.ndimage import gaussian_filter, distance_transform_edt
from matplotlib.path import Path

geo = json.load(open(sys.argv[1])); D = sys.argv[2]
J = json.load(open(f'{D}/cena_terreno.json'))
OX, OY = J['origem']
H1 = np.load(f'{D}/terreno_1m.npy').astype(np.float64)
X1, Y1, R1 = J['x0_1m'], J['y0_1m'], J['res1']
L = lambda p: [(x - OX, y - OY) for x, y in p]
cal = geo['URB-Calçada']; qua = geo['URB-Quadras']
PASSEIO = 1.5      # largura do passeio (medida no DWG entre meio-fio e alinhamento)
MEIOFIO = 0.15     # largura do topo do meio-fio

externo = Polygon(L(cal[5]['p'])).buffer(0)                          # meio-fio externo (C5, fechado)
acesso = Polygon(L(cal[0]['p']) + L(cal[6]['p'])).buffer(0)          # trecho de acesso (C0 / C6)
ilhas_q = [Polygon(L(cal[i]['p'])).buffer(0) for i in (1, 2)]        # quadras internas (meio-fio)
canteiros = [Polygon(L(c['p'])).buffer(0) for i, c in enumerate(cal) if c['closed'] and i not in (1, 2)]
quadras = unary_union([Polygon(L(q['p'])).buffer(0) for q in qua if q['closed']])
# o meio-fio C0 segue além do fim de C6 (ligação com a estrada existente): corta no fim de C6
acesso = acesso.intersection(box(-1e4, -1e4, 1e4, cal[6]['p'][-1][1] - OY))
# fecha as frestas entre o meio-fio C5 e o trecho de acesso
leito = unary_union([externo, acesso]).buffer(1.0, join_style=2).buffer(-1.0, join_style=2)
leito = leito.buffer(-1.5, join_style=2).buffer(1.5, join_style=2)   # remove a lasca no fim de C5
pista = leito.difference(unary_union(ilhas_q)).difference(unary_union(canteiros))
pista = pista.difference(quadras.buffer(-0.3))
passeio_int = unary_union(ilhas_q).difference(quadras)
passeio_ext = leito.buffer(PASSEIO, join_style=2).difference(leito).difference(quadras)
passeio = unary_union([passeio_int, passeio_ext]).buffer(0.02).buffer(-0.02)
passeio = unary_union([p for p in getattr(passeio, 'geoms', [passeio]) if p.area > 10])
meiofio = passeio.intersection(pista.buffer(MEIOFIO + 0.01, join_style=2))
canteiro_mf = unary_union(canteiros).difference(unary_union(canteiros).buffer(-MEIOFIO))
passeio = passeio.difference(meiofio)
grama_c = unary_union(canteiros).buffer(-MEIOFIO)
print('areas m2: pista %.0f passeio %.0f meio-fio %.0f canteiros %.0f' %
      (pista.area, passeio.area, meiofio.area + canteiro_mf.area, unary_union(canteiros).area))

# ---------------------------------------------------------------- greide
ny, nx = H1.shape
gx, gy = np.meshgrid(X1 + np.arange(nx) * R1, Y1 + np.arange(ny) * R1)
corr = unary_union([pista, passeio, meiofio, unary_union(canteiros)]).buffer(0.5)


def raster(geom):
    m = np.zeros(H1.shape, bool)
    pts = np.c_[gx.ravel(), gy.ravel()]
    for g in getattr(geom, 'geoms', [geom]):
        b = g.bounds
        sel = (pts[:, 0] >= b[0] - 1) & (pts[:, 0] <= b[2] + 1) & (pts[:, 1] >= b[1] - 1) & (pts[:, 1] <= b[3] + 1)
        idx = np.where(sel)[0]
        inside = Path(np.array(g.exterior.coords)).contains_points(pts[idx])
        for h in g.interiors:
            inside &= ~Path(np.array(h.coords)).contains_points(pts[idx])
        m.ravel()[idx[inside]] = True
    return m


M = raster(corr)
# greide: média ponderada do terreno ao longo do corredor (perfil suave, sem degraus)
s = 6.0
num = gaussian_filter(np.where(M, H1, 0), s); den = gaussian_filter(M.astype(float), s)
G = np.where(den > 1e-3, num / np.maximum(den, 1e-6), H1)
G = gaussian_filter(G, 2)
d = distance_transform_edt(~M) * R1
w = np.clip(1 - d / 8.0, 0, 1); w = w * w * (3 - 2 * w)          # taludes de 8 m
Hg = H1 * (1 - w) + G * w
Hg[M] = G[M] - 0.25          # terreno fica sob o pavimento
np.save(f'{D}/terreno_1m.npy', Hg.astype(np.float32))
np.save(f'{D}/greide_vias.npy', G.astype(np.float32))
np.save(f'{D}/vias_mascara_1m.npy', M)


# ---------------------------------------------------------------- triangulação
def tris(geom, step=3.0):
    """triângulos (x,y) cobrindo geom, com vértices internos a cada `step` m (p/ acompanhar o greide)."""
    out = []
    for g in getattr(geom, 'geoms', [geom]):
        if g.is_empty or g.area < 0.01:
            continue
        g = g.segmentize(step)
        b = g.bounds
        for x in np.arange(b[0], b[2], step * 4):
            for y in np.arange(b[1], b[3], step * 4):
                piece = g.intersection(box(x, y, x + step * 4, y + step * 4))
                for p in getattr(piece, 'geoms', [piece]):
                    if p.geom_type != 'Polygon' or p.area < 1e-4:
                        continue
                    for t in constrained_delaunay_triangles(p.segmentize(step)).geoms:
                        out.append(np.array(t.exterior.coords)[:3])
    return np.array(out, np.float32).reshape(-1, 3, 2)


def rings(geom):
    r = []
    for g in getattr(geom, 'geoms', [geom]):
        if g.geom_type != 'Polygon':
            continue
        r.append(np.array(g.segmentize(1.0).exterior.coords, np.float32))
        r += [np.array(h.coords, np.float32) for h in g.segmentize(1.0).interiors]
    return r


def only_poly(g):
    return MultiPolygon([p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon'])


out = {}
for nome, g in (('pista', pista), ('passeio', passeio), ('meiofio', unary_union([meiofio, canteiro_mf])),
                ('canteiro', grama_c)):
    g = only_poly(g)
    out[nome] = tris(g)
    rr = rings(g)
    out[nome + '_aneis'] = np.concatenate(rr) if rr else np.zeros((0, 2), np.float32)
    out[nome + '_aneis_n'] = np.array([len(x) for x in rr], np.int32)
    print(nome, len(out[nome]), 'triângulos')
np.savez_compressed(f'{D}/vias.npz', **out)
