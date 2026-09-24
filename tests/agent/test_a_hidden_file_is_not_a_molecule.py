"""A hidden file in the workspace is never admitted as a molecule.

macOS tar writes a ``._<name>`` AppleDouble sidecar beside every file it
copies. The master's R10 smoke goal (CUHK Slurm 2150189) staged
``formaldehyde.xyz`` that way, the workspace scan admitted the sidecar
``._formaldehyde.xyz`` as a geometry, and the goal settled returned_to_human
before any session ran: "workspace XYZ has a malformed atom count". What a
human places as a molecule is never hidden; a dotfile, or anything inside a
dot-directory, is left there by an operating system or a tool.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent.live_session import _scan_xyz_artifacts

_FORMALDEHYDE = (
    "4\nformaldehyde\nC 0.0 0.0 0.0\nO 0.0 0.0 1.2\n"
    "H 0.0 0.94 -0.54\nH 0.0 -0.94 -0.54\n"
)
#: The head of the sidecar macOS tar wrote for that file on this platform
#: (magic 0x00051607, version 2, "Mac OS X", two entries).
_APPLEDOUBLE = (
    b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        \x00\x02"
    b"\x00\x00\x00\t\x00\x00\x002\x00\x00\x00\xa4\x00\x00\x00\x02"
    b"\x00\x00\x00\xd6" + b"\x00" * 28 + b"ATTR"
)


@pytest.mark.capability("tool:bind_scientific_identity")
def test_an_appledouble_sidecar_is_not_scanned(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "formaldehyde.xyz").write_text(_FORMALDEHYDE)
    (workspace / "._formaldehyde.xyz").write_bytes(_APPLEDOUBLE)

    admitted = _scan_xyz_artifacts(workspace.resolve())

    assert [Path(item.artifact.path).name for item in admitted] == [
        "formaldehyde.xyz"
    ]
    assert admitted[0].atom_count == 4
