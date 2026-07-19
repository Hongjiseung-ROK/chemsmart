# ChemSmart macOS internal alpha

This guide applies only to the arm64, macOS 14-or-newer internal alpha. The
application is ad-hoc signed for controlled Zhang Lab evaluation. It is not a
Developer ID signed or notarized public release.

## Verify and install

Keep the downloaded DMG, `SHA256SUMS.txt`, CycloneDX SBOM, release receipt, and
README in the same folder. In Terminal, change to that folder and run:

```console
shasum -a 256 -c SHA256SUMS.txt
```

Every entry must report `OK`. Open the DMG and drag `ChemSmart.app` to its
Applications shortcut. In Applications, Control-click ChemSmart and choose
Open. If macOS still blocks it, open System Settings > Privacy & Security and
choose Open Anyway for ChemSmart. Do not disable Gatekeeper globally and do not
remove quarantine attributes with a shell command.

The first launch creates missing templates under `~/.chemsmart` without editing
shell startup files. AI configuration is optional. The Job builder, Database,
Analysis, and offline 3D viewer remain usable without a provider.

## Upgrade

Quit ChemSmart and copy the newer app from its verified DMG into Applications.
When Finder asks, choose Replace. Existing project files, `~/.chemsmart`
configuration, agent sessions, and macOS preferences are retained. Reopen the
app and confirm its version in About ChemSmart before removing the previous DMG.

Do not merge configuration templates by deleting `~/.chemsmart`. ChemSmart
adds missing templates without overwriting user-owned project configuration.

## Remove

Quit ChemSmart and move `/Applications/ChemSmart.app` to the Trash. That removes
the application but intentionally retains research configuration and sessions.

Optional user-data removal is a separate, destructive decision. Back up any
project YAML, provider configuration, and agent receipts first. Then remove only
the confirmed ChemSmart locations:

- `~/.chemsmart` for configuration and agent sessions;
- `~/Library/Logs/ChemSmart` for rotating desktop diagnostic logs;
- `~/Library/Preferences/com.ZhangLab.ChemSmart.plist` for desktop preferences.

Credentials referenced by ChemSmart may remain in macOS Keychain. Review and
remove them in Keychain Access; never use a broad Keychain deletion command.

## Internal-alpha limits

- The desktop enforces fake/no-scratch input generation. It does not run
  Gaussian, ORCA, or xTB calculations or submit HPC jobs.
- Optional PyMOL must be selected in Settings. Offline 3Dmol remains the default.
- Gatekeeper rejection is expected until Developer ID signing, hardened runtime,
  notarization, and stapling are completed as a separate release gate.
- Report the release-receipt filename, source SHA, macOS version, Mac model, and
  exact visible error. Do not send API keys, provider payloads, or unreviewed
  project data.

## Create a support bundle

Choose Help > Create Support Bundle, select a new ZIP filename, and wait for the
confirmation. ChemSmart includes at most four recent rotating desktop logs,
bounds each log to 256 KiB and the total to 1 MiB, replaces the home-directory
prefix, and redacts common provider-key, token, password, authorization, and
secret-assignment forms. It excludes configuration contents, project files,
provider request/response payloads, session transcripts, and Keychain data.

Open and review the ZIP before sharing it. The manifest reports exactly how many
logs and redactions were included. If the visible issue involves research data,
send the minimum separately reviewed fixture rather than adding a project folder
to the support ZIP.
