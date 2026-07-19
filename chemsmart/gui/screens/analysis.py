"""Native ChemSmart analysis surface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.application.analysis_models import (
    ENERGY_UNITS,
    GROUPER_STRATEGIES,
    IGNORE_HYDROGENS_STRATEGIES,
    MAX_WBI_ATOM_FILTER,
    DIASRequest,
    DIASResult,
    GrouperGroup,
    GrouperRequest,
    GrouperResult,
    ThermochemistryRequest,
    ThermochemistryResult,
    WBIRequest,
    WBIResult,
)
from chemsmart.gui.application.task_controller import (
    QtTaskController,
    TaskFailure,
    TaskProgress,
    TaskSnapshot,
    TaskStatus,
)
from chemsmart.gui.services.analysis_service import AnalysisService

_ACTIVE = {TaskStatus.RUNNING, TaskStatus.CANCELLING}

_THRESHOLD_METADATA = {
    "rmsd": (0.5, " Å", "RMSD distance in angstroms; lower is more similar"),
    "hrmsd": (
        0.5,
        " Å",
        "Hungarian RMSD distance in angstroms; lower is more similar",
    ),
    "spyrmsd": (
        0.5,
        " Å",
        "SpyRMSD distance in angstroms; lower is more similar",
    ),
    "irmsd": (
        0.125,
        " Å",
        "Invariant RMSD distance in angstroms; lower is more similar",
    ),
    "tanimoto": (
        0.9,
        "",
        "Dimensionless Tanimoto similarity; higher is more similar",
    ),
    "torsion": (
        0.1,
        "",
        "Dimensionless torsion fingerprint deviation; lower is more similar",
    ),
    "energy": (
        1.0,
        " kcal/mol",
        "Energy-difference threshold in kilocalories per mole",
    ),
}


class AnalysisScreen(QWidget):
    def __init__(self, window, service: AnalysisService | None = None) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self._service = service or AnalysisService()
        self._controller = QtTaskController[ThermochemistryResult](self)
        self._grouper_controller = QtTaskController[GrouperResult](self)
        self._population_controller = QtTaskController[DIASResult | WBIResult](
            self
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.addWidget(QLabel("Analysis", objectName="ScreenTitle"))
        subtitle = QLabel(
            "Compute structured results with ChemSmart's existing scientific "
            "libraries. Analysis does not launch Gaussian, ORCA, or HPC jobs.",
            objectName="ScreenSubtitle",
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Analysis workflow")
        self.tabs.addTab(self._build_thermochemistry(), "Thermochemistry")
        self.tabs.addTab(self._build_grouper(), "Grouper")
        self.tabs.addTab(self._build_dias_wbi(), "DIAS / WBI")
        root.addWidget(self.tabs, stretch=1)

        self._controller.state_changed.connect(self._on_state)
        self._controller.progress_changed.connect(self._on_progress)
        self._controller.succeeded.connect(self._on_result)
        self._controller.failed.connect(self._on_failure)
        self._controller.cancelled.connect(self._on_cancelled)
        self._grouper_controller.state_changed.connect(self._on_state)
        self._grouper_controller.progress_changed.connect(
            self._on_grouper_progress
        )
        self._grouper_controller.succeeded.connect(self._on_grouper_result)
        self._grouper_controller.failed.connect(self._on_grouper_failure)
        self._grouper_controller.cancelled.connect(self._on_grouper_cancelled)
        self._population_controller.state_changed.connect(self._on_state)
        self._population_controller.progress_changed.connect(
            self._on_population_progress
        )
        self._population_controller.succeeded.connect(
            self._on_population_result
        )
        self._population_controller.failed.connect(self._on_population_failure)
        self._population_controller.cancelled.connect(
            self._on_population_cancelled
        )

    def _build_thermochemistry(self) -> QWidget:
        panel = QWidget()
        panel_root = QVBoxLayout(panel)
        panel_root.setContentsMargins(0, 0, 0, 0)
        controls = QWidget()
        root = QVBoxLayout(controls)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        file_actions = QHBoxLayout()
        add = QPushButton("Add output files…")
        add.setAccessibleName("Add Gaussian or ORCA output files")
        add.clicked.connect(self._choose_files)
        self.remove_files = QPushButton("Remove selected")
        self.remove_files.setAccessibleName(
            "Remove selected thermochemistry files"
        )
        self.remove_files.clicked.connect(self._remove_selected_files)
        file_actions.addWidget(add)
        file_actions.addWidget(self.remove_files)
        file_actions.addStretch(1)
        root.addLayout(file_actions)
        self.add_files_button = add

        self.files = QListWidget()
        self.files.setAccessibleName("Thermochemistry output files")
        self.files.setMinimumHeight(80)
        self.files.setMaximumHeight(100)
        root.addWidget(self.files)

        form = self._responsive_form()
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.01, 5000.0)
        self.temperature.setDecimals(2)
        self.temperature.setValue(298.15)
        self.temperature.setSuffix(" K")
        self.temperature.setAccessibleName("Temperature in kelvin")
        self.pressure = QDoubleSpinBox()
        self.pressure.setRange(0.000001, 100000.0)
        self.pressure.setDecimals(6)
        self.pressure.setValue(1.0)
        self.pressure.setSuffix(" atm")
        self.pressure.setAccessibleName("Pressure in atmospheres")
        self.concentration_enabled = QCheckBox("Use solution concentration")
        self.concentration_enabled.setAccessibleName(
            "Use solution concentration correction"
        )
        self.concentration = QDoubleSpinBox()
        self.concentration.setRange(0.000001, 100000.0)
        self.concentration.setDecimals(6)
        self.concentration.setValue(1.0)
        self.concentration.setSuffix(" mol/L")
        self.concentration.setEnabled(False)
        self.concentration_enabled.toggled.connect(
            self.concentration.setEnabled
        )
        self.energy_units = QComboBox()
        self.energy_units.addItems(ENERGY_UNITS)
        self.energy_units.setAccessibleName("Thermochemistry energy units")
        self.weighted_mass = QCheckBox("Use natural-abundance masses")
        self.weighted_mass.setAccessibleName(
            "Use natural-abundance weighted atomic masses"
        )
        self.weighted_mass.setChecked(True)
        self.check_imaginary = QCheckBox("Reject invalid imaginary modes")
        self.check_imaginary.setAccessibleName(
            "Reject invalid imaginary frequencies"
        )
        self.check_imaginary.setChecked(True)
        form.addRow("Temperature", self.temperature)
        form.addRow("Pressure", self.pressure)
        form.addRow("Solution correction", self.concentration_enabled)
        form.addRow("Concentration", self.concentration)
        form.addRow("Energy units", self.energy_units)
        form.addRow("Masses", self.weighted_mass)
        form.addRow("Frequency safety", self.check_imaginary)

        self.entropy_method = QComboBox()
        self.entropy_method.setAccessibleName("Entropy correction method")
        self.entropy_method.addItem("No entropy correction", "none")
        self.entropy_method.addItem("Grimme quasi-RRHO", "grimme")
        self.entropy_method.addItem("Truhlar quasi-RRHO", "truhlar")
        self.entropy_cutoff = QDoubleSpinBox()
        self.entropy_cutoff.setAccessibleName(
            "Entropy frequency cutoff in inverse centimetres"
        )
        self.entropy_cutoff.setRange(1.0, 10000.0)
        self.entropy_cutoff.setValue(100.0)
        self.entropy_cutoff.setSuffix(" cm⁻¹")
        self.entropy_cutoff.setEnabled(False)
        self.entropy_method.currentIndexChanged.connect(
            lambda: self.entropy_cutoff.setEnabled(
                self.entropy_method.currentData() != "none"
            )
        )
        self.enthalpy_enabled = QCheckBox("Head-Gordon correction")
        self.enthalpy_enabled.setAccessibleName(
            "Use Head-Gordon enthalpy correction"
        )
        self.enthalpy_cutoff = QDoubleSpinBox()
        self.enthalpy_cutoff.setAccessibleName(
            "Enthalpy frequency cutoff in inverse centimetres"
        )
        self.enthalpy_cutoff.setRange(1.0, 10000.0)
        self.enthalpy_cutoff.setValue(100.0)
        self.enthalpy_cutoff.setSuffix(" cm⁻¹")
        self.enthalpy_cutoff.setEnabled(False)
        self.enthalpy_enabled.toggled.connect(self.enthalpy_cutoff.setEnabled)
        self.alpha = QSpinBox()
        self.alpha.setAccessibleName("Quasi-RRHO alpha parameter")
        self.alpha.setRange(1, 20)
        self.alpha.setValue(4)
        form.addRow("Entropy correction", self.entropy_method)
        form.addRow("Entropy cutoff", self.entropy_cutoff)
        form.addRow("Enthalpy correction", self.enthalpy_enabled)
        form.addRow("Enthalpy cutoff", self.enthalpy_cutoff)
        form.addRow("qRRHO alpha", self.alpha)

        self.boltzmann = QCheckBox("Boltzmann-average selected conformers")
        self.boltzmann.setAccessibleName(
            "Boltzmann-average selected conformers"
        )
        self.weighting = QComboBox()
        self.weighting.setAccessibleName("Boltzmann weighting energy")
        self.weighting.addItem("Gibbs free energy", "gibbs")
        self.weighting.addItem("Electronic energy", "electronic")
        self.weighting.setEnabled(False)
        self.boltzmann.toggled.connect(self.weighting.setEnabled)
        form.addRow("Conformer ensemble", self.boltzmann)
        form.addRow("Weighting energy", self.weighting)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.run_button = QPushButton("Compute", objectName="Primary")
        self.run_button.setAccessibleName("Compute thermochemistry")
        self.run_button.clicked.connect(self._run_thermochemistry)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._controller.cancel)
        self.retry_button = QPushButton("Retry")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._retry_thermochemistry)
        actions.addWidget(self.run_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.retry_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Thermochemistry progress")
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status = QLabel("Choose one or more completed output files.")
        self.status.setObjectName("ScreenSubtitle")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.results = QTableWidget(0, 9)
        self.results.setHorizontalHeaderLabels(
            [
                "Structure",
                "E",
                "ZPE",
                "H",
                "qRRHO-H",
                "T·S",
                "qRRHO-T·S",
                "G",
                "qRRHO-G",
            ]
        )
        self.results.setAccessibleName("Thermochemistry structured results")
        self.results.setMinimumHeight(140)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.thermochemistry_scroll = self._scroll_container(
            controls, "Thermochemistry controls"
        )
        panel_root.addWidget(self.thermochemistry_scroll, stretch=3)
        panel_root.addWidget(self.results, stretch=2)
        return panel

    def _build_grouper(self) -> QWidget:
        panel = QWidget()
        panel_root = QVBoxLayout(panel)
        panel_root.setContentsMargins(0, 0, 0, 0)
        controls = QWidget()
        root = QVBoxLayout(controls)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        file_row = QHBoxLayout()
        self.grouper_file = QLineEdit()
        self.grouper_file.setAccessibleName("Multi-structure grouping input")
        self.grouper_file.setPlaceholderText(
            "Choose a multi-structure molecule file"
        )
        choose = QPushButton("Choose…")
        choose.setAccessibleName("Choose multi-structure grouping input")
        choose.clicked.connect(self._choose_grouper_file)
        self.grouper_choose_button = choose
        file_row.addWidget(self.grouper_file, stretch=1)
        file_row.addWidget(choose)
        root.addLayout(file_row)

        form = self._responsive_form()
        self.grouper_strategy = QComboBox()
        self.grouper_strategy.setAccessibleName("Conformer grouping strategy")
        strategy_labels = {
            "rmsd": "RMSD",
            "hrmsd": "Hungarian RMSD",
            "spyrmsd": "SpyRMSD",
            "irmsd": "Invariant RMSD",
            "pymolrmsd": "PyMOL RMSD (P6 optional)",
            "tanimoto": "Tanimoto fingerprint",
            "torsion": "Torsion fingerprint deviation",
            "isomorphism": "RDKit isomorphism",
            "formula": "Chemical formula",
            "connectivity": "Connectivity",
            "energy": "Energy difference",
        }
        for strategy in GROUPER_STRATEGIES:
            self.grouper_strategy.addItem(strategy_labels[strategy], strategy)
        from chemsmart.utils.utils import find_irmsd_command

        irmsd_available = bool(find_irmsd_command(probe_conda=False))
        irmsd_index = GROUPER_STRATEGIES.index("irmsd")
        irmsd_item = self.grouper_strategy.model().item(irmsd_index)
        if irmsd_item is not None and not irmsd_available:
            irmsd_item.setEnabled(False)
            irmsd_item.setToolTip(
                "iRMSD is unavailable because no executable was found in the "
                "standalone app environment."
            )
        pymol_index = GROUPER_STRATEGIES.index("pymolrmsd")
        pymol_item = self.grouper_strategy.model().item(pymol_index)
        if pymol_item is not None:
            pymol_item.setEnabled(False)
            pymol_item.setToolTip(
                "Requires the separately cancellable optional PyMOL boundary in P6."
            )
        self.grouper_strategy.currentIndexChanged.connect(
            self._update_grouper_options
        )

        self.grouping_mode = QComboBox()
        self.grouping_mode.setAccessibleName("Conformer grouping rule")
        self.grouping_mode.addItem("Strategy default", "default")
        self.grouping_mode.addItem("Custom threshold", "threshold")
        self.grouping_mode.addItem("Target number of groups", "groups")
        self.grouping_mode.currentIndexChanged.connect(
            self._update_grouper_options
        )
        self.grouping_threshold = QDoubleSpinBox()
        self.grouping_threshold.setAccessibleName(
            "Conformer grouping threshold"
        )
        self.grouping_threshold.setRange(0.000001, 100000.0)
        self.grouping_threshold.setDecimals(6)
        self.grouping_threshold.setValue(0.5)
        self.grouping_threshold.setEnabled(False)
        self.grouping_count = QSpinBox()
        self.grouping_count.setAccessibleName(
            "Target number of conformer groups"
        )
        self.grouping_count.setRange(1, 2000)
        self.grouping_count.setValue(2)
        self.grouping_count.setEnabled(False)
        self.ignore_hydrogens = QCheckBox(
            "Ignore hydrogen atoms when supported"
        )
        self.ignore_hydrogens.setAccessibleName(
            "Ignore hydrogen atoms when supported"
        )
        self.grouper_workers = QSpinBox()
        self.grouper_workers.setAccessibleName("Conformer grouping workers")
        self.grouper_workers.setRange(1, 8)
        self.grouper_workers.setValue(1)
        self.fingerprint_type = QComboBox()
        self.fingerprint_type.setAccessibleName("Tanimoto fingerprint type")
        self.fingerprint_type.addItems(
            [
                "rdkit",
                "rdk",
                "morgan",
                "maccs",
                "atompair",
                "torsion",
                "usr",
                "usrcat",
            ]
        )
        self.inversion = QComboBox()
        self.inversion.setAccessibleName("Invariant RMSD inversion handling")
        self.inversion.addItems(["auto", "on", "off"])
        self.torsion_weights = QCheckBox("Use torsion weights")
        self.torsion_weights.setAccessibleName("Use torsion weights")
        self.torsion_weights.setChecked(True)
        self.torsion_max_deviation = QComboBox()
        self.torsion_max_deviation.setAccessibleName(
            "Torsion maximum-deviation normalization"
        )
        self.torsion_max_deviation.addItem("Equal normalization", "equal")
        self.torsion_max_deviation.addItem("Specific normalization", "spec")
        form.addRow("Strategy", self.grouper_strategy)
        form.addRow("Grouping rule", self.grouping_mode)
        form.addRow("Custom threshold", self.grouping_threshold)
        form.addRow("Target groups", self.grouping_count)
        form.addRow("Atom selection", self.ignore_hydrogens)
        form.addRow("Workers", self.grouper_workers)
        form.addRow("Tanimoto fingerprint", self.fingerprint_type)
        form.addRow("IRMSD inversion", self.inversion)
        form.addRow("TFD weighting", self.torsion_weights)
        form.addRow("TFD normalization", self.torsion_max_deviation)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.group_button = QPushButton(
            "Group structures", objectName="Primary"
        )
        self.group_button.setAccessibleName("Group conformer structures")
        self.group_button.clicked.connect(self._run_grouper)
        self.group_cancel = QPushButton("Cancel")
        self.group_cancel.setVisible(False)
        self.group_cancel.clicked.connect(self._grouper_controller.cancel)
        self.group_retry = QPushButton("Retry")
        self.group_retry.setVisible(False)
        self.group_retry.clicked.connect(self._retry_grouper)
        actions.addWidget(self.group_button)
        actions.addWidget(self.group_cancel)
        actions.addWidget(self.group_retry)
        actions.addStretch(1)
        root.addLayout(actions)
        self.grouper_progress = QProgressBar()
        self.grouper_progress.setAccessibleName("Conformer grouping progress")
        self.grouper_progress.setVisible(False)
        root.addWidget(self.grouper_progress)
        self.grouper_status = QLabel(
            "Choose a file containing at least two structures.",
            objectName="ScreenSubtitle",
        )
        self.grouper_status.setWordWrap(True)
        root.addWidget(self.grouper_status)
        self.grouper_results = QTableWidget(0, 5)
        self.grouper_results.setHorizontalHeaderLabels(
            ["Group", "Members", "Count", "Representative", "Energy (Eh)"]
        )
        self.grouper_results.setAccessibleName("Conformer grouping results")
        self.grouper_results.setMinimumHeight(140)
        self.grouper_results.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.grouper_results.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.grouper_results.itemSelectionChanged.connect(
            self._show_group_representative
        )
        self.grouper_scroll = self._scroll_container(
            controls, "Conformer grouping controls"
        )
        panel_root.addWidget(self.grouper_scroll, stretch=3)
        panel_root.addWidget(self.grouper_results, stretch=2)
        self._update_grouper_options()
        return panel

    def _build_dias_wbi(self) -> QWidget:
        panel = QWidget()
        panel_root = QVBoxLayout(panel)
        panel_root.setContentsMargins(0, 0, 0, 0)
        controls = QWidget()
        root = QVBoxLayout(controls)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        mode_row = QHBoxLayout()
        self.population_mode = QComboBox()
        self.population_mode.addItem("DIAS energy decomposition", "dias")
        self.population_mode.addItem("WBI / NBO population table", "wbi")
        self.population_mode.setAccessibleName("DIAS or WBI analysis mode")
        self.population_mode.currentIndexChanged.connect(
            self._update_population_mode
        )
        mode_row.addWidget(QLabel("Analysis"))
        mode_row.addWidget(self.population_mode, stretch=1)
        root.addLayout(mode_row)

        path_row = QHBoxLayout()
        self.population_path = QLineEdit()
        self.population_path.setAccessibleName(
            "DIAS folder or WBI output path"
        )
        self.population_choose = QPushButton("Choose…")
        self.population_choose.setAccessibleName(
            "Choose DIAS folder or WBI output"
        )
        self.population_choose.clicked.connect(self._choose_population_path)
        path_row.addWidget(self.population_path, stretch=1)
        path_row.addWidget(self.population_choose)
        root.addLayout(path_row)

        self.population_options = QStackedWidget()
        dias_options = QWidget()
        dias_form = self._responsive_form(dias_options)
        self.dias_program = QComboBox()
        self.dias_program.setAccessibleName("DIAS calculation program")
        self.dias_program.addItem("Detect from folder", "auto")
        self.dias_program.addItem("Gaussian", "gaussian")
        self.dias_program.addItem("ORCA", "orca")
        atom_row = QWidget()
        atom_layout = QHBoxLayout(atom_row)
        atom_layout.setContentsMargins(0, 0, 0, 0)
        self.dias_atom1 = QSpinBox()
        self.dias_atom1.setAccessibleName("First reaction-coordinate atom")
        self.dias_atom1.setRange(1, 100000)
        self.dias_atom1.setValue(5)
        self.dias_atom1.setPrefix("Atom 1: ")
        self.dias_atom2 = QSpinBox()
        self.dias_atom2.setAccessibleName("Second reaction-coordinate atom")
        self.dias_atom2.setRange(1, 100000)
        self.dias_atom2.setValue(7)
        self.dias_atom2.setPrefix("Atom 2: ")
        atom_layout.addWidget(self.dias_atom1)
        atom_layout.addWidget(self.dias_atom2)
        self.dias_zero = QCheckBox("Reference to minimum total energy")
        self.dias_zero.setAccessibleName(
            "Reference DIAS decomposition to the total-energy minimum"
        )
        self.dias_zero.setToolTip(
            "Leaves distortion unchanged and shifts total and interaction by "
            "the same offset, preserving total = distortion + interaction."
        )
        dias_form.addRow("Program", self.dias_program)
        dias_form.addRow("Reaction coordinate", atom_row)
        dias_form.addRow("Energy reference", self.dias_zero)
        self.population_options.addWidget(dias_options)

        wbi_options = QWidget()
        wbi_form = self._responsive_form(wbi_options)
        self.wbi_atoms = QLineEdit()
        self.wbi_atoms.setMaxLength(4096)
        self.wbi_atoms.setAccessibleName("Optional WBI atom index filter")
        self.wbi_atoms.setPlaceholderText("Optional, for example 1, 2, 10-14")
        wbi_form.addRow("Atom indices", self.wbi_atoms)
        explanation = QLabel(
            "Displays Natural Population Analysis, NAO occupancy, and electronic "
            "configuration from Gaussian NBO output. It does not claim a parsed "
            "bond-index matrix.",
            objectName="ScreenSubtitle",
        )
        explanation.setWordWrap(True)
        wbi_form.addRow("Scope", explanation)
        self.population_options.addWidget(wbi_options)
        root.addWidget(self.population_options)

        actions = QHBoxLayout()
        self.population_run = QPushButton("Analyze", objectName="Primary")
        self.population_run.setAccessibleName("Run DIAS or WBI analysis")
        self.population_run.clicked.connect(self._run_population_analysis)
        self.population_cancel = QPushButton("Cancel")
        self.population_cancel.setVisible(False)
        self.population_cancel.clicked.connect(
            self._population_controller.cancel
        )
        self.population_retry = QPushButton("Retry")
        self.population_retry.setVisible(False)
        self.population_retry.clicked.connect(self._retry_population_analysis)
        actions.addWidget(self.population_run)
        actions.addWidget(self.population_cancel)
        actions.addWidget(self.population_retry)
        actions.addStretch(1)
        root.addLayout(actions)
        self.population_progress = QProgressBar()
        self.population_progress.setAccessibleName(
            "DIAS and WBI analysis progress"
        )
        self.population_progress.setVisible(False)
        root.addWidget(self.population_progress)
        self.population_status = QLabel(
            "Choose a completed DIAS folder or Gaussian NBO output.",
            objectName="ScreenSubtitle",
        )
        self.population_status.setWordWrap(True)
        root.addWidget(self.population_status)

        self.population_results = QStackedWidget()
        self.dias_results = QTableWidget(0, 4)
        self.dias_results.setHorizontalHeaderLabels(
            [
                "Coordinate (Å)",
                "Total (kcal/mol)",
                "Distortion (kcal/mol)",
                "Interaction (kcal/mol)",
            ]
        )
        self.dias_results.setAccessibleName("DIAS structured results")
        self.wbi_results = QTableWidget(0, 10)
        self.wbi_results.setHorizontalHeaderLabels(
            [
                "Atom",
                "Natural charge",
                "Core e⁻",
                "Valence e⁻",
                "Rydberg e⁻",
                "Total e⁻",
                "NAOs",
                "NAO occupancy",
                "Element",
                "Electronic configuration",
            ]
        )
        self.wbi_results.setAccessibleName("WBI NBO population results")
        for table in (self.dias_results, self.wbi_results):
            table.setMinimumHeight(140)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            self.population_results.addWidget(table)
        self.population_scroll = self._scroll_container(
            controls, "DIAS and WBI controls"
        )
        panel_root.addWidget(self.population_scroll, stretch=3)
        panel_root.addWidget(self.population_results, stretch=2)
        self._update_population_mode()
        return panel

    @staticmethod
    def _responsive_form(parent: QWidget | None = None) -> QFormLayout:
        form = QFormLayout(parent)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        return form

    @staticmethod
    def _scroll_container(
        content: QWidget, accessible_name: str
    ) -> QScrollArea:
        """Keep scientific controls usable in the supported minimum window."""
        content.setObjectName("ScrollContent")
        scroll = QScrollArea()
        scroll.setAccessibleName(accessible_name)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _update_population_mode(self) -> None:
        mode = str(self.population_mode.currentData())
        index = 0 if mode == "dias" else 1
        self.population_options.setCurrentIndex(index)
        self.population_results.setCurrentIndex(index)
        self.population_path.setPlaceholderText(
            "Choose a folder containing complete DIAS point/fragment outputs"
            if mode == "dias"
            else "Choose a completed Gaussian NBO .log file"
        )

    def _choose_population_path(self) -> None:
        if self.population_mode.currentData() == "dias":
            selected = QFileDialog.getExistingDirectory(
                self,
                "Choose DIAS output folder",
                str(self.window_ref.workspace_root),
            )
        else:
            selected, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Choose Gaussian NBO output",
                str(self.window_ref.workspace_root),
                "Gaussian outputs (*.log);;All files (*)",
            )
        if selected:
            self.population_path.setText(str(Path(selected).resolve()))

    @staticmethod
    def _parse_atom_indices(raw: str) -> tuple[int, ...]:
        if not raw.strip():
            return ()
        if len(raw) > 4096:
            raise ValueError("The atom filter is too long.")
        indices = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                raise ValueError("Remove empty entries from the atom filter.")
            if "-" in token:
                bounds = token.split("-", maxsplit=1)
                if not all(bound.strip().isdigit() for bound in bounds):
                    raise ValueError("Atom ranges use the form 10-14.")
                start, end = (int(bound) for bound in bounds)
                if start > end:
                    raise ValueError("Atom ranges must be in ascending order.")
                span = end - start + 1
                if span > MAX_WBI_ATOM_FILTER - len(indices):
                    raise ValueError(
                        "WBI atom filtering is limited to "
                        f"{MAX_WBI_ATOM_FILTER} indices."
                    )
                indices.extend(range(start, end + 1))
            elif token.isdigit():
                if len(indices) >= MAX_WBI_ATOM_FILTER:
                    raise ValueError(
                        "WBI atom filtering is limited to "
                        f"{MAX_WBI_ATOM_FILTER} indices."
                    )
                indices.append(int(token))
            else:
                raise ValueError(
                    "Atom filters use comma-separated numbers or ranges."
                )
        return tuple(indices)

    def _retry_population_analysis(self) -> None:
        if self._population_controller.active_thread_count:
            self.population_status.setText(
                "Waiting for the previous analysis task to finish cleanup."
            )
            return
        self._run_population_analysis()

    def _run_population_analysis(self) -> None:
        raw_path = self.population_path.text().strip()
        if not raw_path:
            self.population_status.setText("Choose an analysis input first.")
            return
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.window_ref.workspace_root / path
        try:
            if self.population_mode.currentData() == "dias":
                request = DIASRequest(
                    folder=path,
                    atom1=self.dias_atom1.value(),
                    atom2=self.dias_atom2.value(),
                    program=str(self.dias_program.currentData()),
                    zero_reference=self.dias_zero.isChecked(),
                )

                def work(context):
                    return self._service.dias(request, context)

                self.dias_results.setRowCount(0)
            else:
                request = WBIRequest(
                    output_file=path,
                    atom_indices=self._parse_atom_indices(
                        self.wbi_atoms.text()
                    ),
                )

                def work(context):
                    return self._service.wbi(request, context)

                self.wbi_results.setRowCount(0)
        except ValueError as exc:
            self.population_status.setText(str(exc))
            return
        self.population_retry.setVisible(False)
        self._population_controller.start(work)

    def _on_population_progress(self, progress: TaskProgress) -> None:
        if progress.indeterminate:
            self.population_progress.setRange(0, 0)
        else:
            self.population_progress.setRange(0, progress.total or 1)
            self.population_progress.setValue(progress.current or 0)
        if progress.message:
            self.population_status.setText(progress.message)

    def _on_population_result(self, result: DIASResult | WBIResult) -> None:
        if isinstance(result, DIASResult):
            self._show_dias_result(result)
        else:
            self._show_wbi_result(result)

    def _show_dias_result(self, result: DIASResult) -> None:
        self.dias_results.setRowCount(len(result.points))
        for row, point in enumerate(result.points):
            values = (
                point.reaction_coordinate_angstrom,
                point.total_energy_kcal_mol,
                point.distortion_energy_kcal_mol,
                point.interaction_energy_kcal_mol,
            )
            for column, value in enumerate(values):
                self.dias_results.setItem(
                    row, column, QTableWidgetItem(f"{value:.8g}")
                )
        reference = (
            "minimum-referenced with decomposition identity preserved"
            if result.zero_reference
            else "reactant-referenced"
        )
        self.population_status.setText(
            f"Parsed {len(result.points)} {result.program.upper()} DIAS points; "
            f"{reference}. No data or plot files were written."
        )
        self.window_ref.runtime_evidence.setText(
            "DIAS library receipt\n"
            f"{result.folder.name}: {len(result.points)} complete points\n"
            f"atoms {result.atom1}-{result.atom2}; no files written"
        )

    def _show_wbi_result(self, result: WBIResult) -> None:
        self.wbi_results.setRowCount(len(result.atoms))
        for row, atom in enumerate(result.atoms):
            values = (
                atom.label,
                atom.natural_charge,
                atom.core_electrons,
                atom.valence_electrons,
                atom.rydberg_electrons,
                atom.total_electrons,
                atom.nao_count,
                atom.total_nao_occupancy,
                atom.element,
                atom.electronic_configuration,
            )
            for column, value in enumerate(values):
                text = (
                    "—"
                    if value is None
                    else (
                        f"{value:.8g}"
                        if isinstance(value, float)
                        else str(value)
                    )
                )
                self.wbi_results.setItem(row, column, QTableWidgetItem(text))
        version = result.nbo_version or "unknown"
        self.population_status.setText(
            f"Mapped {len(result.atoms)} NBO population rows (NBO {version}). "
            "No result files were written."
        )
        self.window_ref.runtime_evidence.setText(
            "WBI/NBO parser receipt\n"
            f"{result.output_file.name}: {len(result.atoms)} atom rows\n"
            f"NBO {version}; no files written"
        )

    def _on_population_failure(self, failure: TaskFailure) -> None:
        self.population_status.setText(
            f"Analysis failed ({failure.diagnostic_type}). Check that the output "
            "set is complete and the atom indices are valid, then retry."
        )
        self.population_retry.setVisible(True)

    def _on_population_cancelled(self) -> None:
        self.population_status.setText(
            "Analysis cancelled at a parser or atom-mapping checkpoint; no result "
            "was accepted."
        )
        self.population_retry.setVisible(True)

    def _choose_grouper_file(self) -> None:
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose multi-structure molecule file",
            str(self.window_ref.workspace_root),
            "Molecule files (*.xyz *.log *.out);;All files (*)",
        )
        if filename:
            self.grouper_file.setText(str(Path(filename).resolve()))

    def _update_grouper_options(self) -> None:
        strategy = str(self.grouper_strategy.currentData())
        threshold_supported = strategy in _THRESHOLD_METADATA
        mode_model = self.grouping_mode.model()
        for index in (1, 2):
            item = mode_model.item(index)
            if item is not None:
                item.setEnabled(threshold_supported)
        if (
            not threshold_supported
            and self.grouping_mode.currentData() != "default"
        ):
            self.grouping_mode.setCurrentIndex(0)
        mode = self.grouping_mode.currentData()
        self.grouping_threshold.setEnabled(mode == "threshold")
        self.grouping_count.setEnabled(mode == "groups")
        self.fingerprint_type.setEnabled(strategy == "tanimoto")
        self.inversion.setEnabled(strategy == "irmsd")
        self.torsion_weights.setEnabled(strategy == "torsion")
        self.torsion_max_deviation.setEnabled(strategy == "torsion")
        hydrogens_supported = strategy in IGNORE_HYDROGENS_STRATEGIES
        if not hydrogens_supported:
            self.ignore_hydrogens.setChecked(False)
        self.ignore_hydrogens.setEnabled(hydrogens_supported)
        default, suffix, description = _THRESHOLD_METADATA.get(
            strategy,
            (0.5, "", "This strategy has no numeric grouping threshold"),
        )
        self.grouping_threshold.setSuffix(suffix)
        self.grouping_threshold.setAccessibleName(description)
        self.grouping_threshold.setToolTip(description)
        if mode != "threshold":
            self.grouping_threshold.setValue(default)
        if hasattr(self, "grouper_status"):
            if not threshold_supported:
                message = "This strategy uses no numeric grouping threshold."
            elif mode == "groups":
                message = (
                    f"Target-group mode derives a {description.lower()} "
                    "automatically."
                )
            elif mode == "threshold":
                message = f"Custom threshold: {description}."
            else:
                message = (
                    f"Strategy default: {default:g}{suffix}. {description}."
                )
            self.grouper_status.setText(message)

    def _grouper_request(self) -> GrouperRequest:
        raw = self.grouper_file.text().strip()
        if not raw:
            raise ValueError("Choose a multi-structure molecule file.")
        input_file = Path(raw).expanduser()
        if not input_file.is_absolute():
            input_file = self.window_ref.workspace_root / input_file
        mode = self.grouping_mode.currentData()
        strategy = str(self.grouper_strategy.currentData())
        return GrouperRequest(
            input_file=input_file,
            strategy=strategy,
            threshold=(
                self.grouping_threshold.value()
                if mode == "threshold"
                else None
            ),
            num_groups=(
                self.grouping_count.value() if mode == "groups" else None
            ),
            ignore_hydrogens=(
                self.ignore_hydrogens.isChecked()
                and strategy in IGNORE_HYDROGENS_STRATEGIES
            ),
            num_procs=self.grouper_workers.value(),
            fingerprint_type=self.fingerprint_type.currentText(),
            inversion=self.inversion.currentText(),
            torsion_use_weights=self.torsion_weights.isChecked(),
            torsion_max_deviation=str(
                self.torsion_max_deviation.currentData()
            ),
        )

    def _run_grouper(self) -> None:
        try:
            request = self._grouper_request()
        except ValueError as exc:
            self.grouper_status.setText(str(exc))
            return
        self.grouper_results.setRowCount(0)
        self._clear_grouper_preview()
        self.group_retry.setVisible(False)
        self._grouper_controller.start(
            lambda context: self._service.group_structures(request, context)
        )

    def _retry_grouper(self) -> None:
        if self._grouper_controller.active_thread_count:
            self.grouper_status.setText(
                "Waiting for the previous grouping task to finish cleanup."
            )
            return
        self._run_grouper()

    def _on_grouper_progress(self, progress: TaskProgress) -> None:
        if progress.indeterminate:
            self.grouper_progress.setRange(0, 0)
        else:
            self.grouper_progress.setRange(0, progress.total or 1)
            self.grouper_progress.setValue(progress.current or 0)
        if progress.message:
            self.grouper_status.setText(progress.message)

    def _on_grouper_result(self, result: GrouperResult) -> None:
        self.grouper_results.setRowCount(len(result.groups))
        for row_index, group in enumerate(result.groups):
            values = (
                group.group_number,
                ", ".join(str(index) for index in group.member_indices),
                len(group.member_indices),
                group.representative_index,
                group.representative_energy,
            )
            for column, value in enumerate(values):
                text = (
                    "—"
                    if value is None
                    else (
                        f"{value:.10g}"
                        if isinstance(value, float)
                        else str(value)
                    )
                )
                item = QTableWidgetItem(text)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, group)
                self.grouper_results.setItem(row_index, column, item)
        self.grouper_status.setText(
            f"{result.strategy} grouped {result.total_molecules} structures into "
            f"{len(result.groups)} groups. No result files were written."
        )
        self.window_ref.runtime_evidence.setText(
            "Grouper library receipt\n"
            f"{result.input_file.name}: {result.total_molecules} structures\n"
            f"{result.strategy}: {len(result.groups)} groups; no files written"
        )
        if result.groups:
            self.grouper_results.selectRow(0)
        else:
            self._clear_grouper_preview()

    def _show_group_representative(self) -> None:
        selected = self.grouper_results.selectedItems()
        if not selected:
            return
        first = self.grouper_results.item(selected[0].row(), 0)
        group = (
            first.data(Qt.ItemDataRole.UserRole) if first is not None else None
        )
        if not isinstance(group, GrouperGroup):
            return
        from chemsmart.io.molecules.structure import Molecule

        preview = group.preview
        molecule = Molecule(
            symbols=list(preview.symbols),
            positions=list(preview.positions),
            charge=preview.charge,
            multiplicity=preview.multiplicity,
        )
        viewer = self.window_ref.ensure_structure_viewer()
        viewer.load_molecule(molecule)
        self.window_ref.inspector_status.setText(
            f"Previewing representative structure {group.representative_index} "
            f"from group {group.group_number}."
        )

    def _on_grouper_failure(self, failure: TaskFailure) -> None:
        self._clear_grouper_preview()
        self.grouper_status.setText(
            f"Grouping failed ({failure.diagnostic_type}). Check structure "
            "compatibility, energies, and strategy options, then retry."
        )
        self.group_retry.setVisible(True)

    def _on_grouper_cancelled(self) -> None:
        self._clear_grouper_preview()
        self.grouper_status.setText(
            "Grouping cancelled at a comparison checkpoint; no result was accepted."
        )
        self.group_retry.setVisible(True)

    def _clear_grouper_preview(self) -> None:
        viewer = getattr(self.window_ref, "_structure_viewer", None)
        if viewer is not None:
            viewer.clear_molecule()
            viewer.setVisible(False)

    def _choose_files(self) -> None:
        filenames, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Choose completed Gaussian or ORCA outputs",
            str(self.window_ref.workspace_root),
            "Calculation outputs (*.log *.out);;All files (*)",
        )
        existing = {
            self.files.item(i).text() for i in range(self.files.count())
        }
        for filename in filenames:
            resolved = str(Path(filename).resolve())
            if resolved not in existing:
                self.files.addItem(resolved)
                existing.add(resolved)

    def _remove_selected_files(self) -> None:
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))

    def _request(self) -> ThermochemistryRequest:
        method = str(self.entropy_method.currentData())
        return ThermochemistryRequest(
            files=tuple(
                Path(self.files.item(index).text())
                for index in range(self.files.count())
            ),
            temperature=self.temperature.value(),
            pressure=self.pressure.value(),
            concentration=(
                self.concentration.value()
                if self.concentration_enabled.isChecked()
                else None
            ),
            use_weighted_mass=self.weighted_mass.isChecked(),
            alpha=self.alpha.value(),
            entropy_method=method,
            entropy_cutoff_cm=(
                self.entropy_cutoff.value() if method != "none" else None
            ),
            enthalpy_cutoff_cm=(
                self.enthalpy_cutoff.value()
                if self.enthalpy_enabled.isChecked()
                else None
            ),
            energy_units=self.energy_units.currentText(),
            check_imaginary_frequencies=self.check_imaginary.isChecked(),
            boltzmann_average=self.boltzmann.isChecked(),
            weighting_energy=str(self.weighting.currentData()),
        )

    def _run_thermochemistry(self) -> None:
        try:
            request = self._request()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.results.setRowCount(0)
        self.retry_button.setVisible(False)
        self._controller.start(
            lambda context: self._service.thermochemistry(request, context)
        )

    def _retry_thermochemistry(self) -> None:
        if self._controller.active_thread_count:
            self.status.setText(
                "Waiting for the previous thermochemistry task to finish cleanup."
            )
            return
        self._run_thermochemistry()

    def _on_state(self, snapshot: TaskSnapshot) -> None:
        del snapshot
        thermochemistry_busy = (
            self._controller.snapshot.status in _ACTIVE
            or self._controller.active_thread_count > 0
        )
        grouper_busy = (
            self._grouper_controller.snapshot.status in _ACTIVE
            or self._grouper_controller.active_thread_count > 0
        )
        population_busy = (
            self._population_controller.snapshot.status in _ACTIVE
            or self._population_controller.active_thread_count > 0
        )
        busy = thermochemistry_busy or grouper_busy or population_busy
        self.progress.setVisible(thermochemistry_busy)
        self.cancel_button.setVisible(thermochemistry_busy)
        self.run_button.setEnabled(not busy)
        self.add_files_button.setEnabled(not busy)
        self.remove_files.setEnabled(not busy)
        self.grouper_progress.setVisible(grouper_busy)
        self.group_cancel.setVisible(grouper_busy)
        self.group_button.setEnabled(not busy)
        self.grouper_choose_button.setEnabled(not busy)
        self.population_progress.setVisible(population_busy)
        self.population_cancel.setVisible(population_busy)
        self.population_run.setEnabled(not busy)
        self.population_choose.setEnabled(not busy)
        self.retry_button.setEnabled(not busy)
        self.group_retry.setEnabled(not busy)
        self.population_retry.setEnabled(not busy)
        request_controls = (
            self.files,
            self.temperature,
            self.pressure,
            self.concentration_enabled,
            self.energy_units,
            self.weighted_mass,
            self.check_imaginary,
            self.entropy_method,
            self.enthalpy_enabled,
            self.alpha,
            self.boltzmann,
            self.grouper_file,
            self.grouper_strategy,
            self.grouping_mode,
            self.grouper_workers,
            self.population_mode,
            self.population_path,
            self.dias_program,
            self.dias_atom1,
            self.dias_atom2,
            self.dias_zero,
            self.wbi_atoms,
        )
        for control in request_controls:
            control.setEnabled(not busy)
        if busy:
            for dependent in (
                self.concentration,
                self.entropy_cutoff,
                self.enthalpy_cutoff,
                self.weighting,
                self.grouping_threshold,
                self.grouping_count,
                self.ignore_hydrogens,
                self.fingerprint_type,
                self.inversion,
                self.torsion_weights,
                self.torsion_max_deviation,
            ):
                dependent.setEnabled(False)
        else:
            self.concentration.setEnabled(
                self.concentration_enabled.isChecked()
            )
            self.entropy_cutoff.setEnabled(
                self.entropy_method.currentData() != "none"
            )
            self.enthalpy_cutoff.setEnabled(self.enthalpy_enabled.isChecked())
            self.weighting.setEnabled(self.boltzmann.isChecked())
            strategy = str(self.grouper_strategy.currentData())
            mode = self.grouping_mode.currentData()
            self.grouping_threshold.setEnabled(mode == "threshold")
            self.grouping_count.setEnabled(mode == "groups")
            self.ignore_hydrogens.setEnabled(
                strategy in IGNORE_HYDROGENS_STRATEGIES
            )
            self.fingerprint_type.setEnabled(strategy == "tanimoto")
            self.inversion.setEnabled(strategy == "irmsd")
            self.torsion_weights.setEnabled(strategy == "torsion")
            self.torsion_max_deviation.setEnabled(strategy == "torsion")
        self.window_ref.task_status.setText(
            "Analysis: working" if busy else "Idle"
        )

    def _on_progress(self, progress: TaskProgress) -> None:
        if progress.indeterminate:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, progress.total or 1)
            self.progress.setValue(progress.current or 0)
        if progress.message:
            self.status.setText(progress.message)

    def _on_result(self, result: ThermochemistryResult) -> None:
        self.results.setRowCount(len(result.rows))
        for row_index, row in enumerate(result.rows):
            values = (
                row.structure,
                row.electronic_energy,
                row.zero_point_energy,
                row.enthalpy,
                row.qrrho_enthalpy,
                row.entropy_times_temperature,
                row.qrrho_entropy_times_temperature,
                row.gibbs_free_energy,
                row.qrrho_gibbs_free_energy,
            )
            for column, value in enumerate(values):
                text = (
                    "—"
                    if value is None
                    else (
                        f"{value:.8g}"
                        if isinstance(value, float)
                        else str(value)
                    )
                )
                self.results.setItem(row_index, column, QTableWidgetItem(text))
        mode = (
            f"Boltzmann average by {result.weighting_energy}"
            if result.boltzmann_average
            else f"{len(result.rows)} file result(s)"
        )
        concentration = (
            f", {result.concentration:g} mol/L"
            if result.concentration is not None
            else ""
        )
        self.status.setText(
            f"Computed {mode} at {result.temperature:g} K and "
            f"{result.pressure:g} atm{concentration}; energies in "
            f"{result.energy_units}."
        )
        self.window_ref.runtime_evidence.setText(
            "Thermochemistry library receipt\n"
            f"{len(result.files)} input file(s); no calculation launched\n"
            f"{mode}, {result.energy_units}"
        )

    def _on_failure(self, failure: TaskFailure) -> None:
        self.status.setText(
            f"Thermochemistry could not be computed ({failure.diagnostic_type}). "
            "Review the completed outputs and frequency policy, then retry."
        )
        self.retry_button.setVisible(True)

    def _on_cancelled(self) -> None:
        self.status.setText(
            "Analysis cancelled after the active parser boundary; no result was accepted."
        )
        self.retry_button.setVisible(True)

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        per_controller = max(0, timeout_ms // 3)
        return (
            self._controller.shutdown(per_controller)
            and self._grouper_controller.shutdown(per_controller)
            and self._population_controller.shutdown(per_controller)
        )


__all__ = ["AnalysisScreen"]
