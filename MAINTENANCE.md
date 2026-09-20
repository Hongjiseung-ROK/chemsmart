# Maintenance notes: what has worked here, and under what conditions

**This file is evidence, not authority.** `AGENTS.md` is the product
charter and `CONDUCT.md` is the working discipline; where either disagrees
with this file, they win and this file is out of date. Nothing here is a
specification. Each section says what was tried, what happened, and what
the conditions were, so that a later session can judge whether its own
situation resembles ours — and depart from us when it does not.

The failure mode this file exists to avoid is the opposite of
under-documentation: a frozen architecture, defended by a document, that
prevents the science the product exists to do. If a rule below blocks a
legitimate scientific action, the rule is the thing to change.

---

## Adding a quantity the analysis plane can serve

**What we did.** Added `reached_positions` — the structure an optimisation
stopped on, as distinct from the geometry its thermochemistry block
describes.

**What it took, in the order the failures arrived.** An accessor on the
reader was not enough. It also needed: an entry in `SELECTOR_UNITS`; an
entry in `SUPPORTED_SELECTORS` (the request gate, without which nothing
can ask for it); an entry in `_SELECTOR_DIMENSIONS`; and a per-jobtype
declaration, because a declaration is a semantic claim about what the
value means *for the job that ran*. Four separate registries, each of
which failed loudly and separately, one test run at a time.

**What worked well.** The failures were loud and immediate, and each named
the registry it wanted. Threading a new quantity took four iterations of
about a minute each. We would not trade that for a single permissive path.

**What we would watch.** We declared the new selector for `opt` and `ts`
only, and deliberately not for `irc` (whose log prints one structure) or
`scan` (whose last printed structure is a scan point, a different thing).
Choosing the jobtypes is the scientific act; if a future program's log
carries a reached structure for a jobtype we excluded, that exclusion is
the thing to revisit, not the mechanism. PySCF's `irc` (2026-09-20) was
that case: its artifact keeps the branch's endpoint, so the reader
declares `reached_positions` for it and the optimised-geometry edge
admits a path stage only where the reader does; ORCA's `irc` still does
not.

## Adding a numeric policy the host decides science through

**What we did.** Added a 13th capability kind, `policy`, after finding
seven numeric thresholds living as bare module constants with no registry
and no rung — one of which put the bond/no-bond line at 1.120 Å for C–H
and reported a converged formaldehyde as having no C–H bonds.

**Why the existing kinds did not fit.** The ladder's only numeric kind was
`constant`, and all thirteen of its entries are literature values read
from a source text with provenance. A threshold is a decision the host
*makes*, not a value it *reads*. That distinction turned out to be the
whole reason the ladder could stay green over a false delivered vector: it
had no kind that could hold the thing.

**What worked well.** Declaring the policy with its value, unit,
functional form, owning module and consumers made the gap measurable
rather than invisible: one policy is `tested`, six are honestly
`advertised`, and two human-CLI conventions are marked `legacy`. The
`legacy` flag mattered more than expected — it lets a differential oracle
treat a *named* difference between conventions as a scientific
observation rather than a defect to eliminate.

**Condition worth stating.** We only declared policies we could name an
owner for. A policy with no single owning module would have needed the
owner first; the declaration is not a substitute for one.

## Repairs that create an owner

**What we did, twice, with different outcomes.**

In September a repair found a bad X–H tolerance, created
`_molecule_graph` as a single wide-tolerance perceiver, routed two
consumers through it, and its commit message said hydrogens now get the
ordinary buffer "in the one graph every host perception shares". Three
other callers kept the narrow tolerance. Nine days later one of them
delivered a wrong bond-pair vector into a scientific claim.

In the round after, a repair created
`WorkflowExecutionApprovalBundleV1.node_observation_lines()` as the single
reducer of a `tuple[dict, ...]` field — **and in the same commit added an
AST lint forbidding any other consumer from reducing that shape**, with a
planted offender that drives the production scanner.

**What worked.** The second pattern. When a repair creates an owner, the
same commit forbids the bypass mechanically. A comment does not hold, and
a commit message asserting a general property ("every", "the one",
"always") without a check is a claim that reads as done to every later
reader.

**Empirical note on the lint.** Our first version matched by field name
alone and over-captured: a field that is a tuple on one class and a
genuine `dict` on another was flagged. Narrowing it to *names the package
never uses as a mapping* made it correct and kept it general. This is the
same over-capture a marker regex without a left boundary made in the same
round, which suggests the general lesson is to scope a lint by what the
code *does* rather than what a name *looks like*.

## Adding a refusal

**What worked well.** Three properties, each earned by a loss:

- The refusal names the invariant it protects **and a legal route onward**.
  Measured over one round: the agent met 470 refusals, retried the refused
  tool in 60% of them, recovered within the session in 82%, and opened a
  guide in 2%. The refusal message, not the guide, is where the model is
  taught.
- The refusal carries the numbers behind it. When a perception convention
  blocks a geometry edit, the message now states the distance, the cutoff,
  the signed margin, the policy id and the routes out — because
  hypervalent, agostic and proton-transfer cases sit near such a line by
  their nature, and a bare "not bonded" told a session its structure was
  impossible when the host meant its threshold was close.
- The refusal is a **typed** error. A check that accepts any exception
  cannot tell a designed refusal from a defect, and a defect inside a
  refusal path is what ends goals. Assertions on refusals name the host's
  error class.

**What did not work.** Refusals that graded chemistry. Three checks on
composed uncertainty magnitudes fired 13 times with 0 legitimate
derivations prevented, and each was walked past by an equivalent
spelling. They became observations instead, and the delivery improved.

## Writing an oracle for a host-derived value

**Three kinds have been used here, and they catch different things.**

1. **Self-consistency** — declaration against implementation, name against
   state, parameter against round trip. Cheap, and it found real defects.
   **Its limit, measured:** `connectivity` satisfied every one of them with
   every declaration true and still reported that formaldehyde has no C–H
   bonds. A self-consistency oracle cannot see a wrong *value*.
2. **Metamorphic** — a relation that must hold over a transformation of
   the input. Worked where the host can synthesise the input (a bond
   graph over coordinates: perturb the distance, sweep the boundary). Did
   **not** transfer to a closed-form transformation over a program's
   printed block (per-atom mode participation), where the invariants are
   identities of the formula and the real risk — each program's mass
   table — needs the programs to test.
3. **Referential / cross-representation** — two host answers to one
   question must not disagree in silence. This is the one that caught the
   perception defect, and it needed **no chemistry at all**: the generator
   enumerates element pairs from the radii table, takes each declared
   policy's decision boundary, and probes below, at, above and *between*
   boundaries. It was red with 87 generated disagreements and green after.

**Condition that decides which applies.** A transformation that carries a
**threshold** has boundaries to generate from. One that does not (a
normalisation, an index remap) does not, and asking for a generated
adversarial domain there produces noise. The `policy` kind happens to
enumerate exactly the thresholded transformations, which is a convenient
accident worth preserving.

## Receipts, digests and schema growth

**What bit us.** We added a field to a thermochemistry receipt dataclass
and put it in the canonical digest body. Every receipt already written to
disk then failed revalidation, because the `record` an event carries **is**
the digest body and the validator requires the two to hash alike. Three
tests caught it; the run streams this laboratory has produced would have
stopped being evidence.

**What worked instead.** Carrying the new information in a field that is
*already* inside the body — `assumptions`, the free-text channel every
other thermochemistry control narrates itself in. No selection adds no
line, so historical digests are untouched; a real selection changes the
digest, which is what the field was for.

**What also worked.** When a receipt field's permitted contents had to
grow (adding a policy id and per-pair margins to a delivered adjacency),
replacing an exact-set check with an **allow-list** kept the invariant it
actually protected — no perceived *label* rides there — while admitting
measurement provenance. Read what a check protects before widening it.

**What bit us later, and the repair that needed repairing.**
`verify_provenance` compared every requested setting against the
artifact's spec, so the day a new applied-spec field was added
(`scf_stability`, contract v7) was the day every archived artifact failed
its own settings check -- caught by one archived-fixture test. The repair
was made at the comparison, not at the field: a field the artifact's own
contract vocabulary never carried is not compared against it. That repair
passed five red-to-green witnesses and the whole suite and was still one
condition too wide -- it skipped the field whatever had been requested,
so a pre-v7 artifact validated against a request for an analysis it
cannot contain. It now skips only a request that did not ask. The
condition worth stating: probe a new skip with the request it was not
written for, through the public validator, before believing it.

## Removing a capability

**What we did.** Withdrew a distance-derived `bond_order` from everything
the agent can reach, after measuring that it reads ethane's single C–C as
2.0 and benzene's as 3.0 at the buffer a previous repair had chosen.

**What worked.** Withdrawing rather than recalibrating, because the
quantity was on the wrong side of the boundary: where electrons are is not
a distance. The human-CLI consumers that need an rdkit molecule kept
working through rdkit's own perception, and a test now holds that no
agent-reachable module reads a distance-derived order.

**What to be careful of.** The observable-regression guard refuses a
replan that *removes* a stage, on purpose — deleting the node that carries
a finding is the cheapest way to clear it. When we tried to distinguish
two plans by changing a node id, that guard fired correctly and we changed
the discriminator instead of the guard.

## Changing a test that disagrees with a change

**What worked.** Reading what the test pinned before satisfying it. Two
cases in this round:

- A test asserted all-zeros connectivity on a fixture whose O–H is
  1.200 Å. It held only because of the defect, so the suite had encoded
  the defect as a requirement. We re-derived the fixture from chemistry
  (a 1.200 Å O–H is a proton in transit) and added a second test covering
  the case the first had asserted away.
- A test asserted `freq` declares what `opt` declares minus `converged`.
  Adding a reached-geometry selector to `opt` broke it — correctly, because
  a fixed-geometry frequency job has no second structure. The set
  difference gained a second member with the reason written down.

**What we avoid.** Changing an assertion to match new behaviour without
establishing which of the two is right. One test in an earlier round
*asserted the defect*, which is why this is a standing habit.

## Before a long live window

**What worked, measurably.** Three unrelated four-atom cases, one question
each, run before a twelve-hour window. They cost about 23 minutes and 100
seconds of engine time and found two host defects that 3,183 tests, 67
witnesses and five lint gates had passed over — one of which ended a goal
unsettled. The previous long window took twelve hours to reach its first
defect.

**Conditions that made them useful.** Genuinely different chemistry;
one question each; deliverables that are single selectors or a
subtraction; and a deliberately wrong starting geometry so the relaxation
has work to do. A case that cannot fail teaches nothing.

**What we also learned to do.** Freeze the tree for the window's whole
life and arm that as a falsifier. Editing the clone while a goal is parked
made one window's later cycles a mixed-tree observation, because each
per-node subprocess imports the clone fresh.

## Running from a worktree, and on a cluster

**What bit us.** A change was developed in a second worktree while the
interpreter held an editable install of the first. With `PYTHONPATH` set
to the worktree, `python -c` and pytest still imported the *other* tree
whenever the shell's current directory was the first clone, because the
current directory is searched before `PYTHONPATH`. Nothing failed; the
suite simply tested code that had not changed.

**What worked.** Stand inside the worktree (or a neutral directory), set
`PYTHONPATH` to it, and print `chemsmart.__file__` once before believing
any local run. On a cluster, never point at the deployed checkout: archive
the worktree, unpack it in the run's own directory and put *that* on
`PYTHONPATH`. When the personal server profile's core or thread counts
trip a resource-mismatch validation at a small `-n`, copy the server YAML
into a private config directory beside the run and point
`CHEMSMART_CONFIG_DIR` at it; the profile under `~/.chemsmart` stays as it
was. Two separate investigations each lost several steps rediscovering
it before it was written down here. A third then ran four live goals
this way and added the step that makes the run evidence: a digest over
every tracked file of the packed tree, printed locally, recomputed on the
far side before anything is issued, and written into a seal that predates
the first goal -- otherwise nothing shows which code ran. The site's own
recipe (paths, scheduler lines, a template goal script) belongs with the
site's operating notes, not in this repository.

**Conditions worth stating.** `-m` is `--mem-gb` before the program name
and `--multiplicity` after it. PySCF fixtures are generated in the
cluster's compute environment, never on a laptop; reading one back needs
only h5py. A green `--fake` run says nothing about the interpreter, and
an API probe of the engine is a way to learn its behaviour, never evidence
for a delivered capability.

## A writer and a reader are two tables

**What bit us.** The PySCF driver's `RESULT_UNITS` said `normal_modes`
are amu^-1/2 and the reader's per-selector unit table said
`dimensionless`; `vibrational_mode_atom_participation`, declared for
`pyscf:hess`, was refused on every real PySCF Hessian while every
synthetic test passed, and the tool surface reported the selector as
simply absent because `available_selectors` swallows the refusal.

**What worked.** Deriving the reader's expectation from the writer's
table by dataset name, so a disagreement can only be an artifact written
under another contract; and a generated test that reads every declared
selector on an archived real artifact of its jobtype, accepting only
`MissingQuantityError` as an honest absence. With the units agreeing the
same selector then died on `modes or []` over a numpy array -- the
synthetic test had fed the helper lists -- which the archived-fixture
test caught in the same run.

**Condition worth stating.** The blocker recorded against archiving
real PySCF results ("pyscf not in the controller env") was false:
reading an `.h5` needs only h5py, which the controller env has. Verify
a deferred note's reason before believing it.

**The same defect, one layer up (2026-09-19).** A goal was meant to name
each planning session's stream on its own ledger. The code read
`session.run_id`; a live session result carries `session_id` and no
`run_id`, and the only test handed it an object with `run_id` on it. Four
live goals wrote zero `session_stream_recorded` rows while the test
stayed green. A test standing in for a live object uses its live type; a
stand-in that supplies the attribute the code reads proves only that the
code reads it (`f6ce5374`,
`tests/agent/test_a_cycle_settles_on_its_own_stream.py::test_a_live_session_result_names_its_stream`).

## A concept the record should know

**What bit us.** `scf.reference_unstable` reached sessions in a wake for
days while no rule or guide said what it meant; a leaf sentence denied a
Hessian the host had shipped five days earlier. Both were found by hand.

**What worked.** The evidence graph takes concepts from the registries a
change must touch anyway -- a job type, an anomaly signal, and any setting,
selector, operation or constant a sentence or a rule's boundary names --
so they appear with no graph edit, and `graph.py orphans` lists the
signals no sentence explains. A durable concept no registry owns (a
convention, a negative result, a supersession) gets a `graph.yaml` node
with its falsifier, in the same commit as the code that introduces it.

## Adding a PySCF quantity

**What it takes, in order.** One line in the driver skeleton (the
value PySCF computes, taken after the final SCF), one `RESULT_UNITS`
entry (the writer refuses an unregistered numeric dataset), a property
on `PySCFOutput`, an accessor and a jobtype declaration in the reader, a
`_SELECTOR_RESULT_DATASETS` entry (the unit comes from the writer), a
dimension and a display unit, a structural state, and an assertion on
an archived fixture. A result contract bump when a dataset is added; v3
artifacts stay executed evidence because the applied-spec vocabulary is
shared. The fixture assertion is what makes a half-threaded quantity
fail loudly.

**What we would watch.** A quantity computed before the final SCF of an
optimisation would belong to a structure the artifact does not carry;
the driver's stage loop is where that order is fixed.

## Adding a PySCF calculation class

**What it takes, in order** (the response and correlated stages of
contract v5 were added this way, 2026-09-13). (1) A settings field and
the cross-field rules in `PySCFJobSettings.validate()`, each refusal
naming its route; a stage list derived from the resolved settings in
`pyscf_stages`, which the job classes, the writer, preflight and the
result validator all call. (2) The capability's parameter domain,
imported from the settings vocabulary rather than copied -- this is
what generates the round-trip obligation, and the fake preview's
verifier compares every declared value with the applied spec. (3) The
driver stage in the skeleton and its `RESULT_UNITS` entries; a contract
bump when a dataset or a spec field is added, with the applied-spec
vocabulary keyed per contract version so every archived artifact's
provenance digest still reconstructs. (4) Properties on `PySCFOutput`.
(5) Reader accessors, the jobtype declaration, a structural state, an
electronic provenance, a unit and a dimension, and membership in
`SUPPORTED_SELECTORS`. (6) If the class has an iterative failure: a
native error class from the artifact's own flags, a terminal word, and
a repair-menu route that names a public control the settings object
carries -- add the control first. (7) Sensor facts only where the
number is the host's, with no threshold unless a sealed case earned
one. (8) Fixtures generated by the real program through the CLI, with
`reference.json` written from PySCF's own API in the compute env, and a
differential from another program at matched conventions where one
exists. (9) Leaf sentences as registered rules with measured
provenance. (10) A witness through the public surface, red first. (11)
A sealed live case before any release row moves to `recorded`, per
configuration.

**What we would watch.** An upstream property that is off by one
(PySCF 2.14's excited-state gradient scanner indexes its per-root flags
with the 1-based root) is found by a fixture generated at the boundary
value, never by a docstring; and a stage's quantities computed before
the final SCF belong to a structure the artifact does not carry.

**What bit us adding `irc` (2026-09-20).** Upstream's convenience entry
point failed before its first step: `geometric_solver.kernel(...,
irc=True)` under PySCF 2.14 and geomeTRIC 1.1.1 raises on a topology
PySCF's engine never builds, so calling the library it wraps, with that
one step added, was smaller than any workaround. An upstream word turned
out to be a sign: geomeTRIC's `forward` follows an eigenvector whose sign
the eigensolver chose, so the host fixes the sign and the validator
measures it again from the frames; only two nodes on one saddle make that
testable. And the second stage that moves the geometry found every place
that had assumed `opt` was the only one -- the final SCF restart, the
reached structure, the handoff edge -- which is why `PYSCF_MOVING_STAGES`
is a declaration; measuring the IRC endpoint's restart (one SCF cycle)
beside an archived optimisation's (six) exposed that the optimisation's
restart had never used the density its record claimed.

## Retiring a mechanism whose field lives in a digest body

**What we did.** Retired the per-plan stationary-point policy: the
class, its parser, the deferral that admitted an unclassified Hessian,
the delegation string that subtracted a finding, and the validator's
policy argument. The `stationary_point_policy_sha256` (always `""`) and
`stationary_point_policy` (always `None`) fields stayed in the digest
bodies of the validation receipt, the frozen approval, the review and
the bundle, because every record on disk hashes a body that carries
them.

**What worked.** A read-only sweep of every artifact the host holds,
before the commit: 60 PySCF artifacts opened, the seven historical
`unclassified` receipts still analysis-ready, the four failed runs
refused as before. A record that carries a policy is refused as not
this host's, so the retired mechanism cannot return through a record.

## Delegating a review

**What worked.** Two reviewers, kept independent until both returned, each
given the same verified evidence and the same fundamentals verbatim, with
different primary questions — one forensic ("why did prevention fail"),
one architectural ("how should the pattern evolve"). They disagreed on a
central point, which was the most useful thing they produced: it located
the real decision instead of confirming a plan.

**What we insist on afterwards.** Every load-bearing claim verified
against source, behaviour and run record before it enters a synthesis. In
this round both reviewers corrected me and one of their corrections was
itself slightly wrong (a commit id that was a pre-rebase duplicate). Two
of their findings were about defects in work committed hours earlier.

## Measuring a surface change against the Agent, not against a prompt

**What we did.** Changed what the model reads (the operation enum, the
guide index, which signals open a guide) and asked whether the Agent got
scientifically better or worse, on the same requests, before and after.

**What worked.** A *pristine* baseline arm. `git archive HEAD | tar -x -C
/tmp/...` gives a read-only copy of the pre-change tree that the runner
points `PYTHONPATH` at, so a baseline session issued after the working
tree has moved still runs the code it claims to. We lost the first
attempt at this: two sessions started before the edits and two after, on
one tree, and only the timestamps said which code each had imported.
Every session's log records the tree root and a digest of
`chemsmart/agent/**` beside its transcript, so the arm is auditable
afterwards.

Requests written before the change and never edited. Each one names a
molecule and an observable and nothing about guides, tools or routing,
and each was checked against `guides_from_text` *before* issue so that
"what the old router would have opened" is a recorded prediction rather
than a reconstruction. The one pair that carried the round (B1, the
distance from a carbon to its molecule's centre of mass) was chosen
because no guide title contains the words a chemist would use for it.

**What we would watch.** One provider key does not serve many concurrent
sessions. With two cluster goals running, local planning sessions on the
same key sat at `turn_deadline_exceeded` (300 s, zero input tokens) and
made no model turn at all for twenty minutes; the moment the local
sessions were killed the cluster cycles resumed. A session with zero
provider turns is not a weak observation to be kept, and not a run to be
re-rolled either -- it is no run, and the honest record says so. Budget
live arms serially, or accept that the arm will be smaller than planned.

**A trap.** macOS ships bash 3.2, which has no associative arrays.
`declare -A TASKS; TASKS[B3]=...` silently evaluates each subscript
arithmetically, so every label resolves to the last assignment and two
baseline sessions ran a request meant for another label. Use a `case`
function for label-to-text maps in campaign scripts.

## Tool search: what a discovery backend has to return

**What we did.** Replaced the stem-and-guide tool tree with one
searchable catalogue plus three exposure modes, and measured the Agent
on the same request before and after each change.

**What worked, and the number that matters.** The initial context fell
from 92,848 bytes (19 tools) to 45,150 (8 tools), and it is now
*byte-identical* with 2,000 synthetic entries added to the catalogue --
which is the property the round exists for. The old ceilings could only
be raised; this cannot be satisfied by raising anything.

**A search that returns a name costs a turn for nothing.** The first
live session on the new architecture planned correctly and took
twenty-five searches to do it, four of them for the literal string
`declare_requested_observable`, a name it already had from an earlier
result. `search_capabilities` was returning names; a name is not
something a model can act on. Making a search *load* what it returns --
which is what the reference backend's `tool_reference` expansion does --
took the same request from 25 searches, 15 provider turns and 46 tool
calls to 5, 9 and 15, and from 7m10s to 5m08s, with the same plan at the
end. If you build a discovery backend, finding and loading are one turn.

**What we would watch.** The model's own strategy is to survey broadly
and then work: with `limit: 8` on five searches it had 47 of 52 entries
loaded by its second turn. The initial context is still small and still
scale-independent, but the *steady state* of a long session approaches
the eager arm. That is the model's choice and not a defect; constraining
it would be the host deciding what the task is about, which is the thing
this architecture removed.

**A defect worth knowing about.** One session is one `turn_id`. An event
whose idempotency key is `{turn_id}:{digest of the arguments}` collides
with itself when a session repeats a call, and the event store refuses
the write -- which reached the model as the *tool* failing. Anything a
session may legitimately do twice needs an ordinal in its key.

**`chemsmart agent plan` needs `--execution-envelope`.** The driver always
names a review file, and a live session refuses a review without an
envelope, so the command settles `returned_to_human` before any provider
turn and prints an `AttributeError` from `result.public_summary_json()`
on a `None`. Write a four-call bounded-local envelope and pass it; the
command never launches an engine either way.
