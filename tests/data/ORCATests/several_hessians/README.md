# Two ORCA runs that each compute several Hessians

ORCA 6.1.1 on CUHK Charles, written through ChemSmart's public CLI
(`chemsmart run -s CUHK -n 4 -m 8 orca -p <project> ... ts`) by R10
episode Q31's oracles: HCN/HNC isomerisation, B3LYP/G def2-SVP, neutral
singlet, 4 cores. The files are byte-identical to the job directories
(`/project/xlzhang/jiseung/r10/q31/cli/o3` and `.../o1`; sha256 below).

| file | job (CUHK Slurm), code | what it is | sha256 |
|---|---|---|---|
| `hcnscan3.out` | 2154022 (oracle O3a), code 6c32ebf9 | `! ScanTS Freq`, from the project `ts: {tssearch_type: scants, freq: true, scants_modred: {coords: [[3, 2]], dist_start: 2.10, dist_end: 1.10, num_steps: 11}}` on a bent HCN | `e9bc63c2ff00f75a228b3782f217d4d8de93b74fc8696fe86fa5ce04bc15791d` |
| `hcnscan3.inp` | same | the input the CLI wrote for it | `9326db23767d37f2f3834038e72d4e3babc41b8f381e9c83d9714abba4b71982` |
| `hcnsaddle.out` | 2154008 (oracle O1b), code a39f784b | `! OptTS Freq` with `Calc_Hess True` and `Recalc_Hess 5`, from an HCN/HNC saddle guess | `de1d5459de2648b62e7314fe4949d94ec264bf34bff85ba418af4b4bb6a0f4e3` |
| `hcnsaddle.inp` | same | the input the CLI wrote for it | `63d6ba91fb00d9c36f80444d0945a0c879dc7d93672f59ace476c2090240c315` |

What they show:

- `hcnscan3.out` computes ten Hessians -- one at each of the nine scan
  points ORCA ran (H-N 2.10 to 1.30 A; it stopped the scan past the
  maximum) and one at the saddle it then optimised -- and prints a
  complete thermochemistry block for each. It prints the frequency table,
  normal modes and IR spectrum for the first Hessian only: line 4796,
  scan point 1, -574.58, 2427.41 and 4207.65 cm^-1. The saddle's own block
  (line 41501) reads E(el) -93.27590907 Eh, ZPE 0.01078027 Eh and
  G -93.28613642 Eh, and lists its real modes, 2092.72 and 2639.28 cm^-1;
  its imaginary mode (-1123.57 cm^-1) is printed nowhere in this output,
  only in the `.hess` ORCA wrote beside it (not kept here). The saddle
  lies within 0.004 A and 3.5e-7 Eh of `hcnsaddle.out`'s.
- `hcnsaddle.out` computes two Hessians and prints the table for both:
  the initial one at the guess (line 1211, -1076.84 cm^-1) and the final
  one at the saddle (line 3834, -1122.72, 2091.27 and 2629.38 cm^-1).

Read by `tests/agent/test_an_orca_result_is_read_at_its_last_hessian.py`.
Before R10 Q31 the ORCA reader served the ScanTS's scan-point-1
frequencies, electronic energy, zero-point energy and geometry beside its
saddle's Gibbs energy, and read the OptTS's normal modes, IR columns,
thermal corrections and entropy terms from its guess-geometry block.
