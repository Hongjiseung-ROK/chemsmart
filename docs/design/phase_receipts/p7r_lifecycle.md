# P7R residual lifecycle closure receipt

Date: 2026-07-19
Status: complete — source and exact-source frozen PyInstaller gates green
Packaging path: PyInstaller only
Phase commit: `537af747c00772c38af37ce22906b48eaa62f4e0`
Frozen run: `29688097421`

## Scope

This slice closes the source-side macOS Quit and QtWebEngine ownership defect
without changing the CLI, Textual TUI, scientific job semantics, agent safety
boundary, or optional PyMOL execution contract.

The accepted prior internal-alpha artifact remains historical evidence. P7R is
closed by the new exact-source artifact described below.

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

## Frozen PyInstaller evidence

Authorized manual workflow run
[`29688097421`](https://github.com/Hongjiseung-ROK/chemsmart/actions/runs/29688097421)
built exact source and workflow SHA `537af747c00772c38af37ce22906b48eaa62f4e0`
on macOS 14.8.7 arm64 with Python 3.11.9. The job completed green in
12 minutes 36 seconds.

- Remote source preservation: 517 passed, one optional skip.
- All 21 updated mandatory bundle flags: true.
- Three isolated probes: 7.559, 8.287, and 8.618 seconds; each returned zero,
  did not time out, and left no process before or after cleanup.
- Product shell: 4.799 seconds, zero return, no timeout, no residue.
- Lifecycle launch: 4.212 seconds; WebEngine loaded, renderer PID `41439`
  started, the standard Quit action was requested, the event loop returned,
  and the renderer was absent both immediately after return and after cleanup.
- Initial and final exact-bundle process sets: empty.
- App: 811,947,039 bytes, arm64, bundle ID `org.zhanglab.chemsmart`, declared
  minimum macOS 14.0, binary minimum macOS 11.0.
- App inventory: 10,633 files, 2,098 directories, 1,959 relative symlinks,
  zero broken/absolute/escaping symlinks; inventory SHA-256
  `d28fe2f31721704b4481703b9dcdd3034238fb0773f729f35a020bfa72b8afd1`.
- Inner bundle archive: integrity test green; SHA-256
  `2c8a3d109930c62ae4990651d10ddcd85ad8e4a1d9d1aa320567368f061d4b85`.
- Internal-alpha DMG: 338,305,547 bytes; SHA-256
  `93495887fd199a203c8eeddad87d8d336a8cd615569f3624a6a2b9f68b89f5b4`.
- SBOM: 111 shipped components; SHA-256
  `7e6c0609a048afc85230d500a0b4cdfa14cd6bf12b1f67c334ac656e1e8b63eb`.
- Runtime lock: 134 expected distributions, 135 installed including only the
  allowed unlocked local `chemsmart`, with no missing, mismatched, or unexpected
  distribution.

Downloaded artifact IDs and GitHub artifact digests:

- evidence `8442823957` —
  `sha256:93c05a6d01dadf5b4f1f44994a0b6b4b42c64a7b3ec04459edab4bc77e9fbf04`;
- verified bundle `8442824465` —
  `sha256:06ea7b4928cfe10d4a0331a6e8c1c8e56ae55907423003756b13b3f87650831d`;
- internal alpha `8442825015` —
  `sha256:098d82011efaaea73aef9c2a725738afaca9a13b9892f2c6441339726f191830`.

Independent local artifact checks also passed: every distributed checksum,
bundle ZIP decompression, `hdiutil verify`, read-only DMG mount, strict/deep
ad-hoc signature validation, arm64 executable identity, bundle identifier,
Applications link, README presence, and clean detach.

This remains an ad-hoc signed internal alpha. Gatekeeper rejection is expected;
Developer ID, hardened runtime, notarization, stapling, and named clean-lab-Mac
product acceptance remain separate P7/P8.7 gates rather than P7R claims.

No provider request, secret access, real calculation, scheduler action, HPC
submission, package installation, or non-PyInstaller packaging path was used.
