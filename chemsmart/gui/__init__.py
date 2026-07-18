"""ChemSmart native desktop GUI (PySide6/Qt).

A tool-first desktop front-end over the existing ``chemsmart`` CLI and agent
runtime. It coexists with the Textual TUI under :mod:`chemsmart.agent.tui`;
neither replaces the other. The GUI drives the same in-process
:class:`~chemsmart.agent.core.AgentSession`, the same CLI schema, and the same
``~/.chemsmart`` configuration, so GUI-, TUI-, and CLI-authored work is
interchangeable.

Design north star: CDS (Claude Design System) restraint + Codex density.
See the approved plan for the full principle list. Heavy scientific
dependencies (rdkit, pymatgen) are imported lazily by the screens that need
them, mirroring the CLI's ``DeferredGroup`` discipline — importing this
package must stay cheap.
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """Console-script entry point (``chemsmart-gui``).

    Thin re-export so ``[project.gui-scripts]`` and ``python -m chemsmart.gui``
    share one implementation.
    """
    from chemsmart.gui.__main__ import main as _main

    return _main()
