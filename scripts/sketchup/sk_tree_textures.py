"""Renderiza cada espécie de árvore isolada (vista lateral ortográfica, fundo
transparente, luz difusa) para gerar texturas de folhagem com a floração.
blender -b praca.blend --python sk_tree_textures.py -- pasta_saida"""
import bpy, sys, os, math
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out, exist_ok=True)
SPECIES = {'quaresmeira': 'T_quaresmeira', 'extremosa': 'T_extremosa', 'manaca': 'T_manaca',
           'jabuticabeira': 'T_jabuticabeira', 'ipe': 'T_ipe', 'mata1': 'T_mata1', 'mata2': 'T_mata2'}

sc = bpy.data.scenes.new('texturas')
bpy.context.window.scene = sc if bpy.context.window else None
w = bpy.data.worlds.new('w_tex')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.9, 0.92, 0.95, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 1.1
sc.world = w
sun = bpy.data.objects.new('s', bpy.data.lights.new('s', 'SUN'))
sun.data.energy = 2.0
sun.rotation_euler = (math.radians(50), 0, math.radians(20))
sc.collection.objects.link(sun)
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c'))
cam.data.type = 'ORTHO'
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = 2048
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'

for sp, cname in SPECIES.items():
    col = bpy.data.collections[cname]
    inst = bpy.data.objects.new('i_' + sp, None)
    inst.instance_type = 'COLLECTION'
    inst.instance_collection = col
    sc.collection.objects.link(inst)
    # bbox da árvore
    mn = Vector((1e9,) * 3); mx = -mn
    for o in col.all_objects:
        if o.type == 'MESH':
            for v in o.bound_box:
                p = o.matrix_world @ Vector(v)
                mn = Vector(map(min, mn, p)); mx = Vector(map(max, mx, p))
    ctr = (mn + mx) / 2
    size = max(mx.x - mn.x, mx.z - mn.z, mx.y - mn.y) * 1.02
    for view, ang in (('a', 0.0), ('b', math.pi / 2)):
        d = Vector((math.cos(ang), math.sin(ang), 0))
        cam.location = ctr - d * (size * 3)
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = size
        cam.data.clip_end = size * 10
        sc.render.filepath = os.path.join(out, f'{sp}_{view}.png')
        bpy.ops.render.render(write_still=True, scene=sc.name)
    with open(os.path.join(out, f'{sp}_bbox.txt'), 'w') as f:
        f.write(f'{mn.x} {mn.y} {mn.z} {mx.x} {mx.y} {mx.z} {size}\n')
    sc.collection.objects.unlink(inst)
    print('TEX_OK', sp, flush=True)
