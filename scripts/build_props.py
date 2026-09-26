"""Mobiliário e equipamentos conforme memorial descritivo e posições do DWG."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
import lib_common as C
import lib_materials as M
from lib_common import zc_smooth as Z

random.seed(11)


# ---------------------------------------------------------------- materiais
def mats():
    return dict(
        grafite=M.flat('metal_grafite', (0.045, 0.047, 0.05), rough=0.45, metal=0.6, coat=0.2),
        galv=M.pbr('galvanizado', 'Metal032', scale=0.6, tint=(0.75, 0.76, 0.78), macro=0.0, normal=0.3),
        madeira=M.pbr('jatoba', 'Wood066', scale=0.8, macro=0.05, hsv=(0.5, 1.1, 0.95)),
        pinus=M.pbr('palete', 'Wood058', scale=0.6, macro=0.08),
        concreto=M.pbr('concreto', 'Concrete034', scale=2.0, macro=0.08, tint=(0.86, 0.86, 0.84)),
        concreto2=M.pbr('concreto_arq', 'Concrete031', scale=2.0, macro=0.08, hsv=(0.5, 0.5, 1.3)),
        preto=M.flat('epoxi_preto', (0.02, 0.02, 0.02), rough=0.35, metal=0.5),
        cinza_claro=M.flat('aco_cinza_claro', (0.55, 0.56, 0.57), rough=0.35, metal=0.7),
        verde_cerca=M.flat('cerca_verde', (0.02, 0.12, 0.05), rough=0.4, metal=0.2, coat=0.3),
        tela_verde=M.wire_fence('tela_gradil', (0.02, 0.12, 0.05), 0.05, 0.25, wire=0.0045, metal=0.2),
        tela_quadra=M.wire_fence('tela_alambrado', (0.55, 0.57, 0.58), 0.05, 0.05, wire=0.003, metal=0.8),
        rede=M.wire_fence('rede_esporte', (0.9, 0.9, 0.9), 0.045, 0.045, wire=0.003, metal=0.0, rough=0.8),
        palco=M.pbr('palco', 'Concrete034', scale=2.5, tint=(0.46, 0.25, 0.16), macro=0.05, rough_mul=0.8),
        plast_verde=M.flat('plastico_verde', (0.03, 0.30, 0.09), rough=0.3, spec=0.5, coat=0.3),
        plast_marrom=M.flat('madeira_plastica', (0.16, 0.08, 0.035), rough=0.6),
        plast_amarelo=M.flat('plastico_amarelo', (0.85, 0.55, 0.02), rough=0.3, coat=0.3),
        plast_vermelho=M.flat('plastico_vermelho', (0.6, 0.04, 0.03), rough=0.3, coat=0.3),
        plast_azul=M.flat('plastico_azul', (0.02, 0.12, 0.55), rough=0.3, coat=0.3),
        laranja=M.flat('aco_laranja', (0.75, 0.16, 0.02), rough=0.35, metal=0.3, coat=0.3),
        inox=M.flat('inox', (0.8, 0.8, 0.8), rough=0.2, metal=1.0),
        terra=M.pbr('terra_casca', 'Ground037', scale=1.0, hsv=(0.5, 0.4, 0.45), macro=0.0),
        almofada=M.flat('tecido_almofada', (0.55, 0.45, 0.30), rough=0.9),
        almofada2=M.flat('tecido_almofada2', (0.10, 0.25, 0.18), rough=0.9),
        led=M.flat('luminaria', (0.05, 0.05, 0.05), rough=0.3, metal=0.8),
    )


# ---------------------------------------------------------------- modelos
def bench_model(m):
    """Banco padrão Prefeitura de Passo Fundo: listões de jatobá, encosto e
    braços, estrutura tubular grafite.  Frente para +Y, encosto em -Y."""
    c = C.coll('_tmp')
    L = 1.60
    parts = []
    # assento: 5 listões
    for i in range(5):
        y = -0.18 + i * 0.095
        parts.append(C.box('b_as%d' % i, c, (L, 0.075, 0.035), (0, y, 0.43), mat=m['madeira'], bevel=0.006))
    # encosto: 3 listões inclinados
    for i in range(3):
        z = 0.56 + i * 0.11
        b = C.box('b_en%d' % i, c, (L, 0.035, 0.085), (0, -0.25 - (z - 0.5) * 0.18, z), mat=m['madeira'], bevel=0.006)
        b.rotation_euler = (math.radians(-10), 0, 0)
        parts.append(b)
    # estrutura: dois pórticos laterais (pés + braço + apoio do encosto)
    for sx in (-0.72, 0.72):
        pts = [(sx, 0.22, 0.0), (sx, 0.20, 0.42), (sx, 0.24, 0.64), (sx, -0.05, 0.64)]
        parts.append(C.tube_path('b_br', c, pts, 0.02, m['grafite']))
        pts2 = [(sx, -0.24, 0.0), (sx, -0.22, 0.42), (sx, -0.27, 0.62), (sx, -0.33, 0.86)]
        parts.append(C.tube_path('b_ps', c, pts2, 0.02, m['grafite']))
        parts.append(C.tube_path('b_tr', c, [(sx, 0.2, 0.41), (sx, -0.22, 0.41)], 0.018, m['grafite']))
    ob = C.join(parts, 'banco')
    return C.as_asset([ob], 'A_banco')


def lixeira_model(m):
    """Cesto circular em chapa perfurada preta apoiado em suporte tubular."""
    c = C.coll('_tmp')
    parts = [C.cyl('l_poste', c, 0.022, 1.02, (0, 0, 0), m['cinza_claro'], 16)]
    parts.append(C.box('l_base', c, (0.12, 0.12, 0.012), (0, 0, 0), mat=m['cinza_claro']))
    # cesto (cilindro aberto) + tampa
    me = bpy.data.meshes.new('cesto')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=0.19, radius2=0.19, depth=0.58)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.23, 0, 0.35 + 0.29))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('cesto', me)
    c.objects.link(ob)
    me.materials.append(m['preto'])
    s = ob.modifiers.new('s', 'SOLIDIFY')
    s.thickness = 0.004
    parts.append(ob)
    parts.append(C.cyl('l_fundo', c, 0.19, 0.005, (0.23, 0, 0.35), m['preto'], 32))
    parts.append(C.cyl('l_tampa', c, 0.21, 0.02, (0.23, 0, 0.93), m['cinza_claro'], 32))
    parts.append(C.tube_path('l_braco', c, [(0.0, 0, 0.9), (0.05, 0, 0.93)], 0.02, m['cinza_claro']))
    return C.as_asset([C.join(parts, 'lixeira')], 'A_lixeira')


def bicicletario_model(m):
    """Paraciclo em aço galvanizado - 4 vagas (2 arcos em U invertido)."""
    c = C.coll('_tmp')
    parts = []
    for x in (-0.75, -0.25, 0.25, 0.75):
        pts = [(x, -0.35, 0.0)]
        for k in range(9):
            a = math.pi * k / 8
            pts.append((x, -0.35 * math.cos(a), 0.55 + 0.35 * math.sin(a)))
        pts.append((x, 0.35, 0.0))
        parts.append(C.tube_path('bc', c, pts, 0.024, m['galv']))
    parts.append(C.tube_path('bc_b1', c, [(-1.0, -0.35, 0.02), (1.0, -0.35, 0.02)], 0.02, m['galv']))
    parts.append(C.tube_path('bc_b2', c, [(-1.0, 0.35, 0.02), (1.0, 0.35, 0.02)], 0.02, m['galv']))
    return C.as_asset([C.join(parts, 'bicicletario')], 'A_bicicletario')


def bebedouro_model(m):
    c = C.coll('_tmp')
    parts = [C.box('bb_col', c, (0.22, 0.16, 0.95), (0, 0, 0), mat=m['laranja'], bevel=0.01)]
    parts.append(C.cyl('bb_torn', c, 0.015, 0.06, (0, -0.09, 0.8), m['inox'], rot=(math.pi / 2, 0, 0)))
    parts.append(C.box('bb_grelha', c, (0.6, 0.6, 0.015), (0, -0.2, 0), mat=m['laranja']))
    # tigela
    parts.append(C.cyl('bb_tig', c, 0.12, 0.06, (0, -0.28, 0.015), m['inox']))
    parts.append(C.box('bb_base', c, (0.8, 0.8, 0.05), (0, -0.15, -0.04), mat=m['concreto']))
    return C.as_asset([C.join(parts, 'bebedouro')], 'A_bebedouro')


def lixeira_pet_model(m):
    c = C.coll('_tmp')
    parts = [C.cyl('lp_c', c, 0.2, 0.55, (0, 0, 0.35), m['laranja'], 32),
             C.cyl('lp_t', c, 0.21, 0.04, (0, 0, 0.9), m['laranja'], 32),
             C.cyl('lp_p', c, 0.03, 0.4, (0, 0, 0), m['grafite'], 16)]
    return C.as_asset([C.join(parts, 'lixeira_pet')], 'A_lixeira_pet')


def palet_model(m, n=3, cushion=None):
    """Pilha de paletes (0,88 x 0,88 m) - módulos do Espaço Garden."""
    c = C.coll('_tmp')
    parts = []
    for k in range(n):
        z0 = k * 0.145
        for i in range(3):
            parts.append(C.box('p_b', c, (0.88, 0.09, 0.075), (0, -0.39 + i * 0.39, z0), mat=m['pinus']))
        for i in range(7):
            parts.append(C.box('p_t', c, (0.1, 0.88, 0.022), (-0.39 + i * 0.13, 0, z0 + 0.075), mat=m['pinus']))
        for i in range(3):
            parts.append(C.box('p_f', c, (0.1, 0.88, 0.02), (-0.39 + i * 0.39, 0, z0 + 0.123), mat=m['pinus']))
    if cushion:
        parts.append(C.box('p_alm', c, (0.84, 0.84, 0.08), (0, 0, n * 0.145), mat=cushion, bevel=0.03))
    ob = C.join(parts, 'palet')
    return C.as_asset([ob], 'A_palet_%d_%s' % (n, cushion.name if cushion else 'x'))


def grelha_model(m):
    """Grelha circular em ferro fundido (Ø 1,0 m) com pintura epóxi preta."""
    c = C.coll('_tmp')
    parts = []
    for i, r in enumerate((0.16, 0.24, 0.32, 0.40, 0.48)):
        me = bpy.data.meshes.new('gr')
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=False, segments=48, radius=r)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new('gr', me)
        c.objects.link(ob)
        s = ob.modifiers.new('sk', 'SKIN')
        for v in me.skin_vertices[0].data:
            v.radius = (0.018, 0.01)
        me.materials.append(m['preto'])
        parts.append(ob)
    for k in range(16):
        a = 2 * math.pi * k / 16
        parts.append(C.box('gr_r', c, (0.34, 0.025, 0.02), (0.31 * math.cos(a), 0.31 * math.sin(a), -0.01), a, m['preto']))
    return C.as_asset([C.join(parts, 'grelha')], 'A_grelha')


# ---------------------------------------------------------------- utilitários
def place(asset, col, x, y, rot, dz=0.0, s=1.0):
    return C.instance(asset, col, (x, y, Z(x) + dz), rot, s)


def face_to(x, y, fx, fy):
    """rotação para o modelo (frente +Y) olhar para (fx,fy)."""
    return math.atan2(fy - y, fx - x) - math.pi / 2


def resample(loop, step, closed=True):
    ls = LineString(loop + ([loop[0]] if closed else []))
    n = max(2, int(round(ls.length / step)))
    return [ls.interpolate(i / n, normalized=True).coords[0] for i in range(n + (0 if closed else 1))], ls


def fence(name, col, loop, h, mat_tela, mat_post, step=2.5, gate=None, closed=True, post=(0.06, 0.04),
          base=None, dz=0.0):
    """Cerca de painéis ao longo de uma polilinha (portão em gate=(x,y,largura))."""
    pts, ls = resample(loop, step, closed)
    if gate:
        gd = ls.project(Point(gate[0], gate[1]))
        gw = gate[2]
    verts, faces, uvs = [], [], []
    posts = []
    segs = list(zip(pts, pts[1:] + ([pts[0]] if closed else [])))
    dist = 0.0
    for (a, b) in segs:
        L = math.dist(a, b)
        d0, d1 = dist, dist + L
        dist = d1
        if gate and d0 - 0.01 < gd < d1 + 0.01 or gate and abs(d0 - gd) < gw / 2 + 0.2:
            continue
        za, zb = Z(a[0]) + dz, Z(b[0]) + dz
        i = len(verts)
        verts += [(a[0], a[1], za + 0.05), (b[0], b[1], zb + 0.05), (b[0], b[1], zb + h), (a[0], a[1], za + h)]
        faces.append((i, i + 1, i + 2, i + 3))
        uvs += [(0, 0), (L, 0), (L, h - 0.05), (0, h - 0.05)]
        posts += [a, b]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new()
    for li, loopd in enumerate(me.loops):
        uvl.data[li].uv = uvs[loopd.vertex_index]
    me.materials.append(mat_tela)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    # postes
    seen = set()
    pc = []
    for p in posts:
        k = (round(p[0], 2), round(p[1], 2))
        if k in seen:
            continue
        seen.add(k)
        pc.append(C.box(name + '_p', col, (post[0], post[1], h + 0.1), (p[0], p[1], Z(p[0]) + dz), mat=mat_post))
    if pc:
        C.join(pc, name + '_postes')
    if base is not None:
        # cinta de concreto sob a cerca
        g = LineString(loop + ([loop[0]] if closed else [])).buffer(0.1, cap_style=2)
        from build_ground import to_polys
        C.poly_mesh(name + '_cinta', to_polys(g), col, base, z=0.03, thick=0.2, rim_mat=base, step=1.0)
    return ob


# ---------------------------------------------------------------- construção
def build(S):
    m = mats()
    col = C.coll('Mobiliario')
    OBJ = S['objetos']
    A_banco = bench_model(m)
    A_lix = lixeira_model(m)
    A_bic = bicicletario_model(m)
    A_beb = bebedouro_model(m)
    A_lixpet = lixeira_pet_model(m)
    A_grelha = grelha_model(m)

    focos = {}
    for o in OBJ:
        if o['t'] == 'grelha':
            focos['estar%d' % len(focos)] = (o['x'], o['y'])
    focos['pet'] = (-153.1, 3.3)
    focos['kids'] = (156.4, 3.3)

    for o in OBJ:
        t, x, y = o['t'], o['x'], o['y']
        if t == 'banco':
            fx, fy = min(focos.values(), key=lambda f: math.dist(f, (x, y)))
            place(A_banco, col, x, y, face_to(x, y, fx, fy), 0.01)
        elif t == 'lixeira':
            place(A_lix, col, x, y, random.uniform(0, 6.28), 0.01)
        elif t == 'bicicletario':
            place(A_bic, col, x, y, 0.0, 0.005)
        elif t == 'bebedouro':
            place(A_beb, col, x, y, face_to(x, y, *focos['pet']), 0.0)
        elif t == 'grelha':
            place(A_grelha, col, x, y, 0.0, 0.012)

    # banco dos tutores e lixeiras de dejetos (Espaço Pet)
    place(A_banco, col, -148.2, 8.2, face_to(-148.2, 8.2, *focos['pet']), 0.01)
    place(A_lixpet, col, -159.3, 9.0, 0.0, 0.01)
    place(A_lixpet, col, -147.1, -3.3, 0.0, 0.01)

    # pictogramas da ciclovia
    m_pic = M.decal('pictograma', C.TEX + '/gen/pictograma_bici.png')
    for o in OBJ:
        if o['t'] != 'pictograma_bici':
            continue
        x, y = o['x'], o['y']
        rot = 0.0 if y > 11.5 else math.pi   # faixa norte -> leste
        bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, Z(x) + 0.012))
        p = bpy.context.active_object
        p.scale = (2.5, 0.82, 1)
        p.rotation_euler = (0, 0, rot)
        p.data.materials.append(m_pic)
        for c in p.users_collection:
            c.objects.unlink(p)
        col.objects.link(p)

    palco_foodparque(S, m, col)
    quadra(S, m, col)
    cercas(S, m, col)
    playground(m, col)
    pet_brinquedos(m, col)
    garden(S, m, col)
    piso_tatil(S, col)
    tentos(S, col, m)
    bpy.data.collections.remove(bpy.data.collections['_tmp'])
    C.coll('_assets').hide_render = True
    C.coll('_assets').hide_viewport = True
    bpy.context.view_layer.layer_collection.children['_assets'].exclude = True


def palco_foodparque(S, m, col):
    from build_ground import to_polys, shp
    # palco 10 x 12 m, +20 cm
    C.poly_mesh('palco', S['palco'], col, m['palco'], z=0.20, thick=0.25, rim_mat=m['concreto'], step=1.0)
    # bancos perimetrais quadrados em alvenaria + assento de jatobá
    for (x, y, w) in S['bancos_quadrados']:
        outer = Polygon(C.rect(x, y, w, w))
        inner = Polygon(C.rect(x, y, w - 0.9, w - 0.9))
        ring = outer.difference(inner)
        C.poly_mesh('bq_base', to_polys(ring.buffer(-0.03, join_style=2)), col, m['concreto'], z=0.40, thick=0.40,
                    rim_mat=m['concreto'], step=0)
        # listões do assento (moldura em 45° como na referência)
        for k in range(4):
            off = 0.06 + k * 0.105
            ring_k = Polygon(C.rect(x, y, w - 2 * off + 0.0, w - 2 * off)).difference(
                Polygon(C.rect(x, y, w - 2 * off - 0.19, w - 2 * off - 0.19)))
            C.poly_mesh('bq_madeira', to_polys(ring_k), col, m['madeira'], z=0.445, thick=0.045, rim_mat=m['madeira'],
                        step=0)
        C.poly_mesh('bq_terra', to_polys(inner), col, m['terra'], z=0.33, step=0)
    # canteiros curvos (bela-emília) e canteiro do totem
    for p in S['canteiros_curvos']:
        g = Polygon(p).buffer(0)
        C.poly_mesh('cant_curvo_borda', to_polys(g.difference(g.buffer(-0.1))), col, m['concreto'], z=0.12,
                    thick=0.2, rim_mat=m['concreto'], step=0.5)
        C.poly_mesh('cant_curvo_terra', to_polys(g.buffer(-0.1)), col, m['terra'], z=0.08, step=0.5)
    g = shp(S['canteiro_totem'])
    C.poly_mesh('cant_totem_borda', to_polys(g.difference(g.buffer(-0.1))), col, m['concreto'], z=0.12, thick=0.2,
                rim_mat=m['concreto'], step=0.5)
    C.poly_mesh('cant_totem_terra', to_polys(g.buffer(-0.1)), col, m['terra'], z=0.08, step=0.5)
    # totem do empreendimento: muro em concreto aparente com o logotipo
    tot = C.poly_mesh('totem', S['totem'], col, m['concreto2'], z=1.2, thick=1.25, rim_mat=m['concreto2'], step=0.5)
    xs = [p[0] for p in S['totem'][0]['ext']]
    ys = [p[1] for p in S['totem'][0]['ext']]
    cx = (min(xs) + max(xs)) / 2
    ymin = min(p[1] for p in S['totem'][0]['ext'] if abs(p[0] - cx) < 1.0)
    logo = M.decal('logo', C.TEX + '/logo.png', rough=0.4)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, ymin - 0.012, Z(cx) + 0.63))
    p = bpy.context.active_object
    p.scale = (2.55, 1.02, 1)
    p.rotation_euler = (math.pi / 2, 0, 0)
    p.data.materials.append(logo)
    for c in p.users_collection:
        c.objects.unlink(p)
    col.objects.link(p)


def quadra(S, m, col):
    from build_ground import to_polys
    ext = S['quadra_areia'][0]['ext']
    xs = [p[0] for p in ext]; ys = [p[1] for p in ext]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    loop = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    fence('alambrado', col, loop, 3.0, m['tela_quadra'], m['galv'], step=3.0, gate=((x0 + x1) / 2, y0, 1.2),
          post=(0.06, 0.06))
    # travessa superior
    zt = lambda x: Z(x) + 3.0
    C.tube_path('alamb_top', col, [(p[0], p[1], zt(p[0])) for p in loop], 0.025, m['galv'], cyclic=True)
    # portão
    gx = (x0 + x1) / 2
    C.tube_path('portao', col, [(gx - 0.6, y0, Z(gx) + 0.05), (gx - 0.6, y0, Z(gx) + 2.1), (gx + 0.6, y0, Z(gx) + 2.1),
                                (gx + 0.6, y0, Z(gx) + 0.05)], 0.025, m['galv'])
    # postes e rede de beach tennis
    xm = (x0 + x1) / 2
    for yy in (y0 + 0.35, y1 - 0.35):
        C.cyl('poste_rede', col, 0.04, 1.95, (xm, yy, Z(xm)), m['galv'])
    me = bpy.data.meshes.new('rede')
    zz = Z(xm)
    me.from_pydata([(xm, y0 + 0.4, zz + 0.95), (xm, y1 - 0.4, zz + 0.95), (xm, y1 - 0.4, zz + 1.7), (xm, y0 + 0.4, zz + 1.7)],
                   [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new()
    L = y1 - y0 - 0.8
    for i, uv in enumerate([(0, 0), (L, 0), (L, 0.75), (0, 0.75)]):
        uvl.data[i].uv = uv
    me.materials.append(m['rede'])
    ob = bpy.data.objects.new('rede', me)
    col.objects.link(ob)
    C.box('faixa_rede', col, (0.01, L, 0.05), (xm, (y0 + y1) / 2, zz + 1.68), mat=M.flat('fita_branca', (0.9, 0.9, 0.9)))
    # refletores LED (4 postes nos cantos)
    for (px, py, ax, ay) in ((x0 - 0.4, y0 - 0.4, 1, 1), (x1 + 0.4, y0 - 0.4, -1, 1), (x1 + 0.4, y1 + 0.4, -1, -1),
                             (x0 - 0.4, y1 + 0.4, 1, -1)):
        C.cyl('poste_led', col, 0.06, 6.5, (px, py, Z(px)), m['galv'], 16)
        pr = C.box('refletor', col, (0.45, 0.12, 0.35), (px + 0.2 * ax, py + 0.2 * ay, Z(px) + 6.2),
                   math.atan2(ay, ax) + math.pi / 2, m['led'])
        pr.rotation_euler[0] = math.radians(35)
    # arquibancadas em concreto moldado in loco (2 lances)
    C.poly_mesh('arquibancada', S['arquibancadas_hatch'], col, m['concreto2'], z=0.45, thick=0.5,
                rim_mat=m['concreto2'], step=0.3)


def cercas(S, m, col):
    fence('cerca_kids', col, [tuple(p) for p in S['cerca_kids']], 2.0, m['tela_verde'], m['verde_cerca'],
          gate=(148.0, 1.1, 1.2), base=m['concreto'])
    fence('cerca_pet', col, [tuple(p) for p in S['cerca_pet']], 2.0, m['tela_verde'], m['verde_cerca'],
          gate=(-145.3, 3.4, 1.2), base=m['concreto'])


def playground(m, col):
    """Playground em polietileno rotomoldado (padrão Prefeitura) - posição e
    orientação conforme bloco 'LD CASINHA PB 002' da planta."""
    pc = C.coll('Playground', col)
    V, Mr, Am, Vm = m['plast_verde'], m['plast_marrom'], m['plast_amarelo'], m['plast_vermelho']
    T = (157.77, 6.73)                  # torre principal
    ang = math.radians(208.9 - 180)     # eixo torre -> ponte
    ca, sa = math.cos(ang), math.sin(ang)

    def W(u, v):  # local -> mundo
        return (T[0] + u * ca - v * sa, T[1] + u * sa + v * ca)

    def post(u, v, h):
        x, y = W(u, v)
        return C.box('pg_post', pc, (0.1, 0.1, h), (x, y, Z(x)), ang, Mr)

    zg = Z(T[0])
    parts = []
    # torre principal 1,5 x 1,5, plataforma a 1,40 m, telhado piramidal verde
    for u in (-0.75, 0.75):
        for v in (-0.75, 0.75):
            parts.append(post(u, v, 2.6))
    x, y = W(0, 0)
    parts.append(C.box('pg_plat', pc, (1.5, 1.5, 0.06), (x, y, zg + 1.36), ang, Mr))
    roof = bpy.data.meshes.new('telhado')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=1.25, radius2=0.02, depth=0.8)
    bm.to_mesh(roof)
    bm.free()
    ro = bpy.data.objects.new('telhado', roof)
    pc.objects.link(ro)
    ro.location = (x, y, zg + 2.95)
    ro.rotation_euler = (0, 0, ang + math.pi / 4)
    roof.materials.append(V)
    # painéis laterais (guarda-corpos)
    for (u, v, r) in ((0, 0.75, 0), (0.75, 0, math.pi / 2), (0, -0.75, 0)):
        px, py = W(u, v)
        parts.append(C.box('pg_gc', pc, (1.4, 0.05, 0.7), (px, py, zg + 1.42), ang + r, Am, bevel=0.02))
    # escorregador reto (sai para -v)
    sx0, sy0 = W(0.2, -0.75)
    sx1, sy1 = W(0.9, -3.4)
    L = math.dist((sx0, sy0), (sx1, sy1))
    sl = C.box('pg_escorregador', pc, (0.55, L, 0.06), ((sx0 + sx1) / 2, (sy0 + sy1) / 2, zg + 0.75),
               math.atan2(sy1 - sy0, sx1 - sx0) - math.pi / 2, V)
    sl.rotation_euler[0] = -math.atan2(1.3, L)
    for off in (-0.3, 0.3):
        s2 = C.box('pg_esc_borda', pc, (0.05, L, 0.2), ((sx0 + sx1) / 2 + off * math.cos(ang),
                                                         (sy0 + sy1) / 2 + off * math.sin(ang), zg + 0.8),
                   math.atan2(sy1 - sy0, sx1 - sx0) - math.pi / 2, V)
        s2.rotation_euler[0] = sl.rotation_euler[0]
    # ponte pênsil até a torre menor
    for i in range(12):
        u = -0.9 - i * 0.27
        x, y = W(u, 0)
        parts.append(C.box('pg_degrau', pc, (0.2, 0.7, 0.04), (x, y, zg + 1.25 - 0.03 * math.sin(i / 11 * math.pi)),
                           ang, Mr))
    for v in (-0.38, 0.38):
        a, b = W(-0.8, v), W(-4.1, v)
        C.tube_path('pg_corrimao', pc, [(a[0], a[1], zg + 1.95), (b[0], b[1], zg + 1.85)], 0.03, V)
        C.tube_path('pg_corrimao2', pc, [(a[0], a[1], zg + 1.6), (b[0], b[1], zg + 1.5)], 0.02, Vm)
    # torre menor + rede de escalada (leque)
    for u in (-4.2, -5.0):
        for v in (-0.4, 0.4):
            parts.append(post(u, v, 2.2))
    x, y = W(-4.6, 0)
    parts.append(C.box('pg_plat2', pc, (0.9, 0.9, 0.06), (x, y, zg + 1.2), ang, Mr))
    roof2 = ro.copy()
    roof2.data = ro.data.copy()
    pc.objects.link(roof2)
    roof2.location = (x, y, zg + 2.55)
    roof2.scale = (0.75, 0.75, 0.8)
    for k in range(7):
        a = math.radians(-50 + k * 16)
        ex, ey = W(-5.0 - 1.4 * math.cos(a), 1.4 * math.sin(a))
        sx, sy = W(-5.0, 0.35 * math.sin(a))
        C.tube_path('pg_rede', pc, [(sx, sy, zg + 1.2), (ex, ey, zg + 0.02)], 0.012, Mr)
    for kk in range(1, 5):
        pts = []
        for k in range(7):
            a = math.radians(-50 + k * 16)
            f = kk / 5
            ex, ey = W(-5.0 - 1.4 * f * math.cos(a), 1.4 * f * math.sin(a) + 0.35 * (1 - f) * math.sin(a))
            pts.append((ex, ey, zg + 1.2 * (1 - f) + 0.02))
        C.tube_path('pg_rede_h', pc, pts, 0.01, Mr)
    # escada de acesso à torre principal
    for i in range(6):
        x, y = W(0.95 + i * 0.12, 0.95)
        parts.append(C.box('pg_escada', pc, (0.12, 0.5, 0.04), (x, y, zg + 1.3 - i * 0.22), ang, Am))
    # parede de escalada
    x, y = W(0.78, 0.2)
    parts.append(C.box('pg_escalada', pc, (0.05, 1.0, 1.3), (x, y, zg + 0.05), ang, Vm, bevel=0.03))


def pet_brinquedos(m, col):
    """Conjunto de brinquedos pet: plataforma 1,06 x 1,06 com cobertura,
    2 rampas, guarda-corpos e túnel Ø 0,75 x 1,00 m."""
    pc = C.coll('Pet', col)
    cx, cy = -156.86, 6.78
    zg = Z(cx)
    ang = math.radians(341.2)
    for dx in (-0.53, 0.53):
        for dy in (-0.53, 0.53):
            x = cx + dx * math.cos(ang) - dy * math.sin(ang)
            y = cy + dx * math.sin(ang) + dy * math.cos(ang)
            C.box('pp_col', pc, (0.09, 0.09, 1.55), (x, y, zg), ang, m['plast_marrom'])
    C.box('pp_plat', pc, (1.06, 1.06, 0.05), (cx, cy, zg + 0.75), ang, m['plast_marrom'])
    C.box('pp_teto', pc, (1.3, 1.3, 0.05), (cx, cy, zg + 1.55), ang, m['plast_verde'], bevel=0.02)
    for s in (-1, 1):
        x = cx + s * 0.53 * math.sin(ang)
        y = cy - s * 0.53 * math.cos(ang)
        C.box('pp_gc', pc, (0.88, 0.05, 0.75), (x, y, zg + 0.8), ang, m['plast_amarelo'] if s > 0 else m['plast_vermelho'],
              bevel=0.02)
    for s in (-1, 1):
        x = cx + s * 1.25 * math.cos(ang)
        y = cy + s * 1.25 * math.sin(ang)
        r = C.box('pp_rampa', pc, (1.6, 0.5, 0.05), (x, y, zg + 0.36), ang, m['plast_marrom'])
        r.rotation_euler[1] = s * math.atan2(0.72, 1.45)
    # túnel
    t = C.cyl('pp_tunel', pc, 0.375, 1.0, (-152.3, -0.75, zg + 0.38), m['plast_azul'], 32,
              rot=(0, math.pi / 2, 0))
    t.location.x -= 0.5
    s = t.modifiers.new('s', 'SOLIDIFY'); s.thickness = 0.03
    bm_del = t.data
    # remove tampas do túnel (tubo aberto)
    bm = bmesh.new(); bm.from_mesh(bm_del)
    caps = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.delete(bm, geom=caps, context='FACES')
    bm.to_mesh(bm_del); bm.free()
    for s_, xx in ((-1, -154.4), (1, -150.6)):
        r = C.box('pp_ramp2', pc, (1.2, 0.8, 0.05), (xx, -0.75, zg + 0.3), 0, m['plast_marrom'])
        r.rotation_euler[1] = s_ * 0.45


def garden(S, m, col):
    """Espaço Garden: módulos de paletes tratados (posições do DWG)."""
    gc = C.coll('Garden', col)
    A_seat = palet_model(m, 3, m['almofada'])
    A_seat2 = palet_model(m, 3, m['almofada2'])
    A_mesa = palet_model(m, 4)
    k = 0
    for o in S['objetos']:
        if o['t'] != 'palet':
            continue
        x, y = o['x'], o['y']
        if o['w'] < 0.6:
            place(A_mesa, gc, x, y, math.radians(o['rot']), 0.0, 0.55)
        else:
            place(A_seat if k % 2 == 0 else A_seat2, gc, x, y, math.radians(o['rot']), 0.0)
            k += 1


def align_tiles(tiles, s=0.4):
    """Alinha as placas ortogonais de cada trecho numa grade única de 40 cm
    (no DWG algumas faixas estão 8 cm deslocadas, gerando degraus nos cantos)
    e remove placas diagonais que invadem os blocos de alerta ortogonais."""
    from collections import Counter
    def ortho(q):
        a = math.degrees(math.atan2(q[1][1] - q[0][1], q[1][0] - q[0][0])) % 90
        return a < 1.5 or a > 88.5
    ort = [t for t in tiles if ortho(t[0])]
    diag = [t for t in tiles if not ortho(t[0])]
    # componentes conectados de placas ortogonais
    n = len(ort); comp = list(range(n))
    def f(i):
        while comp[i] != i:
            comp[i] = comp[comp[i]]; i = comp[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(ort[i][1], ort[j][1]) < 0.62:
                comp[f(i)] = f(j)
    groups = {}
    for i in range(n):
        groups.setdefault(f(i), []).append(ort[i])
    out = []
    for g in groups.values():
        ax = Counter(round(t[1][0] % s, 2) for t in g).most_common(1)[0][0]
        ay = Counter(round(t[1][1] % s, 2) for t in g).most_common(1)[0][0]
        seen = set()
        for t in g:
            cx = ax + round((t[1][0] - ax) / s) * s
            cy = ay + round((t[1][1] - ay) / s) * s
            k = (round(cx, 2), round(cy, 2))
            if k in seen:
                continue
            seen.add(k)
            rr = Polygon(C.rect(cx, cy, s, s))
            out.append((list(rr.exterior.coords)[:4], (cx, cy), rr))
    ortu = unary_union([t[2] for t in out]) if out else None
    kept = []
    for t in diag:
        low = ortu is not None and t[2].intersection(ortu).area > 0.001
        if any(t[2].intersection(k[2]).area > 0.6 * t[2].area for k in kept):
            continue
        kept.append((t[0], t[1], t[2], low))
    out = [(o[0], o[1], o[2], False) for o in out] + kept
    return out


def piso_tatil(S, col):
    """Piso tátil (NBR 16537) - placas 40 x 40 cm do bloco 'piso tatik'.
    Placas em linha = direcional (barras no sentido do caminho);
    placas em grupo = alerta."""
    tiles = []
    for p in S['tatil']:
        # contorno limpo: retângulo mínimo (alguns blocos têm vértice repetido)
        rr = Polygon(p).buffer(0).minimum_rotated_rectangle
        if rr.geom_type != 'Polygon' or rr.area < 0.02:
            continue
        q = list(rr.exterior.coords)[:4]
        cx = sum(a[0] for a in q) / 4
        cy = sum(a[1] for a in q) / 4
        ang = math.degrees(math.atan2(q[1][1] - q[0][1], q[1][0] - q[0][0])) % 90
        diag_t = 1.5 < ang < 88.5
        lim = 0.6 if diag_t else 0.05   # diagonais encavaladas no DWG: só remove duplicatas
        if any(math.dist((cx, cy), t[1]) < 0.6 and abs(ang - t[3]) < 2 and rr.intersection(t[2]).area > lim * rr.area
               for t in tiles):
            continue  # placa sobreposta a outra (evita faces coplanares)
        tiles.append((q, (cx, cy), rr, ang))
    tiles = align_tiles(tiles)
    cents = [t[1] for t in tiles]
    groups = {'alerta': ([], [], []), 'direcional': ([], [], [])}
    for i, (q, c, _rr, low) in enumerate(tiles):
        nb = [cents[j] for j in range(len(tiles)) if j != i and math.dist(c, cents[j]) < 0.62]
        kind = 'alerta' if len(nb) >= 3 else 'direcional'
        if nb:
            far = max(nb, key=lambda n: math.dist(c, n))
            dvec = Vector((far[0] - c[0], far[1] - c[1], 0)).normalized()
        else:
            dvec = Vector((1, 0, 0))
        e1 = Vector((q[1][0] - q[0][0], q[1][1] - q[0][1], 0))
        e2 = Vector((q[3][0] - q[0][0], q[3][1] - q[0][1], 0))
        if abs(e1.normalized().dot(dvec)) > abs(e2.normalized().dot(dvec)):
            uv = [(0, 0), (0, 1), (1, 1), (1, 0)]
        else:
            uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
        V, F, U = groups[kind]
        k = len(V)
        for (x, y) in q:
            V.append((x, y, Z(x) + (0.006 if low else 0.009) + 0.0006 * (i % 3) * (not low)))
        F.append((k, k + 1, k + 2, k + 3))
        U.extend(uv)
    for kind, (V, F, U) in groups.items():
        if not V:
            continue
        me = bpy.data.meshes.new('tatil_' + kind)
        me.from_pydata(V, [], F)
        uvl = me.uv_layers.new()
        for li, lp in enumerate(me.loops):
            uvl.data[li].uv = U[lp.vertex_index]
        for p in me.polygons:
            if p.normal.z < 0:
                p.flip()
        me.materials.append(M.gen('tatil_' + kind, 'tatil_' + kind, 1.0, uv=True, normal=(0.0 if kind == 'alerta' else 1.0), macro=0))
        ob = bpy.data.objects.new('tatil_' + kind, me)
        col.objects.link(ob)


def tentos(S, col, m):
    """Guias (tentos) de concreto delimitando pavimentos e canteiros."""
    from build_ground import shp, to_polys
    pav = shp(S['paver'])
    cant = None
    for c in S['canteiro']:
        g = shp(c)
        cant = g if cant is None else cant.union(g)
    edge = pav.boundary.buffer(0.05, cap_style=2).intersection(cant.buffer(-0.2))
    edge = edge.difference(shp(S['ciclovia']).buffer(0.02))
    C.poly_mesh('tentos', to_polys(edge), col, m['concreto'], z=0.018, thick=0.06, rim_mat=m['concreto'], step=0.5)
