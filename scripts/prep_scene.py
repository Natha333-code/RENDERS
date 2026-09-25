"""Extrai do DXF (convertido do DWG PAL-RRA-URB-R10) todos os dados de cena
usados pelo Blender: polígonos de piso, contorno do canteiro, cotas e a
posição de cada árvore / mobiliário.  Coordenadas locais em metros com
origem em (162840, 239970) do projeto.  Uso:
    python3 prep_scene.py ents.json objs.json scene.json
"""
import json, math, sys
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union

ENTS, OBJS, OUT = sys.argv[1:4]
E = json.load(open(ENTS))
R = json.load(open(OBJS))
OX, OY = 162840.0, 239970.0


def L(p):
    return (round(p[0] - OX, 4), round(p[1] - OY, 4))


def loops(k):
    return [[L(p) for p in s] for s in E[k]['p'] if len(s) > 2]


def evenodd(k):
    """Hatch -> shapely geometry (regra par-ímpar entre os contornos)."""
    g = None
    for s in E[k]['p']:
        if len(s) < 3:
            continue
        pg = Polygon([L(p) for p in s]).buffer(0)
        g = pg if g is None else g.symmetric_difference(pg)
    return g


def pts(k):
    return [L(p) for p in E[k]['p'][0]]


def geo_to_loops(g):
    out = []
    if g is None or g.is_empty:
        return out
    geoms = g.geoms if hasattr(g, 'geoms') else [g]
    for pg in geoms:
        if pg.geom_type != 'Polygon' or pg.area < 1e-4:
            continue
        out.append({'ext': [tuple(map(lambda v: round(v, 4), c)) for c in pg.exterior.coords[:-1]],
                    'holes': [[tuple(map(lambda v: round(v, 4), c)) for c in h.coords[:-1]] for h in pg.interiors]})
    return out


S = {}

# ---------------------------------------------------------------- canteiro
left = pts(104415) + pts(39615) + [L((162806.3, 239974.2))] + pts(104420) + [L((162795.6, 239982.9))]
right = pts(104416) + pts(104401) + [L((162886.8, 239974.2))] + pts(104422) + [L((162894.6, 239982.9))]
center = pts(104421) + [L((162874.2, 239974.2))] + pts(104423) + [L((162861.9, 239982.9)), L((162831.2, 239982.9))] + pts(109)
cant = [Polygon(c).buffer(0) for c in (left, right, center)]
S['canteiro'] = [geo_to_loops(c) for c in cant]

# ---------------------------------------------------------------- pisos
ciclo = evenodd(99415)
S['ciclovia'] = geo_to_loops(ciclo)
# ciclovia pintada no asfalto nas travessias (faixas elevadas)
S['ciclovia_travessia'] = geo_to_loops(unary_union([evenodd(k) for k in (104408, 104409, 104404, 104405, 104406, 104407)]))
# ciclovia sobre o Food Parque (entre travessias) - continua em concreto vermelho
S['ciclovia_centro'] = geo_to_loops(Polygon([L((162831.2, 239980.1)), L((162861.9, 239980.1)), L((162861.9, 239982.9)), L((162831.2, 239982.9))]))

paver = unary_union([evenodd(k) for k in (104263, 104265)])
S['paver'] = geo_to_loops(paver)
S['faixa_elevada'] = geo_to_loops(unary_union([evenodd(104277), evenodd(104278)]))
S['rampas_faixa'] = geo_to_loops(unary_union([evenodd(104279), evenodd(104280)]))
zebra = [k for k in range(104424, 104472) if E[k]['t'] == 'LWPOLYLINE' and len(E[k]['p'][0]) == 5]
S['zebra'] = [pts(k) for k in zebra]
tri = [k for k in range(104472, 104528) if E[k]['t'] == 'LWPOLYLINE' and len(E[k]['p'][0]) == 4]
S['triangulos'] = [pts(k) for k in tri]
S['linhas_retencao'] = [pts(k) for k in (104496, 104497, 104525, 104527)]

# Food Parque: paver claro (7) e escuro (252) em faixas
fp_all = unary_union([evenodd(k) for k in (99416, 99417, 39376, 39405)])
# faixas de 0,5 m alternando paver escuro / claro nas duas alas (linhas do DWG
# em x = 162819,1 ... 162832,6 e 162860,6 ... 162874,1)
dark = []
for xa, xb, step in ((162832.6, 162818.6, -0.5), (162860.6, 162874.6, 0.5)):
    n = int(round((xb - xa) / step))
    for i in range(n):
        if i % 2 == 0:
            u0, u1 = sorted((xa + i * step - OX, xa + (i + 1) * step - OX))
            dark.append(Polygon([(u0, -20), (u1, -20), (u1, 20), (u0, 20)]))
fp_dark = fp_all.intersection(unary_union(dark))
S['fp_escuro'] = geo_to_loops(fp_dark)
S['fp_claro'] = geo_to_loops(fp_all.difference(fp_dark))
S['palco'] = geo_to_loops(evenodd(30323))
# bancos perimetrais quadrados (contorno externo 2x2) com jerivá
bq = []
for k in (30316, 30319, 30322, 30328, 30331, 30334):
    p = pts(k)
    xs = [a[0] for a in p]; ys = [a[1] for a in p]
    bq.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs)))
S['bancos_quadrados'] = bq
S['canteiros_curvos'] = [pts(30337), pts(30338)]
S['totem'] = geo_to_loops(evenodd(99419))
S['canteiro_totem'] = geo_to_loops(evenodd(99418))
S['totem_arco'] = [pts(46878), pts(46879), pts(46880), pts(46881)]

# areia
S['quadra_areia'] = geo_to_loops(evenodd(39616))
S['kids_areia'] = geo_to_loops(evenodd(99420))
S['pet_grama'] = geo_to_loops(evenodd(104267))
# anel/soleira das cercas (pet e kids)
S['cerca_pet'] = [L(p) for p in E[99805]['p'][0]]
S['cerca_kids'] = [L(p) for p in E[99815]['p'][0]]
S['cerca_quadra'] = [L(p) for p in E[99810]['p'][0]]
S['arquibancadas'] = [pts(99479), pts(99480)]
S['arquibancadas_hatch'] = geo_to_loops(evenodd(99481))
S['eixo_ciclovia'] = pts(39342)
S['trilha'] = geo_to_loops(evenodd(105365))

# piso tátil (blocos 'piso tatik') - quadradinhos 0,4 m
tat = []
for o in E:
    if o['b'] == 'piso tatik' and o['t'] == 'HATCH':
        p = [L(q) for q in o['p'][0]]
        xs = [a[0] for a in p]; ys = [a[1] for a in p]
        if -170 < min(xs) < 170 and -15 < min(ys) < 15:
            tat.append(p)
S['tatil'] = tat

# ------------------------------------------------------------ quadras/lotes
qd = []
for k in (4, 18, 35, 74, 89, 96, 98, 102, 104, 108, 126):
    p = pts(k)
    if len(p) >= 3:
        qd.append(p)
S['quadras'] = qd

# ------------------------------------------------------------ cotas
# cotas de piso do projeto (COTAPISO) - perfil longitudinal do canteiro
S['perfil'] = [(-240, 621.0), (50, 621.0), (69, 619.0), (96, 617.0), (108, 616.0),
               (143, 612.0), (170, 612.0), (200, 610.5), (280, 608.0)]

# ------------------------------------------------------------ objetos
MAP = {'Quares': 'quaresmeira', 'EXTREMOSA BRANCA': 'extremosa', 'LD ARV PB 061': 'jeriva',
       'Árvore05': 'moreia', 'bela emilia': 'belaemilia', 'jacaranda': 'manaca',
       'VE (10)': 'ipe', 'A$C3E835100': 'jaboticabeira', 'banco': 'banco',
       'lixeirass': 'lixeira', 'palet': 'palet', 'BICICLETARIO': 'bicicletario',
       'bebedouro': 'bebedouro', 'GRELHA ARVORE': 'grelha', 'LD CASINHA PB 002': 'playground',
       'per': 'pet_brinquedo', 'BICICLETASIMBOLO': 'pictograma_bici',
       'INICIO_SETA': 'seta', 'FIM_SETA': 'seta_fim'}
objs = []
for r in R:
    t = MAP.get(r['b'])
    if not t:
        continue
    objs.append({'t': t, 'x': round(r['cx'] - OX, 3), 'y': round(r['cy'] - OY, 3),
                 'rot': r['rot'], 'w': r['w'], 'h': r['h']})
# araucárias existentes (bloco p1) na Área de Espaços Livres
import collections
g = collections.defaultdict(list)
for o in E:
    if o['b'] == 'p1' and o.get('i') is not None:
        for s in o['p']:
            g[o['i']].extend(s)
for i, pp in g.items():
    xs = [p[0] for p in pp]; ys = [p[1] for p in pp]
    objs.append({'t': 'araucaria', 'x': round((min(xs) + max(xs)) / 2 - OX, 3),
                 'y': round((min(ys) + max(ys)) / 2 - OY, 3), 'rot': 0,
                 'w': max(xs) - min(xs), 'h': max(ys) - min(ys)})
S['objetos'] = objs
json.dump(S, open(OUT, 'w'))
import collections as C
print(C.Counter(o['t'] for o in objs))
print({k: (len(v) if isinstance(v, list) else v) for k, v in S.items() if k != 'objetos'})
