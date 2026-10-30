"""Pavimentação: pista em asfalto (CBUQ), passeios em paver de concreto intertravado,
meio-fio em concreto (espelho de 15 cm) e canteiros gramados – geometria do DWG (prep_vias.py)."""
import bpy
import numpy as np
import lib_materials as M
from lib_common import TEX

ALTURA_MF = 0.15


def asfalto():
    mat = M.pbr('asfalto', f'{TEX}/Asphalt031', scale=3.0, tint=(0.17, 0.17, 0.18), macro=0.15, rough_mul=1.1)
    return mat


def mesh_tris(name, T, zfun, dz, mat, col):
    n = len(T)
    co = T.reshape(-1, 2)
    z = zfun(co[:, 0], co[:, 1]) + dz
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co)); me.vertices.foreach_set('co', np.c_[co, z].ravel().astype(np.float32))
    me.loops.add(n * 3); me.loops.foreach_set('vertex_index', np.arange(n * 3, dtype=np.int32))
    me.polygons.add(n); me.polygons.foreach_set('loop_start', (np.arange(n) * 3).astype(np.int32))
    me.update(calc_edges=True)
    # normais para cima (a triangulação pode vir em qualquer sentido)
    for p in me.polygons:
        if p.normal.z < 0: p.flip()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)
    bm.to_mesh(me); bm.free()
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    return ob


def walls(name, R, Rn, zfun, top, bottom, mat, col):
    """faces verticais ao longo dos contornos (espelho do meio-fio / borda do passeio)."""
    verts, faces = [], []
    i0 = 0
    for n in Rn:
        ring = R[i0:i0 + n]; i0 += n
        z = zfun(ring[:, 0], ring[:, 1])
        b = len(verts)
        for (x, y), zz in zip(ring, z):
            verts += [(x, y, zz + top), (x, y, zz + bottom)]
        for k in range(n - 1):
            a = b + 2 * k
            faces.append((a, a + 2, a + 3, a + 1))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    return ob


def build(D, zfun, coll_fn, campo_mat):
    V = np.load(f'{D}/vias.npz')
    col = coll_fn('Vias')
    m_asf = asfalto()
    m_pav = M.gen('paver_concreto', 'paver_claro', 4.0, tint=(0.72, 0.71, 0.69), macro=0.08)
    m_con = M.pbr('concreto_meiofio', f'{TEX}/Concrete034', scale=2.0, tint=(0.85, 0.85, 0.84), macro=0.06)
    mesh_tris('pista', V['pista'], zfun, 0.0, m_asf, col)
    mesh_tris('passeio', V['passeio'], zfun, ALTURA_MF, m_pav, col)
    mesh_tris('meio_fio', V['meiofio'], zfun, ALTURA_MF + 0.005, m_con, col)
    mesh_tris('canteiro', V['canteiro'], zfun, ALTURA_MF - 0.03, campo_mat, col)
    for k in ('passeio', 'meiofio', 'canteiro'):
        walls('espelho_' + k, V[k + '_aneis'], V[k + '_aneis_n'], zfun, ALTURA_MF, -0.30, m_con, col)
    walls('borda_pista', V['pista_aneis'], V['pista_aneis_n'], zfun, 0.0, -0.30, m_asf, col)
