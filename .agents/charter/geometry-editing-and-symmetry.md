# Charter topic: geometry-editing-and-symmetry

> Evidence, not instruction: what this surface was qualified by and what it found, under the
> conditions stated. The live tree and ``chemsmart agent capabilities`` outrank it; doctrine is
> ``AGENTS.md``, ``CONDUCT.md`` and ``.agents/rsl/``.

``edit_molecular_geometry`` sets one internal coordinate of an
identity-bound geometry — bond length, angle, or torsion, the same
three coordinates a scan drives — as a host-owned rigid motion. The
model names the coordinate, the target value in the coordinate's own
unit, and which side moves; which side moves is a scientific choice
with three incompatible library conventions behind it, so it is named
by one of the coordinate's own atoms, never defaulted, and the receipt
enumerates every atom that actually moved. The host measures the
coordinate before and after with the same arithmetic the typed
analysis layer uses, verifies it reached what was asked, and records
close contacts and connectivity changes as observations, never
verdicts. Refusals are structural only — an axis that is not a
perceived bond, a ring a rigid motion would tear (which differs per
coordinate), collinear or out-of-range atoms; no energy exists at edit
time and a requested value is never refused on scientific merit,
because grading it is what the consuming optimisation is for. An axis
the perception does not carry is refused with the numbers behind the
refusal -- the distance, the cutoff, the signed margin, the policy id --
and with the routes onward, because a perception convention blocking a
geometric action is a host decision about chemistry and the session is
entitled to see how narrowly it was made. An
edited geometry is a starting structure; atom count, order, and
formula are preserved, so parent atom i is edited atom i and a later
analysis may re-measure the same coordinate on the relaxed result.
Which atoms are adjacent is a host-owned convention, and it is declared
rather than implied. One module decides it for every agent-reachable
consumer, under one named policy: a pair is adjacent when its distance
falls below ``min(1.30 x (r_A + r_B), (r_A + r_B) + 0.45 A)`` on covalent
radii, the factor governing pairs whose radii sum is small -- every pair
involving hydrogen -- and the cap governing the rest. A delivered
adjacency carries, per pair, the distance, the cutoff applied, the policy
id and the **signed margin** by which the pair cleared or missed it,
because a boolean produced by a threshold cannot otherwise be told from a
structural fact. Bond order, aromaticity and valence saturation are not
derived from that cutoff and are not claimed: a distance cannot see where
electrons are, and a number derived from the cutoff moves whenever the
cutoff moves. The cases that have no distance answer -- [FHF]-, B-H-B
bridges, agostic interactions, every proton-transfer saddle -- sit near
the line by their nature, and for those the margin is what the host owes
its reader: it reports what its convention said and how narrowly, and the
scientist draws the chemical conclusion.

The form is two-regime because a single one was measured against this
repository's own structures and failed. An additive tolerance is
scale-inconsistent -- 0.05 A is 8.1% of the H-H radius sum and 3.3% of
C-C -- and hydrogen's covalent radius under-describes its bonds more than
any other element's, so the tightest tolerance sat exactly where real
bond-length variation is largest: H2 at its experimental 0.7414 A had no
perceived bond, a hydrogen-bonded O-H at 1.030 A had none, SiH4 was five
separated pieces, and one converged formaldehyde was delivered with no
C-H bonds while the same molecule at a larger basis carried both. A pure
multiplicative factor fails at the other end: the admissible single
factor is only (1.1958, 1.2473), bounded below by H2 and above by a
non-bonded C...Ti contact at 2.944 A in this repository's own conformer
corpus. Two human-CLI conventions -- the conformer grouper's tolerance
and the rdkit wrapper's -- remain deliberately separate and declared as
legacy rather than presented as interchangeable, because a difference
between two *named* conventions is a scientific observation while two
unnamed answers to one question is the defect this declaration exists to
prevent.

``append_molecular_atom`` is derivation's mirror: one atom, placed by
the three internal coordinates that define its position against three
anchor atoms; parent indices are unchanged and the appended atom is
last. ``displace_along_vibrational_mode`` is the third of the family
and the one a failed stationary point calls for: it steps a completed,
frequency-bearing result's own geometry along one of the normal modes
that result printed, which is what a chemist does when an optimisation
converges onto a saddle rather than a minimum, or when a
transition-state search returns the wrong number of imaginary modes.
The displacement vectors are the program's own and the host owns the
arithmetic, recording the largest displacement it actually achieved
beside the one requested; the model owns which mode and how far. It is
declared for every reader that serves printed modes -- the artifact
kind is the reader's word, never derived from a program's name -- and
is a starting-structure operation like the other two: refusals are structural only — a result printing no
modes, a mode the result does not carry, a zero amplitude — and an
amplitude is never refused on scientific merit, because whether the
step escaped the saddle is decided by the optimisation that consumes
it. The sign of the amplitude chooses the direction along the printed
mode, so the two sides of a saddle are two steps of opposite sign. All three operations bind no electronic state — adding a
hydrogen gives a cation or a radical depending on whether it brought an
electron — so charge and multiplicity are bound explicitly afterwards,
the consuming stage is a new workflow, and the displayed review
renders every hop of a built geometry's chain root-first, because the
hop that decides what the molecule is can sit at the root.

A source geometry carries its builder's symmetry, and an exactly
symmetric start converges to the nearest stationary point of that
symmetry, which is a saddle whenever the minimum lies lower: six live
saddles in two goals came from an idealised D4h start and from methyl
rotors appended at torsions of exactly 60, 180 and 300 degrees. The
host therefore states, on every identity binding and every compiled
node, a point-group estimate found within 0.01 Å from the molecule's
own atoms (and within 0.1 Å when the two differ) together with the
count of built coordinates placed on the exact 60° torsion lattice or
at exactly idealised angles; the estimate rides the review beside the
node's CLI operation as a host observation and never as a refusal. Every
coordinate a session *builds* is counted, appended or edited, because the
two are one act: a live conformer study set one torsion to exactly 0.00°
and exactly 180.00° by editing it, and the 0.00° structure was
syn-periplanar butane -- the top of the rotational barrier rather than a
conformer -- while the counter read append receipts alone and said
nothing. The sentence this replaces named appended atoms only, and the
saddles it cites include an idealised D4h start, which is no append at
all.
``break_symmetry`` is the fourth starting-structure operation: it
perturbs every atom of an identity-bound geometry by a seed and an
amplitude the model names, so the same request gives the same bytes,
removes the net translation, rescales so no atom exceeds the
amplitude, and records the largest step it actually took and the
point-group estimate before and after; refusals are structural only
and an amplitude is never refused on merit. It is declared and
previewable; no approved workflow has yet consumed a perturbed
geometry, and this release does not describe it as completed Agent
execution.

This surface is qualified through completed Agent executions in which
requested-versus-relaxed is the delivered observable: an
N-methylacetamide rotamer study whose cis form is reachable only by a
deliberate amide-torsion edit (the edit survived relaxation to 0.01°;
a task-supplied claim that the amide C–N is an ordinary 1.47 Å single
bond was contradicted by relaxation at 1.363 Å on the same page; the
trans rotamer validated as a strict all-real minimum; successive
sessions diagnosed methyl-rotor saddles from failed strict verdicts
and repaired them by displayed edits, and the completed series
established that the cis form's two methyl rotors are geared, so its
strict minimum is recorded as honestly unconfirmed rather than
claimed); a 1,2-difluoroethane transfer in which the session built
both gauche enantiomers by edits, predicted the gauche effect with
its mechanism before any number existed, and physics returned gauche
lower with the requested 60° torsions relaxing to 71.9°; and an amide
protonation study in which both conjugate acids exist only through
appended protons, the O-protonated cation validated as a strict
minimum confirming the session's resonance-based site prediction, and
the appended O–H and N–H bonds relaxed within 0.01 Å of their
requested lengths. N edits are N observations; no spatial-competence
score or aggregate exists, and nothing grades a request except the
relaxation that consumes it.
