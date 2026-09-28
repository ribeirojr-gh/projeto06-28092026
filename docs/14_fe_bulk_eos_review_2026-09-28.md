# 14 — Review of Gate 12: alpha-Fe bulk Equation of State E(a) and equilibrium lattice a_0 (2026-09-28)

**Date:** 2026-09-28  
**Repository:** `ribeirojr-gh/projeto06-28092026`  
**Branch:** `step-03-dft-baseline`  
**Script:** `scripts/12_fe_bulk_eos.py`  
**Execution:** `SIESTA_MPI_RANKS=4 PYTHON_BIN=.venv-step02/bin/python bash run.sh` (Exit 0)  
**Wrapper log:** `logs/12_fe_bulk_eos.log`  
**Plot artifact:** `outputs/fe_bulk_eos.png`

---

## 1. Context & Objective

Prior gates established:
- **Cutoff:** 1500 Ry requested, realized $72\times 72\times 72$ FFT grid (Gate 08);
- **k-points:** $16\times 16\times 16$ Monkhorst–Pack grid, $\Delta E \le 0.57\text{ meV/Fe}$ (Gate 10A);
- **Basis:** DZP (19 orbitals/Fe), `PAO.EnergyShift = 0.020 Ry` (Gate 11).

Gate 12 determined the physical ground state of the $\alpha$-Fe bcc crystal by mapping the total energy versus lattice parameter $E(a)$ across seven points:
$$a \in [2.780,\ 2.820,\ 2.840,\ 2.8630355,\ 2.880,\ 2.910,\ 2.950]\text{ \AA}$$
and fitting the resulting $E(V)$ curve to the 3rd-order Birch–Murnaghan Equation of State (EOS).

---

## 2. Repeat Anchor Verification

The unrelaxed Materials Project cell ($a = 2.8630355\text{ \AA}$) served as the exact repeat anchor against Gate 10A and Gate 11:

| Quantity | Gate 11 (`dzp_shift0020`) | Gate 12 ($a = 2.863\text{ \AA}$) | Difference ($\Delta$) | Status |
| :--- | :---: | :---: | :---: | :---: |
| $E$ (eV/Fe) | $-3444.00805350$ | $-3444.00805350$ | $+0.0000\text{ meV/Fe}$ | **EXACT MATCH** |
| $M$ ($\mu_\mathrm{B}/\text{Fe}$) | $2.252300$ | $2.252300$ | $+0.000000\ \mu_\mathrm{B}/\text{Fe}$ | **EXACT MATCH** |
| $P$ (kbar) | $-107.562$ | $-107.562$ | $+0.0000\text{ kbar}$ | **EXACT MATCH** |
| SCF iterations | 60 | 60 | $0$ | **EXACT MATCH** |

**Anchor Gate: PASSED.** Exact numerical fidelity confirmed across all three consecutive gates.

---

## 3. Results Table

| $a$ (Å) | $V$ (Å³) | $E$ (eV/Fe) | $\Delta E$ vs $E_0$ (meV/Fe) | $M$ ($\mu_\mathrm{B}/\text{Fe}$) | $P$ (kbar) | SCF |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $2.7800$ | $21.485$ | $-3444.0280700$ | $+4.952$ | $2.116360$ | $+35.57$ | 63 |
| $2.8200$ | $22.426$ | $-3444.0309895$ | $+2.032$ | $2.185070$ | $-22.06$ | 63 |
| $2.8400$ | $22.906$ | $-3444.0224375$ | $+10.584$ | $2.215345$ | $-51.51$ | 63 |
| $2.8630$ | $23.468$ | $-3444.0080535$ | $+24.968$ | $2.252300$ | $-107.56$ | 60 |
| $2.8800$ | $23.888$ | $-3443.9918285$ | $+41.193$ | $2.295110$ | $-139.70$ | 59 |
| $2.9100$ | $24.642$ | $-3443.9590950$ | $+73.927$ | $2.502510$ | $-151.01$ | 66 |
| $2.9500$ | $25.672$ | $-3443.9053350$ | $+127.687$ | $2.598200$ | $-202.51$ | 62 |

---

## 4. Birch–Murnaghan Equation of State Fit

Fitting parameters:
- **Equilibrium lattice parameter $a_0$:** **$2.8037\text{ \AA}$**  
  *(Experimental: $2.866\text{ \AA}$, $\Delta = -2.17\%$)*
- **Equilibrium volume per cell $V_0$:** **$22.039\text{ \AA}^3$** ($11.020\text{ \AA}^3/\text{Fe}$)
- **Ground-state energy $E_0$:** **$-3444.033022\text{ eV/Fe}$**
- **Bulk modulus $B_0$:** **$212.35\text{ GPa}$**  
  *(Experimental range: $\sim 166\text{--}172\text{ GPa}$)*
- **Equilibrium magnetic moment $M(a_0)$:** **$\approx 2.16\ \mu_\mathrm{B}/\text{Fe}$**  
  *(Experimental: $2.22\ \mu_\mathrm{B}/\text{Fe}$)*

---

## 5. Scientific Interpretation

1. **Zero-Stress Coincidence**:
   - The analytical static pressure reported by SIESTA crosses $P = 0$ between $a = 2.780\text{ \AA}$ ($+35.57\text{ kbar}$) and $a = 2.820\text{ \AA}$ ($-22.06\text{ kbar}$), yielding a zero-pressure intercept at:
     $$a_{P=0} \approx 2.805\text{ \AA}$$
   - This matches the energy-minimum lattice parameter $a_0 = 2.8037\text{ \AA}$ to within $<0.002\text{ \AA}$ ($<0.07\%$).
   - This agreement demonstrates that Pulay stress artifacts are minimal at equilibrium and validates the stress tensor evaluation in SIESTA for the DZP basis.

2. **Magnetovolume Effect**:
   - The spin magnetic moment increases monotonically with volume:
     $$M(2.780\text{ \AA}) = 2.12\ \mu_\mathrm{B} \longrightarrow M(2.863\text{ \AA}) = 2.25\ \mu_\mathrm{B} \longrightarrow M(2.950\text{ \AA}) = 2.60\ \mu_\mathrm{B}$$
   - This behavior is in full agreement with the Stoner model and the known physics of itinerant 3d ferromagnetism in bcc iron.

3. **Comparison with Experiment and Literature**:
   - PBE-LCAO in SIESTA with DZP and $0.02\text{ Ry}$ shift yields $a_0 = 2.804\text{ \AA}$, reflecting standard LCAO orbital confinement overbinding ($-2.17\%$ vs. $a_\mathrm{exp} = 2.866\text{ \AA}$).
   - The bulk modulus $B_0 = 212\text{ GPa}$ reflects the slightly stiffer potential well typical of slightly under-expanded LCAO cells.

---

## 6. Gate Decision

**Gate 12: PASSED.**
- The fundamental baseline parameters of the bulk $\alpha$-Fe are now completely and rigorously characterized.
- Both the experimental reference cell ($a = 2.866\text{ \AA}$ / $a_\mathrm{MP} = 2.863\text{ \AA}$) and the DFT-PBE equilibrium cell ($a_0 = 2.804\text{ \AA}$) are documented with their respective energies, moments, and stresses.

---

## 7. Transition to Step 04: Fe(110) Surface Slabs & Corrosion Interfaces

With the bulk baseline closed:
- **Next Stage: Step 04 — Fe(110) Surface Models and Electronic Structure**:
  - Build symmetric $\text{Fe}(110)$ slabs with varying layer thickness (7, 9, 11 physical atomic planes, as generated in Step 02);
  - Vacuum spacing: $15\text{--}20\text{ \AA}$;
  - 2D Brillouin zone k-point sampling ($k_x \cdot a_x \approx k_y \cdot a_y \approx 45\text{ \AA}$);
  - Relaxation of top surface layers;
  - Surface energy calculation $\gamma_{(110)}$ and surface magnetization profile $M(z)$;
  - Preparation for water/chloride adsorption and 8-HQ inhibitor bonding.
