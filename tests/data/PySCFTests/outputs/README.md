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
recorded surface. Its output for each IRC fixture is the `*.reference.json`
beside it, written at the end of Slurm 2140568 (PySCF 2.14.0); the script
committed here differs from the one that ran only by black's formatting.
Every stored energy it re-evaluated agrees to 1e-9 Eh, every gradient to
4e-6 Eh/Bohr, and the recorded transition vector is the stored Hessian's
lowest mode (cosine 1.000000). `inputs/` holds each ORCA saddle exactly as the PySCF runs
read it, so the host resolves the input by the geometry identity the run
recorded. `orca_differential/h2co_hcoh_orca_irc_full_trj.xyz` is ORCA's own
IRC path (`%irc direction both`, 31 frames) on its HF/6-31G* saddle, and
`orca_differential/hcn_hnc_orca_irc_full_trj.xyz` (66 frames, analytic
initial Hessian) on its `B3LYP/G` / def2-SVP saddle, run last in Slurm
2140568.

| directory | what it is | why it is here |
|---|---|---|
| `h2co_hcoh_irc_forward`, `h2co_hcoh_irc_backward` | the two branches of H2CO <-> trans-HCOH at HF/6-31G* from ORCA's saddle (one imaginary mode, -2700.0 cm-1; start gradient 2.7e-5 Eh/Bohr on PySCF's surface) | opposite first-step projections on one host-signed transition vector (+0.982, -0.995); forward reaches trans-HCOH (O-H 0.951 A), backward formaldehyde (C-H 1.092 A); both endpoints agree with ORCA's own IRC ends to 0.006 A in every distance, and ORCA prints the saddle's energy (-113.698939548) as its IRC's "FINAL SINGLE POINT ENERGY", where the PySCF path starts at -113.698939548 |
| `h2co_hcoh_irc_maxsteps3` | the forward branch with `opt_maxsteps: 3` | five accepted frames kept; receipt `failed` on `path_converged`; the endpoint every property describes is the last frame |
| `h2co_irc_from_minimum` | a forward IRC started from the backward branch's endpoint (formaldehyde; handed the `.h5` itself) | geomeTRIC refuses to start (no imaginary mode); the start's all-real spectrum (1335.3, 1382.4, 1679.5 cm-1) and the SCF there are kept, and the ending is `stationary_point_order` |
| `h2co_hcoh_hess_on_irc_endpoint` | a Hessian handed the forward branch's `.h5` | the trans-HCOH endpoint characterised: six real modes, gradient 1.7e-4 Eh/Bohr |
| `hcn_hnc_irc_forward`, `hcn_hnc_irc_backward` | HCN <-> HNC at B3LYP/def2-SVP from ORCA's `B3LYP/G` saddle (-1122.72 cm-1; PySCF -1123.0) | forward reaches HNC, backward HCN, both linear and all-real under PySCF Hessians run on the endpoints; start gradient 2.8e-5 Eh/Bohr |
| `hcn_irc_from_vwn5_saddle` | the forward branch from the saddle ORCA located under its default `B3LYP` (VWN5) | walked on PySCF's VWN3 surface its start gradient is 4.4e-4 Eh/Bohr, sixteen times the matched saddle's and just inside geomeTRIC's 4.5e-4 criterion; it reaches the same HNC |

## Transition-state round (2026-09-21, result contract v9)

Produced through the human CLI (`chemsmart run --no-fake --no-scratch -s
CAMPAIGN -n 8 -m 32 pyscf -p <project> -f <seed> -c 0 -m 1 -l <label> ts`) on
the CUHK Charles cluster in Slurm **2141124**, code tree
`692aed65d4cff8fd992f29360c4a3bb0db4ee1ef35f5a426476550c16d34549b`, PySCF
2.14.0 and geomeTRIC 1.1.1 in the compute env. The whole batch took 4 minutes.
An earlier submission of the same batch (2141121) produced ten artifacts and
no receipt: the controller's Python 3.11 refused a dataclass default that the
authoring tree's 3.12 accepts. The engines had finished; nothing else had.

`inputs/h2co_ts_seed.xyz` and `inputs/hcn_ts_seed.xyz` are the seeds, each an
archived ORCA saddle displaced by hand -- 0.24 A and 0.21 A away -- so the
search has real work to do and the structure it should reach is already in
this corpus.

| directory | what it is | why it is here |
|---|---|---|
| `h2co_hcoh_ts` | the H2CO <-> trans-HCOH saddle at HF/6-31G*, climbed from `inputs/h2co_ts_seed.xyz` in 8 iterations and 9 gradient evaluations | every interatomic distance agrees with ORCA's own OptTS saddle (`inputs/h2co_saddle_orca_hf.xyz`) to **1e-4 A**, from a seed 0.24 A away, with no shared optimiser and no shared initial Hessian. The seed's recorded spectrum has **two** imaginary modes (-2516, -1015 cm-1) at max\|g\| = 0.177 Eh/Bohr: what the search started from is evidence, not inference |
| `h2co_hcoh_ts_hess` | the Hessian at what that search reached | one imaginary mode at **-2700.0 cm-1**, the frequency the archived `h2co_hcoh_irc_*` branches start from, at max\|g\| = 3.1e-5 Eh/Bohr. The `ts` artifact claims none of this: it prints no spectrum and declares no `vibrational_frequencies` selector |
| `hcn_hnc_ts`, `hcn_hnc_ts_hess` | the same chain for HCN <-> HNC at B3LYP(G)/def2-SVP | the saddle agrees with ORCA's `B3LYP/G` one to 3e-4 A; the Hessian gives -1123.2 cm-1 against the -1123.0 the archived IRC round recorded on ORCA's saddle |
| `h2co_hcoh_ts_maxsteps2` | the same search with `opt_maxsteps: 2` | what a search that ran out leaves: three frames, `search_converged: false`, receipt `failed`, and max\|g\| = 0.129 Eh/Bohr where it stopped -- the artifact says how far from stationary it was |
| `h2co_hcoh_irc_fwd_from_pyscf_ts`, `h2co_hcoh_irc_bwd_from_pyscf_ts` | the two IRC branches walked from the saddle `h2co_hcoh_ts` located, in the same batch | the chain this stage exists to close: before it, a PySCF IRC could only start from a saddle another program had found. Each branch's recorded start is that search's reached geometry to 1e-6 A, its start spectrum is the -2700.0 cm-1 one the Hessian node found, and its start gradient is inside the optimiser's criterion. Forward reaches trans-HCOH (O-H 0.951 A), backward formaldehyde (C-H 1.092 A) -- the same two minima the archived `h2co_hcoh_irc_*` branches from ORCA's saddle reach |
| `h2co_ts_from_minimum` | a saddle search seeded at formaldehyde itself (the backward IRC endpoint) | **the case this stage must not hide.** P-RFO converges in one iteration, moves 0.007 amu^1/2 bohr, and delivers the minimum under a `validated` receipt: "converged" is a statement about the gradient, never about the order. What makes it readable is the artifact's own account -- an all-real seed spectrum and a search that went nowhere -- and the Hessian node that would settle it |

Barriers from these runs, for reference: H2CO -> trans-HCOH 104.63 kcal/mol
forward and 52.23 backward at HF/6-31G* (from the IRC endpoints of
`h2co_irc_{fwd,bwd}` in the same batch); HCN -> HNC 47.84 and HNC -> HCN 34.16
at B3LYP(G)/def2-SVP.

## What the live campaign left here (2026-09-21)

| directory | what it is | why it is here |
|---|---|---|
| `h2co_elimination_ts` | the saddle search itself, as goal `g3-h2co-elimination` ran it in cycle 3 from `inputs/h2co_elimination_ridge_seed.xyz` -- a seed the session built with `edit_molecular_geometry` (H-C-H closed to 42 degrees) after diagnosing, from the geometry alone, that its two earlier searches had converged to non-saddles | a live Agent's third attempt, and the one that worked: seed spectrum **two** imaginary modes (-3954.5, -1075.9 cm-1) at max\|g\| = 0.166, 18 iterations, reaching max\|g\| = 3.2e-4 |
| `h2co_elimination_ts_hess`, `h2co_elimination_irc_fwd`, `h2co_elimination_irc_bwd_minimisation_tail` | the Hessian and both IRC branches at the H2CO -> H2 + CO saddle a live goal's third `ts` search found (goal `g3-h2co-elimination`, CUHK **2141229** cycle 3), run as a direct-CLI diagnostic (**2141482**) because the goal ran out of revisions one node short of confirming it | the saddle is genuine: one imaginary mode at -2191.9 cm-1 at max\|g\| = 3.2e-4, forward to formaldehyde, backward to separated H2 (0.730 A) and CO (1.1135 A), C...H 3.31 A. And the backward branch is **the first recorded case of `reached_by: minimisation_from_path_tail`**: 77 frames, of which 37 are Gonzalez-Schlegel path steps and 40 are the minimisation after them. "The IRC reached separated H2 and CO" and "a minimisation started from the IRC's tail reached separated H2 and CO" are different statements, and this is where the host now tells them apart |
| `hnc_linear_hess` | the Hessian the Agent ran on the HNC end of a PySCF IRC, from the saddle a PySCF `ts` node had located in the same goal (CUHK **2141231**, goal `g1-hcn-ts`, cycle 3) | **the first Hessian on a linear polyatomic in this corpus, and it failed.** HNC is 0.047 degrees from linear; the mode-count rule's relative transverse tolerance answers about 0.01 degrees for a triatomic, so the host demanded 3N-6 = 3 modes where PySCF's harmonic analysis had correctly produced 3N-5 = 4, and the independent reconstruction -- run at the rank the same test chose -- projected out half of the degenerate bending pair (551.0, 551.4 cm-1) and returned a survivor at 551.33 between them. The archived receipt is the one the live run wrote and says `failed`; the same bytes validate on this tree, with all four modes and a reconstruction agreeing to 3.9e-6 cm-1 |

## Result contract v10: the decomposition of the total (2026-09-21)

Produced through the ordinary CLI on CUHK (**Slurm 2142387**, five runs,
nineteen seconds of wall time) at PySCF 2.14.0 / libxc 7.0.0, on the water of
`inputs/water_relaxed.xyz` at B3LYP(G)/def2-SVP, every receipt `validated`
with no findings. `reference.py` rebuilds the reference from each applied
spec and reads PySCF's own `scf_summary` there; the four rows are the four
combinations that differ.

| directory | what it is | why it is here |
|---|---|---|
| `water_sp_smd_water` | an SMD/water single point | the only model in this build that gives both terms: polarisation **-0.0161307 Eh** (-10.122 kcal/mol) and CDS **+0.0023062 Eh** (+1.447). PySCF's own recomputation reproduces them to **3e-16 Eh** and exactly |
| `water_sp_cpcm_water` | C-PCM/water, same geometry and level | polarisation **-0.0103444 Eh** (-6.491 kcal/mol), reproduced to 6e-17 Eh, and **no CDS term at all**: the absence is the difference between the two models, not a parsing failure. The same molecule, the same solvent and the same level put the two models 3.6 kcal/mol apart, which is why the model is declared beside the number |
| `water_sp_d3bj` | gas phase with `dispersion: d3bj` | the dispersion term **-0.0005739 Eh** (-0.360 kcal/mol) and neither solvation term. Its total lies below `water_sp_gas_v10`'s by exactly that value: the terms are parts of the total, not corrections to add to it |
| `water_sp_gas_v10` | plain gas phase under the current contract | the control: all three terms absent, and each absence names its own reason. Absent is not zero |
| `water_opt_smd_water` | an optimisation inside the continuum | the terms belong to the structure the optimiser reached, like every other property: polarisation deepens to **-0.0162136 Eh** (-10.174 kcal/mol). Its stored term differs from a fresh SCF at the same geometry by **1.4e-7 Eh**, because the recorded one comes from the final SCF restarted from the optimiser's density -- the same SCF re-convergence difference the UKS hydroxyl case shows |

`projects/{sp,opt}-b3lyp-svp-{smd,cpcm}-water.yaml`, `projects/sp-b3lyp-svp-d3bj.yaml`
and `projects/sp-b3lyp-svp-gas.yaml` are the project files these ran from.

## The stability record heard (2026-09-24, R10 Q13)

The eight stability runs above regenerated through the ordinary CLI on CUHK
(**Slurm 2151881**, code `0a77574f`, PySCF 2.14.0; the same projects, inputs
and states; `reference.py` beside each) by a driver that hands
`mf.stability()` a logger and keeps what the analysis says. Every record
above names real -> complex "not determined" while the log beside it prints
PySCF's verdict and eigenvalues; these carry `analyses/real_to_complex` and,
on every question, the `lowest_eigenvalues` PySCF's Davidson logged (Eh, its
own normalisation), with `eigenvalue_unit` and PySCF's
`instability_threshold` (-1e-5 Eh). Each recorded array equals its own log's
printed array to the printed precision, in all eight.

| directory | lowest eigenvalue, Eh: internal / real -> complex / external | what it adds |
|---|---|---|
| `o2_singlet_sp_stability_heard` | 1.97e-6 / **-0.03830** / **-0.09262** | the singlet the older record called real -> complex "not determined" is unstable to complex orbitals: the real (pi_x*)^2 determinant is not the proper a1-Delta_g component. The internal root at zero is the rotation within the degenerate pi* pair |
| `o2_singlet_hf_sp_stability_heard` | 9.8e-7 / **-0.04903** / **-0.13108** | the same at HF: both instabilities without a functional |
| `o2_triplet_sp_stability_heard` | 0.3696 / 0.2123 / **-0.02928** | stable to complex orbitals, unstable UHF/UKS -> GHF/GKS; the next two external roots are near-degenerate at 0.0167 |
| `water_sp_stability_heard` | 1.151 / 0.2650 / 0.2377 | the stable control: how far from each instability, which the word never said |
| `water_sp_stability_cpcm_heard` | 1.214 / 0.2578 / 0.2276 | the same under C-PCM water (`PCMRKS`) |
| `hydrogen_atom_sp_stability_heard` | 1.362 / -- / -- | ROHF: internal only, and nothing recorded as undetermined, since no external analysis ran |
| `o2_singlet_sp_unconverged_stability_heard` | **-4.0e-4** / -0.03832 / -0.09268 | receipt `failed`, `scf_converged: false`: the internal root crosses PySCF's line only on orbitals that never became stationary |
| `o2_singlet_hess_stability_heard` | -2.6e-6 / -0.03830 / -0.09262 | the Hessian case; the internal zero root's sign is numerical noise inside PySCF's threshold |

## A basis that defines a core potential (2026-09-24, R10 q12)

Produced through the ordinary CLI on CUHK (**Slurm 2152029**, oracle O2',
code `d31f1170`) at PySCF 2.14.0, on HI at r = 1.609 A
(`inputs/hi_1609.xyz`), def2-SVP, `scf_tol 1e-10`, no density fitting.
The driver attached the core potential def2-SVP defines for iodine
(28 core electrons, taken from PySCF's own library entry for the basis),
as ORCA and Gaussian do for the same name; before, the environment probe
refused the run at execution time. Every receipt `validated`.

| directory | what it is | why it is here |
|---|---|---|
| `hi_hf_def2svp_ecp` | HF | 26 explicit electrons, `spec/ecp_core_electrons` {H: 0, I: 28}, atomic numbers [1, 53]; total -297.2315316634 Eh, 9.5e-11 from ORCA's and 1.2e-8 from Gaussian's def2-SVP (CUHK 2151773) |
| `hi_mp2_def2svp_ecp_auto` | MP2 with `frozen_core: auto` | 4 frozen orbitals (4s4p: the chemical core less the potential's 14), ORCA's and Gaussian's default count; total within 2e-9 Eh of ORCA's |
| `hi_mp2_def2svp_ecp_all_electron` | MP2 with `frozen_core` unset | every explicit electron correlated: 14.87 mEh below the frozen one, the HI bond energy 0.27 kcal/mol higher -- one project literal, a different core treatment from ORCA's default |

## A stationary O2 Hessian (2026-09-25, R10 q21)

Produced through the ordinary CLI on CUHK (**Slurm 2153611**, code
`6dceb065`, digest verified on the node) at PySCF 2.14.0, with the
fixtures' own projects: `b3lyp-def2svp.yaml` (opt) and
`hess-b3lyp-svp-stability.yaml` (hess), closed-shell singlet O2 from
`inputs/dioxygen.xyz`. Both receipts `validated`.

Why it is here: `o2_singlet_hess_stability_heard` is a Hessian at the
experimental 1.2075 A bond length, 0.0099 Eh/Bohr from the RKS minimum --
not a stationary point of its own surface -- and a test derived a
zero-point energy from it. A free energy (and its zero-point energy) is a
property of a stationary point, so the host now refuses that derivation;
this pair is the same question asked where it has an answer.

| directory | what it is | numbers |
|---|---|---|
| `o2_singlet_opt` | the RKS relaxation, geomeTRIC | converged; r(O-O) = 1.20122 A; -150.141866 Eh |
| `o2_singlet_relaxed_hess_stability_heard` | the Hessian with `scf_stability: true`, handed `o2_singlet_opt_gas_phase.h5` | max\|g\| 6.2e-8 Eh/Bohr; one mode at 1680.73 cm-1; internal / real -> complex / external lowest eigenvalues 5.7e-9 / **-0.03831** / **-0.09265** Eh -- the unrelaxed geometry's -0.03830 / -0.09262 to 3e-5 Eh: the instability is the determinant's, not the bond length's |
