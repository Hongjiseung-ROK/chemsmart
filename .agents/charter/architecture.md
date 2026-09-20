# Charter topic: architecture

The driver is a step machine -- plan, decide, execute, outcome, settle --
and every phase boundary is a ledger entry, so a process may stop after
any step and a later process may resume from the ledger. That is what
lets an approved run be handed to a scheduler: the job script runs the
same provider-free executor inside the allocation and its own tail runs
``chemsmart agent wake``, which rebuilds the driver at the outcome phase.
No poller, no scheduler accounting, and no second decision are involved;
the same one-shot bundle continues in its own run directory.

What the host can do and what a request carries are two different
facts. The catalogue is the first: one provider-neutral entry per
capability, each carrying its name, the family a scientist would look
for it under, whether it is an act or reference text, whether it loads
eagerly or on demand, and the registry its text was derived from -- and
it is assembled from the live tool builders, so it cannot describe a
tool the host does not have. Exposure is the second, in three modes over
one code path: ``host_search`` (a small core plus what has been
discovered, through one core tool the host answers, which every provider
understands), ``native_tool_search`` (every definition on every request,
byte-identical every turn, everything outside the session's fixed
prefix marked for a provider that searches server-side -- discovery
never moves a definition into the prefix, because modifying the array
would invalidate the very cache deferral protects), and ``eager``
(everything, the control arm and the floor). The initial context is the
same size whether the catalogue holds fifty entries or four thousand.

A workflow is authored the same way. The model is the author of every
scientific choice, and it makes them one coherent act at a time: a
constructor per calculation stage and per analysis kind -- result
extraction, thermochemistry, quantity expression, scientific
validation, claim rendering, and the unsupported analysis a release
keeps as a finding. Each is a catalogue entry, found by searching, and
each is a projection of the one node-schema builder onto the fields
that kind owns, so a task needing thermochemistry never reads the
expression-node schema. Calls accumulate into one draft the host owns;
re-issuing a stage's id replaces that stage, and no earlier stage is
ever resubmitted. A draft runs no whole-workflow check, holds no
canonical object and grants nothing: it is not executable and not
reviewable because it exists.

``plan_scientific_workflow`` is the finaliser and the only door out of
a draft. It is the same handler it always was, fed by the host, so
unique ids, topological order, producer-is-a-dependency, selector
coverage, dimensional propagation, required outputs, the engine-call
budget, excursion ancestry and all three whole-plan digests come out of
the code that produces them today -- a workflow drafted stage by stage
and the same nodes sent in one payload are byte-identical, which resume
and the plan-reproduction rule depend on. A local refusal stores
nothing; a global refusal names the node and keeps the draft, so a
repair costs one stage. After a finalise the draft is closed and the
rules for a reviewed workflow apply unchanged,
``amend_scientific_workflow`` included.

The model writes every query; the host tokenizes and ranks it and
classifies nothing. A search offers its whole ranking and loads only
the head of it: what does not clear the relevance floor is named with a
one-line summary and is one exact-name call away. What the host does route on is typed: the kinds the
workspace scan found and a previous run's terminal states promote
entries before the first request, so the rendered prefix is stable for
the session, and the planned DAG's own job types, operations and
programs surface more (two programs in one DAG surface the
cross-program reference, because equal level strings are not equal
methods). Calling an entry by its exact name is itself a discovery act:
the host loads the definition, records it, and asks for the call again,
so arguments composed before the schema was readable are never run. A
name the catalogue does not hold is a typed refusal that names the
search tool. Loading an act loads its family's reference, which is how
an invariant governing a family of tools is never behind a search the
model may not run. Discovery is not permission: nothing about project
validation, the displayed review, the single human decision, the
execution envelope or any result verdict depends on it, and the
approved-execution surface is not built from the catalogue at all.

Every natural-language rule the host places in front of the model is a
registered capability with an id, a placement (stem, a guide, the goal
wake, or one tool's description), the tier that first needs it, and the
provenance that earned it; the system prompt, the wake context, and the
tool descriptions render from that registry. And every capability of
every kind -- program job types, tools, selectors, operations,
predicates, constants, skills, reference entries, rules -- climbs
one ladder,
declared, wired, advertised, tested, qualified, computed from the
registries that own each kind: wired from the host's handler table and
the readers, tested from the ``capability`` markers tests carry,
qualified from a curated release record of the live runs behind each
executable program job type and from the host's own store, which the
driver writes at every achieved settlement. ``chemsmart agent
capabilities`` renders the ladder; a cell the agent can run but cannot
judge, and a claim without a run behind it, say so out loud.
