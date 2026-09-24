# R10 episode Q18 -- an open-shell singlet the model can ask for without knowing any program

Base: `0ac28beccad766aa743945c4a693de7a5c0e4cec` (verified with `git rev-parse HEAD`
as the first action of the episode, 2026-09-24).

## The question as currently understood

Can the Agent ask for an open-shell (broken-symmetry) singlet as a typed
electronic-state request that the hub translates into each program's own
mechanism (ORCA, Gaussian, PySCF), states in the review, and refuses where no
native equivalent exists? Does the host then record which reference actually
ran and whether spin symmetry actually broke (<S**2>, the program's stability
answer), so the Agent can tell a real diradical from a collapsed closed shell?

## Falsifiers of the premise (armed before any census or run)

- F1 (census): if the archived goals (CUHK R8-R10 under /project/xlzhang/jiseung,
  excluding r10/q6/goals and r10/q3, plus the ax41 mirror's campaign
  workspaces) contain no open-shell-singlet / broken-symmetry request other than
  R10 Q15's g1, the premise "the model needs this as a typed request" is weak:
  repair that route only and end.
- F2 (portability): if a typed request cannot mean one thing across programs,
  say exactly what is portable (the intent and its verification through <S**2>
  and stability) and what is not (the particular solution found).
- F3 (the prior about Gaussian): if Q15 g1's restricted `b3lyp ... guess=mix`
  route actually converged an unrestricted broken-symmetry solution, the
  brief's "probably inert" prior is false.

## Status

- 2026-09-24: episode opened; gate open (hpc --check).
