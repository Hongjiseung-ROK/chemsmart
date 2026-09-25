# R10 episode Q30 -- a torsion that is not a harmonic oscillator

- Base SHA: 194f69e10edfdc1889e29853b7e30bcb24b7b27d (verified with `git rev-parse HEAD` as the first action, 2026-09-25).
- Brief: scratchpad/q30/BRIEF.md, sha256 942d0913b430fa18d55bfda72c5bac4bdb1bc253783e5ccc06273f9a1295e22e.
- Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

A scientist asks for a thermodynamic property of a molecule whose low torsion
is not a harmonic oscillator (the standard entropy or heat capacity of H2O2,
methanol, ethane; a conformer population). Can the Agent get an honest
hindered-rotor answer through the hub -- a typed request each program answers
from its own artifacts (a frequency result and a relaxed scan, or held points)
-- whose receipt says which torsion was treated and how its potential was
obtained, which reduced moment and symmetry numbers were used, and what
replaced the harmonic mode? And does that answer meet experiment where the
harmonic treatment misses it?

## Census (premise, demand side)

scratch q30/census/census.py over (a) every task file and goal ledger fetched
read-only from CUHK r8, r9, r10/q1..q28 (q3/goals only, q17/hc1 only,
q29/census only; no r10/m*, no r10/master) and every campaign directory at
/project/xlzhang/jiseung top level (460 files; list in r10/q30/census_files.txt
on the cluster), and (b) the ax41 mirror (every cut). 425 unique task texts;
39 name an entropy, heat capacity, partition function, population or
internal rotation; read one by one. Tasks that ask for a thermodynamic
property of a molecule with a low torsion:
- ax41 cycle 011 reobservation1: standard molar entropy of 1,3-butadiene
  (lowest mode is the ~160 cm-1 central torsion). Delivered 276.35 J/mol/K
  (ORCA QRRHO) against ~279 tabulated; the evaluator's own ground truth
  called butadiene "rigid ... whose lowest modes are stiff".
- ax41 cycle 011 observation1/analysis1: acetic acid dimerisation dS (a
  near-free methyl rotor); cycle 012 reobservation1 and cycle 004: Diels-Alder
  activation entropy with butadiene; cycle 010 reobservation1: Ala5 peptide
  free-energy correction; cycle 012 observation1: gauche fraction of
  n-butane; benchmark-v1 L3c and benchmark-v2 l3d: 1,2-dichloroethane
  populations; general-round task-rb: 2-aminoethanol populations; cycle 042:
  3-pyridinecarboxaldehyde conformer populations.
- CUHK po3-atorvastatin-pka-concurrency: conformer populations of
  atorvastatin; r10 q21 g1/g2-hooh, q24 g2r, q27 g1 (one task): Gibbs energy of
  H2O2 along its torsion (the session named the harmonic 323 cm-1 torsion as an
  uncertainty it could not remove).
Not counted: benzene S (no torsion), ammonia synthesis, torsional barriers
asked as electronic energies (ethane, ethylene, H2O2 scans), n-hexane ordering.
The demand exists; no archived receipt says that a low torsion was counted as
a harmonic oscillator.

## References read in this session (provenance)

Standard-state pressure 1 bar (0.1 MPa) for every reference below.
- H2O2(g): JANAF 4th ed. table H-070 (janaf.nist.gov/tables/H-070.txt and
  .html, p° = 0.1 MPa): S°(298.15) = 232.991, Cp° = 43.116 J/K/mol,
  H(298.15)-H(0) = 10.853 kJ/mol. Gurvich et al. (1989) via NIST CCCBDB
  (exp2x.asp?casno=7722841): S = 234.52, Cp = 42.40 J/K/mol, H-H(0) = 11.16.
  The two compilations DISAGREE by 1.53 J/K/mol in S and 0.72 in Cp -- more
  than the band below, and exactly over the torsion treatment. The 2003
  NIST-JANAF revision (Dorofeeva et al., JPCRD 32, 879) could not be read
  (srd.nist.gov 503); its value is absent by name. Torsion barriers (Hunt et
  al. 1965, as quoted in arXiv:2105.09186): trans 381 cm-1, cis 2460 cm-1.
- CH3OH(g): Gurvich via CCCBDB (casno 67561): S = 239.87, Cp = 44.10 J/K/mol,
  H-H(0) = 11.44 kJ/mol; TRC 1997 via NIST WebBook: Cp(298.15) = 44.06 +- 0.03
  (p = 1 bar). V3 = 373.08 cm-1 (Herbst et al. 1984, via CCCBDB).
- C2H6(g): Gurvich via CCCBDB (casno 74840): S = 229.16 +- 0.10, Cp = 52.49
  J/K/mol, H-H(0) = 11.88 kJ/mol; V3 = 1024 cm-1 (12.2 kJ/mol); torsion
  fundamental 289 cm-1 (A1u, Shimanouchi). No JANAF table exists for CH3OH or
  C2H6 (janaf.nist.gov H index read).
- Method: NIST-JANAF (Dorofeeva, Novikov, Neumann, JPCRD 30, 475 (2001), read):
  internal-rotation levels by diagonalising the 1D Hamiltonian on
  V = 1/2 sum V_n (1 - cos n phi), reduced moment by Pitzer-Gwinn / Pitzer
  (1946). East & Radom, JCP 106, 6655 (1997), read: I(3,4) is exact within the
  rigid-rotor model for one internal rotation and independent of which end
  turns (methanol MP2/6-31G(d): 0.6348 amu A^2); methanol torsion at 298.15 K,
  1 atm: S(HO) 5.666, S(hindered) 7.345, S(free) 8.358 J/K/mol; explicit
  rotor gives total S within 1 J/K/mol for one-rotor species, harmonic errors
  up to 1.8 J/K/mol per rotor.

## PRE-REGISTRATION -- bands and oracle O1 (written before any run)

Observables: S°(298.15 K, 1 bar) and Cp°(298.15 K) of the ideal gas, computed
through the host (pressure_atm = 0.986923 = 1 bar; most-abundant isotopes;
Cp = Cv + R for the ideal gas).
Treatments:
- T0 harmonic: the host's ordinary RRHO receipt (entropy_method rrho).
- T1 1D-HR on V(phi): the rotor's potential from a relaxed scan's electronic
  energies over one full period, Fourier-fitted; levels from the 1D
  Schrodinger equation; reduced moment I(3,4) (rigid top at zero overall
  angular momentum) at the frequency result's structure; sigma_ext counted by
  the host, sigma_int = lcm of the two tops' rotational orders about the bond;
  the rigid-top internal rotation projected from the Hessian so 3N-7 modes are
  kept beside the rotor.
- T2 1D-HR on G_perp(phi): as T1, the potential being E(phi) + the Helmholtz
  vibrational free energy of the 3N-7 modes projected at held points
  (modred + freq, R10 Q27's projection).

Bands (fixed now, never tuned):
- B-S: a treatment meets experiment on a system when |S - S_ref| <= 1.0 J/K/mol.
  For H2O2, S_ref is the interval [232.99, 234.52] (JANAF 1998 .. Gurvich 1989):
  within 1.0 of the interval; the distance to each compilation is reported.
- B-Cp: |Cp - Cp_ref| <= 1.5 J/K/mol (H2O2: interval [42.40, 43.12]).
- Premise falsified if T1 and T2 both miss B-S on H2O2 or on methanol (the two
  systems where the harmonic is expected to miss); question smaller than it
  looks if T0 is inside B-S on all three systems.

Predictions (physics, before any run):
- P1 (harmonic misses): T0 S is below the band on H2O2 by >= 4 J/K/mol (the
  enantiomeric wells, R ln 2 = 5.76, plus a low trans barrier) and on methanol
  by > 1.0 (East-Radom HO-to-hindered difference 1.68); on ethane T0 is within
  B-S (V3 ~ 5 kT at 298 K): ethane is the control.
- P2 (T1 meets): T1 within B-S on all three systems, for each program.
- P3 (programs agree): |T1(ORCA) - T1(Gaussian)| <= 0.3 J/K/mol per molecule;
  the same for T0.
- P4 (T2 vs T1), reported and not banded: |T2 - T1| <= 0.5 J/K/mol per
  molecule. Falsifier: > 0.5 on any, which would make G_perp necessary.
- P5 (Cp): T1 within B-Cp on all three; T0 reported.
- P6 (moment): methanol I(3,4) within 5 % of 0.6348 amu A^2; the two ends give
  the same I(3,4) to 1e-6 relative (exactness check of the implementation).
- P7 (barriers, reported): scan barriers vs spectroscopy (ethane 1024 cm-1,
  methanol 373 cm-1, H2O2 trans 381 / cis 2460 cm-1).

Oracle O1 (CLI, CUHK; ORCA 6.1.1 and Gaussian 16 C.02; B3LYP-D3(BJ)/def2-TZVP;
starting geometries from scratch q30/oracle/build_geometries.py, torsion set
exactly; scans offset 5 deg from the planar 0/180 points because ORCA refused
to impose a dihedral constraint off an exactly planar step, Q27 g1 CUHK 2153714
"GSTEP: could not impose initial constraints", 0 -> 30 deg):
- opt+freq: H2O2 (start 115 deg), CH3OH (180), C2H6 (60).
- relaxed scans (freq off): H2O2 H3-O1-O2-H4 -175..175 deg, 36 points;
  CH3OH H3-O2-C1-H4 and C2H6 H3-C1-C2-H6 5..115 deg, 12 points.
- held points (modred + freq): H2O2 -165..165 every 30 deg (12); CH3OH and
  C2H6 5..115 every 10 deg (12 each).
- Issued: CUHK Slurm 2153801 (ORCA, slot a, 8 cores / 32 GB) and 2153802
  (Gaussian, slot b, 16 cores / 40 GB), code 57d1ca22 (digest e4fe4adf...),
  pre-registration digest 3695ad70b714.

## Provenance added after pre-registration (not a band change)

- NIST WebBook, H2O2 gas phase (read): S(gas, 1 bar) 232.95 J/K/mol, "Review
  Chase, 1998 -- Data last reviewed in December, 1960": the JANAF H2O2 entry
  predates the far-infrared torsional work (Hunt et al. 1965) that Gurvich's
  1989 evaluation uses. Recorded beside the interval band, which stays as
  registered.

## PRE-REGISTRATION -- live goals g1-h2o2 and g2-meoh (written before issue)

One observation each of deepseek-v4-flash-0731 (alibaba-token-plan), run in
parallel in the two slots, on code that carries 40510c65 (analysis plane),
76acb0fb (shared reachability), 6cef686a (Gaussian archive reader) and
130e99cc (the rule on plan_thermochemistry).
- Tasks (do not name the treatment): "What is the standard molar entropy of
  hydrogen peroxide vapour / methanol vapour at 298.15 K?" at B3LYP-D3(BJ)/
  def2-TZVP, ORCA and Gaussian both available, S at 1 bar in J/(K mol) "with
  what the number rests on and how far you would trust it". TASK.md sha256
  g1 f35084d1fdb71147..., g2 c998b173dc29f85c...; geometries h2o2.xyz
  6dfeac65c22cf826... (H-O-O-H 115 deg), methanol.xyz 769169123d6a84e0...
  (staggered), both unoptimised, comment lines neutral.
- Envelope (make_goal.py): orca and gaussian cpu, 8 cores, 24 GB, node
  5400 s, episode 14400 s, reserve 1800 s, 8 engine calls, 2 revisions,
  local dispatch; granted_by claude-researcher-q30-owner-delegated (a
  delegated approval, never a human decision).
- S-host: (a) every harmonic receipt of these molecules names the torsion as
  counted harmonically and the internal_rotors route; (b) every rotor receipt
  states torsion, potential source and fit, wells and barriers, I(3,4),
  sigma_int and the replaced mode; (c) a scan short of the rotor period (H2O2:
  360 deg) is refused with gate thermochemistry.hindered_rotor_stands_on_its_scan
  and a route.
- S-agent (success): the delivered S stands on a rotor receipt and the
  delivery names the treatment.
- Partial: the harmonic S is delivered with the torsion's harmonic treatment
  stated as a limitation (read, not acted on).
- F-agent: a harmonic S delivered as the S with no word on the torsion.
- Neutral: no scan planned and no torsion word; then check the affordance was
  visible (plan_thermochemistry loaded, the rule sentence and the receipt's
  torsion line in the transcript) before attributing it.
- Physics bands for the delivered S: H2O2 [231.99, 235.52] (B-S); methanol
  [238.87, 240.87]. Harmonic expectation from O1: H2O2 227.6, methanol 238.4-
  238.5 (both outside). A delivered harmonic value inside a band would be a
  finding to explain, not a success.
- Not counted: zero provider turns or turn_deadline_exceeded (infrastructure).
  A weak run is reported, never re-rolled.

## Status

- step 0: brief read, base verified, governance, lessons, charter topics
  (validity-rules, constants-and-pka, orca-scan-irc-modred) and Q27's record
  read; cluster gate open.
- step 1: census done; references read; O1 pre-registered (this file).
- step 2: O1 issued (2153801, 2153802). Built while it ran: 40510c65 (kernel,
  scan reader, analysis-plane route, harmonic receipts name their torsions),
  76acb0fb (shared: reachability, gate registered), 6cef686a (Gaussian
  archive read wherever it wraps: 3 of 122 archive-bearing logs had lost
  their Hessian), 130e99cc (the rule on plan_thermochemistry). Gaussian
  held points 15 and 25 deg of ethane stopped at NStep 38 (typed failures).
- step 3: live goals g1-h2o2 and g2-meoh pre-registered above.
