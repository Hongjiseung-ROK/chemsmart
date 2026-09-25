# A torsion read as a hindered rotor, by the host's own thermochemistry

Gaussian 16 C.02 on CUHK Charles, byte-identical to the runs that wrote them
(sha256 below).

| file | run (CUHK Slurm) | what it is | sha256 |
|---|---|---|---|
| `meoh_b3lyp_d3bj_tzvp_opt.log` | R10 Q30 oracle O1 (2153802), `g_meoh_eq` | `opt freq b3lyp def2tzvp empiricaldispersion=gd3bj`: methanol, staggered; torsion 304.3 cm^-1 | `67f85b386435f4248c223dc3a41dff2aa9ea29d4cfbdf7c7cfd9331d2dc8506e` |
| `meoh_b3lyp_d3bj_tzvp_scan_5_115.log` | the same job, `g_meoh_scan` | relaxed scan `D 3 2 1 4 S 11 10.0` from H3-O2-C1-H4 = 5 deg: 12 points over the methyl rotor's whole 120-deg period | `dff140ff6c02305a20e27ebc524364c5043114d142ee986ea46ccec03ac8d699` |
| `c2h6_b3lyp_d3bj_tzvp_held5.log` | R10 Q30 oracle O1 (2153802), `g_c2h6_heldp005` | `opt=modredundant freq`, ethane with H3-C1-C2-H6 held at 5 deg (one imaginary mode, the torsion, -293.7 cm^-1); Gaussian wrapped its archive entry between the last `\\` and the `@` | `503e517ef5941df70e4c8755cf2308f1afa60bdd0b37b7108660b90cc10f4cf1` |
| `h2o2_b3lyp_svp_opt.log` | R10 Q7 g2-scan-modred, `calc-opt-min` (an Agent goal) | `opt freq b3lyp def2svp`: H2O2 at its gauche minimum | `0e9fee403eb9e51629f8d5ee21dfec05ae2148cb8cc7bc55cb72bcd96e18d708` |
| `h2o2_b3lyp_svp_scan_0_180.log` | the same goal, `calc-scan-torsion` | the Agent's relaxed scan of H3-O1-O2-H4 from 0 to 180 deg in 15-deg steps: half of H2O2's 360-deg rotor period | `b2bc1f9cef40fcfff57ee59eaaa533a846507d14ec033c33dae2d1f4732e301e` |

What they show, through `derive_result_thermochemistry` (R10 Q30): the
methanol pair gives a hindered rotor with sigma_int 3, I(3,4) 0.618 amu A^2
from either end, a 1.076 kcal/mol barrier (spectroscopic V3 373 cm^-1 =
1.067), and S(298.15 K, 1 bar) 239.79 J/(K mol) against the harmonic
238.41 and Gurvich's 239.87. The H2O2 scan covers half a turn, which is
all two Agent-planned H2O2 scans ever covered (this one and R10 Q27 g1's
ORCA scan, 0 to 180 deg in 30-deg steps), and the rotor treatment refuses
it: H2O2's two gauche wells are mirror images, so its rotor period is the
full turn.
