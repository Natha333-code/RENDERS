"""Exporta a praça para COLLADA (.dae) otimizado para SketchUp:
 - elementos repetidos (árvores, bancos, lixeiras...) como COMPONENTES
   (library_nodes + instance_node, formato que o SketchUp importa como
   definições de componente);
 - árvores em versão leve: tronco/galhos simplificados + copa em 'cachos'
   de folhagem texturizados (texturas renderizadas das próprias árvores);
 - texturas com coordenadas UV em metros (escala real), cores finais.
blender -b praca.blend --python sk_export.py -- saida.dae pasta_texturas_rel pasta_texturas_abs"""
import bpy, bmesh, sys, os, math, random, json, re, shutil
from mathutils import Vector, Matrix
from xml.sax.saxutils import escape

argv = sys.argv[sys.argv.index('--') + 1:]
OUT, TEXREL, TEXABS = argv[0], argv[1], argv[2]
rnd = random.Random(7)

# ------------------------------------------------------------ materiais
BOX = {'areia': 2.0, 'asfalto': 3.0, 'calcada': 2.5, 'ciclovia': 2.5, 'concreto': 2.0, 'concreto_arq': 2.0,
       'estipe_jeriva': 0.6, 'galvanizado': 0.6, 'grama': 1.8, 'jatoba': 0.8, 'lote': 2.2, 'meio_fio': 1.5,
       'palco': 2.5, 'palete': 0.6, 'paver_claro': 4.0, 'paver_escuro': 4.0, 'pedrisco': 1.2,
       'solo_mata': 3.0, 'terra_casca': 1.0}
UV = {'tatil_alerta': ('tatil_alerta.jpg', 1.0), 'tatil_direcional': ('tatil_direcional.jpg', 1.0),
      'logo': ('logo.png', 1.0), 'pictograma': ('pictograma.png', 1.0),
      'tela_gradil': ('tela_gradil.png', 0.5), 'tela_alambrado': ('tela_alambrado.png', 0.5),
      'rede_esporte': ('rede_esporte.png', 0.5)}
NICE = {'grama': 'Grama sempre-verde', 'paver_claro': 'Paver holandes cinza claro',
        'paver_escuro': 'Paver holandes cinza escuro', 'ciclovia': 'Concreto escovado pintura epoxi vermelha',
        'asfalto': 'Asfalto', 'calcada': 'Concreto calcada', 'meio_fio': 'Concreto meio-fio e tentos',
        'areia': 'Areia lavada', 'palco': 'Concreto pintado palco', 'jatoba': 'Madeira jatoba',
        'palete': 'Madeira palete tratada', 'tela_gradil': 'Tela Gradil verde', 'pedrisco': 'Pedrisco compactado',
        'tatil_alerta': 'Piso tatil alerta', 'tatil_direcional': 'Piso tatil direcional',
        'tinta_branca': 'Pintura viaria branca', 'metal_grafite': 'Aco pintado grafite', 'lote': 'Grama lotes'}


def lin2srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def sid(s):
    s = re.sub(r'[^A-Za-z0-9_]', '_', s)
    return ('m_' + s) if not s[:1].isalpha() else s


class Mats:
    def __init__(self):
        self.m = {}      # nome -> dict(kind, img, scale, color, alpha)
        self.images = {}

    def image(self, fname):
        self.images[sid('img_' + fname)] = fname
        return sid('img_' + fname)

    def get(self, mat):
        name = mat.name if mat else 'sem_material'
        base = name.split('.')[0]
        if name in self.m:
            return name
        d = {'nice': NICE.get(base, base)}
        if base in BOX:
            d.update(kind='box', img=self.image(base + '.jpg'), scale=BOX[base])
        elif base in UV:
            f, s = UV[base]
            d.update(kind='uv', img=self.image(f), scale=s)
        elif mat and mat.node_tree and any(n.type == 'TEX_IMAGE' and n.image and 'diff' in n.image.name.lower()
                                           for n in mat.node_tree.nodes):
            im = [n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'diff' in n.image.name.lower()][0]
            fn = sid(os.path.splitext(bpy.path.basename(im.filepath))[0]) + '.jpg'
            dst = os.path.join(TEXABS, fn)
            if not os.path.exists(dst):
                src = bpy.path.abspath(im.filepath)
                img = bpy.data.images.load(src, check_existing=False)
                if img.size[0] > 1024:
                    img.scale(1024, int(1024 * img.size[1] / img.size[0]))
                img.filepath_raw = dst
                img.file_format = 'JPEG'
                img.save()
                bpy.data.images.remove(img)
            d.update(kind='uv', img=self.image(fn), scale=1.0)
        else:
            col, a = (0.6, 0.6, 0.6), 1.0
            if mat and mat.node_tree:
                b = [n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']
                if b:
                    c = b[0].inputs['Base Color'].default_value
                    col = tuple(lin2srgb(max(0, v)) for v in c[:3])
            d.update(kind='color', color=col, alpha=a)
        self.m[name] = d
        return name

    def folhagem(self, fname):
        name = 'folhagem_' + fname
        if name not in self.m:
            self.m[name] = dict(kind='uv', img=self.image(fname), scale=1.0, nice=name)
        return name


M = Mats()


# ------------------------------------------------------------ geometria
class Geo:
    """Malha triangulada com materiais e UV (coords no espaço dado)."""
    def __init__(self, name):
        self.name = name
        self.P = []           # posições
        self.pmap = {}
        self.tris = {}        # material -> lista (i0,uv0,i1,uv1,i2,uv2)
        self.UVs = []

    def vid(self, p):
        k = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
        i = self.pmap.get(k)
        if i is None:
            i = self.pmap[k] = len(self.P)
            self.P.append(k)
        return i

    def add_tri(self, mat, pts, uvs):
        base = len(self.UVs)
        self.UVs.extend(uvs)
        t = self.tris.setdefault(mat, [])
        t.append((self.vid(pts[0]), base, self.vid(pts[1]), base + 1, self.vid(pts[2]), base + 2))

    def ntris(self):
        return sum(len(v) for v in self.tris.values())


def box_uv(p, n, s):
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 2:
        return (p[0] / s, p[1] / s)
    if ax == 0:
        return (p[1] / s, p[2] / s)
    return (p[0] / s, p[2] / s)


def add_mesh(geo, ob, mat_world, depsgraph):
    """acrescenta a malha avaliada de `ob` transformada por mat_world."""
    ev = ob.evaluated_get(depsgraph)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return
    if me is None:
        return
    me.calc_loop_triangles()
    uvl = me.uv_layers.active.data if me.uv_layers.active else None
    mats = [s.material for s in ev.material_slots] or [None]
    nm = mat_world.to_3x3().inverted_safe().transposed()
    for lt in me.loop_triangles:
        mat = mats[min(lt.material_index, len(mats) - 1)] if mats else None
        mname = M.get(mat)
        spec = M.m[mname]
        pts = [mat_world @ me.vertices[v].co for v in lt.vertices]
        n = (nm @ lt.normal).normalized()
        if spec['kind'] == 'box':
            uvs = [box_uv(p, n, spec['scale']) for p in pts]
        elif spec['kind'] == 'uv' and uvl:
            s = spec['scale']
            uvs = [(uvl[l].uv[0] / s, uvl[l].uv[1] / s) for l in lt.loops]
        else:
            uvs = [(0, 0)] * 3
        geo.add_tri(mname, [tuple(p) for p in pts], uvs)
    ev.to_mesh_clear()


# ------------------------------------------------------------ árvores leves
def lowpoly_tree(col, species, depsgraph, foliage_files):
    """col: coleção T_* (árvore Poly Haven). Retorna Geo leve."""
    geo = Geo('arvore_' + species)
    src = [o for o in col.all_objects if o.type == 'MESH'][0]
    ev = src.evaluated_get(depsgraph)
    me = ev.to_mesh()
    mats = [s.material for s in ev.material_slots]
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    leaf_idx = {i for i, m in enumerate(mats) if m and ('leaves' in m.name or 'leaf' in m.name)}
    leaves = [f for f in bm.faces if f.material_index in leaf_idx]
    pts = [(f.calc_center_median().copy()) for f in leaves]
    bmesh.ops.delete(bm, geom=leaves, context='FACES')
    # tronco e galhos simplificados
    tmp = bpy.data.meshes.new('tmp_tronco')
    bm.to_mesh(tmp)
    bm.free()
    to = bpy.data.objects.new('tmp_tronco', tmp)
    for m in mats:
        tmp.materials.append(m)
    bpy.context.scene.collection.objects.link(to)
    n = sum(len(p.vertices) - 2 for p in tmp.polygons)
    dec = to.modifiers.new('d', 'DECIMATE')
    dec.ratio = min(1.0, 3500 / max(n, 1))
    bpy.context.view_layer.update()
    add_mesh(geo, to, Matrix.Identity(4), bpy.context.evaluated_depsgraph_get())
    bpy.data.objects.remove(to)
    bpy.data.meshes.remove(tmp)
    # copa: 'cachos' de folhagem sobre pontos das folhas originais
    if pts:
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        ctr = (lo + hi) / 2
        size = max((hi - lo).x, (hi - lo).y, (hi - lo).z)
        k = 260
        sel = rnd.sample(pts, min(k, len(pts)))
        s = size * 0.19
        for p in sel:
            out = (p - ctr)
            out.z *= 0.6
            out = (out.normalized() if out.length > 1e-3 else Vector((0, 0, 1)))
            nrm = (out + Vector((rnd.uniform(-.6, .6), rnd.uniform(-.6, .6), rnd.uniform(-.3, .6)))).normalized()
            t1 = nrm.orthogonal().normalized()
            t1.rotate(Matrix.Rotation(rnd.uniform(0, 6.28), 3, nrm))
            t2 = nrm.cross(t1)
            c = p + out * s * 0.15
            q = [c - t1 * s / 2 - t2 * s / 2, c + t1 * s / 2 - t2 * s / 2, c + t1 * s / 2 + t2 * s / 2,
                 c - t1 * s / 2 + t2 * s / 2]
            mname = M.folhagem(rnd.choice(foliage_files))
            geo.add_tri(mname, [tuple(q[0]), tuple(q[1]), tuple(q[2])], [(0, 0), (1, 0), (1, 1)])
            geo.add_tri(mname, [tuple(q[0]), tuple(q[2]), tuple(q[3])], [(0, 0), (1, 1), (0, 1)])
    return geo


# ------------------------------------------------------------ montagem
dg = bpy.context.evaluated_depsgraph_get()
SPECIES = {'T_quaresmeira': ('quaresmeira', 'Quaresmeira'), 'T_extremosa': ('extremosa', 'Extremosa branca'),
           'T_manaca': ('manaca', 'Manaca-da-serra'), 'T_jabuticabeira': ('jabuticabeira', 'Jabuticabeira'),
           'T_ipe': ('ipe', 'Ipe-amarelo'), 'T_mata1': ('mata1', 'Arvore nativa 1'), 'T_mata2': ('mata2', 'Arvore nativa 2')}
COMPNAMES = {'A_banco': 'Banco padrao PMPF', 'A_lixeira': 'Lixeira padrao PMPF', 'A_bicicletario': 'Bicicletario 4 vagas',
             'A_bebedouro': 'Bebedouro pet', 'A_lixeira_pet': 'Lixeira pet', 'A_grelha': 'Grelha de arvore D100',
             'A_moreia': 'Moreia', 'A_belaemilia': 'Bela-emilia', 'A_jeriva': 'Jeriva', 'A_araucaria': 'Araucaria',
             'A_palet_3': 'Modulo palete assento', 'A_palet_4': 'Modulo palete mesa'}
fol = json.load(open(os.path.join(TEXABS, 'folhagem.json')))
foliage = {sp: sorted(f for f in os.listdir(TEXABS) if f.startswith('folhagem_' + sp + '_')) for sp in fol}

comps = {}   # collection name -> (Geo, nice)


def comp_for(c):
    if c.name in comps:
        return comps[c.name]
    if c.name in SPECIES:
        sp, nice = SPECIES[c.name]
        g = lowpoly_tree(c, sp, dg, foliage[sp])
    else:
        g = Geo(c.name)
        for o in c.all_objects:
            if o.type in ('MESH', 'CURVE'):
                add_mesh(g, o, Matrix.Translation(-c.instance_offset) @ o.matrix_world, dg)
        nice = next((v for k, v in COMPNAMES.items() if c.name.startswith(k)), c.name)
        m = re.search(r'_(\d+)$', c.name)
        if m and not c.name.startswith('A_palet'):
            nice += ' ' + str(int(m.group(1)) % 10 + 1)
    comps[c.name] = (g, nice)
    print('componente', nice, g.ntris(), flush=True)
    return comps[c.name]


SKIP_COLL = {'GramaFios', 'Cameras', '_assets'}
GROUPS = {}   # grupo -> lista (tipo, dados)


def group_of(o):
    cs = [c.name for c in o.users_collection]
    for c in cs:
        if c.startswith('Pessoas') or c in ('GramaFios', 'Cameras', 'Bicicletas') or c.startswith('_'):
            return None
    c = cs[0] if cs else 'Outros'
    return {'Playground': 'Mobiliario', 'Pet': 'Mobiliario', 'Garden': 'Mobiliario'}.get(c, c)


def in_assets(o):
    def walk(c):
        if o.name in c.objects:
            return True
        return any(walk(ch) for ch in c.children)
    a = bpy.data.collections.get('_assets')
    return a is not None and walk(a)


statics = 0
for o in bpy.context.scene.objects:
    if o.name.startswith(('grama_', 'entorno', 'pessoa_')) or o.type not in ('MESH', 'CURVE', 'EMPTY'):
        continue
    if in_assets(o):
        continue
    g = group_of(o)
    if g is None:
        continue
    if o.type == 'EMPTY':
        c = o.instance_collection
        if not c or o.instance_type != 'COLLECTION':
            continue
        if math.hypot(o.location.x - 40, o.location.y) > 330:
            continue   # mata do horizonte (fora do SketchUp)
        comp_for(c)
        GROUPS.setdefault(g, []).append(('inst', o.name, c.name, o.matrix_world.copy()))
    else:
        geo = Geo(o.name)
        add_mesh(geo, o, o.matrix_world, dg)
        if geo.ntris():
            GROUPS.setdefault(g, []).append(('geo', o.name, geo))
            statics += geo.ntris()

# ------------------------------------------------------------ COLLADA
def f4(v):
    return ('%.4f' % v).rstrip('0').rstrip('.') if v != 0 else '0'


def geo_xml(g, gid):
    pos = ' '.join(f4(c) for p in g.P for c in p)
    uv = ' '.join(f4(c) for t in g.UVs for c in t)
    x = [f'<geometry id="{gid}" name="{escape(g.name)}"><mesh>',
         f'<source id="{gid}-pos"><float_array id="{gid}-pos-a" count="{len(g.P) * 3}">{pos}</float_array>'
         f'<technique_common><accessor source="#{gid}-pos-a" count="{len(g.P)}" stride="3">'
         '<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
         '</accessor></technique_common></source>',
         f'<source id="{gid}-uv"><float_array id="{gid}-uv-a" count="{len(g.UVs) * 2}">{uv}</float_array>'
         f'<technique_common><accessor source="#{gid}-uv-a" count="{len(g.UVs)}" stride="2">'
         '<param name="S" type="float"/><param name="T" type="float"/></accessor></technique_common></source>',
         f'<vertices id="{gid}-v"><input semantic="POSITION" source="#{gid}-pos"/></vertices>']
    for mname, tris in g.tris.items():
        p = ' '.join(str(i) for t in tris for i in t)
        x.append(f'<triangles material="{sid(mname)}" count="{len(tris)}">'
                 f'<input semantic="VERTEX" source="#{gid}-v" offset="0"/>'
                 f'<input semantic="TEXCOORD" source="#{gid}-uv" offset="1" set="0"/><p>{p}</p></triangles>')
    x.append('</mesh></geometry>')
    return ''.join(x)


def inst_geo(g, gid):
    b = ''.join(f'<instance_material symbol="{sid(m)}" target="#{sid(m)}"><bind_vertex_input semantic="UVSET0" '
                f'input_semantic="TEXCOORD" input_set="0"/></instance_material>' for m in g.tris)
    return f'<instance_geometry url="#{gid}"><bind_material><technique_common>{b}</technique_common></bind_material></instance_geometry>'


def mat4(m):
    return ' '.join(f4(m[i][j]) for i in range(4) for j in range(4))


with open(OUT, 'w', encoding='utf-8') as F:
    F.write('<?xml version="1.0" encoding="utf-8"?>\n<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">')
    F.write('<asset><contributor><authoring_tool>Praca Linear - Reserva das Araucarias (Blender)</authoring_tool></contributor>'
            '<unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>')
    # geometrias primeiro (para registrar materiais)
    geos = []
    for cname, (g, nice) in comps.items():
        geos.append((g, 'geo_c_' + sid(cname)))
    for grp, items in GROUPS.items():
        for it in items:
            if it[0] == 'geo':
                geos.append((it[2], 'geo_s_' + sid(it[1])))
    used = set(m for g, _ in geos for m in g.tris)
    F.write('<library_images>')
    imgs_used = {M.m[m]['img'] for m in used if 'img' in M.m[m]}
    for iid in sorted(imgs_used):
        F.write(f'<image id="{iid}" name="{iid}"><init_from>{TEXREL}/{M.images[iid]}</init_from></image>')
    F.write('</library_images><library_effects>')
    for m in sorted(used):
        d = M.m[m]
        e = sid(m) + '-fx'
        if 'img' in d:
            iid = d['img']
            tr = ''
            if M.images[iid].endswith('.png'):
                tr = f'<transparent opaque="A_ONE"><texture texture="{iid}-smp" texcoord="UVSET0"/></transparent>'
            F.write(f'<effect id="{e}"><profile_COMMON><newparam sid="{iid}-srf"><surface type="2D"><init_from>{iid}</init_from>'
                    f'</surface></newparam><newparam sid="{iid}-smp"><sampler2D><source>{iid}-srf</source></sampler2D></newparam>'
                    f'<technique sid="common"><lambert><diffuse><texture texture="{iid}-smp" texcoord="UVSET0"/></diffuse>{tr}'
                    f'</lambert></technique></profile_COMMON></effect>')
        else:
            r, g_, b = d['color']
            F.write(f'<effect id="{e}"><profile_COMMON><technique sid="common"><lambert><diffuse><color>{f4(r)} {f4(g_)} {f4(b)} 1'
                    f'</color></diffuse></lambert></technique></profile_COMMON></effect>')
    F.write('</library_effects><library_materials>')
    for m in sorted(used):
        F.write(f'<material id="{sid(m)}" name="{escape(M.m[m]["nice"])}"><instance_effect url="#{sid(m)}-fx"/></material>')
    F.write('</library_materials><library_geometries>')
    for g, gid in geos:
        F.write(geo_xml(g, gid))
    F.write('</library_geometries><library_nodes>')
    for cname, (g, nice) in comps.items():
        F.write(f'<node id="comp_{sid(cname)}" name="{escape(nice)}">{inst_geo(g, "geo_c_" + sid(cname))}</node>')
    F.write('</library_nodes><library_visual_scenes><visual_scene id="cena" name="cena">'
            '<node id="praca" name="Praca Linear - Reserva das Araucarias">')
    NG = {'Pisos': 'Pisos e pavimentos', 'Mobiliario': 'Mobiliario e equipamentos', 'Vegetacao': 'Paisagismo',
          'Mata': 'Vegetacao existente - Area de Espacos Livres'}
    k = 0
    for grp, items in GROUPS.items():
        F.write(f'<node id="grp_{sid(grp)}" name="{escape(NG.get(grp, grp))}">')
        for it in items:
            k += 1
            if it[0] == 'geo':
                F.write(f'<node id="n{k}" name="{escape(it[1])}">{inst_geo(it[2], "geo_s_" + sid(it[1]))}</node>')
            else:
                _, oname, cname, mw = it
                F.write(f'<node id="n{k}" name="{escape(comps[cname][1])}"><matrix>{mat4(mw)}</matrix>'
                        f'<instance_node url="#comp_{sid(cname)}"/></node>')
        F.write('</node>')
    F.write('</node></visual_scene></library_visual_scenes><scene><instance_visual_scene url="#cena"/></scene></COLLADA>')

tot_c = sum(g.ntris() for g, _ in comps.values())
ninst = sum(1 for items in GROUPS.values() for it in items if it[0] == 'inst')
print('EXPORT_OK', OUT, 'estatico_tris', statics, 'componentes', len(comps), 'tris_componentes', tot_c, 'instancias', ninst)


# ------------------------------------------------------------ script Ruby (SketchUp)
cams = []
for o in bpy.data.objects:
    if o.type == 'CAMERA' and o.name != 'topo':
        eye = o.matrix_world.translation
        fwd = o.matrix_world.to_3x3() @ Vector((0, 0, -1))
        tgt = eye + fwd * 20
        fov = math.degrees(2 * math.atan(18 * 9 / 16 / o.data.lens))
        cams.append((o.name, tuple(eye), tuple(tgt), fov))
rb_cams = ',\n'.join(f'    ["{n}", [{e[0]:.3f}, {e[1]:.3f}, {e[2]:.3f}], [{t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f}], {fv:.2f}]'
                     for n, e, t, fv in sorted(cams))
RB = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'organizar_praca.rb.in'), encoding='utf-8').read()
RB = RB.replace('%%CAMERAS%%', rb_cams)
open(os.path.join(os.path.dirname(OUT), 'organizar_praca.rb'), 'w', encoding='utf-8').write(RB)
print('RUBY_OK')
