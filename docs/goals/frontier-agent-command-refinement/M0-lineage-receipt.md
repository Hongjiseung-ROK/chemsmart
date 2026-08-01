# M0 Lineage and Preservation Receipt

## Recorded branch facts

| Item | Recorded value |
| --- | --- |
| exact remote foundation base | `cf986251077b7ee65f8afa951ee76052146c7613` |
| command-refinement parent | `6da43bab030b90ea5b9777105f78fd5848dd4aed` |
| preserved precursor snapshot (local and `fork`) | `8eb17c468c4cbe3c49c64563928a9f7213a602ca` |
| active refinement branch | `codex/frontier-agent-command-refinement` |
| original checkout branch | `feat/agent-xtb-harness` |
| original checkout boundary observation at scope entry (2026-08-01) | 72 porcelain entries; SHA-256 `22afaff13b12d50278d32e11975bf70f368e839ac3d6817a373ee578adee0679` |
| original checkout observation before target validation (2026-08-01) | `fbb82316d13370940080a6b6981f9a047edb761b`; 14 porcelain entries; SHA-256 `684d57bfcc7887a3b8d7f6ae4b83f06b459ab203a63042b06f97321e02ec3f0e` |
| original checkout final read-only observation (2026-08-01) | `fbb82316d13370940080a6b6981f9a047edb761b`; 72 porcelain entries; SHA-256 `22afaff13b12d50278d32e11975bf70f368e839ac3d6817a373ee578adee0679` |

## Preservation statement

The precursor's dirty work was preserved in the named snapshot before active
command-refinement work. M0 documentation and skill work are confined to the
isolated ChemSmart worktree and must not mutate the original checkout.

The intermediate original-checkout observation does **not** match the entry
and final observations. The target worktree did not write to that checkout,
and the final porcelain digest matches the entry digest, but the transient
change cannot establish who changed it or whether all intermediate work was
equivalent. Treat this as an out-of-scope custody exception: preserve the
current checkout untouched, do not use this matching digest as a release-
success claim, and require a human owner to reconcile it before any operation
that would touch that checkout. The digests deliberately record only Git
porcelain text, not unrelated artifact names or contents.

## Remote boundary

This receipt does not assert that the active refinement branch has been pushed.
Before any non-force push, fetch `fork`, verify the destination branch state,
scan the exact proposed content for secrets, and record matching local/remote
SHAs only after success.
