# Charter topic: vibrational-modes

> Evidence, not instruction: what this surface was qualified by and what it found, under the
> conditions stated. The live tree and ``chemsmart agent capabilities`` outrank it; doctrine is
> ``AGENTS.md``, ``CONDUCT.md`` and ``.agents/rsl/``.

A vibrational frequency states how fast a mode moves and never which
atoms move in it, so a session facing a small imaginary mode could not
separate one methyl rotor from another by magnitude alone.
``vibrational_mode_atom_participation`` is each atom's share of a mode's
squared displacement, one row per mode summing to one, derived by the
host from the displacement vectors the program itself printed and
renormalised so the quantity means the same thing across programs whose
vectors do not: ORCA, Gaussian and xTB print Cartesian displacements at
unit norm while PySCF returns the same physical displacement scaled by
one over the square root of the reduced mass, and a per-atom share
divides that per-mode scalar out along with the arbitrary eigenvector
sign and the program's coordinate frame. What renormalisation cannot
remove is each program's atomic mass table, and that limit is stated
where the quantity is defined. The share is an observation: naming a
mode's motion is the scientist's claim, never the host's. Because the
individual eigenvectors inside a degenerate set are an arbitrary basis,
``vibrational_mode_degeneracy_group`` records which modes share a
frequency within a stated tolerance, so a reader can see that a mode has
company before assigning motion to it. Declared for ORCA ``opt`` and
``ts``, xTB ``hess``, and PySCF; Gaussian is deliberately undeclared and
unadvertised, because this release never executes Gaussian and its
displacement block varies with options the reader cannot yet detect.
This surface is qualified through one completed re-observation of the
case that motivated it: given two converged amide rotamers whose strict
verdicts failed, a session read the table and named the acetyl methyl
rotor in one and the N-methyl rotor in the other, a distinction seven
earlier sessions could not draw from frequencies alone.

A program's printed modes are attached to the structure they describe,
which is what lets a result that settled on a saddle be stepped off one.
Where the modes and the structure come from different files, as xTB's
do, they are attached only when the two frames agree atom for atom; a
structure in another orientation is reported without modes, and the
operations that consume them refuse rather than displacing along rotated
axes. Qualified through completed Agent execution: handed only a planar
ammonia saddle, one goal characterised it, displaced it both ways,
relaxed both, bound the structure it reached and confirmed it with a
validated Hessian of six real modes.
