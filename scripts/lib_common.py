"""Funções comuns para montar a cena da Praça Linear no Blender."""
import bpy, bmesh, math, json, os, random
from mathutils import Vector, Matrix

ASSETS = os.environ.get('PRACA_ASSETS', '/home/user/assets')
TEX = ASSETS + '/tex'

S = None  # dados da cena (scene.json)


def load_scene(path):
    global S
    S = json.load(open(path))
    return S


# ------------------------------------------------------------------ perfil
def zc(x):
    """Cota do piso acabado do canteiro (m, relativa a 621,00) na abscissa x."""
    P = S['perfil']
    if x <= P[0][0]:
        return P[0][1] - 621.0
    for (x0, z0), (x1, z1) in zip(P, P[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            # suaviza as quebras de greide (curva vertical)
            return z0 + (z1 - z0) * t - 621.0
    return P[-1][1] - 621.0


def zc_smooth(x, r=6.0):
    n = 7
    return sum(zc(x + r * (i / (n - 1) - 0.5)) for i in range(n)) / n


RUA = -0.15  # rua 15 cm abaixo do canteiro / calçadas


# ------------------------------------------------------------------ coleções
def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(obj, c):
    c.objects.link(obj)
    return obj


# ------------------------------------------------------------------ malhas
def poly_mesh(name, polys, col, mat=None, z=0.0, zfun=None, thick=0.0, step=1.0,
              rim_mat=None, solid_offset=-1.0):
    """polys: lista de {'ext':[(x,y)...], 'holes':[[...]]}.
    Cria malha preenchida (regra par-ímpar), subdivide em faixas de `step` m no
    eixo x e aplica a cota: z_final = zfun(x,y) (ou zc_smooth(x)) + z."""
    if not polys:
        return None
    cu = bpy.data.curves.new(name + '_cu', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    for pg in polys:
        for loop in [pg['ext']] + pg['holes']:
            if len(loop) < 3:
                continue
            sp = cu.splines.new('POLY')
            sp.points.add(len(loop) - 1)
            for i, (x, y) in enumerate(loop):
                sp.points[i].co = (x, y, 0, 1)
            sp.use_cyclic_u = True
    tmp = bpy.data.objects.new(name + '_tmp', cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    if step:
        xs = [v.co.x for v in bm.verts]
        x0, x1 = math.floor(min(xs)), math.ceil(max(xs))
        x = x0 + step
        while x < x1:
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(x, 0, 0), plane_no=(1, 0, 0))
            x += step
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bad = [f for f in bm.faces if f.calc_area() < 1e-7]
    if bad:
        bmesh.ops.delete(bm, geom=bad, context='FACES')
    for v in bm.verts:
        v.co.z = (zfun(v.co.x, v.co.y) if zfun else zc_smooth(v.co.x)) + z
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob, col)
    if mat:
        me.materials.append(mat)
    if thick:
        if rim_mat:
            me.materials.append(rim_mat)
        m = ob.modifiers.new('solid', 'SOLIDIFY')
        m.thickness = thick
        m.offset = solid_offset
        m.use_even_offset = True
        if rim_mat:
            m.material_offset_rim = 1
    for p in me.polygons:
        p.use_smooth = False
    return ob


def rect(cx, cy, w, h, ang=0.0):
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return pts


def box(name, col, size, loc, rot=0.0, mat=None, bevel=0.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2] + size[2] / 2))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot)
    link(ob, col)
    if mat:
        me.materials.append(mat)
    if bevel:
        m = ob.modifiers.new('bev', 'BEVEL')
        m.width = bevel
        m.segments = 2
        m.limit_method = 'ANGLE'
    return ob


def cyl(name, col, r, h, loc, mat=None, verts=24, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h / 2))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    link(ob, col)
    if mat:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def tube_path(name, col, pts, r, mat=None, res=8, cyclic=False):
    """Tubo ao longo de uma polilinha 3D (estruturas metálicas)."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    link(ob, col)
    if mat:
        cu.materials.append(mat)
    return ob


def join(objs, name):
    objs = [o for o in objs if o]
    if not objs:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # converte curvas / aplica modificadores
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def as_asset(ob_list, name):
    """Junta objetos numa coleção fora da cena para ser instanciada."""
    lib = coll('_assets')
    c = bpy.data.collections.new(name)
    lib.children.link(c)
    for o in ob_list:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
    return c


def instance(c, col, loc, rot=0.0, scale=1.0, name=None):
    ob = bpy.data.objects.new(name or c.name + '_i', None)
    ob.instance_type = 'COLLECTION'
    ob.instance_collection = c
    ob.location = loc
    ob.rotation_euler = (0, 0, rot)
    ob.scale = (scale, scale, scale) if not isinstance(scale, tuple) else scale
    link(ob, col)
    return ob
