# P7R residual lifecycle closure receipt

Date: 2026-07-19
Status: source closure green; exact-source frozen PyInstaller gate pending
Packaging path: PyInstaller only

## Scope

This slice closes the source-side macOS Quit and QtWebEngine ownership defect
without changing the CLI, Textual TUI, scientific job semantics, agent safety
boundary, or optional PyMOL execution contract.

The accepted prior internal-alpha artifact remains historical evidence. It does
not contain this source change and therefore cannot satisfy the frozen P7R gate.

## Implemented lifecycle contract

- `Quit ChemSmart` has the standard macOS Quit role and closes all windows
  through their normal `closeEvent` paths.
- Main-window shutdown is two phase: all task-owning screens and the optional
  PyMOL controller must drain before the owned WebEngine page/view is released.
- A rejected close leaves the visible window and 3D viewer intact.
- WebEngine page/view destruction is deferred outside WebEngine callbacks and
  remains idempotent.
- The hidden lifecycle probe creates a real 3Dmol/WebEngine renderer, records
  its PID, triggers the product Quit action, and records event-loop return.
- Renderer and main-process termination are proven by the external bundle
  verifier after the app process returns, avoiding an in-process circular wait.
- Bundle PID ownership is fail-closed: candidates are regex escaped, pgrep tool
  errors are distinct from no-match, and each PID's executable must resolve
  inside the exact app `Contents` tree.
- The verifier rejects a nonempty initial app baseline, shares one baseline
  across all launches, and requires zero residue after every probe, shell, and
  lifecycle launch.
- A leaked PID is preserved as failure evidence, revalidated before signalling,
  cleaned without touching a pre-existing process, checked again, and prevents
  any subsequent launch.
- Inspection failures kill the direct launcher and attempt exact cleanup from
  both already tracked PIDs and an independent process-table fallback.

## Source evidence

- Focused lifecycle, shell, probe, and verifier gate: 69 passed.
- Complete GUI suite within the final preservation run: 399 passed, one
  optional-dependency skip (400 tests collected).
- Packaging-workflow source-preservation gate: 517 passed, one
  optional-dependency skip.
- Twenty fresh-process lifecycle cycles: 20/20 return codes zero, receipts
  passed, event loops exited, renderers started, external-check ownership
  recorded, and renderer PIDs absent after parent return; 42.102 seconds total.
- Ruff, compileall, and `git diff --check`: green.
- Independent source review: GREEN, Critical 0, High 0, Medium 0.

An exploratory all-repository run was not used as the phase gate. It reported
2,590 passed, 26 skipped, one expected failure, and 40 failures attributable to
the current unprovisioned Open Babel dependency, a local Click test-runner API
mismatch, and an existing cross-test working-directory leak. The exact isolated
packaging source gate above is green and does not require changing those
unrelated environment/test issues in this lifecycle slice.

## Frozen gate still required

P7R is not complete until a PyInstaller macOS 14 arm64 artifact built from the
phase commit passes the updated verifier. Required evidence includes:

- the lifecycle receipt names a real renderer PID and records normal Quit and
  event-loop return;
- the reported renderer is absent before cleanup and after cleanup;
- every probe, shell, and lifecycle launch leaves zero exact-bundle processes;
- the final process baseline is empty;
- all updated mandatory flags, signature, archive round-trip, inventory,
  runtime-lock, SBOM, and internal-alpha release gates pass.

No provider request, secret access, real calculation, scheduler action, HPC
submission, package installation, or non-PyInstaller packaging path was used.
