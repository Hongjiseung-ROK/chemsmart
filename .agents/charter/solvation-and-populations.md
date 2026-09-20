# Charter topic: solvation-and-populations

A completed solvated ORCA result can say what its solvation cost. The
electrostatic term, the SMD cavity-dispersion term and the cavity surface
area are declared for ``opt``, ``sp`` and ``ts`` beside the solvation
model and the solvent name, and each reads the last printed block because
an optimisation prints one per SCF step. Absence is meaning rather than
failure: a gas-phase result reports the terms absent, and a CPCM run has
no cavity-dispersion term, which is how it differs from an SMD run. The
terms report what the program *applied*, which is not always what the
route requested, so they are read beside the model rather than instead of
it. A program declares a term where an archived solvated result of its
own exercises it, and nowhere else. PySCF answers the same two solvation
energies from its own ``scf_summary`` under result contract v10 — the
continuum's polarisation energy for every model it attaches, and SMD's
cavitation-dispersion-solvent-structure term — and answers no cavity
surface area, because PySCF discretises a cavity and does not report its
area as a number. xTB answers its solvation free energy, the
electrostatic term and its own SASA, hydrogen-bond and shift terms from
the block it prints, and says that a run was solvated from the model
line rather than from one Hamiltonian's field; a GFN-FF solvation free
energy is not the sum of the terms it prints and is not decomposed. No
archived Gaussian log carries the printed terms, so Gaussian declares
none. The sentence this replaces read "every archived xTB run has solvation switched off";
two ALPB(toluene) runs had arrived with the xTB parser itself, and a
track found it by opening them.

Per-atom populations are positional and named by the scheme that produced
them. Atom-label schemes disagree between programs — ORCA numbers atoms
globally while xTB counts within each element, so the same atom is
``C3`` in one and ``C1`` in the other — and a mapping cannot be reordered
safely afterwards, so labels are resolved against the molecule's own
symbols at the reader and a scheme that does not match is refused rather
than guessed. Mulliken and Löwdin are declared for ORCA because ORCA
prints both without being asked. Hirshfeld is declared for the same three
job types and reached through the project route channel, which carries
two kinds of token and no others: a source-required keyword that refines
an otherwise supported typed method, and a print directive that changes
no method and only makes the program report more of what it already
computed. Both are displayed to the reviewer on their own beside the node
that carries them, because a single word inside a settings dump is what a
reader skims past. PySCF declares Mulliken, which its driver computes and
stores under a mandatory declared unit; xTB's population comes from a
minimal tight-binding density and is not Mulliken, so no xTB accessor
answers to that name. Gaussian declares Mulliken, which it prints
without being asked, and Hirshfeld, through the same kind of print
directive; it prints no Löwdin partition, so that name stays absent
rather than being served by the nearest scheme. CM5 stays parsed and
undeclared. The scheme is in
the name because the schemes disagree: on one phenoxide anion Mulliken
places more than a whole electron of excess charge on the hydroxyl oxygen
where Löwdin places about a third of one, and neither is "the charge on
the oxygen". They also do not close on the formal charge alike — the two
basis partitions divide a sum over basis functions and close to their
printed decimals, while a basin partition divides real space on a
numerical grid and closes two orders of magnitude looser. Both are far
from what a dropped or duplicated atom would cost, so the checksum
remains the check that a per-atom vector is complete and in molecular
order.

This surface is qualified through one completed analysis-only delivery
over four finished results with no engine launched, and the delivery
found a defect the release had carried for years. ORCA prints one column
of populations for a closed shell and two for an open shell, charge then
spin, under a header whose text contains the closed-shell header, so a
reader taking the last number on the row returned charges for restricted
results and spin populations for unrestricted ones under a single name.
Nothing had noticed because nothing in the typed layer had ever read
them; a session that added the vector up saw a neutral radical's charges
sum to +1.00 e, flagged it as unresolvable from its surface rather than
explaining it away, and the trace led to the reader. The values are now
read by position, the per-atom sum matches the formal charge for every
tested species, and the correction reaches further than the new
selectors, because those properties are attached to the molecule and
stored by the database assembler.
