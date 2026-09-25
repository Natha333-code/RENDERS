"""Pessoas (recortes fotográficos Skalgubbar, licença livre para
visualização de arquitetura - www.skalgubbar.se) e bicicletas 3D.

As pessoas são 'cartões' com transparência voltados para cada câmera; um
conjunto por câmera (pessoa_<camera>_*), ligado em render.py só na câmera
renderizada.  As posições são sorteadas nas áreas de circulação do projeto
visíveis pela câmera (sem ficar escondidas atrás de árvores/objetos)."""
import bpy, bmesh, math, random, json, os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import lib_common as C
import lib_materials as M
from lib_common import zc_smooth as Z
from build_ground import shp
from build_env import CAMS

PEOPLE = C.ASSETS + '/people'
WALK = [2, 10, 11, 24, 25, 31, 35, 45, 51, 57, 58, 60, 61, 65, 70, 71, 77, 79, 92, 93, 94, 19]
COUPLE = [32, 39, 56, 76, 156, 157, 158, 160]
FAMILY = [118, 120, 121, 46]
DOG = [26, 43, 128]
CYCLE = [29, 64, 90, 96, 97, 98, 101, 105, 111, 113, 114, 115, 73]
BIKE_STAND = [18, 83, 99, 103, 104, 112]
SIT = [9, 23, 63, 68, 72, 88, 136, 141, 143, 145, 153, 154]
KIDS = [81, 119]
GROUND = [89, 138]
HEIGHT = {'walk': 1.72, 'couple': 1.74, 'family': 1.74, 'dog': 1.74, 'cycle': 1.82, 'stand': 1.76,
          'sit': 1.28, 'kid81': 1.25, 'kid119': 0.88, 'ground': 0.85}

_idx = None
_mats = {}


def index():
    global _idx
    if _idx is None:
        _idx = json.load(open(PEOPLE + '/index.json'))
    return _idx


def person_mat(i):
    if i in _mats:
        return _mats[i]
    m = index()[i]
    mat = bpy.data.materials.new('pessoa_%d' % i)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    out = nt.nodes['Material Output']
    im = nt.nodes.new('ShaderNodeTexImage')
    im.image = bpy.data.images.load(os.path.join(PEOPLE, m['file']), check_existing=True)
    im.interpolation = 'Cubic'
    nt.links.new(im.outputs[0], bsdf.inputs['Base Color'])
    nt.links.new(im.outputs[0], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 0.18
    bsdf.inputs['Roughness'].default_value = 0.7
    bsdf.inputs['Specular IOR Level'].default_value = 0.2
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(im.outputs[1], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    _mats[i] = mat
    return mat


def card(name, col, i, x, y, h, cam_loc, flip=False, dz=0.0):
    w, hh = index()[i]['size']
    wd = h * w / hh
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-wd / 2, 0, 0), (wd / 2, 0, 0), (wd / 2, 0, h), (-wd / 2, 0, h)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
    if flip:
        coords = [(1, 0), (0, 0), (0, 1), (1, 1)]
    for li, lp in enumerate(me.loops):
        uv.data[li].uv = coords[lp.vertex_index]
    me.materials.append(person_mat(i))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.location = (x, y, Z(x) + 0.01 + dz)
    ob.rotation_euler = (0, 0, math.atan2(cam_loc.y - y, cam_loc.x - x) - math.pi / 2)
    ob.visible_diffuse = True
    ob.hide_render = True
    return ob


# ------------------------------------------------------------ bicicleta 3D
def bike_asset():
    c = C.coll('_tmp_bike')
    mat_frame = bpy.data.materials.new('bike_quadro')
    mat_frame.use_nodes = True
    nt = mat_frame.node_tree
    b = nt.nodes['Principled BSDF']
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    cols = [(0.02, 0.02, 0.02), (0.5, 0.03, 0.02), (0.02, 0.1, 0.35), (0.75, 0.75, 0.72), (0.05, 0.25, 0.1), (0.8, 0.45, 0.02)]
    els = ramp.color_ramp.elements
    els[0].color = (*cols[0], 1)
    els[1].position = 1.0 / len(cols)
    els[1].color = (*cols[1], 1)
    for k, cc in enumerate(cols[2:], 2):
        e = els.new(k / len(cols))
        e.color = (*cc, 1)
    nt.links.new(oi.outputs['Random'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    b.inputs['Metallic'].default_value = 0.5
    b.inputs['Roughness'].default_value = 0.3
    b.inputs['Coat Weight'].default_value = 0.5
    pneu = M.flat('bike_pneu', (0.015, 0.015, 0.015), rough=0.8)
    aro = M.flat('bike_aro', (0.7, 0.7, 0.72), rough=0.25, metal=1.0)
    selim = M.flat('bike_selim', (0.03, 0.025, 0.02), rough=0.6)
    parts = []
    R = 0.34
    for wx in (-0.52, 0.52):
        for (r, rad, mt) in ((R, 0.019, pneu), (R - 0.02, 0.008, aro)):
            me = bpy.data.meshes.new('roda')
            bm = bmesh.new()
            bmesh.ops.create_circle(bm, cap_ends=False, segments=48, radius=r)
            bm.to_mesh(me); bm.free()
            o = bpy.data.objects.new('roda', me)
            c.objects.link(o)
            o.rotation_euler = (math.pi / 2, 0, 0)
            o.location = (wx, 0, R + 0.02)
            sk = o.modifiers.new('sk', 'SKIN')
            for v in me.skin_vertices[0].data:
                v.radius = (rad, rad)
            me.materials.append(mt)
            parts.append(o)
        for k in range(18):
            a = 2 * math.pi * k / 18
            parts.append(C.tube_path('raio', c, [(wx, 0, R + 0.02), (wx + (R - 0.03) * math.cos(a), 0, R + 0.02 + (R - 0.03) * math.sin(a))],
                                     0.0015, aro))
    zb = R + 0.02
    Rr, F = (-0.52, 0, zb), (0.52, 0, zb)
    B, S, H, Hb = (-0.07, 0, 0.3), (-0.19, 0, 0.84), (0.40, 0, 0.86), (0.44, 0, 0.70)
    for a, bb, r in ((B, S, 0.017), (S, H, 0.015), (B, Hb, 0.019), (B, Rr, 0.011), (S, Rr, 0.01), (Hb, F, 0.013),
                     (H, Hb, 0.02)):
        parts.append(C.tube_path('quadro', c, [a, bb], r, mat_frame))
    parts.append(C.tube_path('guidao', c, [(0.40, 0, 0.86), (0.36, 0, 1.0), (0.33, -0.28, 1.0), (0.33, 0.28, 1.0), (0.36, 0, 1.0)], 0.011, aro))
    parts.append(C.tube_path('canote', c, [S, (-0.21, 0, 0.93)], 0.012, aro))
    parts.append(C.box('selim', c, (0.26, 0.12, 0.05), (-0.23, 0, 0.93), 0, selim, bevel=0.02))
    parts.append(C.tube_path('pedivela', c, [(-0.07, -0.06, 0.3), (-0.02, -0.06, 0.13), (-0.02, -0.14, 0.13)], 0.008, aro))
    parts.append(C.tube_path('pedivela2', c, [(-0.07, 0.06, 0.3), (-0.12, 0.06, 0.47), (-0.12, 0.14, 0.47)], 0.008, aro))
    ob = C.join(parts, 'bicicleta')
    a = C.as_asset([ob], 'A_bicicleta')
    bpy.data.collections.remove(c)
    return a


def bikes(S):
    col = C.coll('Bicicletas')
    A = bike_asset()
    rnd = random.Random(3)
    for o in S['objetos']:
        if o['t'] != 'bicicletario':
            continue
        slots = [-0.5, 0.0, 0.5]
        for k, dx in enumerate(slots):
            if rnd.random() < 0.25:
                continue
            x, y = o['x'] + dx, o['y']
            C.instance(A, col, (x, y + rnd.uniform(-0.05, 0.05), Z(x) + 0.005), math.pi / 2 + (math.pi if k % 2 else 0),
                       1.0, name='bike_%d' % k)
    # bicicletas encostadas no Espaço Garden e junto ao estar leste
    for (x, y, r) in ((93.6, 9.6, 0.4), (94.4, 9.9, 0.55), (-60.0, 7.2, 1.2)):
        C.instance(A, col, (x, y, Z(x)), r, 1.0, name='bike_g')
    return A


# ------------------------------------------------------------ pessoas
def build(S, seed=1):
    rnd = random.Random(seed)
    idx = index()
    bikes(S)
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    paths = unary_union([shp(S['paver']), shp(S['fp_claro']), shp(S['fp_escuro']), shp(S['faixa_elevada'])]).buffer(-0.35)
    ciclo = shp(S['ciclovia'])
    kids = shp(S['kids_areia']).buffer(-1.2)
    pet = shp(S['pet_grama']).buffer(-1.0)
    palco = shp(S['palco']).buffer(-0.6)
    garden = Point(97.0, 8.0).buffer(4.0).difference(paths.buffer(0.3))
    trees = [(o['x'], o['y']) for o in S['objetos'] if o['t'] in ('quaresmeira', 'extremosa', 'jeriva', 'ipe', 'manaca',
                                                                  'jaboticabeira', 'lixeira', 'banco', 'bicicletario')]
    trees += [(b[0], b[1]) for b in S['bancos_quadrados']]
    obstacles = unary_union([Point(t).buffer(0.9) for t in trees])
    # arcos do playground e brinquedos pet
    obstacles = obstacles.union(Point(157.0, 5.8).buffer(3.2)).union(Point(-156.8, 6.8).buffer(1.6)).union(
        Point(-152.3, -0.75).buffer(1.6))
    benches = []
    focos = [(o['x'], o['y']) for o in S['objetos'] if o['t'] == 'grelha'] + [(-153.1, 3.3), (156.4, 3.3)]
    for o in S['objetos']:
        if o['t'] == 'banco':
            f = min(focos, key=lambda q: math.dist(q, (o['x'], o['y'])))
            d = Vector((f[0] - o['x'], f[1] - o['y'], 0)).normalized()
            benches.append((o['x'] + d.x * 0.18, o['y'] + d.y * 0.18))
    for (x, y, w) in S['bancos_quadrados']:
        for dx, dy in ((0, -(w / 2 + 0.05)), (w / 2 + 0.05, 0)):
            benches.append((x + dx, y + dy))

    def sample(poly, n):
        minx, miny, maxx, maxy = poly.bounds
        out = []
        for _ in range(n * 40):
            p = (rnd.uniform(minx, maxx), rnd.uniform(miny, maxy))
            if poly.contains(Point(p)):
                out.append(p)
            if len(out) >= n:
                break
        return out

    for cname, (cp, ct, lens) in CAMS.items():
        cam = bpy.data.objects[cname]
        cl = cam.matrix_world.translation
        aerial = cp[2] > 5
        col = C.coll('Pessoas_' + cname)
        maxd = 260 if aerial else 38
        mind = 20 if aerial else 4.5
        placed = []

        def visible(x, y, h):
            base = Vector((x, y, Z(x) + 0.05))
            top = Vector((x, y, Z(x) + h))
            for p in (base, top):
                v = world_to_camera_view(sc, cam, p)
                if not (0.03 < v.x < 0.97 and 0.03 < v.y < 0.97 and v.z > 0):
                    return False
            d = (cl - Vector((x, y, cl.z))).length
            if not (mind < d < maxd):
                return False
            tgt = Vector((x, y, Z(x) + h * 0.6))
            ray = tgt - cl
            hit = sc.ray_cast(dg, cl, ray.normalized(), distance=ray.length - 0.3)
            return not hit[0]

        def ok(x, y, space=1.6):
            if obstacles.contains(Point(x, y)):
                return False
            return all(math.dist((x, y), q) > space for q in placed)

        def put(kind, pool, area_pts, n, h=None, dz=0.0, space=1.6):
            k = 0
            for (x, y) in area_pts:
                if k >= n:
                    break
                hh = h or HEIGHT[kind] * rnd.uniform(0.95, 1.04)
                if not ok(x, y, space) or not visible(x, y, hh):
                    continue
                i = rnd.choice(pool)
                card('pessoa_%s_%d' % (cname, len(placed)), col, i, x, y, hh, cl, rnd.random() < 0.5, dz)
                placed.append((x, y))
                k += 1

        # área de interesse próxima da câmera
        f = Vector((ct[0] - cp[0], ct[1] - cp[1], 0)).normalized()
        reach = 150 if aerial else 30
        focus = Point(cp[0] + f.x * reach * 0.6, cp[1] + f.y * reach * 0.6).buffer(reach)
        mult = 3 if aerial else 1
        # sentados nos bancos visíveis
        bs = [b for b in benches if focus.contains(Point(b))]
        rnd.shuffle(bs)
        for (x, y) in bs[:(10 if aerial else 4)]:
            hh = HEIGHT['sit']
            if visible(x, y, hh) and all(math.dist((x, y), q) > 0.7 for q in placed):
                card('pessoa_%s_%d' % (cname, len(placed)), col, rnd.choice(SIT), x, y, hh, cl, rnd.random() < 0.5)
                placed.append((x, y))
        # ciclistas na ciclovia
        put('cycle', CYCLE, sample(ciclo.intersection(focus), 60), 3 * mult, space=4.0)
        # caminhantes, casais e famílias nos caminhos
        pts = sample(paths.intersection(focus), 200)
        put('walk', WALK, pts, 6 * mult)
        put('couple', COUPLE, pts[::-1], 2 * mult, space=2.5)
        put('family', FAMILY, pts[50:], 1 * mult, space=2.5)
        put('stand', BIKE_STAND, pts[100:], 1 * mult, space=2.5)
        # palco / Food Parque
        put('walk', WALK, sample(palco.intersection(focus), 20), 1 * mult)
        # crianças no Espaço Kids + adultos
        kp = sample(kids.intersection(focus), 40)
        put('kid81', [81], kp, 2 if not aerial else 1, space=1.2)
        put('kid119', [119], kp[10:], 1, space=1.2)
        put('family', FAMILY, kp[20:], 1, space=2.0)
        # tutores com cães no Espaço Pet
        put('dog', DOG, sample(pet.intersection(focus), 40), 2, space=2.5)
        # caminhantes na trilha de pedrisco
        put('walk', WALK + COUPLE, sample(shp(S['trilha']).buffer(-0.4).intersection(focus), 60), 4, space=3.0)
        # piquenique no gramado do Garden
        put('ground', GROUND, sample(garden.intersection(focus), 20), 2, space=1.5)
        print('pessoas', cname, len(placed))
