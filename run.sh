#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export SIESTA_PS_PATH="${SIESTA_PS_PATH:-$HOME/Pacotes/PSEUDOS/DOJO-PSML}"
SIESTA_MPI_RANKS="${SIESTA_MPI_RANKS:-2}"
if ! [[ "$SIESTA_MPI_RANKS" =~ ^[1-4]$ ]]; then
  echo "ERROR: this screening permits 1–4 MPI ranks (default 2)." >&2
  exit 10
fi
export SIESTA_MPI_RANKS OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

if ! command -v siesta >/dev/null 2>&1 || ! command -v mpirun >/dev/null 2>&1; then
  echo "ERROR: siesta and mpirun must be available in PATH." >&2
  exit 11
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python interpreter not found: $PYTHON_BIN" >&2
  exit 12
fi

if ! "$PYTHON_BIN" -c "from ase.calculators.siesta import Siesta; import numpy" >/dev/null 2>&1; then
  if [[ -x .venv-step02/bin/python ]] && .venv-step02/bin/python -c "from ase.calculators.siesta import Siesta; import numpy" >/dev/null 2>&1; then
    PYTHON_BIN="$ROOT_DIR/.venv-step02/bin/python"
  else
    echo "[Step 03] Installing prerequisites in a project-local Python virtual environment."
    python3 -m venv .venv-step02
    "$ROOT_DIR/.venv-step02/bin/python" -m pip install --upgrade pip setuptools wheel
    "$ROOT_DIR/.venv-step02/bin/python" -m pip install -r requirements-step02.txt
    PYTHON_BIN="$ROOT_DIR/.venv-step02/bin/python"
  fi
fi

mkdir -p outputs logs
# Optional local secrets file (never committed): MP_API_KEY=...
SECRETS_FILE="${CORROSAO_SECRETS_FILE:-$HOME/.config/corrosao/secrets.env}"
if [[ -z "${MP_API_KEY:-}" && -r "$SECRETS_FILE" ]]; then
  set -a; source "$SECRETS_FILE"; set +a
fi
if [[ ! -s outputs/POSCAR_Fe_bulk || ! -s outputs/Fe_bulk_metadata.json ]]; then
  if [[ -z "${MP_API_KEY:-}" ]]; then
    echo "ERROR: validated bulk Fe prerequisite missing; export MP_API_KEY for Materials Project retrieval." >&2
    exit 13
  fi
  if ! "$PYTHON_BIN" -c "from mp_api.client import MPRester; import pymatgen.core, ase" >/dev/null 2>&1; then
    if [[ ! -x .venv-step02/bin/python ]] || ! .venv-step02/bin/python -c "from mp_api.client import MPRester; import pymatgen.core, ase" >/dev/null 2>&1; then
      python3 -m venv .venv-step02
      .venv-step02/bin/python -m pip install --upgrade pip setuptools wheel
      .venv-step02/bin/python -m pip install -r requirements-step02.txt
    fi
    PYTHON_BIN="$ROOT_DIR/.venv-step02/bin/python"
  fi
  echo "[Step 03] Reconstructing the Materials Project alpha-Fe bulk prerequisite."
  "$PYTHON_BIN" scripts/01_fetch_fe_bulk.py 2>&1 | tee logs/01_fetch_fe_bulk.log
else
  echo "[Step 03] Reusing the validated local bulk alpha-Fe reference."
fi

echo "[Step 03] Refreshing actual local Fe/O PSML + ASE preflight."
"$PYTHON_BIN" scripts/04_audit_siesta_pseudos.py 2>&1 | tee logs/04_siesta_preflight.log

SIESTA_BIN="$(command -v siesta)"
export ASE_SIESTA_COMMAND="mpirun -np $SIESTA_MPI_RANKS $SIESTA_BIN < PREFIX.fdf > PREFIX.out"
if [[ ! -s outputs/fe_bulk_siesta_pilot_summary.json ]]; then
  echo "[Step 03] Initial validated pilot absent; running it once before numerical screening."
  "$PYTHON_BIN" scripts/05_siesta_fe_bulk_pilot.py 2>&1 | tee logs/05_siesta_fe_bulk_pilot.log
else
  echo "[Step 03] Reusing previously completed alpha-Fe bulk pilot."
fi

# Reviewed gates are replayed on a fresh clone/machine so that every
# prerequisite of the current gate is produced by the local SIESTA build.
run_reviewed_gate() {
  local summary="$1" script="$2" log="$3" label="$4"
  if [[ ! -s "$summary" ]]; then
    echo "[Step 03] Reviewed gate absent locally; replaying: $label"
    "$PYTHON_BIN" "$script" 2>&1 | tee "$log"
    if [[ ! -s "$summary" ]]; then
      echo "ERROR: replay of reviewed gate did not produce $summary" >&2
      exit 16
    fi
  else
    echo "[Step 03] Reusing reviewed gate: $label"
  fi
}
run_reviewed_gate outputs/fe_bulk_mesh_cutoff_summary.json \
  scripts/06_fe_bulk_mesh_cutoff_screen.py logs/06_fe_bulk_mesh_cutoff.log \
  "MeshCutoff screen 250–550 Ry (script 06)"
run_reviewed_gate outputs/fe_bulk_mesh_cutoff_extension_summary.json \
  scripts/07_fe_bulk_mesh_cutoff_extension.py logs/07_fe_bulk_mesh_cutoff_extension.log \
  "MeshCutoff extension 550–850 Ry (script 07)"
run_reviewed_gate outputs/fe_bulk_realized_grid_summary.json \
  scripts/08_fe_bulk_realized_grid_screen.py logs/08_fe_bulk_realized_grid.log \
  "realized FFT-grid screen 850–1500 Ry (script 08)"
run_reviewed_gate outputs/fe_bulk_kpoint_summary.json \
  scripts/09_fe_bulk_kpoint_screen.py logs/09_fe_bulk_kpoint_screen.log \
  "k-point screen 6x6x6–14x14x14 (script 09)"
run_reviewed_gate outputs/fe_bulk_kpoint_refinement_summary.json \
  scripts/10_fe_bulk_kpoint_refinement.py logs/10_fe_bulk_kpoint_refinement.log \
  "k-point refinement 14³–20³ (script 10)"
run_reviewed_gate outputs/fe_bulk_pao_basis_summary.json \
  scripts/11_fe_bulk_pao_basis_screen.py logs/11_fe_bulk_pao_basis_screen.log \
  "PAO basis and EnergyShift screen (script 11)"
echo "[Step 03] Performing Gate 12: Equation of State E(a) and equilibrium lattice constant a_0."
echo "[Step 03] Sampled lattice constants a in [2.780, 2.820, 2.840, 2.863, 2.880, 2.910, 2.950] Å."
echo "[Step 03] MPI ranks: $SIESTA_MPI_RANKS; OpenMP and BLAS: 1 thread per rank."
"$PYTHON_BIN" scripts/12_fe_bulk_eos.py 2>&1 | tee logs/12_fe_bulk_eos.log
for result in outputs/fe_bulk_eos_summary.json outputs/fe_bulk_eos_summary.csv outputs/fe_bulk_eos_report.txt outputs/fe_bulk_eos.png logs/12_fe_bulk_eos.log; do
  if [[ ! -s "$result" ]]; then
    echo "ERROR: EOS result missing or empty: $result" >&2
    exit 20
  fi
done
echo "[Step 03] Gate 12 Equation of State finished. Return summary JSON, report TXT, plot PNG and wrapper log for review."
