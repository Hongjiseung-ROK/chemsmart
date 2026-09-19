#!/usr/bin/env python
"""PySCF's own numbers for an archived ChemSmart PySCF IRC artifact.

Runs in the compute env, imports pyscf and numpy, never chemsmart and never
geomeTRIC. Rebuilds the mean field from the artifact's applied spec and
recomputes what the IRC stage claims with PySCF's public API:

* the harmonic spectrum of the stored start Hessian at the supplied
  geometry, and the transition vector as the lowest eigenvector of that
  Hessian mass-weighted and projected free of rigid motion;
* the SCF energy and the gradient at the supplied geometry, the SCF energy
  at the endpoint, and the energy and gradient at two interior frames;
* an account of the path that shares no code with the integrator that
  walked it: each accepted step, superposed on the frame before it by the
  mass-weighted Kabsch rotation, against the negative mass-weighted
  gradient at both of its ends. An intrinsic reaction coordinate is the
  steepest-descent path in mass-weighted coordinates, so the cosines say
  whether the recorded path is that path of the recorded surface.

Writes reference.json beside the .h5 with the command that produced it.

Usage: <compute-env>/python reference_irc.py FILE.h5
"""

import json
import sys

import h5py
import numpy as np
import pyscf
from pyscf import dft, gto, scf
from pyscf.data import nist
from pyscf.hessian import thermo


def _read(handle, name):
    if name not in handle:
        return None
    node = handle[name]
    if not isinstance(node, h5py.Dataset):
        return None
    if bool(node.attrs.get("chemsmart_is_null", False)):
        return None
    value = node[()]
    if isinstance(value, bytes):
        return value.decode()
    return value


def _mean_field(spec, mol):
    xc = spec.get("xc")
    if xc is None:
        mf = scf.HF(mol)
    else:
        mf = dft.KS(mol, xc=xc)
        grid = spec.get("atom_grid")
        if grid is not None and len(grid):
            mf.grids.atom_grid = tuple(int(item) for item in grid)
    if spec.get("scf_tol") is not None:
        mf.conv_tol = float(spec["scf_tol"])
    if spec.get("scf_maxiter") is not None:
        mf.max_cycle = int(spec["scf_maxiter"])
    return mf


def _mole(spec, positions):
    symbols = [
        item.decode() if isinstance(item, bytes) else str(item)
        for item in spec["symbols"]
    ]
    return gto.M(
        atom=[
            (s, tuple(float(v) for v in row))
            for s, row in zip(symbols, positions)
        ],
        basis=spec["basis"],
        charge=int(spec["charge"]),
        spin=int(spec["spin"]),
        unit="Angstrom",
        verbose=0,
    )


def _energy_and_gradient(spec, positions, *, gradient=True):
    mol = _mole(spec, positions)
    mf = _mean_field(spec, mol)
    energy = float(mf.kernel())
    grad = mf.nuc_grad_method().kernel() if gradient else None
    return (
        energy,
        (np.asarray(grad, dtype=float) if grad is not None else None),
        bool(mf.converged),
    )


def _superpose(previous, current, masses):
    """Rotate ``current`` onto ``previous`` (mass-weighted Kabsch)."""
    w = np.asarray(masses, dtype=float)
    a = np.asarray(previous, dtype=float)
    b = np.asarray(current, dtype=float)
    ca = (w[:, None] * a).sum(0) / w.sum()
    cb = (w[:, None] * b).sum(0) / w.sum()
    covariance = (w[:, None] * (b - cb)).T @ (a - ca)
    u, _s, vt = np.linalg.svd(covariance)
    handed = float(np.sign(np.linalg.det(vt.T @ u.T))) or 1.0
    rotation = vt.T @ np.diag([1.0, 1.0, handed]) @ u.T
    return (b - cb) @ rotation.T + ca, rotation


def _rigid_projector(positions, masses):
    """Projector out of translations and rotations in mass-weighted space."""
    w = np.sqrt(np.asarray(masses, dtype=float))
    x = np.asarray(positions, dtype=float)
    x = x - (np.asarray(masses)[:, None] * x).sum(0) / np.sum(masses)
    n = len(masses)
    vectors = []
    for axis in range(3):
        v = np.zeros((n, 3))
        v[:, axis] = w
        vectors.append(v.ravel())
    for axis in range(3):
        e = np.zeros(3)
        e[axis] = 1.0
        v = np.cross(e, x) * w[:, None]
        vectors.append(v.ravel())
    basis = np.linalg.qr(np.array(vectors).T)[0]
    keep = np.linalg.svd(np.array(vectors).T, compute_uv=False) > 1e-8
    basis = basis[:, : int(keep.sum())]
    return np.eye(3 * n) - basis @ basis.T


def main(path):
    with h5py.File(path, "r") as handle:
        spec = {key: _read(handle["spec"], key) for key in handle["spec"]}
        irc_status = {
            key: _read(handle["status/stages/irc"], key)
            for key in handle["status/stages/irc"]
            if isinstance(handle["status/stages/irc"][key], h5py.Dataset)
        }
        irc = {
            key: _read(handle["results/irc"], key)
            for key in handle["results/irc"]
        }
        final_positions = _read(handle["results"], "positions")
        total_energy = _read(handle["results"], "total_energy")
    supplied = np.asarray(spec["positions"], dtype=float)
    record = {
        "source": path,
        "pyscf_version": pyscf.__version__,
        "command": " ".join(sys.argv),
        "requested_direction": spec.get("irc_direction"),
        "irc_status": {
            k: (v.tolist() if hasattr(v, "tolist") else v)
            for k, v in irc_status.items()
        },
    }
    natm = len(spec["symbols"])

    # The start: spectrum of the stored Hessian, and the transition vector.
    hessian = np.asarray(irc["start_hessian"], dtype=float)
    mol0 = _mole(spec, supplied)
    analysis = thermo.harmonic_analysis(mol0, hessian, imaginary_freq=False)
    frequencies = np.asarray(analysis["freq_wavenumber"], dtype=float)
    record["start_frequencies_recomputed_cm1"] = frequencies.tolist()
    record["start_frequencies_max_abs_difference_cm1"] = float(
        np.max(
            np.abs(
                frequencies - np.asarray(irc["start_frequencies"], dtype=float)
            )
        )
    )
    masses = mol0.atom_mass_list(isotope_avg=True)
    matrix = hessian.transpose(0, 2, 1, 3).reshape(3 * natm, 3 * natm)
    inv_sqrt = 1.0 / np.sqrt(np.repeat(masses, 3))
    weighted = matrix * np.outer(inv_sqrt, inv_sqrt)
    projector = _rigid_projector(supplied / nist.BOHR, masses)
    weighted = projector @ weighted @ projector
    values, vectors = np.linalg.eigh(weighted)
    lowest = vectors[:, 0] * inv_sqrt  # back to Cartesian displacements
    lowest /= np.linalg.norm(lowest)
    recorded = (
        np.asarray(irc.get("transition_mode"), dtype=float).ravel()
        if irc.get("transition_mode") is not None
        else None
    )
    if recorded is not None and recorded.size:
        record["transition_mode_cosine_with_recomputed"] = float(
            abs(recorded @ lowest) / np.linalg.norm(recorded)
        )

    # Energies and gradients at stored geometries, recomputed.
    frames = np.asarray(irc["path_positions"], dtype=float)
    energies = np.asarray(irc["path_energies"], dtype=float)
    gradients = np.asarray(irc["path_gradients"], dtype=float)
    e0, g0, c0 = _energy_and_gradient(spec, supplied)
    record["start_energy_recomputed_eh"] = e0
    record["start_energy_minus_path_first_eh"] = float(e0 - energies[0])
    record["start_max_abs_gradient_recomputed_eh_per_bohr"] = float(
        np.max(np.abs(g0))
    )
    record["start_gradient_max_abs_difference_eh_per_bohr"] = float(
        np.max(np.abs(g0 - gradients[0]))
    )
    checks = []
    for index in sorted({1, len(frames) // 2}):
        if index >= len(frames):
            continue
        e, g, c = _energy_and_gradient(spec, frames[index])
        checks.append(
            {
                "frame": int(index),
                "energy_recomputed_eh": e,
                "energy_minus_recorded_eh": float(e - energies[index]),
                "gradient_max_abs_difference_eh_per_bohr": float(
                    np.max(np.abs(g - gradients[index]))
                ),
                "scf_converged": c,
            }
        )
    record["interior_frames"] = checks
    if final_positions is not None:
        e_end, _g, c_end = _energy_and_gradient(
            spec, final_positions, gradient=False
        )
        record["end_energy_recomputed_eh"] = e_end
        record["end_energy_minus_total_energy_eh"] = (
            float(e_end - float(total_energy))
            if total_energy is not None
            else None
        )
        record["end_matches_last_frame_angstrom"] = float(
            np.max(np.abs(np.asarray(final_positions) - frames[-1]))
        )

    # The path against steepest descent, in mass-weighted coordinates.
    path_masses = np.asarray(irc["path_masses"], dtype=float)
    sqrt_m = np.sqrt(np.repeat(path_masses, 3))
    switch = irc_status.get("switch_after_iteration")
    last_path_step = len(frames) - 1
    if switch is not None and np.size(switch):
        last_path_step = min(
            last_path_step, int(np.asarray(switch).ravel()[0])
        )
    cosines = []
    for k in range(last_path_step):
        moved, rotation = _superpose(frames[k], frames[k + 1], path_masses)
        step = (moved - frames[k]).ravel() * sqrt_m
        g_start = gradients[k].ravel() / sqrt_m
        g_end = (gradients[k + 1] @ rotation.T).ravel() / sqrt_m
        mean = -(
            g_start / np.linalg.norm(g_start) + g_end / np.linalg.norm(g_end)
        )
        if np.linalg.norm(step) == 0 or np.linalg.norm(mean) == 0:
            continue
        cosines.append(
            float(step @ mean / (np.linalg.norm(step) * np.linalg.norm(mean)))
        )
    record["steepest_descent_cosines"] = cosines
    if cosines:
        record["steepest_descent_cosine_min"] = (
            float(min(cosines[1:])) if len(cosines) > 1 else None
        )
        record["steepest_descent_cosine_median"] = float(np.median(cosines))
        record["steepest_descent_note"] = (
            "step k is compared with the mean of the unit negative "
            "mass-weighted gradients at its two ends; the first step leaves "
            "the saddle along the transition vector, where the gradient is "
            "near zero, so it is excluded from the minimum"
        )
    if len(frames) > 1:
        moved, _rotation = _superpose(frames[0], frames[1], path_masses)
        first = (moved - frames[0]).ravel()
        record["first_step_cosine_with_recomputed_mode"] = float(
            first @ lowest / np.linalg.norm(first)
        )
    out = path[: -len(".h5")] + ".reference.json"
    with open(out, "w") as handle:
        json.dump(record, handle, indent=1, default=float)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
