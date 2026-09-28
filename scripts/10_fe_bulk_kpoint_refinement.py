#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-variable ASE–SIESTA k-point refinement (14³–20³) for fixed alpha-Fe.

This gate refines k-point sampling on the provisional 1500 Ry requested
MeshCutoff (realized 72³ FFT grid) to test whether the ~1.33 meV/Fe odd/even
energy oscillation observed between 10³ and 14³ damps below the 1.0 meV/Fe
tolerance threshold at 300 K.

All other parameters are held strictly fixed:
- alpha-Fe conventional cell (mp-13, unrelaxed, 2 Fe atoms, Im-3m)
- Fe.psml (PseudoDojo/ONCVPSP 3.3, PBE, semicore 3s/3p, verified SHA-256)
- PBE functional, DZP basis, PAO.EnergyShift 0.02 Ry
- Requested MeshCutoff 1500 Ry (realized 72³ grid)
- ElectronicTemperature 300 K (Fermi-Dirac)
- Collinear spin, initial moments +2.2 muB/Fe
- SCF.DM.Tolerance 1.0e-4, MaxSCFIterations 120, DM.MixingWeight 0.05
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
K_GRIDS = (14, 16, 18, 20)
REQUESTED_CUTOFF_RY = 1500
ENERGY_SHIFT_RY = 0.02
INITIAL_MOMENT_MUB = 2.2
SCF_MAX = 120

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
K_BLOCK_RE = re.compile(
    r"(?ims)^\s*%block\s+kgrid_Monkhorst_Pack\s*\n"
    r"(.*?)"
    r"^\s*%endblock\s+kgrid_Monkhorst_Pack\s*$"
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
        "grid": OUT / "fe_bulk_realized_grid_summary.json",
        "k_screen": OUT / "fe_bulk_kpoint_summary.json",
    }
    for name, path in inputs.items():
        if not path.is_file():
            raise RuntimeError(f"Validated prerequisite {name} is missing: {path}")

    meta = json.loads(inputs["bulk_meta"].read_text())
    preflight = json.loads(inputs["preflight"].read_text())
    pilot = json.loads(inputs["pilot"].read_text())
    grid = json.loads(inputs["grid"].read_text())
    k_screen = json.loads(inputs["k_screen"].read_text())

    if meta.get("formula") != "Fe" or meta.get(
        "standardized_structure_symmetry_strict", {}
    ).get("space_group_number") != 229:
        raise RuntimeError("Validated Im-3m alpha-Fe structural prerequisite not found.")
    if not preflight.get("preflight_passed") or not pilot.get("ase_returned_finite_energy"):
        raise RuntimeError("The Fe PSML preflight or ASE–SIESTA pilot is not validated.")

    approved_hash = preflight["pseudos"]["Fe"]["sha256"]
    if sha256(pseudo_dir / "Fe.psml") != approved_hash or pilot["Fe_psml_sha256"] != approved_hash:
        raise RuntimeError("Fe.psml has changed since PSML audit/pilot; revalidate before DFT.")

    if not k_screen.get("all_scf_converged"):
        raise RuntimeError("Gate 09 k-point screening has unconverged SCF calculations.")

    atoms = read(inputs["bulk"], format="vasp")
    if len(atoms) != 2 or set(atoms.get_chemical_symbols()) != {"Fe"} or not all(atoms.pbc):
        raise RuntimeError("Expected the validated periodic two-Fe conventional bulk cell.")

    return atoms, meta, preflight, k_screen, approved_hash


def check_fdf_kgrid(fdf: Path, k: int) -> list[int]:
    if not fdf.is_file():
        raise RuntimeError(f"Missing generated FDF: {fdf}")
    data = fdf.read_text(errors="replace")
    if not re.search(r"(?im)^\s*Spin\s+collinear\b", data) or not re.search(
        r"(?im)^\s*%block\s+DM\.InitSpin\b", data
    ):
        raise RuntimeError(f"Generated FDF lacks collinear spin initialization: {fdf}")
    blocks = K_BLOCK_RE.findall(data)
    if len(blocks) != 1:
        raise RuntimeError(f"Expected one Monkhorst–Pack k-grid block: {fdf}")
    lines = [line.split() for line in blocks[0].splitlines() if line.strip()]
    if len(lines) != 3 or any(len(line) < 4 for line in lines):
        raise RuntimeError(f"Malformed k-grid block: {fdf}")
    grid = [[int(line[j]) for j in range(3)] for line in lines]
    if grid != [[k, 0, 0], [0, k, 0], [0, 0, k]]:
        raise RuntimeError(f"FDF k-grid differs from intended {k}x{k}x{k}: {grid}")
    return [k, k, k]


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


def one_kpoint(atoms, k: int, root: Path, pseudo_dir: Path, command: str) -> dict:
    folder = root / f"k{k:02d}"
    folder.mkdir(parents=True, exist_ok=False)
    label = f"Fe_bulk_k{k:02d}"
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
        kpts=[k, k, k],
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
    confirmed_grid = check_fdf_kgrid(fdf, k)
    native = parse_native(native_out, REQUESTED_CUTOFF_RY)
    if abs(native["native_energy_eV_cell"] - ase_total) > 0.001:
        raise RuntimeError(f"{label}: ASE/native energies disagree by more than 1 meV/cell.")
    return {
        "requested_k_points": confirmed_grid,
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
    root = OUT / "dft" / "fe_bulk_kpoint_refinement" / stamp
    root.mkdir(parents=True, exist_ok=False)

    mpi_ranks = int(os.environ.get("SIESTA_MPI_RANKS", "2"))
    setup = {
        "purpose": "k-point refinement 14³–20³ at provisional 1500 Ry / 72³ FFT grid",
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
        "kpoint_grids": [[k, k, k] for k in K_GRIDS],
        "previous_k_screen_run_id": previous_k["run_id"],
        "provisional_mesh_only": True,
        "not_a_final_convergence_claim": True,
    }
    (root / "settings.json").write_text(json.dumps(setup, indent=2) + "\n")

    # Anchor from Gate 09 (14x14x14 point)
    gate09_k14 = next(
        r for r in previous_k["results"] if r["requested_k_points"] == [14, 14, 14]
    )

    records = []
    for k in K_GRIDS:
        print(f"[K-REFINE] Starting alpha-Fe at Monkhorst–Pack {k}x{k}x{k}...", flush=True)
        try:
            row = one_kpoint(atoms, k, root, pseudo_dir, command)
            # Check FFT grid remains 72x72x72
            if row["realized_fft_mesh"] != [72, 72, 72]:
                raise RuntimeError(
                    f"Fixed MeshCutoff produced unexpected FFT mesh {row['realized_fft_mesh']} instead of 72x72x72."
                )

            # Check 14x14x14 repeat anchor against Gate 09
            if k == 14:
                delta_e = (row["energy_eV_per_Fe"] - gate09_k14["energy_eV_per_Fe"]) * 1000
                delta_m = row["moment_muB_per_Fe"] - gate09_k14["moment_muB_per_Fe"]
                delta_p = row["pressure_static_kbar"] - gate09_k14["pressure_static_kbar"]
                row["anchor_k14_delta_energy_meV_per_Fe"] = delta_e
                row["anchor_k14_delta_moment_muB_per_Fe"] = delta_m
                row["anchor_k14_delta_pressure_kbar"] = delta_p
                if abs(delta_e) > 0.5 or abs(delta_m) > 0.005 or abs(delta_p) > 0.5:
                    raise RuntimeError(
                        f"Repeated 14x14x14 anchor mismatch: dE={delta_e:+.4f} "
                        f"meV/Fe, dM={delta_m:+.6f} muB/Fe, dP={delta_p:+.4f} kbar."
                    )
                print(
                    f"[K-REFINE] 14x14x14 repeat anchor verified: dE={delta_e:+.4f} meV/Fe, "
                    f"dM={delta_m:+.6f} muB/Fe, dP={delta_p:+.4f} kbar.",
                    flush=True,
                )

            records.append(row)
            (root / "partial_results.json").write_text(json.dumps(records, indent=2) + "\n")
            print(
                f"[K-REFINE] {k}x{k}x{k}: E={row['energy_eV_per_Fe']:.8f} eV/Fe; "
                f"M={row['moment_muB_per_Fe']:.6f} muB/Fe; "
                f"P={row['pressure_static_kbar']:.3f} kbar; "
                f"SCF={row['scf_iterations']}; FFT={row['realized_fft_mesh']}",
                flush=True,
            )
        except Exception:
            (root / "failure.json").write_text(
                json.dumps(
                    {
                        **setup,
                        "completed": records,
                        "failed_k_grid": [k, k, k],
                        "traceback": traceback.format_exc(),
                    },
                    indent=2,
                ) + "\n"
            )
            print(f"[K-REFINE] FAILED at {k}x{k}x{k}; see {root / 'failure.json'}", file=sys.stderr)
            raise

    # Densest grid in this gate (20x20x20) serves as reference
    reference_20 = records[-1]
    for row in records:
        row["delta_energy_vs_k20_meV_per_Fe"] = (
            row["energy_eV_per_Fe"] - reference_20["energy_eV_per_Fe"]
        ) * 1000
        row["delta_moment_vs_k20_muB_per_Fe"] = (
            row["moment_muB_per_Fe"] - reference_20["moment_muB_per_Fe"]
        )
        row["delta_pressure_vs_k20_kbar"] = (
            row["pressure_static_kbar"] - reference_20["pressure_static_kbar"]
        )

    # Compute peak-to-peak span
    energies_per_fe = [r["energy_eV_per_Fe"] for r in records]
    e_span_mev = (max(energies_per_fe) - min(energies_per_fe)) * 1000

    result = {
        **setup,
        "n_expected": len(K_GRIDS),
        "n_completed": len(records),
        "all_scf_converged": all(r["scf_converged"] for r in records),
        "n_distinct_k_grids": len({tuple(r["requested_k_points"]) for r in records}),
        "all_realized_fft_72_cubed": all(r["realized_fft_mesh"] == [72, 72, 72] for r in records),
        "energy_span_14_to_20_meV_per_Fe": e_span_mev,
        "results": records,
        "limitations": (
            "Requested 1500 Ry cutoff is provisional; stress and PAO basis are "
            "unconverged, and fixed input lattice is not equilibrium. "
            "20x20x20 is the densest screened k-grid in this refinement."
        ),
    }

    json_path = OUT / "fe_bulk_kpoint_refinement_summary.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n")

    fields = [
        "requested_k_points", "realized_fft_mesh", "energy_eV_per_Fe",
        "delta_energy_vs_k20_meV_per_Fe", "moment_muB_per_Fe",
        "delta_moment_vs_k20_muB_per_Fe", "pressure_static_kbar",
        "delta_pressure_vs_k20_kbar", "scf_iterations", "native_output",
    ]
    with (OUT / "fe_bulk_kpoint_refinement_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in fields} for row in records])

    lines = [
        "Alpha-Fe fixed-cell k-point refinement 14³–20³ (Gate 10A)",
        "=======================================================",
        "SIESTA PBE/DZP, approved Fe semicore PSML, 1500 Ry requested cutoff (72³ FFT), 300 K.",
        f"Energy span across 14³–20³: {e_span_mev:.4f} meV/Fe.",
        "",
        "k-grid   FFT-grid       E(eV/Fe)     dE(meV/Fe)  M(muB/Fe)  P(kbar)  SCF",
    ]
    for row in records:
        k = row["requested_k_points"][0]
        fft = "x".join(map(str, row["realized_fft_mesh"]))
        lines.append(
            f"{k:2d}x{k:2d}x{k:<2d} {fft:>10}  "
            f"{row['energy_eV_per_Fe']:14.7f} "
            f"{row['delta_energy_vs_k20_meV_per_Fe']:11.4f} "
            f"{row['moment_muB_per_Fe']:10.6f} "
            f"{row['pressure_static_kbar']:8.3f} "
            f"{row['scf_iterations']:3d}"
        )
    lines.append("")
    lines.append("Reference for dE, dM, dP is 20x20x20. Convergence threshold: dE <= 1.0 meV/Fe.")
    (OUT / "fe_bulk_kpoint_refinement_report.txt").write_text("\n".join(lines) + "\n")

    print(
        f"[K-REFINE] Gate 10A completed successfully. Energy span 14³–20³: {e_span_mev:.4f} meV/Fe.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
