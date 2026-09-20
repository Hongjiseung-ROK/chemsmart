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

ORCA ``modred`` is declared for planning, preview, and native-input generation
only. Constrained optimisation is expressible and previewable, and no
constrained optimisation has yet run here, so this release does not describe it
as completed Agent execution.
