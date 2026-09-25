import json, math
from ezdxf import recover, path
from ezdxf.math import Vec3
doc,_=recover.readfile('fixed.dxf'); msp=doc.modelspace()
X0,Y0,X1,Y1=162600,239100,163100,240050
out=[]
def inb(pts): return any(X0<p[0]<X1 and Y0<p[1]<Y1 for p in pts)
def add(e,layer,blk=None,depth=0,iid=None):
    t=e.dxftype()
    if t=='INSERT':
        if depth>6: return
        try:
            for v in e.virtual_entities(): add(v, layer if v.dxf.layer=="0" else v.dxf.layer, blk or e.dxf.name, depth+1, iid)
        except Exception as ex: pass
        return
    try:
        if t=='HATCH':
            for p in e.paths.rendering_paths(e.dxf.hatch_style) if False else []: pass
            ps=[]
            for bp in e.paths:
                pp=path.from_hatch_boundary_path(bp, e.ocs(), e.dxf.elevation.z)
                ps.append([(v.x,v.y) for v in pp.flattening(0.02)])
            pts=[q for s in ps for q in s]
            if pts and inb(pts):
                out.append(dict(t='HATCH',l=layer,b=blk,p=ps,pat=e.dxf.pattern_name,c=e.dxf.color,sol=e.dxf.solid_fill,i=iid))
            return
        if t in ('TEXT','MTEXT'):
            ins=e.dxf.insert
            if X0<ins.x<X1 and Y0<ins.y<Y1:
                txt=e.plain_text() if t=='MTEXT' else e.dxf.text
                out.append(dict(t='TEXT',l=layer,b=blk,p=[[(ins.x,ins.y)]],s=txt,h=1,i=iid))
            return
        if t in ('DIMENSION','LEADER','POINT','ATTRIB','ATTDEF','SOLID','3DFACE','WIPEOUT','IMAGE'): return
        pp=path.make_path(e)
        pts=[(v.x,v.y) for v in pp.flattening(0.02)]
        if pts and inb(pts):
            out.append(dict(t=t,l=layer,b=blk,p=[pts],c=e.dxf.color,i=iid))
    except Exception as ex:
        pass
for k,e in enumerate(msp): add(e,e.dxf.layer,None,0,k)
json.dump(out,open('ents.json','w'))
import collections
print(len(out)); print(collections.Counter((o['l'],o['t']) for o in out).most_common(80))
print(collections.Counter(o['b'] for o in out).most_common(60))
