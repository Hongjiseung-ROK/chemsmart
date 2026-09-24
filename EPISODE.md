# R10 episode Q13 -- what the programs print that the Agent never sees

Base SHA: 4db49c22b6dfab29a4ceca9eba4b59245bda0b7e (verified with `git rev-parse HEAD` at start).
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

Which quantities Gaussian, ORCA, PySCF and xTB print that bear on the science
the Agent is asked to do reach it as neither typed evidence nor a pointer to
where they sit? For each one that matters: can the hub serve it under the same
reader contract as every other selector, or, failing that, can the Agent be
told truthfully that the output holds it? Does serving it change what the
Agent concludes?

Two failure shapes are hunted:
- a printed quantity the science needs that no reader serves;
- a host statement of absence ("not determined") about something the output
  determines.

## Falsifier of the premise (from the brief)

Census the archived real outputs under /project/xlzhang/jiseung/ (sealed goals
r10/q6/goals and r10/q3 excluded; the master's r10/m* excluded) and tests/data.
If the quantities that matter are only the few named in the brief (PySCF
real->complex stability and the stability eigenvalues, Gaussian <R**2> and
molar volume, ORCA Hirshfeld spin populations), serve those and end. If a live
goal shows serving them changes nothing the Agent concludes, that is the
result.

## Census (provider-free, 2026-09-24)

Scope: 1,459 files pulled from /project/xlzhang/jiseung (miniforge3, the
deployed checkout, r10/q6/goals, r10/q3, r10/m*, r10/q13 excluded; slurm
outputs excluded) plus the worktree's tests/data. Program identified from each
file's own banner: 324 Gaussian logs, 273 ORCA outputs, 409 PySCF logs (plus
their .h5), 126 xTB outputs. Each printed block was counted once per file and
checked against the live readers (`RESULT_READERS[...].accessors`).
Script and tables: scratchpad q13/census (census.py, census.json); bundle on
CUHK /project/xlzhang/jiseung/r10/q13/census/.

Judged by one question: would a scientist use it to answer, or to question,
a task of the kind the Agent receives (reaction/BDE/pKa/redox energetics,
spin states and stability, excitations, spectra, solvation, bonding)?

Printed, unserved, and it matters (serve):
| quantity | program | files | parsed? | who asked |
|---|---|---|---|---|
| real->complex stability verdict | PySCF log | 26 | no; the record says "not determined" | gdev1 (Q1) settled with "a complex-rotation analysis would be needed for the remainder" while its log printed real->complex UNSTABLE, lowest eig -0.0383 |
| lowest stability-matrix eigenvalues (internal, real->complex, external) | PySCF log | 26-28 | no | r9/pyscf g2-stability declared both as observables; settled unreachable_from_evidence while the log printed them (out:2595-2599) |
| lowest stability-matrix eigenvalue | Gaussian | 11 | no (verdict only) | same science as PySCF's, other program |
| <R**2> electronic spatial extent | Gaussian | 267 (every population analysis) | no | Q10 LG1 (seeded) |
| molar volume (`volume` keyword) | Gaussian | 2 (+5 SMD logs print a solvent's 0.000 under the same words: a trap) | no | Q6 ar04/ar10 (sealed; quoted by Q10) |
| T1 diagnostic of coupled cluster | ORCA | 16 (DLPNO and canonical) | no | none recorded; it is the standard single-reference check of every CCSD(T) number |
| SMD-CDS (non-electrostatic) energy | Gaussian | 14 (tests/data SMD logs) | no | the solvation charter topic states "No archived Gaussian log carries the printed terms" -- false of tests/data |
| Mayer bond orders, Mayer free valence | ORCA | 238 (printed by default) | YES, never served | bond order questions; xTB WBO is served |
| Hirshfeld spin populations | ORCA, Gaussian | 0 open-shell outputs archived (closed shells print 0.000) | YES, never served | the brief; no archived open-shell output exercises it |

Printed, unserved, and derivable or low value (not served; reported):
thermochemistry components (ZPE, H, S, G corrections; 78 G / 57 ORCA / 50 xTB:
`derive_thermochemistry` computes them from served frequencies with stated
conventions), rotational constants and symmetry numbers, point group, nuclear
repulsion, energy components and virial ratio (ORCA), SCF cycle counts and
optimiser criteria values, APT charges (88), Fermi-contact couplings (50),
Raman activities (50), CD rotatory strengths (29), quadrupole and higher
multipoles (Gaussian 267, xTB 121; frame-dependent), polarizability (Gaussian
freq 89 -- some print "Exact polarizability: 0.000 ..." beside an approximate
one, a trap; xTB's alpha(0) is the D4 model's, not a response property),
Gaussian CM5 (charter: deliberately undeclared), "Low frequencies" line.

Premise verdict: partly falsified. The brief's few are not the whole class:
the census adds the Gaussian stability eigenvalue, ORCA's T1 diagnostic,
Gaussian's SMD-CDS term (where a charter sentence states an absence the
archive contradicts) and a second class -- quantities CHEMSMART's own parsers
already read and no reader serves (ORCA Mayer bond orders and free valence,
Hirshfeld spin populations). And one named item is thinner than stated: no
archived open-shell output prints a nonzero Hirshfeld spin population.

## The control already on disk (read from host records, CUHK)

gdev1 (R10 Q1, Slurm 2149848, code e687b9cf): singlet O2 as a closed shell,
B3LYP/def2-SVP, 1.2075 A, PySCF. Settled achieved_with_observations. The
session's finding: "(i) internal -- stable ... with real->complex rotations
not determined by PySCF; (ii) external -- unstable to RKS->UKS". Its recorded
uncertainties: "internal real->complex rotations were recorded as not
determined by PySCF (anomaly e41265...) ... a complex-rotation analysis would
be needed for the remainder." The same run's log prints
"rhf_real2complex: lowest eigs of H = [-0.0383 ...]" and "wavefunction has an
real -> complex instability". The host's false absence became the Agent's
stated uncertainty.

## Status

- Census: done (above).
- Next: PySCF stability record keeps PySCF's own answers (writer), then the
  reader serves them; Gaussian/ORCA census items; live goals pre-registered
  below before any is issued.
