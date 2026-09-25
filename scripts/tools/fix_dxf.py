"""Corrige textos multilinha quebrados no DXF gerado pelo dwg2dxf (LibreDWG).
Uso: python3 fix_dxf.py projeto.dxf fixed.dxf"""
import sys
raw = open(sys.argv[1], 'rb').read()
lines = raw.split(b'\r\n') if b'\r\n' in raw[:2000] else raw.split(b'\n')
out = []; i = 0
while i < len(lines) - 1:
    try:
        int(lines[i].strip())
    except ValueError:
        out[-1] += b' ' + lines[i].strip(); i += 1; continue
    out += [lines[i], lines[i + 1]]; i += 2
open(sys.argv[2], 'wb').write(b'\n'.join(out) + b'\n')
