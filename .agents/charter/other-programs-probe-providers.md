# Charter topic: other-programs-probe-providers

Gaussian ``sp/opt/ts/irc/td/link/scan/modred`` is supported for project YAML,
native-input generation, safe preview, and parsing of user-supplied completed
results; this release does not claim Gaussian Agent execution.

What a completed Gaussian result answers is decided by the job the log says
produced it, and its route line alone cannot say: ``opt=modredundant`` is
written both for a relaxed scan and for a constrained optimisation, and a
response calculation on a fixed geometry carries no other keyword. The
reader is therefore asked the question the log can answer -- the
ModRedundant section Gaussian echoes, whose scan rows end ``S <steps>
<size>`` -- and declares ``opt``, ``ts``, ``sp``, ``td``, ``modred``,
``scan`` and the two IRC branch words. Never a bare ``irc``: ChemSmart
writes a Gaussian IRC as two one-direction inputs, so no log answers to it
and no IRC producer edge is admitted, which is the mirror of ORCA's reason
rather than the same one. Never ``link`` either, because a link job's
route resolves to its linked target and the result reads as that job. A
relaxed scan's surface is assembled by the parser from the points the log
marks converged and each point's own driven coordinate, because Gaussian
prints the optimiser's trace and no profile table: 29 energies for a
13-point surface on the first scan this was read against. The structure an
optimisation, a saddle search, a constrained optimisation or an IRC branch
reached is declared as that role and carried by the geometry lift; a
single point reaches nothing beyond what it was handed and a scan ends on a
sampled point, and both refuse. Mulliken and Hirshfeld populations and IR
intensities are declared where Gaussian prints them.

Gaussian 16 C.02 has been driven through ChemSmart on a Slurm target
(CUHK Charles, jobs 2142374 and 2142393): fifteen small jobs covering
every declared job type, including a saddle search reaching the HCN/HNC
1,2-hydrogen shift at -1146.1 cm^-1 whose two IRC branches change
connectivity in one direction and not the other. Those are runs through
the human CLI. An Agent goal on the same target planned, compiled,
safely previewed, program-validated and preflighted a Gaussian
optimisation with zero findings and built its execution review, and then
made no execution decision, so no Gaussian engine call has been made
under the approval chain and no job type is claimed for Agent execution.

One boundary of the Gaussian route channel is worth stating because the
program does not state it. A route parameter is appended verbatim, so a
token the project section already carries is written twice, and Gaussian
answers a route naming ``freq`` twice by running no frequency step and
terminating normally. The result is a converged optimisation with no
spectrum rather than a failure: the host reports the absence, the
stationary-point rule has nothing to classify, and no wrong number is
delivered -- but the Hessian the run was asked for is gone without a word
from either program.

GPU4PySCF
``sp/opt/hess`` is a PySCF-engine configuration and preview surface, not a
release-qualified Agent execution path. ORCA ``neb`` may be planned and previewed, but requires
target-specific qualification before it is described as completed execution.
NCIPLOT and additional human CLI families without an Agent declaration remain
outside the version-3.1.4 Agent execution surface.

Product support never asserts that an engine is installed on the current host.
Every real operation must pass its normal environment probe and appear in the
human review before it can run.

Where the active server profile names an ORCA executable, preflight also
runs ORCA's own input check on the materialised input that the safe
preview retained by digest: a bounded probe launch on the controller,
stopped the moment ORCA's ``INPUT FILE`` banner appears or a 20 s cap is
reached, never inside a scheduler allocation, minting a typed receipt --
passed, aborted, or not run, with ORCA's own lines -- that rides an
``input_check_probed`` event marked uncharged, joins the node's
observations on the review **and the compile reply the model reads**,
and reaches the wake with ORCA's own lines rather than only a count. It
is never an engine call, because engine calls derive from execution
receipts alone. Two live cycles had died at that check under green
previews, one per rule ORCA states in its first tenth of a second.

What the probe refuses is exactly one thing: spending an engine call on
bytes the program has already rejected. It never refuses on scientific
grounds -- a green preview is ChemSmart's compile, the probe is ORCA's
check, and which of the legal repairs to make is a method decision the
session owns. The sentence this replaces said the probe never refuses at
all, because the decision stays the human's; that was written for the
case where a human reads the review, and it was silently generalised to
a goal's standing approval, where no human is present at that moment. So
the probe's word had no consumer in the authority chain, and eight
engine calls across two windows went to inputs whose abort the host had
already recorded, for free, in a tenth of a second. A node is therefore
not launched while the last check on its exact input digest aborted, and
the refusal quotes the program's lines. The override is to re-probe:
repair the field the program named and compile the node again, which
mints a new check on the new bytes -- so an abort against an executable
or environment that has since changed is superseded rather than
permanent. The probe's own receipt and its uncharged event are held by
``tests/agent/test_an_input_check_probe_is_orcas_word_and_costs_nothing.py``;
the launch refusal is held by
``tests/agent/test_a_tuple_field_is_never_read_as_a_mapping.py``, which
exists because the refusal first shipped with **no** test at all and
read one node's observations by calling a mapping's method on a tuple --
so the first goal to reach a launch after it died with an
``AttributeError`` inside the check and settled nothing.

Runtime orchestration is provider-neutral. This release contains registered
adapters for Alibaba Token Plan, DeepSeek, and OpenAI; an Anthropic profile
is accepted as configuration and refuses execution until its adapter is
registered. A user-selected profile supplies the provider, endpoint, model,
reasoning setting, and credential label; source code and documentation must
not impose a default model. Credentials resolve from the environment or the
managed key store and never live in agent.yaml or in Git. A profile may state
``record_reasoning: true`` for a campaign that studies the model: the host
then keeps each turn's provider-native reasoning in the private run directory
at mode 0600, the event stream records the artifact by digest and never by
content, and the turn receipt says it was kept. Hidden reasoning remains
never scientific evidence and never reaches the public transcript.
