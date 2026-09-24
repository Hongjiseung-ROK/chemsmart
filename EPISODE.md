# R10 episode q26 -- when the hub refuses to write an input, the model learns why

Base SHA: dc9ff937129cfb3c09d575113d0ce79c9529391f (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q26`.

## The question (as currently understood)

When the hub refuses to write a program input, does the Agent learn why, in
the compile reply (`compile_command`, handler `_prepare_program_node`) and in
the review it reads? Where the reason is lost, carry it through one path,
bounded, sanitised and true, so the compile reply and the review say the same
words from one function; then observe whether the Agent takes the route the
refusal names instead of guessing.

What decides whether a reason arrives is the phase in which the refusal
fires, not the refusal:
- project validation (`project_yaml` -> `validate_project_yaml`): the
  receipt keeps `error_class` and a bounded, path-scrubbed `diagnostic`;
- compile-time agent gates (`RoutedContractError`): the rejection carries
  the failure report;
- inside the safe preview's Click invocation (CLI settings construction and
  the writers): `chemsmart/agent/preview.py` keeps
  `type(result.exception).__name__` and a digest of the output only.

## Established so far (provider-free, base tree, scripted model)

Instrument: `run_live_agent_session` driven end to end with only the provider
transport replaced by a script (HOME fenced to scratch, placeholder key, no
provider contacted). Every reply below is the reply a model would read.

- ORCA, PySCF, Gaussian: `broken_symmetry: true` on a triplet (O2, 0/3).
  The reason exists (`str(exc)` is the full sentence, naming both routes:
  "Bind multiplicity 1 for the broken-symmetry singlet, or remove
  broken_symmetry for the high-spin state."). The compile reply carries
  `status: preview_failed`, `exception_class: "ValueError"`, findings that
  restate rule ids, `next_action: "inspect the generated-input validation
  findings"`, and an observation asserting the singlet translation the writer
  refused ("ORCA runs the unrestricted determinant ... on the singlet").
- Gaussian (writer refusal): the refused writer leaves a 0-byte `.com`; the
  validator reads it and reports five `preview.semantic.mismatch` findings
  (functional, basis, charge, multiplicity, and `broken_symmetry expected True
  observed False`). The tool description promises "A red finding names the
  field that needs repair".
- A plan whose only node is refused is never materialised: no review is
  attempted and the session ending names no reason. With a second, valid node
  the review refuses: "every initial workflow node requires a green preview
  ... (compiled, not previewed): compile_command previews a node" -- no
  reason, and a route (recompile) that fails identically; the ending also
  says "safe preview remain valid".
- Reaches the model: ORCA MDCI with no pair (the writer's refusal duplicated
  as an agent-layer RoutedContractError, Q14); Gaussian route refusals that
  do not depend on the bound state (Gaussian's validate() builds the route):
  `broken_symmetry` + semiempirical, `freq` + `numfreq`.

## Falsifiers and pre-registered outcomes

Premise P: a refusal whose reason exists in the hub does not reach the model.
- Census C1 (static + phase trace): every raise site in the Gaussian, ORCA,
  PySCF and xTB settings, writers and CLI builders, classified by the phase
  it can fire in (validation / preview / unexercised) with a state-dependence
  flag. Denominator: raise sites. Outcome reported as counts, not tuned.
- Census C2 (driven): each preview-phase refusal family I can trigger, driven
  through the public compile path on the base; record what the compile reply
  and the review carry. P is FALSIFIED if every driven refusal's reason
  reaches the model (compile reply or review) on the base.
- Replay R1 (archive): every compile-path refusal in the archived R10 session
  streams (named episode directories only), with the hidden reason recovered
  by re-running the preview on the tree that produced it where possible; what
  the session did in its next calls: took the route the hidden reason names /
  changed something else (a guess) / recompiled unchanged (blind retry) /
  abandoned the node or program / ended. Counted with the denominator. If no
  archived instance exists, reported as zero, not substituted.

Repair outcome (to be pre-registered in full before any live goal): the
compile reply and the review render one refusal text from one function; the
text is the program's own sentence, bounded and free of host paths; a
refused writer leaves no input file behind. A witness drives the public
entry point and is red on the base, green after.

## Oracle

The program's own refusal sentence (`str(exc)` of the exception the preview's
Click invocation raised), recovered by re-running the same argv on the same
tree. The host's rules are the oracle for "which route is legal"; no model
output is ever the oracle.

## Jobs issued

- 2026-09-25: none. (A read-only stream bundle was written to
  `/project/xlzhang/jiseung/r10/q26/corpus/` on the login node; it is not a
  job and nothing was downloaded.)

## Status

- 2026-09-25: base verified; governance, lessons, charter topics, Q20's
  record and the round merges read; gate open; scripted-model instrument
  built in scratch; census C2 begun (six cases above). Next: C1, the archive
  scan as a slot job, the repair.
