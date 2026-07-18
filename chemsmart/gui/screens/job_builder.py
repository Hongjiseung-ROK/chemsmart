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

import shlex
from typing import Any, Callable

from PySide6.QtCore import Qt
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


class JobBuilderScreen(QWidget):
    def __init__(self, window) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self.setProperty("density", "compact")
        self._field_getters: dict[str, Callable[[], Any]] = {}
        self._dry_run_controller = None
        self._handoff_available = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)

        outer.addWidget(QLabel("Job builder", objectName="ScreenTitle"))
        subtitle = QLabel(
            "Forms generated from the CLI schema · command preview only "
            "until fake-run artifact parity is verified",
            objectName="ScreenSubtitle",
        )
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        left = QVBoxLayout()
        outer.addLayout(left, stretch=1)

        selectors = QFormLayout()
        self.program = QComboBox()
        self.program.addItems(schema.programs() or ["gaussian", "orca"])
        self.program.setAccessibleName("Quantum chemistry program")
        self.program.currentTextChanged.connect(self._on_program_changed)
        self.job_type = QComboBox()
        self.job_type.setAccessibleName("Calculation job type")
        program_label = QLabel("Program", objectName="FieldLabel")
        program_label.setBuddy(self.program)
        job_type_label = QLabel("Job type", objectName="FieldLabel")
        job_type_label.setBuddy(self.job_type)
        selectors.addRow(program_label, self.program)
        selectors.addRow(job_type_label, self.job_type)
        left.addLayout(selectors)

        self.common_box = QGroupBox("Options")
        self.common_form = QFormLayout(self.common_box)
        left.addWidget(self.common_box)

        self.advanced_toggle = QPushButton("Advanced options ▸")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setAccessibleDescription(
            "Shows or hides optional fields inherited from the ChemSmart CLI."
        )
        self.advanced_toggle.toggled.connect(self._on_advanced_toggled)
        left.addWidget(self.advanced_toggle)
        self.advanced_box = QGroupBox("Advanced")
        self.advanced_form = QFormLayout(self.advanced_box)
        self.advanced_box.setVisible(False)
        left.addWidget(self.advanced_box)
        left.addStretch(1)

        self.preview = QPlainTextEdit(objectName="Preview")
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Generated ChemSmart command preview")
        self.preview.setMaximumHeight(120)
        outer.addWidget(QLabel("Command", objectName="FieldLabel"))
        outer.addWidget(self.preview)
        self.validation_status = QLabel(
            "",
            objectName="ScreenSubtitle",
        )
        self.validation_status.setWordWrap(True)
        self.validation_status.setAccessibleName("Job draft validation status")
        outer.addWidget(self.validation_status)

        actions = QHBoxLayout()
        self.dry_run_button = QPushButton("Dry run", objectName="Primary")
        self.dry_run_button.setEnabled(False)
        self.dry_run_button.setToolTip(
            "Available after GUI and direct CLI fake runs produce equivalent "
            "artifacts."
        )
        self.dry_run_button.setAccessibleDescription(
            "Disabled until the generated-input artifact parity gate passes."
        )
        self.dry_run_button.clicked.connect(self._on_dry_run)
        self.to_chat_button = QPushButton("Send to Chat")
        self.to_chat_button.setEnabled(False)
        self.to_chat_button.setToolTip(
            "Available after the desktop agent handoff safety gate passes."
        )
        self.to_chat_button.setAccessibleDescription(
            "Opens Chat with this typed job draft; no command is executed."
        )
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
            widget.setAccessibleName(opt["name"])
            if opt.get("help"):
                widget.setAccessibleDescription(opt["help"])
            self._field_getters[opt["field_id"]] = getter
            label = QLabel(opt["name"], objectName="FieldLabel")
            label.setBuddy(widget)
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

    def _current_draft(self):
        """Return typed form state; rendered command text is only a view."""
        return schema.draft_from_values(
            self.program.currentText(),
            self.job_type.currentText(),
            self._current_values(),
        )

    def _build_argv(self) -> list[str]:
        return schema.command_from_draft(self._current_draft())

    def _update_preview(self) -> None:
        try:
            command = shlex.join(self._build_argv())
        except ValueError:
            self.preview.clear()
            self.validation_status.setText(
                "Review the molecule source and option values to continue."
            )
            self.to_chat_button.setEnabled(False)
            return
        self.preview.setPlainText(command)
        self.validation_status.setText("Command ready for review.")
        self.to_chat_button.setEnabled(self._handoff_available)

    def _on_advanced_toggled(self, shown: bool) -> None:
        self.advanced_box.setVisible(shown)
        self.advanced_toggle.setText(
            "Advanced options ▾" if shown else "Advanced options ▸"
        )

    # -- actions -------------------------------------------------------- #

    def _on_dry_run(self) -> None:
        self.output.setPlainText("Running dry run…")
        self._dry_run_controller = start_dry_run(
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
        default = opt.get("default")
        if default is None:
            box.setTristate(True)
            box.setCheckState(Qt.CheckState.PartiallyChecked)

            def tristate_value():
                state = box.checkState()
                if state == Qt.CheckState.PartiallyChecked:
                    return None
                return state == Qt.CheckState.Checked

            return box, tristate_value
        box.setChecked(bool(default))
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
