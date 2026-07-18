"""Background workers and library-facade services for the GUI.

Services wrap the existing chemsmart library APIs (agent core, CLI schema,
database, grouper, thermochemistry) and run blocking work on ``QThread``
workers so the UI thread never stalls (mirrors the TUI's threaded-worker
pattern). Screens talk to services, never to the CLI as a subprocess for
library-callable work.
"""
