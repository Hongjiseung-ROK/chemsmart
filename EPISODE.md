# R10 Q2 -- one name, one physics

Base SHA: b834057741edb1246d7d2762c374a0e83d4e4f33 (verified `git rev-parse HEAD` at start)
Episode id: q2
Branch: worktree-agent-a00bcce00d346c895

## Question (as currently understood)

Can one project statement mean one Hamiltonian wherever CHEMSMART
translates it, and one selector name one physical quantity whichever
program produced it -- with the host recording what was actually applied
and telling any operation that combines numbers when its inputs are not
comparable -- so that neither the Agent nor a reviewer needs a program's
conventions, and the model is no longer taught them?

## What the tree says before any change (read, not yet run)

- `functional: b3lyp` is written `B3LYP` for ORCA (VWN5 local correlation,
  ORCA prints `LDAOpt .... VWN-5`), `b3lyp` for Gaussian (IExCor 402), and
  resolved to `b3lypg` (libxc 402, the VWN-RPA form) for PySCF. Archived
  evidence already shows ORCA `B3LYP/G` (`LDAOpt .... VWN-3`) equals PySCF
  `b3lypg` to 1.1e-6 Eh on water (orca_differential/water_td_b3lypg.out
  E(SCF) -76.358315131 vs water_td_singlet -76.358316223).
- ORCA's `energy` on a `td` job is `FINAL SINGLE POINT ENERGY`, which ORCA
  writes as E(SCF)+DE(CIS) of root 1 (-76.080796713 on that same fixture),
  while the reader resolves its provenance to `reference` and PySCF's `td`
  `energy` is the reference -- one selector name, two quantities.
- Gaussian `energy` is `energies[-1]`, where `energies` returns the EUMP2
  list whenever any EUMP2 line exists and SCF Done energies otherwise.
- ORCA/Gaussian surfaces write `unknown` for dispersion, density fitting,
  frozen core; so no log-reader surface ever compares.

## Falsifiers and pre-registered bands (written before any job ran)

Oracle 1 (CLI reference, base tree = code identical to b8340577; jobs
`cli/oracle1a`, `cli/oracle1b`). Energies are Eh unless stated.

H0 (premise falsified) if ALL hold: matched-numerics programs agree
(P1), AND the VWN5-minus-VWN-RPA change in every relative energy of Block R
(vertical IP of water, HCN->HNC, C-Cl homolysis of CH3Cl) is below
0.1 kcal/mol, AND no archived plan combined values across programs or
levels. Then the divergence is inert and the episode narrows to the
wrong-number defects and deleting the taught convention.

P1 (numerics bound). At tight matched numerics (ORCA NoRI DEFGRID3
VeryTightSCF; Gaussian scf=tight int=ultrafine; PySCF defgrid3 conv_tol
1e-10), ORCA `B3LYP/G`, Gaussian `B3LYP` and PySCF `b3lyp` (b3lypg) totals
agree within 5e-5 on every species; ORCA `B3LYP` and PySCF `b3lyp5` agree
within 5e-5. Failure of P1 means a further Hamiltonian difference hides
behind the name (basis, ECP, grid pathology) and is itself a finding.

P2 (size). Same-program VWN5 minus VWN-RPA total offset is positive and
between 0.02 and 0.5 on every species, growing with electron count.

P3 (relative energies, the premise's live test). |Delta(VWN5) -
Delta(VWN-RPA)| for the water vertical IP, HCN->HNC and CH3Cl -> CH3 + Cl:
expected < 0.3 kcal/mol for the isogyric isomerisation and larger (0.3-5
kcal/mol) for the two electron-pair-changing ones. The band is recorded,
never tuned.

P4 (Gaussian `energy`). On the base tree the reader's `energy` returns the
EUMP2 value for MP3/MP4/CCSD/CCSD(T)/QCISD(T) routes (differs from the
log's own final method energy by > 1e-3), the SCF part for B2PLYP (differs
from E(B2PLYP) by the PT2 term), and the ground state for the TD
optimisation. HF and MP2 are correct. Any route where `energy` equals the
printed final method total falsifies that case.

P5 (dispersion). D3(BJ) dispersion energies of benzene from ORCA, Gaussian
and PySCF agree within 1e-7 if all three apply the same two-body form; a
difference of order 1e-5-1e-4 is a three-body term in one program.

P6 (frozen core). CH3Cl MP2/def2-SVP: ORCA default and Gaussian default
correlation energies agree within 1e-6; PySCF default (all-electron)
differs from them by > 1e-3; PySCF `frozen_core: auto` matches them within
1e-6.

P7 (handoff fingerprint). PySCF b3lyp (tight) max|gradient| at the
formaldehyde minimum ORCA reaches with `functional: b3lyp` (as the Agent
writes it) is at least 3x the value at the minima reached by ORCA
`B3LYP/G` and by Gaussian `b3lyp`.

## Oracle

Block F: water, 9 project literals x 3 programs, tight numerics.
Block R: water, water cation (vertical), HCN, HNC, CH3Cl, CH3, Cl, benzene
x {as-written defaults per program, ORCA B3LYP/G defaults, and at tight
numerics PySCF b3lyp / b3lyp5, ORCA B3LYP/G / B3LYP, Gaussian B3LYP}.
Block C: Gaussian water/cc-pVDZ HF, MP2, MP3, MP4, CCSD, CCSD(T),
QCISD(T), B2PLYP; ORCA and PySCF CCSD(T) (PySCF default and frozen_core
auto); Gaussian TD-B3LYP/6-31G* optimisation of formaldehyde root 1.
Block X: benzene B3LYP-D3(BJ) in three programs, D4 in ORCA and PySCF.
Block Z: CH3Cl MP2/def2-SVP frozen-core defaults.
Block H: formaldehyde optimised by ORCA b3lyp, ORCA B3LYP/G, Gaussian
b3lyp; PySCF b3lyp Hessian (and gradient) on each reached geometry.

Private config: /project/xlzhang/jiseung/r10/q2/config (SERVER cores 8,
threads 8, memory 24 GB; scratch under /scratch/s1/xlzhang/jiseung/r10/q2;
every program block otherwise unchanged).

## Jobs issued

(none yet)

## Status

- step 1: oracle 1 pre-registered; code unchanged.
