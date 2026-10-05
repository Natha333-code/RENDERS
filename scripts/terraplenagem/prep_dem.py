"""Prepara o DEM da terraplenagem (Plato Geral - Rua B) a partir do DWG + LandXML.

  dwg2dxf -y -o terr.dxf "Terraplanagem AEIs R02-Model(AutoCAD).dwg"
  python3 ../tools/fix_dxf.py terr.dxf terr_fixed.dxf
  python3 prep_dem.py terr_fixed.dxf "Terraplanagem AEIs R02.xml" dem.npz

Fontes (todas do projeto):
  * terreno final no plato ....... LandXML "PLATO GERAL - RUA B" (TIN exato)
  * terreno final no entorno ..... curvas T-HM-CURVA_* do DWG (já modeladas)
  * terreno natural sob o corte .. curvas fora da mancha A-MODELAGEM +
                                   perfis de Terreno Natural dos cortes AA', BB',
                                   CC', DD' e do passeio da Rua C
  * mancha de corte/aterro ....... SOLIDs da camada A-MODELAGEM (cor 11 corte, 161 aterro)
  * vias / calçadas / quadras .... URB-Quadras, URB-Calçadas
"""
import sys, json, numpy as np
import xml.etree.ElementTree as ET
from ezdxf import recover
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from shapely import contains_xy
from scipy.interpolate import LinearNDInterpolator, CloughTocher2DInterpolator
from scipy.ndimage import gaussian_filter, distance_transform_edt

DXF, LXML, OUT = sys.argv[1:4]
X0, X1, Y0, Y1, R = 340610., 341000., 6994400., 6994790., 0.25

doc, _ = recover.readfile(DXF)
msp = doc.modelspace()

# ---------------- LandXML
ns = '{http://www.landxml.org/schema/LandXML-1.2}'
root = ET.parse(LXML).getroot()
surf = root.find(f'.//{ns}Surface')
P = {}
for p in surf.iter(ns + 'P'):
    n, e, z = map(float, p.text.split()); P[p.get('id')] = (e, n, z)
TRI = np.array([[P[i] for i in f.text.split()] for f in surf.iter(ns + 'F') if f.get('i') != '1'])
print('LandXML', surf.get('name'), len(P), 'pontos', len(TRI), 'triângulos')

# ---------------- curvas de nível
cp = []
for e in msp.query('LWPOLYLINE'):
    if not e.dxf.layer.startswith('T-HM-CURVA'):
        continue
    p = np.array(e.get_points('xy'))
    if p[:, 0].max() < X0 - 200 or p[:, 0].min() > X1 + 200 or p[:, 1].max() < Y0 - 200 or p[:, 1].min() > Y1 + 200:
        continue
    if e.is_closed:
        p = np.vstack([p, p[:1]])
    z = e.dxf.elevation
    for a, b in zip(p[:-1], p[1:]):
        k = max(1, int(np.hypot(*(b - a)) / 1.5))
        for t in np.arange(k) / k:
            cp.append((*(a + (b - a) * t), z))
cp = np.unique(np.round(np.array(cp), 2), axis=0)

# ---------------- mancha de corte/aterro (A-MODELAGEM)
cf = {11: [], 161: []}
for e in msp.query('SOLID[layer=="A-MODELAGEM"]'):
    q = np.array([tuple(e.dxf.get(k))[:2] for k in ('vtx0', 'vtx1', 'vtx3', 'vtx2')])
    pg = Polygon(q).buffer(0)
    if pg.area > 1e-6 and e.dxf.color in cf:
        cf[e.dxf.color].append(pg.buffer(0.02))
CUT, FILL = unary_union(cf[11]), unary_union(cf[161])
FOOT = unary_union([CUT, FILL]).buffer(1.0)


# ---------------- perfis de terreno natural
def prof(x0):
    for e in msp.query('LWPOLYLINE[layer=="F-VT-TERRENO"]'):
        p = np.array(e.get_points('xy'))
        if abs(p[:, 0].min() - x0) < 3:
            return p


# (início, fim do alinhamento, x inicial do perfil, y da régua, cota da régua)  – escala V = 2x H
VIEWS = [((340764.6, 6994616.0), (340840.4, 6994533.8), 341173.2, 6994967.7, 724),   # AA'
         ((340818.8, 6994605.6), (340773.7, 6994571.4), 341161.5, 6995077.4, 726),   # BB'
         ((340836.6, 6994586.8), (340794.9, 6994548.5), 341242.1, 6995077.4, 724),   # CC'
         ((340852.2, 6994569.9), (340810.5, 6994531.6), 341201.7, 6995024.5, 722)]   # DD'
tn = []
for A, B, tx, by, be in VIEWS:
    ls = LineString([A, B]); t = prof(tx); x0 = t[:, 0].min()
    for s in np.arange(0, ls.length, 1.0):
        q = ls.interpolate(s)
        if FOOT.contains(q):
            tn.append((q.x, q.y, np.interp(x0 + s, t[:, 0], be + (t[:, 1] - by) / 2)))
for e in msp.query('LWPOLYLINE[layer=="Alinhamento"]'):          # passeio de acesso Rua C
    p = np.array(e.get_points('xy'))
    if len(p) == 4:
        ls = LineString(p); t = prof(340666.6); x0 = t[:, 0].min()
        for s in np.arange(0, ls.length, 1.0):
            q = ls.interpolate(s)
            if FOOT.contains(q):
                tn.append((q.x, q.y, np.interp(x0 + s, t[:, 0], 718 + (t[:, 1] - 6993913.4) / 2)))
tn = np.array(tn)
print('pontos de terreno natural dos perfis:', len(tn))

# ---------------- grades
xs = np.arange(X0, X1 + 1e-6, R); ys = np.arange(Y0, Y1 + 1e-6, R)
GX, GY = np.meshgrid(xs, ys)


def fillnan(A):
    idx = distance_transform_edt(np.isnan(A), return_distances=False, return_indices=True)
    return A[tuple(idx)]


inside = contains_xy(FOOT, cp[:, 0], cp[:, 1])
egp = np.vstack([cp[~inside], tn])
EG = CloughTocher2DInterpolator(egp[:, :2], egp[:, 2])(GX, GY)
EG = np.where(np.isnan(EG), LinearNDInterpolator(egp[:, :2], egp[:, 2])(GX, GY), EG)
FIN = LinearNDInterpolator(cp[:, :2], cp[:, 2])(GX, GY)

LZ = np.full(GX.shape, np.nan)                                  # rasteriza o TIN do LandXML
for T in TRI:
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = T
    i0 = max(0, int((min(x1, x2, x3) - X0) / R)); i1 = int((max(x1, x2, x3) - X0) / R) + 2
    j0 = max(0, int((min(y1, y2, y3) - Y0) / R)); j1 = int((max(y1, y2, y3) - Y0) / R) + 2
    gx, gy = GX[j0:j1, i0:i1], GY[j0:j1, i0:i1]
    det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(det) < 1e-12:
        continue
    l1 = ((y2 - y3) * (gx - x3) + (x3 - x2) * (gy - y3)) / det
    l2 = ((y3 - y1) * (gx - x3) + (x1 - x3) * (gy - y3)) / det
    l3 = 1 - l1 - l2
    m = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
    LZ[j0:j1, i0:i1][m] = (l1 * z1 + l2 * z2 + l3 * z3)[m]
LX = ~np.isnan(LZ)
FIN = fillnan(FIN); EG = fillnan(EG)
# concordância: talude de ~2,5 m entre a borda do LandXML e o terreno do entorno
dlx, idx = distance_transform_edt(~LX, return_indices=True)
zedge = np.where(LX, LZ, 0)[tuple(idx)]
tt = np.clip(dlx * R / 2.5, 0, 1); tt = tt * tt * (3 - 2 * tt)
FIN = np.where(LX, LZ, zedge * (1 - tt) + FIN * tt)

# suaviza o que vem das curvas (degraus da interpolação), mantendo o LandXML exato
w = np.clip((distance_transform_edt(~LX) * R - 2.5) / 3.0, 0, 1)
FIN = FIN * (1 - w) + gaussian_filter(FIN, 1.8 / R) * w
footm = contains_xy(FOOT.buffer(0.5), GX, GY)
EG = np.where(footm, EG * (1 - w) + gaussian_filter(EG, 1.8 / R) * w, FIN)
dz = FIN - EG
dz[~footm] = 0
dz *= np.clip(distance_transform_edt(footm) * R / 1.0, 0, 1)
EG = FIN - dz

cutm = contains_xy(CUT, GX, GY); film = contains_xy(FILL, GX, GY)
print('coerência com A-MODELAGEM: corte %.0f%%  aterro %.0f%%' % (
    100 * np.mean(dz[cutm] < 0), 100 * np.mean(dz[film] > 0)))
A = R * R
vol = dict(area_plato=float(LX.sum() * A),
           corte_plato=float(-dz[LX & (dz < 0)].sum() * A), aterro_plato=float(dz[LX & (dz > 0)].sum() * A),
           corte_total=float(-dz[dz < 0].sum() * A), aterro_total=float(dz[dz > 0].sum() * A),
           dz_min=float(dz.min()), dz_max=float(dz.max()))
print(json.dumps(vol, indent=1))

# ---------------- vias, calçadas, quadras
qs = [Polygon(np.array(e.get_points('xy'))).buffer(0) for e in msp.query('LWPOLYLINE[layer=="URB-Quadras"]')
      if len(e) >= 3]
Q = unary_union([q for q in qs if q.area > 100])
qb = unary_union([LineString(np.array(e.get_points('xy'))) for e in msp.query('LWPOLYLINE[layer=="URB-Quadras"]')
                  if len(e) >= 2])
cl = [LineString(np.array(e.get_points('xy'))) for e in msp.query('LWPOLYLINE[layer=="URB-Calçadas"]') if len(e) >= 2]
dd = [qb.distance(Point(c)) for l in cl for c in l.coords]
ws = float(np.median([d for d in dd if d < 6]))
inQ = contains_xy(Q, GX, GY)
inS = contains_xy(Q.buffer(ws), GX, GY) & ~inQ
cm = np.zeros(GX.shape, bool)
for l in cl:
    for s in np.linspace(0, l.length, int(l.length / 0.1) + 2):
        q = l.interpolate(s)
        i = int(round((q.x - X0) / R)); j = int(round((q.y - Y0) / R))
        if 0 <= i < len(xs) and 0 <= j < len(ys):
            cm[j, i] = True
road = ~inQ & ~inS & (distance_transform_edt(~cm) * R < 11)
print('calçada %.2f m' % ws)

# limite do plato (LandXML) para desenhar na imagem
lxpoly = unary_union([Polygon(t[:, :2]).buffer(0.01) for t in TRI]).buffer(-0.01)
lxpoly = max(getattr(lxpoly, 'geoms', [lxpoly]), key=lambda g: g.area)
bnd = np.array(lxpoly.exterior.coords)

np.savez_compressed(OUT, xs=xs, ys=ys, FIN=FIN.astype(np.float32), EG=EG.astype(np.float32),
                    dz=dz.astype(np.float32), lx=LX, foot=footm, inQ=inQ, inS=inS, road=road,
                    lxbnd=bnd, vol=json.dumps(vol))
