"""Recoverable placeholders for desktop surfaces not implemented yet."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class UnavailableFeatureScreen(QWidget):
    """Explain an intentionally unavailable phase without breaking navigation."""

    def __init__(self, title: str, phase: str, detail: str, parent=None) -> None:
        super().__init__(parent, objectName="Screen")
        self.setAccessibleName(f"{title} unavailable")
        self.setAccessibleDescription(detail)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.addWidget(QLabel(title, objectName="ScreenTitle"))

        state = QLabel(f"Planned for {phase}", objectName="ScreenSubtitle")
        state.setAccessibleName(f"Availability: planned for {phase}")
        layout.addWidget(state)

        message = QLabel(detail)
        message.setWordWrap(True)
        message.setMaximumWidth(560)
        layout.addWidget(message)
        layout.addStretch(1)
