# Charter topic: constants-and-pka

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
