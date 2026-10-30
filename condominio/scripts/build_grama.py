"""Grama 3D (touceiras instanciadas) junto às câmeras ao nível do observador.
Longe das câmeras o campo é só textura (material campo_nativo)."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector

rnd = random.Random(21)


def grass_material():
    mat = bpy.data.materials.new('capim')
    mat.use_nodes = True
    nt = mat.node_tree; N = nt.nodes; L = nt.links.new
    b = N['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.6
    b.inputs['Subsurface Weight'].default_value = 0.0
    b.inputs['Transmission Weight'].default_value = 0.0
    oi = N.new('ShaderNodeObjectInfo')
    at = N.new('ShaderNodeAttribute'); at.attribute_name = 'h'      # altura relativa na lâmina
    r = N.new('ShaderNodeValToRGB'); L(oi.outputs['Random'], r.inputs[0])
    el = r.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0.06, 0.12, 0.025, 1)
    el[1].position = 0.75; el[1].color = (0.16, 0.20, 0.05, 1)
    e3 = el.new(0.92); e3.color = (0.36, 0.30, 0.12, 1)              # algumas touceiras secas
    e4 = el.new(1.0); e4.color = (0.40, 0.34, 0.16, 1)
    base = N.new('ShaderNodeMix'); base.data_type = 'RGBA'
    L(at.outputs['Fac'], base.inputs[0])
    base.inputs[6].default_value = (0.03, 0.05, 0.012, 1)
    L(r.outputs[0], base.inputs[7])
    L(base.outputs[2], b.inputs['Base Color'])
    # translucidez da folha
    tr = N.new('ShaderNodeBsdfTranslucent'); L(r.outputs[0], tr.inputs[0])
    mx = N.new('ShaderNodeMixShader'); mx.inputs[0].default_value = 0.25
    out = N['Material Output']
    L(b.outputs[0], mx.inputs[1]); L(tr.outputs[0], mx.inputs[2]); L(mx.outputs[0], out.inputs[0])
    return mat


def clump(name, n_blades, hmin, hmax, spread, mat, col):
    bm = bmesh.new()
    hl = bm.loops.layers.uv.new('UVMap')
    hv = []
    for i in range(n_blades):
        a = rnd.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a), math.sin(a), 0))
        root = d * rnd.uniform(0, spread)
        H = rnd.uniform(hmin, hmax)
        lean = rnd.uniform(0.15, 0.55) * H
        wid = rnd.uniform(0.004, 0.009)
        side = Vector((-d.y, d.x, 0))
        seg = 4
        prev = None
        for k in range(seg + 1):
            t = k / seg
            p = root + d * (lean * t * t) + Vector((0, 0, H * (t - 0.18 * t * t)))
            w = wid * (1 - t) + 0.0005
            v1 = bm.verts.new(p - side * w); v2 = bm.verts.new(p + side * w)
            hv += [(v1, t), (v2, t)]
            if prev:
                bm.faces.new((prev[0], prev[1], v2, v1))
            prev = (v1, v2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    att = me.attributes.new('h', 'FLOAT', 'POINT')
    att.data.foreach_set('value', [t for _, t in hv])
    me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    return ob


def build(height_fn, H1, X1, Y1, R1, cams, coll_fn, grid_mesh, radius=85.0, dens_max=55.0):
    """cams: lista de (x, y, dir_x, dir_y) das câmeras ao nível do chão."""
    lib = coll_fn('_assets')
    gcol = coll_fn('_grama', lib)
    mat = grass_material()
    for i in range(6):
        clump(f'touceira_{i}', rnd.randint(14, 26), 0.10 + 0.04 * i, 0.30 + 0.08 * i, 0.07, mat, gcol)
    for i in range(2):  # macegas (capim alto)
        clump(f'macega_{i}', 40, 0.45, 0.95, 0.15, mat, gcol)

    def keep(cx, cy):
        k = np.zeros(cx.shape, bool)
        for x, y, dx, dy in cams:
            vx, vy = cx - x, cy - y
            dist = np.hypot(vx, vy)
            front = (vx * dx + vy * dy) > -6
            k |= (dist < radius) & front
        return k
    me_ob = grid_mesh('grama_patch', H1, X1, Y1, R1, coll_fn('Grama'), bpy.data.materials['campo_nativo'],
                      keep=keep, dz=0.0)
    me = me_ob.data
    # remove vértices soltos
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free()
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    dmin = np.full(len(co), 1e9)
    for x, y, dx, dy in cams:
        dmin = np.minimum(dmin, np.hypot(co[:, 0] - x, co[:, 1] - y))
    dens = np.clip(1 - dmin / radius, 0, 1) ** 1.6
    a = me.attributes.new('dens', 'FLOAT', 'POINT'); a.data.foreach_set('value', dens.astype(np.float32))
    me_ob.hide_render = False
    # geometry nodes: distribui touceiras com densidade decrescente
    ng = bpy.data.node_groups.new('grama_gn', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    Nn = ng.nodes; L = ng.links.new
    gi = Nn.new('NodeGroupInput'); go = Nn.new('NodeGroupOutput')
    dp = Nn.new('GeometryNodeDistributePointsOnFaces'); dp.distribute_method = 'RANDOM'
    na = Nn.new('GeometryNodeInputNamedAttribute'); na.data_type = 'FLOAT'; na.inputs['Name'].default_value = 'dens'
    mu = Nn.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = dens_max
    L(na.outputs['Attribute'], mu.inputs[0])
    L(gi.outputs[0], dp.inputs['Mesh']); L(mu.outputs[0], dp.inputs['Density'])
    ci = Nn.new('GeometryNodeCollectionInfo'); ci.inputs['Collection'].default_value = gcol
    ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    iop = Nn.new('GeometryNodeInstanceOnPoints'); iop.inputs['Pick Instance'].default_value = True
    rv = Nn.new('FunctionNodeRandomValue'); rv.data_type = 'INT'
    rv.inputs['Min'].default_value = 0; rv.inputs['Max'].default_value = 7
    rr = Nn.new('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'
    rr.inputs['Min'].default_value = (-0.15, -0.15, 0); rr.inputs['Max'].default_value = (0.15, 0.15, 6.28)
    rs = Nn.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
    rs.inputs['Min'].default_value = 0.7; rs.inputs['Max'].default_value = 1.4
    e2r = Nn.new('FunctionNodeEulerToRotation'); L(rr.outputs['Value'], e2r.inputs[0])
    L(dp.outputs['Points'], iop.inputs['Points']); L(ci.outputs[0], iop.inputs['Instance'])
    L(rv.outputs[2], iop.inputs['Instance Index']); L(e2r.outputs[0], iop.inputs['Rotation'])
    L(rs.outputs[1], iop.inputs['Scale'])
    jg = Nn.new('GeometryNodeJoinGeometry')
    L(iop.outputs[0], jg.inputs[0]); L(gi.outputs[0], jg.inputs[0])
    L(jg.outputs[0], go.inputs[0])
    md = me_ob.modifiers.new('grama', 'NODES'); md.node_group = ng
    # a malha base do patch fica 2 cm acima do terreno (cobre a textura sob a grama)
    me_ob.location.z = 0.02
    return me_ob
