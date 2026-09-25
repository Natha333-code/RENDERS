"""Paisagismo conforme memorial: posições exatas dos blocos do DWG.
 Quaresmeira (52), Extremosa branca (52), Jerivá (50), Moreia (29),
 Bela-emília (108), Manacá-da-serra (4), Ipê-amarelo (2), Jabuticabeira (1)
 + araucárias existentes (bloco p1) e mata da Área de Espaços Livres."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise
import lib_common as C
import lib_materials as M
from lib_common import zc_smooth as Z

rnd = random.Random(5)


# ------------------------------------------------------------- assets PH
def append_tree(name, colname, newname):
    f = f'{C.ASSETS}/{name}/{name}.blend'
    with bpy.data.libraries.load(f, link=False) as (src, dst):
        dst.collections = [colname]
    c = dst.collections[0]
    c.name = newname
    C.coll('_assets').children.link(c)
    return c


def flower_mix(c, color, amount=0.35, scale=5.0, color2=None, leaf_tint=None):
    """Mistura manchas de flores (cor) na textura das folhas da árvore."""
    done = {}
    for o in c.all_objects:
        for s in o.material_slots:
            mt = s.material
            if not mt or 'leaves' not in mt.name and 'shrub' not in mt.name:
                continue
            if mt.name not in done:
                nm = mt.copy()
                nm.name = mt.name + '_' + c.name
                nt = nm.node_tree
                grp = [n for n in nt.nodes if n.type == 'GROUP'][0]
                lk = None
                for l in nt.links:
                    if l.to_node == grp and l.from_node.type == 'TEX_IMAGE' and l.to_socket.type == 'RGBA':
                        lk = l
                        break
                if lk is None:
                    done[mt.name] = nm
                    continue
                src, dst = lk.from_socket, lk.to_socket
                nt.links.remove(lk)
                geo = nt.nodes.new('ShaderNodeNewGeometry')
                nz = nt.nodes.new('ShaderNodeTexNoise')
                nz.inputs['Scale'].default_value = scale
                nz.inputs['Detail'].default_value = 2
                nt.links.new(geo.outputs['Position'], nz.inputs[0])
                ramp = nt.nodes.new('ShaderNodeValToRGB')
                ramp.color_ramp.elements[0].position = 0.5 - amount * 0.25
                ramp.color_ramp.elements[1].position = 0.52 - amount * 0.25 + 0.04
                nt.links.new(nz.outputs[0], ramp.inputs[0])
                cur = src
                if leaf_tint:
                    t = nt.nodes.new('ShaderNodeMix'); t.data_type = 'RGBA'; t.blend_type = 'MULTIPLY'
                    t.inputs['Factor'].default_value = 1
                    nt.links.new(src, t.inputs[6]); t.inputs[7].default_value = (*leaf_tint, 1)
                    cur = t.outputs[2]
                fcol = nt.nodes.new('ShaderNodeMix'); fcol.data_type = 'RGBA'
                fcol.inputs[6].default_value = (*color, 1)
                fcol.inputs[7].default_value = (*(color2 or color), 1)
                n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 1.5
                nt.links.new(geo.outputs['Position'], n2.inputs[0])
                nt.links.new(n2.outputs[0], fcol.inputs['Factor'])
                # flores mantêm a luminância da folha (variação natural)
                bw = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(src, bw.inputs[0])
                mulv = nt.nodes.new('ShaderNodeMath'); mulv.operation = 'MULTIPLY_ADD'
                nt.links.new(bw.outputs[0], mulv.inputs[0]); mulv.inputs[1].default_value = 1.6; mulv.inputs[2].default_value = 0.35
                fl = nt.nodes.new('ShaderNodeMix'); fl.data_type = 'RGBA'; fl.blend_type = 'MULTIPLY'
                nt.links.new(mulv.outputs[0], fl.inputs['Factor'])
                nt.links.new(fcol.outputs[2], fl.inputs[6]); fl.inputs[7].default_value = (1, 1, 1, 1)
                fl.inputs['Factor'].default_value = 0
                mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
                nt.links.new(ramp.outputs[0], mix.inputs['Factor'])
                nt.links.new(cur, mix.inputs[6])
                nt.links.new(fcol.outputs[2], mix.inputs[7])
                nt.links.new(mix.outputs[2], dst)
                done[mt.name] = nm
            s.material = done[mt.name]


def tint_leaves(c, tint):
    flower_mix(c, (0, 0, 0), amount=-10, leaf_tint=tint)


# ------------------------------------------------------------- jerivá
def jeriva_model(seed, H):
    """Palmeira jerivá (Syagrus romanzoffiana): estipe cinza anelado e ~14
    folhas pinadas plumosas arqueadas."""
    r = random.Random(seed)
    c = C.coll('_tmp_veg')
    trunk_mat = M.pbr('estipe_jeriva', 'Concrete031', scale=0.6, hsv=(0.5, 0.3, 0.55), macro=0.1)
    leaf_mat = M.flat('folha_jeriva', (0.07, 0.17, 0.03), rough=0.55, spec=0.4, trans=0.0)
    petiole_mat = M.flat('peciolo_jeriva', (0.13, 0.14, 0.05), rough=0.6)
    # estipe com anéis
    me = bpy.data.meshes.new('estipe')
    bm = bmesh.new()
    seg, rings = 12, int(H / 0.08)
    lean = Vector((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), 0))
    verts = []
    for i in range(rings + 1):
        t = i / rings
        z = H * t
        rad = 0.17 - 0.035 * t + (0.012 if i % 3 == 0 else 0)
        ctr = lean * (t * t)
        ring = [bm.verts.new((ctr.x + rad * math.cos(2 * math.pi * k / seg), ctr.y + rad * math.sin(2 * math.pi * k / seg), z))
                for k in range(seg)]
        verts.append(ring)
    for i in range(rings):
        for k in range(seg):
            bm.faces.new((verts[i][k], verts[i][(k + 1) % seg], verts[i + 1][(k + 1) % seg], verts[i + 1][k]))
    bm.to_mesh(me); bm.free()
    trunk = bpy.data.objects.new('estipe', me); c.objects.link(trunk)
    me.materials.append(trunk_mat)
    for p in me.polygons:
        p.use_smooth = True
    top = Vector((lean.x, lean.y, H))
    # folhas
    lv, lf = [], []
    pv, pf = [], []
    nf = 15
    for f in range(nf):
        az = 2 * math.pi * f / nf * 2.618 + r.uniform(-0.2, 0.2)
        el0 = math.radians(r.uniform(15, 80) if f % 3 else r.uniform(60, 95))  # ângulo inicial vs vertical
        L = r.uniform(2.4, 3.2)
        d = Vector((math.cos(az), math.sin(az), 0))
        n = 34
        pts = []
        p = top.copy()
        ang = el0
        for i in range(n + 1):
            pts.append(p.copy())
            step = L / n
            dirv = d * math.sin(ang) + Vector((0, 0, 1)) * math.cos(ang)
            p = p + dirv * step
            ang += math.radians(2.6)   # arqueamento
        # ráquis (tubo fino)
        for i in range(n):
            a, b = pts[i], pts[i + 1]
            w = 0.02 * (1 - i / n) + 0.006
            side = d.cross(Vector((0, 0, 1))).normalized() * w
            k = len(pv)
            pv += [a - side, a + side, b + side * 0.9, b - side * 0.9]
            pf.append((k, k + 1, k + 2, k + 3))
        # folíolos em vários planos (plumosa)
        for i in range(5, n):
            t = i / n
            a = pts[i]
            tang = (pts[min(i + 1, n)] - pts[i - 1]).normalized()
            side = tang.cross(Vector((0, 0, 1)))
            if side.length < 1e-3:
                side = Vector((1, 0, 0))
            side.normalize()
            up = side.cross(tang).normalized()
            ll = 0.62 * math.sin(math.pi * (0.15 + 0.85 * t)) + 0.12
            for s in (-1, 1):
                for pl in (-0.9, -0.2, 0.5):
                    e = pl + r.uniform(-0.25, 0.25)
                    dv = (side * s * math.cos(e) + up * math.sin(e) * 0.8 - Vector((0, 0, 0.35 + 0.3 * t))).normalized()
                    dv = (dv + tang * 0.45).normalized()
                    w = 0.018
                    wv = dv.cross(tang).normalized() * w
                    tip = a + dv * ll + Vector((0, 0, -0.12 * ll))
                    mid = a + dv * ll * 0.5
                    k = len(lv)
                    lv += [a, mid + wv, tip, mid - wv]
                    lf.append((k, k + 1, k + 2, k + 3))
    me2 = bpy.data.meshes.new('folhas')
    me2.from_pydata(lv, [], lf)
    me2.materials.append(leaf_mat)
    lo = bpy.data.objects.new('folhas', me2); c.objects.link(lo)
    me3 = bpy.data.meshes.new('raquis')
    me3.from_pydata(pv, [], pf)
    me3.materials.append(petiole_mat)
    ro = bpy.data.objects.new('raquis', me3); c.objects.link(ro)
    ob = C.join([trunk, lo, ro], 'jeriva_%d' % seed)
    return C.as_asset([ob], 'A_jeriva_%d' % seed)


# ------------------------------------------------------------- araucária
def araucaria_model(seed, H):
    """Araucaria angustifolia adulta: fuste reto, copa em taça (candelabro)."""
    r = random.Random(seed)
    c = C.coll('_tmp_veg')
    bark = M.flat('casca_araucaria', (0.16, 0.10, 0.07), rough=0.9)
    fol = M.flat('grimpa', (0.03, 0.075, 0.03), rough=0.65)
    parts = [C.cyl('fuste', c, 0.32, H, (0, 0, 0), bark, 14)]
    parts[0].data.vertices.foreach_set('co', [v for vv in [(vv.co.x * (1 - 0.6 * vv.co.z / H), vv.co.y * (1 - 0.6 * vv.co.z / H), vv.co.z) for vv in parts[0].data.vertices] for v in vv])
    tufts = []
    whorls = 6
    for w in range(whorls):
        zb = H * (0.72 + 0.28 * w / whorls)
        nb = 6
        for b in range(nb):
            az = 2 * math.pi * (b + 0.5 * w) / nb + r.uniform(-0.3, 0.3)
            Lb = (1 - w / whorls) * r.uniform(4.0, 6.0) + 1.2
            d = Vector((math.cos(az), math.sin(az), 0))
            p0 = Vector((0, 0, zb))
            p1 = p0 + d * Lb * 0.6 + Vector((0, 0, 0.5))
            p2 = p0 + d * Lb + Vector((0, 0, 1.6 + r.uniform(0, 0.8)))
            parts.append(C.tube_path('galho', c, [tuple(p0), tuple(p1), tuple(p2)], 0.07, bark))
            # tufos (grimpas) ao longo do galho e na ponta
            for t in (0.55, 0.8, 1.0):
                q = p0.lerp(p1, t / 0.6) if t <= 0.6 else p1.lerp(p2, (t - 0.6) / 0.4)
                tufts.append((q + Vector((0, 0, 0.25)), 0.9 + 0.5 * t))
    me = bpy.data.meshes.new('grimpas')
    bm = bmesh.new()
    for q, s in tufts:
        # núcleo escuro achatado
        g = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=s * 0.55)
        for v in g['verts']:
            v.co = v.co * Vector((1.2, 1.2, 0.45)) + q
        # raminhos (grimpas) em leque voltados para cima/fora
        for k in range(34):
            az = r.uniform(0, 2 * math.pi)
            el = r.uniform(0.15, 1.2)
            d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el) * 0.7 + 0.15)).normalized()
            L = s * r.uniform(0.7, 1.15)
            side = d.cross(Vector((0, 0, 1)))
            side = (side.normalized() if side.length > 1e-3 else Vector((1, 0, 0))) * 0.07 * s
            a = q + d * 0.2 * s
            b = q + d * L + Vector((0, 0, 0.1 * L))
            m1 = a.lerp(b, 0.5) + Vector((0, 0, -0.05 * L))
            vs = [bm.verts.new(a - side * 0.6), bm.verts.new(m1 - side), bm.verts.new(b), bm.verts.new(m1 + side),
                  bm.verts.new(a + side * 0.6)]
            bm.faces.new(vs)
    bm.to_mesh(me); bm.free()
    me.materials.append(fol)
    go = bpy.data.objects.new('grimpas', me); c.objects.link(go)
    parts.append(go)
    ob = C.join(parts, 'araucaria_%d' % seed)
    return C.as_asset([ob], 'A_araucaria_%d' % seed)


# ------------------------------------------------------------- moreia
def moreia_model(seed):
    """Moreia (Dietes iridioides): touceira de folhas lineares + flores brancas."""
    r = random.Random(seed)
    c = C.coll('_tmp_veg')
    leaf = M.flat('folha_moreia', (0.05, 0.14, 0.035), rough=0.5)
    flw = M.flat('flor_moreia', (0.85, 0.85, 0.82), rough=0.5)
    v, f = [], []
    for i in range(60):
        az = r.uniform(0, 2 * math.pi)
        tilt = r.uniform(0.05, 0.6)
        L = r.uniform(0.45, 0.75)
        base = Vector((r.gauss(0, 0.06), r.gauss(0, 0.06), 0))
        d = Vector((math.cos(az) * math.sin(tilt), math.sin(az) * math.sin(tilt), math.cos(tilt)))
        side = Vector((-math.sin(az), math.cos(az), 0)) * 0.012
        k = len(v)
        segs = 5
        for s in range(segs + 1):
            t = s / segs
            p = base + d * L * t + Vector((math.cos(az), math.sin(az), 0)) * (t * t * L * 0.25) - Vector((0, 0, t * t * L * 0.15))
            w = side * (1 - 0.8 * t)
            v += [p - w, p + w]
        for s in range(segs):
            f.append((k + 2 * s, k + 2 * s + 1, k + 2 * s + 3, k + 2 * s + 2))
    me = bpy.data.meshes.new('moreia')
    me.from_pydata(v, [], f)
    me.materials.append(leaf)
    o = bpy.data.objects.new('moreia', me); c.objects.link(o)
    parts = [o]
    for i in range(r.randint(3, 6)):
        az = r.uniform(0, 6.28)
        p = (0.18 * math.cos(az), 0.18 * math.sin(az), r.uniform(0.45, 0.7))
        s = C.cyl('flor', c, 0.035, 0.01, p, flw, 6)
        parts.append(s)
    ob = C.join(parts, 'moreia_%d' % seed)
    return C.as_asset([ob], 'A_moreia_%d' % seed)


def belaemilia_model(seed):
    """Bela-emília (Plumbago auriculata): arbusto em moita arredondada com
    folhagem densa e inflorescências azul-claras."""
    r = random.Random(seed)
    c = C.coll('_tmp_veg')
    leaf = M.flat('folha_belaemilia', (0.06, 0.16, 0.035), rough=0.55)
    core = M.flat('miolo_belaemilia', (0.02, 0.05, 0.012), rough=0.8)
    flw = M.flat('flor_belaemilia', (0.42, 0.58, 0.95), rough=0.5)
    R = Vector((0.36, 0.36, 0.34))
    bm = bmesh.new()
    g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in g['verts']:
        v.co = Vector((v.co.x * R.x * 0.85, v.co.y * R.y * 0.85, max(v.co.z, -0.1) * R.z * 0.9 + R.z * 0.85))
    me0 = bpy.data.meshes.new('miolo'); bm.to_mesh(me0); bm.free()
    me0.materials.append(core)
    o0 = bpy.data.objects.new('miolo', me0); c.objects.link(o0)
    lv, lf, fv, ff = [], [], [], []
    for i in range(1100):
        u, w = r.uniform(0, 2 * math.pi), r.uniform(-0.15, 1.0)
        n = Vector((math.cos(u) * math.sqrt(1 - w * w), math.sin(u) * math.sqrt(1 - w * w), w))
        p = Vector((n.x * R.x, n.y * R.y, n.z * R.z + R.z * 0.85)) * r.uniform(0.85, 1.05)
        t1 = n.orthogonal().normalized()
        t1.rotate(Matrix.Rotation(r.uniform(0, 6.28), 3, n))
        t2 = n.cross(t1)
        a, b = 0.045, 0.02
        k = len(lv)
        lv += [p - t1 * a, p - t2 * b + n * 0.01, p + t1 * a, p + t2 * b + n * 0.01]
        lf.append((k, k + 1, k + 2, k + 3))
        if w > 0.1 and r.random() < 0.3:
            q = p + n * 0.02
            k = len(fv)
            fv.append(q)
            for j in range(6):
                aa = 2 * math.pi * j / 6
                fv.append(q + (t1 * math.cos(aa) + t2 * math.sin(aa)) * 0.035)
            for j in range(6):
                ff.append((k, k + 1 + j, k + 1 + (j + 1) % 6))
    me = bpy.data.meshes.new('folhas_be'); me.from_pydata(lv, [], lf); me.materials.append(leaf)
    o1 = bpy.data.objects.new('folhas_be', me); c.objects.link(o1)
    me2 = bpy.data.meshes.new('flores_be'); me2.from_pydata(fv, [], ff); me2.materials.append(flw)
    o2 = bpy.data.objects.new('flores_be', me2); c.objects.link(o2)
    ob = C.join([o0, o1, o2], 'belaemilia_%d' % seed)
    return C.as_asset([ob], 'A_belaemilia_%d' % seed)


# ------------------------------------------------------------- construção
def build(S, light=False):
    col = C.coll('Vegetacao')
    OBJ = S['objetos']
    # árvores Poly Haven (LOD1) com floração
    quar = append_tree('island_tree_01', 'island_tree_01_LOD1', 'T_quaresmeira')
    flower_mix(quar, (0.38, 0.08, 0.62), amount=0.3, scale=4.0, color2=(0.55, 0.2, 0.8))
    extr = append_tree('island_tree_02', 'island_tree_02_LOD1', 'T_extremosa')
    flower_mix(extr, (0.88, 0.88, 0.85), amount=0.32, scale=6.0)
    mana = append_tree('tree_small_02', 'tree_small_02_LOD1', 'T_manaca')
    flower_mix(mana, (0.65, 0.20, 0.55), amount=0.6, scale=5.0, color2=(0.9, 0.85, 0.9))
    jabo = append_tree('island_tree_03', 'island_tree_03_LOD1', 'T_jabuticabeira')
    tint_leaves(jabo, (0.55, 0.75, 0.5))
    ipe = append_tree('jacaranda_tree', 'jacaranda_tree_LOD1', 'T_ipe')
    flower_mix(ipe, (0.95, 0.70, 0.02), amount=1.4, scale=3.0, color2=(1.0, 0.82, 0.1))
    belas = [belaemilia_model(30 + i) for i in range(3)]
    mata1 = append_tree('island_tree_01', 'island_tree_01_LOD1', 'T_mata1')
    mata2 = append_tree('tree_small_02', 'tree_small_02_LOD1', 'T_mata2')

    jer = [jeriva_model(i, h) for i, h in enumerate((4.6, 5.2, 5.8, 6.3))]
    arauc = [araucaria_model(10 + i, h) for i, h in enumerate((17, 20, 23))]
    mor = [moreia_model(20 + i) for i in range(3)]

    for o in OBJ:
        t, x, y = o['t'], o['x'], o['y']
        rot = rnd.uniform(0, 2 * math.pi)
        z = Z(x)
        if t == 'quaresmeira':
            C.instance(quar, col, (x, y, z), rot, rnd.uniform(0.85, 1.0))
        elif t == 'extremosa':
            C.instance(extr, col, (x, y, z), rot, rnd.uniform(0.8, 0.95))
        elif t == 'jeriva':
            dz = 0.33 if any(math.dist((x, y), b[:2]) < 0.5 for b in S['bancos_quadrados']) else 0.0
            C.instance(rnd.choice(jer), col, (x, y, z + dz), rot, 1.0)
        elif t == 'moreia':
            C.instance(rnd.choice(mor), col, (x, y, z + 0.06), rot, rnd.uniform(0.9, 1.1))
        elif t == 'belaemilia':
            C.instance(rnd.choice(belas), col, (x, y, z + 0.0), rot, rnd.uniform(0.85, 1.1))
        elif t == 'manaca':
            C.instance(mana, col, (x, y, z), rot, rnd.uniform(0.85, 0.95))
        elif t == 'ipe':
            C.instance(ipe, col, (x, y, z), rot, 0.34)
        elif t == 'jaboticabeira':
            C.instance(jabo, col, (x, y, z), rot, 1.35)
        elif t == 'araucaria':
            C.instance(rnd.choice(arauc), col, (x, y, z), rot, rnd.uniform(0.85, 1.1))

    # mata existente na Área de Espaços Livres (trilha) e reserva ao fundo
    from shapely.geometry import Polygon, Point
    elup = Polygon(S['quadras'][2]).buffer(0)
    trilha = Polygon(S['trilha'][0]['ext']).buffer(1.5)
    mc = C.coll('Mata', col)
    n = 0
    tries = 0
    while n < (320 if not light else 30) and tries < 8000:
        tries += 1
        x, y = rnd.uniform(178, 300), rnd.uniform(-60, 90)
        if not elup.contains(Point(x, y)) or trilha.contains(Point(x, y)):
            continue
        k = rnd.random()
        a = rnd.choice(arauc) if k < 0.25 else (mata1 if k < 0.65 else mata2)
        s = rnd.uniform(1.2, 2.2) if a in (mata1, mata2) else rnd.uniform(0.8, 1.1)
        C.instance(a, mc, (x, y, Z(x)), rnd.uniform(0, 6.28), s)
        n += 1
    # manchas de mata com araucárias no horizonte (Reserva Maragatos, APP)
    centers = []
    for i in range(0 if light else 28):
        ang = rnd.uniform(-2.8, 2.6)
        dist = rnd.uniform(280, 900)
        centers.append((60 + dist * math.cos(ang), 20 + dist * math.sin(ang), rnd.uniform(35, 110)))
    centers += [(260, 150, 120), (320, -40, 90), (60, 260, 110)]
    for (cx, cy, rr) in centers:
        for i in range(int(rr * 0.9)):
            a, d = rnd.uniform(0, 6.28), rr * math.sqrt(rnd.random())
            x, y = cx + d * math.cos(a), cy + d * math.sin(a)
            if -75 < y < 80 and -235 < x < 300 or math.dist((x, y), (-128, -58)) < 170 or math.dist((x, y), (150, 45)) < 90:
                continue
            k = rnd.random()
            t = rnd.choice(arauc) if k < 0.3 else (mata1 if k < 0.7 else mata2)
            s = rnd.uniform(2.0, 3.2) if t in (mata1, mata2) else rnd.uniform(0.9, 1.2)
            C.instance(t, mc, (x, y, Z(x)), rnd.uniform(0, 6.28), s)
    if '_tmp_veg' in bpy.data.collections:
        bpy.data.collections.remove(bpy.data.collections['_tmp_veg'])
    lc = bpy.context.view_layer.layer_collection.children.get('_assets')
    if lc:
        lc.exclude = True
