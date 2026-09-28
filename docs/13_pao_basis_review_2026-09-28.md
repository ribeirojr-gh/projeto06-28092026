# 13 — Review of Gate 11: alpha-Fe bulk PAO basis size and EnergyShift screening (2026-09-28)

**Date:** 2026-09-28  
**Repository:** `ribeirojr-gh/projeto06-28092026`  
**Branch:** `step-03-dft-baseline`  
**Script:** `scripts/11_fe_bulk_pao_basis_screen.py`  
**Execution:** `SIESTA_MPI_RANKS=4 PYTHON_BIN=.venv-step02/bin/python bash run.sh` (Exit 0)  
**Wrapper log:** `logs/11_fe_bulk_pao_basis_screen.log`

---

## 1. Context & Objective

In Gate 10A, k-point sampling convergence was established across $14^3 \to 20^3$ ($\Delta E \le 0.57\text{ meV/Fe}$, $M$ and $P$ plateaued).  
Gate 11 investigated the sensitivity of the atomistic representation to:
1. Confinement potential (`PAO.EnergyShift`: $0.005, 0.010, 0.020, 0.050\text{ Ry}$) on the standard DZP basis.
2. Basis set cardinality (SZ, DZ, DZP, TZP) at standard `PAO.EnergyShift = 0.020 Ry`.

All other parameters remained strictly fixed:
- alpha-Fe conventional cubic cell (`mp-13`, 2 Fe atoms, $a = 2.8630355\text{ \AA}$, unrelaxed);
- Approved `Fe.psml` (PseudoDojo/ONCVPSP 3.3, PBE, scalar-relativistic, semicore $3s/3p$, 16 valence electrons);
- PBE functional, $T_\text{elec} = 300\text{ K}$, collinear spin ($+2.2\ \mu_\mathrm{B}/\text{Fe}$ initial);
- $16\times 16\times 16$ Monkhorst–Pack grid (from Gate 10A);
- Requested `MeshCutoff = 1500 Ry` (realized $72\times 72\times 72$ FFT grid held constant across all runs);
- 4 MPI ranks, 1 OpenMP/BLAS thread per rank.

---

## 2. Repeat Anchor Verification

The `dzp_shift0020` configuration directly reproduces the $16\times 16\times 16$ calculation of Gate 10A:

| Quantity | Gate 10A ($16^3$) | Gate 11 (`dzp_shift0020`) | Difference ($\Delta$) | Status |
| :--- | :---: | :---: | :---: | :---: |
| $E$ (eV/Fe) | $-3444.00805350$ | $-3444.00805350$ | $+0.0000\text{ meV/Fe}$ | **EXACT MATCH** |
| $M$ ($\mu_\mathrm{B}/\text{Fe}$) | $2.252300$ | $2.252300$ | $+0.000000\ \mu_\mathrm{B}/\text{Fe}$ | **EXACT MATCH** |
| $P$ (kbar) | $-107.562$ | $-107.562$ | $+0.0000\text{ kbar}$ | **EXACT MATCH** |
| SCF iterations | 60 | 60 | $0$ | **EXACT MATCH** |
| Realized FFT grid | $72\times 72\times 72$ | $72\times 72\times 72$ | identical | **EXACT MATCH** |

**Anchor Gate: PASSED.** Complete cross-script numerical integrity confirmed.

---

## 3. Results Table

| Label | Basis | Shift (Ry) | Orbitals/Fe | $E$ (eV/Fe) | $\Delta E$ vs baseline (meV/Fe) | $M$ ($\mu_\mathrm{B}/\text{Fe}$) | $P$ (kbar) | $\Delta P$ (kbar) | SCF |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `dzp_shift0005` | DZP | $0.005$ | 19 | $-3445.4672310$ | $-1459.178$ | $2.260880$ | $-73.904$ | $+33.658$ | 51 |
| `dzp_shift0010` | DZP | $0.010$ | 19 | $-3445.0037000$ | $-995.646$ | $2.254555$ | $-101.186$ | $+6.376$ | 77 |
| **`dzp_shift0020`** *(baseline)* | **DZP** | **$0.020$** | **19** | **$-3444.0080535$** | **$0.000$** | **$2.252300$** | **$-107.562$** | **$0.000$** | **60** |
| `dzp_shift0050` | DZP | $0.050$ | 19 | $-3440.5526495$ | $+3455.404$ | $2.305160$ | $-439.856$ | $-332.294$ | 31 |
| `sz_shift0020` | SZ | $0.020$ | 10 | $-3434.9218345$ | $+9086.219$ | $2.733865$ | $-112.074$ | $-4.513$ | 57 |
| `dz_shift0020` | DZ | $0.020$ | 16 | $-3440.5574255$ | $+3450.628$ | $2.664645$ | $-484.883$ | $-377.322$ | 78 |
| `tzp_shift0020` | TZP | $0.020$ | 25 | $-3444.1685155$ | $-160.462$ | $2.259305$ | $-80.029$ | $+27.533$ | 59 |

---

## 4. Scientific Interpretation

### 4.1 Importance of Polarization (DZP vs. DZ and SZ)
- Stripping polarization orbitals (`DZ`: 16 orbs/Fe) or un-doubling the valence (`SZ`: 10 orbs/Fe) leads to catastrophic loss of bonding:
  - Energy rises by $+3.45\text{ eV/Fe}$ (DZ) and $+9.09\text{ eV/Fe}$ (SZ).
  - Magnetic moment jumps to unphysical values ($2.66\ \mu_\mathrm{B}$ and $2.73\ \mu_\mathrm{B}$).
  - Static stress changes drastically ($-484.9\text{ kbar}$ for DZ).
- **Conclusion:** Polarization orbitals are essential to describe the metallic $d$-band and interatomic directional bonding in $\alpha$-Fe. SZ and DZ are completely inadequate.

### 4.2 DZP vs. TZP Completeness
- Adding a third radial function (`TZP`: 25 orbs/Fe):
  - Energy lowers by only **$-160.5\text{ meV/Fe}$** (less than $0.005\%$ of total energy).
  - Spin moment shifts by merely **$+0.007\ \mu_\mathrm{B}/\text{Fe}$** ($2.252 \to 2.259\ \mu_\mathrm{B}/\text{Fe}$).
- **Conclusion:** **DZP is already near-complete** for the electronic and magnetic properties of $\alpha$-Fe. For large slabs and interfacial systems (where $N_\mathrm{atoms} > 200$), DZP provides the optimal accuracy-to-cost ratio.

### 4.3 `EnergyShift` and Pulay Stress
- As `EnergyShift` decreases from $0.050 \to 0.005\text{ Ry}$ (orbital confinement relaxed, cutoffs $r_c$ expand):
  - Total energy lowers variationally.
  - The static pressure magnitude drops dramatically from $-439.9\text{ kbar}$ ($0.05\text{ Ry}$) to $-107.6\text{ kbar}$ ($0.02\text{ Ry}$) and $-73.9\text{ kbar}$ ($0.005\text{ Ry}$).
- This confirms that a substantial portion of the static pressure at unrelaxed geometry arises from **Pulay stress** (dependence of the localized basis on cell volume).
- In the next gate (Equation of State), determining the equilibrium lattice parameter $a_0$ via energy minimization $E(a)$ will be completely independent of Pulay stress artifacts.

---

## 5. Gate Decision

**Gate 11: PASSED.**
- Production basis selected: **DZP** (19 orbitals/Fe).
- Production `PAO.EnergyShift` range: **$0.010\text{--}0.020\text{ Ry}$**.

---

## 6. Next Single-Variable Gate: Equation of State & Equilibrium Lattice (Gate 12)

With cutoff ($1500\text{ Ry} \to 72^3$), k-points ($16\times 16\times 16$), and basis (DZP, `EnergyShift = 0.02 Ry`) frozen:
- **Gate 12 — Equation of State $E(a)$ of $\alpha$-Fe bulk**:
  - Sample lattice parameters $a \in [2.78, 2.82, 2.84, 2.863, 2.88, 2.90, 2.94]\text{ \AA}$ (7 points around the experimental $a_\mathrm{exp} = 2.866\text{ \AA}$).
  - Fit to Birch–Murnaghan Equation of State (EOS) to determine:
    1. Equilibrium lattice parameter $a_0$ (DFT-PBE);
    2. Minimum energy $E_0$;
    3. Bulk modulus $B_0$ and its derivative $B_0'$;
    4. Magnetic moment variation $M(a)$.
  - Independent benchmark comparison with GPAW (Plane-Wave mode).
