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
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
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


def _new_web_view():
    """Construct the default owned WebEngine view behind a test seam."""
    from PySide6.QtWebEngineWidgets import QWebEngineView

    return QWebEngineView()


def pymol_available() -> bool:
    """True when a ``pymol`` executable is discoverable on PATH."""
    from chemsmart.gui.services.pymol_render_service import (
        discover_pymol_executable,
    )

    return discover_pymol_executable() is not None


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
        raise ValueError(
            "3D viewer background must be a six-digit hex colour."
        )

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

    def __init__(self, parent=None, pymol_service=None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Molecular structure viewer")
        self._molecule = None
        self._source_path: Path | None = None
        self._pymol_pixmap = QPixmap()

        from chemsmart.gui.application.task_controller import QtTaskController
        from chemsmart.gui.services.pymol_render_service import (
            PyMOLRenderService,
        )

        self._pymol_service = pymol_service or PyMOLRenderService()
        self._pymol_controller = QtTaskController(self)
        self._pymol_controller.state_changed.connect(self._on_pymol_state)
        self._pymol_controller.progress_changed.connect(
            lambda progress: (
                self.pymol_status.setText(progress.message)
                if progress.message
                else None
            )
        )
        self._pymol_controller.succeeded.connect(self._on_pymol_result)
        self._pymol_controller.failed.connect(self._on_pymol_failure)
        self._pymol_controller.cancelled.connect(self._on_pymol_cancelled)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        toggle = QHBoxLayout()
        self.interactive_button = QPushButton("3D")
        self.interactive_button.setCheckable(True)
        self.interactive_button.setChecked(True)
        self.interactive_button.setAccessibleName("Interactive 3D viewer")
        self.interactive_button.setToolTip("Interactive 3D molecule viewer")
        self.interactive_button.clicked.connect(
            lambda: self._set_mode("interactive")
        )
        self.render_button = QPushButton("PyMOL")
        self.render_button.setCheckable(True)
        self.render_button.setAccessibleName("Render with PyMOL")
        self.render_button.setAccessibleDescription(
            "Runs the optional local PyMOL executable in a cancellable isolated "
            "process. The interactive 3D viewer remains the default."
        )
        self.render_button.setToolTip(
            "Render with the Zhang Lab PyMOL style"
            if self._pymol_service.available
            else "PyMOL is not available on PATH; interactive 3D remains available."
        )
        self.render_button.setEnabled(self._pymol_service.available)
        self.render_button.clicked.connect(lambda: self._set_mode("pymol"))
        toggle.addWidget(self.interactive_button)
        toggle.addWidget(self.render_button)
        toggle.addStretch(1)
        root.addLayout(toggle)

        self.stack = QStackedWidget()
        self._interactive = self._build_interactive()
        self._pymol_panel = self._build_pymol_panel()
        self.stack.addWidget(self._interactive)
        self.stack.addWidget(self._pymol_panel)
        root.addWidget(self.stack, stretch=1)

    # -- public API ----------------------------------------------------- #

    def load_molecule(self, molecule, source_path: str | Path | None = None):
        """Show ``molecule`` (a chemsmart ``Molecule``) in the active mode."""
        self._molecule = molecule
        self._source_path = Path(source_path) if source_path else None
        self._refresh()

    def clear_molecule(self) -> None:
        """Remove stale structure state before a new source is accepted."""
        if self._molecule is None and self._source_path is None:
            return
        self._molecule = None
        self._source_path = None
        self._pymol_controller.cancel()
        self._pymol_pixmap = QPixmap()
        self.pymol_image.clear()
        if self._web is not None:
            from chemsmart.gui import theme

            palette = theme.palette_for()
            self._web.setHtml(
                "<!doctype html><html><body style='margin:0;display:flex;"
                "align-items:center;justify-content:center;height:100%;"
                f"background:{palette.surface_2};color:{palette.text_muted};"
                "font:13px -apple-system'>Select a molecule source to preview "
                "its 3D structure.</body></html>"
            )
        self.pymol_status.setText(
            "PyMOL is not available; use the interactive 3D viewer."
            if not self._pymol_service.available
            else "Select a molecule, then choose PyMOL to render it."
        )

    # -- internals ------------------------------------------------------ #

    def _build_interactive(self) -> QWidget:
        if _webengine_available():
            self._web = _new_web_view()
            self._web.setAccessibleName("Interactive 3D molecular structure")
            self._web.setAccessibleDescription(
                "Rotate and zoom the selected molecular geometry."
            )
            from chemsmart.gui import theme

            palette = theme.palette_for()
            self._web.setHtml(
                "<!doctype html><html><body style='margin:0;display:flex;"
                "align-items:center;justify-content:center;height:100%;"
                f"background:{palette.surface_2};color:{palette.text_muted};"
                "font:13px -apple-system'>Select a molecule source to preview "
                "its 3D structure.</body></html>"
            )
            return self._web
        # Fallback when QtWebEngine could not be bundled (plan Phase 0 note).
        self._web = None
        fallback = QLabel(
            "3D viewer unavailable (QtWebEngine not installed).",
            objectName="ScreenSubtitle",
        )
        fallback.setAccessibleName("Interactive 3D viewer unavailable")
        return fallback

    def _build_pymol_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.pymol_image = QLabel()
        self.pymol_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pymol_image.setAccessibleName("PyMOL rendered molecule image")
        self.pymol_status = QLabel(
            (
                "Select a molecule, then choose PyMOL to render it."
                if self._pymol_service.available
                else "PyMOL is not available; use the interactive 3D viewer."
            ),
            objectName="ScreenSubtitle",
        )
        self.pymol_status.setWordWrap(True)
        self.pymol_status.setAccessibleName("PyMOL render status")
        self.pymol_progress = QProgressBar()
        self.pymol_progress.setRange(0, 0)
        self.pymol_progress.setTextVisible(False)
        self.pymol_progress.setAccessibleName("PyMOL render progress")
        self.pymol_progress.setVisible(False)
        actions = QHBoxLayout()
        self.pymol_cancel = QPushButton("Cancel render")
        self.pymol_cancel.setAccessibleName("Cancel PyMOL render")
        self.pymol_cancel.setVisible(False)
        self.pymol_cancel.clicked.connect(self._pymol_controller.cancel)
        self.pymol_retry = QPushButton("Retry render")
        self.pymol_retry.setAccessibleName("Retry PyMOL render")
        self.pymol_retry.setVisible(False)
        self.pymol_retry.clicked.connect(self._start_pymol_render)
        actions.addWidget(self.pymol_cancel)
        actions.addWidget(self.pymol_retry)
        actions.addStretch(1)
        layout.addWidget(self.pymol_image, stretch=1)
        layout.addWidget(self.pymol_status)
        layout.addWidget(self.pymol_progress)
        layout.addLayout(actions)
        return panel

    def _set_mode(self, mode: str) -> None:
        if mode == "pymol" and not self._pymol_service.available:
            mode = "interactive"
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
            self._start_pymol_render()

    def _start_pymol_render(self) -> None:
        if not self._pymol_service.available:
            self.pymol_status.setText(
                "PyMOL is not available; use the interactive 3D viewer."
            )
            return
        if self._molecule is None:
            self.pymol_status.setText("Select a molecule before rendering.")
            return
        molecule = self._molecule
        # Never show a prior molecule while a new render is pending. A stale
        # image beside a current status would be scientifically misleading.
        self._pymol_pixmap = QPixmap()
        self.pymol_image.clear()
        self.pymol_status.setText(
            "Starting PyMOL render for selected molecule…"
        )
        self.pymol_retry.setVisible(False)
        self._pymol_controller.start(
            lambda context: self._pymol_service.render(molecule, context),
            timeout_ms=120_000,
        )

    def _on_pymol_state(self, snapshot) -> None:
        from chemsmart.gui.application.task_controller import TaskStatus

        active = snapshot.status in {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
        }
        self.pymol_progress.setVisible(active)
        self.pymol_cancel.setVisible(active)
        self.render_button.setEnabled(
            self._pymol_service.available and not active
        )

    def _on_pymol_result(self, result) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(result.png_bytes, "PNG"):
            self._pymol_pixmap = QPixmap()
            self.pymol_image.clear()
            self.pymol_status.setText(
                "PyMOL returned an image that Qt could not display."
            )
            self.pymol_retry.setVisible(True)
            return
        self._pymol_pixmap = pixmap
        self._scale_pymol_image()
        self.pymol_status.setText(
            f"PyMOL render verified · SHA-256 {result.sha256[:12]}…"
        )

    def _on_pymol_failure(self, failure) -> None:
        self._pymol_pixmap = QPixmap()
        self.pymol_image.clear()
        self.pymol_status.setText(
            "PyMOL rendering failed "
            f"({failure.diagnostic_type}). Check the local PyMOL installation."
        )
        self.pymol_retry.setVisible(True)

    def _on_pymol_cancelled(self) -> None:
        self.pymol_status.setText(
            "PyMOL rendering cancelled; no image was accepted."
        )
        self.pymol_retry.setVisible(True)

    def _scale_pymol_image(self) -> None:
        if self._pymol_pixmap.isNull():
            return
        target = self.pymol_image.size()
        self.pymol_image.setPixmap(
            self._pymol_pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_pymol_image()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        if not self.prepare_shutdown(timeout_ms):
            return False
        self.finalize_shutdown()
        return True

    def prepare_shutdown(self, timeout_ms: int = 1000) -> bool:
        """Drain mutable work without destroying the still-visible viewer."""
        return self._pymol_controller.shutdown(timeout_ms)

    def finalize_shutdown(self) -> None:
        """Release WebEngine only after every window participant drained."""
        self._release_web_view()

    def _release_web_view(self) -> None:
        """Stop and destroy the owned WebEngine page before the app can quit.

        ``QWebEngineView`` owns the page it creates by default.  Explicitly
        scheduling both objects makes the renderer boundary visible and keeps
        this teardown idempotent.  Deletion remains deferred because shutdown
        can be requested from a WebEngine callback; destroying the C++ objects
        synchronously from that callback is unsafe.
        """
        web = self._web
        if web is None:
            return
        self._web = None

        stop = getattr(web, "stop", None)
        if callable(stop):
            stop()
        page = web.page()
        if page is not None:
            page.deleteLater()
        if self.stack.indexOf(web) >= 0:
            self.stack.removeWidget(web)
        web.hide()
        web.setParent(None)
        web.deleteLater()

    def set_pymol_service(self, service) -> None:
        """Apply a validated optional renderer after draining the old one."""
        if self._pymol_controller.active_thread_count:
            self._pymol_controller.cancel()
            raise RuntimeError(
                "The existing PyMOL render is still stopping; try again."
            )
        self._pymol_service = service
        available = service.available
        self.render_button.setEnabled(available)
        self.render_button.setToolTip(
            "Render with the Zhang Lab PyMOL style"
            if available
            else "PyMOL is not available on PATH; interactive 3D remains available."
        )
        if not available and self.stack.currentWidget() is self._pymol_panel:
            self._set_mode("interactive")
        self._pymol_pixmap = QPixmap()
        self.pymol_image.clear()
        self.pymol_status.setText(
            f"PyMOL ready: {service.executable}"
            if available
            else "PyMOL is not available; use the interactive 3D viewer."
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
