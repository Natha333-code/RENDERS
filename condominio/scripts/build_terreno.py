"""Maquete eletrônica do terreno natural – condomínio (PT_TJ_TER_R02).
blender -b --python build_terreno.py -- dados_dir saida.blend [--sem-perimetro] [--sem-arvores]
Terreno: MDT 1 m gerado das curvas de nível do DWG; entorno ilustrativo."""
import bpy, sys, os, math, json, random
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))   # libs do projeto da praça
import lib_common as C
import lib_materials as M

argv = sys.argv[sys.argv.index('--') + 1:]
D, OUT = argv[0], argv[1]
FLAGS = set(argv[2:])
ASSETS = C.ASSETS
TEX = C.TEX

bpy.ops.wm.read_factory_settings(use_empty=True)
J = json.load(open(f'{D}/cena_terreno.json'))
H1 = np.load(f'{D}/terreno_1m.npy').astype(np.float64)
H8 = np.load(f'{D}/terreno_8m.npy').astype(np.float64)
HF = np.load(f'{D}/terreno_100m.npy').astype(np.float64)
X1, Y1, R1 = J['x0_1m'], J['y0_1m'], J['res1']
R8, HALF = J['r8'], J['half']
R100, HALF100 = J['r100'], J['half100']
rnd = random.Random(3)


def _bil(H, x0, y0, r, x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    c = np.clip((x - x0) / r, 0, H.shape[1] - 1.001); rr = np.clip((y - y0) / r, 0, H.shape[0] - 1.001)
    c0 = np.floor(c).astype(int); r0 = np.floor(rr).astype(int); fc = c - c0; fr = rr - r0
    return (H[r0, c0] * (1 - fc) * (1 - fr) + H[r0, c0 + 1] * fc * (1 - fr) +
            H[r0 + 1, c0] * (1 - fc) * fr + H[r0 + 1, c0 + 1] * fc * fr)


def height(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    in1 = (x >= X1) & (x <= X1 + (H1.shape[1] - 1) * R1) & (y >= Y1) & (y <= Y1 + (H1.shape[0] - 1) * R1)
    return np.where(in1, _bil(H1, X1, Y1, R1, x, y), _bil(H8, -HALF, -HALF, R8, x, y))


# ------------------------------------------------------------------ malhas de grade
def grid_mesh(name, H, x0, y0, r, col, mat, keep=None, dz=0.0):
    ny, nx = H.shape
    xs = x0 + np.arange(nx) * r; ys = y0 + np.arange(ny) * r
    X, Y = np.meshgrid(xs, ys)
    co = np.c_[X.ravel(), Y.ravel(), H.ravel() + dz].astype(np.float32)
    i = np.arange(ny * nx).reshape(ny, nx)
    q = np.stack([i[:-1, :-1], i[:-1, 1:], i[1:, 1:], i[1:, :-1]], -1).reshape(-1, 4)
    if keep is not None:
        cx = (X[:-1, :-1] + r / 2).ravel(); cy = (Y[:-1, :-1] + r / 2).ravel()
        q = q[keep(cx, cy)]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co)); me.vertices.foreach_set('co', co.ravel())
    me.loops.add(q.size); me.loops.foreach_set('vertex_index', q.ravel().astype(np.int32))
    me.polygons.add(len(q)); me.polygons.foreach_set('loop_start', (np.arange(len(q)) * 4).astype(np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(len(q), bool))
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    return ob


# ------------------------------------------------------------------ material do campo
def terrain_material():
    mat = bpy.data.materials.new('campo_nativo')
    mat.use_nodes = True
    nt = mat.node_tree; N = nt.nodes; L = nt.links.new
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs['Roughness'].default_value = 0.93
    bsdf.inputs['Specular IOR Level'].default_value = 0.25
    tc = N.new('ShaderNodeTexCoord')
    geo = N.new('ShaderNodeNewGeometry')
    obj = tc.outputs['Object']

    def tex(path, scale, rot=0.0, noncolor=False):
        mp = N.new('ShaderNodeMapping'); L(obj, mp.inputs[0])
        mp.inputs['Scale'].default_value = (1 / scale,) * 3
        mp.inputs['Rotation'].default_value = (0, 0, rot)
        t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True)
        if noncolor: t.image.colorspace_settings.name = 'Non-Color'
        L(mp.outputs[0], t.inputs[0])
        return t

    def noise(scale, detail=4, rough=0.55, dist=0.0):
        n = N.new('ShaderNodeTexNoise'); L(obj, n.inputs[0])
        n.inputs['Scale'].default_value = 1 / scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['Distortion'].default_value = dist
        return n

    def mix(a, b, fac, blend='MIX'):
        m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = blend
        m.clamp_result = True
        for s, v in ((m.inputs[0], fac), (m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(v, (int, float)): s.default_value = v
            elif isinstance(v, tuple): s.default_value = v
            else: L(v, s)
        return m.outputs[2]

    def ramp(src, stops):
        r = N.new('ShaderNodeValToRGB'); L(src, r.inputs[0])
        el = r.color_ramp.elements
        while len(el) > len(stops): el.remove(el[-1])
        while len(el) < len(stops): el.new(0.5)
        for e, (p, c) in zip(el, stops):
            e.position = p; e.color = (*c, 1)
        return r.outputs[0]

    def mr(src, a, b, c=0.0, d=1.0, smooth=True):
        m = N.new('ShaderNodeMapRange'); L(src, m.inputs[0])
        if smooth: m.interpolation_type = 'SMOOTHSTEP'
        m.inputs[1].default_value = a; m.inputs[2].default_value = b
        m.inputs[3].default_value = c; m.inputs[4].default_value = d
        return m.outputs[0]

    def math_(op, a, b):
        m = N.new('ShaderNodeMath'); m.operation = op
        for s, v in ((m.inputs[0], a), (m.inputs[1], b)):
            if isinstance(v, (int, float)): s.default_value = v
            else: L(v, s)
        return m.outputs[0]

    g = f'{TEX}/Grass004/Grass004_2K-JPG'
    g2 = f'{TEX}/Grass001/Grass001_2K-JPG'
    s = f'{TEX}/Ground037/Ground037_2K-JPG'
    ga = tex(g + '_Color.jpg', 2.6)
    gb = tex(g2 + '_Color.jpg', 3.7, 0.9)
    gmix = mix(ga.outputs[0], gb.outputs[0], noise(9).outputs[0])
    # cor de campo nativo do planalto: verde, verde-oliva e palha seca
    n_mid = noise(45, 5, 0.6, 0.4).outputs[0]
    n_big = noise(220, 3, 0.5).outputs[0]
    c_mid = ramp(n_mid, [(0.30, (0.090, 0.125, 0.035)), (0.50, (0.150, 0.170, 0.060)),
                         (0.68, (0.240, 0.215, 0.105))])
    c_big = ramp(n_big, [(0.35, (0.80, 0.95, 0.80)), (0.65, (1.15, 1.02, 0.85))])
    base = mix(c_mid, c_big, 1.0, 'MULTIPLY')
    # textura (luminância relativa) modulando a cor
    lum = N.new('ShaderNodeRGBToBW'); L(gmix, lum.inputs[0])
    lumk = math_('MULTIPLY', lum.outputs[0], 2.7)
    cm = N.new('ShaderNodeMix'); cm.data_type = 'RGBA'; cm.blend_type = 'MULTIPLY'
    cm.inputs[0].default_value = 1.0; L(base, cm.inputs[6])
    cc = N.new('ShaderNodeCombineColor'); L(lumk, cc.inputs[0]); L(lumk, cc.inputs[1]); L(lumk, cc.inputs[2])
    L(cc.outputs[0], cm.inputs[7])
    col = cm.outputs[2]
    # touceiras (capim) – manchas escuras pequenas
    vor = N.new('ShaderNodeTexVoronoi'); L(obj, vor.inputs[0]); vor.inputs['Scale'].default_value = 1 / 1.3
    vor.feature = 'F1'
    tuf = mr(vor.outputs['Distance'], 0.15, 0.5, 0.0, 1.0)
    col = mix((0.05, 0.07, 0.02, 1), col, math_('ADD', math_('MULTIPLY', tuf, 0.55), 0.45))
    # baixadas mais verdes/úmidas
    z = N.new('ShaderNodeSeparateXYZ'); L(obj, z.inputs[0])
    wet = mr(z.outputs[2], 545, 520, 0.0, 0.55)
    col = mix(col, (0.07, 0.13, 0.035, 1), wet)
    # encostas muito íngremes: solo exposto em manchas
    nz = N.new('ShaderNodeSeparateXYZ'); L(geo.outputs['Normal'], nz.inputs[0])
    steep = mr(nz.outputs[2], 0.80, 0.62, 0.0, 1.0)
    soilmask = math_('MULTIPLY', steep, mr(noise(6, 6, 0.65).outputs[0], 0.52, 0.64))
    st = tex(s + '_Color.jpg', 3.0)
    soil = mix(st.outputs[0], (0.55, 0.26, 0.14, 1), 1.0, 'MULTIPLY')
    col = mix(col, soil, math_('MULTIPLY', soilmask, 0.85))
    # entorno distante: mosaico de lavouras/pastagens (ilustrativo)
    dist = N.new('ShaderNodeVectorMath'); dist.operation = 'LENGTH'
    xy = N.new('ShaderNodeCombineXYZ'); L(z.outputs[0], xy.inputs[0]); L(z.outputs[1], xy.inputs[1])
    L(xy.outputs[0], dist.inputs[0])
    wfar = mr(dist.outputs['Value'], 650, 1100, 0.0, 1.0)
    vf = N.new('ShaderNodeTexVoronoi'); L(obj, vf.inputs[0]); vf.inputs['Scale'].default_value = 1 / 260
    vf.inputs['Randomness'].default_value = 0.85
    sep = N.new('ShaderNodeSeparateColor'); L(vf.outputs['Color'], sep.inputs[0])
    fcol = ramp(sep.outputs[0], [(0.00, (0.09, 0.17, 0.03)), (0.22, (0.09, 0.17, 0.03)),
                                 (0.23, (0.16, 0.24, 0.05)), (0.42, (0.16, 0.24, 0.05)),
                                 (0.43, (0.20, 0.10, 0.06)), (0.52, (0.20, 0.10, 0.06)),
                                 (0.53, (0.30, 0.26, 0.11)), (0.66, (0.30, 0.26, 0.11)),
                                 (0.67, (0.12, 0.19, 0.04)), (1.00, (0.12, 0.19, 0.04))])
    # linhas de plantio
    wav = N.new('ShaderNodeTexWave'); L(obj, wav.inputs[0]); wav.inputs['Scale'].default_value = 1 / 6.0
    wav.inputs['Distortion'].default_value = 0.0
    fcol = mix(fcol, mix(fcol, (0, 0, 0, 1), 0.25), mr(wav.outputs[1], 0.4, 0.6))
    col = mix(col, mix(fcol, col, 0.15), math_('MULTIPLY', wfar, 0.85))
    L(col, bsdf.inputs['Base Color'])
    # relevo fino
    nm = tex(g + '_NormalGL.jpg', 2.6, noncolor=True)
    nmap = N.new('ShaderNodeNormalMap'); nmap.inputs['Strength'].default_value = 0.6
    L(nm.outputs[0], nmap.inputs['Color'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.1
    L(vor.outputs['Distance'], bump.inputs['Height']); L(nmap.outputs[0], bump.inputs['Normal'])
    L(bump.outputs[0], bsdf.inputs['Normal'])
    return mat


# ------------------------------------------------------------------ cena
col_t = C.coll('Terreno')
mat = terrain_material()
nyx = H1.shape
x1e, y1e = X1 + (nyx[1] - 1) * R1, Y1 + (nyx[0] - 1) * R1
grid_mesh('terreno_levantamento', H1, X1, Y1, R1, col_t, mat)
ins = 2 * R8
grid_mesh('terreno_entorno', H8, -HALF, -HALF, R8, col_t, mat, dz=-0.4,
          keep=lambda cx, cy: ~((cx > X1 + ins) & (cx < x1e - ins) & (cy > Y1 + ins) & (cy < y1e - ins)))
grid_mesh('terreno_horizonte', HF, -HALF100, -HALF100, R100, col_t, mat, dz=-1.0,
          keep=lambda cx, cy: ~((np.abs(cx) < HALF - 150) & (np.abs(cy) < HALF - 150)))

# plano de fundo até o horizonte (sob as demais malhas)
bpy.ops.mesh.primitive_plane_add(size=400000, location=(0, 0, J['cota_base'] - 3))
fundo = bpy.context.active_object; fundo.name = 'terreno_fundo'; fundo.data.materials.append(mat)
for c in fundo.users_collection: c.objects.unlink(fundo)
col_t.objects.link(fundo)

# perímetro do terreno (linha de demarcação sobre o terreno)
if '--sem-perimetro' not in FLAGS:
    P = np.array(J['perimetro'])
    pts = []
    for a, b in zip(P[:-1], P[1:]):
        n = max(1, int(np.hypot(*(b - a)) / 1.0))
        for k in range(n): pts.append(a + (b - a) * k / n)
    pts.append(P[0]); pts = np.array(pts)
    zz = height(pts[:, 0], pts[:, 1]) + 0.25
    cu = bpy.data.curves.new('perimetro', 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = 0.45; cu.bevel_resolution = 1
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    sp.points.foreach_set('co', np.c_[pts, zz, np.ones(len(pts))].ravel().astype(np.float32))
    sp.use_cyclic_u = True
    pm = bpy.data.materials.new('perimetro_mat'); pm.use_nodes = True
    b = pm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (1.0, 0.75, 0.05, 1)
    b.inputs['Emission Color'].default_value = (1.0, 0.70, 0.05, 1)
    b.inputs['Emission Strength'].default_value = 1.5
    cu.materials.append(pm)
    po = bpy.data.objects.new('perimetro', cu); C.coll('Perimetro').objects.link(po)

# ------------------------------------------------------------------ vegetação do entorno
if '--sem-arvores' not in FLAGS:
    import build_veg as V

    def append_tree(name, colname, newname):
        f = f'{ASSETS}/{name}/{name}.blend'
        with bpy.data.libraries.load(f, link=False) as (src, dst):
            dst.collections = [colname]
        c = dst.collections[0]; c.name = newname
        return c

    lib = C.coll('_assets')
    kinds = C.coll('_arvores', lib)
    trees = [append_tree('island_tree_01', 'island_tree_01_LOD1', 'T1'),
             append_tree('island_tree_02', 'island_tree_02_LOD1', 'T2'),
             append_tree('tree_small_02', 'tree_small_02_LOD1', 'T3')]
    V.tint_leaves(trees[1], (0.6, 0.8, 0.55))
    arauc = [V.araucaria_model(10 + i, h) for i, h in enumerate((17, 20, 23))]
    allk = trees + arauc
    for c in allk:
        if c.name in lib.children:
            lib.children.unlink(c)
        kinds.children.link(c)
    if '_tmp_veg' in bpy.data.collections:
        bpy.data.collections.remove(bpy.data.collections['_tmp_veg'])
    T = np.array(J['arvores'])
    n = len(T)
    rr = np.random.default_rng(11)
    kind = np.where(rr.random(n) < 0.30, rr.integers(3, 6, n), rr.integers(0, 3, n))
    scl = np.where(kind >= 3, rr.uniform(0.75, 1.15, n), rr.uniform(1.4, 2.6, n))
    z = height(T[:, 0], T[:, 1]) - 0.3
    me = bpy.data.meshes.new('pts_arvores')
    me.vertices.add(n); me.vertices.foreach_set('co', np.c_[T, z].ravel().astype(np.float32))
    for nm, dt, val in (('kind', 'INT', kind.astype(np.int32)), ('escala', 'FLOAT', scl.astype(np.float32)),
                        ('rotz', 'FLOAT', rr.uniform(0, 6.283, n).astype(np.float32))):
        a = me.attributes.new(nm, dt, 'POINT'); a.data.foreach_set('value', val)
    ob = bpy.data.objects.new('mata_entorno', me); C.coll('Vegetacao').objects.link(ob)
    ng = bpy.data.node_groups.new('instanciar_arvores', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    Nn = ng.nodes; Ll = ng.links.new
    gi = Nn.new('NodeGroupInput'); go = Nn.new('NodeGroupOutput')
    ci = Nn.new('GeometryNodeCollectionInfo'); ci.inputs['Collection'].default_value = kinds
    ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    ci.transform_space = 'ORIGINAL'
    iop = Nn.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True

    def attr(name, dt):
        a = Nn.new('GeometryNodeInputNamedAttribute'); a.data_type = dt; a.inputs['Name'].default_value = name
        return a.outputs['Attribute']
    Ll(gi.outputs[0], iop.inputs['Points']); Ll(ci.outputs[0], iop.inputs['Instance'])
    Ll(attr('kind', 'INT'), iop.inputs['Instance Index'])
    Ll(attr('escala', 'FLOAT'), iop.inputs['Scale'])
    cx = Nn.new('ShaderNodeCombineXYZ'); Ll(attr('rotz', 'FLOAT'), cx.inputs[2])
    e2r = Nn.new('FunctionNodeEulerToRotation'); Ll(cx.outputs[0], e2r.inputs[0])
    Ll(e2r.outputs[0], iop.inputs['Rotation'])
    Ll(iop.outputs[0], go.inputs[0])
    md = ob.modifiers.new('arvores', 'NODES'); md.node_group = ng
    lc = bpy.context.view_layer.layer_collection.children.get('_assets')
    if lc: lc.exclude = True

# ------------------------------------------------------------------ céu, sol e câmeras
sc = bpy.context.scene
w = bpy.data.worlds.new('ceu'); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes['Background']
env = nt.nodes.new('ShaderNodeTexEnvironment')
env.image = bpy.data.images.load(ASSETS + '/hdri/kloofendal_48d_partly_cloudy_puresky_4k.exr')
mp = nt.nodes.new('ShaderNodeMapping'); tco = nt.nodes.new('ShaderNodeTexCoord')
nt.links.new(tco.outputs['Generated'], mp.inputs[0]); nt.links.new(mp.outputs[0], env.inputs[0])
nt.links.new(env.outputs[0], bg.inputs[0])
# sol do HDRI (elev. 47,8°) girado para noroeste: tarde em Passo Fundo (hemisfério sul)
SUN_DIR = (-0.62, 0.78)
sun_tex = math.atan2(0.562, -0.827)
mp.inputs['Rotation'].default_value = (0, 0, sun_tex - math.atan2(SUN_DIR[1], SUN_DIR[0]))
bg.inputs[1].default_value = 0.9
sun = bpy.data.lights.new('sol', 'SUN'); sun.energy = 3.2; sun.angle = math.radians(0.6)
sun.color = (1.0, 0.95, 0.87)
so = bpy.data.objects.new('sol', sun); sc.collection.objects.link(so)
el = math.radians(47.8)
sv = Vector((SUN_DIR[0] * math.cos(el), SUN_DIR[1] * math.cos(el), math.sin(el)))
so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()


def gz(x, y): return float(height(x, y))


# nome: (posição, alvo, lente, tipo); z < 30 => altura sobre o terreno
CAMS = {
    'aerea_sudeste':  ((520, -560, 300), (-30, 20, 0), 35, 'P'),
    'aerea_sudoeste': ((-560, -520, 300), (-20, 30, 0), 35, 'P'),
    'aerea_norte':    ((120, 900, 260), (-30, -40, 0), 35, 'P'),
    'aerea_leste':    ((480, 60, 90), (-20, 20, 0), 30, 'P'),
    'drone_alto':     ((300, -380, 650), (-15, 30, 0), 30, 'P'),
    'mirante_topo':   ((45, -125, 1.65), (420, -40, 70), 24, 'P'),
    'acesso_norte':   ((-60, 215, 1.65), (-20, -100, 1.0), 24, 'P'),
    'vale_leste':     ((260, -40, 1.65), (-20, 10, 40), 24, 'P'),
}
cc = C.coll('Cameras')
for name, (p, t, lens, kind) in CAMS.items():
    cam = bpy.data.cameras.new(name); cam.lens = lens
    cam.clip_start = 0.1; cam.clip_end = 40000
    ob = bpy.data.objects.new(name, cam); cc.objects.link(ob)
    pz = p[2] + gz(p[0], p[1]) if p[2] < 30 else p[2] + 620
    tz = t[2] + gz(t[0], t[1])
    ob.location = (p[0], p[1], pz)
    ob['solo'] = p[2] < 5          # câmera ao nível do observador
    ob.rotation_euler = (Vector((t[0], t[1], tz)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
# grama 3D junto às câmeras ao nível do observador
if '--sem-grama' not in FLAGS:
    import build_grama
    ground = []
    for name, (p, t, lens, kind) in CAMS.items():
        if p[2] < 5:
            d = np.array(t[:2], float) - np.array(p[:2], float); d /= np.linalg.norm(d)
            ground.append((p[0], p[1], d[0], d[1]))
    build_grama.build(height, H1, X1, Y1, R1, ground, C.coll, grid_mesh)
    lc = bpy.context.view_layer.layer_collection.children.get('_assets')
    if lc: lc.exclude = True

# vista superior ortográfica (planta humanizada)
cam = bpy.data.cameras.new('planta'); cam.type = 'ORTHO'; cam.ortho_scale = 900
cam.clip_start = 1; cam.clip_end = 5000
ob = bpy.data.objects.new('planta', cam); cc.objects.link(ob)
ob.location = (-10, 40, 1500); ob['res'] = (1600, 2000)

r = sc.render
r.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = 64; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 2
sc.cycles.transparent_max_bounces = 16
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
r.image_settings.file_format = 'PNG'
# perspectiva aérea (névoa) só na geometria
vl = sc.view_layers[0]; vl.use_pass_mist = True; vl.use_pass_environment = True
w.mist_settings.start = 300; w.mist_settings.depth = 30000; w.mist_settings.falloff = 'INVERSE_QUADRATIC'
r.film_transparent = True
sc.use_nodes = True
ct = sc.node_tree
for n in list(ct.nodes): ct.nodes.remove(n)
rl = ct.nodes.new('CompositorNodeRLayers')
mix = ct.nodes.new('CompositorNodeMixRGB'); mix.inputs[2].default_value = (0.72, 0.78, 0.86, 1)
mm = ct.nodes.new('CompositorNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = 0.85
ct.links.new(rl.outputs['Mist'], mm.inputs[0]); ct.links.new(mm.outputs[0], mix.inputs[0])
ct.links.new(rl.outputs['Image'], mix.inputs[1])
sa = ct.nodes.new('CompositorNodeSetAlpha')
ct.links.new(mix.outputs[0], sa.inputs[0]); ct.links.new(rl.outputs['Alpha'], sa.inputs[1])
ao = ct.nodes.new('CompositorNodeAlphaOver')
ct.links.new(rl.outputs['Env'], ao.inputs[1]); ct.links.new(sa.outputs[0], ao.inputs[2])
comp = ct.nodes.new('CompositorNodeComposite'); comp.use_alpha = False
ct.links.new(ao.outputs[0], comp.inputs[0])
sc.camera = bpy.data.objects['aerea_sudeste']
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=False)
print('SALVO', OUT)
