# Charter topic: validity-rules

Every executed result is judged on one program-neutral rule beside its
program's own validator: the approved jobtype promises a count of
imaginary modes -- one for a transition-state search, none for a minimum
-- and the program's own printed frequencies deliver one under the
20 cm-1 convention thermochemistry uses for numerical noise. A mismatch
is a typed failure, ``failed_wrong_stationary_point``, for every program
whose frequencies the host reads; a run that printed none makes no
claim. The spin expectation value is read from the program's own table
and recorded as an observation beside the bound multiplicity, never as
a gate; a deviation of 0.2 or more from S(S+1) is an anomaly
observation carrying its number, ``spin.s2_deviation_ge_0.2``, named
for the measurement and not for an expectation, because a requested
broken-symmetry state is not a surprise. A saddle whose one imaginary
mode lies inside 50 cm-1 -- past the convention and still far from the
hundreds of wavenumbers a forming bond carries -- is an anomaly
observation carrying its number, ``stationary_point.imaginary_mode_lt_50``,
because a rule at a threshold certifies noise on the far side of it: a
live search relaxed to a van der Waals complex at -22.8 cm-1 and the
word was ``validated``. The observation stands beside the verdict and
the session, not the host, says what the mode is. That observation had been
empty on every ORCA and Gaussian result until this round -- the readers
expose the table as a property and the host called it as a method -- so
a charter sentence with no consumer is treated as an unverified claim
until something reads it. Per-atom spin populations, Mulliken and
Löwdin, are declared for ORCA ``sp``, ``opt``, ``ts`` and ``freq``:
ORCA prints them in the second column of the same table as the
charges, the reader had parsed and discarded that column for years,
and a session that asked where a radical cation's spin lives was
answered by nothing while the number sat in its output. They are read
by column position, checked against 2S to 0.05, and refused for a
closed-shell result rather than served as zeros. A converged SCF is a
stationary point in orbital-rotation space and not necessarily a minimum
of one, and where a run recorded a program's own stability analysis that
found a saddle there, ``scf.reference_unstable`` is an anomaly
observation carrying the rotation space the program searched --
"externally unstable" is RHF/RKS -> UHF/UKS for a restricted reference
and UHF/UKS -> GHF/GKS for an unrestricted one, and a boolean would
report one of two questions -- beside what stayed undetermined, what the
program could not answer, and whether the orbitals it ran on had
converged at all. It is never a verdict: a broken-symmetry or
deliberately constrained solution is sometimes what was asked for, and
the session says what the instability means. What it buys is that the
numbers standing on such a reference are named where a human reads one
word, through the delivery walk every anomaly already drives. Silence is
never stability -- a reader that answers nothing, an artifact older than
the record, a run nobody asked and an analysis that raised all arrive as
no diagnostics at all -- and the diagnostic reaches the host through one
reader function rather than a per-program thread, because the record it
reads had been written for a round and consumed by nothing. Capability is measured as
filled coverage cells rather than CLI verbs: the capability receipt
names, per program and jobtype, which typed axes -- electronic,
geometry, identity, spin, thermochemistry -- are readable or validated,
and which host validity rules apply, so a jobtype the agent can run but
cannot judge says ``unsupported`` out loud.

The mode count is not stationarity, and one organ still reads it as such.
``characterise_stationary_point`` checks a claimed order against the
printed modes only: given the PySCF Hessian of a UHF/3-21G methoxy saddle
on the B3LYP/def2-SVP surface (CUHK g5-methoxy, 2026-09-20), whose
gradient of 0.0485 Eh/Bohr the host had just recorded as
``stationary_point.gradient_above_optimizer_criterion``, it issued an order-1
characterisation with no anomaly cited, and the session called the
geometry "host-characterised as a first-order saddle" for a cycle before
it withdrew the barriers standing on it. The gap is stated, not closed:
closing it is a refusal on the gradient that reaches every program's
characterisation, which this round did not measure.
