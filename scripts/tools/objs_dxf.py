"""Centróide/rotação de cada bloco (árvores, mobiliário) - gera objs.json.
Uso: python3 objs_dxf.py fixed.dxf ents.json objs.json"""
import json, collections, sys
from ezdxf import recover
dxf, ents, out = sys.argv[1:4]
E = json.load(open(ents))
doc, _ = recover.readfile(dxf); msp = list(doc.modelspace())
g = collections.defaultdict(list)
for o in E:
    if o['b'] is None or o.get('i') is None: continue
    for s in o['p']: g[(o['b'], o['i'])].extend(s)
res = []
for (b, i), pts in g.items():
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    if not (239940 < cy < 239995 and 162670 < cx < 163015): continue
    e = msp[i]
    res.append(dict(b=b, i=i, cx=cx, cy=cy, w=max(xs)-min(xs), h=max(ys)-min(ys), rot=e.dxf.rotation, l=e.dxf.layer))
json.dump(res, open(out, 'w'))
