"""blender -b cena.blend --python render.py -- pasta_saida cam1,cam2 [largura] [amostras]"""
import bpy, sys, os
argv = sys.argv[sys.argv.index('--') + 1:]
out, cams = argv[0], argv[1].split(',')
width = int(argv[2]) if len(argv) > 2 else 1920
spp = int(argv[3]) if len(argv) > 3 else 128
sc = bpy.context.scene
sc.render.resolution_x = width
sc.render.resolution_y = int(width * 9 / 16)
sc.cycles.samples = spp
sc.render.threads_mode = 'AUTO'
os.makedirs(out, exist_ok=True)
for c in cams:
    sc.camera = bpy.data.objects[c]
    for o in bpy.data.objects:
        if o.name.startswith('grama_'):
            o.hide_render = (o.name != 'grama_' + c)
    sc.render.filepath = os.path.join(out, c + '.png')
    bpy.ops.render.render(write_still=True)
    print('RENDER_OK', c, flush=True)
