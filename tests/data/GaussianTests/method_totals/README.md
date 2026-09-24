# Gaussian logs whose method prints its total beside lower levels

Gaussian 16 C.02 on CUHK Charles, CUHK Slurm 2149277 (R10 q2 oracle 1),
written and run through the human CLI (`chemsmart run -s CUHK -n 8 -m 24
gaussian -p <project> -f water.xyz -c 0 -m 1 -l <label> sp`) on the base
tree `8f2c3443` (code identical to `b8340577`). Water at one fixed geometry,
cc-pVDZ, Gaussian's default frozen core.

| file | route | the total Gaussian printed for the route's method |
|---|---|---|
| `water_hf_ccpvdz.log` | `hf` | archive `HF=-76.0267721` |
| `water_mp2_ccpvdz.log` | `mp2` | archive `MP2=-76.228438` |
| `water_mp3_ccpvdz.log` | `mp3` | archive `MP3=-76.2354356` |
| `water_mp4_ccpvdz.log` | `mp4` | archive `MP4SDTQ=-76.2406725` |
| `water_ccsd_ccpvdz.log` | `ccsd` | archive `CCSD=-76.2380047` |
| `water_ccsdt_ccpvdz.log` | `ccsd(t)` | archive `CCSD(T)=-76.2410412` |
| `water_qcisdt_ccpvdz.log` | `qcisd(t)` | archive `QCISD(T)=-76.2411041` |
| `water_b2plyp_ccpvdz.log` | `b2plyp` | `E(B2PLYP) = -76.353098437995` (archive `MP2=`) |
| `h2co_td_b3lyp_opt_root1.log` | `opt b3lyp 6-31g* td(nstates=3,root=1)` | `Total Energy, E(TD-HF/TD-DFT) = -114.362268294` |
| `water_pbe0_word_ran_pbe0dh.log` | `pbe0 def2svp` | Gaussian completed the word to PBE0-DH: `SCF Done:  E(RPBE0DH)`, `E(PBE0DH) = -76.269879732702` |

On that tree the reader's `energy` returned the EUMP2 total, -76.2284380,
for every correlated route above MP2, the SCF part of B2PLYP (-76.2884647),
and the ground state of the TD optimisation (-114.4864268). The last log is
the evidence that a route word Gaussian does not know as a keyword is run
as a keyword it prefixes, without a warning.
