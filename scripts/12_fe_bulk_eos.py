#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Equation of State (EOS) and equilibrium lattice parameter a_0 for alpha-Fe.

This gate samples 7 lattice constants around the experimental reference
(a_exp = 2.866 Å):
  a in [2.780, 2.820, 2.840, 2.8630355, 2.880, 2.910, 2.950] Å

The unrelaxed Materials Project cell (a = 2.8630355 Å) serves as the exact
repeat anchor against Gate 10A and Gate 11.

Numerical setup (frozen from earlier gates):
- PBE functional, approved Fe semicore PSML (16 valence electrons)
- DZP basis, PAO.EnergyShift 0.020 Ry (established in Gate 11)
- k-grid: 16x16x16 Monkhorst–Pack (converged in Gate 10A)
- Requested MeshCutoff: 1500 Ry (realized 72³ FFT grid)
- ElectronicTemperature: 300 K (Fermi–Dirac)
- Collinear spin, initial moments +2.2 muB/Fe
- SCF.DM.Tolerance: 1.0e-4, MaxSCFIterations: 120, DM.MixingWeight: 0.05

Outputs:
- Birch–Murnaghan 3rd-order EOS fit: a_0, V_0, E_0, B_0 (GPa), B_0'
- Comparison of Pulay stress vs numerical derivative dE/dV
- outputs/fe_bulk_eos_summary.json, CSV, TXT report and EOS plot (PNG)
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import traceback

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ase.calculators.siesta import Siesta
from ase.eos import EquationOfState
from ase.io import read
from ase.units import GPa, Ry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
REQUESTED_CUTOFF_RY = 1500
ENERGY_SHIFT_RY = 0.020
INITIAL_MOMENT_MUB = 2.2
SCF_MAX = 120
K_GRID = [16, 16, 16]

# Sampling grid around a_exp = 2.866 Å (including anchor 2.8630355 Å)
A_LATTICE_LIST = [2.780, 2.820, 2.840, 2.863035498949916, 2.880, 2.910, 2.950]

SCF_RE = re.compile(r"SCF cycle converged after\s+(\d+)\s+iterations", re.I)
ETOT_RE = re.compile(r"(?m)^\s*siesta:\s+Etot\s*=\s*([-+0-9.eEdD]+)")
SPIN_RE = re.compile(r"spin moment:.*?([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$", re.I)
PRESSURE_RE = re.compile(
    r"(?m)^\s*siesta:\s+([-+0-9.eEdD]+)\s+[-+0-9.eEdD]+\s+kBar\s*$"
)
MESH_RE = re.compile(
    r"InitMesh:\s*MESH\s*=\s*(\d+)\s*x\s*(\d+)\s*x\s*(\d+)\s*=\s*(\d+)"
)
ACTUAL_RE = re.compile(
    r"InitMesh:\s*Mesh cutoff \(required, used\)\s*=\s*"
    r"([-+0-9.eEdD]+)\s+([-+0-9.eEdD]+)\s+Ry"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(s: str) -> float:
    x = float(s.replace("D", "E").replace("d", "e"))
    if not math.isfinite(x):
        raise RuntimeError("Found non-finite number in native output.")
    return x


def prerequisite_gate(pseudo_dir: Path):
    inputs = {
        "bulk": OUT / "POSCAR_Fe_bulk",
        "bulk_meta": OUT / "Fe_bulk_metadata.json",
        "preflight": OUT / "siesta_preflight.json",
        "pilot": OUT / "fe_bulk_siesta_pilot_summary.json",
        "pao_basis": OUT / "fe_bulk_pao_basis_summary.json",
    }
    for name, path in inputs.items():
        if not path.is_file():
            raise RuntimeError(f"Validated prerequisite {name} is missing: {path}")

    meta = json.loads(inputs["bulk_meta"].read_text())
    preflight = json.loads(inputs["preflight"].read_text())
    pilot = json.loads(inputs["pilot"].read_text())
    pao_basis = json.loads(inputs["pao_basis"].read_text())

    if meta.get("formula") != "Fe" or meta.get(
        "standardized_structure_symmetry_strict", {}
    ).get("space_group_number") != 229:
        raise RuntimeError("Validated Im-3m alpha-Fe structural prerequisite not found.")
    if not preflight.get("preflight_passed") or not pilot.get("ase_returned_finite_energy"):
        raise RuntimeError("The Fe PSML preflight or ASE–SIESTA pilot is not validated.")

    approved_hash = preflight["pseudos"]["Fe"]["sha256"]
    if sha256(pseudo_dir / "Fe.psml") != approved_hash or pilot["Fe_psml_sha256"] != approved_hash:
        raise RuntimeError("Fe.psml has changed since PSML audit/pilot; revalidate before DFT.")

    if not pao_basis.get("all_scf_converged"):
        raise RuntimeError("Gate 11 PAO basis screening has unconverged SCF calculations.")

    atoms = read(inputs["bulk"], format="vasp")
    if len(atoms) != 2 or set(atoms.get_chemical_symbols()) != {"Fe"} or not all(atoms.pbc):
        raise RuntimeError("Expected the validated periodic two-Fe conventional bulk cell.")

    return atoms, meta, preflight, pao_basis, approved_hash


def parse_native(path: Path, expected_cutoff_ry: int) -> dict:
    if not path.is_file():
        raise RuntimeError(f"Missing native SIESTA stdout: {path}")
    native = path.read_text(errors="replace")
    if "Job completed" not in native or "Fe.1.psml" not in native:
        raise RuntimeError("SIESTA native output lacks completion or Fe PSML provenance.")
    scf, etot = SCF_RE.findall(native), ETOT_RE.findall(native)
    moments = [
        m for line in native.splitlines() if "spin moment:" in line.lower()
        for m in [SPIN_RE.search(line)] if m is not None
    ]
    meshes, cutoffs = MESH_RE.findall(native), ACTUAL_RE.findall(native)
    after_pressure = native.rsplit("Pressure (static):", 1)
    pressures = PRESSURE_RE.findall(after_pressure[-1]) if len(after_pressure) == 2 else []
    if not all((scf, etot, moments, meshes, cutoffs, pressures)):
        raise RuntimeError("Missing SCF/energy/moment/pressure/realized-grid data in native stdout.")
    dims = [int(x) for x in meshes[-1][:3]]
    if math.prod(dims) != int(meshes[-1][3]):
        raise RuntimeError("SIESTA reported inconsistent realized FFT-grid point count.")
    requested_native, used_native = map(number, cutoffs[-1])
    if abs(requested_native - expected_cutoff_ry) > 0.01 or used_native < requested_native:
        raise RuntimeError("Native requested/used MeshCutoff inconsistent with fixed numerical setup.")
    return {
        "native_energy_eV_cell": number(etot[-1]),
        "native_spin_moment_muB_cell": number(moments[-1].group(1)),
        "pressure_static_kbar": number(pressures[0]),
        "realized_fft_mesh": dims,
        "used_mesh_cutoff_Ry": used_native,
        "native_required_cutoff_Ry": requested_native,
        "scf_iterations": int(scf[-1]),
        "scf_converged": True,
    }


def run_one_lattice(atoms, a_val: float, root: Path, pseudo_dir: Path, command: str) -> dict:
    label = f"fe_bulk_a{a_val:.3f}".replace(".", "_")
    folder = root / label
    folder.mkdir(parents=True, exist_ok=False)

    # Scale cell uniformly to target lattice parameter a_val
    sample = atoms.copy()
    current_a = atoms.cell[0, 0]
    scale_factor = a_val / current_a
    new_cell = atoms.cell * scale_factor
    sample.set_cell(new_cell, scale_atoms=True)

    calc = Siesta(
        label=label,
        directory=str(folder),
        command=command,
        pseudo_path=str(pseudo_dir),
        pseudo_qualifier="",
        symlink_pseudos=True,
        xc="PBE",
        mesh_cutoff=REQUESTED_CUTOFF_RY * Ry,
        energy_shift=ENERGY_SHIFT_RY * Ry,
        basis_set="DZP",
        kpts=K_GRID,
        spin="collinear",
        fdf_arguments={
            "ElectronicTemperature": "300 K",
            "SCF.DM.Tolerance": 1.0e-4,
            "MaxSCFIterations": SCF_MAX,
            "DM.MixingWeight": 0.05,
            "SCFMustConverge": True,
            "Charge.Mulliken": "end",
            "DM.UseSaveDM": False,
        },
    )
    sample.set_initial_magnetic_moments([INITIAL_MOMENT_MUB] * len(sample))
    sample.calc = calc
    ase_total = float(sample.get_potential_energy())
    if not math.isfinite(ase_total):
        raise RuntimeError(f"{label}: ASE returned non-finite energy.")
    fdf, native_out = folder / f"{label}.fdf", folder / f"{label}.out"
    native = parse_native(native_out, REQUESTED_CUTOFF_RY)
    if abs(native["native_energy_eV_cell"] - ase_total) > 0.001:
        raise RuntimeError(f"{label}: ASE/native energies disagree by more than 1 meV/cell.")

    vol = float(sample.get_volume())
    return {
        "label": label,
        "lattice_param_a_A": a_val,
        "volume_cell_A3": vol,
        "volume_per_Fe_A3": vol / len(sample),
        "energy_eV_cell": ase_total,
        "energy_eV_per_Fe": ase_total / len(sample),
        "moment_muB_per_Fe": native["native_spin_moment_muB_cell"] / len(sample),
        **native,
        "run_directory": str(folder.relative_to(ROOT)),
        "input_FDF": str(fdf.relative_to(ROOT)),
        "native_output": str(native_out.relative_to(ROOT)),
    }


def main() -> int:
    command = os.environ.get("ASE_SIESTA_COMMAND", "")
    if "PREFIX.fdf" not in command or "PREFIX.out" not in command:
        raise RuntimeError("ASE_SIESTA_COMMAND must contain PREFIX.fdf and PREFIX.out.")
    pseudo_dir = Path(os.path.expanduser(
        os.environ.get("SIESTA_PS_PATH", "~/Pacotes/PSEUDOS/DOJO-PSML")
    )).resolve()
    atoms, meta, audit, previous_pao, approved_hash = prerequisite_gate(pseudo_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    root = OUT / "dft" / "fe_bulk_eos" / stamp
    root.mkdir(parents=True, exist_ok=False)

    mpi_ranks = int(os.environ.get("SIESTA_MPI_RANKS", "4"))
    setup = {
        "purpose": "Equation of State E(a) and equilibrium lattice parameter a_0 for alpha-Fe",
        "run_id": stamp,
        "mp_id": meta["material_id"],
        "geometry": "outputs/POSCAR_Fe_bulk",
        "Fe_psml_sha256": approved_hash,
        "xc": "PBE",
        "basis": "DZP",
        "energy_shift_Ry": ENERGY_SHIFT_RY,
        "mesh_cutoff_requested_Ry": REQUESTED_CUTOFF_RY,
        "electronic_temperature_K": 300,
        "initial_moments_muB_per_Fe": INITIAL_MOMENT_MUB,
        "SCF_DM_tolerance": 1.0e-4,
        "SCF_max_iterations": SCF_MAX,
        "MPI_ranks": mpi_ranks,
        "k_grid": K_GRID,
        "sampled_a_lattice_A": A_LATTICE_LIST,
        "previous_pao_basis_run_id": previous_pao["run_id"],
    }
    (root / "settings.json").write_text(json.dumps(setup, indent=2) + "\n")

    # Anchor from Gate 11 baseline (dzp_shift0020 on unrelaxed cell a = 2.8630355 Å)
    gate11_baseline = next(
        r for r in previous_pao["results"] if r["label"] == "dzp_shift0020"
    )

    records = []
    for a_val in A_LATTICE_LIST:
        print(f"[EOS] Running alpha-Fe at a = {a_val:.4f} Å...", flush=True)
        try:
            row = run_one_lattice(atoms, a_val, root, pseudo_dir, command)

            # Anchor check at a = 2.8630355 Å
            if abs(a_val - 2.863035498949916) < 1e-6:
                delta_e = (row["energy_eV_per_Fe"] - gate11_baseline["energy_eV_per_Fe"]) * 1000
                delta_m = row["moment_muB_per_Fe"] - gate11_baseline["moment_muB_per_Fe"]
                delta_p = row["pressure_static_kbar"] - gate11_baseline["pressure_static_kbar"]
                row["anchor_delta_energy_meV_per_Fe"] = delta_e
                row["anchor_delta_moment_muB_per_Fe"] = delta_m
                row["anchor_delta_pressure_kbar"] = delta_p
                if abs(delta_e) > 0.5 or abs(delta_m) > 0.005 or abs(delta_p) > 0.5:
                    raise RuntimeError(
                        f"Repeat anchor mismatch at a=2.863 Å: dE={delta_e:+.4f} meV/Fe, "
                        f"dM={delta_m:+.6f} muB/Fe, dP={delta_p:+.4f} kbar."
                    )
                print(
                    f"[EOS] a=2.863 Å anchor verified: dE={delta_e:+.4f} meV/Fe, "
                    f"dM={delta_m:+.6f} muB/Fe, dP={delta_p:+.4f} kbar.",
                    flush=True,
                )

            records.append(row)
            (root / "partial_results.json").write_text(json.dumps(records, indent=2) + "\n")
            print(
                f"[EOS] a={a_val:.3f} Å (V={row['volume_cell_A3']:.3f} Å³): "
                f"E={row['energy_eV_per_Fe']:.8f} eV/Fe; "
                f"M={row['moment_muB_per_Fe']:.6f} muB/Fe; "
                f"P={row['pressure_static_kbar']:.2f} kbar; "
                f"SCF={row['scf_iterations']}",
                flush=True,
            )
        except Exception:
            (root / "failure.json").write_text(
                json.dumps(
                    {
                        **setup,
                        "completed": records,
                        "failed_a": a_val,
                        "traceback": traceback.format_exc(),
                    },
                    indent=2,
                ) + "\n"
            )
            print(f"[EOS] FAILED at a={a_val}; see {root / 'failure.json'}", file=sys.stderr)
            raise

    # Fit Birch–Murnaghan Equation of State
    volumes = [r["volume_cell_A3"] for r in records]
    energies_cell = [r["energy_eV_cell"] for r in records]

    eos = EquationOfState(volumes, energies_cell, eos="birchmurnaghan")
    v0, e0, B = eos.fit()
    # a_0 for cubic cell: a_0 = (V_0)^(1/3)
    a0 = v0 ** (1 / 3)
    b_gpa = B / GPa

    # Plot EOS fit
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), dpi=300)

    # Left panel: E(a)
    a_fit = np.linspace(min(A_LATTICE_LIST) - 0.02, max(A_LATTICE_LIST) + 0.02, 200)
    v_fit = a_fit ** 3
    # Evaluate Birch-Murnaghan energy
    eta = (v0 / v_fit) ** (2 / 3)
    e_bm = e0 + (9 * v0 * B / 16) * (
        (eta - 1) ** 3 * 4.0 + (eta - 1) ** 2 * (6 - 4 * eta)
    )

    ax1.plot([r["lattice_param_a_A"] for r in records],
             [r["energy_eV_per_Fe"] for r in records], 'ro', label="SIESTA (PBE/DZP)")
    ax1.plot(a_fit, e_bm / 2.0, 'b-', label=f"Birch–Murnaghan Fit\n$a_0 = {a0:.4f}$ Å\n$B_0 = {b_gpa:.1f}$ GPa")
    ax1.axvline(a0, color='gray', linestyle='--', alpha=0.7)
    ax1.set_xlabel(r"Lattice parameter $a$ (Å)")
    ax1.set_ylabel(r"Energy (eV/Fe)")
    ax1.set_title(r"$\alpha$-Fe Birch–Murnaghan EOS")
    ax1.legend(frameon=True, fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Right panel: M(a) and P(a)
    ax2.plot([r["lattice_param_a_A"] for r in records],
             [r["moment_muB_per_Fe"] for r in records], 'gs-', label=r"Magnetic moment ($\mu_\mathrm{B}$/Fe)")
    ax2.set_xlabel(r"Lattice parameter $a$ (Å)")
    ax2.set_ylabel(r"Spin moment ($\mu_\mathrm{B}$/Fe)", color='g')
    ax2.tick_params(axis='y', labelcolor='g')

    ax2_twin = ax2.twinx()
    ax2_twin.plot([r["lattice_param_a_A"] for r in records],
                  [r["pressure_static_kbar"] for r in records], 'md--', label="Static pressure (kbar)")
    ax2_twin.set_ylabel("Pressure (kbar)", color='m')
    ax2_twin.tick_params(axis='y', labelcolor='m')
    ax2_twin.axhline(0, color='k', linestyle=':', alpha=0.5)
    ax2.set_title("Magnetization and Stress vs. Lattice")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    plot_path = OUT / "fe_bulk_eos.png"
    fig.savefig(plot_path)
    plt.close(fig)

    eos_results = {
        "equilibrium_volume_cell_A3": v0,
        "equilibrium_volume_per_Fe_A3": v0 / 2.0,
        "equilibrium_lattice_param_a0_A": a0,
        "equilibrium_energy_cell_eV": e0,
        "equilibrium_energy_per_Fe_eV": e0 / 2.0,
        "bulk_modulus_B0_GPa": b_gpa,
        "experimental_a_exp_A": 2.866,
        "a0_relative_error_vs_exp_percent": (a0 - 2.866) / 2.866 * 100,
    }

    result = {
        **setup,
        "n_expected": len(A_LATTICE_LIST),
        "n_completed": len(records),
        "all_scf_converged": all(r["scf_converged"] for r in records),
        "eos_fit": eos_results,
        "results": records,
    }

    json_path = OUT / "fe_bulk_eos_summary.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n")

    fields = [
        "label", "lattice_param_a_A", "volume_cell_A3",
        "energy_eV_per_Fe", "moment_muB_per_Fe", "pressure_static_kbar",
        "scf_iterations", "native_output",
    ]
    with (OUT / "fe_bulk_eos_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in fields} for row in records])

    lines = [
        "Alpha-Fe Equation of State & Equilibrium Lattice (Gate 12)",
        "==========================================================",
        "SIESTA PBE, approved Fe semicore PSML, DZP basis, 16x16x16 k-grid, 1500 Ry cutoff, 300 K.",
        "",
        "Birch–Murnaghan Fit Results:",
        f"  Equilibrium lattice constant a_0 : {a0:.5f} Å (Exp: 2.866 Å, Δ = {(a0-2.866)/2.866*100:+.2f}%)",
        f"  Equilibrium volume per cell V_0  : {v0:.4f} Å³",
        f"  Equilibrium energy E_0           : {e0/2.0:.7f} eV/Fe",
        f"  Bulk modulus B_0                 : {b_gpa:.2f} GPa (Exp: ~166–172 GPa)",
        "",
        "Sampled Points Table:",
        "a(Å)      V(Å³)     E(eV/Fe)        dE_min(meV/Fe)  M(muB/Fe)  P(kbar)   SCF",
    ]
    min_e_fe = e0 / 2.0
    for row in records:
        de_min = (row["energy_eV_per_Fe"] - min_e_fe) * 1000
        lines.append(
            f"{row['lattice_param_a_A']:<9.4f} "
            f"{row['volume_cell_A3']:<9.3f} "
            f"{row['energy_eV_per_Fe']:15.7f} "
            f"{de_min:13.3f}   "
            f"{row['moment_muB_per_Fe']:10.6f} "
            f"{row['pressure_static_kbar']:9.2f} "
            f"{row['scf_iterations']:3d}"
        )
    (OUT / "fe_bulk_eos_report.txt").write_text("\n".join(lines) + "\n")

    print(
        f"[EOS] Gate 12 completed successfully. a_0 = {a0:.4f} Å, B_0 = {b_gpa:.1f} GPa.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
