# Terraplenagem – Plato Geral · Rua B

Imagem 3D realista da superfície projetada **PLATO GERAL - RUA B** (Civil 3D), com
destaque de corte e aterro, vista em perspectiva a partir da Rua B.

Resultados (1920×1080) em `renders_terraplenagem/`:
- `plato_rua_b.png` / `plato_rua_b_sem_legenda.png`: perspectiva elevada, estilo realista, com corte e aterro.
- `plato_rua_b_calcada_conceitual.png` / `..._sem_titulo.png`: vista do pedestre (olho a 1,65 m) na
  calçada SO da Rua B, estilo conceitual (maquete), sem manchas de corte/aterro. As figuras humanas
  servem apenas de escala.

## Dados usados (pasta `dados/`)
| Fonte | Uso |
|---|---|
| `Terraplanagem AEIs R02.xml` (LandXML) | terreno final do plato: TIN exato (646 pontos, 1.857,7 m², cotas 724,37–731,80) |
| DWG – curvas `T-HM-CURVA_*` | terreno final do entorno (vias, quadras, lotes já modelados) |
| DWG – perfis `F-VT-TERRENO` dos cortes AA', BB', CC', DD' e do passeio da Rua C | terreno natural sob o plato |
| DWG – `A-MODELAGEM` (SOLIDs cor 11 = corte, 161 = aterro) | mancha de corte/aterro do projeto (usada para recortar e conferir) |
| DWG – `URB-Quadras`, `URB-Calçadas` | vias, calçadas (2,49 m) e quadras |

A superfície do Civil 3D não é legível fora do Civil 3D, por isso o terreno final do
plato vem do LandXML. O terreno natural dentro da área modelada foi reconstruído
com as curvas de fora da mancha `A-MODELAGEM` e os perfis de terreno natural das
seções. O sinal do corte/aterro calculado bate com a mancha do projeto em 94 %
(corte) e 96 % (aterro) da área.

Volumes estimados no plato: **corte ≈ 2.207 m³, aterro ≈ 180 m³**. Corte máximo de
cerca de 3,5 m e aterro máximo de cerca de 2,0 m. São estimativas; o valor oficial é
o relatório de volumes do Civil 3D.

## Como reproduzir
Requisitos: LibreDWG (`dwg2dxf`), Python 3.11 com `ezdxf shapely scipy numpy pillow`
e `bpy==4.2.0` (Blender como módulo, com OpenImageDenoise).
```
dwg2dxf -y -o terr.dxf "dados/Terraplanagem AEIs R02-Model(AutoCAD).dwg"
python3 scripts/tools/fix_dxf.py terr.dxf terr_fixed.dxf
python3 scripts/terraplenagem/prep_dem.py terr_fixed.dxf "dados/Terraplanagem AEIs R02.xml" dem.npz
python3 scripts/terraplenagem/build_render.py -- dem.npz bruto.png 1920 1080 192 ruab
python3 scripts/terraplenagem/legenda.py bruto.png dem.npz plato_rua_b.png
# vista conceitual do pedestre
python3 scripts/terraplenagem/build_render.py -- dem.npz calc.png 1920 1080 160 calcada conceitual
python3 scripts/terraplenagem/legenda.py calc.png dem.npz plato_rua_b_calcada_conceitual.png conceitual
```
Outras vistas em `build_render.py`: `ruab_ped` (pedestre na Rua B), `ruab_lat`,
`ruab_nw` e `topo` (planta, para conferência).

Materiais 100 % procedurais: latossolo vermelho no solo exposto, grama, asfalto e
concreto. Céu físico (Nishita) e sol da manhã vindo de nordeste. A vegetação de
fundo é ilustrativa (fora do loteamento).
