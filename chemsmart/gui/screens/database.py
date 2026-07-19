"""Native database browse, build, and export workflows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.application.database_models import (
    MAX_DATABASE_PAGE_SIZE,
    DatabaseAssembleRequest,
    DatabaseAssembleResult,
    DatabaseBrowseRequest,
    DatabaseDetail,
    DatabaseDetailRequest,
    DatabaseExportRequest,
    DatabaseExportResult,
    DatabasePage,
    DatabaseRow,
)
from chemsmart.gui.application.task_controller import (
    QtTaskController,
    TaskFailure,
    TaskProgress,
    TaskSnapshot,
    TaskStatus,
)
from chemsmart.gui.services.database_service import DatabaseService

_ACTIVE = {TaskStatus.RUNNING, TaskStatus.CANCELLING}
_EXPORT_FORMATS = (
    ("JSON — complete structured records", ".json"),
    ("CSV — scalar property table", ".csv"),
    ("XYZ — selected coordinates", ".xyz"),
    ("Extended XYZ — coordinates, energy, forces", ".extxyz"),
)


class DatabaseScreen(QWidget):
    def __init__(self, window, service: DatabaseService | None = None) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self._service = service or DatabaseService()
        self._page: DatabasePage | None = None
        self._pending_browse_path: Path | None = None
        self._browse_controller = QtTaskController[DatabasePage](self)
        self._detail_controller = QtTaskController[DatabaseDetail](self)
        self._assemble_controller = QtTaskController[DatabaseAssembleResult](
            self
        )
        self._export_controller = QtTaskController[DatabaseExportResult](self)
        self._controllers = (
            self._browse_controller,
            self._detail_controller,
            self._assemble_controller,
            self._export_controller,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.addWidget(QLabel("Database", objectName="ScreenTitle"))
        subtitle = QLabel(
            "Browse structured results or create verified database artifacts. "
            "Browsing never changes the database; existing files are never overwritten.",
            objectName="ScreenSubtitle",
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Database workflows")
        root.addWidget(self.tabs, stretch=1)
        self._build_browse_tab()
        self._build_assemble_tab()
        self._build_export_tab()

        self._request_controls = (
            self.file_path,
            self.choose_button,
            self.open_button,
            self.target,
            self.query,
            self.limit,
            self.search_button,
            self.results,
            self.build_source,
            self.build_source_button,
            self.build_program,
            self.build_structures,
            self.build_include_failed,
            self.build_continue_errors,
            self.build_output,
            self.build_output_button,
            self.build_button,
            self.export_db_path,
            self.export_db_button,
            self.export_format,
            self.export_output,
            self.export_output_button,
            self.export_scope,
            self.export_selector,
            self.export_structure_index,
            self.export_method_basis,
            self.export_csv_keys,
            self.export_button,
        )

        self._connect_controllers()
        self._on_export_format_changed()

    def _build_browse_tab(self) -> None:
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(12, 12, 12, 12)

        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setAccessibleName("ChemSmart database file")
        self.file_path.setPlaceholderText("Choose a ChemSmart .db file")
        self.file_path.returnPressed.connect(self._start_browse)
        self.choose_button = QPushButton("Choose…")
        self.choose_button.setAccessibleName("Choose ChemSmart database")
        self.choose_button.clicked.connect(self._choose_database)
        self.open_button = QPushButton("Open", objectName="Primary")
        self.open_button.clicked.connect(self._start_browse)
        file_row.addWidget(self.file_path, stretch=1)
        file_row.addWidget(self.choose_button)
        file_row.addWidget(self.open_button)
        root.addLayout(file_row)

        filters = QFormLayout()
        self.target = QComboBox()
        self.target.addItem("Records", "records")
        self.target.addItem("Molecules", "molecules")
        self.target.addItem("Structures", "structures")
        self.target.setAccessibleName("Database entity type")
        self.query = QLineEdit()
        self.query.setAccessibleName("Database query expression")
        self.query.setPlaceholderText("Optional, e.g. program = 'gaussian'")
        self.query.setToolTip(
            "Use ChemSmart fields with <, <=, >, >=, =, !=, ~ and AND/OR."
        )
        self.query.returnPressed.connect(self._start_browse)
        self.limit = QSpinBox()
        self.limit.setRange(1, MAX_DATABASE_PAGE_SIZE)
        self.limit.setValue(250)
        self.limit.setAccessibleName("Maximum database results")
        filters.addRow("View", self.target)
        filters.addRow("Filter", self.query)
        filters.addRow("Result limit", self.limit)
        root.addLayout(filters)

        action_row = QHBoxLayout()
        self.search_button = QPushButton("Browse")
        self.search_button.clicked.connect(self._start_browse)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_browse)
        self.retry_button = QPushButton("Retry current request")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._retry_browse)
        action_row.addWidget(self.search_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.retry_button)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self.progress = self._progress_bar("Database browse progress")
        root.addWidget(self.progress)
        self.status = QLabel("Choose a ChemSmart database to begin.")
        self.status.setObjectName("ScreenSubtitle")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Database browser status")
        root.addWidget(self.status)

        self.results = QTableWidget()
        self.results.setAccessibleName("Database query results")
        self.results.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.results.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.results.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.results.verticalHeader().setVisible(False)
        self.results.itemSelectionChanged.connect(self._load_selected_detail)
        self.results.setMinimumHeight(100)
        root.addWidget(self.results, stretch=2)

        root.addWidget(QLabel("Selected detail", objectName="FieldLabel"))
        self.detail = QPlainTextEdit(objectName="MonoOutput")
        self.detail.setReadOnly(True)
        self.detail.setAccessibleName("Selected database entity detail")
        self.detail.setPlaceholderText(
            "Select a result to inspect structured data."
        )
        self.detail.setMinimumHeight(80)
        root.addWidget(self.detail, stretch=1)
        self.tabs.addTab(self._scroll_container(content), "Browse")

    def _build_assemble_tab(self) -> None:
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(12, 12, 12, 12)
        explanation = QLabel(
            "Build a new, validated .db file from calculation outputs. ChemSmart "
            "writes to private staging storage first and publishes only after all "
            "checks pass. The database preserves original source-file paths; "
            "review it before sharing outside your lab.",
            objectName="ScreenSubtitle",
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        source_row = QHBoxLayout()
        self.build_source = QLineEdit()
        self.build_source.setAccessibleName("Calculation output folder")
        self.build_source.setPlaceholderText(
            "Folder containing Gaussian/ORCA outputs"
        )
        self.build_source_button = QPushButton("Choose folder…")
        self.build_source_button.clicked.connect(self._choose_build_source)
        source_row.addWidget(self.build_source, stretch=1)
        source_row.addWidget(self.build_source_button)
        root.addLayout(source_row)

        options = self._responsive_form()
        self.build_program = QComboBox()
        self.build_program.setAccessibleName("Calculation program filter")
        self.build_program.addItem("Detect Gaussian and ORCA", "auto")
        self.build_program.addItem("Gaussian only", "gaussian")
        self.build_program.addItem("ORCA only", "orca")
        self.build_structures = QComboBox()
        self.build_structures.setAccessibleName("Structures to assemble")
        self.build_structures.addItem("All parsed structures", ":")
        self.build_structures.addItem("Final structure only", "-1")
        self.build_include_failed = QCheckBox(
            "Include incomplete calculations"
        )
        self.build_include_failed.setAccessibleName(
            "Include abnormally terminated calculations"
        )
        self.build_include_failed.setToolTip(
            "May include incomplete trajectories. The receipt identifies skipped files."
        )
        self.build_continue_errors = QCheckBox("Continue after parser errors")
        self.build_continue_errors.setAccessibleName(
            "Allow partial database after parser errors"
        )
        self.build_continue_errors.setToolTip(
            "Off by default. When enabled, the receipt lists failed files; "
            "the database is still integrity-checked before publication."
        )
        options.addRow("Programs", self.build_program)
        options.addRow("Structures", self.build_structures)
        options.addRow("Partial calculation", self.build_include_failed)
        options.addRow("Partial batch", self.build_continue_errors)
        root.addLayout(options)

        output_row = QHBoxLayout()
        self.build_output = QLineEdit()
        self.build_output.setAccessibleName("New database destination")
        self.build_output.setPlaceholderText("New file name ending in .db")
        self.build_output_button = QPushButton("Choose destination…")
        self.build_output_button.clicked.connect(self._choose_build_output)
        output_row.addWidget(self.build_output, stretch=1)
        output_row.addWidget(self.build_output_button)
        root.addLayout(output_row)

        actions = QHBoxLayout()
        self.build_button = QPushButton(
            "Build new database", objectName="Primary"
        )
        self.build_button.clicked.connect(self._start_assemble)
        self.build_cancel_button = QPushButton("Cancel")
        self.build_cancel_button.setVisible(False)
        self.build_cancel_button.clicked.connect(self._cancel_assemble)
        self.build_retry_button = QPushButton("Retry current request")
        self.build_retry_button.setVisible(False)
        self.build_retry_button.clicked.connect(self._retry_assemble)
        actions.addWidget(self.build_button)
        actions.addWidget(self.build_cancel_button)
        actions.addWidget(self.build_retry_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.build_progress = self._progress_bar("Database build progress")
        root.addWidget(self.build_progress)
        self.build_status = QLabel(
            "No output is created if validation, parsing, cancellation, or integrity checks fail."
        )
        self.build_status.setObjectName("ScreenSubtitle")
        self.build_status.setWordWrap(True)
        self.build_status.setAccessibleName("Database build status")
        root.addWidget(self.build_status)
        self.build_receipt = QPlainTextEdit(objectName="MonoOutput")
        self.build_receipt.setReadOnly(True)
        self.build_receipt.setAccessibleName("Database build receipt")
        self.build_receipt.setPlaceholderText(
            "A verification receipt will appear after a successful build."
        )
        self.build_receipt.setMinimumHeight(100)
        root.addWidget(self.build_receipt, stretch=1)
        self.build_scroll = self._scroll_container(content)
        self.tabs.addTab(self.build_scroll, "Build database")

    def _build_export_tab(self) -> None:
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(12, 12, 12, 12)
        explanation = QLabel(
            "Export a new JSON, CSV, XYZ, or extended XYZ copy. JSON contains "
            "record provenance, including original source-file paths; review it "
            "before sharing outside your lab.",
            objectName="ScreenSubtitle",
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        db_row = QHBoxLayout()
        self.export_db_path = QLineEdit()
        self.export_db_path.setAccessibleName("Export source database")
        self.export_db_path.setPlaceholderText("Choose a ChemSmart .db file")
        self.export_db_button = QPushButton("Choose database…")
        self.export_db_button.clicked.connect(self._choose_export_database)
        db_row.addWidget(self.export_db_path, stretch=1)
        db_row.addWidget(self.export_db_button)
        root.addLayout(db_row)

        options = self._responsive_form()
        self.export_format = QComboBox()
        self.export_format.setAccessibleName("Database export format")
        for label, suffix in _EXPORT_FORMATS:
            self.export_format.addItem(label, suffix)
        self.export_format.currentIndexChanged.connect(
            self._on_export_format_changed
        )
        self.export_scope = QComboBox()
        self.export_scope.setAccessibleName("Database export selection")
        self.export_scope.addItem("Whole database", "whole")
        self.export_scope.addItem("Record index", "record_index")
        self.export_scope.addItem("Record ID", "record_id")
        self.export_scope.addItem("Structure ID", "structure_id")
        self.export_scope.addItem("Molecule ID", "molecule_id")
        self.export_scope.currentIndexChanged.connect(
            self._on_export_scope_changed
        )
        self.export_selector = QLineEdit()
        self.export_selector.setAccessibleName(
            "Database export selector value"
        )
        self.export_structure_index = QLineEdit()
        self.export_structure_index.setAccessibleName(
            "Structure index within selected record"
        )
        self.export_structure_index.setPlaceholderText(
            "Optional: final by default, ':' for all, or one-based index"
        )
        self.export_method_basis = QLineEdit()
        self.export_method_basis.setAccessibleName("Export method and basis")
        self.export_method_basis.setPlaceholderText(
            "Optional for structure/molecule, e.g. MN15/def2tzvp"
        )
        self.export_csv_keys = QLineEdit()
        self.export_csv_keys.setAccessibleName("Additional CSV property keys")
        self.export_csv_keys.setPlaceholderText(
            "Optional comma-separated scalar fields"
        )
        options.addRow("Format", self.export_format)
        options.addRow("Selection", self.export_scope)
        options.addRow("Selection value", self.export_selector)
        options.addRow("Structure index", self.export_structure_index)
        options.addRow("Method/basis", self.export_method_basis)
        options.addRow("Extra CSV fields", self.export_csv_keys)
        root.addLayout(options)

        output_row = QHBoxLayout()
        self.export_output = QLineEdit()
        self.export_output.setAccessibleName("New export destination")
        self.export_output.setPlaceholderText("Choose a new .json file")
        self.export_output_button = QPushButton("Choose destination…")
        self.export_output_button.clicked.connect(self._choose_export_output)
        output_row.addWidget(self.export_output, stretch=1)
        output_row.addWidget(self.export_output_button)
        root.addLayout(output_row)

        actions = QHBoxLayout()
        self.export_button = QPushButton(
            "Export verified copy", objectName="Primary"
        )
        self.export_button.clicked.connect(self._start_export)
        self.export_cancel_button = QPushButton("Cancel")
        self.export_cancel_button.setVisible(False)
        self.export_cancel_button.clicked.connect(self._cancel_export)
        self.export_retry_button = QPushButton("Retry current request")
        self.export_retry_button.setVisible(False)
        self.export_retry_button.clicked.connect(self._retry_export)
        actions.addWidget(self.export_button)
        actions.addWidget(self.export_cancel_button)
        actions.addWidget(self.export_retry_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.export_progress = self._progress_bar("Database export progress")
        root.addWidget(self.export_progress)
        self.export_status = QLabel(
            "Exports are staged, validated, hashed, and published only to a new file name."
        )
        self.export_status.setObjectName("ScreenSubtitle")
        self.export_status.setWordWrap(True)
        self.export_status.setAccessibleName("Database export status")
        root.addWidget(self.export_status)
        self.export_receipt = QPlainTextEdit(objectName="MonoOutput")
        self.export_receipt.setReadOnly(True)
        self.export_receipt.setAccessibleName("Database export receipt")
        self.export_receipt.setPlaceholderText(
            "A verification receipt will appear after a successful export."
        )
        self.export_receipt.setMinimumHeight(100)
        root.addWidget(self.export_receipt, stretch=1)
        self.export_scroll = self._scroll_container(content)
        self.tabs.addTab(self.export_scroll, "Export")

    @staticmethod
    def _responsive_form() -> QFormLayout:
        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        return form

    @staticmethod
    def _scroll_container(content: QWidget) -> QScrollArea:
        content.setObjectName("ScrollContent")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _connect_controllers(self) -> None:
        self._browse_controller.state_changed.connect(self._on_task_state)
        self._browse_controller.progress_changed.connect(
            lambda value: self._on_browse_progress(value)
        )
        self._browse_controller.succeeded.connect(self._on_page)
        self._browse_controller.failed.connect(self._on_browse_failure)
        self._browse_controller.cancelled.connect(self._on_browse_cancelled)

        self._detail_controller.state_changed.connect(self._on_task_state)
        self._detail_controller.progress_changed.connect(
            lambda value: self._on_browse_progress(value)
        )
        self._detail_controller.succeeded.connect(self._on_detail)
        self._detail_controller.failed.connect(self._on_detail_failure)
        self._detail_controller.cancelled.connect(self._on_detail_cancelled)

        self._assemble_controller.state_changed.connect(self._on_task_state)
        self._assemble_controller.progress_changed.connect(
            lambda value: self._set_progress(self.build_progress, value)
        )
        self._assemble_controller.succeeded.connect(self._on_assembled)
        self._assemble_controller.failed.connect(self._on_assemble_failure)
        self._assemble_controller.cancelled.connect(
            self._on_assemble_cancelled
        )
        self._assemble_controller.drained.connect(
            self._open_assembled_when_drained
        )

        self._export_controller.state_changed.connect(self._on_task_state)
        self._export_controller.progress_changed.connect(
            lambda value: self._set_progress(self.export_progress, value)
        )
        self._export_controller.succeeded.connect(self._on_exported)
        self._export_controller.failed.connect(self._on_export_failure)
        self._export_controller.cancelled.connect(self._on_export_cancelled)

    @staticmethod
    def _progress_bar(accessible_name: str) -> QProgressBar:
        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(True)
        progress.setAccessibleName(accessible_name)
        progress.setVisible(False)
        return progress

    @staticmethod
    def _set_progress(progress: QProgressBar, value: TaskProgress) -> None:
        if value.indeterminate:
            progress.setRange(0, 0)
            progress.setFormat(value.message or "Working…")
        else:
            progress.setRange(0, value.total or 1)
            progress.setValue(value.current or 0)
            progress.setFormat(
                f"{value.message} %v/%m" if value.message else "%v/%m"
            )

    def _choose_database(self) -> None:
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose ChemSmart database",
            str(self.window_ref.workspace_root),
            "ChemSmart databases (*.db);;All files (*)",
        )
        if filename:
            self.file_path.setText(filename)
            self.export_db_path.setText(filename)
            self._start_browse()

    def _choose_build_source(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose calculation output folder",
            str(self.window_ref.workspace_root),
        )
        if directory:
            self.build_source.setText(directory)

    def _choose_build_output(self) -> None:
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Choose new database destination",
            str(self.window_ref.workspace_root / "chemsmart-results.db"),
            "ChemSmart databases (*.db)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if filename:
            path = Path(filename)
            self.build_output.setText(
                str(
                    path
                    if path.suffix.lower() == ".db"
                    else path.with_suffix(".db")
                )
            )

    def _choose_export_database(self) -> None:
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose export source database",
            str(self.window_ref.workspace_root),
            "ChemSmart databases (*.db);;All files (*)",
        )
        if filename:
            self.export_db_path.setText(filename)
            if not self.file_path.text().strip():
                self.file_path.setText(filename)

    def _choose_export_output(self) -> None:
        suffix = str(self.export_format.currentData())
        label = self.export_format.currentText().split(" —", 1)[0]
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Choose new export destination",
            str(self.window_ref.workspace_root / f"chemsmart-export{suffix}"),
            f"{label} files (*{suffix})",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if filename:
            path = Path(filename)
            self.export_output.setText(
                str(
                    path
                    if path.suffix.lower() == suffix
                    else path.with_suffix(suffix)
                )
            )

    def _resolve_workspace_path(self, raw: str, missing_message: str) -> Path:
        if not raw.strip():
            raise ValueError(missing_message)
        path = Path(raw.strip()).expanduser()
        return (
            path
            if path.is_absolute()
            else self.window_ref.workspace_root / path
        )

    def _current_request(self) -> DatabaseBrowseRequest:
        return DatabaseBrowseRequest(
            db_file=self._resolve_workspace_path(
                self.file_path.text(), "Choose a ChemSmart .db file."
            ),
            target=str(self.target.currentData()),
            query=self.query.text(),
            limit=self.limit.value(),
        )

    def _current_assemble_request(self) -> DatabaseAssembleRequest:
        return DatabaseAssembleRequest(
            input_directory=self._resolve_workspace_path(
                self.build_source.text(), "Choose a calculation output folder."
            ),
            output_file=self._resolve_workspace_path(
                self.build_output.text(), "Choose a new .db destination."
            ),
            program=str(self.build_program.currentData()),
            structure_index=str(self.build_structures.currentData()),
            include_failed=self.build_include_failed.isChecked(),
            continue_on_parse_errors=self.build_continue_errors.isChecked(),
        )

    def _current_export_request(self) -> DatabaseExportRequest:
        db_file = self._resolve_workspace_path(
            self.export_db_path.text(), "Choose an export source database."
        )
        output_file = self._resolve_workspace_path(
            self.export_output.text(), "Choose a new export destination."
        )
        suffix = str(self.export_format.currentData())
        if output_file.suffix.lower() != suffix:
            raise ValueError(
                f"The selected format requires a {suffix} destination."
            )

        scope = str(self.export_scope.currentData())
        selector = self.export_selector.text().strip()
        values = {
            "record_index": None,
            "record_id": None,
            "structure_id": None,
            "molecule_id": None,
        }
        if scope != "whole":
            if not selector:
                raise ValueError("Enter a selection value for this export.")
            if scope == "record_index":
                try:
                    values[scope] = int(selector)
                except ValueError as exc:
                    raise ValueError(
                        "Record index must be a positive integer."
                    ) from exc
            else:
                values[scope] = selector

        csv_keys = tuple(
            key.strip()
            for key in self.export_csv_keys.text().split(",")
            if key.strip()
        )
        structure_index = (
            self.export_structure_index.text().strip() or None
            if scope in {"record_index", "record_id"}
            else None
        )
        method_basis = (
            self.export_method_basis.text().strip() or None
            if scope in {"structure_id", "molecule_id"}
            else None
        )
        return DatabaseExportRequest(
            db_file=db_file,
            output_file=output_file,
            record_index=values["record_index"],
            record_id=values["record_id"],
            structure_index=structure_index,
            structure_id=values["structure_id"],
            molecule_id=values["molecule_id"],
            csv_keys=csv_keys,
            method_basis=method_basis,
        )

    def _start_browse(self) -> None:
        try:
            request = self._current_request()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._detail_controller.cancel()
        self._clear_results()
        self.retry_button.setVisible(False)
        self._browse_controller.start(
            lambda context: self._service.browse(request, context)
        )

    def _start_assemble(self) -> None:
        try:
            request = self._current_assemble_request()
        except ValueError as exc:
            self.build_status.setText(str(exc))
            return
        self.build_receipt.clear()
        self.build_retry_button.setVisible(False)
        self._assemble_controller.start(
            lambda context: self._service.assemble(request, context)
        )

    def _start_export(self) -> None:
        try:
            request = self._current_export_request()
        except ValueError as exc:
            self.export_status.setText(str(exc))
            return
        self.export_receipt.clear()
        self.export_retry_button.setVisible(False)
        self._export_controller.start(
            lambda context: self._service.export(request, context)
        )

    def _retry_browse(self) -> None:
        if self._has_live_tasks():
            self.status.setText(
                "Waiting for the previous database task to finish cleanup."
            )
            return
        self._start_browse()

    def _retry_assemble(self) -> None:
        if self._has_live_tasks():
            self.build_status.setText(
                "Waiting for the previous database task to finish cleanup."
            )
            return
        self._start_assemble()

    def _retry_export(self) -> None:
        if self._has_live_tasks():
            self.export_status.setText(
                "Waiting for the previous database task to finish cleanup."
            )
            return
        self._start_export()

    def _cancel_browse(self) -> None:
        self._browse_controller.cancel()
        self._detail_controller.cancel()

    def _cancel(self) -> None:
        """Compatibility alias for the original browse-only interaction."""

        self._cancel_browse()

    def _cancel_assemble(self) -> None:
        self._assemble_controller.cancel()

    def _cancel_export(self) -> None:
        self._export_controller.cancel()

    @staticmethod
    def _controller_busy(controller) -> bool:
        return (
            controller.snapshot.status in _ACTIVE
            or controller.active_thread_count > 0
        )

    def _has_live_tasks(self) -> bool:
        return any(
            self._controller_busy(controller)
            for controller in self._controllers
        )

    def _on_task_state(self, _snapshot: TaskSnapshot) -> None:
        browse_busy = self._controller_busy(
            self._browse_controller
        ) or self._controller_busy(self._detail_controller)
        build_busy = self._controller_busy(self._assemble_controller)
        export_busy = self._controller_busy(self._export_controller)
        busy = browse_busy or build_busy or export_busy
        self.progress.setVisible(browse_busy)
        self.cancel_button.setVisible(browse_busy)
        self.build_progress.setVisible(build_busy)
        self.build_cancel_button.setVisible(build_busy)
        self.export_progress.setVisible(export_busy)
        self.export_cancel_button.setVisible(export_busy)
        for control in self._request_controls:
            control.setEnabled(not busy)
        self.retry_button.setEnabled(not busy)
        self.build_retry_button.setEnabled(not busy)
        self.export_retry_button.setEnabled(not busy)
        self.window_ref.task_status.setText(
            "Database: working" if busy else "Idle"
        )
        if not busy:
            self._on_export_format_changed()

    def _on_browse_progress(self, progress: TaskProgress) -> None:
        self._set_progress(self.progress, progress)
        if progress.message:
            self.status.setText(progress.message)

    def _on_page(self, page: DatabasePage) -> None:
        self._page = page
        self.file_path.setText(str(page.db_file))
        self.export_db_path.setText(str(page.db_file))
        self.results.setColumnCount(len(page.columns))
        self.results.setHorizontalHeaderLabels(
            [column.label for column in page.columns]
        )
        self.results.setRowCount(len(page.rows))
        for row_index, row in enumerate(page.rows):
            for column_index, column in enumerate(page.columns):
                item = QTableWidgetItem(
                    self._cell_text(column.key, row.value(column.key))
                )
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row)
                self.results.setItem(row_index, column_index, item)
        header = self.results.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if page.columns:
            header.setSectionResizeMode(
                len(page.columns) - 1, QHeaderView.ResizeMode.Stretch
            )
        self.status.setText(self._page_status(page))
        self.window_ref.runtime_evidence.setText(
            f"Read-only database receipt\n{page.db_file.name}\n"
            f"{page.target}: {len(page.rows)}/{page.matched_count} shown"
        )
        if page.rows:
            self.results.selectRow(0)
        else:
            self.detail.setPlainText("No matching entities.")
            self._clear_structure()

    def _load_selected_detail(self) -> None:
        if self._page is None:
            return
        selected = self.results.selectedItems()
        if not selected:
            return
        first = self.results.item(selected[0].row(), 0)
        row = (
            first.data(Qt.ItemDataRole.UserRole) if first is not None else None
        )
        if not isinstance(row, DatabaseRow):
            return
        request = DatabaseDetailRequest(
            db_file=self._page.db_file,
            target=row.target,
            entity_id=row.entity_id,
        )
        self._clear_structure()
        self.detail.setPlainText("Loading structured detail…")
        self._detail_controller.start(
            lambda context: self._service.detail(request, context),
            retain_for_retry=False,
        )

    def _on_detail(self, detail: DatabaseDetail) -> None:
        lines = [detail.title]
        for section in detail.sections:
            lines.extend(("", section.title))
            lines.extend(
                f"{field.label}: {field.value}" for field in section.fields
            )
        self.detail.setPlainText("\n".join(lines))
        if self._page is not None:
            self.status.setText(
                f"{self._page_status(self._page)} Selected detail loaded."
            )
        if detail.structure is None:
            self._clear_structure()
            self.window_ref.inspector_status.setText(
                f"Selected {detail.target[:-1]} has no previewable geometry."
            )
            return
        from chemsmart.io.molecules.structure import Molecule

        preview = detail.structure
        molecule = Molecule(
            symbols=list(preview.symbols),
            positions=list(preview.positions),
            charge=preview.charge,
            multiplicity=preview.multiplicity,
        )
        viewer = self.window_ref.ensure_structure_viewer()
        viewer.load_molecule(molecule)
        self.window_ref.inspector_status.setText(
            f"Previewing {detail.title} from validated structured coordinates."
        )

    def _on_assembled(self, result: DatabaseAssembleResult) -> None:
        skipped = self._summarize_names(result.skipped_files)
        failed = self._summarize_names(result.failed_files)
        dependencies = self._summarize_names(result.dependency_files)
        receipt = (
            "Verified database build\n"
            f"Source folder: {result.input_directory}\n"
            f"Output: {result.output_file}\n"
            f"Programs: {result.program}\n"
            f"Files found: {result.files_found}\n"
            f"Records parsed/stored: {result.records_parsed}/{result.records_stored}\n"
            f"Duplicate records replaced in staging: {result.duplicate_records}\n"
            f"Referenced geometry files: {dependencies}\n"
            f"Referenced geometry bytes: {result.dependency_bytes}\n"
            f"Skipped calculations: {skipped}\n"
            f"Parser failures allowed by user: {failed}\n"
            f"Size: {result.output_bytes} bytes\n"
            f"SHA-256: {result.sha256}\n"
            "Publish policy: new file only; integrity and foreign-key checks passed.\n"
            "Privacy: the database preserves provenance source-file paths; review before sharing."
        )
        self.build_receipt.setPlainText(receipt)
        self.build_status.setText(
            f"Created {result.records_stored} verified records. Opening the new database…"
        )
        self.window_ref.runtime_evidence.setText(receipt)
        self.file_path.setText(str(result.output_file))
        self.export_db_path.setText(str(result.output_file))
        self._pending_browse_path = result.output_file
        self.tabs.setCurrentIndex(0)

    def _open_assembled_when_drained(self) -> None:
        if self._pending_browse_path is None or self._has_live_tasks():
            return
        self.file_path.setText(str(self._pending_browse_path))
        self._pending_browse_path = None
        self._start_browse()

    def _on_exported(self, result: DatabaseExportResult) -> None:
        privacy = (
            "\nPrivacy: JSON includes provenance source-file paths; review before sharing."
            if result.format == ".json"
            else ""
        )
        skipped = self._summarize_names(result.skipped_structure_ids)
        receipt = (
            "Verified database export\n"
            f"Source: {result.db_file}\n"
            f"Output: {result.output_file}\n"
            f"Format: {result.format}\n"
            f"Scope: {result.scope}\n"
            f"Items considered/exported: {result.requested_items}/{result.exported_items}\n"
            f"Skipped structure IDs: {skipped}\n"
            f"Size: {result.output_bytes} bytes\n"
            f"SHA-256: {result.sha256}\n"
            "Publish policy: new file only; staged output validation passed."
            f"{privacy}"
        )
        self.export_receipt.setPlainText(receipt)
        self.export_status.setText(
            f"Exported a verified {result.format} copy."
        )
        self.window_ref.runtime_evidence.setText(receipt)

    def _on_browse_failure(self, failure: TaskFailure) -> None:
        self.status.setText(
            f"Database could not be opened ({failure.diagnostic_type}). "
            "Check the file and filter, then retry."
        )
        self.retry_button.setVisible(True)

    def _on_detail_failure(self, failure: TaskFailure) -> None:
        self.detail.setPlainText(
            f"Selected detail could not be loaded ({failure.diagnostic_type})."
        )
        self._clear_structure()

    def _on_assemble_failure(self, failure: TaskFailure) -> None:
        self.build_status.setText(
            f"Database was not created ({failure.diagnostic_type}). Check the "
            "source files, optional Open Babel support, and unused destination name."
        )
        self.build_retry_button.setVisible(True)

    def _on_export_failure(self, failure: TaskFailure) -> None:
        self.export_status.setText(
            f"Export was not published ({failure.diagnostic_type}). Check the "
            "selection and choose an unused destination name."
        )
        self.export_retry_button.setVisible(True)

    def _on_detail_cancelled(self) -> None:
        self.detail.setPlainText(
            "Selected detail loading was cancelled; no preview was accepted."
        )
        self._clear_structure()

    def _on_browse_cancelled(self) -> None:
        self.status.setText(
            "Database task cancelled. You can adjust the request and retry."
        )
        self.retry_button.setVisible(True)

    def _on_assemble_cancelled(self) -> None:
        self.build_status.setText(
            "Build cancelled before publish. No destination file was created."
        )
        self.build_retry_button.setVisible(True)

    def _on_export_cancelled(self) -> None:
        self.export_status.setText(
            "Export cancelled before publish. No destination file was created."
        )
        self.export_retry_button.setVisible(True)

    def _on_export_format_changed(self) -> None:
        suffix = str(self.export_format.currentData())
        whole_database = suffix in {".json", ".csv"}
        if whole_database:
            self.export_scope.setCurrentIndex(0)
        elif self.export_scope.currentData() == "whole":
            self.export_scope.setCurrentIndex(1)
        self.export_scope.setEnabled(
            not whole_database and not self._has_live_tasks()
        )
        self.export_csv_keys.setEnabled(
            suffix == ".csv" and not self._has_live_tasks()
        )
        self.export_output.setPlaceholderText(f"Choose a new {suffix} file")
        self._on_export_scope_changed()

    def _on_export_scope_changed(self) -> None:
        scope = str(self.export_scope.currentData())
        xyz = str(self.export_format.currentData()) in {".xyz", ".extxyz"}
        idle = not self._has_live_tasks()
        self.export_selector.setEnabled(scope != "whole" and idle)
        self.export_structure_index.setEnabled(
            xyz and scope in {"record_index", "record_id"} and idle
        )
        self.export_method_basis.setEnabled(
            xyz and scope in {"structure_id", "molecule_id"} and idle
        )
        placeholders = {
            "whole": "Not used for complete database export",
            "record_index": "Positive one-based record index",
            "record_id": "Full or unique record ID prefix",
            "structure_id": "Full or unique structure ID prefix",
            "molecule_id": "Molecule InChIKey",
        }
        self.export_selector.setPlaceholderText(placeholders[scope])

    def _clear_results(self) -> None:
        self._page = None
        self.results.clear()
        self.results.setRowCount(0)
        self.results.setColumnCount(0)
        self.detail.clear()
        self._clear_structure()

    def _clear_structure(self) -> None:
        viewer = getattr(self.window_ref, "_structure_viewer", None)
        if viewer is not None:
            viewer.clear_molecule()
            viewer.setVisible(False)

    @staticmethod
    def _cell_text(key: str, value) -> str:
        if value is None:
            return "—"
        if key == "normal_termination":
            return "Normal" if value else "Failed"
        if isinstance(value, float):
            return f"{value:.8g}"
        return str(value)

    @staticmethod
    def _summarize_names(values: tuple[str, ...], limit: int = 8) -> str:
        if not values:
            return "none"
        shown = ", ".join(values[:limit])
        remaining = len(values) - limit
        return f"{shown}, … and {remaining} more" if remaining > 0 else shown

    @staticmethod
    def _page_status(page: DatabasePage) -> str:
        qualifier = " (limited)" if page.truncated else ""
        return (
            f"Showing {len(page.rows)} of {page.matched_count} matching "
            f"{page.target}; {page.total_count} total{qualifier}."
        )

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        per_controller = max(0, timeout_ms // len(self._controllers))
        return all(
            controller.shutdown(per_controller)
            for controller in self._controllers
        )


__all__ = ["DatabaseScreen"]
