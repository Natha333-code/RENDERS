import sys, json
from ezdxf import recover, path
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
doc,_=recover.readfile(sys.argv[1]); msp=doc.modelspace()
out={}
fig,ax=plt.subplots(figsize=(14,24))
col={'C-TOPO-MAJR':'#a0522d','C-TOPO-MINR':'#deb887','TOPO_Aux_Superficie':'#dddddd','URB-Lotes':'k','URB-Quadras':'b','URB-Calçada':'g','URB-Perímetr':'r','Banhado':'c','BOUNDARIE':'m','BOUNDARIE SURFACE':'y','Poligonal':'orange','TOPO_Des Meio Fio':'purple'}
for e in msp:
    l=e.dxf.layer; t=e.dxftype()
    if t in('LWPOLYLINE','POLYLINE','LINE','ARC','CIRCLE'):
        try: pts=[(v.x,v.y) for v in path.make_path(e).flattening(0.1)]
        except: continue
        z=e.dxf.elevation if t=='LWPOLYLINE' else 0
        out.setdefault(l,[]).append(dict(z=z,p=pts,closed=bool(getattr(e,'closed',False))))
        xs,ys=zip(*pts); ax.plot(xs,ys,color=col.get(l,'gray'),lw=0.4 if 'TOPO' in l else 0.9)
    elif t in('TEXT','MTEXT'):
        txt=e.plain_text() if t=='MTEXT' else e.dxf.text; p=e.dxf.insert
        out.setdefault('_txt',[]).append(dict(l=l,s=txt,x=p.x,y=p.y,r=e.dxf.get('rotation',0)))
        ax.text(p.x,p.y,txt,fontsize=4 if l!='TXT-Ruas' else 8)
    elif t=='HATCH':
        for bp in e.paths:
            pp=path.from_hatch_boundary_path(bp,e.ocs(),e.dxf.elevation.z)
            pts=[(v.x,v.y) for v in pp.flattening(0.1)]
            out.setdefault('_hatch',[]).append(dict(l=l,pat=e.dxf.pattern_name,p=pts))
            xs,ys=zip(*pts); ax.fill(xs,ys,alpha=0.3)
ax.set_aspect('equal'); plt.savefig(sys.argv[2],dpi=110,bbox_inches='tight')
json.dump(out,open(sys.argv[3],'w'))
for k,v in out.items(): print(k,len(v))
