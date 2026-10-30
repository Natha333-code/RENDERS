"""Gera, a partir da cena do Blender, os recursos da maquete interativa (web/dados):
 - chao_nucleo.jpg / chao_entorno.jpg / chao_horizonte.jpg: vistas ortogonais de cima do terreno
   (sem árvores, casas e vias do condomínio), sob céu uniforme -> cor do chão para o three.js;
 - arvores.png: atlas com os 6 tipos de árvore renderizados de lado (fundo transparente);
 - arvores.bin: pontos das árvores (x, y, z, escala, rotação, tipo);
 - ceu.jpg: panorama do céu (HDRI) já com a rotação usada nos renders;
 - bake.json: extensões das texturas e dimensões dos sprites.
Uso: blender -b terreno.blend --python bake_web.py -- dados_dir saida_dir"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
D, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
J = json.load(open(f'{D}/cena_terreno.json'))
sc = bpy.context.scene
meta = {}

# ---------------------------------------------------------------- pontos das árvores
ob = bpy.data.objects['mata_entorno']; me = ob.data
n = len(me.vertices)
co = np.zeros(n * 3, np.float32); me.vertices.foreach_get('co', co)
att = {}
for nm, dt in (('kind', np.int32), ('escala', np.float32), ('rotz', np.float32)):
    a = np.zeros(n, dt); me.attributes[nm].data.foreach_get('value', a); att[nm] = a
co = co.reshape(-1, 3)
rec = np.zeros(n, dtype=[('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('s', '<f4'), ('r', '<f4'), ('k', '<f4')])
rec['x'], rec['y'], rec['z'] = co[:, 0], co[:, 1], co[:, 2]
rec['s'], rec['r'], rec['k'] = att['escala'], att['rotz'], att['kind']
rec.tofile(f'{OUT}/arvores.bin')
meta['arvores'] = int(n)

# ---------------------------------------------------------------- céu
env = [nd for nd in sc.world.node_tree.nodes if nd.type == 'TEX_ENVIRONMENT'][0]
mp = [nd for nd in sc.world.node_tree.nodes if nd.type == 'MAPPING'][0]
meta['ceu_rot'] = float(mp.inputs['Rotation'].default_value[2])
meta['ceu_forca'] = float(sc.world.node_tree.nodes['Background'].inputs[1].default_value)
sol = bpy.data.objects['sol']
meta['sol_dir'] = list((sol.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized())
img = env.image.copy(); img.scale(2048, 1024)
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Base Contrast'
sc.view_settings.exposure = 0.0
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
img.save_render(f'{OUT}/ceu.jpg', scene=sc)

# ---------------------------------------------------------------- vistas ortogonais do chão
keep_world = sc.world
wflat = bpy.data.worlds.new('plano'); wflat.use_nodes = True
wflat.node_tree.nodes['Background'].inputs[0].default_value = (1, 1, 1, 1)
wflat.node_tree.nodes['Background'].inputs[1].default_value = 1.0
sc.world = wflat
esconder = ['mata_entorno', 'grama_patch', 'casas_vizinhanca', 'predios_osm', 'perimetro', 'sol',
            'pista', 'passeio', 'meio_fio', 'canteiro', 'espelho_passeio', 'espelho_meiofio',
            'espelho_canteiro', 'borda_pista']
for nm in esconder:
    if nm in bpy.data.objects: bpy.data.objects[nm].hide_render = True
sc.render.use_compositing = False
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.cycles.samples = 12; sc.cycles.use_denoising = True
sc.render.film_transparent = False
cam = bpy.data.cameras.new('orto'); cam.type = 'ORTHO'; cam.clip_end = 1e6
co_ = bpy.data.objects.new('orto', cam); sc.collection.objects.link(co_)
sc.camera = co_


def orto(nome, cx, cy, tam, px):
    cam.ortho_scale = tam
    co_.location = (cx, cy, 5000); co_.rotation_euler = (0, 0, 0)
    sc.render.resolution_x = sc.render.resolution_y = px; sc.render.resolution_percentage = 100
    sc.render.filepath = f'{OUT}/{nome}.jpg'
    bpy.ops.render.render(write_still=True)
    meta[nome] = [cx - tam / 2, cy - tam / 2, tam]
    print('BAKE_OK', nome, flush=True)


X1, Y1 = J['x0_1m'], J['y0_1m']
orto('chao_nucleo', X1 + 480, Y1 + 480, 960, 4096)
orto('chao_entorno', 0, 0, 5000, 2048)
orto('chao_horizonte', 0, 0, 30000, 1024)

# ---------------------------------------------------------------- sprites das árvores
ss = bpy.data.scenes.new('sprites')
ss.render.engine = 'CYCLES'; ss.cycles.samples = 48; ss.cycles.use_denoising = True
ss.render.film_transparent = True; ss.world = keep_world
ss.view_settings.view_transform = 'AgX'; ss.view_settings.look = 'AgX - Medium High Contrast'
ss.render.image_settings.file_format = 'PNG'; ss.render.image_settings.color_mode = 'RGBA'
ss.render.resolution_x = ss.render.resolution_y = 512
lt = bpy.data.lights.new('sol_sp', 'SUN'); lt.energy = 3.2; lt.angle = math.radians(1.0)
lo = bpy.data.objects.new('sol_sp', lt); ss.collection.objects.link(lo)
lo.rotation_euler = (math.radians(42), 0, math.radians(-35))
cs = bpy.data.cameras.new('cam_sp'); cs.type = 'ORTHO'; cs.clip_end = 1e4
cso = bpy.data.objects.new('cam_sp', cs); ss.collection.objects.link(cso); ss.camera = cso
kinds = sorted([c for c in bpy.data.collections if c.name[:1] == 'k' and '_' in c.name], key=lambda c: c.name)
sprites = []
tiles = []
for i, c in enumerate(kinds):
    o = c.objects[0]
    ss.collection.objects.link(o)
    bb = np.array([o.matrix_world @ Vector(v) for v in o.bound_box])
    mn, mx = bb.min(0), bb.max(0)
    w = max(mx[0] - mn[0], mx[1] - mn[1]); h = mx[2] - mn[2]
    tam = max(w, h) * 1.02
    cxx, cyy, czz = (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2
    cs.ortho_scale = tam
    cso.location = (cxx, cyy - 500, czz); cso.rotation_euler = (math.radians(90), 0, 0)
    ss.render.filepath = f'{OUT}/_sp{i}.png'
    bpy.ops.render.render(write_still=True, scene=ss.name)
    ss.collection.objects.unlink(o)
    loc = o.matrix_world.translation
    # tamanho do quadro (m, escala 1) e altura do centro do quadro sobre a base do modelo
    sprites.append(dict(nome=c.name, tam=tam, zc=czz - loc[2], xc=cxx - loc[0], yc=cyy - loc[1]))
    tiles.append(f'{OUT}/_sp{i}.png')
    print('SPRITE_OK', c.name, round(w, 2), round(h, 2), flush=True)
meta['sprites'] = sprites
json.dump(meta, open(f'{OUT}/bake.json', 'w'), indent=1)
