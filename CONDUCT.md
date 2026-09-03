# ChemSmart Development Conduct

This file binds every session that changes this repository, human or
model. It says what a test may exist for, what a gate may be, how large
a change may be, and how a change is proven. `AGENTS.md` is the product
charter; this is the working discipline beneath it. When the two
disagree, the charter wins and this file is wrong.

## 0. The values, in the order they win

When two of these conflict, the earlier one wins, and the conflict is
written down.

1. **The host's word is true.** Every verdict, settlement, match and
   refusal is backed by a receipt and means what the physics means. A
   word that can be false for a real structure is a defect: `failed`
   for a quasi-planar radical whose inversion barrier lies below the
   zero-point level, `achieved` over an undelivered headline, `agreed`
   by dimension alone.
2. **One human decision per goal.** Displayed, one-shot, digest-bound;
   a delegated approval is disclosed on every record it touches.
3. **Replication before belief.** An anomaly, a number or a claim
   stands after it reproduces under a stated perturbation; N runs are
   N observations, and a weak run is never re-rolled.
4. **Freedom of route.** Any chemically valid route, decomposition or
   interpretation is admissible; a gate exists only where language
   cannot compute an invariant, and a refusal names the route.
5. **The anomaly has standing.** What the host detects it records with
   the numbers that tripped it, whether or not it was asked for; the
   model interprets, the human judges, and a gate is never loosened to
   buy a discovery.
6. **Errors first, receipts always, the seal is the method.**

## 1. What a test may exist for

A test exists for exactly one of three reasons:

- **Heartbeat.** The live `chemsmart` CLI compiles and safely previews
  a program and jobtype through project YAML, and a written native
  input reads back to what was requested.
- **Reachability.** A tool the Agent can call reaches the ChemSmart
  function it claims: every advertised parameter is settable, written,
  and read back; every declared selector is requestable; every operation
  in the vocabulary is exposed.
- **Production path.** A release-qualified path runs end to end on
  archived real program output: the approval chain, the provider-free
  executor, the result readers, unit and dimension arithmetic, the goal
  driver's settlements, and one pin per code gate that protects a
  scientific or authority invariant.

A test that pins wording, a single observed stream shape, a private
helper, or a historical defect a general invariant already covers is not
written; if it exists, it is deleted. A test says what it pins with a
``capability(...)`` marker (``kind:id``, a trailing ``*`` for a kind),
which is how the capability ladder learns that a capability is tested. A
defect earns one general test at the invariant it broke, never a test of
the case. Tests verify mechanics; a real observation through the public
surface establishes behaviour, and no test is ever cited as engine
execution.

## 2. What a gate may be

A refusal lives in code only when it protects an invariant that
language cannot compute or that an optimising model would erode:

- molecular identity, atom order, and geometry lineage;
- explicit charge and multiplicity, and the arithmetic of impossible
  states;
- the single human decision: the digest-bound one-shot bundle and the
  equality of recompiled argv with reviewed argv;
- no model-authored native input, path, shell, or status;
- the execution envelope's budgets and the dispatch target;
- units and dimensions across the analysis DAG, and the per-jobtype
  meaning of a selector;
- host-rendered claims and completion receipts;
- credentials;
- the terminal-state vocabulary and the stationary-point rule;
- the observable-regression guard, because deleting the node that
  carries a finding is the cheapest way to clear it.

Everything else is a sentence at the point of use: on the tool whose
argument it governs, in the wake context that carries it, or in a guide
the host opens. A sentence is a registered rule with an id, a placement,
and the provenance that earned it (``chemsmart/agent/rules.py``); prose
that lives nowhere else is not a rule. Before a gate is added, its
reachability from the model is measured by a direct probe; a check the
host already normalises away is not a gate and gets no sentence. A gate
earned by a live loss names that loss in a comment.

## 3. How large a change may be

- One general commit per defect or affordance, at the smallest layer
  that owns it. A repair that rescues exactly one case is the wrong
  repair.
- Never repair while a session is live; a defect exists when a stream
  shows it.
- A deletion is its own commit, so it reverts cleanly.
- A premise stated in a plan is verified against the tree before the
  commit that depends on it; a corrected premise is written into the
  commit message as loudly as the change.

## 4. How a change is proven

- After every change: the fast suite with its exit code checked, then
  `ruff check chemsmart tests`, `black`, `isort`, and the docs linters as
  fixed points.
- A behavioural change to the Agent is followed by a sealed live
  observation on chemically different tasks. N runs are N observations;
  a rate lives inside one contiguous window; a weak run is never
  re-rolled.
- The seal is written and closed before issue, with input digests, the
  runtime configuration, the physics bands never scored, and the
  falsifiers armed. If it leaks, the case is void and reported void.
- Physics outranks the scoreboard: every delivery is read against
  geometry, arithmetic, and the constants registry, and
  achieved-per-contract and wrong-per-physics are both written down.
- Errors are reported as loudly as wins, in the first section. An
  inferred mechanism reported as fact is corrected in place.
- An insight is registered in the memory ledger the day it is read.
- A planted gem is checked to survive the optimiser before issue, a
  planted false gem is checked to exist, and the task text never asks
  for the observation the change under test is meant to elicit (the
  first STANDING window: a planar cyclohexane relaxed to the
  twist-boat unplanted, MMFF benzenes gave no imaginary modes, and
  both arms reported saddle character because the text asked).

## 5. The invariants every session carries

The claim ladder -- proposed, planned, materialised, previewed,
approved, executing, engine-complete, parsed, scientifically validated,
interpreted -- is owned by the deterministic host alone. Provider text
is never execution evidence. The hub invariant holds: one public
YAML-and-CLI layer, no second approval plane, no LLM grading a step.

## 6. Repository hygiene

- One branch per round; push only on fresh explicit instruction.
- Campaign evidence, licensed media, credentials, private transcripts,
  and generated program inputs never enter Git. `experiments/` is
  untracked scratch and is never touched.
- `/opt/chemsmart` stays stable; work happens in the research clone with
  `PYTHONPATH` set, because the controller environment shadows it.
