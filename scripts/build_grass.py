"""Grama 'Sempre Verde' em fios (partículas de cabelo) na área de gramado
vista por cada câmera ao nível do observador.  Um objeto por câmera
(grama_<camera>); render.py liga só o da câmera renderizada."""
import bpy, math
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import lib_common as C
import lib_materials as M
from build_ground import shp, to_polys
from build_env import CAMS


def grass_material():
    mat = bpy.data.materials.new('grama_fios')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    hi = nt.nodes.new('ShaderNodeHairInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.012, 0.035, 0.006, 1)
    ramp.color_ramp.elements[1].color = (0.10, 0.23, 0.035, 1)
    nt.links.new(hi.outputs['Intercept'], ramp.inputs[0])
    hue = nt.nodes.new('ShaderNodeHueSaturation')
    nt.links.new(ramp.outputs[0], hue.inputs['Color'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    nt.links.new(hi.outputs['Random'], mr.inputs[0])
    mr.inputs[3].default_value = 0.47
    mr.inputs[4].default_value = 0.55
    nt.links.new(mr.outputs[0], hue.inputs['Hue'])
    mv = nt.nodes.new('ShaderNodeMapRange')
    nt.links.new(hi.outputs['Random'], mv.inputs[0])
    mv.inputs[3].default_value = 0.75
    mv.inputs[4].default_value = 1.2
    nt.links.new(mv.outputs[0], hue.inputs['Value'])
    nt.links.new(hue.outputs[0], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.45
    bsdf.inputs['Subsurface Weight'].default_value = 0.0
    return mat


def build(S, radius=19.0, density=95, children=12):
    col = C.coll('GramaFios')
    hard = []
    for k in ('paver', 'ciclovia', 'ciclovia_centro', 'ciclovia_travessia', 'fp_claro', 'fp_escuro', 'palco',
              'faixa_elevada', 'quadra_areia', 'kids_areia', 'totem', 'canteiro_totem', 'arquibancadas_hatch'):
        hard.append(shp(S[k]))
    for p in S['canteiros_curvos']:
        hard.append(Polygon(p).buffer(0))
    for (x, y, w) in S['bancos_quadrados']:
        hard.append(Polygon(C.rect(x, y, w, w)))
    cant = unary_union([shp(c) for c in S['canteiro']])
    grass = cant.buffer(-0.08).difference(unary_union(hard).buffer(0.04))
    mat = grass_material()
    sc = bpy.context.scene
    sc.cycles_curves.shape = 'RIBBONS'
    sc.cycles_curves.subdivisions = 2
    for name, (p, t, lens) in CAMS.items():
        if p[2] > 5:
            continue
        f = (t[0] - p[0], t[1] - p[1])
        n = math.hypot(*f)
        f = (f[0] / n, f[1] / n)
        c = Point(p[0] + f[0] * (radius - 3), p[1] + f[1] * (radius - 3)).buffer(radius)
        area = grass.intersection(c)
        if area.is_empty or area.area < 1:
            continue
        ob = C.poly_mesh('grama_' + name, to_polys(area), col, mat, z=-0.009, step=1.0)
        ob.data.materials.append(mat)
        mod = ob.modifiers.new('fios', 'PARTICLE_SYSTEM')
        part = ob.particle_systems[0].settings
        part.name = 'fios_' + name
        part.type = 'HAIR'
        part.count = int(area.area * density)
        part.hair_length = 0.075
        part.emit_from = 'FACE'
        part.use_emit_random = True
        part.use_even_distribution = True
        part.normal_factor = 0.045
        part.factor_random = 0.022
        part.hair_step = 3
        part.render_step = 3
        part.display_step = 1
        part.child_type = 'INTERPOLATED'
        part.child_percent = 0
        part.rendered_child_count = children
        part.child_length = 1.0
        part.child_length_threshold = 0.4
        part.roughness_1 = 0.015
        part.roughness_1_size = 1.0
        part.roughness_2 = 0.035
        part.roughness_endpoint = 0.012
        part.root_radius = 1.0
        part.tip_radius = 0.05
        part.radius_scale = 0.0018
        part.use_close_tip = True
        part.material = 1
        part.display_percentage = 1
        ob.show_instancer_for_render = False
        ob.hide_render = True
        print('grama', name, round(area.area), 'm2', part.count)
