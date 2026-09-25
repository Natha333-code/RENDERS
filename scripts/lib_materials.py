"""Materiais PBR (texturas ambientCG + texturas geradas) e procedurais."""
import bpy, os
from lib_common import TEX

_cache = {}


def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (900, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return nt, bsdf, out


def _img(nt, path, noncolor=False, loc=(0, 0)):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        n.image.colorspace_settings.name = 'Non-Color'
    n.location = loc
    return n


def _find(folder, key):
    for f in os.listdir(folder):
        if key in f and (f.endswith('.jpg') or f.endswith('.png')):
            return os.path.join(folder, f)
    return None


def _coords(nt, scale, rot=0.0, uv=False):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (-900, 0)
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.location = (-700, 0)
    nt.links.new(tc.outputs['UV' if uv else 'Object'], mp.inputs[0])
    s = 1.0 / scale
    mp.inputs['Scale'].default_value = (s, s, s)
    mp.inputs['Rotation'].default_value = (0, 0, rot)
    return mp


def _macro(nt, scale=9.0, amt=0.18):
    """variação de grande escala (evita repetição visível)."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nt.links.new(tc.outputs['Object'], nz.inputs[0])
    nz.inputs['Scale'].default_value = 1.0 / scale
    nz.inputs['Detail'].default_value = 3
    mr = nt.nodes.new('ShaderNodeMapRange')
    nt.links.new(nz.outputs[0], mr.inputs[0])
    mr.inputs[1].default_value = 0.3
    mr.inputs[2].default_value = 0.7
    mr.inputs[3].default_value = 1 - amt
    mr.inputs[4].default_value = 1 + amt
    return mr


def pbr(name, folder=None, scale=2.0, tint=None, rough_mul=1.0, normal=1.0, uv=False,
        rot=0.0, files=None, macro=0.12, macro_scale=9.0, hsv=None, spec=0.5):
    """folder: pasta ambientCG em assets/tex; files: dict com color/rough/normal."""
    key = name
    if key in _cache:
        return _cache[key]
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = _nodes(mat)
    mp = _coords(nt, scale, rot, uv)
    if files is None:
        d = os.path.join(TEX, folder)
        files = {'color': _find(d, '_Color'), 'rough': _find(d, '_Roughness'), 'normal': _find(d, '_NormalGL')}
    col = _img(nt, files['color'], loc=(-400, 300))
    boxp = not uv
    nt.links.new(mp.outputs[0], col.inputs[0])
    if boxp:
        col.projection = 'BOX'; col.projection_blend = 0.25
    c_out = col.outputs[0]
    if hsv:
        h = nt.nodes.new('ShaderNodeHueSaturation')
        h.inputs['Hue'].default_value, h.inputs['Saturation'].default_value, h.inputs['Value'].default_value = hsv
        nt.links.new(c_out, h.inputs['Color'])
        c_out = h.outputs[0]
    if tint:
        m = nt.nodes.new('ShaderNodeMix')
        m.data_type = 'RGBA'
        m.blend_type = 'MULTIPLY'
        m.inputs['Factor'].default_value = 1.0
        m.inputs[7].default_value = (*tint, 1)
        nt.links.new(c_out, m.inputs[6])
        c_out = m.outputs[2]
    if macro:
        mr = _macro(nt, macro_scale, macro)
        m = nt.nodes.new('ShaderNodeMix')
        m.data_type = 'RGBA'
        m.blend_type = 'MULTIPLY'
        m.inputs['Factor'].default_value = 1.0
        cr = nt.nodes.new('ShaderNodeCombineColor')
        for i in range(3):
            nt.links.new(mr.outputs[0], cr.inputs[i])
        nt.links.new(c_out, m.inputs[6])
        nt.links.new(cr.outputs[0], m.inputs[7])
        c_out = m.outputs[2]
    nt.links.new(c_out, bsdf.inputs['Base Color'])
    if files.get('rough'):
        r = _img(nt, files['rough'], True, (-400, 0))
        if boxp:
            r.projection = 'BOX'; r.projection_blend = 0.25
        nt.links.new(mp.outputs[0], r.inputs[0])
        if rough_mul != 1.0:
            mm = nt.nodes.new('ShaderNodeMath')
            mm.operation = 'MULTIPLY'
            mm.inputs[1].default_value = rough_mul
            nt.links.new(r.outputs[0], mm.inputs[0])
            nt.links.new(mm.outputs[0], bsdf.inputs['Roughness'])
        else:
            nt.links.new(r.outputs[0], bsdf.inputs['Roughness'])
    if files.get('normal') and normal:
        n = _img(nt, files['normal'], True, (-400, -300))
        if boxp:
            n.projection = 'BOX'; n.projection_blend = 0.25
        nt.links.new(mp.outputs[0], n.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal
        nt.links.new(n.outputs[0], nm.inputs['Color'])
        nt.links.new(nm.outputs[0], bsdf.inputs['Normal'])
    bsdf.inputs['Specular IOR Level'].default_value = spec
    _cache[key] = mat
    return mat


def flat(name, color, rough=0.5, metal=0.0, spec=0.5, alpha=1.0, trans=0.0, coat=0.0):
    if name in _cache:
        return _cache[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = _nodes(mat)
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Specular IOR Level'].default_value = spec
    bsdf.inputs['Coat Weight'].default_value = coat
    if trans:
        bsdf.inputs['Transmission Weight'].default_value = trans
    if alpha < 1:
        bsdf.inputs['Alpha'].default_value = alpha
    _cache[name] = mat
    return mat


def gen(name, prefix, scale, tint=None, uv=False, normal=1.0, macro=0.08):
    d = os.path.join(TEX, 'gen')
    return pbr(name, scale=scale, uv=uv, tint=tint, normal=normal, macro=macro,
               files={'color': f'{d}/{prefix}_color.jpg', 'rough': f'{d}/{prefix}_rough.jpg',
                      'normal': f'{d}/{prefix}_normal.png'})


def ciclovia_mat():
    """Concreto escovado com pintura epóxi vermelha, juntas a cada 1,75 m."""
    if 'ciclovia' in _cache:
        return _cache['ciclovia']
    base = pbr('_ciclo_base', 'Concrete034', scale=2.5, macro=0.0)
    mat = base.copy()
    mat.name = 'ciclovia'
    nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    colnode = [n for n in nt.nodes if n.type == 'TEX_IMAGE' and '_Color' in n.image.name][0]
    # cor vermelha modulada pelo concreto
    bw = nt.nodes.new('ShaderNodeRGBToBW')
    nt.links.new(colnode.outputs[0], bw.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.30, 0.025, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.9
    ramp.color_ramp.elements[1].color = (0.62, 0.07, 0.05, 1)
    nt.links.new(bw.outputs[0], ramp.inputs[0])
    # juntas transversais (x mod 1,75)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    md = nt.nodes.new('ShaderNodeMath'); md.operation = 'PINGPONG'
    md.inputs[1].default_value = 0.875
    nt.links.new(sep.outputs[0], md.inputs[0])
    lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'
    lt.inputs[1].default_value = 0.006
    nt.links.new(md.outputs[0], lt.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    nt.links.new(lt.outputs[0], mix.inputs['Factor'])
    nt.links.new(ramp.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (0.08, 0.02, 0.02, 1)
    nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
    _cache['ciclovia'] = mat
    return mat


def paint(name, color, rough=0.45):
    """tinta de sinalização viária (termoplástica)."""
    return flat(name, color, rough=rough, spec=0.5)


def wire_fence(name, color, sx, sy, wire=0.004, metal=0.3, rough=0.45):
    """Tela metálica procedural com alfa: malha sx (horizontal) x sy (vertical)
    em coordenadas UV em metros (u ao longo do painel, v altura)."""
    if name in _cache:
        return _cache[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = _nodes(mat)
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['UV'], sep.inputs[0])

    def lines(inp, sp):
        pp = nt.nodes.new('ShaderNodeMath'); pp.operation = 'PINGPONG'
        pp.inputs[1].default_value = sp / 2
        nt.links.new(inp, pp.inputs[0])
        lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'
        lt.inputs[1].default_value = wire / 2
        nt.links.new(pp.outputs[0], lt.inputs[0])
        return lt.outputs[0]
    a = lines(sep.outputs[0], sx)
    b = lines(sep.outputs[1], sy)
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'
    nt.links.new(a, mx.inputs[0]); nt.links.new(b, mx.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(mx.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    mat.blend_method = 'HASHED'
    _cache[name] = mat
    return mat


def decal(name, path, rough=0.5):
    """imagem com alfa (UV) - logo do totem, pictogramas."""
    if name in _cache:
        return _cache[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = _nodes(mat)
    im = _img(nt, path)
    nt.links.new(im.outputs[0], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = rough
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(im.outputs[1], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    _cache[name] = mat
    return mat
