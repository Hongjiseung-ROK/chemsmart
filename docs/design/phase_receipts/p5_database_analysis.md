# P5 receipt — Database and structured analysis

Date: 2026-07-19
Status: complete in phase commit `dcf600db`; automated and review gates GREEN
Baseline commit: `5067903d`
Branch distance before the phase commit: 5 ahead, 6 behind

## Outcome

P5 replaces the Database and Analysis placeholders with source-checkout product
slices over ChemSmart's structured domain APIs. No screen parses formatted CLI
text, launches Gaussian/ORCA/xTB, submits HPC work, or implicitly writes grouping,
DIAS, WBI, thermochemistry, or plot output files.

- Database provides Browse, Build database, and Export tabs. Browse is read-only
  and supports real parameterized query syntax, bounded result pages, structured
  detail, explicit empty/error/retry states, and the shared 3D structure viewer.
  Build and Export are explicit create-new operations over the existing
  `SingleFileAssembler`, `Database`, and `DatabaseExporter` APIs; they never
  update or overwrite an existing file.
- Analysis provides independently controlled Thermochemistry, Grouper, and
  DIAS/WBI tabs. Each validates before dispatch, runs through the common task
  controller, reports honest determinate or indeterminate progress, supports
  cooperative cancellation and retry, and returns typed result tables.
- The desktop v1 agent registry and real-compute boundary are unchanged.

## Database evidence

The fixed fixture contains exactly 47 records, 33 molecules, and 314 structures.
For all three targets, desktop rows, counts, IDs, details, and geometry map from
`DatabaseQuery` and `DatabaseInspector`; formatted terminal output is never
parsed. Pages are limited to 500 rows. Detail values are bounded for display,
and structures are translated to the existing viewer DTO.

`DatabaseQuery` now accepts an optional cancellation callback. When supplied,
SQLite's progress handler interrupts an active statement and re-raises the
original task cancellation. Default CLI callers are unchanged. A direct domain
test proves cancellation occurs inside a statement, not only before/after it.

The UI clearly states that browsing never changes the database. Invalid schemas,
missing files, malformed filters, empty results, repeated queries, target
switches, selection drift, cancellation, retry, and worker drain are covered.
Retry rebuilds the request from the current file, target, filter, and limit only
after the prior worker thread has fully drained; it never silently replays a
captured stale request.

Build discovers Gaussian and ORCA outputs through `BaseFolder`, supports all or
final structures, and keeps abnormal calculations excluded unless the researcher
turns on the explicit partial-calculation option. The default batch policy is
fail-closed: parser exceptions and normally terminated files without molecular
structures abort with no destination. A separate partial-batch toggle can admit
other valid records while listing each failed basename in the receipt. Inputs
are bounded to 2,000 files and 2 GiB, source symlinks/out-of-root paths are
rejected, and the optional Open Babel requirement is surfaced without installing
or modifying the environment. ORCA `xyzfile` single-point outputs are treated as
two-source records: their referenced coordinate file must be a regular,
non-symlink file inside the selected root and counts toward both bounds. Parent
traversal, missing files, symlink components, and parsing-time mutation fail
closed before staging. The dependency path, SHA-256, and byte size are persisted
in record provenance, survive database read-back, and are summarized in the UI
receipt. This also corrected the shared ORCA all/final selection path so a valid
external single-point geometry is assembled as the calculation's sole structure.
The ORCA output then overwrites the XYZ comment's potentially stale energy and
supplies charge, multiplicity, final SP energy, frozen atoms, and available
force/spectroscopic metadata before any `structure_id` is computed. A synthetic
charged doublet built from the characterized fixture proves electronic-state
identity, DB read-back, and XYZ re-export use the ORCA result
(`-4380.167450201429 Eh`) rather than the coordinate file's prior energy
(`-4379.227445 Eh`).

Build writes all records in one transaction to a same-directory private staging
database, then verifies record counts, `PRAGMA integrity_check`, foreign keys,
schema, file type, size, and SHA-256. Export uses the same domain validator as the
CLI for JSON/CSV whole-database and XYZ/extXYZ selection semantics, resolves
method/basis through the database, validates the staged output by format, hashes
it, and only then publishes it. Publishing uses an fsynced hard link with
`EEXIST` fail-closed semantics, so repeated or concurrent tasks cannot overwrite
researcher data. Broken/valid destination symlinks are treated as existing.
The domain exporter returns structured requested/exported/skipped-frame metadata.
The fixed molecule-ID fixture proves both explicit-method XYZ and automatically
selected-force extXYZ consider seven structures, export four, and receipt the
three omitted full structure IDs; the UI bounds their display with an exact
remaining count rather than implying a complete conformer export.

Cancellation is checked before and between the Gaussian/ORCA discovery passes,
per file around parsing, and at transaction/export boundaries. A recursive
folder scan, one third-party parser call, and one export writer call have no inner
callback and therefore remain honestly indeterminate/non-interruptible until the
call returns; the 2,000-file/2-GiB bounds are applied immediately after discovery.
The final publish runs inside the shared task controller's irreversible commit
seal. Cancel or timeout before the seal wins and leaves no output; cancel or
timeout after the seal is rejected so a published file can never be reported as
cancelled. Build and Export retry reconstruct the current controls only after all
workers drain. Build and JSON export prominently warn that provenance includes
original source-file paths, including referenced geometry paths.

A final repeated-start stress run exposed a PySide signal-registration mutex
stall when many superseded QThreads were created while older workers were being
deleted. `QtTaskController` now keeps only the latest pending generation, drains
the active worker completely, and then starts the pending worker, bounding each
controller to one active QThread. A lifecycle regression freezes
`old-start -> old-drained -> current-start`; 40 rapid start/cancel cycles and the
complete GUI suite finish without leaked threads or the former stall.

## Analysis evidence

Thermochemistry maps the existing unnamed nine-value domain tuple into named
fields and units without copying formulas. It covers Gaussian/ORCA outputs,
single and bounded batch operation, natural-abundance masses, concentration,
imaginary-frequency policy, Grimme/Truhlar entropy correction, Head-Gordon
enthalpy correction, qRRHO alpha, and Gibbs/electronic Boltzmann weighting.

Grouper preserves the complete 11-strategy inventory. Nine strategies are
immediately available in the current native environment. Optional iRMSD is
enabled only when its executable is found by a nonblocking availability probe;
PyMOL remains visibly disabled until P6's separately cancellable
optional-process boundary. Domain groupers gained
default-preserving optional no-output, progress, and cancellation hooks. The CLI
default still records results. Pairwise strategies report real comparison
progress; the characterized 18-conformer RMSD fixture performs 153 comparisons
and returns 12 groups at threshold 0.5 with no output files.

The screen now exposes the domain's exact strategy semantics: RMSD-family
thresholds are in Å, Energy uses kcal/mol, Tanimoto similarity and TFD deviation
are dimensionless, and the iRMSD default is 0.125 Å. iRMSD inversion uses the
real `auto/on/off` contract. Unsupported ignore-hydrogen state is cleared and
rejected at the typed request boundary. Retry reconstructs all three analysis
requests from current controls, and a new Grouper run clears stale 3D preview
state before dispatch.

SpyRMSD previously depended on a temporary XYZ reload that failed with the
installed RDKit backend. It now converts the existing `Molecule` through its
tested RDKit representation, including hydrogen-removal semantics, and retains
the established RMSD values. Seven skips in the Grouper/Thermochemistry run are
explicit optional/external boundaries, including unavailable PyMOL; they are not
reported as passes.

DIAS calls `GaussianDIASLogFolder` or `ORCADIASOutFolder` directly and returns
reaction coordinate, total, distortion, and interaction energies in Å and
kcal/mol. The fixed ORCA folder yields three characterized points. Execution
found two shared-domain defects: ORCA single-point output always entered the
optimization branch and its DIAS energy reader asked a `Molecule` for an output
property. The parser now distinguishes an empty optimization section, resolves
the sibling `xyzfile` case-insensitively relative to the output, and DIAS reads
`ORCAOutput.final_energy`. Direct and desktop regression tests freeze the
coordinates and all three energy series, including minimum referencing.
Minimum referencing keeps distortion unchanged and shifts total and interaction
by the same offset, so `total = distortion + interaction` remains true at every
point. The UI describes this reference convention explicitly.

The WBI-named legacy script actually exposes Gaussian NBO Natural Population
Analysis and Natural Atomic Orbital properties, not a parsed Wiberg bond-index
matrix. The UI states this boundary explicitly. Typed rows include atom label and
index, natural charge, core/valence/Rydberg/total electrons, NAO count and total
occupancy, and electronic configuration. The 128-atom fixture freezes NBO 3.1,
Ni1/C100 charges, NAO counts, occupancy, and atom filters. Missing tables,
missing indices, duplicate filters, ranges, repeated calls, and cancellation
during atom mapping fail closed. A Natural Population Analysis without a Natural
Atomic Orbital table is rejected rather than reported as plausible zero NAOs,
and atom ranges are bounded before expansion so an input such as
`1-1000000000` cannot freeze or exhaust the UI process.

## Visual and interaction evidence

Fresh offscreen inspection at the 720 x 520 minimum window kept every analysis
result region visible with at least 70 px height. Thermochemistry, Grouper, and
DIAS/WBI retain their primary action, status, progress/cancel/retry state, and
result table inside the screen. Full light/dark/increased-contrast, keyboard,
screen-reader, and rendered screenshot acceptance remain P6 gates.

A second 720 x 520 Database render after the Build/Export expansion found and
removed compressed, overlapping form rows. Browse, Build database, and Export
now use independent vertical scroll areas; Browse results and the Build primary
action remain visible, while the dense Export form requires one short scroll to
its action at the minimum size. This is recorded as a P6 density/action-placement
refinement rather than hiding fields or shrinking their touch targets.

Database selection and Grouper representatives reuse the same lazily initialized
integrity-checked 3Dmol viewer. Database build/export receipts name source,
destination, counts or scope, bytes, SHA-256, verification/publish policy, partial
records, and JSON privacy. Analysis receipts name the input scope, domain result,
units/program, and no-write boundary without exposing raw exception or provider
payloads.

## Stress and validation receipts

- Database task/service/UI atomic-publish and interaction slice, including all
  four export formats, real and mocked assembly, bounds, malformed input,
  no-overwrite, symlink, cancellation, retry, stale selection, and concurrent
  exactly-once publication, together with the Analysis/task slice:
  `103 passed, 1 skipped in 3.87s`.
- Complete Database domain suite plus a real Gaussian+ORCA desktop assembly
  round trip in the `chemsmart` environment, which contains the established Open
  Babel dependency: `53 passed` (`52 passed in 2.55s` for the domain suite plus
  `1 passed in 0.88s` for the desktop round-trip test).
- Grouper plus Thermochemistry domain suites:
  `108 passed, 7 skipped, 45 warnings in 25.69s`.
- Complete ORCA parser suite: `63 passed in 7.94s`.
- Complete GUI preservation suite:
  `308 passed, 1 skipped in 90.37s`.
- Complete Agent preservation suite:
  `1110 passed, 6 warnings in 53.89s`.
- Changed-file Black/isort/Ruff, Python compilation, diff check, and the feature
  contract's 18 unique surfaces are GREEN in the current review run.

Running the complete Database domain suite with the base GUI Python exposed the
known absence of Open Babel in that interpreter. The same suite passed in the
project's Open-Babel-capable `chemsmart` environment. No dependency was installed
or modified, and the environment failure is not counted as a product regression.

## P1 packaging evidence refreshed during P5

With explicit user authorization, fork ref `codex/p1-macos-packaging-spike` was
confirmed, manual run `29668168830` executed `candidate=both`, and all three
artifacts were downloaded and independently audited. PyInstaller is GREEN on all
18 gates. pyside6-deploy is RED after successful compilation because its strict
normalizer rejects the exact generated 19-byte `Contents/MacOS/qt6.conf`.

The bounded exact-payload normalizer amendment is documented for P7, but another
remote run requires new authorization. The selected production path remains
PyInstaller. The temporary ad-hoc artifact is not a release candidate.

## Deferred boundaries

- Optional PyMOL rendering, full Apple-design review, keyboard-only and
  screen-reader acceptance, appearance matrices, and user-facing help belong to
  P6.
- No Database legacy migrator exists in the current CLI, library, or inspected
  history. Schema mismatch continues to instruct the researcher to reassemble;
  a fictional migration command is therefore explicitly N/A rather than silently
  implemented.
- Updating an existing database and overwriting an export are not supported by
  the desktop. The bounded v1 operations create a new atomic output only. Open
  Babel remains required for real molecular identity assembly and is a P7 bundle
  dependency gate, not something P5 installs on the host.
- DIAS plot/data writers and the legacy WBI logger remain available outside the
  GUI; the desktop structured result paths deliberately do not call them.
- Finder launch, `.dmg`, current-product PyInstaller integration, Developer ID,
  hardened runtime, notarization, maintained-builder, clean-machine use,
  upgrade/uninstall, and final Computer Use scenarios remain P7 gates.
- No provider key, `api.env`, real calculation executable, scheduler, or remote
  service was read or invoked for P5.
- Dependency device/inode/size/time/hash is checked before and after parsing,
  which detects persistent and observable local mutation. P5 does not create an
  immutable private snapshot for parsing and therefore does not claim protection
  against an adversary that changes a file transiently and restores exact bytes
  and metadata; snapshot/file-descriptor hardening remains a P7 candidate.

## Independent review verdict

Final read-only review: **GREEN — Critical 0, High 0; P5 phase commit allowed.**
The reviewer confirmed indirect ORCA path and symlink controls, dependency bounds
and provenance, charged/open-shell structure identity and energy re-export,
additive v1 schema compatibility, legacy CLI soft-fail preservation, and the
receipt counts above.
