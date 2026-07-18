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
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.services import cli_schema_service as schema
from chemsmart.gui.application.cli_launcher import DryRunRequest, DryRunResult
from chemsmart.gui.application.task_controller import (
    TaskFailure,
    TaskProgress,
    TaskSnapshot,
    TaskStatus,
)
from chemsmart.gui.services.job_worker import start_dry_run


_COMMON_FIELDS = frozenset(
    {
        "filename",
        "pubchem",
        "project",
        "charge",
        "multiplicity",
        "record_index",
        "record_id",
        "structure_index",
        "structure_id",
    }
)
_DATABASE_FIELDS = frozenset(
    {"record_index", "record_id", "structure_index", "structure_id"}
)
_MAX_STRUCTURE_PREVIEW_BYTES = 8 * 1024 * 1024


class JobBuilderScreen(QWidget):
    def __init__(self, window) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self.setProperty("density", "compact")
        self._field_getters: dict[str, Callable[[], Any]] = {}
        self._field_widgets: dict[str, QWidget] = {}
        self._field_rows: dict[str, tuple[QLabel, QWidget]] = {}
        self._dry_run_controller = None
        self._handoff_available = False
        self._accepted_command = ""
        self._preview_artifacts = ()
        self._preview_dependencies = ()
        self._preview_verdict = "ok"
        self._running_command = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)

        outer.addWidget(QLabel("Job builder", objectName="ScreenTitle"))
        subtitle = QLabel(
            "Choose chemistry settings, review the exact command, and "
            "generate input safely. No calculation or submission is available.",
            objectName="ScreenSubtitle",
        )
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        self.form_scroll = QScrollArea()
        self.form_scroll.setObjectName("JobBuilderFormScroll")
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.form_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.form_scroll.setMinimumHeight(120)
        self.form_content = QWidget()
        left = QVBoxLayout(self.form_content)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.form_scroll.setWidget(self.form_content)
        outer.addWidget(self.form_scroll, stretch=1)

        selectors = QFormLayout()
        self.program = QComboBox()
        self.program.addItems(schema.programs() or ["gaussian", "orca", "xtb"])
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
        self.source_mode = QComboBox()
        self.source_mode.addItem("Local file", "file")
        self.source_mode.addItem("PubChem identifier", "pubchem")
        self.source_mode.addItem("ChemSmart database", "database")
        self.source_mode.setAccessibleName("Molecule source type")
        self.source_mode.setAccessibleDescription(
            "Choose a local file, a PubChem identifier, or a ChemSmart database."
        )
        self.source_mode.currentIndexChanged.connect(
            self._on_source_mode_changed
        )
        source_label = QLabel("Molecule source", objectName="FieldLabel")
        source_label.setBuddy(self.source_mode)
        selectors.addRow(source_label, self.source_mode)
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
        self.dry_run_button = QPushButton("Generate input", objectName="Primary")
        self.dry_run_button.setEnabled(False)
        self.dry_run_button.setToolTip(
            "Generate and validate input with the enforced fake runner."
        )
        self.dry_run_button.setAccessibleDescription(
            "Runs only fake and no-scratch mode in an isolated workspace."
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
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_dry_run)
        actions.addWidget(self.cancel_button)
        self.retry_button = QPushButton("Retry")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._retry_dry_run)
        actions.addWidget(self.retry_button)
        actions.addWidget(self.to_chat_button)
        actions.addStretch(1)
        outer.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Safe preview progress")
        self.progress.setVisible(False)
        outer.addWidget(self.progress)

        self.output = QPlainTextEdit(objectName="MonoOutput")
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(140)
        self.output.setAccessibleName("Generated input and validation receipt")
        self.output.setPlaceholderText(
            "Generated Gaussian, ORCA, or xTB input will appear here after safe preview."
        )
        self.artifact_label = QLabel("Artifact", objectName="FieldLabel")
        self.artifact_selector = QComboBox()
        self.artifact_selector.setAccessibleName("Generated input artifact")
        self.artifact_selector.setAccessibleDescription(
            "Choose any generated input to inspect its content and receipt."
        )
        self.artifact_selector.currentIndexChanged.connect(
            self._show_selected_artifact
        )
        self.artifact_label.setVisible(False)
        self.artifact_selector.setVisible(False)
        outer.addWidget(self.artifact_label)
        outer.addWidget(self.artifact_selector)
        outer.addWidget(QLabel("Generated input", objectName="FieldLabel"))
        outer.addWidget(self.output)

        safe_preview = self.window_ref.menu_actions.get("safe_preview")
        if safe_preview is not None:
            safe_preview.triggered.connect(self._on_dry_run)

        self.job_type.currentTextChanged.connect(self._rebuild_fields)
        self._on_program_changed(self.program.currentText())

    # -- schema-driven form --------------------------------------------- #

    def _on_program_changed(self, program: str) -> None:
        self._configure_source_modes(program)
        self.job_type.blockSignals(True)
        self.job_type.clear()
        job_types = schema.job_types(program)
        self.job_type.addItems(job_types)
        if "opt" in job_types:
            self.job_type.setCurrentText("opt")
        self.job_type.blockSignals(False)
        self._rebuild_fields()

    def _configure_source_modes(self, program: str) -> None:
        local_only = program == "xtb"
        if local_only and self.source_mode.currentData() != "file":
            self.source_mode.setCurrentIndex(0)
        model = self.source_mode.model()
        for index in (1, 2):
            item = model.item(index) if hasattr(model, "item") else None
            if item is not None:
                item.setEnabled(not local_only)
                item.setToolTip(
                    "xTB safe preview currently accepts local molecule files only."
                    if local_only
                    else ""
                )
        self.source_mode.setToolTip(
            "xTB safe preview uses local files only."
            if local_only
            else "Choose a molecule source."
        )

    def _rebuild_fields(self) -> None:
        self._clear_structure_preview()
        _clear_form(self.common_form)
        _clear_form(self.advanced_form)
        self._field_getters.clear()
        self._field_widgets.clear()
        self._field_rows.clear()

        program = self.program.currentText()
        job_type = self.job_type.currentText()
        if not job_type:
            self._update_preview()
            return

        for opt in schema.options(program, job_type):
            if opt["name"] == "molecule_id":
                # The CLI exposes this legacy selector, but Gaussian/ORCA job
                # construction rejects it. Do not offer an always-invalid UI.
                continue
            widget, getter = _field_for(opt)
            widget.setAccessibleName(opt["name"])
            if opt.get("help"):
                widget.setAccessibleDescription(opt["help"])
            self._field_getters[opt["field_id"]] = getter
            self._field_widgets[opt["field_id"]] = widget
            label = QLabel(_field_label(opt["name"]), objectName="FieldLabel")
            label.setBuddy(widget)
            target = (
                self.common_form
                if opt.get("required") or opt["name"] in _COMMON_FIELDS
                else self.advanced_form
            )
            if opt["name"] == "filename" and isinstance(widget, QLineEdit):
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(widget, stretch=1)
                choose = QPushButton("Choose…")
                choose.setAccessibleName("Choose molecule file")
                choose.clicked.connect(
                    lambda _checked=False, field=widget: self._choose_file(field)
                )
                row.addWidget(choose)
                target.addRow(label, row_widget)
                widget.editingFinished.connect(self._load_structure_preview)
                widget.textChanged.connect(self._clear_structure_preview)
            else:
                target.addRow(label, widget)
                row_widget = widget
            self._field_rows[opt["field_id"]] = (label, row_widget)
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._update_preview)
            elif hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(self._update_preview)
            elif hasattr(widget, "toggled"):
                widget.toggled.connect(self._update_preview)
        self._apply_source_visibility()
        self.form_content.adjustSize()
        self._update_preview()

    def _on_source_mode_changed(self) -> None:
        self._clear_structure_preview()
        filename = self._field_widgets.get("filename")
        pubchem = self._field_widgets.get("pubchem")
        # A filename has different semantics in file and database modes.
        # Clear every source payload when the mode changes so a local XYZ can
        # never remain active under a "Database file" label (or vice versa).
        _clear_field(filename)
        _clear_field(pubchem)
        for field_id in _DATABASE_FIELDS:
            _clear_field(self._field_widgets.get(field_id))
        self._apply_source_visibility()
        self._update_preview()

    def _apply_source_visibility(self) -> None:
        mode = self.source_mode.currentData()
        for field_id, (label, widget) in self._field_rows.items():
            if field_id == "filename":
                visible = mode in {"file", "database"}
                label.setText("Database file" if mode == "database" else "Molecule file")
            elif field_id == "pubchem":
                visible = mode == "pubchem"
            elif field_id in _DATABASE_FIELDS:
                visible = mode == "database"
            else:
                visible = True
            label.setVisible(visible)
            widget.setVisible(visible)

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
            argv = self._build_argv()
            command = shlex.join(argv)
        except ValueError as exc:
            self.preview.clear()
            self._invalidate_previous_preview()
            self.validation_status.setText(_bounded_validation_message(str(exc)))
            self._set_preview_enabled(False)
            self.to_chat_button.setEnabled(False)
            return
        self.preview.setPlainText(command)
        if self._accepted_command and command != self._accepted_command:
            self._invalidate_previous_preview()
        try:
            request = DryRunRequest(
                argv=tuple(argv),
                cwd=self.window_ref.workspace_root,
            )
        except ValueError as exc:
            self.validation_status.setText(
                _bounded_validation_message(str(exc))
            )
            self._set_preview_enabled(False)
            self.to_chat_button.setEnabled(False)
            return
        self.preview.setPlainText(command)
        self.validation_status.setText(
            "Ready for isolated fake-run validation. No real calculation or "
            "submission is available."
        )
        running = self._task_is_active()
        self._set_preview_enabled(not running and request.cwd.is_dir())
        self.to_chat_button.setEnabled(self._handoff_available)

    def _on_advanced_toggled(self, shown: bool) -> None:
        self.advanced_box.setVisible(shown)
        self.advanced_toggle.setText(
            "Advanced options ▾" if shown else "Advanced options ▸"
        )

    # -- actions -------------------------------------------------------- #

    def _set_preview_enabled(self, enabled: bool) -> None:
        self.dry_run_button.setEnabled(enabled)
        action = self.window_ref.menu_actions.get("safe_preview")
        if action is not None:
            action.setEnabled(enabled)

    def _choose_file(self, field: QLineEdit) -> None:
        database_mode = self.source_mode.currentData() == "database"
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose molecule source",
            str(self.window_ref.workspace_root),
            (
                "ChemSmart databases (*.db);;All files (*)"
                if database_mode
                else "Molecule files (*.xyz *.com *.gjf *.inp *.out *.log);;"
                "All files (*)"
            ),
        )
        if not filename:
            return
        field.setText(filename)
        self._load_structure_preview()

    def _load_structure_preview(self) -> None:
        self._clear_structure_preview()
        if self.source_mode.currentData() != "file":
            return
        field = self._field_widgets.get("filename")
        if not isinstance(field, QLineEdit):
            return
        path = Path(field.text()).expanduser()
        if not path.is_absolute():
            path = self.window_ref.workspace_root / path
        if not path.is_file() or path.suffix.lower() == ".db":
            return
        try:
            size_bytes = path.stat().st_size
        except OSError:
            self.window_ref.inspector_status.setText(
                "The selected structure could not be inspected. Safe input "
                "generation will use the real CLI parser."
            )
            return
        if size_bytes > _MAX_STRUCTURE_PREVIEW_BYTES:
            self.window_ref.inspector_status.setText(
                "The selected file is too large for an interactive structure "
                "preview. Safe input generation remains available."
            )
            return
        try:
            from chemsmart.io.molecules.structure import Molecule

            molecule = Molecule.from_filepath(path)
        except Exception:
            self.window_ref.inspector_status.setText(
                "The source is selected, but its structure preview could not "
                "be loaded. Safe preview will still use the real CLI parser."
            )
            return
        viewer = self.window_ref.ensure_structure_viewer()
        viewer.load_molecule(molecule, source_path=path)
        self.window_ref.inspector_status.setText(
            f"Selected source: {path.name}. Generated-input evidence will "
            "appear after safe preview."
        )

    def _clear_structure_preview(self) -> None:
        viewer = getattr(self.window_ref, "_structure_viewer", None)
        if viewer is None:
            return
        clear = getattr(viewer, "clear_molecule", None)
        if clear is not None:
            clear()
        viewer.setVisible(False)

    def _on_dry_run(self) -> None:
        if not self.dry_run_button.isEnabled():
            return
        argv = self._build_argv()
        self._running_command = shlex.join(argv)
        self._accepted_command = ""
        self._clear_preview_artifacts()
        self.output.setPlainText("Generating input with the fake runner…")
        self.retry_button.setVisible(False)
        self._set_preview_enabled(False)
        try:
            self._dry_run_controller = start_dry_run(
                argv,
                self._on_dry_run_done,
                parent=self,
                cwd=self.window_ref.workspace_root,
                on_failed=self._on_dry_run_failed,
                on_cancelled=self._on_dry_run_cancelled,
            )
        except ValueError as exc:
            self._running_command = ""
            self.validation_status.setText(_bounded_validation_message(str(exc)))
            self._update_preview()
            return
        self._dry_run_controller.state_changed.connect(self._on_task_state)
        self._dry_run_controller.progress_changed.connect(self._on_task_progress)
        self._on_task_state(self._dry_run_controller.snapshot)

    def _on_dry_run_done(self, result: DryRunResult) -> None:
        current_command = shlex.join(self._build_argv())
        if current_command != self._running_command:
            self._clear_preview_artifacts()
            self.output.clear()
            self.validation_status.setText(
                "Draft changed while the preview was running. The stale "
                "result was discarded; generate input again."
            )
        elif result.semantic.verdict == "reject" or not result.artifacts:
            rules = ", ".join(result.semantic.failed_rule_ids) or "no artifact"
            self.validation_status.setText(
                f"Safe preview was blocked by deterministic validation: {rules}."
            )
            self.output.setPlainText(
                _bounded_validation_message(result.output or result.semantic.notice)
            )
            self.retry_button.setVisible(True)
        else:
            self._accepted_command = result.semantic.command
            self._set_preview_artifacts(result)
        self._finish_task_ui()

    def _on_dry_run_failed(self, failure: TaskFailure) -> None:
        self._clear_preview_artifacts()
        self.validation_status.setText(
            f"Safe preview failed before validation. ({failure.diagnostic_type})"
        )
        self.output.setPlainText(
            "No generated input was accepted. Review the source and project, "
            "then retry."
        )
        self.retry_button.setVisible(True)
        self._finish_task_ui()

    def _on_dry_run_cancelled(self) -> None:
        self._clear_preview_artifacts()
        self.validation_status.setText(
            "Safe preview cancelled. No isolated preview files were retained."
        )
        self.output.setPlainText("Cancelled.")
        self._finish_task_ui()

    def _on_task_state(self, snapshot: TaskSnapshot) -> None:
        active = snapshot.status in {TaskStatus.RUNNING, TaskStatus.CANCELLING}
        self.form_content.setEnabled(not active)
        self.progress.setVisible(active)
        self.cancel_button.setVisible(active)
        self.cancel_button.setEnabled(snapshot.status == TaskStatus.RUNNING)
        self._set_task_status(
            {
                TaskStatus.RUNNING: "Safe preview: running",
                TaskStatus.CANCELLING: "Safe preview: cancelling",
            }.get(snapshot.status, "Idle")
        )

    def _on_task_progress(self, progress: TaskProgress) -> None:
        if progress.indeterminate:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, progress.total or 1)
            self.progress.setValue(progress.current or 0)
        if progress.message:
            self.validation_status.setText(progress.message)

    def _finish_task_ui(self) -> None:
        status_message = self.validation_status.text()
        self.form_content.setEnabled(True)
        self._running_command = ""
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self._set_task_status("Idle")
        self._update_preview()
        self.validation_status.setText(status_message)

    def _cancel_dry_run(self) -> None:
        if self._dry_run_controller is not None:
            self._dry_run_controller.cancel()

    def _retry_dry_run(self) -> None:
        self.retry_button.setVisible(False)
        self._on_dry_run()

    def _task_is_active(self) -> bool:
        if self._dry_run_controller is None:
            return False
        return self._dry_run_controller.snapshot.status in {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
        }

    def _invalidate_previous_preview(self) -> None:
        if not self._accepted_command:
            return
        self._accepted_command = ""
        self._clear_preview_artifacts()
        self.output.clear()
        self.window_ref.runtime_evidence.setText(
            "Draft changed. Run safe preview again to create a current receipt."
        )

    def _set_preview_artifacts(self, result: DryRunResult) -> None:
        self._preview_artifacts = result.artifacts
        self._preview_dependencies = result.dependencies
        self._preview_verdict = result.semantic.verdict
        self.artifact_selector.blockSignals(True)
        self.artifact_selector.clear()
        for artifact in result.artifacts:
            self.artifact_selector.addItem(
                f"{artifact.name} · {artifact.size_bytes} B · "
                f"{artifact.sha256[:12]}…"
            )
        self.artifact_selector.blockSignals(False)
        self.artifact_label.setVisible(True)
        self.artifact_selector.setVisible(True)
        self.artifact_selector.setCurrentIndex(0)
        self._show_selected_artifact(0)

    def _show_selected_artifact(self, index: int) -> None:
        if index < 0 or index >= len(self._preview_artifacts):
            return
        artifact = self._preview_artifacts[index]
        self.output.setPlainText(artifact.content)
        status = (
            "passed"
            if self._preview_verdict == "ok"
            else "passed with warnings"
        )
        self.validation_status.setText(
            f"Safe preview {status}. Artifact {index + 1} of "
            f"{len(self._preview_artifacts)}: {artifact.name} · "
            f"{artifact.size_bytes} bytes · SHA-256 {artifact.sha256[:12]}…"
        )
        artifact_lines = [
            f"- {item.name} · {item.size_bytes} bytes · {item.sha256}"
            for item in self._preview_artifacts[:24]
        ]
        if len(self._preview_artifacts) > 24:
            artifact_lines.append(
                f"- … {len(self._preview_artifacts) - 24} more; use the selector"
            )
        self.window_ref.runtime_evidence.setText(
            f"Fake-run receipt: {self._preview_verdict}\n"
            f"Artifacts: {len(self._preview_artifacts)}\n"
            f"{chr(10).join(artifact_lines)}\n"
            f"Selected: {artifact.name}\n"
            f"Route: {artifact.route}\n"
            f"Charge / multiplicity: {artifact.charge} / "
            f"{artifact.multiplicity}\n"
            f"Staged dependencies: "
            f"{', '.join(item.name for item in self._preview_dependencies) or 'none'}"
        )

    def _clear_preview_artifacts(self) -> None:
        self._preview_artifacts = ()
        self._preview_dependencies = ()
        self._preview_verdict = "ok"
        self.artifact_selector.clear()
        self.artifact_label.setVisible(False)
        self.artifact_selector.setVisible(False)

    def _set_task_status(self, message: str) -> None:
        self.window_ref.task_status.setText(message)
        self.window_ref.task_status.setAccessibleName(f"Task status: {message}")
        self.window_ref.task_status.setAccessibleDescription(
            "No background task is running."
            if message == "Idle"
            else f"Background task state: {message}."
        )

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        if self._dry_run_controller is None:
            return True
        return self._dry_run_controller.shutdown(timeout_ms)

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


def _bounded_validation_message(message: str, limit: int = 320) -> str:
    normalized = " ".join(message.split())
    normalized = normalized.replace(
        "Dry run is not ready: ",
        "To continue: ",
        1,
    ).replace(
        "Dry run is missing required fields: ",
        "Complete these required fields: ",
        1,
    )
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


def _field_label(name: str) -> str:
    labels = {
        "filename": "Molecule file",
        "pubchem": "PubChem identifier",
        "record_index": "Record index",
        "record_id": "Record ID",
        "structure_index": "Structure index",
        "structure_id": "Structure ID",
        "multiplicity": "Spin multiplicity",
    }
    return labels.get(name, name.replace("_", " ").capitalize())


def _clear_field(widget: QWidget | None) -> None:
    if isinstance(widget, QLineEdit):
        widget.clear()
    elif isinstance(widget, QComboBox):
        widget.setCurrentIndex(0)


def _clear_form(form: QFormLayout) -> None:
    while form.rowCount():
        form.removeRow(0)
    QScrollArea,
