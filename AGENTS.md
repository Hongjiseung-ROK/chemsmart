# ChemSmart Product Charter

## Mission

ChemSmart is the canonical, CLI-first hub through which humans and AI agents
operate computational-chemistry programs. Scientific intent belongs in
readable project YAML and typed scientific DAGs. ChemSmart validates that
intent, materialises program-native inputs, compiles the public CLI, controls
execution, and returns typed scientific evidence.

The model is a computational scientist, not an input-file generator. It may
choose a defensible method, program, decomposition, and interpretation when a
task leaves them open. It must not bypass ChemSmart by inventing native input,
shell commands, execution status, or result values.

## Product boundary for version 3.1.4

The production Agent supports:

- project-YAML creation and validation;
- ChemSmart CLI compilation and safe preview;
- causal scientific workflow planning;
- inspection and typed analysis of supported results; and
- explicitly approved execution on release-qualified CPU paths: ORCA
  single-points, optimization/frequency, transition-state, excited-state,
  relaxed coordinate scans, intrinsic reaction coordinates, and serial DAG
  workflows; PySCF ``sp/opt/hess``; and xTB ``sp/opt/hess``.

ORCA ``scan`` is qualified for approved execution: a relaxed torsional profile
ran through the ordinary plan, preview, single human approval, and provider-free
execution path, and its surface is read into typed quantities by the same
analysis layer as any other result. A scan's driven coordinate is carried on the
workflow node, not in project YAML, because it is a fact about this molecule in
this calculation rather than reusable method rationale.

ORCA ``irc`` is qualified for approved Agent execution: a TS-to-IRC
workflow — one converged transition-state search feeding two
intrinsic-reaction-coordinate runs, each consuming the transition state's
own geometry and analytic Hessian as role-distinct producer bindings —
was planned, previewed, approved in one displayed decision, executed
provider-free, validated, and delivered host-rendered claims on a
qualification target; that approval was made by an owner-delegated
reviewer and the record names it as such. Admission keys each producer
data edge by its consumer role, so distinct roles on one node coexist
while one role never admits two edges, and execution readiness demands
every binding before launch. ORCA writes the reaction path to an XYZ
sidecar rather than into the log; the log's only printed structure is the
starting point, so every state-dependent selector — geometry, energies,
orbitals, dipoles, spin — is deliberately not declared for the jobtype:
the first executed chain rendered the transition state's own distances as
both endpoints, and its printed energy differs from the true endpoint by
the entire barrier. Only job-level facts (charge, multiplicity, direction,
solvation route, atom identity) are declared, and selector declarations
now gate extraction rather than merely advertising coverage. The
trajectory sidecar enters the typed layer as a registered geometry
artifact and is readable there today; a log-native path route is future
parser work, so whether a saddle connects two particular minima remains an
observation a scientist makes from the trajectory artifact, not a
host-rendered claim.

ORCA ``modred`` is declared for planning, preview, and native-input generation
only. Constrained optimisation is expressible and previewable, and no
constrained optimisation has yet run here, so this release does not describe it
as completed Agent execution.

A typed analysis chain planned with a workflow is carried verbatim in the
review packet and the approval bundle, and the single human approval covers
it: after every approved calculation node validates, the provider-free
executor runs the chain and renders a completed-analysis report. The model
never writes those numbers; interpretation and the recorded scientific
decision remain a session act.

``compose_molecular_arrangement`` places two identity-bound geometry
artifacts into one arrangement at an explicit atomic contact. The host owns
the placement mathematics and the composed bytes with full parent lineage;
the model owns the fragment, contact, and distance choices, must bind the
arrangement's charge and multiplicity explicitly, and the consuming stage is
a new workflow for review.

``derive_molecular_species`` is its mirror: it takes an ordered subset of one
identity-bound parent's atoms, which is the single operation underneath
homolysis, deprotonation, and fragment extraction. The model names either the
atoms to remove or the atoms to keep and the host records both, copies the
parent's coordinates unchanged, and owns the derived bytes with full parent
lineage; the derived geometry is therefore a starting structure rather than a
relaxed one. Derivation never infers an electronic state — removing a
hydrogen gives a radical or an anion depending on where its electron went —
so charge and multiplicity are bound explicitly afterwards and the consuming
stage is a new workflow for review. Whether the result is one species or
several separated pieces is recorded as an observation, not judged.

The third producer selection rule (``validated_producer_orca_hessian``)
declares a validated frequency-bearing ORCA producer as a legal source for
an ORCA transition-state search's ``--inhess-filename`` starting Hessian,
and the materialised input carries the file natively; the starting Hessian
may carry any imaginary-mode count and the observed count is recorded.
Declaration is not completion: when the geometry and the Hessian both
arrive as producer edges the pair freezes into one approval, while a lone
Hessian edge on a directly supplied geometry is still refused by the
bounded review, so the reachable route is the producer pair. No workflow
has yet executed through this rule, and producer-Hessian TS seeding
therefore remains admitted, previewable intent rather than completed Agent
execution. Wavefunction
(gbw) reuse has no CLI surface and is not claimed.

The fourth producer selection rule (``validated_scan_minimum_geometry``)
carries a validated ORCA relaxed scan's minimum-energy sampled point into
a downstream calculation inside one approval. A scan ends at a surface,
and which point travels is a scientific judgement; the rule does not move
that judgement to the host — its meaning is exactly the minimum-energy
sampled point (ties resolving to the lowest point index), the planning
session declares it per edge, and the displayed review names it, so the
scientist approves that settlement explicitly. Any other point on the
surface remains the explicit scan-point binding, whose consuming stage is
a new workflow with its own review. This rule is qualified through
completed Agent execution: an executed torsional scan's carried minimum
seeded an optimization that validated as a true minimum, escaping a
saddle a direct optimization deterministically returned to.

A host-owned literature-constants registry holds the values a scientist
takes from the record rather than computes — an aqueous proton free
energy, a standard-state correction, a reference acid's measured pKa —
each entry a version-pinned name with a value, a unit, and the
standard-state convention that gives the number its meaning. An
expression selects an entry by name through the ``constant`` operation
and the host resolves it; a ``literal`` remains recorded as
model-authored, a ``constant`` as host-owned, and an unregistered name is
refused when planned, naming the registered set. Domain conversions own
their conventions as named operations (``gibbs_to_pka`` owns
pKa = ΔG/(RT ln 10)). The displayed review and the completed-analysis
report render every selected constant with its value, unit, and
convention.

Aqueous pKa is qualified as a composed workflow rather than a task
feature: no pKa-specific code exists in the Agent or analysis layers.
Two chemically distinct constructions have executed through the ordinary
plan, preview, single displayed approval, and provider-free path — a
direct absolute cycle (solvated opt+freq of an acid and its derived
conjugate base, thermochemistry at an explicit solution standard state,
the registry proton constant, ``gibbs_to_pka``) and a proton-exchange
cycle in which the proton term cancels and a registry experimental datum
anchors the scale, reusing registered results from the first as typed
inputs to the second. Both deliveries carried the method's documented
continuum-solvation systematic openly in host-rendered reports; neither
licenses an accuracy claim. An analysis kernel's scientific refusal, or
a registered result missing from the workspace, settles its node as a
typed finding and the run delivers every receipt that survived.

A batch is N enumerated records under the one displayed decision, not
an autonomy feature, and no task-specific batch code exists. A
workspace chemsmart ``.db`` database is an inspectable artifact whose
stored per-record fields (charge, multiplicity, energy, optimized
flags) are observations from the records' own provenance, never
bindings: a session enumerates records, extracts one record's exact
coordinates into a lineage-carrying geometry artifact — database
digest, record, explicit structure selection, with multi-structure
ambiguity refused rather than resolved — and binds identity and
electronic state explicitly per record, exactly as for a derived
species; execution never reads the database again. N records are
planned as N disconnected sub-DAGs in one workflow; the record
boundary is derived from the plan's own edges and stored nowhere; the
displayed review carries one row per record — molecule, explicitly
bound state, origin, and any stored-versus-bound mismatch flagged
loudly rather than refused — beside full derivation and
database-record lineage panels, and no row is ever elided. Execution
is sequential and record-major, and the provider-free executor
enforces the displayed envelope itself: the episode window, the
postprocessing reserve, and the engine-call budget, which counts
replayed receipts so it spans the approval's whole life. One record's
failure settles that record while the others deliver — the approved
chain walks whether the calculation partition completed or not,
unfulfilled analysis settles as typed findings naming the producer,
and the result and report carry per-record delivery verdicts with
reached states and verdicts as separate facts, never-attempted
distinct from failed, and deliberately no aggregate quantity: a batch
of N is N observations. A run continues by re-entering its own run
directory — the consumption ledger admits the same bundle whose
durable stream records the incomplete run, appends each resume naming
the remainder, replays terminal nodes from their receipts without
re-executing anything, reports a mid-engine interruption as ambiguous
pending human reconciliation, and refuses a completed approval
outright. This surface is qualified through completed Agent
executions: a six-record opt+freq batch (four whole deliveries, one
engine timeout by declared budget, one genuine saddle delivered as a
failed verdict; three invocations, six engine launches total); the
composed aqueous pKa carried over a four-acid database in one approval
(three pKa values delivered with the registry proton constant and the
documented anion systematic stated, the fourth settled typed on its
own saddle); and a mid-engine interruption resumed with zero
re-execution.

``edit_molecular_geometry`` sets one internal coordinate of an
identity-bound geometry — bond length, angle, or torsion, the same
three coordinates a scan drives — as a host-owned rigid motion. The
model names the coordinate, the target value in the coordinate's own
unit, and which side moves; which side moves is a scientific choice
with three incompatible library conventions behind it, so it is named
by one of the coordinate's own atoms, never defaulted, and the receipt
enumerates every atom that actually moved. The host measures the
coordinate before and after with the same arithmetic the typed
analysis layer uses, verifies it reached what was asked, and records
close contacts and connectivity changes as observations, never
verdicts. Refusals are structural only — an axis that is not a
perceived bond, a ring a rigid motion would tear (which differs per
coordinate), collinear or out-of-range atoms; no energy exists at edit
time and a requested value is never refused on scientific merit,
because grading it is what the consuming optimisation is for. An
edited geometry is a starting structure; atom count, order, and
formula are preserved, so parent atom i is edited atom i and a later
analysis may re-measure the same coordinate on the relaxed result.
``append_molecular_atom`` is derivation's mirror: one atom, placed by
the three internal coordinates that define its position against three
anchor atoms; parent indices are unchanged and the appended atom is
last. Both operations bind no electronic state — adding a hydrogen
gives a cation or a radical depending on whether it brought an
electron — so charge and multiplicity are bound explicitly afterwards,
the consuming stage is a new workflow, and the displayed review
renders every hop of a built geometry's chain root-first, because the
hop that decides what the molecule is can sit at the root.

This surface is qualified through completed Agent executions in which
requested-versus-relaxed is the delivered observable: an
N-methylacetamide rotamer study whose cis form is reachable only by a
deliberate amide-torsion edit (the edit survived relaxation to 0.01°;
a task-supplied claim that the amide C–N is an ordinary 1.47 Å single
bond was contradicted by relaxation at 1.363 Å on the same page; the
trans rotamer validated as a strict all-real minimum; successive
sessions diagnosed methyl-rotor saddles from failed strict verdicts
and repaired them by displayed edits, and the completed series
established that the cis form's two methyl rotors are geared, so its
strict minimum is recorded as honestly unconfirmed rather than
claimed); a 1,2-difluoroethane transfer in which the session built
both gauche enantiomers by edits, predicted the gauche effect with
its mechanism before any number existed, and physics returned gauche
lower with the requested 60° torsions relaxing to 71.9°; and an amide
protonation study in which both conjugate acids exist only through
appended protons, the O-protonated cation validated as a strict
minimum confirming the session's resonance-based site prediction, and
the appended O–H and N–H bonds relaxed within 0.01 Å of their
requested lengths. N edits are N observations; no spatial-competence
score or aggregate exists, and nothing grades a request except the
relaxation that consumes it.

A vibrational frequency states how fast a mode moves and never which
atoms move in it, so a session facing a small imaginary mode could not
separate one methyl rotor from another by magnitude alone.
``vibrational_mode_atom_participation`` is each atom's share of a mode's
squared displacement, one row per mode summing to one, derived by the
host from the displacement vectors the program itself printed and
renormalised so the quantity means the same thing across programs whose
vectors do not: ORCA, Gaussian and xTB print Cartesian displacements at
unit norm while PySCF returns the same physical displacement scaled by
one over the square root of the reduced mass, and a per-atom share
divides that per-mode scalar out along with the arbitrary eigenvector
sign and the program's coordinate frame. What renormalisation cannot
remove is each program's atomic mass table, and that limit is stated
where the quantity is defined. The share is an observation: naming a
mode's motion is the scientist's claim, never the host's. Because the
individual eigenvectors inside a degenerate set are an arbitrary basis,
``vibrational_mode_degeneracy_group`` records which modes share a
frequency within a stated tolerance, so a reader can see that a mode has
company before assigning motion to it. Declared for ORCA ``opt`` and
``ts``, xTB ``hess``, and PySCF; Gaussian is deliberately undeclared and
unadvertised, because this release never executes Gaussian and its
displacement block varies with options the reader cannot yet detect.
This surface is qualified through one completed re-observation of the
case that motivated it: given two converged amide rotamers whose strict
verdicts failed, a session read the table and named the acetyl methyl
rotor in one and the N-methyl rotor in the other, a distinction seven
earlier sessions could not draw from frequencies alone.

Electric charge is a dimension, so an electrode potential is one too.
Potential is derived as energy per charge rather than asserted, which
makes ΔG = −nFE dimensionally checkable and leaves the Faraday constant
in the unit system where a definition belongs rather than in a registry
of measured values. ``gibbs_to_redox_potential`` owns E = −ΔG/(nF) and
with it the IUPAC sign, so a favourable reduction has a negative free
energy and a positive potential; referencing an electrode stays ordinary
subtraction against a registered constant, so which electrode a value is
quoted against remains visible in the expression.

A literature constant now declares the convention family it may be
combined within and what it is for. Constants that look independent are
often matched pairs — an absolute electrode potential means one thing
beside the proton solvation free energy determined on the same scale and
another beside a different one — and the literature circulates the
halves separately, so a crossed pair fails silently with both values
correct and the answer wrong. The family is displayed and never refused,
because choosing a convention set is a scientist's judgement and a mixed
selection can be deliberate. A family says nothing about standard state,
and that limit is stated where a session reads it: the purpose phrase
says which entry belongs beside which, and where a finished composed
value is registered it says to prefer it. Values never reach the model;
a choice is made from a name, a unit, a family and a use.

Two refusals move to where the human decides rather than where the
engine finds out. An electronic state that no molecule can have — a
negative electron count, more unpaired electrons than electrons, an even
count paired with an odd number of unpaired — is refused when the state
is bound and wherever a node rebinds one, program-neutral, admitting
every state the arithmetic permits and preferring none; parity survives
an effective core potential because a standard ECP removes closed
shells. An expression node that reads a value no earlier node or
analysis input provides is refused when planned, because expression
nodes evaluate in the order given and the alternative is discovering it
after every engine has finished.

A proton-coupled electron transfer square scheme is qualified as a
composition, with no PCET-specific code in the Agent or analysis layers.
One phenol parent produced three further species by three different
operations — the hydroxyl hydrogen removed to give a geometry bound once
as the closed-shell anion and once as the neutral radical, and a radical
cation that moves no atoms at all and is a second electronic state on
the parent's own geometry — planned and previewed together, approved in
one displayed decision, executed provider-free, validated as four strict
minima with clean doublet spin, and delivered as host-rendered aqueous
pKa values and reduction potentials against the standard hydrogen
electrode. The delivered numbers carry the method's documented
systematic openly and license no accuracy claim: the two legs containing
the phenoxide anion disagree with experiment by 9–11 kcal/mol in the
same direction while the leg containing no anion is off by a third of
that, which is the continuum description of a small localised anion
without explicit hydrogen bonding, appearing in two independent
observables at consistent magnitude and sign. An earlier review of the
same scheme was denied because its chain composed the aqueous proton
free energy from terms at two standard states; catching that before an
engine ran is what the single displayed approval is for.

A completed solvated ORCA result can say what its solvation cost. The
electrostatic term, the SMD cavity-dispersion term and the cavity surface
area are declared for ``opt``, ``sp`` and ``ts`` beside the solvation
model and the solvent name, and each reads the last printed block because
an optimisation prints one per SCF step. Absence is meaning rather than
failure: a gas-phase result reports the terms absent, and a CPCM run has
no cavity-dispersion term, which is how it differs from an SMD run. The
terms report what the program *applied*, which is not always what the
route requested, so they are read beside the model rather than instead of
it. Only ORCA declares them — no archived Gaussian log carries the
printed terms, PySCF folds solvation into its total energy with no
decomposition, and every archived xTB run has solvation switched off,
so for those three there is nothing a declaration could have audited.

Per-atom populations are positional and named by the scheme that produced
them. Atom-label schemes disagree between programs — ORCA numbers atoms
globally while xTB counts within each element, so the same atom is
``C3`` in one and ``C1`` in the other — and a mapping cannot be reordered
safely afterwards, so labels are resolved against the molecule's own
symbols at the reader and a scheme that does not match is refused rather
than guessed. Mulliken and Löwdin are declared for ORCA because ORCA
prints both without being asked; Hirshfeld and CM5 are parsed and not
declared, because reaching them means spending the project route channel
on a directive that changes no method, which is a question about that
channel rather than about the quantity. The scheme is in the name because
the schemes disagree: on one phenoxide anion Mulliken places more than a
whole electron of excess charge on the hydroxyl oxygen where Löwdin
places about a third of one, and neither is "the charge on the oxygen".

This surface is qualified through one completed analysis-only delivery
over four finished results with no engine launched, and the delivery
found a defect the release had carried for years. ORCA prints one column
of populations for a closed shell and two for an open shell, charge then
spin, under a header whose text contains the closed-shell header, so a
reader taking the last number on the row returned charges for restricted
results and spin populations for unrestricted ones under a single name.
Nothing had noticed because nothing in the typed layer had ever read
them; a session that added the vector up saw a neutral radical's charges
sum to +1.00 e, flagged it as unresolvable from its surface rather than
explaining it away, and the trace led to the reader. The values are now
read by position, the per-atom sum matches the formal charge for every
tested species, and the correction reaches further than the new
selectors, because those properties are attached to the molecule and
stored by the database assembler.

Gaussian ``sp/opt/ts/irc/td/link/scan/modred`` is supported for project YAML,
native-input generation, safe preview, and parsing of user-supplied completed
results; this release does not claim Gaussian Agent execution. GPU4PySCF
``sp/opt/hess`` is a PySCF-engine configuration and preview surface, not a
release-qualified Agent execution path. PySCF CPU ``td`` is likewise
preview-only. ORCA ``neb`` may be planned and previewed, but requires
target-specific qualification before it is described as completed execution.
NCIPLOT and additional human CLI families without an Agent declaration remain
outside the version-3.1.4 Agent execution surface.

Product support never asserts that an engine is installed on the current host.
Every real operation must pass its normal environment probe and appear in the
human review before it can run.

Runtime orchestration is provider-neutral. This release contains registered
adapters for Alibaba Token Plan, DeepSeek, and OpenAI; an Anthropic profile
is accepted as configuration and refuses execution until its adapter is
registered. A user-selected profile supplies the provider, endpoint, model,
reasoning setting, and credential label; source code and documentation must
not impose a default model. Credentials resolve from the environment or the
managed key store and never live in agent.yaml or in Git.

## Authority and approval chain

Planning, YAML validation, CLI compilation, safe preview, and result analysis
do not grant engine authority. Real calculation follows this chain:

1. the Agent produces a project-backed DAG;
2. ChemSmart compiles and safely previews every executable node while retaining
   any scientifically necessary release-unsupported stage as explicit
   non-executable intent;
3. the terminal interface displays the complete plan, marks non-executable
   stages and their reasons, and displays molecular identity, electronic state,
   effective project settings, CLI operations, dependencies, environment, and
   resources for the executable partition;
4. a human enters ``/approve`` once, or chooses ``/deny`` or ``/revise``;
5. the displayed workflow is removed from the pending state before launch;
6. a provider-free executor runs only that reviewed executable partition; and
7. ChemSmart records engine and validation evidence; a typed analysis chain
   displayed and approved with the workflow then executes provider-free in
   the same run, recording extraction, thermochemistry, expression,
   validation-verdict, and claim receipts, while scientific interpretation
   and the recorded decision remain a subsequent explicit session act; a
   workflow approved without an analysis chain keeps the prior behavior, and
   a later explicit analysis request may always read completed results.

There is no permanent calculation grant, session-wide "always allow", command
prefix allow-list, or model-created approval. A revised molecule, state,
project, environment, resource allocation, or DAG is a new workflow and must be
reviewed again. A multi-node causal workflow needs one human action because the
complete graph is displayed together; a displayed non-executable stage remains
unapproved and unlaunched.

The terminal UI is a view and controller for this chain. It is not a second
permission engine. Internal receipts and content digests preserve provenance
and mutation evidence in the durable records; they are not hashes or
approval-file tokens that a human must retype, and the production TUI does
not display them.

## Scientific invariants

Before materialisation, establish the facts that determine meaning:

- molecular identity and the role of each geometry;
- coordinate units and atom order;
- charge, multiplicity, electronic state, and constraints;
- requested observable and physical conditions;
- method or program requirements fixed by the question; and
- whether the task requests planning, preview, analysis, or execution.

Ask rather than invent a consequential missing fact. Never infer identity or
state from a filename. Preserve artifact lineage across geometry handoff and
state changes. Keep signs, dimensions, units, standard states, temperature,
pressure or concentration, and thermochemical conventions explicit.

Normal process exit is not scientific validation. Distinguish, in order:

- proposed;
- planned;
- materialised;
- previewed;
- approved;
- executing;
- engine-complete;
- parsed;
- scientifically validated; and
- interpreted.

Only the deterministic host owns these states. Provider text is not execution
evidence, and hidden model reasoning is never scientific evidence.

## Product differentiation

ChemSmart does not compete by maximising autonomy or agent count. Its value is
the separation of flexible scientific reasoning from a reproducible,
multi-program execution authority:

- one public YAML-and-CLI layer instead of model-authored native inputs;
- molecular, electronic-state, artifact, and geometry-lineage preservation;
- preview and one explicit human decision over the displayed scientific and
  resource state;
- provider-independent execution semantics;
- native outputs plus typed, unit-aware analysis rather than transcript-only
  provenance; and
- explicit maturity claims for each program and operation.

Do not force one paper answer, molecule-specific branch, preferred DAG, tool
order, or reporting style. Algebraically equivalent transformations and
scientifically stronger program-native routes are acceptable when their
evidence chain is complete.

## Implementation discipline

- Treat live project loaders and Click commands as the public authority.
- Keep provider protocol code inside registered adapters.
- Use the smallest existing architectural layer that owns a defect.
- Do not create a parallel orchestration, scheduler, or grading system.
- Preserve unrelated working-tree changes; never reset, clean, or overwrite
  user work without explicit authority.
- Do not commit credentials, user configuration, engine binaries, generated
  inputs, outputs, scratch data, private transcripts, or one-off reports.
- Keep controller and program compute environments explicit in user or server
  YAML. Never replace an operator-selected executable implicitly.
- Validate a target host from its actual operating system, architecture,
  scheduler, program builds, and resource limits. No single cloud or server is
  the universal reference.

After a material change, run one focused mechanical check and then prefer a
decisive real scientific observation. Tests verify mechanics; they do not
grade computational-chemistry intelligence. Never claim an engine run from a
fake preview, fixture, parser test, or source inspection.

## Human scientific review

The human scientist owns interpretation and publication. Evaluate whether
identity, state, method, numerical transformations, units, conditions,
dependencies, and limitations are coherent. Accept creative valid routes.
Reject invented data, unperformed actions presented as completed, silent
changes to the scientific problem, and invalid chemistry or mathematics.

Report the route, strong scientific decisions, consequential limitations, the
general ChemSmart capability involved, and exactly what was planned,
previewed, executed, parsed, validated, or inferred.

## Documentation and repository hygiene

User documentation lives under `docs/source` and describes released public
behavior only. It must not contain development diaries, hidden evaluation
rubrics, private infrastructure, future implementation status, or internal
class inventories. `README.md` is a concise human entry point.

This charter and `.agents/skills/chemsmart-agent/SKILL.md` are the two
governance exceptions. Keep them aligned with the live product. The repository
source and CLI win if either instruction becomes stale.
