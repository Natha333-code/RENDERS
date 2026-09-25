# Renders – Parque Linear / Praça · Loteamento Reserva das Araucárias (Passo Fundo/RS)

Imagens realistas geradas a partir do projeto **PAL-RRA-URB-R10.dwg** e do
**Memorial Descritivo – Área de Lazer (09/09/26)**. A cena 3D é montada
automaticamente a partir da geometria do DWG (sem redesenho manual), então
posições, dimensões e quantidades seguem o projeto.

## Resultado
`renders_4k/` – versão atual, 3840×2160 (4K), com pessoas e bicicletas.
`renders/` – primeira versão, 1920×1080.

Revisão 2: piso tátil corrigido (placas sobrepostas no DWG causavam mancha
preta), nova câmera do Espaço Pet (sem galhos na frente), vistas aéreas mais
fechadas na praça (nova `aerea_oeste`), pessoas e bicicletas.

Pessoas: recortes fotográficos de **Skalgubbar** (www.skalgubbar.se), de uso
livre em visualizações de arquitetura. Bicicletas estacionadas: modelo 3D.

| Arquivo | Vista |
|---|---|
| aerea_geral.png | Vista aérea (drone) do lado oeste: Espaço Pet, quadra, estar, Food Parque |
| aerea_oeste.png | Vista aérea do extremo oeste: Espaço Pet, quadra, estar |
| aerea_leste.png | Vista aérea do lado leste: Garden, estar, Espaço Kids |
| aerea_food.png | Food Parque visto do alto: paginação claro/escuro, palco, totem |
| food_parque.png | Food Parque: bancos quadrados em alvenaria + jatobá com jerivás, palco |
| palco_totem.png | Totem do empreendimento com canteiro de moreias, vindo da Av. H |
| estar_ipe.png | Estar circular com ipê-amarelo, grelha, bancos e bela-emílias |
| quadra_areia.png | Quadra de areia 21×11 m cercada, refletores LED, piso tátil |
| espaco_kids.png | Espaço Kids: areia, playground, cerca Gradil 2,00 m, manacás |
| espaco_pet.png | Espaço Pet: brinquedos, bebedouros, cerca Gradil |
| caminho_garden.png | Passeio em paver, Espaço Garden (paletes), ciclovia |
| vista_ciclovia.png | Ciclovia bidirecional em concreto vermelho (2,80 m) |
| vista_trilha.png | Trilha de pedrisco na Área de Espaços Livres (mata com araucárias) |

## Fidelidade ao projeto
Extraído diretamente do DWG (cópia usada na prancha "folha A-2"):
- contorno do canteiro central (129,5 + 55,5 + 119,5 m), ciclovia com recuos
  dos bicicletários e rampas de 5 % nas travessias, faixas elevadas em paver
  com zebrado e triângulos;
- caminhos sinuosos em paver holandês espinha-de-peixe, estares circulares,
  piso tátil (597 placas; direcional/alerta), quadra 21×11 m, palco 10×12 m
  (+20 cm), 6 bancos perimetrais quadrados, arquibancadas, totem, canteiros;
- Food Parque com faixas alternadas de paver claro/escuro de 0,50 m (linhas do DWG);
- perfil longitudinal pelas cotas de piso (COTAPISO): 621,15 → 612,15 m;
- vegetação na posição exata de cada bloco, com as quantidades do memorial:
  50 jerivás, 52 quaresmeiras, 52 extremosas brancas, 29 moreias,
  108 bela-emílias, 4 manacás-da-serra, 2 ipês-amarelos, 1 jabuticabeira,
  além das araucárias existentes (bloco p1);
- mobiliário na posição do DWG: 16 bancos (padrão Prefeitura de Passo Fundo),
  17 lixeiras, 3 bicicletários (4 vagas), grelhas, bebedouros pet, playground,
  brinquedos pet, 12 módulos de paletes;
- sol: tarde de primavera, orientado pela rosa-dos-ventos do memorial.

Interpretações (não definidas em projeto): alturas do totem (1,20 m) e do
alambrado da quadra (3,0 m), cor do "concreto pintado" do palco (terracota),
modelo exato do playground e dos brinquedos pet (seguem as referências do
memorial), entorno com lotes vazios (loteamento em execução).

## Como reproduzir
Requisitos: LibreDWG (`dwg2dxf`), Python 3 com `ezdxf shapely pillow numpy`,
Blender 4.2 (com `shapely` no Python do Blender), texturas ambientCG e modelos
Poly Haven em `/home/user/assets` (ver `scripts/lib_*`).
```
dwg2dxf -y -o projeto.dxf PAL-RRA-URB-R10.dwg
python3 scripts/tools/fix_dxf.py projeto.dxf fixed.dxf
python3 scripts/tools/extract_dxf.py            # -> ents.json (usa fixed.dxf)
python3 scripts/tools/objs_dxf.py fixed.dxf ents.json objs.json
python3 scripts/prep_scene.py ents.json objs.json dados/scene.json
python3 scripts/gen_textures.py /home/user/assets/tex/gen
blender -b --python scripts/build_scene.py -- dados/scene.json praca.blend
blender -b praca.blend --python scripts/render.py -- renders aerea_geral,food_parque 1920 64
```
