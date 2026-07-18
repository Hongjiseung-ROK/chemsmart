"""Job builder — the home surface (plan Phase 3, principle #5).

Forms are generated from the live CLI schema
(:mod:`chemsmart.gui.services.cli_schema_service`) rather than hand-built per
subcommand. Required/common options render first; the rest hide behind an
"Advanced options" disclosure (principle #7). The built argv is previewed in
monospace (principles #3/#9), driven as a ``--fake --no-scratch`` dry run
(never real compute), and shared with the chat via the same schema mapping.

This is a compact-density surface: the root sets ``density="compact"`` so the
stylesheet applies the dense, monospaced input treatment.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.services import cli_schema_service as schema
from chemsmart.gui.services.job_worker import start_dry_run
from chemsmart.gui.widgets.structure_viewer import StructureViewer


class JobBuilderScreen(QWidget):
    def __init__(self, window) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self.setProperty("density", "compact")
        self._field_getters: dict[str, Callable[[], Any]] = {}
        self._thread = None
        self._worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)

        outer.addWidget(QLabel("Job builder", objectName="ScreenTitle"))
        outer.addWidget(
            QLabel(
                "Forms generated from the CLI schema · command preview only "
                "until the safe launcher is verified",
                objectName="ScreenSubtitle",
            )
        )

        body = QHBoxLayout()
        outer.addLayout(body, stretch=1)

        left = QVBoxLayout()
        body.addLayout(left, stretch=3)

        selectors = QFormLayout()
        self.program = QComboBox()
        self.program.addItems(schema.programs() or ["gaussian", "orca"])
        self.program.currentTextChanged.connect(self._on_program_changed)
        self.job_type = QComboBox()
        selectors.addRow(QLabel("Program", objectName="FieldLabel"), self.program)
        selectors.addRow(
            QLabel("Job type", objectName="FieldLabel"), self.job_type
        )
        left.addLayout(selectors)

        self.common_box = QGroupBox("Options")
        self.common_form = QFormLayout(self.common_box)
        left.addWidget(self.common_box)

        self.advanced_toggle = QPushButton("Advanced options ▸")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._on_advanced_toggled)
        left.addWidget(self.advanced_toggle)
        self.advanced_box = QGroupBox("Advanced")
        self.advanced_form = QFormLayout(self.advanced_box)
        self.advanced_box.setVisible(False)
        left.addWidget(self.advanced_box)
        left.addStretch(1)

        right = QVBoxLayout()
        body.addLayout(right, stretch=2)
        right.addWidget(QLabel("Structure", objectName="FieldLabel"))
        self.viewer = StructureViewer()
        right.addWidget(self.viewer, stretch=1)

        self.preview = QPlainTextEdit(objectName="Preview")
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(120)
        outer.addWidget(QLabel("Command", objectName="FieldLabel"))
        outer.addWidget(self.preview)

        actions = QHBoxLayout()
        self.dry_run_button = QPushButton("Dry run", objectName="Primary")
        self.dry_run_button.setEnabled(False)
        self.dry_run_button.setToolTip(
            "Available after the checkout-verified fake-run launcher is ready."
        )
        self.dry_run_button.setAccessibleDescription(
            "Disabled until ChemSmart can verify the executable and enforce "
            "fake-run safety."
        )
        self.dry_run_button.clicked.connect(self._on_dry_run)
        self.to_chat_button = QPushButton("Hand off to agent")
        self.to_chat_button.clicked.connect(self._on_hand_off)
        actions.addWidget(self.dry_run_button)
        actions.addWidget(self.to_chat_button)
        actions.addStretch(1)
        outer.addLayout(actions)

        self.output = QPlainTextEdit(objectName="MonoOutput")
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(140)
        outer.addWidget(self.output)

        self.job_type.currentTextChanged.connect(self._rebuild_fields)
        self._on_program_changed(self.program.currentText())

    # -- schema-driven form --------------------------------------------- #

    def _on_program_changed(self, program: str) -> None:
        self.job_type.blockSignals(True)
        self.job_type.clear()
        job_types = schema.job_types(program)
        self.job_type.addItems(job_types)
        if "opt" in job_types:
            self.job_type.setCurrentText("opt")
        self.job_type.blockSignals(False)
        self._rebuild_fields()

    def _rebuild_fields(self) -> None:
        _clear_form(self.common_form)
        _clear_form(self.advanced_form)
        self._field_getters.clear()

        program = self.program.currentText()
        job_type = self.job_type.currentText()
        if not job_type:
            self._update_preview()
            return

        for opt in schema.options(program, job_type):
            widget, getter = _field_for(opt)
            self._field_getters[opt["field_id"]] = getter
            label = QLabel(opt["name"], objectName="FieldLabel")
            target = self.common_form if opt.get("required") else self.advanced_form
            target.addRow(label, widget)
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._update_preview)
            elif hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(self._update_preview)
            elif hasattr(widget, "toggled"):
                widget.toggled.connect(self._update_preview)
        self._update_preview()

    def _current_values(self) -> dict[str, Any]:
        return {name: getter() for name, getter in self._field_getters.items()}

    def _build_argv(self) -> list[str]:
        return schema.build_command(
            self.program.currentText(),
            self.job_type.currentText(),
            self._current_values(),
        )

    def _update_preview(self) -> None:
        self.preview.setPlainText(" ".join(self._build_argv()))

    def _on_advanced_toggled(self, shown: bool) -> None:
        self.advanced_box.setVisible(shown)
        self.advanced_toggle.setText(
            "Advanced options ▾" if shown else "Advanced options ▸"
        )

    # -- actions -------------------------------------------------------- #

    def _on_dry_run(self) -> None:
        self.output.setPlainText("Running dry run…")
        self._thread, self._worker = start_dry_run(
            self._build_argv(), self._on_dry_run_done, parent=self
        )

    def _on_dry_run_done(self, returncode: int, output: str) -> None:
        status = "ok" if returncode == 0 else f"exit {returncode}"
        self.output.setPlainText(f"[{status}]\n{output}")

    def _on_hand_off(self) -> None:
        # Round-trips the built command into the chat via the shared schema
        # mapping (principle #5). Wired to the chat screen in Phase 4.
        self.window_ref.navigate("chat")


def _field_for(opt: dict) -> tuple[QWidget, Callable[[], Any]]:
    """Build an input widget + value getter for one schema option."""
    if opt.get("is_flag"):
        box = QCheckBox()
        box.setChecked(bool(opt.get("default")))
        return box, box.isChecked
    choices = opt.get("choices") or _choices_from_type(opt.get("type"))
    if choices:
        combo = QComboBox()
        combo.addItem("")
        combo.addItems([str(c) for c in choices])
        return combo, combo.currentText
    edit = QLineEdit()
    default = opt.get("default")
    if default not in (None, False):
        edit.setText(str(default))
    return edit, edit.text


def _choices_from_type(type_field) -> list:
    if isinstance(type_field, dict) and type_field.get("type") == "choice":
        return list(type_field.get("choices", []))
    return []


def _clear_form(form: QFormLayout) -> None:
    while form.rowCount():
        form.removeRow(0)
