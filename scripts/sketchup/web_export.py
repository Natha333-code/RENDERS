"""Gera o modelo web (glTF + Draco) a partir da mesma versão otimizada usada
no SketchUp (sk_export.py): componentes reaproveitados, texturas em escala.
blender -b praca.blend --python web_export.py -- tmp.dae texturas pasta_texturas saida.gltf"""
import bpy, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sk_export as E   # executa a montagem (comps, GROUPS, M)

OUT = sys.argv[sys.argv.index('--') + 1:][3]
TEXABS = E.TEXABS


def srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# cena limpa para exportação
sc = bpy.data.scenes.new('web')
bpy.context.window.scene = sc if bpy.context.window else None
mats = {}


def material(name):
    if name in mats:
        return mats[name]
    d = E.M.m[name]
    mt = bpy.data.materials.new('W_' + d.get('nice', name))
    mt.use_nodes = True
    nt = mt.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.85
    b.inputs['Specular IOR Level'].default_value = 0.3
    if 'img' in d:
        fn = E.M.images[d['img']]
        im = nt.nodes.new('ShaderNodeTexImage')
        im.image = bpy.data.images.load(os.path.join(TEXABS, fn), check_existing=True)
        nt.links.new(im.outputs[0], b.inputs['Base Color'])
        if fn.endswith('.png'):
            nt.links.new(im.outputs[1], b.inputs['Alpha'])
            mt.blend_method = 'CLIP'
            mt.alpha_threshold = 0.45
    else:
        r, g, bb = d['color']
        b.inputs['Base Color'].default_value = (srgb2lin(r), srgb2lin(g), srgb2lin(bb), 1)
    mt.use_backface_culling = False
    mats[name] = mt
    return mt


def mesh_from_geo(g, name):
    me = bpy.data.meshes.new(name)
    faces, uvs, mids = [], [], []
    order = list(g.tris.keys())
    for mi, m in enumerate(order):
        for (a, ua, b, ub, c, uc) in g.tris[m]:
            faces.append((a, b, c))
            uvs.extend([g.UVs[ua], g.UVs[ub], g.UVs[uc]])
            mids.append(mi)
    me.from_pydata(g.P, [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', [c for uv in uvs for c in uv])
    me.polygons.foreach_set('material_index', mids)
    for m in order:
        me.materials.append(material(m))
    me.validate(clean_customdata=False)
    return me


root = bpy.data.objects.new('Praca Linear', None)
sc.collection.objects.link(root)
comp_mesh = {c: mesh_from_geo(g, nice) for c, (g, nice) in E.comps.items()}
NG = {'Pisos': 'Pisos e pavimentos', 'Mobiliario': 'Mobiliario e equipamentos', 'Vegetacao': 'Paisagismo',
      'Mata': 'Vegetacao existente'}
for grp, items in E.GROUPS.items():
    gob = bpy.data.objects.new(NG.get(grp, grp), None)
    sc.collection.objects.link(gob)
    gob.parent = root
    for it in items:
        if it[0] == 'geo':
            ob = bpy.data.objects.new(it[1], mesh_from_geo(it[2], it[1]))
        else:
            _, oname, cname, mw = it
            ob = bpy.data.objects.new(E.comps[cname][1], comp_mesh[cname])
            ob.matrix_world = mw
        sc.collection.objects.link(ob)
        mwc = ob.matrix_world.copy()
        ob.parent = gob
        ob.matrix_world = mwc

bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLTF_SEPARATE', export_texture_dir='tex',
                          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
                          export_draco_position_quantization=15, export_draco_texcoord_quantization=12,
                          export_draco_normal_quantization=8, export_image_format='AUTO', export_yup=True,
                          export_apply=True, export_cameras=False, export_lights=False, use_active_scene=True)
print('WEB_OK', OUT)
