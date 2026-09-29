"""Cena Blender da terraplenagem (Plato Geral - Rua B) a partir do DEM de prep_dem.py.

  blender -b --python build_render.py -- dem.npz saida.png LARG ALT AMOSTRAS [vista]

Terreno final = LandXML (plato) + curvas de nível do DWG (entorno, já modelado).
Corte/aterro = terreno final - terreno natural reconstruído (atributo 'dz').
Materiais 100% procedurais (sem texturas externas)."""
import bpy, sys, math, numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
DEM, OUT = argv[0], argv[1]
W, H, SPP = int(argv[2]), int(argv[3]), int(argv[4])
VIEW = argv[5] if len(argv) > 5 else 'ruab'
STYLE = argv[6] if len(argv) > 6 else 'realista'      # 'realista' (corte/aterro), 'conceitual' (maquete)
#                                                       ou 'foto' (materiais realistas, sem manchas: base p/ Runway)

O = np.array([340800.0, 6994550.0, 720.0])       # origem local (UTM SIRGAS 22S)
Z = np.load(DEM)
xs, ys = Z['xs'] - O[0], Z['ys'] - O[1]
R = float(xs[1] - xs[0])
FIN = Z['FIN'].astype(np.float64)
EG = Z['EG'].astype(np.float64)
dz = Z['dz'].astype(np.float64)
from scipy.ndimage import gaussian_filter          # bordas suaves (anti-serrilhado)
side = gaussian_filter(Z['inS'].astype(np.float64), 0.9)
roadf = gaussian_filter(Z['road'].astype(np.float64), 0.9)
rng = np.random.default_rng(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def zat(x, y):
    """cota do terreno final (coords locais)."""
    i = int(np.clip(round((x - xs[0]) / R), 0, len(xs) - 1))
    j = int(np.clip(round((y - ys[0]) / R), 0, len(ys) - 1))
    return FIN[j, i] - O[2]


# ------------------------------------------------------------------ malhas
def mesh_from(name, verts, quads, attrs=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts)); me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    me.loops.add(quads.size); me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4))
    me.polygons.foreach_set('loop_total', np.full(len(quads), 4))
    for an, arr in (attrs or {}).items():
        a = me.attributes.new(an, 'FLOAT', 'POINT')
        a.data.foreach_set('value', arr.astype(np.float32).ravel())
    me.update(calc_edges=True); me.validate()
    me.polygons.foreach_set('use_smooth', np.ones(len(quads), bool))
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    return ob


def grid(Zg, step, crop=None, attrs=None):
    zz = Zg[::step, ::step]; ny, nx = zz.shape
    GX, GY = np.meshgrid(xs[::step], ys[::step])
    verts = np.c_[GX.ravel(), GY.ravel(), (zz - O[2]).ravel()]
    ii = np.arange(ny * nx).reshape(ny, nx)
    q = np.c_[ii[:-1, :-1].ravel(), ii[:-1, 1:].ravel(), ii[1:, 1:].ravel(), ii[1:, :-1].ravel()]
    if crop is not None:
        k = crop[::step, ::step]
        q = q[(k[:-1, :-1] & k[:-1, 1:] & k[1:, 1:] & k[1:, :-1]).ravel()]
    at = {k: v[::step, ::step] for k, v in (attrs or {}).items()}
    return verts, q, at


# terreno final (calçada 15 cm acima = meio-fio)
gyy, gxx = np.gradient(FIN, R)
slope = np.hypot(gxx, gyy)
lev = np.abs(FIN * 2 - np.round(FIN * 2)) / 2                       # dist. vertical à curva de 0,50 m
cn = np.clip(1 - (lev / np.maximum(slope, 1e-3)) / 0.12, 0, 1) * (slope > 0.06)
sideh = gaussian_filter(Z['inS'].astype(np.float64), 1.6) if STYLE == 'conceitual' else side
v, q, at = grid(FIN + 0.15 * sideh, 1, attrs=dict(cn=cn, 
    dz=dz, road=roadf, side=side, foot=Z['foot'], lx=Z['lx']))
ter = mesh_from('Terreno', v, q, at)

# anel externo (horizonte): extrapola a borda do DEM e suaviza para a média
S = 2400.0; n = 121
gx = np.linspace(-S, S, n); GX, GY = np.meshgrid(gx, gx)
cx = np.clip(GX, xs[0], xs[-1]); cy = np.clip(GY, ys[0], ys[-1])
ii = np.clip(((cx - xs[0]) / R).round().astype(int), 0, len(xs) - 1)
jj = np.clip(((cy - ys[0]) / R).round().astype(int), 0, len(ys) - 1)
edge = FIN[jj, ii] - O[2]
dout = np.maximum(np.maximum(xs[0] - GX, GX - xs[-1]), np.maximum(ys[0] - GY, GY - ys[-1]))
wgt = np.clip(dout / 600.0, 0, 1)
zr = edge * (1 - wgt) + (np.nanmean(FIN) - O[2]) * wgt - 0.35 * (dout > 0)
vv = np.c_[GX.ravel(), GY.ravel(), zr.ravel()]
ii = np.arange(n * n).reshape(n, n)
qq = np.c_[ii[:-1, :-1].ravel(), ii[:-1, 1:].ravel(), ii[1:, 1:].ravel(), ii[1:, :-1].ravel()]
inside = ((GX[:-1, :-1] >= xs[0] + 5) & (GX[:-1, 1:] <= xs[-1] - 5) &
          (GY[:-1, :-1] >= ys[0] + 5) & (GY[1:, :-1] <= ys[-1] - 5)).ravel()
ring = mesh_from('Horizonte', vv, qq[~inside])


# ------------------------------------------------------------------ nós auxiliares
class NT:
    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree; self.L = self.nt.links
        for nd in list(self.nt.nodes):
            self.nt.nodes.remove(nd)
        self.out = self.new('ShaderNodeOutputMaterial')
        self.bsdf = self.new('ShaderNodeBsdfPrincipled')
        self.L.new(self.bsdf.outputs[0], self.out.inputs[0])
        self.P = self.new('ShaderNodeTexCoord').outputs['Object']

    def new(self, t):
        return self.nt.nodes.new(t)

    def link(self, a, sock):
        if isinstance(a, (int, float)):
            sock.default_value = a
        elif isinstance(a, tuple):
            sock.default_value = a + (1,) if len(a) == 3 else a
        else:
            self.L.new(a, sock)

    def attr(self, name):
        nd = self.new('ShaderNodeAttribute'); nd.attribute_name = name
        return nd.outputs['Fac']

    def math(self, op, a, b=0.0, clamp=False):
        nd = self.new('ShaderNodeMath'); nd.operation = op; nd.use_clamp = clamp
        self.link(a, nd.inputs[0]); self.link(b, nd.inputs[1])
        return nd.outputs[0]

    def noise(self, scale, detail=6, rough=0.6):
        nd = self.new('ShaderNodeTexNoise')
        nd.inputs['Scale'].default_value = scale
        nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough
        self.L.new(self.P, nd.inputs['Vector'])
        return nd.outputs['Fac']

    def ramp(self, fac, stops):
        nd = self.new('ShaderNodeValToRGB'); el = nd.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], stops[0][1] + (1,)
        el[1].position, el[1].color = stops[-1][0], stops[-1][1] + (1,)
        for p, c in stops[1:-1]:
            e = el.new(p); e.color = c + (1,)
        self.link(fac, nd.inputs[0])
        return nd.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        nd = self.new('ShaderNodeMix'); nd.data_type = 'RGBA'; nd.blend_type = blend
        self.link(fac, nd.inputs[0]); self.link(a, nd.inputs[6]); self.link(b, nd.inputs[7])
        return nd.outputs[2]

    def bump(self, h, strength, dist=0.05):
        nd = self.new('ShaderNodeBump')
        nd.inputs['Strength'].default_value = strength; nd.inputs['Distance'].default_value = dist
        self.link(h, nd.inputs['Height'])
        self.L.new(nd.outputs[0], self.bsdf.inputs['Normal'])


def spec(bsdf, v):
    for k in ('Specular IOR Level', 'Specular'):
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = v
            return


def grass_color(t):
    macro = t.ramp(t.noise(0.035, 4), [(0.30, (0.100, 0.150, 0.038)), (0.50, (0.150, 0.200, 0.055)),
                                       (0.70, (0.215, 0.215, 0.080))])
    micro = t.ramp(t.noise(1.6, 8), [(0.35, (0.78, 0.78, 0.78)), (0.65, (1.12, 1.12, 1.06))])
    g = t.mix(1.0, macro, micro, 'MULTIPLY')
    straw = t.math('GREATER_THAN', t.noise(0.30, 3), 0.62)
    return t.mix(t.math('MULTIPLY', straw, 0.45), g, (0.30, 0.26, 0.13))


# ------------------------------------------------------------------ material do terreno
mat = bpy.data.materials.new('Terreno'); t = NT(mat)
grass = grass_color(t)
soil = t.ramp(t.noise(0.9, 7), [(0.35, (0.290, 0.100, 0.048)), (0.55, (0.390, 0.155, 0.078)),
                                (0.75, (0.460, 0.225, 0.125))])          # latossolo vermelho
soil_c = t.ramp(t.noise(0.08, 3), [(0.3, (0.40, 0.235, 0.145)), (0.7, (0.47, 0.31, 0.20))])
lxf = t.attr('lx')
soil = t.mix(t.math('MULTIPLY', lxf, 0.45), soil, soil_c)                  # plato compactado
asph = t.ramp(t.noise(6.0, 8), [(0.3, (0.030, 0.030, 0.032)), (0.7, (0.062, 0.062, 0.064))])
conc = t.ramp(t.noise(3.0, 6), [(0.3, (0.40, 0.39, 0.36)), (0.7, (0.54, 0.53, 0.49))])

dzf = t.attr('dz'); absdz = t.math('ABSOLUTE', dzf)
modif = t.math('MAXIMUM', t.math('GREATER_THAN', absdz, 0.08), t.math('MULTIPLY', t.attr('foot'), lxf))
base = t.mix(modif, grass, soil)
def sharp(f):          # borda nítida a partir da máscara suavizada
    return t.math('DIVIDE', t.math('SUBTRACT', f, 0.38), 0.24, clamp=True)


base = t.mix(sharp(t.attr('side')), base, conc)
base = t.mix(sharp(t.attr('road')), base, asph)

# destaque: corte (amarelo->vermelho) / aterro (azul claro->azul), por |dz|
cut01 = t.math('DIVIDE', t.math('MULTIPLY', dzf, -1.0), 3.5, clamp=True)
fil01 = t.math('DIVIDE', dzf, 2.0, clamp=True)
cut_c = t.ramp(cut01, [(0.0, (0.98, 0.80, 0.25)), (0.35, (0.95, 0.40, 0.07)), (1.0, (0.60, 0.02, 0.02))])
fil_c = t.ramp(fil01, [(0.0, (0.60, 0.88, 1.00)), (0.40, (0.14, 0.50, 0.95)), (1.0, (0.02, 0.14, 0.58))])
cf = t.mix(t.math('GREATER_THAN', dzf, 0.0), cut_c, fil_c)
# isolinhas de espessura a cada 0,50 m
fr = t.math('FRACT', t.math('MULTIPLY', absdz, 2.0))
iso = t.math('MULTIPLY', t.math('LESS_THAN', fr, 0.07), t.math('GREATER_THAN', absdz, 0.3))
cf = t.mix(t.math('MULTIPLY', iso, 0.5), cf, (0.03, 0.02, 0.02))
alpha = t.math('MULTIPLY', t.math('DIVIDE', t.math('SUBTRACT', absdz, 0.04), 0.45, clamp=True), 0.66)
cf = t.mix(1.0, cf, t.ramp(t.noise(1.1, 6), [(0.3, (0.80, 0.80, 0.80)), (0.7, (1.08, 1.08, 1.08))]), 'MULTIPLY')
col = t.mix(t.math('MULTIPLY', alpha, 0.0 if STYLE == 'foto' else 1.0), base, cf)   # 'foto': sem manchas
t.link(col, t.bsdf.inputs['Base Color'])
t.bsdf.inputs['Roughness'].default_value = 0.93
spec(t.bsdf, 0.2)
t.bump(t.noise(22.0, 6), 0.3)
if STYLE == 'conceitual':
    # maquete: tons claros, sem manchas de corte/aterro; plato em areia clara,
    # curvas de nível do terreno final a cada 0,50 m como traço fino
    mat = bpy.data.materials.new('TerrenoConceitual'); t = NT(mat)
    lxf = t.attr('lx'); dzf = t.attr('dz')
    modif = t.math('MAXIMUM', t.math('GREATER_THAN', t.math('ABSOLUTE', dzf), 0.08),
                   t.math('MULTIPLY', t.attr('foot'), lxf))
    var = t.ramp(t.noise(0.05, 3), [(0.3, (0.96, 0.96, 0.96)), (0.7, (1.03, 1.03, 1.03))])
    base = t.mix(modif, (0.46, 0.53, 0.42), (0.78, 0.69, 0.55))
    base = t.mix(1.0, base, var, 'MULTIPLY')
    base = t.mix(sharp(t.attr('side')), base, (0.62, 0.62, 0.60))
    road_ = sharp(t.attr('road'))
    base = t.mix(road_, base, (0.36, 0.37, 0.39))
    cl = t.math('MULTIPLY', t.math('GREATER_THAN', t.attr('cn'), 0.35),
                t.math('SUBTRACT', 1.0, t.math('MAXIMUM', road_, sharp(t.attr('side')))))
    base = t.mix(t.math('MULTIPLY', cl, 0.0), base, (0.25, 0.24, 0.22))   # curvas desligadas
    t.link(base, t.bsdf.inputs['Base Color'])
    t.bsdf.inputs['Roughness'].default_value = 0.85; spec(t.bsdf, 0.15)
ter.data.materials.append(mat)

# horizonte: grama/campo
mat2 = bpy.data.materials.new('Campo'); t2 = NT(mat2)
t2.link(grass_color(t2) if STYLE != 'conceitual' else (0.58, 0.63, 0.52), t2.bsdf.inputs['Base Color'])
t2.bsdf.inputs['Roughness'].default_value = 0.95; spec(t2.bsdf, 0.15)
ring.data.materials.append(mat2)

# ------------------------------------------------------------------ limite do plato (LandXML)
bnd = Z['lxbnd'] - O[:2]
cu = bpy.data.curves.new('LimitePlato', 'CURVE'); cu.dimensions = '3D'
sp = cu.splines.new('POLY'); sp.points.add(len(bnd) - 1)
for k, (x, y) in enumerate(bnd):
    sp.points[k].co = (x, y, zat(x, y) + 0.06, 1)
sp.use_cyclic_u = True
cu.bevel_depth = 0.07; cu.bevel_resolution = 2
lim = bpy.data.objects.new('LimitePlato', cu); sc.collection.objects.link(lim)
mlim = bpy.data.materials.new('Limite'); tlim = NT(mlim)
tlim.bsdf.inputs['Base Color'].default_value = (1.0, 0.95, 0.75, 1)
tlim.bsdf.inputs['Emission Color'].default_value = (1.0, 0.95, 0.75, 1)
tlim.bsdf.inputs['Emission Strength'].default_value = 1.5
lim.data.materials.append(mlim); lim.visible_shadow = False
if STYLE in ('conceitual', 'foto'):
    lim.hide_render = True

# ------------------------------------------------------------------ vegetação de fundo (procedural)
tc = bpy.data.collections.new('ArvoresModelo'); sc.collection.children.link(tc)
tc.hide_render = False
mt = bpy.data.materials.new('Tronco'); tt = NT(mt)
tt.bsdf.inputs['Base Color'].default_value = (0.09, 0.06, 0.04, 1)
ml = bpy.data.materials.new('Folhagem'); tl = NT(ml)
lc = tl.ramp(tl.noise(1.2, 5), [(0.35, (0.030, 0.060, 0.018)), (0.65, (0.075, 0.120, 0.035))])
tl.link(lc if STYLE != 'conceitual' else (0.80, 0.84, 0.76), tl.bsdf.inputs['Base Color'])
tl.bsdf.inputs['Roughness'].default_value = 0.8
if STYLE == 'conceitual':
    tt.bsdf.inputs['Base Color'].default_value = (0.70, 0.68, 0.64, 1)
tl.bump(tl.noise(4.0, 4), 0.6, 0.3)


def make_tree(name, kind, seed):
    r = np.random.default_rng(seed); parts = []
    h = r.uniform(6, 11) if kind == 'folhosa' else r.uniform(12, 18)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18 if kind == 'folhosa' else 0.25,
                                        depth=h * 0.7, location=(0, 0, h * 0.35))
    tr = bpy.context.object; tr.data.materials.append(mt); parts.append(tr)
    if kind == 'folhosa':
        for i in range(5):
            s = r.uniform(1.6, 2.8)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=s,
                location=(r.uniform(-1.4, 1.4), r.uniform(-1.4, 1.4), h * 0.62 + r.uniform(-0.6, 1.6)))
            parts.append(bpy.context.object)
    else:   # araucária: copa em "taça"
        for i in range(7):
            a = i / 7 * 2 * math.pi
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=5, radius=1.3,
                location=(math.cos(a) * 2.8, math.sin(a) * 2.8, h * 0.93 + r.uniform(-0.3, 0.3)))
            o = bpy.context.object; o.scale = (1.8, 1.8, 0.45); parts.append(o)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=5, radius=1.8, location=(0, 0, h * 0.97))
        o = bpy.context.object; o.scale = (1.5, 1.5, 0.4); parts.append(o)
    for o in parts[1:]:
        o.data.materials.append(ml)
        d = o.modifiers.new('d', 'DISPLACE'); tx = bpy.data.textures.new(name + 'tx', 'CLOUDS')
        tx.noise_scale = 0.6; d.texture = tx; d.strength = 0.5
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    for o in parts[1:]:
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier='d')
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.object; ob.name = name
    for c in ob.users_collection:
        c.objects.unlink(ob)
    tc.objects.link(ob)
    ob.location = (0, 0, -1000)
    return ob


models = [make_tree('F%d' % i, 'folhosa', i) for i in range(4)] + \
         [make_tree('A%d' % i, 'araucaria', 10 + i) for i in range(3)]
tc.hide_render = True
for m in models:
    m.hide_render = False

road = Z['road']; foot = Z['foot']; blk = Z['inQ']; sidem = Z['inS']


def free_px(x, y):
    i = int(round((x - xs[0]) / R)); j = int(round((y - ys[0]) / R))
    if not (0 <= i < len(xs) and 0 <= j < len(ys)):
        return 'fora'
    if road[j, i] or sidem[j, i] or foot[j, i]:
        return None
    return 'blk' if blk[j, i] else 'livre'


def place(m, x, y, s):
    o = m.copy(); o.data = m.data
    inside = xs[0] < x < xs[-1] and ys[0] < y < ys[-1]
    o.location = (x, y, (zat(x, y) if inside else ring_z(x, y)) - 0.2)
    o.rotation_euler = (0, 0, rng.uniform(0, 6.28)); o.scale = (s, s, s)
    sc.collection.objects.link(o)


def ring_z(x, y):
    i = int(np.clip(round((x + S) / (2 * S) * (n - 1)), 0, n - 1))
    j = int(np.clip(round((y + S) / (2 * S) * (n - 1)), 0, n - 1))
    return zr[j, i]


# mata nativa (fundo) fora do loteamento e algumas árvores isoladas em áreas livres
cnt = 0
for _ in range(16000):
    x, y = rng.uniform(-S * 0.55, S * 0.55, 2)
    d = math.hypot(x, y)
    if d < 150:
        continue
    st = free_px(x, y)
    if st is None or st == 'blk':
        continue
    # densidade maior longe (mata), rala perto
    if rng.random() > np.clip((d - 150) / 200, 0.04, 1.0):
        continue
    kind = rng.random()
    m = models[rng.integers(4, 7)] if kind < 0.25 else models[rng.integers(0, 4)]
    place(m, x, y, rng.uniform(0.8, 1.3)); cnt += 1
print('arvores', cnt)

# ------------------------------------------------------------------ escala humana (estilo conceitual)
if STYLE == 'conceitual':
    mh = bpy.data.materials.new('Figura'); th = NT(mh)
    th.bsdf.inputs['Base Color'].default_value = (0.80, 0.80, 0.78, 1)
    A0 = np.array([340820.9, 6994591.3]) - O[:2]; AV = np.array([-0.7156, 0.6985]); NV = np.array([AV[1], -AV[0]])
    for stt, lat, hh in ((-40, -6.9, 1.72), (-37.5, -6.2, 1.62), (-12, -6.6, 1.75)):
        p = A0 + AV * stt + NV * lat; z0 = zat(*p) + 0.15
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.19, depth=hh - 0.3, location=(p[0], p[1], z0 + (hh - 0.3) / 2))
        b = bpy.context.object
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.12, location=(p[0], p[1], z0 + hh - 0.14))
        hd = bpy.context.object
        for o in (b, hd):
            o.data.materials.append(mh)
            o.data.polygons.foreach_set('use_smooth', np.ones(len(o.data.polygons), bool))

# ------------------------------------------------------------------ luz e céu
world = bpy.data.worlds.new('Mundo'); sc.world = world; world.use_nodes = True
wn = world.node_tree; bg = wn.nodes['Background']
sky = wn.nodes.new('ShaderNodeTexSky'); sky.sky_type = 'NISHITA'
SUN_EL, SUN_AZ = math.radians(27), math.radians(48)          # az a partir do Norte (+Y), horário
sky.sun_elevation = SUN_EL; sky.sun_rotation = math.pi / 2 - SUN_AZ + math.pi / 2
sky.sun_disc = False; sky.altitude = 700; sky.air_density = 1.0; sky.dust_density = 0.6
sky.ozone_density = 2.0
# nuvens: ruído projetado num plano alto, só acima do horizonte
wtc = wn.nodes.new('ShaderNodeTexCoord')
sep = wn.nodes.new('ShaderNodeSeparateXYZ'); wn.links.new(wtc.outputs['Generated'], sep.inputs[0])
zc = wn.nodes.new('ShaderNodeMath'); zc.operation = 'MAXIMUM'; zc.inputs[1].default_value = 0.03
wn.links.new(sep.outputs[2], zc.inputs[0])
proj = wn.nodes.new('ShaderNodeVectorMath'); proj.operation = 'DIVIDE'
wn.links.new(wtc.outputs['Generated'], proj.inputs[0])
cz = wn.nodes.new('ShaderNodeCombineXYZ'); [wn.links.new(zc.outputs[0], cz.inputs[k]) for k in range(3)]
wn.links.new(cz.outputs[0], proj.inputs[1])
cn = wn.nodes.new('ShaderNodeTexNoise'); cn.inputs['Scale'].default_value = 1.3
cn.inputs['Detail'].default_value = 8; cn.inputs['Roughness'].default_value = 0.62
wn.links.new(proj.outputs[0], cn.inputs['Vector'])
cr = wn.nodes.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].position = 0.52
cr.color_ramp.elements[1].position = 0.72; wn.links.new(cn.outputs['Fac'], cr.inputs[0])
hz = wn.nodes.new('ShaderNodeMapRange'); hz.inputs[1].default_value = 0.02; hz.inputs[2].default_value = 0.18
wn.links.new(sep.outputs[2], hz.inputs[0])
cm_ = wn.nodes.new('ShaderNodeMath'); cm_.operation = 'MULTIPLY'
wn.links.new(cr.outputs[0], cm_.inputs[0]); wn.links.new(hz.outputs[0], cm_.inputs[1])
cm2 = wn.nodes.new('ShaderNodeMath'); cm2.operation = 'MULTIPLY'; cm2.inputs[1].default_value = 0.85
wn.links.new(cm_.outputs[0], cm2.inputs[0])
cmix = wn.nodes.new('ShaderNodeMix'); cmix.data_type = 'RGBA'
wn.links.new(cm2.outputs[0], cmix.inputs[0]); wn.links.new(sky.outputs[0], cmix.inputs[6])
cmix.inputs[7].default_value = (5.5, 5.5, 5.6, 1)
wn.links.new(cmix.outputs[2], bg.inputs[0]); bg.inputs[1].default_value = 0.22
sd = Vector((math.sin(SUN_AZ) * math.cos(SUN_EL), math.cos(SUN_AZ) * math.cos(SUN_EL), math.sin(SUN_EL)))
sun = bpy.data.objects.new('Sol', bpy.data.lights.new('Sol', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 4.2; sun.data.angle = math.radians(0.8); sun.data.color = (1.0, 0.96, 0.90)
sun.rotation_euler = (-sd).to_track_quat('-Z', 'Y').to_euler()
if STYLE == 'conceitual':          # luz macia, céu em degradê claro
    sun.data.energy = 3.6; sun.data.angle = math.radians(3.0); sun.data.color = (1.0, 0.98, 0.95)
    for nd in list(wn.nodes):
        if nd.type != 'BACKGROUND' and nd.type != 'OUTPUT_WORLD':
            wn.nodes.remove(nd)
    gtc = wn.nodes.new('ShaderNodeTexCoord'); gs = wn.nodes.new('ShaderNodeSeparateXYZ')
    wn.links.new(gtc.outputs['Generated'], gs.inputs[0])
    gr = wn.nodes.new('ShaderNodeValToRGB'); wn.links.new(gs.outputs[2], gr.inputs[0])
    gr.color_ramp.elements[0].position = 0.0; gr.color_ramp.elements[0].color = (0.95, 0.95, 0.94, 1)
    gr.color_ramp.elements[1].position = 0.45; gr.color_ramp.elements[1].color = (0.36, 0.56, 0.86, 1)
    lp = wn.nodes.new('ShaderNodeLightPath')          # céu azul só para a câmera; luz ambiente neutra
    mxw = wn.nodes.new('ShaderNodeMix'); mxw.data_type = 'RGBA'
    mxw.inputs[6].default_value = (0.80, 0.82, 0.85, 1)
    wn.links.new(lp.outputs['Is Camera Ray'], mxw.inputs[0]); wn.links.new(gr.outputs[0], mxw.inputs[7])
    wn.links.new(mxw.outputs[2], bg.inputs[0]); bg.inputs[1].default_value = 0.6

# ------------------------------------------------------------------ câmera
AX0 = np.array([340820.9, 6994591.3]) - O[:2]; AXV = np.array([-0.7156, 0.6985])   # eixo Rua B (SE->NW)
NRM = np.array([AXV[1], -AXV[0]])                                                     # lado NE
VIEWS = {
    # nome: (estaca no eixo [m], afastamento lateral [m], altura sobre a via [m], alvo xy local, alvo z, lente)
    'ruab':     (-68, 2.0, 13.0, (-4.0, 24.0), 725.5, 28),
    'ruab_lat': (-10, 9.0, 12.0, (-2.0, 12.0), 727.0, 28),
    'ruab_ped': (-44, 3.0, 1.65, (6.0, 18.0), 728.0, 26),
    # pedestre (1,65 m) na calçada SO da Rua B (lado do plato), olhando rua acima; alvo z None = visada horizontal
    'calcada':  (-58, -6.5, 1.80, ('giro', 17.0), None, 24),
    'topo':     (0, 0, 0, (0, 0), 0, 0),
    'ruab_nw':  (38, 2.0, 7.5, (8.0, 12.0), 727.0, 30),
}
st, off, hgt, tgt, tz, lens = VIEWS[VIEW]
cp = AX0 + AXV * st + NRM * off
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam)
cam.location = (cp[0], cp[1], zat(*cp) + hgt)
if tgt[0] == 'giro':          # visada = eixo da rua girado para o lado do plato (graus)
    a = math.radians(tgt[1]); dd = AXV * math.cos(a) - NRM * math.sin(a)
    tgt = (cp[0] + dd[0] * 50, cp[1] + dd[1] * 50)
d = Vector((tgt[0], tgt[1], (cam.location.z if tz is None else tz - O[2]))) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = lens; cam.data.clip_end = 6000; cam.data.sensor_width = 36
sc.camera = cam
if VIEW == 'topo':
    cam.location = (5, 15, 400); cam.rotation_euler = (0, 0, 0)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 160
print('camera', tuple(round(c, 2) for c in cam.location), 'utm', cp + O[:2])

# ------------------------------------------------------------------ render
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
sc.cycles.max_bounces = 6; sc.cycles.use_adaptive_sampling = True
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.render.film_transparent = False
for vt, lk in ((('Standard', 'None'),) if STYLE == 'conceitual' else ()) + (('AgX', 'AgX - Punchy'), ('Filmic', 'Medium High Contrast')):
    try:
        sc.view_settings.view_transform = vt; sc.view_settings.look = lk; break
    except Exception:
        continue
sc.view_settings.exposure = 0.0
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
