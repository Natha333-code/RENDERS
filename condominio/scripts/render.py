"""blender -b terreno.blend --python render.py -- pasta_saida cam1,cam2 [largura] [amostras]"""
import bpy, sys, os
argv = sys.argv[sys.argv.index('--') + 1:]
out, cams = argv[0], argv[1].split(',')
width = int(argv[2]) if len(argv) > 2 else 1920
spp = int(argv[3]) if len(argv) > 3 else 128
sc = bpy.context.scene
sc.cycles.samples = spp
os.makedirs(out, exist_ok=True)
for c in cams:
    ob = bpy.data.objects[c]
    sc.camera = ob
    if 'res' in ob:          # resolução própria (ex.: planta em retrato)
        rx, ry = ob['res']
        k = width / 1920
        sc.render.resolution_x, sc.render.resolution_y = int(rx * k), int(ry * k)
    else:
        sc.render.resolution_x, sc.render.resolution_y = width, int(width * 9 / 16)
    # perímetro só nas vistas aéreas (ao nível do olho vira um "tubo")
    per = bpy.data.objects.get('perimetro')
    if per:
        per.hide_render = bool(ob.get('solo', False))
    sc.render.filepath = os.path.join(out, c + '.png')
    bpy.ops.render.render(write_still=True)
    print('RENDER_OK', c, flush=True)
