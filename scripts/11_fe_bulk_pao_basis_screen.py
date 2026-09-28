#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-variable ASE–SIESTA PAO basis size and EnergyShift screen for alpha-Fe.

This gate investigates:
1. PAO.EnergyShift sensitivity (0.005, 0.010, 0.020, 0.050 Ry) on DZP basis.
2. Basis cardinality sensitivity (SZ, DZ, DZP, TZP) at standard EnergyShift (0.020 Ry).

All other parameters are held strictly fixed:
- alpha-Fe conventional cell (mp-13, unrelaxed, 2 Fe atoms, Im-3m, a = 2.8630355 Å)
- Fe.psml (PseudoDojo/ONCVPSP 3.3, PBE, semicore 3s/3p, verified SHA-256)
- PBE functional
- k-grid: 16x16x16 Monkhorst–Pack (converged in Gate 10A)
- Requested MeshCutoff: 1500 Ry (realized 72³ FFT grid)
- ElectronicTemperature: 300 K (Fermi–Dirac)
- Collinear spin, initial moments +2.2 muB/Fe
- SCF.DM.Tolerance: 1.0e-4, MaxSCFIterations: 120, DM.MixingWeight: 0.05
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

from ase.calculators.siesta import Siesta
from ase.io import read
from ase.units import Ry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
REQUESTED_CUTOFF_RY = 1500
INITIAL_MOMENT_MUB = 2.2
SCF_MAX = 120
K_GRID = [16, 16, 16]

# Test matrix: (label, basis_set, energy_shift_Ry, category)
TEST_CONFIGS = [
    # EnergyShift variation on DZP (anchor: dzp_shift0020)
    ("dzp_shift0005", "DZP", 0.005, "energy_shift_scan"),
    ("dzp_shift0010", "DZP", 0.010, "energy_shift_scan"),
    ("dzp_shift0020", "DZP", 0.020, "anchor_and_baseline"),
    ("dzp_shift0050", "DZP", 0.050, "energy_shift_scan"),
    # Basis cardinality variation at standard shift (0.020 Ry)
    ("sz_shift0020",  "SZ",  0.020, "basis_size_scan"),
    ("dz_shift0020",  "DZ",  0.020, "basis_size_scan"),
    ("tzp_shift0020", "TZP", 0.020, "basis_size_scan"),
]

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
ORBITALS_RE = re.compile(r"atom:\s*Total number of Sankey-type orbitals:\s*(\d+)", re.I)


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
        "k_refine": OUT / "fe_bulk_kpoint_refinement_summary.json",
    }
    for name, path in inputs.items():
        if not path.is_file():
            raise RuntimeError(f"Validated prerequisite {name} is missing: {path}")

    meta = json.loads(inputs["bulk_meta"].read_text())
    preflight = json.loads(inputs["preflight"].read_text())
    pilot = json.loads(inputs["pilot"].read_text())
    k_refine = json.loads(inputs["k_refine"].read_text())

    if meta.get("formula") != "Fe" or meta.get(
        "standardized_structure_symmetry_strict", {}
    ).get("space_group_number") != 229:
        raise RuntimeError("Validated Im-3m alpha-Fe structural prerequisite not found.")
    if not preflight.get("preflight_passed") or not pilot.get("ase_returned_finite_energy"):
        raise RuntimeError("The Fe PSML preflight or ASE–SIESTA pilot is not validated.")

    approved_hash = preflight["pseudos"]["Fe"]["sha256"]
    if sha256(pseudo_dir / "Fe.psml") != approved_hash or pilot["Fe_psml_sha256"] != approved_hash:
        raise RuntimeError("Fe.psml has changed since PSML audit/pilot; revalidate before DFT.")

    if not k_refine.get("all_scf_converged"):
        raise RuntimeError("Gate 10A k-point refinement has unconverged SCF calculations.")

    atoms = read(inputs["bulk"], format="vasp")
    if len(atoms) != 2 or set(atoms.get_chemical_symbols()) != {"Fe"} or not all(atoms.pbc):
        raise RuntimeError("Expected the validated periodic two-Fe conventional bulk cell.")

    return atoms, meta, preflight, k_refine, approved_hash


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
    orbitals = ORBITALS_RE.findall(native)
    if not all((scf, etot, moments, meshes, cutoffs, pressures)):
        raise RuntimeError("Missing SCF/energy/moment/pressure/realized-grid data in native stdout.")
    dims = [int(x) for x in meshes[-1][:3]]
    if math.prod(dims) != int(meshes[-1][3]):
        raise RuntimeError("SIESTA reported inconsistent realized FFT-grid point count.")
    requested_native, used_native = map(number, cutoffs[-1])
    if abs(requested_native - expected_cutoff_ry) > 0.01 or used_native < requested_native:
        raise RuntimeError("Native requested/used MeshCutoff inconsistent with fixed numerical setup.")
    orbs_per_atom = int(orbitals[-1]) if orbitals else None
    return {
        "native_energy_eV_cell": number(etot[-1]),
        "native_spin_moment_muB_cell": number(moments[-1].group(1)),
        "pressure_static_kbar": number(pressures[0]),
        "realized_fft_mesh": dims,
        "used_mesh_cutoff_Ry": used_native,
        "native_required_cutoff_Ry": requested_native,
        "scf_iterations": int(scf[-1]),
        "scf_converged": True,
        "orbitals_per_atom": orbs_per_atom,
    }


def run_one_config(atoms, label: str, basis_set: str, shift_ry: float,
                   category: str, root: Path, pseudo_dir: Path, command: str) -> dict:
    folder = root / label
    folder.mkdir(parents=True, exist_ok=False)
    calc = Siesta(
        label=label,
        directory=str(folder),
        command=command,
        pseudo_path=str(pseudo_dir),
        pseudo_qualifier="",
        symlink_pseudos=True,
        xc="PBE",
        mesh_cutoff=REQUESTED_CUTOFF_RY * Ry,
        energy_shift=shift_ry * Ry,
        basis_set=basis_set,
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
    sample = atoms.copy()
    sample.set_initial_magnetic_moments([INITIAL_MOMENT_MUB] * len(sample))
    sample.calc = calc
    ase_total = float(sample.get_potential_energy())
    if not math.isfinite(ase_total):
        raise RuntimeError(f"{label}: ASE returned non-finite energy.")
    fdf, native_out = folder / f"{label}.fdf", folder / f"{label}.out"
    native = parse_native(native_out, REQUESTED_CUTOFF_RY)
    if abs(native["native_energy_eV_cell"] - ase_total) > 0.001:
        raise RuntimeError(f"{label}: ASE/native energies disagree by more than 1 meV/cell.")
    return {
        "label": label,
        "category": category,
        "basis_set": basis_set,
        "energy_shift_Ry": shift_ry,
        "k_grid": K_GRID,
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
    atoms, meta, audit, previous_k, approved_hash = prerequisite_gate(pseudo_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    root = OUT / "dft" / "fe_bulk_pao_basis" / stamp
    root.mkdir(parents=True, exist_ok=False)

    mpi_ranks = int(os.environ.get("SIESTA_MPI_RANKS", "4"))
    setup = {
        "purpose": "PAO basis size and EnergyShift screening at fixed 16x16x16 k-grid and 1500 Ry cutoff",
        "run_id": stamp,
        "mp_id": meta["material_id"],
        "geometry": "outputs/POSCAR_Fe_bulk",
        "Fe_psml_sha256": approved_hash,
        "xc": "PBE",
        "mesh_cutoff_requested_Ry": REQUESTED_CUTOFF_RY,
        "electronic_temperature_K": 300,
        "initial_moments_muB_per_Fe": INITIAL_MOMENT_MUB,
        "SCF_DM_tolerance": 1.0e-4,
        "SCF_max_iterations": SCF_MAX,
        "MPI_ranks": mpi_ranks,
        "k_grid": K_GRID,
        "previous_k_refine_run_id": previous_k["run_id"],
    }
    (root / "settings.json").write_text(json.dumps(setup, indent=2) + "\n")

    # Anchor from Gate 10A (16x16x16 point: DZP, 0.02 Ry)
    gate10_k16 = next(
        r for r in previous_k["results"] if r["requested_k_points"] == [16, 16, 16]
    )

    records = []
    for label, basis_set, shift_ry, category in TEST_CONFIGS:
        print(f"[PAO] Running {label}: basis={basis_set}, shift={shift_ry} Ry...", flush=True)
        try:
            row = run_one_config(atoms, label, basis_set, shift_ry, category, root, pseudo_dir, command)
            # Check FFT grid remains 72x72x72
            if row["realized_fft_mesh"] != [72, 72, 72]:
                raise RuntimeError(
                    f"Unexpected FFT mesh {row['realized_fft_mesh']} instead of 72x72x72."
                )

            # Check repeat anchor against Gate 10A (16x16x16, DZP, 0.02 Ry)
            if label == "dzp_shift0020":
                delta_e = (row["energy_eV_per_Fe"] - gate10_k16["energy_eV_per_Fe"]) * 1000
                delta_m = row["moment_muB_per_Fe"] - gate10_k16["moment_muB_per_Fe"]
                delta_p = row["pressure_static_kbar"] - gate10_k16["pressure_static_kbar"]
                row["anchor_delta_energy_meV_per_Fe"] = delta_e
                row["anchor_delta_moment_muB_per_Fe"] = delta_m
                row["anchor_delta_pressure_kbar"] = delta_p
                if abs(delta_e) > 0.5 or abs(delta_m) > 0.005 or abs(delta_p) > 0.5:
                    raise RuntimeError(
                        f"Repeat anchor mismatch on dzp_shift0020: dE={delta_e:+.4f} meV/Fe, "
                        f"dM={delta_m:+.6f} muB/Fe, dP={delta_p:+.4f} kbar."
                    )
                print(
                    f"[PAO] dzp_shift0020 anchor verified: dE={delta_e:+.4f} meV/Fe, "
                    f"dM={delta_m:+.6f} muB/Fe, dP={delta_p:+.4f} kbar.",
                    flush=True,
                )

            records.append(row)
            (root / "partial_results.json").write_text(json.dumps(records, indent=2) + "\n")
            print(
                f"[PAO] {label}: E={row['energy_eV_per_Fe']:.8f} eV/Fe; "
                f"M={row['moment_muB_per_Fe']:.6f} muB/Fe; "
                f"P={row['pressure_static_kbar']:.3f} kbar; "
                f"orbs/atom={row['orbitals_per_atom']}; "
                f"SCF={row['scf_iterations']}",
                flush=True,
            )
        except Exception:
            (root / "failure.json").write_text(
                json.dumps(
                    {
                        **setup,
                        "completed": records,
                        "failed_config": label,
                        "traceback": traceback.format_exc(),
                    },
                    indent=2,
                ) + "\n"
            )
            print(f"[PAO] FAILED at {label}; see {root / 'failure.json'}", file=sys.stderr)
            raise

    # Baseline reference is dzp_shift0020
    baseline = next(r for r in records if r["label"] == "dzp_shift0020")
    for row in records:
        row["delta_energy_vs_baseline_meV_per_Fe"] = (
            row["energy_eV_per_Fe"] - baseline["energy_eV_per_Fe"]
        ) * 1000
        row["delta_moment_vs_baseline_muB_per_Fe"] = (
            row["moment_muB_per_Fe"] - baseline["moment_muB_per_Fe"]
        )
        row["delta_pressure_vs_baseline_kbar"] = (
            row["pressure_static_kbar"] - baseline["pressure_static_kbar"]
        )

    result = {
        **setup,
        "n_expected": len(TEST_CONFIGS),
        "n_completed": len(records),
        "all_scf_converged": all(r["scf_converged"] for r in records),
        "baseline_anchor": "dzp_shift0020",
        "results": records,
    }

    json_path = OUT / "fe_bulk_pao_basis_summary.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n")

    fields = [
        "label", "basis_set", "energy_shift_Ry", "orbitals_per_atom",
        "energy_eV_per_Fe", "delta_energy_vs_baseline_meV_per_Fe",
        "moment_muB_per_Fe", "delta_moment_vs_baseline_muB_per_Fe",
        "pressure_static_kbar", "delta_pressure_vs_baseline_kbar",
        "scf_iterations", "native_output",
    ]
    with (OUT / "fe_bulk_pao_basis_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in fields} for row in records])

    lines = [
        "Alpha-Fe PAO Basis & EnergyShift Screening (Gate 11)",
        "===================================================",
        "SIESTA PBE, approved Fe semicore PSML, 16x16x16 k-grid, 1500 Ry requested cutoff (72³ FFT), 300 K.",
        "Baseline reference: DZP with EnergyShift = 0.020 Ry (dzp_shift0020).",
        "",
        "Label             Basis  Shift(Ry) Orbs/Fe    E(eV/Fe)     dE(meV/Fe)  M(muB/Fe)  P(kbar)  dP(kbar) SCF",
    ]
    for row in records:
        lines.append(
            f"{row['label']:<17} {row['basis_set']:<5} {row['energy_shift_Ry']:<9.3f} "
            f"{row['orbitals_per_atom'] or 0:>7d}  "
            f"{row['energy_eV_per_Fe']:14.7f} "
            f"{row['delta_energy_vs_baseline_meV_per_Fe']:11.4f} "
            f"{row['moment_muB_per_Fe']:10.6f} "
            f"{row['pressure_static_kbar']:8.3f} "
            f"{row['delta_pressure_vs_baseline_kbar']:8.3f} "
            f"{row['scf_iterations']:3d}"
        )
    lines.append("")
    lines.append("All results reflect unrelaxed cell (mp-13). Pulay stress and lattice relaxation pending.")
    (OUT / "fe_bulk_pao_basis_report.txt").write_text("\n".join(lines) + "\n")

    print("[PAO] Gate 11 completed successfully. Results written to outputs/", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
