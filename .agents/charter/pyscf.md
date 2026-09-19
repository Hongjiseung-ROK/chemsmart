# Charter topic: pyscf

Every program answers the shared selector vocabulary through one
extraction plane. A structured PySCF result is a registered reader beside
the log-parsing programs, with job-type declarations for ``sp``, ``opt``
and ``hess``, so the capability query reports what it carries and the
same declaration gate refuses a selector whose meaning was never audited
for that job type. It had been a second plane reached by name — its own
selector vocabulary, its own unit table, and no gate — which is how a
plan naming a selector this program never implemented could pass
planning and be refused only after every engine had finished. Merging it
closes a recorded cross-program disagreement as a unit rather than a
quantity: PySCF stores excitation energies in hartree where the
log-parsing programs print electronvolts, and a reader states its own
native unit while the arithmetic stays canonical. The HDF5 path keeps
what no log format has, an admission guard binding the exact bytes to a
sibling run receipt and its whole ancestry of digests, and each numeric
dataset is read only under the unit it declares; a stored unit that
differs from the one a selector reads it as is a divergence to state,
not an absence to report. PySCF ``td`` declares the SCF set beside the
excitation set, because the response stage is executable under result
contract v5 (below), and the provenance axis says whose each value is.

A PySCF result is one structure, and the host says which. The driver
re-converges the SCF on the final geometry, from the optimiser's own
last density, before any energy, orbital, dipole, population, spin
expectation or frequency is read, so every quantity belongs to
``results/positions``; the geometry the run was handed sits beside it
in ``spec/positions``. The reader declares the states accordingly --
``supplied_positions`` as supplied, ``positions`` and every property as
reached, ``reached_positions`` and ``converged`` for ``opt`` alone --
and the structural-state oracle that holds for ORCA's OptTS holds for
PySCF's archived optimisations, with a fourth relation a fixed-geometry
stage makes checkable: supplied and final coincide, and the runner's
own invariant is read back through the selector plane. A PySCF result
opens whether or not its run succeeded, on the receipt binding alone;
every quantity and every free energy still demands the green receipt.
A failed optimisation's last evaluated geometry -- which PySCF returns
whether or not it converged, 0.066 Å from the input on an archived
one-step run -- is therefore what ``bind_reached_geometry`` carries.
The host sensors are fed through each program's reader by one step,
so the stationary-point rule, the spin observation and the basin walk
reach PySCF as they reach ORCA (the basin sensor had been fed by the
ORCA branch alone), and a PySCF Hessian on a saddle -- an exactly
planar ammonia optimised onto its D3h saddle, one imaginary mode at
−830 cm⁻¹ -- ends ``failed_wrong_stationary_point`` with the anomaly
recorded. The per-plan stationary-point policy that once deferred a
PySCF Hessian to a downstream classification no organ performed is
retired; its digest fields stay, always empty, so every approval on
disk keeps its digest. A Hessian's stationarity is an observation with
standing: PySCF's harmonic analysis projects rotations out, and an
archived water Hessian at a stretched geometry prints three real
frequencies at a gradient forty times the optimiser's criterion, so the
driver records the gradient at the Hessian geometry and the host raises
``stationary_point.gradient_above_optimizer_criterion`` above
geomeTRIC's own ``convergence_gmax`` (the registered policy
``hess_stationarity_gradient``), never a refusal. The result contract
(v4) also records per-atom Mulliken spin populations for open shells,
the isotope-averaged mass table behind the frequencies, the symmetry
tolerance behind the point group -- a hundred times tighter than an
optimiser's displacement criteria, so a molecule relaxed onto a
symmetric minimum can lose its symmetry number silently, which is why
the number and its source ride the thermochemistry receipt -- and the
optimiser's convergence criteria. ``functional`` on a PySCF result is
the name the project asked for: ``b3lyp`` and ``b3lypg`` are one libxc
functional in this build and ``b3lyp5`` the VWN5 form, so a matching
string across programs is necessary and never sufficient. Two Hessians
PySCF 2.14 cannot compute -- any ROHF reference, and an open-shell
reference under a non-local-correlation functional -- are refused at
preflight. Every PySCF declaration is exercised on archived real
artifacts with PySCF's own reference numbers beside them, and the host
RRHO engine agrees with PySCF's thermochemistry on the zero-point energy
to 3e-11 Eh on the same Hessian.

The PySCF surface beyond the ground-state SCF is three capabilities
under result contract v5, each with something that goes red. ``td``
runs: TDA or full TDDFT on a closed-shell reference in the singlet or
the triplet manifold, or on an open-shell reference in the one
``unrestricted`` manifold, gas phase or under a PCM-family or SMD
reference. Roots are ascending ordinals within the manifold at the
artifact's own geometry -- an index, never a state identity -- and the
artifact records per root its convergence, its oscillator strength and
its transition dipole, and per stage how many roots were requested, how
many PySCF's positive-eigenvalue filter (1e-3 Eh) kept, and the
iteration cap applied; ``nstates`` may exceed what comes back and the
ordinals shift with it, which is why the count is written. A solvated
spectrum records the static dielectric it applied and the response
dielectric PySCF actually used, which is 1.78 for every solvent in this
build; a toluene fixture shows the divergence instead of hiding it
behind water. The ``opt`` stage carrying ``excited_state_root``
optimises on root *k* of that manifold with the analytic TDA/TDDFT
gradient, gas phase only (the solvated gradient is not implemented
upstream), reading the per-root flags directly because PySCF 2.14's
scanner property is off by one and raises when the followed root is the
last requested; it re-converges the SCF and re-evaluates the spectrum at
the reached geometry so every quantity belongs to one structure, and
records the followed root's gap to the ground state and to its neighbour
there. A followed root that PySCF's filter drops ends the node typed
rather than switching roots. Those gaps and counts are neutral sensor
facts in the run outcome with no threshold behind them: a 0.1 eV
degeneracy policy was in the plan and withdrawn under independent
review, because nobody here derived the number; a water root that ended
degenerate with its neighbour to 3e-6 eV is the case the number exists
for, and the session, not the host, says what it means. No Hessian
existed for that minimum when this stage shipped, so the delivered
geometry was worded uncharacterised; the difference Hessian below is its
Hessian now. ``mp2``, ``ccsd`` and ``ccsd(t)`` are ``ab_initio``
values on an HF reference, as ORCA's settings already spell them:
energies for all three, analytic gradients for MP2 and CCSD (the CCSD(T)
gradient exists upstream and is refused as unaudited, never called
absent), no Hessian, and no density fitting or solvent this round.
``reference_energy`` and ``correlation_energy`` are the program's own
components, ``correlation_energy`` meaning the final method's whole
correlation with the triples included, as the ORCA reader already means
it, with ``ccsd_correlation_energy`` and ``triples_correction`` beside.
PySCF correlates every electron unless ``frozen_core`` says otherwise,
where ORCA and Gaussian freeze the core by default; the choice is the
scientist's, ``auto`` names PySCF's own chemical-core rule, the artifact
records the count applied, the level line displays it, and the
crossprogram guide's first placed rule says so: on water, ORCA's default
MP2 correlation reproduces PySCF's ``frozen_core: 1`` to 5e-8 Eh and
differs from the all-electron default by 2.4e-3 Eh.

Two words join the terminal vocabulary,
``failed_nonconverged_excited_state`` and
``failed_nonconverged_correlation``, derived from the artifact's own
stage flags, because an unconverged Davidson root or amplitude set sits
on an SCF that did converge and ``failed_nonconverged_scf`` would be
false for a real run; each is repairable and its menu names the public
control that answers it, ``td_max_cycle`` and ``cc_max_cycle``, project
keys the artifact records. The unconverged fixtures were generated
through the CLI with those controls, so the route the menu names is a
route that exists.

A structural state identifies a geometry, not a density. An excited-root
or correlated artifact carries the reference's dipole, populations,
orbital energies and spin expectation beside a total energy that is not
the reference's, and every hash, unit and geometry check passes while a
session reads "the S1 dipole" off a ground-state number. So a second
declaration axis stands beside the structural state: each reader
declares, per selector, whether a value belongs to the ``reference``, an
``excited_root``, the ``correlated`` method, or the surface the job
computed on, resolved per artifact; PySCF and ORCA's ``td`` both declare
it, ``inspect_run`` lists the resolved word beside the structural state
and the level the artifact's own record names (method, basis, the
frozen-core count applied, the response and the followed root), and the
extraction receipt carries it inside its digest -- present only where a
reader declares the axis, so every receipt minted before it verifies
unchanged. ``energy`` is the surface the job computed on, ORCA's "FINAL
SINGLE POINT ENERGY" semantics: the reference for a spectrum, the
followed root's total for an excited-root optimisation, the correlated
total otherwise; ``scf_energy`` names the reference.

An excited minimum is a structure producer through the same handoff
every optimisation uses, and the archived chain shows it over real
bytes: the reached geometry of the formaldehyde S1 optimisation, written
by the host's own reached-geometry route, was the input of a response
run whose first root equals the gap the producer recorded at its end,
3.052 eV -- the emission energy read where the excited surface reached,
on a reference energy the two runs agree on to 3e-12 Eh. Every
declaration is exercised on eighteen new real fixtures with PySCF's own
recomputation beside them and on two ORCA differentials at matched
conventions, and the applied-spec vocabulary is versioned per contract,
because extending one tuple would have changed the provenance digest of
every archived v4 artifact and turned nine real fixtures red. What is
not claimed: CCSD(T) optimisation, EOM-CCSD, CASSCF, PySCF scans,
transition states and IRC, DF-MP2 gradients, solvated correlated
methods, and the triplet and unrestricted manifolds, solvated ``td``
and the two iteration controls, which stay fixture-qualified until a
sealed case exercises them.

Result contract v6 adds what none of those artifacts carried: the
electronic **surface** a result's geometry and total energy belong to.
Every field in it is a value the host applied rather than one a project
asked for, so ``b3lyp`` and ``b3lypg`` -- one functional in this build --
record the same surface, and a frozen-core count is the count the
correlated stage actually froze. Where a reader cannot determine a field
it writes ``unknown``, and two surfaces agree only when every field
agrees and neither reader wrote it: a frozen core nobody recorded on
either side is two unknowns, not a match. The comparison therefore has
three answers rather than two, and the third is never read as the first.
Two organs ask it. A method family this release has never audited
resolves to the provenance word ``unknown`` instead of falling through to
``reference``, which was a true sentence about the wrong density. And a
validated Hessian characterises the stationary point of the geometry it
consumed only when the two share a surface: a ground-state Hessian at an
excited minimum, or a cheap one at a correlated minimum, is a real number
about a real structure that says nothing about the surface the
optimisation walked on, and the delivery now names that pair instead of
crediting it. Where the two cannot be compared the Hessian still
characterises, as before, and the reader is told the comparison was not
available.

PySCF differentiates an HF or DFT energy twice analytically and does not
differentiate a TDA root, an MP2 or a CCSD energy twice at all, so a
``hess`` on an excited root differences that root's analytic gradient,
which the driver already has: 6N central displacements at 0.005
Angstrom, with the step in both units, the gradient count, the
per-displacement convergence
and the class of the object that produced the gradients recorded beside
the frequencies. ``hessian_derivative`` and ``fd_step_angstrom`` are
project keys and CLI options, and an unset derivative resolves to the
analytic one where PySCF has it and to the difference on an excited
root, where ``analytic`` is refused: it would be ``mf.Hessian()``, the
reference's curvature under a surface record naming the root. Stages run in a declared order so a
surface is built before anything differentiates it, and the gradient a
Hessian stage records is the gradient of the surface it differentiated --
at the relaxed planar S1 point of formaldehyde the mean field's own
gradient is 0.133 Eh/Bohr where S1's is 9.1e-06, and the first would call
a stationary point of one surface far from stationary using a number
belonging to another. A differenced Hessian's raw asymmetry is the
truncation error of the step rather than the quadrature noise the
analytic limit was calibrated on -- 4.4e-05 Eh/Bohr^2 on water against a
limit of 1.1e-05, with frequencies agreeing to 0.40 cm-1 -- so for a
numerical Hessian it is recorded and never graded, because nobody here
derived a limit for it. The driver would difference an MP2 or CCSD
gradient the same way, and this charter said from 44499f2a on that it does;
the settings validator never stopped refusing a correlated ``hess``, so
that path has run on no fixture and in no goal and is not claimed. Its
refusal named "an HF or DFT hess node" as the route, which is exactly
the pairing the surface comparison above refuses to credit; it now says
that such a Hessian describes a different surface.

None of this is described as completed Agent execution. It is exercised
on six new real fixtures with PySCF's own recomputation beside them and
through direct runs of the human CLI, and no sealed goal has run any of
it. What those runs establish is that the host can now ask a question it
could not ask before: the relaxed planar stationary point of
formaldehyde's S1 surface carries one imaginary mode at -503.9 cm-1 at a
maximum S1 gradient of 9.1e-06 Eh/Bohr, so it is a genuine stationary
point of that surface and not its minimum, and the program-neutral order
rule types it. An excited-state stationary point delivered as "the
geometry" with no way to say which kind of stationary point it is was
exactly what the previous round's acetone goal delivered.

Four sealed goals ran this surface through the ordinary plan, preview,
one displayed decision and provider-free execution. HCN/HNC: two MP2
optimisations feeding four CCSD(T)/cc-pVTZ single points through
validated handoffs, the isomerisation energy 14.95 kcal/mol
core-correlated and 14.63 frozen, the core effect stated, frozen core
in the level line and ``correlated`` on every extraction. Formic acid: a
CCSD optimisation feeding ORCA and PySCF MP2 single points, the first
PySCF-to-ORCA geometry handoff, the two programs 1.7e-6 Eh apart at
matched frozen core and 7.6e-3 Eh apart between their defaults, the
convention named by the session. Acrolein: a ``td`` validated on the
geometry its optimisation reached, three roots with their strengths,
the bright root's ordinal tied to the geometry it holds at. Acetone: the
excited-root optimisation from an exactly symmetric start stopping on a
planar stationary point whose gaps the outcome reported as facts, and
the woken session breaking symmetry by its own declared rule to reach
the pyramidal S1 minimum 3.5 kcal/mol lower -- and claiming the planar
numbers it had already made, so the goal settled achieved with the
better result computed and unclaimed. Three host defects were found by
those goals and repaired where they were made: an approval id
normalised by one organ and not another, which had also let a refusal
end a goal unsettled; the expected input geometry handed to the
validator for two of its three fixed-geometry job types; and a
same-structure sensor that joined a consumer to its producer by digest,
which a handoff file never matches, hidden until this round by its own
three-heavy-atom floor.

Three losses the first sealed PySCF goals paid for are repaired where
they were made. The bootstrap conformance, which fake-previews every
declared program on the workspace's own first geometry, bound charge 0
and multiplicity 1 to whatever that geometry was, so a workspace whose
supplied molecule was the allyl radical made every PySCF job type
reference-only before any plan existed -- PySCF's preflight refuses the
impossible singlet where ORCA's and Gaussian's previews do not -- and a
correctly planned single point returned to the human at zero engine
calls; the probe now binds, neutral, the multiplicity the input's own
electron count permits. A number read from an optimisation whose
reached geometry a validated Hessian consumed through the handoff edge
was worded "uncharacterised (no frequencies printed)" in the settlement
while that Hessian validated beside it -- true per result, false per
goal -- and is now joined in the run stream and in the workspace
record, so PySCF's and xTB's two nodes get the word ORCA's one node
gets. And the qualification rows the capability ladder reads were
written from the settling cycle alone, so a goal that ran in cycle one
and settled in an analysis-only cycle two qualified nothing; they now
come from every cycle the goal recorded, and from both settlements,
because the first repair reached only the executed run's. Three more
sentences from the re-issue. Conformance coverage is per stage: the CPU
PySCF surface declares ``td``, whose preview then refused any reference
but a closed-shell singlet (it now previews an open-shell reference in
the unrestricted manifold), and one uncoverable stage had failed
the whole engine, so a radical workspace stayed reference-only after
the probe's own state was repaired; a stage that cannot preview this
molecule is now the gap the receipt reports, never a failure of the
stages that did. And a number claimed in a later cycle's session on a
result an earlier run typed failed keeps its word at settlement -- that
it stands on a node that did not meet its promise, or on one the
session had the host characterise -- because the workspace record
holds those results and both settle-time deliveries read them; the
planar phosphine goal had claimed six characterised numbers on its
inversion saddle and the settlement named only the anomalies.

A converged SCF is not necessarily a minimum in orbital-rotation space,
and result contract v7 lets a run say so. ``scf_stability`` asks PySCF's
own analysis about the reference the run converged, after the final SCF,
and records the answer as an observation that moves no stage, no
convergence flag, no termination word and no validation state. The record
names the question rather than only the answer, because ``external`` is
not one question: PySCF searches RHF/RKS -> UHF/UKS for a restricted
reference and UHF/UKS -> GHF/GKS for an unrestricted one, and it solves
the real -> complex question inside both, logs it, and returns only the
other flag -- on triplet O2 at UKS those two answers differ, so the
returned flag is recorded with its space and real -> complex is named as
undetermined. An ROHF reference has no external answer at all, and because
one combined call runs the internal Davidson and then raises, the two
questions are asked in two calls so the answer already computed survives.
Absence is never stability: a run nobody asked records ``not_requested``,
an earlier contract carries no field, and a ``--fake`` preview that asked
carries no record, and none of them is read as a stable reference.
Nothing follows an instability -- the singlet-O2 solution a follow reaches
is 13.2 kcal/mol lower and itself unstable both ways, and which solution
is wanted is the scientist's question. Seven real fixtures generated on a
cluster through the ordinary CLI exercise it.

That record is now read. A reader declares what its own result says about
the reference every number above it stands on, one function on the reader
plane beside the surface identity, and the host's program-neutral sensor
step reads it through that function the way it reads the surface, the
frequencies and the spin expectation: PySCF answers from
``status/properties/scf_stability`` and Gaussian from its own stability
verdict, every other reader answers nothing, and nothing reads nothing as
stability. Where a determined answer came back unstable the host raises
``scf.reference_unstable``, an anomaly observation carrying the rotation
space, what stayed undetermined, what the program could not answer, and
whether the orbitals it ran on had converged. Nothing about the verdict
moves: no finding, no validation state, no terminal word, because the
solution may be the one that was wanted. What the anomaly buys is the
delivery walk every anomaly already drives -- a number descending from
that node is named in the settlement as delivered from the flagged
result, and the goal settles ``achieved_with_observations`` rather than
plain ``achieved``. Two further fixtures, run on the cluster through the
ordinary CLI for this round, carry the cases the seven do not: a Hessian
whose receipt is ``validated`` with no finding delivering one real mode
at 1641.76 cm-1 on an ``RHF/RKS -> UHF/UKS`` unstable singlet-O2
reference, which is the whole case for a sensor; and the same molecule at
``scf_maxiter: 2``, whose analysis answered *both* questions unstable at
``scf_converged: false``, which is why the observation carries that flag
-- on orbitals that are not stationary at all the word says far less.
Gaussian's own verdict is a history, and only its last entry is the state
of the reference the run delivered: the archived ``dna_link_sp`` log finds
an internal instability and then reports stability, so reading any earlier
entry would flag a reference Gaussian had already repaired. Gaussian names
no rotation space and the record invents none. No sealed goal has run this
surface, so the sensor is described as a host observation over real
archived results and not as something a goal has yet acted on.

What a session is told about this surface is now held to the host. The
leaf had said "No Hessian exists for an excited or a correlated surface"
from 44499f2a on, while the project loader admitted a Hessian on an
excited root; the project tool's own rule still called ``td``
preview-only; and ``hessian_derivative`` and ``fd_step_angstrom`` were
applied by the loader and advertised nowhere, so the execution review
never displayed them. Probing that last gap found a wrong spectrum under
green receipts: ``hessian_derivative: analytic`` on an excited root ran
``mf.Hessian()``, and on CUHK (job 2140014) the planar formaldehyde S1
point validated with no finding, the ground state's six real modes
beside S1's own 9.1e-06 Eh/Bohr gradient, under a surface record naming
root 1 -- where the difference Hessian of that root has a mode at
-503.9 cm-1. The analytic derivative on a root is refused, an unknown
derivative word and a non-positive step are refused, both keys are
advertised and displayed, and the correlated refusal no longer names a
DFT Hessian as its route. A rule that states a settings boundary carries
the sections that make it true, and a test asks each of the model's own
project path, so the next such sentence goes red when the host moves.
The leaf gains the reference-stability sentence: what ``scf_stability``
asks, where a lower solution is chemically plausible, and what
``scf.reference_unstable`` means when it arrives. A four-goal sealed
campaign on CUHK (jobs 2140018-2140021: formaldehyde and trans-glyoxal
S1 structures, the ethylene torsion barrier, ozone at MP2) was issued
on this tree and its results were not read before the cluster gate
closed, so no Agent behaviour is claimed from it here.
