# Archived PySCF results

Real PySCF 2.14.0 / libxc 7.0.0 runs produced on chemsmart-hpc on
2026-09-12 through the human CLI (`chemsmart run --no-fake --no-scratch
-n 4 -m 8 pyscf -p <project> -f <input> [-c C -m M] -l <label> <stage>`)
at commit b4fce1c7 (result contract v4); the three Hessians were re-run at cb99bbff after the runner stopped producing the `unclassified` word, so their receipts say `validated`. Each directory holds the
artifact (`.h5`), its three receipts (`.receipt.json`, `.input.json`,
`.environment.json`), PySCF's own log (`.out`, never parsed) and
`.reference.json`, PySCF's independent account of the same bytes written
by `reference.py` in the compute env (harmonic analysis and RRHO
thermochemistry from the stored Hessian, point group, isotope-averaged
masses). The generated driver script is deliberately not archived. The
receipts carry this host's paths, as the archived ORCA and xTB logs do;
admission compares digests, never paths.

| directory | what it is | why it is here |
|---|---|---|
| `water_sp` | B3LYP/def2-SVP single point at a distorted water (O–H 1.10 Å, 90°) | a green `sp`; supplied and final structures coincide |
| `water_opt` | the same start optimised (moved 0.083 Å) | supplied ≠ reached; `converged`; `energies` = [E(supplied), E(reached)] |
| `water_hess` | Hessian on the converged geometry (`-f water_opt.h5`) | three real modes; gradient 8e-6 Eh/Bohr; the thermochemistry differential oracle |
| `nh3_planar_opt` | exactly planar D3h ammonia optimised: stays planar | a converged saddle from a symmetric start |
| `nh3_planar_hess` | its Hessian: one imaginary mode at −830 cm⁻¹, two degenerate pairs | `failed_wrong_stationary_point` must be typed; PySCF's `detect_symm` says Cs at 1e-5 Bohr while the structure is D3h to 1e-14 Å in z |
| `hydroxyl_sp` | OH· UKS doublet single point | spin populations [1.026, −0.026]; ⟨S²⟩ 0.7518 |
| `water_opt_maxsteps1` | the distorted water with `opt_maxsteps: 1` | an unconverged optimisation: `results/positions` is the last evaluated geometry (0.066 Å from the input); receipt state `failed` |
| `water_stretched_hess` | Hessian at the converged water with O–H(1) +0.02 Å | three real frequencies at max\|g\| = 0.0185 Eh/Bohr: zero imaginary modes is not stationarity |
| `water_hess_historical_unclassified` | the water Hessian as the pre-cb99bbff runner wrote it: receipt `engine_complete` / `unclassified` | historical receipts keep admitting after the per-plan policy was retired |
| `water_sp_scfmaxiter2` | the distorted water with `scf_maxiter: 2` | a quiet SCF non-convergence: `normal_termination` false, `energies` present |

## Expansion round (2026-09-13, result contract v5)

Produced the same way at commit 9e219c8f (the driver's response,
excited-surface and correlated stages), on the relaxed water of
`inputs/water_relaxed.xyz` (the `water_opt` minimum) unless the row says
otherwise; the electronic state was bound on the command line (`-c 0 -m 1`,
`-c 0 -m 2` for the hydroxyl radical). `reference.py` rebuilds the mean
field from the applied spec and recomputes the TDA/TDDFT roots, oscillator
strengths and transition dipoles, or the MP2/CCSD/CCSD(T) components, with
PySCF's public API; every green fixture agrees with that recomputation to
1e-13 Eh (3e-5 Eh for the UKS hydroxyl case, an SCF re-convergence
difference) and every correlated total to 1e-8 Eh. `orca_differential/`
holds ORCA 6.1.1 runs on the same relaxed water: TDA with `B3LYP/G` (the
VWN3 functional PySCF's `b3lypg` names) agrees with `water_td_singlet` to
1 meV on all three roots and on every oscillator strength; MP2 with ORCA's
default frozen core reproduces `water_mp2_sp_fc1` (frozen_core 1) and
`NoFrozenCore` reproduces `water_mp2_sp` (PySCF's all-electron default),
each to 5e-8 Eh in the correlation energy -- the frozen-core divergence is
a convention, and both programs agree once it is named.

| directory | what it is | why it is here |
|---|---|---|
| `water_td_singlet` | TDA-B3LYP(G)/def2-SVP, three singlet roots | ascending roots, oscillator strengths, transition dipoles (Debye), per-root convergence; the ORCA differential |
| `water_td_triplet` | the triplet manifold | multiplicity 3 records, zero oscillator strengths |
| `water_td_rpa` | full TDDFT (RPA) singlets | differs from TDA on the same reference; both ascending |
| `hydroxyl_td_unrestricted` | OH· UKS-TDA, the one unrestricted manifold | no multiplicities, oscillator strengths served, no per-root ⟨S²⟩ |
| `water_td_cpcm_toluene` | TDA singlets under C-PCM toluene | the artifact records `static_eps_applied` 2.3741 and `response_eps_applied` 1.78: PySCF's non-equilibrium response uses water's optical dielectric for every solvent |
| `water_td_unconverged` | `td_max_cycle: 1` through the CLI | every root unconverged; `stages/td/converged` false; receipt `failed` -- the typed ending, with the per-root flags and energies still inspectable |
| `formaldehyde_s1_opt` | H₂CO from a symmetry-broken start (`inputs/formaldehyde_bent_start.xyz`), root 1 of **one** requested root | `excited_state_root == nstates`, the case where PySCF 2.14's scanner `converged` property raises; converged, final gradient 2.5e-5 Eh/Bohr, gap to the ground state 3.05 eV at the reached geometry |
| `formaldehyde_s1_opt_planar` | H₂CO from the exactly planar start, root 1 of three | a symmetric excited stationary point the host cannot characterise (no Hessian): planar stays planar, emission 3.406 eV, neighbour gap 4.59 eV |
| `water_s1_opt_degenerate` | water, root 1 of three | the followed root ends **degenerate with its neighbour** (gap 3e-6 eV) after a 0.52 Å move: root identity is undecidable from the index, which the gap sensor facts say |
| `formaldehyde_s1_td` | TDA singlets, three roots, on `inputs/formaldehyde_s1_reached.xyz` -- the XYZ `bind_reached_geometry` wrote from `formaldehyde_s1_opt` | the response consumer of an excited-surface producer over real bytes: supplied == reached to 5e-11 Å, root 1 is the producer's end gap (3.052 eV, the emission), the reference energies agree to 3e-12 Eh |
| `water_mp2_sp`, `water_mp2_sp_fc1` | MP2, all-electron and `frozen_core: 1` | `reference_energy`, `correlation_energy`, `total_energy`; the frozen-core convention against ORCA |
| `water_ccsd_sp`, `water_ccsdt_sp` | CCSD; CCSD(T) with `frozen_core: auto` (1 orbital applied) | `ccsd_correlation_energy`, `triples_correction`, `correlation_energy` = their sum |
| `hydroxyl_ump2_sp` | OH· UMP2 on a UHF reference | an open-shell correlated result |
| `water_mp2_opt`, `water_ccsd_opt` | the distorted water optimised on the MP2 and on the CCSD surface | correlated structure producers: amplitude and Λ convergence, final gradient 6e-6 Eh/Bohr, components at the reached geometry |
| `water_ccsd_unconverged` | `cc_max_cycle: 1` through the CLI | amplitudes unconverged; `stages/corr/converged` false; receipt `failed` |

## Surface round (2026-09-14, result contract v6)

Produced the same way in the compute env, on the distorted water of
`inputs/water_distorted.xyz`, with `reference.py` beside each. These
four are the first artifacts to record a `surface`: the electronic
surface a result's geometry and total energy belong to. They exist as a
matched and a mismatched pair, because the question a Hessian answers is
about one surface and the host had no way to ask which.

| directory | what it is | why it is here |
|---|---|---|
| `water_mp2_opt_v6` | MP2/def2-SVP optimisation | surface `mp2:rhf:-:def2-svp:0:1:-:-:-:-:0:-:-:-`; all-electron, so the frozen-core count is 0 rather than absent |
| `water_dft_hess_on_mp2_geometry` | B3LYP Hessian on that MP2 minimum (`-f water_mp2_opt.h5`) | the mismatch: a validated Hessian that characterises a *different* surface from the geometry it consumed |
| `water_dft_opt_v6` | B3LYP/def2-SVP optimisation of the same start | surface `dft:rks:b3lypg:def2-svp:0:1:-:-:-:-:-:-:-:-` |
| `water_dft_hess_on_dft_geometry` | B3LYP Hessian on that B3LYP minimum | the control: same surface, so the Hessian characterises the structure |

One measurement worth keeping beside them. A B3LYP Hessian at the
geometry the S1 (TDA root 1) optimisation of formaldehyde reached is
refused by the validator as `pyscf.result.hessian_invalid`: PySCF's
analytic Hessian there carries a raw antisymmetry of 5.0e-05 Eh/Bohr^2
against a limit calibrated near stationarity, because the ground state
at that geometry is not stationary at all -- its gradient is 0.0998
Eh/Bohr. A cross-surface Hessian is not merely uninformative; at a
geometry far from its own stationary point it is numerically worse too.

### Numerical Hessians (same round)

PySCF differentiates an HF or DFT energy twice analytically and does not
differentiate a TDA root, an MP2 or a CCSD energy twice at all, so the
curvature of those surfaces is reached by differencing the analytic
gradient the driver already has: 6N evaluations, central, step 0.005 A.
The step, in both units, how many gradients it cost, and whether every
displaced point converged are recorded on the `hess` stage beside the
frequencies.

| directory | what it is | why it is here |
|---|---|---|
| `water_hess_fd` | the water Hessian again, `--hessian-derivative finite_difference` | the differential oracle: 1638.741 / 3791.985 / 3886.980 cm-1 against the analytic 1638.699 / 3791.587 / 3886.729, max delta 0.40 cm-1 in 18 gradients |
| `formaldehyde_s1_planar_hess` | the curvature of the S1 (TDA root 1) surface at the relaxed planar stationary point of `formaldehyde_s1_opt_planar` | one imaginary mode at -503.9 cm-1, at a maximum S1 gradient of 9.1e-06 Eh/Bohr: a true stationary point of that surface and not its minimum. Round 2 delivered this shape of structure as "the S1 geometry" because no Hessian of an excited surface existed |

Two facts these runs settled. A numerical Hessian's raw asymmetry is
truncation error, not quadrature noise: 4.4e-05 Eh/Bohr^2 on water at
0.005 A against an analytic-Hessian limit of 1.1e-05, with frequencies
agreeing to 0.40 cm-1. Nobody here derived a limit for it, so it is
recorded and never graded. And the gradient a Hessian stage records is
the gradient of the surface it differentiated: at the planar S1 point
the mean field's own gradient is 0.133 Eh/Bohr while S1's is 9.1e-06,
and reporting the first would call a stationary point of one surface far
from stationary using a number belonging to another.


## SCF stability round (2026-09-19, result contract v7)

Produced in the compute env of the CUHK Charles cluster through the human
CLI (`chemsmart run --no-fake --no-scratch -n 4 -m 8 pyscf -p <project>
-f <input> -c C -m M -l <label> sp`) against the worktree of this commit,
with `reference.py` beside each. Every one has receipt `validated`,
`fake: false`, no findings. The molecules: the `water_opt` minimum of
`inputs/water_relaxed.xyz`, dioxygen at its experimental 1.2075 A bond
(`inputs/dioxygen.xyz`), and a single hydrogen atom
(`inputs/hydrogen_atom.xyz`), which is the one-electron open shell
`pyscf.scf.HF` builds as `rohf.HF1e`.

These are the first artifacts to record whether the converged reference
is a minimum in orbital-rotation space, under
`status/properties/scf_stability`. They exist because `external` is not
one question, and because PySCF answers one of the questions it solves
only to its log.

| directory | what it is | why it is here |
|---|---|---|
| `water_sp_stability` | B3LYP(G)/def2-SVP at the relaxed water | the stable control: internal and RHF/RKS -> UHF/UKS both stable |
| `water_sp_no_stability` | the same run with `scf_stability: false` | the absence written down: `not_requested`, which is not a failure and is never read as stable |
| `o2_singlet_sp_stability` | closed-shell singlet O2, B3LYP(G)/def2-SVP | internally stable, **RHF/RKS -> UHF/UKS unstable**: two electrons forced into one of a degenerate pi* pair, with a lower spin-broken solution |
| `o2_singlet_hf_sp_stability` | the same molecule and state at HF | the same verdict without a functional: the observation is not DFT-only |
| `o2_triplet_sp_stability` | triplet O2, B3LYP(G)/def2-SVP, UKS | the reason the record names the space: this reference's `external` is **UHF/UKS -> GHF/GKS**, a different question from the restricted rows above, and it is unstable |
| `water_sp_stability_cpcm` | the stable control under C-PCM water | PySCF's solvated `stability` sets `equilibrium_solvation` for the analysis, so the solvent response enters the orbital Hessian; the record carries the `PCMRKS` class |
| `hydrogen_atom_sp_stability` | the hydrogen atom at HF, an ROHF/HF1e reference | `pyscf.scf.stability.rohf_external` raises `NotImplementedError`, and the internal answer (stable) survives it, because the driver asks the two questions in two calls |

Three facts these runs settled.

**The two external questions can disagree, and PySCF returns only one of
them.** `rhf_external` and `uhf_external` each solve real -> complex and
then the R->U / U->G question, log both, and return the second alone. On
triplet O2 at UKS the two differ: `reference.json` captures PySCF's own
log saying the wavefunction *is* stable in the real -> complex analysis
while it *has* a UHF/UKS -> GHF/GKS instability. A record that reported
one boolean named "externally unstable" would have been reporting one of
two answers and hiding the other, so the artifact records the returned
flag with its space and names real -> complex under `not_determined`.

**A combined call throws an answer away.** `rohf_stability(internal=True,
external=True)` runs the internal Davidson, then raises from
`rohf_external`, so the internal result is lost with it. The hydrogen
atom fixture is that case, and its `analyses/internal/stable` is true
beside an `external` whose `unavailable` is PySCF's own
`NotImplementedError`.

**What it costs, measured on these runs.** The recorded `seconds` for the
whole analysis: 0.005 (H atom, internal only), 0.74 (O2 RHF), 3.98
(water RKS), 4.43 (O2 singlet RKS), 5.39 (O2 triplet UKS), 11.67 (water
RKS under C-PCM). Of the same order as the SCF it follows on cases this
size, which is why it is asked for rather than always run.

## Reference-diagnostics round (2026-09-19, the sensor that reads it)

Produced the same way on the CUHK Charles cluster (Slurm job 2140002;
`reference.py` at 2140003), PySCF 2.14.0, against the worktree of this
commit. Two rows, because the seven above are all converged `sp` runs
and the host sensor that now reads the record needed the two cases they
do not carry.

| directory | what it is | why it is here |
|---|---|---|
| `o2_singlet_hess_stability` | a Hessian on closed-shell singlet O2 at B3LYP(G)/def2-SVP with `scf_stability: true` | receipt `validated`, no findings, one real mode at 1641.76 cm-1 -- a delivered frequency standing on a reference PySCF itself reports **RHF/RKS -> UHF/UKS unstable**. Nothing in the run failed; the number describes a saddle in orbital-rotation space under green receipts, which is the whole case for a sensor |
| `o2_singlet_sp_unconverged_stability` | the same molecule with `scf_maxiter: 2` | receipt `failed` (`pyscf.result.stage_mismatch`), and the analysis answered anyway: **both** questions unstable at `scf_converged: false`. The only record in this corpus whose `internal` is false, and the reason the anomaly carries `reference_converged` -- on orbitals that are not stationary at all, "unstable" says far less than it does on the row above |

## IRC round (2026-09-20, result contract v8)

Produced through the human CLI (`chemsmart run --no-scratch -s CAMPAIGN
-n 8 -m 32 pyscf -p <project> -f <saddle> -c 0 -m 1 -l <label> irc`) on the
CUHK Charles cluster, PySCF 2.14.0 and geomeTRIC 1.1.1 in the compute env,
each saddle located first by ORCA 6.1.1 `OptTS Freq` through the same CLI.
Slurm 2140566 ran on code tree `a44b1929` (the formaldehyde branches and the
step-limited one) and 2140568 on `58ca745b` (the start that was a minimum,
regenerated after the driver stopped raising there, and every HCN/HNC run);
the two trees differ in nothing these converged runs reached.
`reference_irc.py` is PySCF's own account of each IRC artifact without
geomeTRIC: the start spectrum from the stored Hessian, the SCF energy and
gradient at the stored start, two interior frames and the endpoint, and the
cosine of every accepted step, superposed by the mass-weighted Kabsch
rotation, with the mean of the unit negative mass-weighted gradients at its
two ends -- whether the recorded path is the steepest-descent path of the
recorded surface. `inputs/` holds each ORCA saddle exactly as the PySCF runs
read it, so the host resolves the input by the geometry identity the run
recorded. `orca_differential/h2co_hcoh_orca_irc_full_trj.xyz` is ORCA's own
IRC path (`%irc direction both`, 31 frames) on its HF/6-31G* saddle.

| directory | what it is | why it is here |
|---|---|---|
| `h2co_hcoh_irc_forward`, `h2co_hcoh_irc_backward` | the two branches of H2CO <-> trans-HCOH at HF/6-31G* from ORCA's saddle (one imaginary mode, -2700.0 cm-1; start gradient 2.7e-5 Eh/Bohr on PySCF's surface) | opposite first-step projections on one host-signed transition vector (+0.982, -0.995); forward reaches trans-HCOH (O-H 0.951 A), backward formaldehyde (C-H 1.092 A); both endpoints agree with ORCA's own IRC ends to 0.006 A in every distance, and ORCA prints the saddle's energy (-113.698939548) as its IRC's "FINAL SINGLE POINT ENERGY", where the PySCF path starts at -113.698939548 |
| `h2co_hcoh_irc_maxsteps3` | the forward branch with `opt_maxsteps: 3` | five accepted frames kept; receipt `failed` on `path_converged`; the endpoint every property describes is the last frame |
| `h2co_irc_from_minimum` | a forward IRC started from the backward branch's endpoint (formaldehyde; handed the `.h5` itself) | geomeTRIC refuses to start (no imaginary mode); the start's all-real spectrum (1335.3, 1382.4, 1679.5 cm-1) and the SCF there are kept, and the ending is `stationary_point_order` |
| `h2co_hcoh_hess_on_irc_endpoint` | a Hessian handed the forward branch's `.h5` | the trans-HCOH endpoint characterised: six real modes, gradient 1.7e-4 Eh/Bohr |
| `hcn_hnc_irc_forward`, `hcn_hnc_irc_backward` | HCN <-> HNC at B3LYP/def2-SVP from ORCA's `B3LYP/G` saddle (-1122.72 cm-1; PySCF -1123.0) | forward reaches HNC, backward HCN, both linear and all-real under PySCF Hessians run on the endpoints; start gradient 2.8e-5 Eh/Bohr |
| `hcn_irc_from_vwn5_saddle` | the forward branch from the saddle ORCA located under its default `B3LYP` (VWN5) | walked on PySCF's VWN3 surface its start gradient is 4.4e-4 Eh/Bohr, sixteen times the matched saddle's and just inside geomeTRIC's 4.5e-4 criterion; it reaches the same HNC |
