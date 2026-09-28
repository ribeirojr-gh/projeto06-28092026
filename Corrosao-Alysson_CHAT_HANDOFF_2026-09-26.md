# Corrosão–Alysson — Handoff completo do chat

**Data de consolidação:** 2026-09-26  
**Uso:** iniciar um novo chat sem perder o estado técnico, as decisões, as instruções e o histórico do projeto.

> Este é um handoff estruturado reconstruído a partir do conteúdo visível do chat e dos arquivos/resultados efetivamente enviados. Não inclui instruções internas da plataforma, raciocínio privado ou chaves secretas.

## 1. Escopo científico

Projeto de modelagem computacional de proteção contra corrosão de **aço carbono ABNT 1020 em NaCl 3,5 wt%**, no contexto de revestimentos epóxi, sílica, microcápsulas de cério, óleos e 8-hidroxiquinolina (8-HQ).

Interpretação mecanística usada até aqui:
- barreira do revestimento;
- tortuosidade;
- precipitação/passivação por espécies de Ce;
- contribuição orgânica/selagem;
- inibição química.

O objetivo computacional é construir um baseline reprodutível de α-Fe, convergir SIESTA/ASE no bulk e só depois avançar para Fe(110), espécies corrosivas/passivantes e modelos de coating/inibidor.

## 2. Regras obrigatórias do workflow

1. **Anti-invenção:** não inventar IDs do Materials Project, estruturas, resultados, pseudos ou dados experimentais.
2. **Proveniência estrutural obrigatória.**
3. **Um script por gate:** preparar uma etapa, executar localmente, receber outputs, auditar e só então liberar a seguinte.
4. **Execução local:** não usar GitHub Actions para simulações.
5. Cada etapa deve ter `run.sh`, README e outputs auditáveis.
6. SCF convergido não implica parâmetros numericamente convergidos.
7. Bulk convergido não implica slab convergido.
8. Fe deve ser tratado com spin; magnetismo precisa ser verificado.
9. Pseudopotenciais devem ter família, XC, relatividade, valência e hash registrados.
10. Não comparar energias absolutas entre famílias de pseudo diferentes.
11. Não reconstruir dados experimentais brutos inexistentes.
12. `MP_API_KEY` pode ser usada localmente, mas nunca deve ser exposta ou commitada.
13. Não avançar para Fe(110) de produção antes de fechar bulk: cutoff/grid real, k-points, base e lattice/stress.
14. Não descartar alterações locais automaticamente; verificar `git status --short`.

## 3. Infraestrutura local

Diretório:
```text
~/SIMULACOES/corrosao
```

GitHub privado:
```text
ribeirojr-gh/corrosao
```

Preferências:
- Git/gh via HTTPS;
- execução local;
- sem GitHub Actions.

Hardware auditado:
- Linux;
- 32 CPUs lógicas;
- ~31.03 GiB RAM;
- NVIDIA RTX 4070 Laptop GPU, 8188 MiB;
- Python 3.12.3.

Software:
- SIESTA 5.4.2: `/usr/local/bin/siesta`
- ASE 3.29.0
- GPAW 25.7.0
- Open MPI 4.1.6
- `mpirun`: `/usr/bin/mpirun`
- pymatgen 2026.5.4
- NumPy 2.4.4
- SciPy 1.18.0
- mpi4py 3.1.5

Threads:
```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
```

## 4. Material experimental revisado

No início do projeto foram revisados:
```text
Projeto Corrosão UnB.PDF
reunião acompanhamento 1109.pptx
```

Eles serviram de base experimental/mecanística. Não foram encontrados dados brutos completos suficientes para reconstruir curvas EIS ou outras séries numéricas.

## 5. α-Fe de referência

Materials Project:
```text
mp-13
```

Estrutura validada:
- α-Fe bcc;
- célula convencional cúbica, 2 átomos;
- `a = 2.863035498949916 Å`;
- `Im-3m (#229)`;
- 0 eV/atom acima do hull.

Nuance:
- estrutura bruta MP: `Fmmm` a `symprec=0.001 Å`;
- recupera `Im-3m` a `0.1 Å`;
- célula padronizada convencional passa como `Im-3m`.

Arquivos:
```text
outputs/POSCAR_Fe_bulk
outputs/Fe_bulk_metadata.json
```

## 6. Step 02 — modelos estruturais

Branch:
```text
step-02-structural-models
```

Script:
```text
scripts/02_build_fe_surfaces.py
```

Foram gerados 18 slabs geométricos:
- Fe(110), Fe(100), Fe(111);
- `layers = 7, 9, 11`;
- `vacuum = 15, 20 Å`.

Todos passaram nos checks geométricos.

Nuance crítica do ASE:
- Fe(110): planos físicos detectados ~ layers solicitado;
- Fe(100) e Fe(111): ~2× mais planos físicos que o parâmetro `layers`.

Exemplos de espessuras:
- Fe(110) L7 ~12.147 Å;
- Fe(110) L9 ~16.196 Å;
- Fe(110) L11 ~20.245 Å;
- Fe(100) L7 ~18.610 Å;
- Fe(111) L7 ~10.744 Å.

Comparações entre orientações devem usar espessura física / planos detectados, não apenas `layers`.

Superfície primária:
```text
Fe(110)
```

Nenhum slab foi considerado DFT-convergido.

## 7. Step 03 — DFT baseline

Branch:
```text
step-03-dft-baseline
```

Objetivo:
1. auditar ambiente;
2. validar SIESTA/ASE/pseudos;
3. executar α-Fe bulk;
4. convergir grid/cutoff, k-points, base, lattice/stress;
5. só depois Fe(110).

## 8. SIESTA + ASE

O usuário perguntou se SIESTA poderia ser usado “dentro” do ASE.

Decisão:
- ASE atua como orquestrador/calculator;
- SIESTA permanece executável externo;
- ASE gera FDF, chama SIESTA e lê resultados.

Comando utilizado:
```text
mpirun -np 2 /usr/local/bin/siesta < PREFIX.fdf > PREFIX.out
```

## 9. Pseudopotenciais

Pasta real:
```text
~/Pacotes/PSEUDOS/DOJO-PSML
```

Família em uso:
- PSML;
- ONCVPSP/PseudoDojo;
- PBE;
- scalar-relativistic.

Elementos relevantes já presentes incluem H, C, N, O, Na, Si, Cl, Fe, P, S.

**Ce ainda não foi aprovado/validado.**

### Fe.psml
- PSML 1.1;
- ONCVPSP 3.3;
- PBE;
- scalar-relativistic;
- core corrections;
- 16 elétrons de valência;
- `3s2 3p6 3d6 4s2`;
- semicore 3s/3p.

SHA256:
```text
6b540d480fbdf34ef2058028ed6a6d47fc818f9ead7ea31e496720420ab44e12
```

### O.psml
- PSML 1.1;
- ONCVPSP 3.3;
- PBE;
- scalar-relativistic;
- core corrections;
- 6 elétrons de valência;
- `2s2 2p4`.

SHA256:
```text
224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e
```

## 10. Preflight SIESTA/ASE/PSML

Script:
```text
scripts/04_audit_siesta_pseudos.py
```

Arquivos devolvidos pelo usuário:
```text
siesta_preflight.json
siesta_preflight.txt
```

Resultado:
```text
SIESTA /usr/local/bin/siesta, v5.4.2
mpirun /usr/bin/mpirun
ASE 3.29.0
Preflight PASSED
issues = []
```

Limites:
- não prova transferibilidade;
- não prova convergência numérica;
- não prova estado magnético final.

## 11. Primeiro piloto α-Fe bulk

Script:
```text
scripts/05_siesta_fe_bulk_pilot.py
```

Parâmetros:
```text
mp-13
2 Fe
PBE
DZP
MeshCutoff 250 Ry
PAO EnergyShift 0.02 Ry
k = 6x6x6
spin collinear
initial moments +2.2 μB/Fe
ElectronicTemperature 300 K
SCF.DM.Tolerance 1e-4
MaxSCFIterations 120
DM.MixingWeight 0.05
MPI ranks 2
cell/positions fixed
```

Run:
```text
20260923T154129_596106Z
```

Arquivo nativo:
```text
/home/luiz/SIMULACOES/corrosao/outputs/dft/fe_bulk_siesta_pilot/20260923T154129_596106Z/Fe_bulk_pilot.out
```

Resultados:
```text
Ecell = -6888.008116 eV
E/Fe  = -3444.004058 eV
SCF = 60 iterações
max |DM_out-DM_in| = 1.30807e-5
max |H_out-H_in| = 9.684788e-4 eV
spin total = 4.57220 μB/cell
~2.28610 μB/Fe
Pstatic = -105.61670162 kbar
V = 23.468223 Å³
```

Gate:
- ASE–SIESTA execution: PASS;
- SCF: PASS;
- PSML: PASS;
- numerical convergence: NOT PASSED;
- lattice/stress: NOT PASSED.

## 12. MeshCutoff 250–550 Ry

Script:
```text
scripts/06_fe_bulk_mesh_cutoff_screen.py
```

Mantidos fixos:
- geometry;
- pseudo;
- PBE/DZP;
- EnergyShift 0.02 Ry;
- 6³ k-grid;
- 300 K;
- +2.2 μB/Fe;
- MPI 2.

Resultados:

| Ry | E (eV/Fe) | ΔE vs 550 (meV/Fe) | M (μB/Fe) | SCF | P (kbar) |
|---:|---:|---:|---:|---:|---:|
| 250 | -3444.0040580 | -0.3415 | 2.286100 | 60 | -105.62 |
| 350 | -3444.0027895 | +0.9270 | 2.286045 | 59 | -94.81 |
| 450 | -3444.0042215 | -0.5050 | 2.286020 | 60 | -95.84 |
| 550 | -3444.0037165 | 0 | 2.286015 | 59 | -94.43 |

Energia não monotônica.  
Amplitude ~1.432 meV/Fe.  
Momento muito estável.

Decisão:
```text
550 Ry NÃO declarado convergido.
```

## 13. Extensão 550–850 Ry

Script:
```text
scripts/07_fe_bulk_mesh_cutoff_extension.py
```

Resultados iniciais:
```text
550: E=-3444.00371650, M=2.286015, P=-94.4344
650: E=-3444.00371650, M=2.286015, P=-94.4344
750: E=-3444.00371650, M=2.286015, P=-94.4344
850: E=-3444.00360100, M=2.286010, P=-99.4162
```

O 550 Ry repetiu exatamente o cálculo anterior.

Como 550/650/750 eram idênticos, o workflow foi pausado e foram solicitados os FDF/OUT nativos.

## 14. Diagnóstico nativo do SIESTA

Arquivo enviado:
```text
fe_mesh_extension_diagnostics.tar.gz
```

Diagnóstico:
- 550 Ry -> FFT 48×48×48; cutoff usado 776.839 Ry
- 650 Ry -> FFT 48×48×48; cutoff usado 776.839 Ry
- 750 Ry -> FFT 48×48×48; cutoff usado 776.839 Ry
- 850 Ry -> FFT 54×54×54; cutoff usado 983.187 Ry

Conclusão:
> SIESTA quantizou pedidos diferentes para a mesma grid real. O keyword MeshCutoff não estava sendo ignorado.

## 15. Screening por grids FFT realmente distintas

Script:
```text
scripts/08_fe_bulk_realized_grid_screen.py
```

Pedidos:
```text
850, 1000, 1250, 1500 Ry
```

Arquivos do usuário:
```text
fe_bulk_realized_grid_summary.json
fe_bulk_realized_grid_report.txt
08_fe_bulk_realized_grid.log
```

Run:
```text
20260923T181410_514058Z
```

Todos os quatro:
```text
SCF converged
4 grids FFT distintas
```

Resultados:

| Pedido | FFT real | usado (Ry) | E (eV/Fe) | ΔE vs 1500 meV/Fe | M μB/Fe | P kbar |
|---:|:---:|---:|---:|---:|---:|---:|
| 850 | 54³ | 983.187 | -3444.0036010 | -0.4235 | 2.286010 | -99.416 |
| 1000 | 60³ | 1213.811 | -3444.0033855 | -0.2080 | 2.286005 | -101.969 |
| 1250 | 64³ | 1381.047 | -3444.0031125 | +0.0650 | 2.286000 | -94.695 |
| 1500 | 72³ | 1747.888 | -3444.0031775 | 0 | 2.285995 | -99.379 |

850 Ry repeat anchor:
```text
dE = 0
dM = 0
dP = 0
```

Span:
```text
energia: 0.4885 meV/Fe
momento: 0.000015 μB/Fe
pressão: ~7.2747 kbar
```

Decisão:
- energia e magnetização: muito estáveis;
- stress: ainda não estável;
- 1500 Ry pode ser usado **provisoriamente para o screening de k-points**;
- não é cutoff de produção;
- não liberar lattice/slab ainda.

## 16. Gate atual: k-point screening

Script já criado:
```text
scripts/09_fe_bulk_kpoint_screen.py
```

Grids:
```text
6x6x6
8x8x8
10x10x10
12x12x12
14x14x14
```

Fixos:
```text
mp-13 / POSCAR_Fe_bulk
Fe.psml hash aprovado
PBE
DZP
PAO EnergyShift 0.02 Ry
MeshCutoff pedido 1500 Ry
FFT esperada 72x72x72
ElectronicTemperature 300 K
spin collinear
initial +2.2 μB/Fe
SCF tolerance 1e-4
MaxSCF 120
MPI 2
OMP/BLAS 1 thread
```

O script verifica:
- `kgrid_Monkhorst_Pack` no FDF;
- cutoff nativo;
- FFT nativa;
- FFT constante durante o scan;
- SCF;
- energia;
- momento;
- pressão;
- 6³ como repeat anchor contra o cálculo anterior em 1500 Ry.

Outputs esperados:
```text
outputs/fe_bulk_kpoint_summary.json
outputs/fe_bulk_kpoint_report.txt
logs/09_fe_bulk_kpoint_screen.log
```

Comando atual:
```bash
cd ~/SIMULACOES/corrosao

git status --short
git fetch origin
git switch step-03-dft-baseline
git pull --ff-only origin step-03-dft-baseline

SIESTA_PS_PATH="$HOME/Pacotes/PSEUDOS/DOJO-PSML" bash run.sh
```

Se `git status --short` mostrar alterações locais:
> revisar antes; não descartar automaticamente.

## 17. Próximos gates após k-points

1. **k-points**
   - energia;
   - magnetização;
   - pressão;
   - SCF;
   - FFT constante.

2. **base PAO**
   - DZP atual;
   - EnergyShift;
   - possível TZP/TZDP;
   - qualidade para superfícies/adsorção;
   - efeito sobre stress.

3. **lattice α-Fe**
   - só depois de k/base;
   - reavaliar cutoff com parâmetros finais;
   - tratar Pulay/grid stress;
   - curva E(a) / otimização;
   - magnetização vs a;
   - stress residual.

4. **Fe(110)**
   - espessura;
   - planos físicos;
   - vácuo;
   - k-grid 2D;
   - relaxação;
   - magnetismo por camada;
   - energia de superfície.

5. **química interfacial**
   - O/OH/H2O;
   - Cl/NaCl;
   - Ce;
   - sílica/coating;
   - 8-HQ/orgânicos;
   - defeitos/óxidos/passivação.

## 18. Ce: pendência

Ainda não há `Ce.psml` aprovado.

Quando chegar essa etapa:
- PBE/scalar-relativistic/PSML compatível;
- validar valência e 4f;
- considerar DFT+U para Ce(III)/Ce(IV), CeO2/Ce2O3;
- registrar hash;
- não misturar arbitrariamente famílias de pseudo.

## 19. GPAW

Instalado:
```text
/home/luiz/.local/bin/gpaw
```

Decisão atual:
- SIESTA = backend principal;
- GPAW = possível cross-check independente em casos selecionados.

## 20. Arquivos GitHub principais

Scripts:
```text
scripts/01_fetch_fe_bulk.py
scripts/02_build_fe_surfaces.py
scripts/03_check_dft_environment.py
scripts/04_audit_siesta_pseudos.py
scripts/05_siesta_fe_bulk_pilot.py
scripts/06_fe_bulk_mesh_cutoff_screen.py
scripts/07_fe_bulk_mesh_cutoff_extension.py
scripts/08_fe_bulk_realized_grid_screen.py
scripts/09_fe_bulk_kpoint_screen.py
```

Docs:
```text
docs/03_dft_environment_review_2026-09-23.md
docs/04_siesta_preflight_review_2026-09-23.md
docs/05_fe_bulk_pilot_review_2026-09-23.md
docs/06_mesh_cutoff_initial_review_2026-09-23.md
docs/07_mesh_cutoff_extension_review_hold_2026-09-23.md
docs/08_native_mesh_diagnostics_review_2026-09-23.md
docs/09_realized_grid_review_2026-09-23.md
```

Runner:
```text
run.sh
```

## 21. Commits explicitamente registrados neste chat

```text
f76beab7438239132ce7cbe227fb4acabd391b57  docs/03...
c2a8e6e213d465e4d272361b40c1cf54312143dc  script 04
4c215276354afd1b1519c1a08d540567686e4487  run.sh preflight
3931da9c17f98688eba060cdeb69c3ca5167bb61  README preflight
cbe1e78edd047c0f2aa7a2f89f8c79e5649491ec  script 05
e25b39e43700db908330f9be0a1429ba94776dc7  run.sh pilot
973124d25d1f358cb8d3be316a736f4a16fc366e  README pilot
5d81ef76c0702e82b1fd8a2ae57f8e5b00a0f9f8  docs/04
d8b35d52ebe0772ccfc1177616ef602048513955  docs/05
072ab899d7f8596105c8e9cdb0e1010e6d167ddd  script 06
999379bf3cc4ee403b3e32592e37063489b81475  run.sh cutoff 250–550
0997b9f811cb2b0172d40c640e4ca86dd29b90f2  README cutoff
801dbc084cdcb4d8e8d9adde81babdcc68136979  docs/06
a470b6b611d19fc8f9c50d6160b28d56dfcca1bd  script 07
326fb2af8829c872b5102852eaf7b6fca820e7d6  run.sh extension
ff88341d06eacb5fecb7d366495b50655df739ac  README extension
26de0b3efb794f5d04b26abbbd421d264ad81ab7  docs/07
bd476a1b9ea59c561019d6845b0ce453eacd960e  docs/08
10d14515724797c9bf45a37aa2dc384d6bfe9764  script 08
8af6d3b88fd94c1f3c39b4fce00c512615896910  run.sh realized-grid
12228604a13303b58e2638fb76d4d58f64ac1dab  README realized-grid
7b96635b947a82df152890fb3a442b5ab8efaa0b  docs/09
cd0efd0ff7053068d648468abd88ca817d4e2b05  script 09
e7c844cd27117bb21b55e6dc69e6e65fa104496d  run.sh k-points
394b1ca4ef32a8629b80c6e6a3364767219ad87f  README k-points
```

## 22. Arquivos enviados pelo usuário durante este segmento

Pseudos/instalação:
```text
screenshots da instalação do SIESTA e diretório de pseudos
head-fe
head-o
```

Preflight:
```text
siesta_preflight.json
siesta_preflight.txt
```

Pilot:
```text
fe_bulk_siesta_pilot_summary.json
05_siesta_fe_bulk_pilot.log
Fe_bulk_pilot.out
```

Cutoff 250–550:
```text
fe_bulk_mesh_cutoff_summary.json
fe_bulk_mesh_cutoff_report.txt
06_fe_bulk_mesh_cutoff.log
```

Extensão:
```text
07_fe_bulk_mesh_cutoff_extension.log
fe_bulk_mesh_cutoff_extension_summary.csv
fe_bulk_mesh_cutoff_report(1).txt
```

Nota: `fe_bulk_mesh_cutoff_report(1).txt` era o report anterior, não o report correto da extensão.

Diagnóstico nativo:
```text
fe_mesh_extension_diagnostics.tar.gz
```

Realized-grid:
```text
fe_bulk_realized_grid_summary.json
fe_bulk_realized_grid_report.txt
08_fe_bulk_realized_grid.log
```

## 23. O que NÃO fazer no novo chat

- não reiniciar do zero;
- não trocar `mp-13` sem razão;
- não trocar `Fe.psml` sem reauditar hash e repetir gates;
- não dizer que 1500 Ry é cutoff final;
- não interpretar pressão atual como lattice físico;
- não iniciar slab ainda;
- não rodar vários gates de uma vez;
- não usar GitHub Actions;
- não expor `MP_API_KEY`;
- não misturar energia absoluta entre pseudos;
- não assumir que `layers` ASE = planos físicos para todas as orientações.

## 24. Instrução de continuidade para o próximo chat

O novo chat deve continuar **do gate de k-points**.

Se o usuário ainda não executou:
> executar `run.sh` no branch `step-03-dft-baseline` e enviar os três outputs do k-point screening.

Se já executou:
1. analisar `fe_bulk_kpoint_summary.json`;
2. analisar o TXT e log;
3. confirmar repeat anchor 6³;
4. confirmar FFT 72³ em todos os cálculos;
5. calcular diferenças vs 14³;
6. decidir, por critério explícito, se precisa 16³/18³ ou se pode fixar k provisório;
7. documentar o gate no GitHub;
8. preparar **somente a etapa seguinte**.

## 25. Resumo executivo

**Estado atual:** SIESTA 5.4.2 + ASE 3.29.0 + Fe PBE ONCVPSP/PSML semicore validados; α-Fe `mp-13` executa e converge SCF; grid real foi testado até 72³ / pedido 1500 Ry, com energia e momento muito estáveis, mas stress ainda não convergido. O próximo gate, já implementado no GitHub, é k-point screening 6³→14³ via `scripts/09_fe_bulk_kpoint_screen.py`. Ainda não avançar para lattice ou Fe(110).

## 26. Prompt recomendado para abrir o próximo chat

> Este documento contém o histórico consolidado do projeto Corrosão–Alysson. Leia-o integralmente e assuma o projeto exatamente do estado descrito. Mantenha o protocolo de um script por gate, execução local, auditoria dos outputs antes da próxima etapa, anti-invenção e proveniência completa. O gate atual é o k-point screening do α-Fe bulk no branch `step-03-dft-baseline`.
