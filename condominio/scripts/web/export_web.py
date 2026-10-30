"""Exporta a geometria da maquete interativa (web/dados) a partir de dados/:
 - terreno_nucleo.bin (2 m), terreno_entorno.bin (16 m), terreno_horizonte.bin (200 m): Float32;
 - vias.bin: pista, passeio, meio-fio, canteiros e espelhos (triângulos xyz, Float32);
 - edificacoes.bin: prédios do OSM e casas do entorno (triângulos xyz + cor RGB);
 - linhas.json: perímetro, lotes e quadras (polilinhas com cota);
 - texturas de detalhe reduzidas (paver, grama, concreto) e minimapa;
 - cena.json: metadados (grades, deslocamentos dos blocos, pontos de vista).
Coordenadas locais em metros: x = leste, y = norte, z = cota (origem E 383400, N 6852450).
Uso: python3 export_web.py dados_dir saida_dir"""
import sys, json, math
from glob import glob
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, minimum_filter

D, OUT = sys.argv[1], sys.argv[2]
ASSETS = '/home/user/assets/tex'
J = json.load(open(f'{D}/cena_terreno.json'))
H1 = np.load(f'{D}/terreno_1m.npy').astype(np.float64)
H8 = np.load(f'{D}/terreno_8m.npy').astype(np.float64)
H100 = np.load(f'{D}/terreno_100m.npy').astype(np.float64)
G = np.load(f'{D}/greide_vias.npy').astype(np.float64)
MV = np.load(f'{D}/vias_mascara_1m.npy')
X1, Y1, R1 = J['x0_1m'], J['y0_1m'], J['res1']
HALF, R8, HF, R100 = J['half'], J['r8'], J['half100'], J['r100']
meta = dict(origem=J['origem'])


def bil(H, x0, y0, r, x, y):
    c = (np.asarray(x) - x0) / r; rr = (np.asarray(y) - y0) / r
    c = np.clip(c, 0, H.shape[1] - 1.001); rr = np.clip(rr, 0, H.shape[0] - 1.001)
    c0 = np.floor(c).astype(int); r0 = np.floor(rr).astype(int); fc = c - c0; fr = rr - r0
    return (H[r0, c0] * (1 - fc) * (1 - fr) + H[r0, c0 + 1] * fc * (1 - fr) +
            H[r0 + 1, c0] * (1 - fc) * fr + H[r0 + 1, c0 + 1] * fc * fr)


def altura(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    z = bil(H8, -HALF, -HALF, R8, x, y)
    dentro = (x >= X1) & (x <= X1 + (H1.shape[1] - 1) * R1) & (y >= Y1) & (y <= Y1 + (H1.shape[0] - 1) * R1)
    z[dentro] = bil(H1, X1, Y1, R1, x[dentro], y[dentro])
    return z


# ---------------------------------------------------------------- terreno
# núcleo 2 m: junto às vias usa o mínimo local (o terreno não aflora pelo pavimento)
perto = binary_dilation(MV, iterations=4)
Hn = np.where(perto, minimum_filter(H1, 3), H1)[::2, ::2]
Hn.astype('<f4').tofile(f'{OUT}/terreno_nucleo.bin')
He = H8[::2, ::2]; He.astype('<f4').tofile(f'{OUT}/terreno_entorno.bin')
Hh = H100[::2, ::2]; Hh.astype('<f4').tofile(f'{OUT}/terreno_horizonte.bin')
meta['grades'] = dict(
    nucleo=dict(x0=X1, y0=Y1, res=2 * R1, nx=Hn.shape[1], ny=Hn.shape[0], dz=0.0),
    entorno=dict(x0=-HALF, y0=-HALF, res=2 * R8, nx=He.shape[1], ny=He.shape[0], dz=-0.8),
    horizonte=dict(x0=-HF, y0=-HF, res=2 * R100, nx=Hh.shape[1], ny=Hh.shape[0], dz=-2.5))
meta['cota_base'] = J['cota_base']

# ---------------------------------------------------------------- vias (mesmas cotas do build_vias.py)
V = np.load(f'{D}/vias.npz')
ALT = 0.15
zg = lambda x, y: bil(G, X1, Y1, R1, x, y)


def tris(T, dz):
    co = T.reshape(-1, 2).astype(np.float64)
    z = zg(co[:, 0], co[:, 1]) + dz
    P = np.c_[co, z].reshape(-1, 3, 3)
    # normais para cima
    nz = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])[:, 2]
    P[nz < 0] = P[nz < 0][:, ::-1]
    return P.reshape(-1, 3)


def paredes(R, Rn, top, bot):
    out = []; i0 = 0
    for n in Rn:
        ring = R[i0:i0 + n].astype(np.float64); i0 += n
        z = zg(ring[:, 0], ring[:, 1])
        for k in range(n - 1):
            a = (*ring[k], z[k] + top); b = (*ring[k + 1], z[k + 1] + top)
            c = (*ring[k + 1], z[k + 1] + bot); d = (*ring[k], z[k] + bot)
            out += [a, b, c, a, c, d]
    return np.array(out).reshape(-1, 3)


blocos = {}
blocos['pista'] = np.r_[tris(V['pista'], 0.0), paredes(V['pista_aneis'], V['pista_aneis_n'], 0.0, -0.30)]
blocos['passeio'] = tris(V['passeio'], ALT)
blocos['meiofio'] = np.r_[tris(V['meiofio'], ALT + 0.005)]
blocos['canteiro'] = tris(V['canteiro'], ALT - 0.03)
blocos['espelho'] = np.r_[tuple(paredes(V[k + '_aneis'], V[k + '_aneis_n'], ALT, -0.30)
                                for k in ('passeio', 'meiofio', 'canteiro'))]
ofs = 0; meta['vias'] = {}
with open(f'{OUT}/vias.bin', 'wb') as f:
    for k, P in blocos.items():
        a = P.astype('<f4'); f.write(a.tobytes())
        meta['vias'][k] = [ofs, len(a)]; ofs += len(a)

# ---------------------------------------------------------------- edificações do entorno
rng = np.random.default_rng(3)
pos, cor = [], []


def quad(a, b, c, d, col):
    pos.extend([a, b, c, a, c, d]); cor.extend([col] * 6)


def tri(a, b, c, col):
    pos.extend([a, b, c]); cor.extend([col] * 3)


def parede_cor():
    return np.clip(np.array([0.78, 0.75, 0.70]) * rng.uniform(0.75, 1.05) + rng.normal(0, 0.03, 3), 0.2, 0.9)


from shapely.geometry import Polygon
from shapely import constrained_delaunay_triangles
for pr in J['predios']:
    p = np.array(pr['p'])[:-1]
    if len(p) < 3: continue
    z0 = float(altura(p[:, 0], p[:, 1]).min()) - 0.3
    z1 = z0 + 0.3 + pr['h']
    pc = parede_cor(); rc = np.array(pr['cor'])
    # sentido anti-horário (paredes viradas para fora)
    if Polygon(p).exterior.is_ccw is False: p = p[::-1]
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1), pc)
    try:
        for t in constrained_delaunay_triangles(Polygon(p)).geoms:
            c = np.array(t.exterior.coords)[:3]
            if Polygon(c).exterior.is_ccw is False: c = c[::-1]
            tri(*[(x, y, z1) for x, y in c], rc)
    except Exception:
        pass
for x, y, w, l, h, rz, r, g, b in J['casas']:
    ca, sa = math.cos(rz), math.sin(rz)
    L = lambda u, v, z: (x + u * ca - v * sa, y + u * sa + v * ca, z)
    hw, hl = w / 2, l / 2
    z0 = float(altura(np.array([L(-hw, -hl, 0)[0], L(hw, hl, 0)[0]]), np.array([L(-hw, -hl, 0)[1], L(hw, hl, 0)[1]])).min()) - 0.3
    zt = z0 + 0.3 + h; zr = zt + 0.38 * h * 0.55
    pc = parede_cor(); rc = np.array([r, g, b])
    cs = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]
    for i in range(4):
        (u0, v0), (u1, v1) = cs[i], cs[(i + 1) % 4]
        quad(L(u0, v0, z0), L(u1, v1, z0), L(u1, v1, zt), L(u0, v0, zt), pc)
    # oitões (empena ao longo de v) e águas do telhado
    tri(L(-hw, -hl, zt), L(hw, -hl, zt), L(0, -hl, zr), pc)
    tri(L(hw, hl, zt), L(-hw, hl, zt), L(0, hl, zr), pc)
    quad(L(hw, -hl - 0.4, zt - 0.2), L(hw, hl + 0.4, zt - 0.2), L(0, hl + 0.4, zr), L(0, -hl - 0.4, zr), rc)
    quad(L(-hw, hl + 0.4, zt - 0.2), L(-hw, -hl - 0.4, zt - 0.2), L(0, -hl - 0.4, zr), L(0, hl + 0.4, zr), rc)
P = np.array(pos, '<f4'); Cc = (np.clip(np.array(cor), 0, 1) * 255).astype(np.uint8)
with open(f'{OUT}/edificacoes.bin', 'wb') as f:
    f.write(P.tobytes()); f.write(Cc.tobytes())
meta['edificacoes'] = len(P)

# ---------------------------------------------------------------- linhas (perímetro, lotes, quadras)


def drape(p, step=2.0, dz=0.12):
    p = np.array(p, float); out = [p[0]]
    for a, b in zip(p[:-1], p[1:]):
        n = max(1, int(np.hypot(*(b - a)) / step))
        out += [a + (b - a) * t for t in np.arange(1, n + 1) / n]
    out = np.array(out)
    z = altura(out[:, 0], out[:, 1])
    # sobre as vias, acompanha o pavimento
    zv = zg(out[:, 0], out[:, 1]) + ALT
    c = np.round((out[:, 0] - X1) / R1).astype(int); r = np.round((out[:, 1] - Y1) / R1).astype(int)
    ok = (c >= 0) & (c < MV.shape[1]) & (r >= 0) & (r < MV.shape[0])
    via = np.zeros(len(out), bool); via[ok] = MV[r[ok], c[ok]]
    z = np.where(via, np.maximum(z, zv), z) + dz
    return np.c_[out, z].round(2).tolist()


lin = dict(perimetro=drape(J['perimetro'], dz=0.25), lotes=[drape(l) for l in J['lotes']],
           quadras=[drape(q) for q in J['quadras']])
json.dump(lin, open(f'{OUT}/linhas.json', 'w'), separators=(',', ':'))


# ---------------------------------------------------------------- texturas de detalhe e minimapa
def reduz(src, dst, px=1024, q=85):
    im = Image.open(src).convert('RGB'); im = im.resize((px, px), Image.LANCZOS); im.save(dst, quality=q)


reduz(f'{ASSETS}/gen/paver_escuro_color.jpg', f'{OUT}/paver_pista.jpg')
reduz(f'{ASSETS}/gen/paver_claro_color.jpg', f'{OUT}/paver_passeio.jpg')
reduz(sorted(glob(f'{ASSETS}/Concrete034/*Color*'))[0], f'{OUT}/concreto.jpg', 512)
reduz(sorted(glob(f'{ASSETS}/Grass004/*Color*'))[0], f'{OUT}/grama.jpg', 1024)
mp = Image.open('renders/planta.jpg'); mp.thumbnail((720, 900)); mp.save(f'{OUT}/minimapa.jpg', quality=82)
# planta: câmera ortogonal em (-10, 40), 900 m na vertical, 1600 x 2000 px
meta['minimapa'] = dict(x0=-10 - 360, x1=-10 + 360, y0=40 - 450, y1=40 + 450)

# ---------------------------------------------------------------- pontos de vista (os mesmos dos renders;
# z < 30: altura sobre o terreno, senão cota = z + 620)
meta['vistas'] = {
    'Rua de acesso': ((-86, 118, 1.65), (-62, 0, 0.8)),
    'Rua das quadras': ((14, -128, 1.65), (-45, -204, 0.6)),
    'Clareira no topo': ((-20, -212, 1.65), (-80, 60, 1.0)),
    'Acesso norte': ((-92, 168, 1.65), (-60, -100, 1.0)),
    'Aérea das vias': ((170, -330, 140), (-45, -90, 0)),
    'Aérea sudeste': ((520, -560, 300), (-30, 20, 0)),
    'Aérea sudoeste': ((-560, -520, 300), (-20, 30, 0)),
    'Drone alto': ((300, -380, 650), (-15, 30, 0)),
}
meta['zmin'], meta['zmax'] = J['zmin'], J['zmax']
json.dump(meta, open(f'{OUT}/cena.json', 'w'), indent=1, ensure_ascii=False)
print('vias', {k: v[1] // 3 for k, v in meta['vias'].items()}, 'edificações (tri)', len(P) // 3)

# o servidor de artefatos não serve .bin: binários vão em base64 (.txt), decodificados no navegador
import base64, os
for f in glob(f'{OUT}/*.bin'):
    open(f[:-4] + '.txt', 'w').write(base64.b64encode(open(f, 'rb').read()).decode())
    os.remove(f)
