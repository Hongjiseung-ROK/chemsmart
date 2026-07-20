"""Shared token plumbing for the P8.1 primitive widgets.

Primitives style themselves from :mod:`chemsmart.gui.design.tokens` and
restyle in place when the appearance changes; screens never write raw hex
into them. Widgets here render state and emit typed intent only — no
chemistry, task execution, or terminal-output parsing.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from chemsmart.gui.design.tokens import Tokens, resolve_tokens


class TokenConsumer:
    """Mixin storing the active token set and driving ``_restyle``.

    Subclasses implement ``_restyle(tokens)`` and call
    ``self._init_tokens(tokens)`` once their child widgets exist.
    """

    _tokens: Tokens

    def _init_tokens(self, tokens: Tokens | None) -> None:
        self._tokens = tokens if tokens is not None else resolve_tokens()
        self._restyle(self._tokens)

    def apply_tokens(self, tokens: Tokens) -> None:
        """Restyle for a new appearance mode without rebuilding widgets."""
        self._tokens = tokens
        self._restyle(tokens)

    def tokens(self) -> Tokens:
        return self._tokens

    def _restyle(self, tokens: Tokens) -> None:  # pragma: no cover
        raise NotImplementedError


class PaintedSurface(QWidget):
    """A container that paints its own rounded background deterministically.

    Stylesheet backgrounds on ``QWidget`` subclasses proved unreliable under
    widget churn (the QStyleSheetStyle fill was intermittently dropped,
    leaving status pills and panels on the default window color), so
    surface-owning primitives draw their fill and outline directly.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._surface_fill: str | None = None
        self._surface_outline: str | None = None
        self._surface_radius: int = 0

    def set_surface(
        self,
        fill: str,
        *,
        outline: str | None = None,
        radius: int = 0,
    ) -> None:
        self._surface_fill = fill
        self._surface_outline = outline
        self._surface_radius = radius
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._surface_fill is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(self._surface_fill))
            if self._surface_outline is not None:
                painter.setPen(QPen(QColor(self._surface_outline), 1))
            else:
                painter.setPen(QPen(QColor(self._surface_fill), 1))
            radius = self._surface_radius
            painter.drawRoundedRect(
                self.rect().adjusted(0, 0, -1, -1), radius, radius
            )
            painter.end()
        super().paintEvent(event)
