# Step 04 — Fe(110) Surface Models, Surface Energy & Inhibitor Adsorption

## 1. Overview & Scientific Goals

Step 04 builds upon the fully converged and audited $\alpha$-Fe bulk baseline (Step 03) and the geometric slab candidate library (Step 02) to simulate:
1. **Clean $\text{Fe}(110)$ surface electronic structure and relaxation**:
   - Determine the relaxed surface energy $\gamma_{(110)}$, interlayer relaxations ($\Delta d_{12}/d_0$), surface work function ($\Phi$), and layer-resolved magnetization profile ($M(z)$).
   - Establish slab-thickness convergence (7, 9, 11 atomic layers with $15\text{--}20\text{ \AA}$ vacuum).
2. **Inhibitor (8-Hydroxyquinoline, 8-HQ) molecular modeling**:
   - Construct and optimize the 3D structure of 8-HQ ($\text{C}_9\text{H}_7\text{NO}$) in neutral and deprotonated/chelated forms.
3. **MACE GPU-accelerated Screening of Adsorption Geometries**:
   - Use the MACE foundational interatomic potential (MACE-MP-0 / MACE-OFF23) accelerated by the NVIDIA RTX 5070 Laptop GPU to pre-relax and screen flat vs. vertical/chelated adsorption configurations on large $(3\times 3)$ and $(4\times 4)$ $\text{Fe}(110)$ supercells.
4. **SIESTA DFT Refinement & Electronic Passivation Mechanism**:
   - Compute high-accuracy adsorption energy ($E_\mathrm{ads}$), charge transfer ($\Delta q$), charge-density difference ($\Delta \rho$), and Projected Density of States (PDOS) to elucidate the chemical inhibition mechanism of steel in chloride environments.

---

## 2. Methodology & Computational Parameters

- **Substrate:** $\alpha$-Fe(110) oriented slab from validated bulk ($a_0 = 2.804\text{ \AA}$ / $a_\mathrm{ref} = 2.863\text{ \AA}$).
- **Exchange-Correlation:** PBE (GGA) with spin polarization (ferromagnetic).
- **Pseudopotentials:** `DOJO-PSML` ONCVPSP 3.3 scalar-relativistic (Fe semicore $3s/3p$ 16 valence electrons; H, C, N, O).
- **Basis Set:** DZP with polarization orbitals, `PAO.EnergyShift = 0.020 Ry`.
- **2D k-point Grid:** $12\times 12\times 1$ for $(1\times 1)$ surface unit cell ($k \cdot a \approx 48\text{ \AA}$ density); $4\times 4\times 1$ for $(3\times 3)$ supercell.
- **Real-Space Grid:** Commensurate with $1500\text{ Ry}$ MeshCutoff.
- **GPU MLIP Engine:** MACE (PyTorch + CUDA on RTX 5070) via ASE interface.

---

## 3. Tasks & Gate Sequence

- **Gate 01:** Relaxation of clean $\text{Fe}(110)$ slabs (7, 9, 11 layers), calculation of $\gamma_{(110)}$, work function, and surface spin enhancement.
- **Gate 02:** Isolated 8-HQ molecule conformer optimization (MACE + DFT reference).
- **Gate 03:** MACE GPU screening of 8-HQ adsorption modes on $\text{Fe}(110)$.
- **Gate 04:** DFT/SIESTA self-consistent electronic structure, adsorption energies, charge transfer, and PDOS.
- **Gate 05:** Co-adsorption with water and chloride ($\text{Cl}^-$) to quantify the displacement and competitive adsorption barrier.
