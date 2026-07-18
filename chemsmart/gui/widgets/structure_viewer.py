"""Shared 3D molecular structure viewer (plan Phase 1 design decision).

Hybrid, PyMOL-as-hero:

- **Interactive mode (default)** — a lightweight molecular viewer (3Dmol.js)
  embedded in a ``QWebEngineView`` for smooth rotate/zoom during job building.
  Input geometry is produced by the existing ``Molecule.write_xyz()`` /
  ``to_pdb()`` — no new export code.
- **PyMOL render mode (publication)** — shells out to the existing
  ``MolJobRunner`` (headless PyMOL + the lab ``zhang_group_pymol_style.py``
  style) to produce a PNG, preserving the lab's visual identity.

PyMOL is *not* embedded in-process (its own Qt would clash with PySide6); it is
used only as the subprocess renderer it already is. Both dependencies degrade
gracefully: if QtWebEngine is unavailable the interactive mode falls back to a
message, and if ``pymol`` is not on PATH the render mode is disabled.

This one widget is reused by Job builder, run preview, and the Database
browser (principle #10).
"""

from __future__ import annotations

import base64
import re
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


def _webengine_available() -> bool:
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401

        return True
    except Exception:
        return False


def pymol_available() -> bool:
    """True when a ``pymol`` executable is discoverable on PATH."""
    return shutil.which("pymol") is not None or shutil.which("pymol.exe") is not None


_HTML_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<script>{threedmol_javascript}</script>
<style>html,body{{margin:0;height:100%;background:{bg}}}#v{{width:100%;height:100%}}</style>
</head><body><div id="v"></div>
<script>
  const decodeUtf8 = (encoded) => {{
    const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }};
  const viewer = $3Dmol.createViewer("v", {{backgroundColor: "{bg}"}});
  const model = viewer.addModel(decodeUtf8("{data_b64}"), decodeUtf8("{fmt_b64}"));
  window.__chemsmartAtomCount = model.selectedAtoms({{}}).length;
  viewer.setStyle({{}}, {{stick:{{}}, sphere:{{scale:0.25}}}});
  viewer.zoomTo();
  viewer.render();
</script></body></html>"""


def build_3dmol_html(data: str, background: str, fmt: str = "xyz") -> str:
    """Build a fully offline 3Dmol document from an integrity-checked asset."""
    from chemsmart.gui.resources import read_threedmol_javascript

    if not re.fullmatch(r"#[0-9a-fA-F]{6}", background):
        raise ValueError("3D viewer background must be a six-digit hex colour.")

    def encode(value: str) -> str:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    return _HTML_TEMPLATE.format(
        threedmol_javascript=read_threedmol_javascript(),
        bg=background,
        data_b64=encode(data),
        fmt_b64=encode(fmt),
    )


class StructureViewer(QWidget):
    """Segmented Interactive / PyMOL viewer over a chemsmart ``Molecule``."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._molecule = None
        self._source_path: Path | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        toggle = QHBoxLayout()
        self.interactive_button = QPushButton("Interactive")
        self.interactive_button.setCheckable(True)
        self.interactive_button.setChecked(True)
        self.interactive_button.clicked.connect(
            lambda: self._set_mode("interactive")
        )
        self.render_button = QPushButton("PyMOL render")
        self.render_button.setCheckable(True)
        self.render_button.setEnabled(pymol_available())
        self.render_button.clicked.connect(lambda: self._set_mode("pymol"))
        toggle.addWidget(self.interactive_button)
        toggle.addWidget(self.render_button)
        toggle.addStretch(1)
        root.addLayout(toggle)

        self.stack = QStackedWidget()
        self._interactive = self._build_interactive()
        self._pymol_panel = QLabel(
            "Render with the lab PyMOL style.", objectName="ScreenSubtitle"
        )
        self.stack.addWidget(self._interactive)
        self.stack.addWidget(self._pymol_panel)
        root.addWidget(self.stack, stretch=1)

    # -- public API ----------------------------------------------------- #

    def load_molecule(self, molecule, source_path: str | Path | None = None):
        """Show ``molecule`` (a chemsmart ``Molecule``) in the active mode."""
        self._molecule = molecule
        self._source_path = Path(source_path) if source_path else None
        self._refresh()

    # -- internals ------------------------------------------------------ #

    def _build_interactive(self) -> QWidget:
        if _webengine_available():
            from PySide6.QtWebEngineWidgets import QWebEngineView

            self._web = QWebEngineView()
            return self._web
        # Fallback when QtWebEngine could not be bundled (plan Phase 0 note).
        self._web = None
        return QLabel(
            "3D viewer unavailable (QtWebEngine not installed).",
            objectName="ScreenSubtitle",
        )

    def _set_mode(self, mode: str) -> None:
        self.interactive_button.setChecked(mode == "interactive")
        self.render_button.setChecked(mode == "pymol")
        self.stack.setCurrentWidget(
            self._interactive if mode == "interactive" else self._pymol_panel
        )
        self._refresh()

    def _refresh(self) -> None:
        if self._molecule is None:
            return
        if self.stack.currentWidget() is self._interactive and self._web:
            self._render_interactive()
        elif self.stack.currentWidget() is self._pymol_panel:
            # PyMOL render runs on a worker in the job screen; the panel here
            # displays the resulting PNG. Wiring lands with Phase 5 mol work.
            self._pymol_panel.setText(
                "PyMOL render pending — run to generate the lab-style image."
                if pymol_available()
                else "PyMOL not found on PATH; render mode disabled."
            )

    def _render_interactive(self) -> None:
        from chemsmart.gui import theme

        try:
            xyz = self._molecule.write_xyz  # noqa: F841 - existence check
            data = self._molecule_to_xyz_string()
            fmt = "xyz"
        except Exception:
            data, fmt = "", "xyz"

        bg = theme.palette_for().surface_2
        html = build_3dmol_html(data, bg, fmt)
        self._web.setHtml(html)

    def _molecule_to_xyz_string(self) -> str:
        """Serialize the molecule to an XYZ string via the existing writer."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            "w+", suffix=".xyz", delete=False
        ) as handle:
            path = Path(handle.name)
        self._molecule.write_xyz(str(path), mode="w")
        text = path.read_text(encoding="utf-8")
        path.unlink(missing_ok=True)
        return text
