"""Casas dos bairros vizinhos (contexto): volumes simples com telhado de duas águas,
posição e cor do telhado tiradas da imagem aérea (prep_cobertura.py)."""
import bpy, bmesh
import numpy as np


def casa_mesh(m_parede, m_telhado):
    """caixa 1x1x1 (paredes) + telhado de duas águas com beiral; escalada por instância."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.z += 0.5
    for f in bm.faces:
        f.material_index = 0
    b = 0.06  # beiral
    ridge = 1.38
    vs = [bm.verts.new(p) for p in ((-0.5 - b, -0.5 - b, 0.97), (0.5 + b, -0.5 - b, 0.97), (0.5 + b, 0, ridge),
                                     (-0.5 - b, 0, ridge), (-0.5 - b, 0.5 + b, 0.97), (0.5 + b, 0.5 + b, 0.97))]
    for q in ((vs[0], vs[1], vs[2], vs[3]), (vs[3], vs[2], vs[5], vs[4])):
        f = bm.faces.new(q); f.material_index = 1
    for q in ((vs[0], vs[3], vs[4]), (vs[1], vs[5], vs[2])):   # oitões
        f = bm.faces.new(q); f.material_index = 0
    me = bpy.data.meshes.new('casa')
    bm.to_mesh(me); bm.free()
    me.materials.append(m_parede); me.materials.append(m_telhado)
    return me


def materiais():
    mp = bpy.data.materials.new('casa_parede'); mp.use_nodes = True
    nt = mp.node_tree; b = nt.nodes['Principled BSDF']
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    r = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(oi.outputs['Random'], r.inputs[0])
    r.color_ramp.elements[0].color = (0.62, 0.58, 0.50, 1); r.color_ramp.elements[1].color = (0.85, 0.83, 0.78, 1)
    nt.links.new(r.outputs[0], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.85
    mt = bpy.data.materials.new('casa_telhado'); mt.use_nodes = True
    nt = mt.node_tree; b = nt.nodes['Principled BSDF']
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = 'cor'
    nt.links.new(at.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.6
    return mp, mt


def build(casas, height, coll_fn):
    if not casas:
        return
    C = np.array(casas, float)
    n = len(C)
    col = coll_fn('Contexto')
    mp, mt = materiais()
    me_c = casa_mesh(mp, mt)
    proto = bpy.data.objects.new('casa_modelo', me_c)
    coll_fn('_casa', coll_fn('_assets')).objects.link(proto)
    z = height(C[:, 0], C[:, 1]) - 0.3
    me = bpy.data.meshes.new('pts_casas')
    me.vertices.add(n); me.vertices.foreach_set('co', np.c_[C[:, :2], z].ravel().astype(np.float32))
    a = me.attributes.new('dim', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', np.c_[C[:, 2], C[:, 3], C[:, 4] + 0.3].ravel().astype(np.float32))
    a = me.attributes.new('rotz', 'FLOAT', 'POINT'); a.data.foreach_set('value', C[:, 5].astype(np.float32))
    a = me.attributes.new('cor', 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set('color', np.c_[C[:, 6:9], np.ones(n)].ravel().astype(np.float32))
    ob = bpy.data.objects.new('casas_vizinhanca', me); col.objects.link(ob)
    ng = bpy.data.node_groups.new('instanciar_casas', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links.new
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = proto
    iop = N.new('GeometryNodeInstanceOnPoints')

    def attr(nm, dt):
        x = N.new('GeometryNodeInputNamedAttribute'); x.data_type = dt; x.inputs['Name'].default_value = nm
        return x.outputs['Attribute']
    L(gi.outputs[0], iop.inputs['Points']); L(oi.outputs['Geometry'], iop.inputs['Instance'])
    L(attr('dim', 'FLOAT_VECTOR'), iop.inputs['Scale'])
    cx = N.new('ShaderNodeCombineXYZ'); L(attr('rotz', 'FLOAT'), cx.inputs[2])
    e2r = N.new('FunctionNodeEulerToRotation'); L(cx.outputs[0], e2r.inputs[0]); L(e2r.outputs[0], iop.inputs['Rotation'])
    L(iop.outputs[0], go.inputs[0])
    ob.modifiers.new('casas', 'NODES').node_group = ng
