"""Entorno real a partir do OpenStreetMap (© colaboradores do OSM, ODbL):
ruas em asfalto sobre o terreno e prédios extrudados (cor do telhado da imagem aérea)."""
import bpy, bmesh
import numpy as np
import lib_materials as M
from lib_common import TEX


def ruas(R, height, col):
    m_asf = M.pbr('asfalto_rua', f'{TEX}/Asphalt031', scale=3.0, tint=(0.20, 0.20, 0.21), macro=0.15)
    m_terra = M.pbr('estrada_terra', f'{TEX}/Ground037', scale=3.0, tint=(0.75, 0.55, 0.42), macro=0.15)
    for terra, mat in ((False, m_asf), (True, m_terra)):
        verts, faces = [], []
        for r in R:
            if r['terra'] != terra:
                continue
            p = np.array(r['p'], float)
            # reamostra a cada 3 m
            seg = np.hypot(*np.diff(p, axis=0).T); s = np.r_[0, np.cumsum(seg)]
            if s[-1] < 1: continue
            t = np.linspace(0, s[-1], max(2, int(s[-1] / 3) + 1))
            q = np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])]
            d = np.gradient(q, axis=0); d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
            nrm = np.c_[-d[:, 1], d[:, 0]] * r['w'] / 2
            a, b = q + nrm, q - nrm
            za = height(a[:, 0], a[:, 1]); zb = height(b[:, 0], b[:, 1]); zc = height(q[:, 0], q[:, 1])
            za = np.maximum(za, zc) + 0.12; zb = np.maximum(zb, zc) + 0.12
            k0 = len(verts)
            for i in range(len(q)):
                verts += [(a[i, 0], a[i, 1], za[i]), (b[i, 0], b[i, 1], zb[i])]
            for i in range(len(q) - 1):
                k = k0 + 2 * i
                faces.append((k, k + 2, k + 3, k + 1))
        if not faces: continue
        me = bpy.data.meshes.new('ruas_terra' if terra else 'ruas_asfalto')
        me.from_pydata(verts, [], faces); me.materials.append(mat)
        for p in me.polygons:
            if p.normal.z < 0: p.flip()
        ob = bpy.data.objects.new(me.name, me); col.objects.link(ob)


def predios(P, height, col):
    mp = bpy.data.materials.get('casa_parede')
    if mp is None:
        import build_casas
        mp, _ = build_casas.materiais()
    mt = bpy.data.materials.new('predio_cobertura'); mt.use_nodes = True
    nt = mt.node_tree; b = nt.nodes['Principled BSDF']
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'cor'
    nt.links.new(at.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.6
    bm = bmesh.new()
    cl = bm.loops.layers.color.new('cor')
    for pr in P:
        pts = np.array(pr['p'])[:-1]
        if len(pts) < 3: continue
        z0 = float(np.min(height(pts[:, 0], pts[:, 1]))) - 0.3
        z1 = float(np.max(height(pts[:, 0], pts[:, 1]))) + pr['h']
        bot = [bm.verts.new((x, y, z0)) for x, y in pts]
        top = [bm.verts.new((x, y, z1)) for x, y in pts]
        try:
            ft = bm.faces.new(top)
        except ValueError:
            continue
        ft.material_index = 1
        c = (*pr['cor'], 1.0)
        for l in ft.loops: l[cl] = c
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((bot[i], bot[j], top[j], top[i])); f.material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('predios_osm'); bm.to_mesh(me); bm.free()
    me.materials.append(mp); me.materials.append(mt)
    ob = bpy.data.objects.new('predios_osm', me); col.objects.link(ob)


def build(J, height, coll_fn):
    col = coll_fn('Contexto')
    if J.get('ruas_osm'): ruas(J['ruas_osm'], height, col)
    if J.get('predios'): predios(J['predios'], height, col)
