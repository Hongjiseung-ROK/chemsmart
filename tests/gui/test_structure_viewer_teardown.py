"""Teardown contracts for the shared 3D structure viewer.

Regression cover for the frozen-build High issue: a packaged Quit removed the
window but left the main process and a QtWebEngine renderer alive. The viewer's
``shutdown`` previously drained only the optional PyMOL controller, so the
``QWebEngineView`` — and therefore its Chromium renderer process — was never
released while the event loop was still running.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from PySide6.QtWidgets import QWidget


class _StubWebView(QWidget):
    """Records the teardown calls a real ``QWebEngineView`` would need."""

    def __init__(self) -> None:
        super().__init__()
        self.page_deleted = False
        self.deleted = False
        self.parent_cleared = False
        self.html = ""

    # -- the subset StructureViewer touches -- #
    def setAccessibleName(self, _name) -> None:
        return None

    def setAccessibleDescription(self, _description) -> None:
        return None

    def setHtml(self, html) -> None:
        self.html = html

    def page(self):
        stub = self

        class _Page:
            def deleteLater(self_inner) -> None:
                stub.page_deleted = True

        return _Page()

    def setParent(self, parent) -> None:
        if parent is None:
            self.parent_cleared = True

    def deleteLater(self) -> None:
        self.deleted = True


def _viewer_with_stub_web(monkeypatch):
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    stub = _StubWebView()
    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: True)
    monkeypatch.setattr(
        viewer_module,
        "_new_web_view",
        lambda: stub,
        raising=False,
    )

    class _Service:
        available = False

    viewer = viewer_module.StructureViewer(pymol_service=_Service())
    return viewer, stub


def test_shutdown_releases_the_web_engine_view(qapp, monkeypatch) -> None:
    """``shutdown`` must release the renderer, not only the PyMOL controller."""
    viewer, stub = _viewer_with_stub_web(monkeypatch)
    try:
        viewer.show()
        qapp.processEvents()
        assert viewer._web is stub

        assert viewer.shutdown(1000)

        assert stub.page_deleted, "QWebEnginePage was never deleted"
        assert stub.deleted, "QWebEngineView was never scheduled for deletion"
        assert viewer._web is None, "viewer kept a stale web-view reference"
    finally:
        viewer.close()


def test_shutdown_is_idempotent(qapp, monkeypatch) -> None:
    """A second shutdown must not raise once the renderer is already gone."""
    viewer, _stub = _viewer_with_stub_web(monkeypatch)
    try:
        viewer.show()
        qapp.processEvents()
        assert viewer.shutdown(1000)
        assert viewer.shutdown(1000)
        assert viewer._web is None
    finally:
        viewer.close()


def test_shutdown_without_webengine_still_succeeds(qapp, monkeypatch) -> None:
    """The QtWebEngine-absent fallback path must keep the same contract."""
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)

    class _Service:
        available = False

    viewer = viewer_module.StructureViewer(pymol_service=_Service())
    try:
        viewer.show()
        qapp.processEvents()
        assert viewer._web is None
        assert viewer.shutdown(1000)
    finally:
        viewer.close()


def test_failed_worker_drain_preserves_the_live_web_view(
    qapp,
    monkeypatch,
) -> None:
    """An ignored close must not destroy part of the still-visible window."""
    viewer, stub = _viewer_with_stub_web(monkeypatch)
    monkeypatch.setattr(viewer._pymol_controller, "shutdown", lambda _ms: False)
    try:
        assert viewer.shutdown(1) is False
        assert viewer._web is stub
        assert not stub.page_deleted
        assert not stub.deleted
    finally:
        viewer.close()


def test_later_screen_rejection_preserves_web_view_until_atomic_close(
    qapp,
    monkeypatch,
) -> None:
    """A later shutdown rejection must not partially destroy the window."""
    from chemsmart.gui.app import MainWindow

    viewer, stub = _viewer_with_stub_web(monkeypatch)

    class _RejectingScreen:
        allow_close = False

        def shutdown(self, _timeout_ms: int) -> bool:
            return self.allow_close

    rejecting = _RejectingScreen()
    window = MainWindow()
    window._structure_viewer = viewer
    window._screens["rejecting"] = rejecting
    window.show()
    try:
        assert window.close() is False
        assert window.isVisible()
        assert viewer._web is stub
        assert not stub.page_deleted
        assert not stub.deleted

        rejecting.allow_close = True
        assert window.close() is True
        assert stub.page_deleted
        assert stub.deleted
        assert viewer._web is None
    finally:
        rejecting.allow_close = True
        window.close()
        viewer.close()
