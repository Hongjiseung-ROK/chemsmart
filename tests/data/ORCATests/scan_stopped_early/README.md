# ORCA relaxed scans that stopped early

Real ORCA 6.1.1 outputs of the CHEMSMART Agent goal R10 Q20 G1 (CUHK Slurm
2153658; (Z)-1,3,5-hexatriene ring closure, B3LYP-D3(BJ), C1...C6 driven),
kept byte for byte with the per-step geometry files ORCA wrote beside them.
Each output's sha256 equals the `result_artifact_sha256` that goal's
workspace record holds for the node.

- `timeout/` -- node `scan-c1c6-r2`, cycle 2 (def2-TZVP, RIJCOSX, 4.5 -> 1.6 A
  in 13 points), killed by the 3 h node limit after 10808 s during step 11.
  Steps 1-10 converged; step 10 holds C1...C6 = 2.325 A. No surface table.
  sha256 99fd69768f6248eab592d5ab85c109a9fa92bb82ff56233f5ce996b400d5edc7.
- `step_not_converged/` -- node `scan-bracket-r3`, cycle 3 (def2-SVP, 3.0 ->
  1.9 A), whose first step ran out of optimisation cycles
  (`failed_nonconverged_scan_step`). ORCA still wrote `.001.xyz` for that
  unconverged step. sha256
  859c4be33d1ebb0e06fa16765833293a77c07ff68f8219440782140cabf215e0.

`../scan_completed/` is a completed scan for comparison: R10 Q7's CLI oracle
`h2o2_o_scan` (B3LYP/G def2-SVP, H-O-O-H 0 -> 180 deg in 13 points), with the
per-point files and ORCA's `.relaxscanact.dat`.
