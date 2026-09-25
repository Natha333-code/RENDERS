"""Monta a cena completa da Praça Linear - Reserva das Araucárias.
blender -b --python build_scene.py -- scene.json saida.blend [--sem-veg]"""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_common as C
import lib_materials as M

argv = sys.argv[sys.argv.index('--') + 1:]
SCENE_JSON, OUT = argv[0], argv[1]
FLAGS = set(argv[2:])

bpy.ops.wm.read_factory_settings(use_empty=True)
S = C.load_scene(SCENE_JSON)

import build_ground
build_ground.build(S)
if '--sem-props' not in FLAGS:
    import build_props
    build_props.build(S)
if '--sem-veg' not in FLAGS:
    import build_veg
    build_veg.build(S, light='--veg-leve' in FLAGS)
import build_env
build_env.build(S)
if '--sem-grama' not in FLAGS:
    import build_grass
    build_grass.build(S)
if '--sem-pessoas' not in FLAGS:
    import build_people
    build_people.build(S)

bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=False)
print('SALVO', OUT)
