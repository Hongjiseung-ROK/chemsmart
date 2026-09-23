# R10 episode q4 -- composition integrity

Base SHA: b834057741edb1246d7d2762c374a0e83d4e4f33 (verified with
`git rev-parse HEAD` as the first action, 2026-09-24).

## The question (as currently understood)

Which organ disagreements and verdicts actually break the multi-stage
routes chemists take (scan -> saddle refinement -> IRC -> endpoint
characterisation; a saddle's Hessian into its IRC; the same across
programs), and can each such question be answered by one function
derived from reader and registry declarations, with a guard that
forbids the bypass?

## Falsifier of the premise -- run first, provider-free (DONE)

Replayed every reachable archived plan and run stream through the
current organs (tree b8340577):

- corpus: 1,807 run streams (CUHK cluster `/project/xlzhang/jiseung/*`
  excluding r10, downloaded read-only; Hetzner mirror campaign,
  2026-09-14 and 2026-09-15 campaign trees; `experiments-public`),
  1,325 `command_workflow_planned` events, 762 distinct plans, 881
  distinct-plan data edges, 391 executed `workflow_data_edge_bound`
  records, 78 goal ledgers.
- The premise is NOT falsified. Real plans were affected:
  1. frontier vs review, ORCA scan -> opt/ts (`validated_scan_minimum_geometry`):
     every one of 24 planning sessions that planned the edge (Hetzner,
     2026-08-21 .. 09-04) ended `planned: workflow recorded but not
     approvable; these nodes still block approval: <the consumer>`,
     while the review admitted the edge; 11 such edges then executed
     (bound). The current tree still computes the same false word.
  2. review vs post-run handoff, ORCA modred -> ts: r9o-g5 cycle 2
     (CUHK Slurm 2144929): the modred ran 19,578 s, validated, and the
     host then recorded `workflow_node_launch_refused` for the node that
     had run ("orca result is not a converged OPT or TS"); the TS never
     launched in that cycle, the run was recorded `workflow_state:
     running`, the recovery saw no terminal state; the structure crossed
     only in cycle 3 through `bind_reached_geometry`. The native handoff
     accepts only opt/ts while the edge predicate admits modred.
  3. ORCA TS Hessian -> ORCA IRC (`hess_filename` role): 7 executed
     bindings; in every native IRC input reachable (Hetzner h1, h1b,
     irc-agent-path, irc-agent-path-2; CUHK r8 goal-ts) there is no
     `InitHess read` / `Hess_Filename`, and ORCA prints "Initial
     displacement Hessian type .... Compute numerically" (6N+1 gradients).
     The bound Hessian was never read.
  4. `geometry.same_structure_comparison_not_made` (a sensor stopping at
     its declared floor, not a registered anomaly signal) was minted as
     an anomaly receipt 49 times; 8 goals settled
     `achieved_with_observations` on it alone (cluster: g1-hcn-rotor-r1,
     water-levels-1, pak-g1-formaldehyde, g4-formaldehyde-h2, r8m-smoke,
     r8p-solvation, round-a-xtb-handoff-r1, sm3-run3-cuhk).
  5. Latent (no real record yet): a Hessian inside one approval fed a
     TS's geometry through the XYZ handoff inherits no promise; ORCA IRC
     endpoint is liftable but refused as an edge (2 pre-reader plans);
     `surfaces_agree` None read as agreement with no disclosure; the
     Gaussian workspace scanner's hand list drops scan/modred/ircf/ircr.

## Pre-registered repairs and their falsifiers

- R1 one owner answers "may this consumer take this producer's output
  inside one approval, by which rule" (execution.py), called by the
  review, bounded admission, the frozen rule, the frontier, the waiting
  reply and the result-file reason; the native handoff accepts exactly
  the stages the owner admits. Guard: a lint forbidding the per-rule
  predicates outside the owner. Falsifier: any archived edge whose
  review rule changes (authority change) -- expected zero; witness red
  on b8340577 (scan consumer blocking; modred refused post-run), green
  after.
- R2 a bound IRC Hessian is read (ORCA translation). Falsifier: a
  materialised IRC input with a bound Hessian and no `InitHess read`.
- R3 a sensor that stopped at its floor mints no anomaly; minting refuses
  an unregistered signal. Falsifier: any archived goal whose settlement
  word would change for a reason other than the floor record.

## Live validation (not yet designed -- will be written here before any
submission, with physics bands)

## Status

- 2026-09-24: replay done; repairs R1-R3 next.
