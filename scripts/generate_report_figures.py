#!/usr/bin/env python3
"""Generate publication-quality figures for the Preliminary Simulation Activity Report.
Figures:
  1. Alpha-Fe bulk Equation of State (Birch-Murnaghan fit)
  2. Numerical convergence of bulk Fe (MeshCutoff / Realized Grid and k-points)
  3. Fe(110) surface diagnostics (Surface energy, interlayer relaxations, V_bar(z), magnetic moments)
  4. 8-Hydroxyquinoline (8-HQ) inhibitor structure and chelating sites
"""
import io
import json
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from ase.io import read

# Style configurations
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 14,
    'lines.linewidth': 1.8,
    'axes.grid': True,
    'grid.alpha': 0.35,
    'grid.linestyle': '--',
})

OUT_FIG = Path("outputs/figures")
OUT_FIG.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# Figure 1: Alpha-Fe bulk Equation of State
# -------------------------------------------------------------
def plot_eos():
    eos_data = json.loads(Path("outputs/fe_bulk_eos_summary.json").read_text())
    res = eos_data["results"]
    a_vals = np.array([r["lattice_param_a_A"] for r in res])
    v_vals = np.array([r["volume_cell_A3"] for r in res])
    e_vals = np.array([r["energy_eV_per_Fe"] for r in res])

    fit = eos_data["eos_fit"]
    v0 = fit["equilibrium_volume_cell_A3"]
    e0 = fit["equilibrium_energy_per_Fe_eV"]
    b0_gpa = fit["bulk_modulus_B0_GPa"]
    b1 = 4.0  # standard BM 3rd order derivative
    a0 = fit["equilibrium_lattice_param_a0_A"]

    # Generate analytical curve
    v_dense = np.linspace(v_vals.min() * 0.98, v_vals.max() * 1.02, 300)
    a_dense = (v_dense)**(1.0 / 3.0)

    # Birch-Murnaghan equation
    eta = (v0 / v_dense)**(2.0 / 3.0)
    e_bm = e0 + (9.0 * (v0 * 1e-30) * (b0_gpa * 1e9) / (16.0 * 1.602176634e-19 * 2.0)) * (
        (eta - 1.0)**3 * b1 + (eta - 1.0)**2 * (6.0 - 4.0 * eta)
    )

    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=300)
    ax.plot(a_dense, e_bm, color='#1f77b4', lw=2.2, label=f'Ajuste Birch-Murnaghan ($a_0 = {a0:.3f}\\ \\mathrm{{\\AA}}$)')
    ax.scatter(a_vals, e_vals, color='#d62728', s=60, zorder=5, label='Pontos DFT (SIESTA PBE/DZP)')

    # Anchor point MP
    anchor_a = 2.8630355
    anchor_idx = np.argmin(np.abs(a_vals - anchor_a))
    ax.scatter([a_vals[anchor_idx]], [e_vals[anchor_idx]], color='#2ca02c', marker='s', s=110, zorder=6,
               label=f'Âncora Materials Project ($a = {anchor_a:.3f}\\ \\mathrm{{\\AA}}$)')

    # Equilibrium marker
    ax.scatter([a0], [e0], color='#ff7f0e', marker='*', s=200, zorder=6,
               label=f'Mínimo $E_0 = {e0:.4f}\\ \\mathrm{{eV/Fe}}$')

    ax.set_xlabel('Parâmetro de Rede $a$ (Å)')
    ax.set_ylabel('Energia Total por Átomo (eV/Fe)')
    ax.set_title(r'Equação de Estado do $\alpha$-Fe CCC (Birch-Murnaghan)')
    ax.legend(frameon=True, facecolor='white', framealpha=0.9, loc='upper center')

    info_box = (f"$a_0 = {a0:.4f}\\ \\mathrm{{\\AA}}$ (calc)\n"
                f"$a_{{\\mathrm{{exp}}}} = 2.8660\\ \\mathrm{{\\AA}}$ (exp)\n"
                f"$\\Delta a = -2.17\\%$\n"
                f"$B_0 = {b0_gpa:.1f}\\ \\mathrm{{GPa}}$")
    ax.text(0.05, 0.40, info_box, transform=ax.transAxes, fontsize=10,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#f0f4f8', edgecolor='#b0c4de'))

    plt.tight_layout()
    fig_path = OUT_FIG / "fig1_fe_bulk_eos.png"
    plt.savefig(fig_path)
    plt.close()
    print(f"Generated {fig_path}")


# -------------------------------------------------------------
# Figure 2: Bulk Fe numerical convergence
# -------------------------------------------------------------
def plot_bulk_convergence():
    # 1. Mesh cutoff data
    grid_data = json.loads(Path("outputs/fe_bulk_realized_grid_summary.json").read_text())["results"]
    grid_used_ry = [r["native_used_cutoff_Ry"] for r in grid_data]
    grid_de_mev = [r["delta_E_vs_1500_meV_per_Fe"] for r in grid_data]
    grid_mesh = [f"{r['realized_fft_mesh'][0]}³" for r in grid_data]

    # 2. k-point refinement data
    kpt_data = json.loads(Path("outputs/fe_bulk_kpoint_refinement_summary.json").read_text())["results"]
    kpt_n = [r["requested_k_points"][0] for r in kpt_data]
    kpt_de_mev = [r["delta_energy_vs_k20_meV_per_Fe"] for r in kpt_data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8), dpi=300)

    # Panel A: Mesh Cutoff
    ax1.plot(grid_used_ry, grid_de_mev, marker='o', color='#2b5c8f', lw=2)
    for ry, de, m in zip(grid_used_ry, grid_de_mev, grid_mesh):
        ax1.annotate(m, (ry, de), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=9)
    ax1.axhline(0, color='gray', linestyle=':', lw=1.2)
    ax1.set_xlabel('MeshCutoff Efetivo Utilizado (Ry)')
    ax1.set_ylabel(r'$\Delta E$ relativo à malha $72^3$ (meV/Fe)')
    ax1.set_title('(a) Convergência de Malha FFT Discreta')

    # Panel B: k-points
    ax2.plot(kpt_n, kpt_de_mev, marker='s', color='#c0392b', lw=2)
    ax2.axhline(0, color='gray', linestyle=':', lw=1.2)
    ax2.axhspan(-1.0, 1.0, color='green', alpha=0.12, label='Critério de Convergência (±1 meV/Fe)')
    ax2.set_xlabel(r'Densidade da Malha k ($N \times N \times N$)')
    ax2.set_ylabel(r'$\Delta E$ relativo à $20^3$ (meV/Fe)')
    ax2.set_title(r'(b) Convergência na Zona de Brillouin ($k$-grid)')
    ax2.set_xticks(kpt_n)
    ax2.set_xticklabels([f"{n}³" for n in kpt_n])
    ax2.legend(loc='lower right')

    plt.tight_layout()
    fig_path = OUT_FIG / "fig2_fe_bulk_convergence.png"
    plt.savefig(fig_path)
    plt.close()
    print(f"Generated {fig_path}")


# -------------------------------------------------------------
# Figure 3: Fe(110) Surface Diagnostics
# -------------------------------------------------------------
def plot_surface_diagnostics():
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=300)

    # (a) Surface Energy vs Slab Thickness
    slabs = ['Fe(110) 7 Camadas\n(14 átomos)', 'Fe(110) 9 Camadas\n(18 átomos)']
    gamma_unrel = [3.6718, 3.6686]
    gamma_rel = [3.5709, 3.5476]

    x = np.arange(len(slabs))
    width = 0.35

    rects1 = axes[0, 0].bar(x - width/2, gamma_unrel, width, label=r'Não Relaxada ($\gamma_{\mathrm{unrel}}$)', color='#85929e')
    rects2 = axes[0, 0].bar(x + width/2, gamma_rel, width, label=r'Relaxada BFGS ($\gamma_{\mathrm{rel}}$)', color='#2e86c1')
    axes[0, 0].set_ylabel(r'Energia de Superfície $\gamma_{(110)}$ ($\mathrm{J/m^2}$)')
    axes[0, 0].set_title(r'(a) Energia de Superfície Fe(110) vs. Espessura')
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(slabs)
    axes[0, 0].set_ylim(3.2, 3.9)
    axes[0, 0].legend()

    for rect in rects1:
        h = rect.get_height()
        axes[0, 0].annotate(f'{h:.4f}', xy=(rect.get_x() + rect.get_width()/2, h),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
    for rect in rects2:
        h = rect.get_height()
        axes[0, 0].annotate(f'{h:.4f}', xy=(rect.get_x() + rect.get_width()/2, h),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # (b) Interlayer relaxation delta d / d0
    layers_labels = ['$d_{12}$ (externo)', '$d_{23}$ (subsuperfície)']
    delta_l07 = [-3.2, 1.4]
    delta_l09 = [-4.8, -2.8]

    x2 = np.arange(len(layers_labels))
    axes[0, 1].bar(x2 - width/2, delta_l07, width, label='Slab L=7', color='#e67e22')
    axes[0, 1].bar(x2 + width/2, delta_l09, width, label='Slab L=9', color='#16a085')
    axes[0, 1].axhline(0, color='gray', linestyle='--', lw=1)
    axes[0, 1].set_ylabel(r'Relaxação Interplanar $\Delta d / d_0$ (%)')
    axes[0, 1].set_title('(b) Contração / Expansão Interplanar Relativa')
    axes[0, 1].set_xticks(x2)
    axes[0, 1].set_xticklabels(layers_labels)
    axes[0, 1].legend()

    # (c) Planar Electrostatic Potential V(z)
    l07_rel = json.load(open('runs/13_fe110_surface_relaxation/Fe110_L07_V15A/02_relax_bfgs/result.json'))
    v_z = np.array(l07_rel['v_z'])
    z_coords = np.linspace(0, 27.17, len(v_z))
    e_fermi = l07_rel['fermi_energy_eV']
    v_vac = l07_rel['vacuum_level_eV']
    phi = v_vac - e_fermi

    axes[1, 0].plot(z_coords, v_z, color='#8e44ad', lw=2, label=r'$\bar{V}(z)$ Eletrostático')
    axes[1, 0].axhline(v_vac, color='#27ae60', linestyle='--', label=f'Nível de Vácuo $V_{{\\mathrm{{vac}}}} = {v_vac:.3f}\\ \\mathrm{{eV}}$')
    axes[1, 0].axhline(e_fermi, color='#c0392b', linestyle=':', label=f'Nível de Fermi $E_{{\\mathrm{{F}}}} = {e_fermi:.3f}\\ \\mathrm{{eV}}$')
    axes[1, 0].annotate(f'Função de Trabalho\n$\\Phi = {phi:.2f}\\ \\mathrm{{eV}}$',
                        xy=(23.5, (v_vac + e_fermi)/2),
                        xytext=(16, (v_vac + e_fermi)/2 - 1.5),
                        arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=6),
                        fontsize=10, bbox=dict(boxstyle='round', facecolor='#f9ebea', edgecolor='#c0392b'))
    axes[1, 0].set_xlabel('Coordenada normal $z$ (Å)')
    axes[1, 0].set_ylabel('Potencial Eletrostático Médio (eV)')
    axes[1, 0].set_title(r'(c) Perfil de Potencial Planar e Função de Trabalho')
    axes[1, 0].legend(loc='lower left', fontsize=9)

    # (d) Layer-resolved Magnetic Moments
    l07_spins = np.array(l07_rel['mulliken_spins'])
    pos_l07 = read('outputs/surfaces/POSCAR_Fe110_L07_V15A_relaxed', format='vasp')
    z_l07 = pos_l07.positions[:, 2]
    unique_z = np.sort(np.unique(np.round(z_l07, 1)))
    layer_m_l07 = []
    for uz in unique_z:
        mask = np.abs(z_l07 - uz) < 0.35
        layer_m_l07.append(float(np.mean(l07_spins[mask])))

    layer_idx_l07 = np.arange(1, len(layer_m_l07) + 1)
    axes[1, 1].plot(layer_idx_l07, layer_m_l07, marker='o', color='#d35400', lw=2, label='Fe(110) L=7')
    axes[1, 1].axhline(2.25, color='gray', linestyle='--', label=r'Bulk $\alpha$-Fe ($2.25\ \mu_\mathrm{B}$)')
    axes[1, 1].set_xlabel('Índice da Camada Atômica (1 = Superfície Inferior)')
    axes[1, 1].set_ylabel(r'Momento Magnético Local ($\mu_\mathrm{B}$)')
    axes[1, 1].set_title('(d) Perfil de Momento Magnético por Camada')
    axes[1, 1].set_xticks(layer_idx_l07)
    axes[1, 1].legend()

    plt.tight_layout()
    fig_path = OUT_FIG / "fig3_fe110_surface_diagnostics.png"
    plt.savefig(fig_path)
    plt.close()
    print(f"Generated {fig_path}")


# -------------------------------------------------------------
# Figure 4: 8-Hydroxyquinoline (8-HQ) Molecular Structure
# -------------------------------------------------------------
def plot_8hq_molecule():
    # Fetch 3D conformer from PubChem
    url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/1923/record/SDF/?record_type=3d&response_type=display"
    req = urllib.request.Request(url, headers={'User-Agent': 'MaterialsSimulation/1.0'})
    with urllib.request.urlopen(req) as resp:
        sdf_text = resp.read().decode('utf-8')
    mol = read(io.StringIO(sdf_text), format='sdf')

    # 3D scatter plot of the molecule
    fig = plt.figure(figsize=(9, 6.5), dpi=300)
    ax = fig.add_subplot(111, projection='3d')

    coords = mol.positions
    symbols = mol.get_chemical_symbols()

    color_map = {'C': '#34495e', 'H': '#bdc3c7', 'N': '#2980b9', 'O': '#c0392b'}
    size_map = {'C': 180, 'H': 70, 'N': 240, 'O': 240}

    # Plot bonds
    for i in range(len(mol)):
        for j in range(i + 1, len(mol)):
            dist = np.linalg.norm(coords[i] - coords[j])
            if dist < 1.65:  # Bond threshold
                ax.plot([coords[i, 0], coords[j, 0]],
                        [coords[i, 1], coords[j, 1]],
                        [coords[i, 2], coords[j, 2]],
                        color='#7f8c8d', lw=2.5, zorder=1)

    # Plot atoms
    for sym in ['C', 'H', 'N', 'O']:
        mask = [s == sym for s in symbols]
        pts = coords[mask]
        if len(pts) > 0:
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                       color=color_map[sym], s=size_map[sym], edgecolor='black', lw=1.2,
                       label=f'{sym} ({len(pts)})', depthshade=True, zorder=3)

    # Annotate chelating sites: N and O
    n_idx = symbols.index('N')
    o_idx = symbols.index('O')

    ax.text(coords[n_idx, 0] + 0.3, coords[n_idx, 1] + 0.3, coords[n_idx, 2],
            "N (piridínico)\n[Par isolado $\\sigma$]", color='#1b4f72', fontweight='bold', fontsize=10)
    ax.text(coords[o_idx, 0] - 0.4, coords[o_idx, 1] + 0.4, coords[o_idx, 2],
            "O (fenólico)\n[-OH quelante]", color='#922b21', fontweight='bold', fontsize=10)

    ax.set_title(r"Molécula Inibidora 8-Hidroxiquinolina (8-HQ, $\mathrm{C_9H_7NO}$)" + "\nCentros Quelantes Bidentados", fontsize=12)
    ax.set_axis_off()
    ax.legend(loc='upper right', frameon=True)
    ax.view_init(elev=25, azim=-60)

    plt.tight_layout()
    fig_path = OUT_FIG / "fig4_8hq_inhibitor_molecule.png"
    plt.savefig(fig_path)
    plt.close()
    print(f"Generated {fig_path}")


if __name__ == "__main__":
    plot_eos()
    plot_bulk_convergence()
    plot_surface_diagnostics()
    plot_8hq_molecule()
    print("All report figures successfully generated in outputs/figures/")
