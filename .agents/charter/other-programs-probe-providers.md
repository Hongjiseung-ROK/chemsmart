# Charter topic: other-programs-probe-providers

Gaussian ``sp/opt/ts/irc/td/link/scan/modred`` is supported for project YAML,
native-input generation, safe preview, and parsing of user-supplied completed
results; this release does not claim Gaussian Agent execution. GPU4PySCF
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
