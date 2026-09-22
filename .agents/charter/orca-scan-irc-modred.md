# Charter topic: orca-scan-irc-modred

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
every binding before launch.

An IRC log's only printed structure is the starting point, so every
selector read from the log body describes the saddle rather than the path:
the first executed chain rendered the transition state's own distances as
both endpoints, and its printed energy differs from the endpoint by the
entire barrier — 33.40 kcal/mol, measured again on job 2142379.
``energy``, ``positions`` and the orbital, dipole and spin families are
therefore not declared for the jobtype, and selector declarations gate
extraction rather than merely advertising coverage.

The path itself is not absent from the host. ORCA prints it as the IRC
PATH SUMMARY table and writes each branch's endpoint to its own
``_IRC_F.xyz`` / ``_IRC_B.xyz`` sidecar. The reader reads both and binds
each end to the other by the table's own energies, declaring
``trajectory_energies``, ``trajectory_frame_count`` and the two ends of
the branch; the endpoint carries the ``as_reached`` structural state, so
``bind_reached_geometry`` carries an executed branch's product structure
into the optimisation that identifies the minimum and seals the sidecar's
name and digest on its receipt. A ``direction both`` run leaves two branch
endpoints and its path table opens 45.5 kcal/mol below its own saddle, so
the geometry selectors refuse it and name the route: one direction per irc
node. Whether a saddle connects two particular minima remains an
observation a scientist makes from the two branches, not a host-rendered
claim; what changed is that each branch's profile and product are typed
evidence rather than files on disk. Carrying that endpoint inside a single
approval is still refused — the in-approval producer edge asks for
``reached_positions`` by name — so the reuse route is a new workflow with
its own review.

ORCA ``modred`` is a constrained optimisation: it relaxes every degree of
freedom except the ones it holds, so what it returns is a structure on the
surface at a chosen value of a chosen coordinate, which is what seeds a
saddle search. A completed one now answers. The reader declares the job
type the host's classifier had already been assigning it, and the
constraint family says which coordinates were held, by which atoms and at
what value -- each kind under its own name so a bond keeps its Angstrom
and an angle its degrees, and each value measured in the structure ORCA
returned rather than copied from ORCA's declaration of it, because a
reader that echoed the table would say "held at 2.4714" about any
geometry at all. Disagreement beyond the reader's tolerance is reported
with both numbers and names ``reached_positions``: a constraint that did
not hold is a finding, not a parse error. The vibrational family is
absent by decision -- a constrained optimum is a stationary point only in
the subspace orthogonal to what is held, ORCA projects nothing out of the
Hessian it prints, and no thermochemistry is derived from one. The
structure it reaches may cross a producer edge inside one approval, as an
optimisation's or a saddle search's may.

Execution is still not claimed. A live goal did run one under the approval
chain -- ORCA held BINOL's biaryl torsion to -1.4e-5 degrees for 103
cycles and the whole approved node budget, relieving the strain a rigid
turn to coplanarity had created -- and it neither converged nor left a
receipt, because the host's own teardown crashed at the approved timeout.
No node completed, so the execution flag stays false and is earned by a
goal that finishes one.

Two sentences were bought by live streams on a BINOL racemisation task.
Asked to relax the molecule with its biaryl torsion brought to a coplanar
value, the first session read "coordinates held fixed while everything
else relaxes" as "moved there and held", wrote the value it meant into a
``modred`` project YAML as a key the loader does not have, had it
correctly rejected, and replanned the stage as a relaxed scan -- the only
coordinate vocabulary that carries a target. A constraint holds a
coordinate where the bound geometry already has it, in ChemSmart as in
ORCA's own ``{B i j C}``, and the two legal routes to a value a structure
does not yet have are to edit the coordinate there first or to drive a
range with a scan. The second session took the edit, and then offered the
coordinate to an ``opt`` node; the refusal it met was true and named no
route, so it dropped the coordinate and compiled a plain optimisation,
which relaxes straight off the coordinate it had been asked to hold. A
refused job option now names the job types of that program whose live
Click scope carries it.
