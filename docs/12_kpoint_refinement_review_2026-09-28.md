# 12 — Review of Gate 10A: alpha-Fe bulk k-point refinement 14³–20³ (2026-09-28)

**Date:** 2026-09-28  
**Repository:** `ribeirojr-gh/projeto06-28092026`  
**Branch:** `step-03-dft-baseline`  
**Script:** `scripts/10_fe_bulk_kpoint_refinement.py`  
**Execution:** `SIESTA_MPI_RANKS=4 PYTHON_BIN=.venv-step02/bin/python bash run.sh` (Exit 0)  
**Wrapper log:** `logs/10_fe_bulk_kpoint_refinement.log`

---

## 1. Context & Objective

In Gate 09 (`scripts/09_fe_bulk_kpoint_screen.py`, run `20260927T184249_729844Z`), k-point sampling across $6^3 \to 14^3$ demonstrated that magnetic moment ($M \approx 2.25\ \mu_\mathrm{B}/\text{Fe}$) and static pressure ($P \approx -107.9\text{ kbar}$) stabilized for $k \ge 10^3$, but total energy exhibited an odd/even oscillation of $\sim 1.33\text{ meV/Fe}$ across $10^3 \to 14^3$, leaving numerical energy convergence at $300\text{ K}$ unresolved against the strict $\le 1.0\text{ meV/Fe}$ threshold.

Gate 10A tested denser Monkhorst–Pack sampling ($14^3, 16^3, 18^3, 20^3$) under identical, single-variable numerical conditions:
- alpha-Fe conventional cubic cell (`mp-13`, 2 Fe atoms, $a = 2.8630355\text{ \AA}$, unrelaxed);
- Approved `Fe.psml` (PseudoDojo/ONCVPSP 3.3, PBE, scalar-relativistic, semicore $3s/3p$, 16 valence electrons, SHA-256: `6b540d480fbdf34ef2058028ed6a6d47fc818f9ead7ea31e496720420ab44e12`);
- PBE functional, DZP basis, `PAO.EnergyShift = 0.02 Ry`;
- Requested `MeshCutoff = 1500 Ry` (realized $72\times 72\times 72$ FFT grid held constant across all points);
- Electronic temperature: $300\text{ K}$ (Fermi–Dirac);
- Spin: collinear, initial moments $+2.2\ \mu_\mathrm{B}/\text{Fe}$;
- SCF criteria: `SCF.DM.Tolerance = 1.0e-4`, `MaxSCFIterations = 120`, `DM.MixingWeight = 0.05`;
- Parallelization: 4 MPI ranks, 1 OpenMP/BLAS thread per rank.

---

## 2. Anchor Reproducibility Verification

The $14^3$ calculation served as an internal repeat anchor against Gate 09:

| Quantity | Gate 09 ($14^3$) | Gate 10A ($14^3$) | Difference ($\Delta$) | Status |
| :--- | :---: | :---: | :---: | :---: |
| $E$ (eV/Fe) | $-3444.00893900$ | $-3444.00893900$ | $+0.0000\text{ meV/Fe}$ | **EXACT MATCH** |
| $M$ ($\mu_\mathrm{B}/\text{Fe}$) | $2.248840$ | $2.248840$ | $+0.000000\ \mu_\mathrm{B}/\text{Fe}$ | **EXACT MATCH** |
| $P$ (kbar) | $-107.919$ | $-107.919$ | $+0.0000\text{ kbar}$ | **EXACT MATCH** |
| SCF iterations | 65 | 65 | $0$ | **EXACT MATCH** |
| Realized FFT grid | $72\times 72\times 72$ | $72\times 72\times 72$ | identical | **EXACT MATCH** |

**Anchor Gate: PASSED.** Numerical consistency across successive scripts and MPI configurations is verified to all printed digits.

---

## 3. Results of the Refinement Series ($14^3 \to 20^3$)

| k-grid | Irreducible $k$ | $E$ (eV/Fe) | $\Delta E$ vs $20^3$ (meV/Fe) | $M$ ($\mu_\mathrm{B}/\text{Fe}$) | $\Delta M$ vs $20^3$ ($\mu_\mathrm{B}/\text{Fe}$) | $P$ (kbar) | $\Delta P$ vs $20^3$ (kbar) | SCF iter. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$14\times 14\times 14$** | 1484 | $-3444.0089390$ | $-1.1980$ | $2.248840$ | $-0.003950$ | $-107.919$ | $-1.025$ | 65 |
| **$16\times 16\times 16$** | 2176 | $-3444.0080535$ | $-0.3125$ | $2.252300$ | $-0.000490$ | $-107.562$ | $-0.668$ | 60 |
| **$18\times 18\times 18$** | 3060 | $-3444.0083140$ | $-0.5730$ | $2.254575$ | $+0.001785$ | $-106.932$ | $-0.038$ | 62 |
| **$20\times 20\times 20$** | 4160 | $-3444.0077410$ | $0.0000$ | $2.252790$ | $0.000000$ | $-106.894$ | $0.000$ | 39 |

---

## 4. Scientific Interpretation

1. **Energy Oscillation Damped Below $1.0\text{ meV/Fe}$**:
   - The total energy span across the dense range $16^3 \to 20^3$ is:
     $$\Delta E_\mathrm{span}(16^3\text{--}20^3) = |-3444.0077410 - (-3444.0083140)| = \mathbf{0.573\text{ meV/Fe}}$$
   - This value is strictly below the protocol tolerance limit of $\le 1.0\text{ meV/Fe}$.
   - The step differences are:
     - $E(16^3) - E(14^3) = +0.886\text{ meV/Fe}$
     - $E(18^3) - E(16^3) = -0.261\text{ meV/Fe}$
     - $E(20^3) - E(18^3) = +0.573\text{ meV/Fe}$
   - The odd/even Fermi-surface oscillations have damped from $\sim 5.8\text{ meV/Fe}$ (at $6^3$) down to $<0.6\text{ meV/Fe}$.

2. **Magnetic Moment Rigorously Converged**:
   - For $k \ge 16^3$, the spin moment varies within $\pm 0.0018\ \mu_\mathrm{B}/\text{Fe}$ ($2.2523 \to 2.2546 \to 2.2528\ \mu_\mathrm{B}/\text{Fe}$).
   - The magnetic ground state is completely stable.

3. **Pressure Plateauing**:
   - Between $18^3$ and $20^3$, static hydrostatic pressure changes by only **$0.038\text{ kbar}$** (from $-106.932$ to $-106.894\text{ kbar}$).
   - This confirms that $k$-sampling error in the stress tensor is reduced to negligible levels ($\ll 0.1\text{ kbar}$).

---

## 5. Gate Decision

**Gate 10A: PASSED.**
- Numerical k-point convergence for the conventional bulk cell of $\alpha$-Fe is formally established.
- For bulk calculations: **$16\times 16\times 16$** (or $18\times 18\times 18$) provides energy convergence to within $\sim 0.5\text{ meV/Fe}$ and pressure to within $\sim 0.6\text{ kbar}$.
- For surface slabs ($\text{Fe}(110)$ with larger in-plane supercell dimensions), the equivalent k-point density corresponds to:
  $$k_x \cdot a_x \approx k_y \cdot a_y \approx 45\text{--}50\text{ \AA}$$
  (e.g., $12\times 12$ for primitive surface cells or $6\times 6$ for $(2\times 2)$ supercells).

---

## 6. Next Single-Variable Gate: PAO Basis & EnergyShift (Gate 11)

With cutoff ($1500\text{ Ry} \to 72^3$) and $k$-points ($16^3\text{--}18^3$) established:
- **Gate 11 — PAO Basis Set & EnergyShift Sensitivity**:
  - Test basis size: DZP vs. TZP (or DZP with tuned radius).
  - Test `PAO.EnergyShift`: $0.01\text{ Ry}$, $0.02\text{ Ry}$ (current), and $0.05\text{ Ry}$.
  - Measure the effect on total energy and, crucially, on the Pulay stress / static pressure.
- **Following Gate**: Equation of State $E(a)$ and equilibrium lattice parameter $a_0$ of $\alpha$-Fe bulk.
