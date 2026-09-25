"""Céu (HDRI), sol, câmeras e configurações de render."""
import bpy, math, os
from mathutils import Vector
import lib_common as C

HDRI = C.ASSETS + '/hdri/kloofendal_48d_partly_cloudy_puresky_4k.exr'

# câmeras: nome -> (posição (x,y,z_rel), alvo (x,y,z_rel), lente mm)
# coordenadas locais do projeto (origem 162840,239970); z relativo ao piso local
CAMS = {
    'aerea_geral':   ((-128, -58, 36), (-25, 4, -4), 24),
    'aerea_leste':   ((150, 45, 32), (40, 2, -8), 24),
    'aerea_food':    ((6.5, -40, 26), (6.5, 1.5, -1.0), 24),
    'food_parque':   ((-7.5, -6.5, 1.65), (12.0, 4.0, 1.0), 20),
    'palco_totem':   ((4.5, -22.5, 1.6), (6.5, -10.5, 1.3), 26),
    'estar_ipe':     ((-49.5, -3.6, 1.6), (-58.2, 2.4, 1.6), 20),
    'quadra_areia':  ((-80.5, -6.5, 1.7), (-97.0, 2.5, 0.8), 20),
    'espaco_kids':   ((145.0, 1.8, 1.65), (155.6, 5.0, 1.3), 22),
    'espaco_pet':    ((-136.0, 2.5, 1.65), (-154.0, 6.5, 1.0), 22),
    'caminho_garden': ((82.0, 6.0, 1.65), (104.0, 8.0, 1.2), 24),
    'vista_ciclovia': ((-30.0, 11.6, 1.65), (-110, 11.0, 0.8), 26),
    'vista_trilha':  ((188, -10, 1.7), (196, 5, 1.2), 22),
}


def zrel(x):
    return C.zc_smooth(x)


def build(S, sun_elev=38, sun_az=205):
    sc = bpy.context.scene
    w = bpy.data.worlds.new('ceu')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(HDRI)
    mp = nt.nodes.new('ShaderNodeMapping')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Generated'], mp.inputs[0])
    nt.links.new(mp.outputs[0], env.inputs[0])
    nt.links.new(env.outputs[0], bg.inputs[0])
    # O sol vem do próprio HDRI (elev. 47,8°, u=0,595).  Giramos o HDRI para
    # que o sol fique a OSO no referencial da planta (norte da rosa-dos-ventos
    # do memorial a 135°): tarde de primavera em Passo Fundo (~15h).
    sun_tex = math.atan2(0.562, -0.827)
    sun_want = math.atan2(-0.40, -0.92)
    mp.inputs['Rotation'].default_value = (0, 0, sun_tex - sun_want)
    bg.inputs[1].default_value = 0.85
    # lâmpada solar alinhada ao sol do HDRI (reforça sombras nítidas)
    sun = bpy.data.lights.new('sol', 'SUN')
    sun.energy = 3.0
    sun.angle = math.radians(0.6)
    sun.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new('sol', sun)
    sc.collection.objects.link(so)
    el = math.radians(47.8)
    sv = Vector((-0.92 * math.cos(el), -0.40 * math.cos(el), math.sin(el)))
    so.rotation_euler = (-sv).to_track_quat('-Z', 'Y').to_euler()
    cc = C.coll('Cameras')
    for name, (p, t, lens) in CAMS.items():
        cam = bpy.data.cameras.new(name)
        cam.lens = lens
        cam.clip_start = 0.05
        cam.clip_end = 6000
        ob = bpy.data.objects.new(name, cam)
        cc.objects.link(ob)
        pz = p[2] + zrel(p[0]) if abs(p[2]) < 5 else p[2]
        tz = t[2] + zrel(t[0])
        ob.location = (p[0], p[1], pz)
        d = Vector((t[0], t[1], tz)) - ob.location
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = bpy.data.objects['aerea_geral']

    r = sc.render
    r.engine = 'CYCLES'
    r.resolution_x, r.resolution_y = 1920, 1080
    r.film_transparent = False
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 128
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 2
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.transmission_bounces = 2
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = 0.0
    r.image_settings.file_format = 'PNG'
    # perspectiva aérea (névoa atmosférica) via passe de mist
    vl = sc.view_layers[0]
    vl.use_pass_mist = True
    w.mist_settings.start = 120
    w.mist_settings.depth = 2500
    w.mist_settings.falloff = 'LINEAR'
    sc.use_nodes = True
    ct = sc.node_tree
    for n in list(ct.nodes):
        ct.nodes.remove(n)
    vl.use_pass_environment = True
    rl = ct.nodes.new('CompositorNodeRLayers')
    r.film_transparent = True
    mix = ct.nodes.new('CompositorNodeMixRGB')
    mix.inputs[2].default_value = (0.70, 0.78, 0.90, 1)
    mm = ct.nodes.new('CompositorNodeMath'); mm.operation = 'MULTIPLY'
    mm.inputs[1].default_value = 0.45
    ct.links.new(rl.outputs['Mist'], mm.inputs[0])
    ct.links.new(mm.outputs[0], mix.inputs[0])
    ct.links.new(rl.outputs['Image'], mix.inputs[1])
    sa = ct.nodes.new('CompositorNodeSetAlpha')
    ct.links.new(mix.outputs[0], sa.inputs[0])
    ct.links.new(rl.outputs['Alpha'], sa.inputs[1])
    ao = ct.nodes.new('CompositorNodeAlphaOver')
    ct.links.new(rl.outputs['Env'], ao.inputs[1])
    ct.links.new(sa.outputs[0], ao.inputs[2])
    comp = ct.nodes.new('CompositorNodeComposite')
    comp.use_alpha = False
    ct.links.new(ao.outputs[0], comp.inputs[0])
