# Condomínio – maquete eletrônica (terreno natural)

Maquete do loteamento a partir de `PT_TJ_TER_R02-ModelAutoCAD.dwg` (curvas de nível, perímetro,
quadras, lotes e meio-fio), sem edificações nos lotes.

## Georreferência e escala
- O DWG está em UTM 22S, SIRGAS 2000 (EPSG:31982), escala 1:1. Conferido com o KML `KMZ_TJ`
  (os cantos dos lotes coincidem com diferença de cerca de 3 m).
- Origem local da cena: E 383400, N 6852450.
- A imagem aérea foi calibrada pelas ruas do OpenStreetMap: 1,322 m/px, sem rotação.

## Etapas (`scripts/`)
1. `dwg2dxf` (LibreDWG) → `extract_geo.py`: polilinhas por layer, com cota.
2. `make_dem.py`: MDT de 1 m interpolado das curvas.
3. `prep_terrain.py`: núcleo de 1 m e entorno de 8 m e 100 m, sintético fora do levantamento.
4. `prep_vias.py`: pista, passeio, meio-fio e canteiros, com o greide ajustado sob as vias.
5. `prep_cobertura.py imagem.png dados`: classes mata, campo, lavoura e urbano a partir da
   imagem aérea; árvores da mata; casas; prédios e ruas do OSM.
6. `build_terreno.py` (Blender 4.2, Cycles) → `render.py`.

```bash
blender -b --python scripts/build_terreno.py -- dados cena.blend
```

```bash
blender -b cena.blend --python scripts/render.py -- renders planta,drone_alto 1920 64
```

## Materiais
- Pista: paver intertravado cinza-escuro, em espinha-de-peixe.
- Passeio: paver de concreto claro.
- Meio-fio: concreto, com 15 cm de altura.
- Lotes e clareira: campo nativo (grama 3D nas vistas ao nível do olho).

## Limitações
- Fora de cerca de 450 m do terreno, o relevo, as lavouras e os capões são ilustrativos.
- A mata foi retirada só sobre as vias projetadas, com folga de 4 m.

## Fontes
- Prédios e ruas do entorno: © colaboradores do OpenStreetMap (ODbL), em `dados/osm_local.json`.
- A imagem aérea fornecida pelo cliente não está no repositório; só a classificação
  `dados/cobertura.png` está.

## Vistas (`renders/`)
`_contato.jpg` reúne todas as vistas: planta, drone_alto, aerea_vias, aerea_sudeste,
aerea_sudoeste, aerea_norte, aerea_leste, drone_leste, rua_acesso, rua_quadras, acesso_norte
e clareira_topo.

## Maquete interativa (`web/`)
Visualizador three.js com os modos caminhar, voar e orbitar, os mesmos pontos de vista dos
renders, camadas (lotes, mata, bairros, sombras) e minimapa.
1. Gerar as texturas do chão, os sprites das árvores e o céu:
   ```bash
   blender -b cena.blend --python scripts/web/bake_web.py -- dados web/dados
   ```
2. Gerar a geometria (terreno, vias, edificações, linhas). Os binários saem em base64 (`.txt`):
   ```bash
   python3 scripts/web/export_web.py dados web/dados
   ```
3. Abrir `web/index.html` por um servidor local, por exemplo `python3 -m http.server` dentro de `web/`.
