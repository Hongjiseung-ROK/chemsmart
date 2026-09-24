# Charter topic: pyscf

> Evidence, not instruction: what this surface was qualified by and what it found, under the
> conditions stated. The live tree and ``chemsmart agent capabilities`` outrank it; doctrine is
> ``AGENTS.md``, ``CONDUCT.md`` and ``.agents/rsl/``.

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
reference's curvature under a surface record naming the root. Stages
run in a declared order so a surface is built before anything
differentiates it, and the gradient a
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
gets. A Hessian on a geometry a later cycle lifted with
``bind_reached_geometry`` -- the only route to a Hessian after the fact,
since a woken session holds no earlier workflow -- was not joined at all:
the lift writes a new file, and the receipt naming its source lived only
in the planning stream. The workspace record now carries that lineage
and each result's surface, and credits the lift only when the two
surfaces agree; unlike the in-run edge, a comparison that cannot be made
is not credited, because this join is new and has no earlier behaviour
to keep. And the qualification rows the capability ladder reads were
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
other flag -- on triplet O2 at UKS those two answers differ. Since R10
Q13 (0a77574f, 2d927932) the record keeps what PySCF's own log said: the
real -> complex verdict as a question of its own, and every question's
lowest eigenvalues in Eh. Each is normalised as its own matrix is -- the
internal root is four times Gaussian's lowest singlet root on water -- so
they compare within one question, never across questions. The sentence
this replaces named real -> complex as undetermined while the log had
printed it (singlet O2 at RKS: -0.0383 Eh, CUHK 2152079). An ROHF reference has no external answer at all, and because
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
entry would flag a reference Gaussian had already repaired. A stable
Gaussian verdict names no rotation space and the record invents none; an
unstable one names its own ("RHF -> UHF", with the eigenvalue it is drawn
from, R10 Q13 a54aaadf -- the reader had read that sentence as no verdict
at all, CUHK 2152098). No sealed goal has run this
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
``scf.reference_unstable`` means when it arrives.

A sealed four-goal campaign ran that tree on CUHK (jobs 2140018-2140021,
default provider profile, approval delegated by the owner and recorded
as ``opus-researcher-owner-delegated``, never a human decision); no task
named a Hessian, a root, stability or a saddle except ozone's, whose
question is its frequencies. Four goals are four observations, with no
arm that lacked the sentences. Formaldehyde's session seeded its S1
optimisation off-plane, planned the root's Hessian with the root's
settings and ``finite_difference``, and ran it on the reached geometry:
six real modes (693-3114 cm-1), a pyramidal minimum with C=O 1.304
Angstrom, an out-of-plane angle of 35.5 degrees (the session reported
the H-C-O-H dihedral, 140.3) and an adiabatic gap of 3.711 eV at
TDDFT-B3LYP/6-31G*, each matching the result files; the settlement
still called all ten numbers uncharacterised, the lineage defect above.
The ethylene session asked ``scf_stability`` on the twisted structure,
read the RKS -> UKS answer as diradical character, and delivered 97.32
kcal/mol as the rigid restricted barrier under an explicit approximates
relation. Its split of the gap to about 65 (20 kcal/mol restriction, 8
geometry) is not what the CLI references (jobs 2140014 and 2140017,
def2-SVP) show: at one twisted geometry the RKS energy lies 30.4
kcal/mol above the UKS triplet. The ozone session asked stability on
the RHF reference beneath MP2, probed the MP2 ``hess`` through the
project path three times, quoted the refusal, and put no DFT frequency
forward as MP2 (MP2/aug-cc-pVTZ: 1.2838 Angstrom, 116.67 degrees); the
refusal returned to the human because the verifier asked the job
type's selector before the blocked node carrying the observable, which
is repaired in the settlement topic. Trans-glyoxal
planned the root's Hessian twice and ran nothing: its first plan was
not approvable while ``select_execution_wave`` answered that the wave
would be submitted, and the re-woken cycle's approvable plan was
returned for never having read a previous run that did not exist. No
session asked stability of a closed-shell ground state except
ethylene's planar optimisation, which shared the twisted structure's
project.

Result contract v8 adds ``irc``: one branch of the intrinsic reaction
coordinate from the geometry a node is handed, on an HF or DFT surface on
the CPU engine. PySCF's own ``geometric_solver.kernel(..., irc=True)`` does
not reach the first step under PySCF 2.14 and geomeTRIC 1.1.1 --
``run_optimizer`` reads ``M.molecules`` for every IRC and PySCF's engine
builds a molecule whose topology nobody built -- and it would return only a
flag and the last geometry evaluated. So the driver calls geomeTRIC with
PySCF's engine itself and records what the walk was. It first takes the
analytic Hessian of the walked surface at the supplied geometry, so the
start is shown to be a saddle of that surface and not of whichever surface
located it: the artifact carries that spectrum and the gradient there, and
the host's order rule, applied to the start through ``START_POINT_PROMISES``,
types a start with no imaginary mode or several
``failed_wrong_stationary_point`` (geomeTRIC refuses to walk from it, and the
refusal is recorded beside the start's spectrum and the SCF there rather than
raised past them). A start gradient above geomeTRIC's criterion is the
existing gradient anomaly, marked ``geometry: supplied``. The branch word is a
sign, not a species: geomeTRIC's ``forward`` steps against the eigenvector it
holds, and an eigenvector's sign is the eigensolver's choice, so the host fixes
the transition vector's sign (the first component within 1e-3 of the largest
is positive), ``forward`` is the branch whose first step projects positively
on it, and the validator measures that projection again from the recorded
frames. Two nodes on one saddle walk opposite branches; which minimum each
reached is read from its path. Every accepted frame is kept with its energy,
gradient and mass-weighted arc length, rigid motion removed, on success and on
running out of steps alike; every property belongs to where the branch ended,
where the SCF restarts from the density the walk last evaluated; and the
endpoint hands on through the optimised-geometry edge, admitted for a path
stage only where its reader declares a reached structure, which ORCA's IRC
log does not. An endpoint is where the walk met the optimiser's criteria,
never a characterised minimum: a Hessian on it says which.

What the validator states and does not grade: each recorded step against the
mean unit negative mass-weighted gradient at its two ends. geomeTRIC finds the
next point from a quadratic model of the gradient, and on formaldehyde's 1,2-H
shift at HF/6-31G* the median cosine is 0.999 while single mid-path steps fall
to 0.60 and 0.18 where the valley turns, and to -0.15 among the last tiny
steps at the minimum: the walk reaches its basin, and in those steps the
recorded path is not the surface's steepest descent. No threshold was earned,
so none is applied.

The direct CLI evidence (CUHK Slurm 2140566, 2140568) walked two surfaces from
ORCA OptTS saddles. H2CO / trans-HCOH at HF/6-31G*: ORCA's saddle carries one
imaginary mode at -2700.0 cm-1 on PySCF's surface with a start gradient of
2.7e-5 Eh/Bohr; the branches reach trans-HCOH and formaldehyde, whose PySCF
Hessians are all real, and ORCA's own IRC ends at the same two minima to 0.006
A in every distance, printing the saddle's energy as its "FINAL SINGLE POINT
ENERGY". HCN / HNC at B3LYP/def2-SVP from ORCA's ``B3LYP/G`` saddle (-1122.72
cm-1; PySCF -1123.0) reach HNC and HCN, both linear minima; from the saddle
ORCA located under its default ``B3LYP`` (VWN5), the start gradient on PySCF's
VWN3 surface is 4.4e-4 Eh/Bohr, sixteen times the matched one and just inside
the criterion, and the branch reaches the same HNC. A branch cut at three
steps keeps five frames and ends ``failed_nonconverged_geometry``; a branch
started at formaldehyde ends ``failed_wrong_stationary_point`` with its
all-real start spectrum. ORCA's own IRC on the ``B3LYP/G`` saddle ends
within 0.0008 A of PySCF's HCN and HNC and falls by the same energies to
0.025 kcal/mol, the two programs' totals sitting 5e-5 to 8e-5 Eh apart;
and PySCF's own account of every archived path, without geomeTRIC
(``reference_irc.py``), reproduces each stored energy to 1e-9 Eh and
gradient to 4e-6 Eh/Bohr and finds the recorded transition vector to be
the stored Hessian's lowest mode.

Five sealed goals ran the IRC tree on CUHK (jobs 2140676, 2140679-2140682;
frozen tree f1bd9361, default provider profile, a delegated approval), each
asked as a chemist would. Vinyl alcohol / acetaldehyde from a supplied
B3LYP saddle: two branches, each endpoint named from its connectivity,
barriers 57.34 and 68.51 kcal/mol against the direct-CLI 57.3 and 68.5;
settled ``achieved_with_observations``, the observation being the
session's own expectation that the more stable tautomer sits under the
smaller barrier, which it then corrected. HONO: ORCA optimised both
conformers and located the saddle from a 90-degree seed; PySCF's branches
from that default-``B3LYP`` (VWN5) saddle start at 3.6e-4 Eh/Bohr, inside
the criterion, and end at dihedrals 0.008 and -179.87 degrees; barriers
14.51 and 14.08 from ORCA's own energies, never mixed with PySCF's, cis
lower by 0.44 at this level and said to be smaller than the method's
error. H2CO -> H2 + CO: backward to formaldehyde, forward to an H2...CO
pair, barrier 84.72; the pair's optimised energy, +10.27, was delivered
as "separated H2 + CO", 0.21 kcal/mol below the separated fragments. A
staggered ethane called a transition state was recognised from its
dihedral before any engine ran; the goal lost its first cycle to a plan
that fed an optimisation's result file to its Hessian and IRC nodes and
settled ``exhausted``. The methoxy saddle from UHF/3-21G carries 0.0485
Eh/Bohr on the B3LYP surface; the session declined to walk an IRC from
it, displaced along the B3LYP mode and optimised to the two true minima,
withdrew its own barriers (36.64 and 42.69, each 2.0 above those of the
B3LYP saddle) as resting on a non-stationary energy, and was returned to
the human with the measurement it planned unclaimed. An IRC started there
on the reference side ends at a symmetric CH2OH 5.1 kcal/mol above the
minimum: a path from another surface's saddle is not this surface's path.

One claim of this topic was false until this round: "The driver re-converges
the SCF on the final geometry, from the optimiser's own last density". PySCF's
gradient scanner works on a copy of the mean field, whose orbitals the walk
never touches, so every optimisation's final SCF started from the supplied
geometry's density while its record said ``final_scf_from_optimizer_density:
true`` (the archived ``water_opt`` fixture: six final SCF cycles where a
restart takes one). The driver now builds the scanner it walks and restarts
from its last density, and the flag says whether it did; archived artifacts
keep the record they were written with.

Result contract v9 adds ``ts``: a saddle search on PySCF's own surface, so
an ``irc`` no longer needs a saddle another program located. It is the
IRC's own route rather than an exposed optimiser option --
geomeTRIC's partitioned rational-function step, driven with PySCF's engine
directly the way ``_run_irc`` drives the Gonzalez-Schlegel integrator, given
PySCF's analytic Hessian of the job's own surface at the seed as
``hess_data``. That Hessian is what tells P-RFO which mode to climb and what
keeps geomeTRIC from spending 6N gradients on a numerical one; taking it
costs nothing extra and buys the fact a chemist needs about a search that
has not run yet, which is what the seed was. The seed's spectrum and the
gradient there ride the artifact, so a search that started at a minimum, at
a saddle of another surface, or far from stationary is visible as that
rather than inferred from where it ended. ``START_POINT_PROMISES`` declares
nothing for a ``ts``: a guess is allowed to be anything, and the one
imaginary mode an ``irc`` start must have is a different promise.

The stage takes no Hessian where it arrives, exactly as an ``opt`` does not.
Convergence is a statement about the gradient and the step, never about the
order, and a ``hess`` node on the reached geometry is what settles which
stationary point it is -- which is also why a number delivered from a ``ts``
node is worded uncharacterised until that Hessian joins it, through the
organ ``opt`` already goes through (``GEOMETRY_SEARCH_JOBTYPES``).
geomeTRIC's own updated curvature at the end was recorded for one revision
and removed: on the H2CO/HCOH saddle this driver located to 0.0001 A of
ORCA's, a genuine first-order saddle, that unprojected internal-coordinate
Hessian had four negative eigenvalues, and a number nothing can read
correctly is worse than no number. v9 adds no applied-spec field, so its
digest vocabulary is v8's and every archived v8 digest stays
reconstructible; the version moves because an artifact whose ``stages``
names a stage an older reader has never heard of is a different contract.
The reader declares ``ts`` with the SCF set of the structure the climb
reached plus the seed's spectrum, served under the name an IRC's start
spectrum answers to -- one question, one selector, filed in two homes. The
trajectory vocabulary is deliberately absent: the frames of a search are an
optimiser's route to a structure and not a path on the surface. The whole
capability cost the stem tool schema four bytes.

The direct CLI evidence (CUHK Slurm 2141124, four minutes) climbed two
surfaces from seeds made by displacing archived ORCA saddles. H2CO /
trans-HCOH at HF/6-31G*: from a seed 0.24 A away and carrying **two**
imaginary modes at max|g| = 0.177 Eh/Bohr, eight iterations and nine
gradients reach ORCA's own OptTS saddle with every interatomic distance
agreeing to 1e-4 A -- no shared optimiser, no shared initial Hessian. The
Hessian there has one imaginary mode at -2700.0 cm-1, the frequency the
archived IRC fixtures start from, at max|g| = 3.1e-5; both branches walked
from it start at that geometry to 1e-6 A and reach trans-HCOH and
formaldehyde, the two minima the branches from ORCA's saddle reach. HCN /
HNC at B3LYP(G)/def2-SVP agrees with ORCA's saddle to 3e-4 A and gives
-1123.2 cm-1 against the -1123.0 the IRC round recorded on ORCA's. A search
cut at two steps keeps its seed spectrum, its three frames and max|g| =
0.129 where it stopped, and fails. And a search seeded at a *minimum* of its
own surface converges in one iteration, moves 0.007 amu^1/2 bohr and
delivers the minimum under a ``validated`` receipt: the case the stage must
not hide, readable only from the artifact's own account.

An earlier submission of that same batch (2141121) produced ten artifacts
and no receipt at all: the deployed controller's Python 3.11 refuses a
dataclass default that the authoring tree's 3.12 accepts, and every
invocation died importing ``chemsmart.agent.terminal_states`` after its
engine had finished. The engines were fine; the whole host layer was lost.
A probe that imports every module under the compute interpreter now runs
beside the suite.

Two defects the new fixtures found. Whether a Hessian's raw
mixed-derivative mismatch is graded against the analytic limit or kept as
quadrature evidence was read from the *caller's* settings, so the runner
called the archived ``hcn_hnc_ts_hess`` admissible and the host evaluator,
called with the settings it verifies, refused the same bytes: one Hessian,
two verdicts. It is read from ``spec/xc`` now, which is a fact the artifact
states about itself. And the unit guard demanded every declared home of a
selector be present, which a selector with two homes cannot satisfy; a
selector is absent when none of its homes is, and a home that is present
keeps its unit audited.

A sealed four-goal campaign ran the ts tree on CUHK (jobs 2141227-2141231,
default provider profile, approval delegated by the owner and recorded as
``opus-researcher-owner-delegated``, never a human decision), on the code
tree ``a63ee6e8``. No task named a transition-state search, a seed spectrum
or a path account; every one of the four planned a PySCF ``ts`` node from
ordinary language and executed one, six searches over four molecules, all
validated. **No goal settled ``achieved``.**

HCN/HNC reached the same saddle as the direct CLI and as ORCA (C-N 1.1882,
C-H 1.1966, N-H 1.3977 A), walked both branches from it -- start spectrum
-1123.2 cm-1, both ``reached_by: path_step`` -- to HCN and HNC, and
computed barriers of 47.84 and 34.16 kcal/mol, matching the direct-CLI
references to 0.01. It claimed none of them. Its analysis chain waited on
a Hessian at the HNC end, and that Hessian is the first on a linear
polyatomic in this corpus: HNC is 0.047 degrees from linear, the
mode-count rule's transverse tolerance answers about 0.01 degrees, and a
correct 3N-5 spectrum was refused with four findings and typed
``failed_native``. The session had reasoned correctly that a walked branch
proves the saddle promise and that a separate Hessian would cost an engine
call it could spend elsewhere; what defeated it was the host.

The formaldehyde goal relaxed a supplied Hartree-Fock saddle onto the
B3LYP/def2-SVP surface it was asked about -- seed max|g| 0.0378 Eh/Bohr
there, eighty-four times the criterion, reached 3.5e-5 -- and delivered
87.25 kcal/mol with the uncertainty decomposed and the saddle verification
held open as an unquantified component, because the Hessian confirming it
had not run. The elimination goal diagnosed, from the geometries alone,
that two of its own searches had converged to non-saddles, built a seed by
hand that worked, and ran out of revisions one node short of confirming
it. The hydrogen-peroxide goal located the cis rotation structure (one
imaginary mode at -612.8 cm-1, dihedral 0.000 degrees, O-O 1.4491 A
against a gauche minimum at 120.59 degrees) and delivered 34.72 kJ/mol.

Two host defects the campaign found are repaired where they were made. The
linear-rotor mode count above: a polyatomic's count is now the run's own,
the arrays follow it, and the independent reconstruction runs at the
translation-rotation rank that count implies, which reproduces PySCF's
four frequencies to 3.9e-6 cm-1 where the geometric rank dropped one. And
a Hessian that confirms a saddle was being typed
``failed_wrong_stationary_point`` for containing the one imaginary mode it
was run to find: ORCA runs ``OptTS Freq`` as one node, PySCF and xTB split
the same physics, and the Hessian half was judged as a minimum's. A fixed-
geometry curvature node now inherits the promise of whatever produced its
structure. It reads both ways -- a saddle search that converges onto a
minimum, which a converged ``ts`` cannot detect from its own artifact and
which happened live, now fails at its Hessian instead of validating.

Three things the campaign could not show. ORCA's arm of the cross-program
goal died in Startup on both cycles: the campaign template allocates
``--cpus-per-task=8`` on one task while the server profile writes ``%pal
nprocs 8``, so ORCA saw one MPI slot; the previous campaign's own script
used ``--ntasks=8`` and ORCA ran. Two goals lost their last two cycles to
three provider timeouts each, a sustained outage, with budget still in
hand; the host retried, typed the reason and settled without claiming
science, which is what that word is for. And every node in every goal
raised ``geometry.same_structure_comparison_not_made``: the basin sensor's
three-heavy-atom floor stopped on molecules of two, so the campaign's
molecule choice disabled it throughout.

One observation this round had reported as implemented and unobserved is
now observed. Finishing the elimination goal's question as a direct-CLI
diagnostic (2141482) shows its saddle genuine -- one imaginary mode at
-2191.9 cm-1 -- and its backward branch recording 77 frames of which 37
are path steps and 40 are the minimisation after them. The endpoint is
separated H2 and CO; "the IRC reached them" and "a minimisation from the
IRC's tail reached them" are different statements, and the path account is
where the host tells them apart.

Result contract v10 records what a total energy is made of. PySCF computes
the continuum's polarisation energy and, under SMD, the
cavitation-dispersion-solvent-structure term, adds both into ``e_tot`` and
keeps them in its own ``scf_summary``; the driver dropped them at the
boundary, so every solvated PySCF energy in this corpus was an opaque total
a session could not tell from a gas-phase one except by trusting a file
name, could not put in an expression or a claim, and could not read against
ORCA's. The driver now reads that summary after the final SCF and writes
``solvation_electrostatic_energy``, ``solvation_nonelectrostatic_energy``
and ``dispersion_energy`` beside the total, and the reader declares them for
every job type under the names and with the meanings the ORCA reader has
served for a round -- one selector name, one unit, two programs. Nothing is
recomputed here: a term the program did not produce is absent, never zero,
and the three absences are different facts that each name themselves -- no
continuum was attached, a PCM-family model has no CDS term by construction,
or the artifact predates v10. That took giving the unit audit a way to ask
the accessor: until then all three arrived as "dataset absent", which is the
class of defect where the mechanism is right where it is computed and
unconnected where it is consumed. ``solvation_model`` and ``solvent`` are
declared beside the numbers rather than only displayed on the level line,
because a solvation term whose model a claim cannot carry is how two legs of
a thermodynamic cycle come to disagree silently; they stay identities on the
provenance axis while the three energies declare ``reference``, which is what
an excited-root or correlated artifact needs, since PySCF adds them into the
reference's total whatever surface ran above it. v10 adds no applied-spec
field, so its digest vocabulary is v9's and every archived v9 digest stays
reconstructible; the version moves because under it a solvated artifact
carrying no continuum term is a defective record rather than an older one,
and the validator says so in both directions for the continuum and forwards
only for dispersion, where a functional whose name carries a correction
(``wb97x-d3bj``) produces the term with no ``dispersion`` setting behind it.

The direct CLI evidence (CUHK Slurm 2142387, five runs in nineteen seconds
of wall time, every receipt ``validated`` with no findings) is water at
B3LYP(G)/def2-SVP. At the gas-phase minimum SMD's polarisation term is
-10.122 kcal/mol and its CDS term +1.447; C-PCM at the same geometry and
the same level polarises by -6.491 and has no CDS term at all, which is the
difference between the two models rather than a parsing failure. D3(BJ) on
that water is -0.360 kcal/mol, and the corrected total lies below the
uncorrected one by exactly that: these terms are parts of the total, not
corrections to add to it, and an agent that subtracted one would double
count. An optimisation inside the continuum deepens the polarisation to
-10.174 and the terms belong to the structure it reached, as every other
property does. PySCF's own recomputation from each applied spec
(``reference.py``) reproduces every stored term -- 3e-16 Eh on the SMD
single point, 6e-17 on the C-PCM one, exactly on the dispersion, and 1.4e-7
Eh on the optimisation, where the recorded term comes from a final SCF
restarted from the optimiser's density while the reference converges a
fresh one there. What is not claimed: no cavity surface area, which ORCA
prints and PySCF does not compute as a number; the applied dielectric,
which rides the spec and the materialisation record and is not a selector;
a solvated correlated or excited-root artifact, which the settings
validator still refuses; and no GPU row, since GPU4PySCF has run none of
this.

One defect the round's own probe found is repaired where it was made.
``_validate_correlated_results`` -- "the components are finite and sum to
the total the artifact states" -- had performed no check on any artifact
since it was written. ``_finite_number`` is a predicate and was read as a
value: every entry of a ``results`` mapping read back from HDF5 is a NumPy
array, so each component answered False, the sum that followed compared
``False + False`` with ``False`` and agreed, and a component that was not
there at all was never reported because a bool is never None. It reads a
value now; all seven archived correlated fixtures still pass, and every one
of them goes red when a component is removed, which is the half that was
never true while the check was green.

Two live goals ran this surface on CUHK (jobs 2142392 and 2142398, the
default provider profile, the approval delegated by the owner and recorded
as ``claude-researcher-pyscf-owner-delegated``, never a human decision).
Neither task named a selector, a term or a model. Asked what the solvent
contributes to formaldehyde's energy, the first session searched the
catalogue, opened ``about_result_selectors_pyscf``, wrote and validated a
gas-phase and an SMD project file, and planned a two-node PySCF workflow
whose solvated node declares ``solvation_electrostatic_energy`` and
``solvation_nonelectrostatic_energy`` among the workflow's required
observables; three of the four expectation bands it declared are on the new
terms, and its own words separate "PySCF's own term, not derived" from "the
derived sum". Both nodes compiled and previewed with no critical finding,
and the goal settled ``execution_wave_decision_pending``: three provider
turns hit the 300-second transport deadline and the session never reached
its execution decision. The science was planned; the transport was not
there. The second session was given two completed runs -- the archived
gas-phase and SMD water single points, with their receipts -- and asked to
read them. ``inspect_run`` offered the solvation selectors on the SMD
artifact and not on the gas-phase one, which is availability per artifact
and not per job type; the session extracted the two terms with the model and
the solvent beside them, derived E(SMD) - E(gas) = -7.318 kcal/mol through
the host's own arithmetic, and claimed four numbers: that difference, the
program's own -10.122 and +1.447, and their sum -8.675. It settled
``achieved`` with an asserted 1 kcal/mol uncertainty for the continuum's own
parameters and an unquantified component naming the fixed geometry, so what
it delivered is an electronic contribution at one geometry and not a free
energy of solvation -- and it wrote down that the printed terms "do not
exactly partition the net (residual +1.36 kcal/mol measured)", which is the
electronic reorganisation the solute pays to polarise. No session could
state that decomposition here before.

An open-shell PySCF result served no HOMO and no LUMO, and served a gap.
``homo_energy`` answers only off multiplicity 1, so those two selectors
refused on every open shell, while ``fmo_gap``'s open-shell branch
subtracted the highest SOMO from the lowest virtual of *either* channel --
one channel's occupied level paired with the other channel's virtual one.
On the archived hydroxyl radical the two orbitals it subtracts are the
alpha and beta halves of the singly occupied orbital, so 4.7957 eV was
reported under the name a session reads as a frontier separation while the
beta channel's own separation is 4.0674. The ORCA reader had settled the
definition and states the reason -- for an unrestricted reference the
frontier orbitals need not share a channel, so the extremum over both is
what survives that case -- and this program had grown its own. PySCF's
reader states the same relation now and declares ``alpha_homo``,
``alpha_lumo``, ``beta_homo`` and ``beta_lumo`` beside it, each an
extremum over the orbital energies and occupations the artifact already
stores; nothing is authored. Triplet dioxygen is the case the definition
exists for: its highest occupied level is alpha and its lowest virtual
beta, so alpha alone reports 14.23 eV and beta alone 9.50 where the
separation is 5.34, and its gap is unchanged because the extremum was
already what it had. Three archived numbers move and no closed-shell one
does, since a restricted reference hands one orbital array to both
channels: hydroxyl at UKS 4.7957 to 4.0674, the same radical at UHF
18.6471 to 17.3843. The one-electron ROHF hydrogen atom keeps the zero gap
it already reported and now says why -- its one spatial orbital is
occupied in alpha and empty in beta, so the pair is that orbital twice --
and ``beta_homo`` refuses by name rather than returning a level that is
not there. What is not claimed: ``fmo_gap`` in the shared mixin still
carries the SOMO pairing for the log-parsing readers, so Gaussian and xTB
answer ``gap`` on an open shell by a construction ORCA and PySCF no longer
use; that is one shared function and it is not this program's to move.

The formaldehyde goal ran when the act that runs a workflow could be
reached. Its first issue settled ``execution_wave_decision_pending``, and
the transport timeouts were not the cause: ``select_execution_wave`` was
in no session's callable set at all. Re-issued unchanged on the repaired
tree (CUHK 2142406), the same task found it by searching in the words a
chemist uses -- "execute approved workflow run calculations wave approval
review readiness" returned that act and ``continue_execution_reasoning``
as its first two results -- selected a wave of two ready nodes, and ran
them under the approval chain: two PySCF single points on formaldehyde at
B3LYP/def2-SVP, gas phase and SMD water, both receipts ``validated`` with
no findings. The approved analysis chain then executed provider-free and
read the terms out of what those runs wrote, with ``solvent: water`` and
``solvent_model: smd`` in the extraction's level record beside them and
neither on the gas-phase node's: -6.625 kcal/mol of continuum
electrostatics, +4.104 of cavitation, their sum -2.522, against a
total-energy difference between the two runs of -1.026. It settled
``achieved_with_observations``, the observations being two
``geometry.same_structure_comparison_not_made`` -- the basin sensor's
three-heavy-atom floor on a four-atom molecule, as in the earlier
campaigns. This is the decomposition arriving from a calculation the
Agent planned and ran, rather than from one prepared for it.

A continuum is two numbers, not a name, and until now a session could
read only the name. The density is polarised with the static relative
permittivity; a vertical excitation leaves the solvent's nuclei where the
ground state put them, so PySCF answers a non-equilibrium response with
the optical permittivity instead -- a single hard-coded 1.78 for every
solvent it is handed, which is water's n squared. This topic has said
since contract v5 that the artifact records both and that "a toluene
fixture shows the divergence instead of hiding it behind water". The
recording was real and the reading never existed:
``status/stages/td/solvent`` has carried both numbers all along, a green
test has asserted them on the archived artifact for a round, and no
selector, level line or receipt served either, so what reached a session
was "C-PCM, toluene". Two such spectra differenced and called a
solvatochromic shift would have passed every digest, unit, geometry and
surface check on the way, which is the class of defect this laboratory
names by heart: the mechanism is right where it is computed and
unconnected where it is consumed. The reader declares both now, as
identities of the run rather than values on a density, exactly as the
model and the solvent name already are: ``solvent_dielectric`` wherever
an SCF converges, because a solvent name is not a permittivity and two
legs of one cycle can both say "water"; and
``excitation_response_dielectric`` on ``td`` alone -- an excited-root
``opt`` inherits the excitation set, PySCF has no solvated excited-state
gradient and the settings validator refuses one, so there the question
could never be answered and a declaration a job type can never satisfy is
worse than none. The level record ``inspect_run`` shows and every
extraction receipt carries names both numbers and the word that makes the
second operative. No contract version moves: these are bytes that were
already written, so every archived digest is untouched. On the archived
``water_td_cpcm_toluene`` the density was polarised with toluene's 2.3741
and the excitations were answered with 1.78, which against PySCF's own
``solvent_db`` is water's n squared of 1.7764 to 5e-3 and sits 0.46 away
from toluene's own 2.2383; so the whole solvent dependence a PySCF 2.14
spectrum can carry enters through the ground-state density. What is not
claimed here: no reader but this one answers either selector, and the two
numbers ORCA prints (``Epsilon``, ``Refrac``) and the two Gaussian prints
(``Eps``, ``EpsInf``) are where the shared names will meet a second
program when one of them declares them.

One live goal ran that surface (CUHK Slurm 2142833, three hours seventeen,
settled ``achieved``, the approval delegated by the owner and recorded as
``claude-researcher-pyscf-owner-delegated``). The task named no selector,
no permittivity and no solvent model; it asked how far the absorption band
of trans-4-(dimethylamino)-4'-nitrostilbene, a push-pull dye of twenty
heavy atoms, moves with solvent. The session chose CAM-B3LYP itself and
recorded rejecting B3LYP and PBE0 for placing the charge-transfer state
too low, optimised once, and carried that geometry into three ``td`` nodes
through the optimised-geometry edge -- each node's supplied structure
equals the reached one to 4.9e-11 Angstrom, so the three spectra differ
only by the continuum. The bright root is root 1 everywhere: gas 3.51179
eV at f 1.24279, C-PCM n-hexane 3.31881, C-PCM acetonitrile 3.20362, and
the host's own arithmetic gave the n-hexane-to-acetonitrile shift as
-0.11519 eV and +13.43 nm, red as a charge-transfer band must be. The two
runs applied static permittivities differing by a factor of nineteen,
1.8819 and 35.688, and their responses applied the same 1.78; so that
shift is ground-state density polarisation and the excited-state fast
response contributed identically in both solvents, which is the sentence
this surface exists to make sayable.

It was not said. The cycle-1 plan asked for both permittivities on both
solvated nodes and on neither the gas node, which is the discovery half
working; woken after the optimisation, the session replanned and bound
only the excitation energies and oscillator strengths, and delivered the
shift without naming the permittivity that bounds it. The numbers were on
every receipt it held -- the level record inside each extraction receipt's
digest carries both on a solvated node and neither on the gas one -- so
what the goal qualifies is ``excitation_energies`` and
``oscillator_strengths`` on ``td``, and the two permittivity selectors
stay tested. Reachable is not used, and a level field a session never has
to ask for may be a field it does not read.

The reference-stability record is now read the way the permittivities are.
``status/properties/scf_stability`` has carried PySCF's own analysis since
result contract v7 and one organ consumed it, the sensor step that raises
``scf.reference_unstable``; no selector served it, so a session could not
state that the orbitals its energy came from are a saddle in rotation
space, and could not report a sound reference at all. Three selectors
answer it now -- ``scf_stability_internal``, ``scf_stability_external``
and ``scf_stability_external_rotation_space`` -- declared wherever an SCF
converges, as the spin diagnostic is. They are deliberately not served
under Gaussian's ``wavefunction_stability_verdict``: Gaussian prints one
word about one unnamed question, PySCF answers two questions and names
each rotation space, and the archived dioxygen pair is why that matters --
the singlet at RKS and the triplet at UKS are both ``unstable`` and the
first is about ``RHF/RKS -> UHF/UKS`` while the second is about
``UHF/UKS -> GHF/GKS``, which is two different physical statements. Four
absences stay four facts and none of them is stability: not asked, older
than v7, a question PySCF cannot answer for this reference -- an ROHF
hydrogen atom has no external answer while its internal one is still
served -- or no answer returned.

A live goal (CUHK Slurm 2145043, 24 minutes) asked whether the
closed-shell description of the push-pull dye of the previous goal is a
sound one, starting from that goal's own reached-geometry handoff file. It
ran one single point with the analysis, and the answer is that the RKS
reference of trans-4-(dimethylamino)-4'-nitrostilbene at CAM-B3LYP/def2-SVP
is stable both internally and to ``RHF/RKS -> UHF/UKS`` -- so the
absorption energies of the previous goal do rest on a sound reference --
with ``real -> complex`` undetermined by that tree's record, though the
log printed every question's eigenvalues. The energy there,
-878.0848750592156 Eh, reproduces the optimisation's own total to 5e-12 Eh,
which is the handoff arriving intact across two goals.

The goal did not settle ``achieved``. Its session declared its observables
as *numbers* -- the lowest eigenvalue of each stability matrix -- and the
host verified, against the reader, that no program exposes such a number
for ``sp``; it settled ``unreachable_from_evidence`` with the verdicts
delivered inside the recorded decision and the word ``stable`` quoted from
the reader, rather than converting a word into a number. That is the
refusal behaving correctly, and it exposes a boundary this topic did not
have before: a declared observable carries a unit and the completion gate
requires a claim in its dimension, so a *categorical* selector can be
extracted and can ride a receipt but can never be the thing a goal
delivers. That holds for every word-valued selector in the shared
vocabulary -- ``solvation_model``, ``solvent``, ``irc_direction``,
``functional``, ``basis`` -- and not only for these three. The three cells
are therefore exercised and not qualified: no extraction receipt bound
them and the host wrote no qualification row, and a capability is not
qualified because a settlement quoted it.

R10 Q13 (2d927932) served the numbers that goal had declared: each
stability question's lowest eigenvalue is a PySCF ``sp`` selector. The
same task, rerun byte-identical on the same geometry (CUHK Slurm 2152080),
settled ``achieved`` with the RHF/RKS -> UHF/UKS root +0.042085 Eh
delivered, real -> complex stable at +0.1135 Eh, and the energy again
-878.08487505922 Eh; four selector records name those runs.
