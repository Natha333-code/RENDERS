"""Pisos: ruas, calçadas, lotes, canteiro central, ciclovia, pavers, faixas elevadas."""
import bpy, math
from shapely.geometry import Polygon, box as sbox
from shapely.ops import unary_union
import lib_common as C
import lib_materials as M


def to_polys(g):
    out = []
    geoms = g.geoms if hasattr(g, 'geoms') else [g]
    for pg in geoms:
        if pg.geom_type != 'Polygon' or pg.area < 1e-3:
            continue
        out.append({'ext': list(pg.exterior.coords)[:-1], 'holes': [list(h.coords)[:-1] for h in pg.interiors]})
    return out


def shp(polys):
    g = []
    for p in polys:
        g.append(Polygon(p['ext'], p['holes']).buffer(0))
    return unary_union(g)


# rampas da ciclovia (5 %) nas travessias - abscissas locais
RAMPAS = [(-44.4, -41.4, 'down'), (-11.8, -8.8, 'up'), (21.9, 24.9, 'down'), (54.6, 57.6, 'up')]


def z_ciclo_trav(x, y):
    z = C.zc_smooth(x)
    for a, b, k in RAMPAS:
        if a <= x <= b:
            t = (x - a) / (b - a)
            return z + C.RUA * (t if k == 'down' else 1 - t)
    if -41.4 < x < -11.8 or 24.9 < x < 54.6:
        return z + C.RUA
    return z


def z_rampa_faixa(x, y):
    # faixa elevada ocupa y∈[-0.8, 4.2]; rampas de 3 m ao norte e ao sul
    if y > 4.2:
        t = min((y - 4.2) / 3.0, 1)
    elif y < -0.8:
        t = min((-0.8 - y) / 3.0, 1)
    else:
        t = 0
    return C.zc_smooth(x) + C.RUA * t


def build(S):
    col = C.coll('Pisos')
    m_asf = M.pbr('asfalto', 'Asphalt025C', scale=3.0, macro=0.05, macro_scale=14, rough_mul=1.5, spec=0.35, hsv=(0.5, 0.8, 0.8))
    m_calc = M.pbr('calcada', 'Concrete031', scale=2.5, macro=0.1, hsv=(0.5, 0.6, 1.25))
    m_meiofio = M.pbr('meio_fio', 'Concrete034', scale=1.5, tint=(0.82, 0.82, 0.8), macro=0.05)
    m_grama = M.pbr('grama', 'Grass004', scale=1.8, macro=0.2, macro_scale=6, hsv=(0.5, 1.3, 0.75))
    m_lote = M.pbr('lote', 'Grass001', scale=2.2, macro=0.25, macro_scale=12, hsv=(0.49, 1.1, 0.9))
    m_paver = M.gen('paver_claro', 'paver_claro', 4.0)
    m_paver_esc = M.gen('paver_escuro', 'paver_escuro', 4.0)
    m_areia = M.pbr('areia', 'Ground079S', scale=2.0, macro=0.08, hsv=(0.5, 0.75, 1.25))
    m_pedrisco = M.pbr('pedrisco', 'Gravel041', scale=1.2, macro=0.1)
    m_branco = M.paint('tinta_branca', (0.8, 0.8, 0.78))
    m_vermelho_asf = M.paint('tinta_vermelha', (0.45, 0.04, 0.03), rough=0.55)
    m_ciclo = M.ciclovia_mat()

    # --------------------------------------------------------------- asfalto
    rua = sbox(-235, -75, 265, 80)
    quadras = [Polygon(q).buffer(0) for q in S['quadras']]
    lotes = unary_union([q for i, q in enumerate(quadras) if i not in (2, 3)])  # 2,3 = ELUP
    elup = unary_union([quadras[2], quadras[3]])
    calc = unary_union([q.buffer(3.0, join_style=2) for q in quadras]).difference(unary_union(quadras))
    calc = calc.intersection(rua)
    C.poly_mesh('asfalto', to_polys(rua), col, m_asf, z=C.RUA, step=2.0)
    C.poly_mesh('calcadas', to_polys(calc), col, m_calc, z=0.0, thick=0.4, rim_mat=m_meiofio, step=2.0)
    C.poly_mesh('lotes', to_polys(lotes.intersection(rua)), col, m_lote, z=0.02, thick=0.4, rim_mat=m_calc, step=2.0)
    # entorno distante (campo) - bem além das quadras
    far = sbox(-2500, -2500, 2500, 2500).difference(rua)
    C.poly_mesh('entorno', to_polys(far), col, m_lote, z=0.05, step=25.0)
    # piso da Área de Espaços Livres (mata) e trilha de pedrisco
    m_mata = M.pbr('solo_mata', 'Ground037', scale=3.0, macro=0.25, hsv=(0.5, 1.1, 0.45))
    C.poly_mesh('elup', to_polys(elup.intersection(rua).difference(shp(S['trilha']))), col, m_mata, z=0.02,
                thick=0.4, rim_mat=m_calc, step=2.0)
    C.poly_mesh('trilha', S['trilha'], col, m_pedrisco, z=0.03, step=1.0)

    # --------------------------------------------------------------- canteiro
    cant = unary_union([shp(c) for c in S['canteiro']])
    cant_polys = to_polys(cant)
    C.poly_mesh('canteiro_grama', cant_polys, col, m_grama, z=-0.01, thick=0.45, rim_mat=m_meiofio, step=1.0)

    E = 0.004  # afastamento anti z-fighting
    C.poly_mesh('ciclovia', S['ciclovia'], col, m_ciclo, z=E, thick=0.02, rim_mat=m_ciclo, step=0.5)
    C.poly_mesh('ciclovia_centro', S['ciclovia_centro'], col, m_ciclo, z=E, step=0.5)
    C.poly_mesh('ciclovia_travessia', S['ciclovia_travessia'], col, m_ciclo, z=E, zfun=z_ciclo_trav, step=0.25)

    # pavers dos caminhos, estares e contorno da quadra
    C.poly_mesh('paver', S['paver'], col, m_paver, z=E, thick=0.02, rim_mat=m_meiofio, step=0.5)
    # Food Parque: faixas claras e escuras
    C.poly_mesh('fp_claro', S['fp_claro'], col, m_paver, z=E, step=0.5)
    C.poly_mesh('fp_escuro', S['fp_escuro'], col, m_paver_esc, z=E, step=0.5)
    # faixas elevadas em paver + rampas asfálticas
    C.poly_mesh('faixa_elevada', S['faixa_elevada'], col, m_paver, z=0.0, thick=0.3, rim_mat=m_meiofio, step=0.5)
    C.poly_mesh('rampas_faixa', S['rampas_faixa'], col, m_asf, z=0.0, zfun=z_rampa_faixa, step=0.5)
    zebra = [{'ext': p, 'holes': []} for p in S['zebra']]
    C.poly_mesh('zebra', zebra, col, m_branco, z=0.006, step=0)
    tri = [{'ext': p, 'holes': []} for p in S['triangulos'] + S['linhas_retencao']]
    C.poly_mesh('triangulos', tri, col, m_branco, z=0.006, zfun=z_rampa_faixa, step=0.3)

    # areias (quadra e espaço kids) levemente rebaixadas
    C.poly_mesh('areia_quadra', S['quadra_areia'], col, m_areia, z=0.012, step=1.0)
    C.poly_mesh('areia_kids', S['kids_areia'], col, m_areia, z=0.008, step=1.0)

    # eixo tracejado da ciclovia + bordos
    (x0, y0), (x1, y1) = S['eixo_ciclovia']
    dashes = []
    x = -170.0
    while x < 170:
        dashes.append({'ext': [(x, 11.45), (x + 1.0, 11.45), (x + 1.0, 11.55), (x, 11.55)], 'holes': []})
        x += 2.0
    dg = shp(dashes).intersection(shp(S['ciclovia']).union(shp(S['ciclovia_centro'])).buffer(-0.15))
    C.poly_mesh('eixo_ciclovia', to_polys(dg), col, m_branco, z=E + 0.003, step=0.5)
    dg2 = shp(dashes).intersection(shp(S['ciclovia_travessia']))
    C.poly_mesh('eixo_ciclovia_trav', to_polys(dg2), col, m_branco, z=E + 0.003, zfun=z_ciclo_trav, step=0.25)
    return cant
