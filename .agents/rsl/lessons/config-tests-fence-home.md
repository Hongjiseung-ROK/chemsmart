---
id: config-tests-fence-home
paths:
  - "chemsmart/cli/config.py"
  - "chemsmart/settings/**"
  - "tests/test_config*.py"
conditions: "macOS developer host with a real ~/.chemsmart; the `chemsmart config` command before b78f5bec ignored CHEMSMART_CONFIG_DIR"
evidence:
  - "commit:b78f5bec"
  - "file:tests/test_config.py#the first run of this very test rewrote the real"
repeat_cost: "the developer host's real ~/.chemsmart/server files were overwritten by a test's first run and restored by hand"
falsifier: "retire when tests/conftest.py fences HOME and Path.home for every test; wrong if a config-writing command cannot reach the real home even when its override handling is broken"
home: prose
supersedes: []
earned: 2026-09-21
last_verified: "2026-09-24 @ 986bdb56"
---
A test of a command that writes configuration fences both the HOME variable and Path.home to a temporary directory before its first run.
A witness for "the command honours its override" is red exactly when the command ignores the override, and in that state it writes wherever the real home points; setting CHEMSMART_CONFIG_DIR alone is not a fence.
Evidence: b78f5bec; the first run of TestConfigureAProgramFolder rewrote the real ~/.chemsmart/server.
