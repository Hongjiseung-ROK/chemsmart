# Charter topic: architecture

The driver is a step machine -- plan, decide, execute, outcome, settle --
and every phase boundary is a ledger entry, so a process may stop after
any step and a later process may resume from the ledger. That is what
lets an approved run be handed to a scheduler: the job script runs the
same provider-free executor inside the allocation and its own tail runs
``chemsmart agent wake``, which rebuilds the driver at the outcome phase.
No poller, no scheduler accounting, and no second decision are involved;
the same one-shot bundle continues in its own run directory.

The surface the model reads is a tree, not a list. A stem of sixteen
tools, the operations that belong to no family, and the universal rules
is what every session reads; a guide is a family unit -- structure,
scan, constants, cbs, ensemble, spectroscopy, database, crossprogram,
recovery, saddle -- of extra tools, extra operations, a few hundred
words of guidance, and the rules placed on it. The host opens a guide on
four signals, each recorded with the new tool-schema digest: the task
text, the workspace, the planned DAG's own jobtypes, operations and
programs (a DAG naming two programs opens ``crossprogram``), and the
previous run's terminal states under a goal; the model may open any
guide itself with ``open_guide``. The exposure record follows the
surface each request is actually built from, so a guide opened
mid-session is recorded with the digest it produced. Opening a guide
changes what the model can express and how much it reads, never what
the host approves.

Every natural-language rule the host places in front of the model is a
registered capability with an id, a placement (stem, a guide, the goal
wake, or one tool's description), the tier that first needs it, and the
provenance that earned it; the system prompt, the wake context, and the
tool descriptions render from that registry. And every capability of
every kind -- program job types, tools, selectors, operations,
predicates, constants, skills, guides, rules -- climbs one ladder,
declared, wired, advertised, tested, qualified, computed from the
registries that own each kind: wired from the host's handler table and
the readers, tested from the ``capability`` markers tests carry,
qualified from a curated release record of the live runs behind each
executable program job type and from the host's own store, which the
driver writes at every achieved settlement. ``chemsmart agent
capabilities`` renders the ladder; a cell the agent can run but cannot
judge, and a claim without a run behind it, say so out loud.
