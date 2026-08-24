"""The one vocabulary of the host-rendered analysis report.

The writer (the tool host's completed-analysis renderers) and the
terminal reader (``chemsmart.agent.tui.report``) both import these
headings, so their contract is an import rather than a pair of string
literals kept aligned by hand.
"""

HOST_REPORT_TITLE = "# Host-validated structured analysis"

COMPLETION_RECEIPT_LABEL = "Completion receipt"
TOOLCHAIN_PLAN_LABEL = "Toolchain plan"
CLAIM_RECORD_LABEL = "Claim record"

NO_DECISION_PREFIX = "Scientific decision: not recorded"

PARTIAL_STATUS_PREFIX = "Partial analysis"

CONDITIONS_HEADING = "## Task-owned conditions"
THERMO_CONDITIONS_HEADING = "## Thermochemical conditions"
LITERATURE_CONSTANTS_HEADING = "## Literature constants"
CLAIMS_HEADING = "## Host-rendered numerical claims"
FINDINGS_HEADING = "## Analysis nodes that did not execute"
SURVIVING_HEADING = "## Surviving receipts (evidence, not claims)"
VERDICTS_HEADING = "## Validation verdicts"
RECOVERY_PREFIX = "Recovery"

EVIDENCE_COLUMN = "Evidence"
SOURCE_RECEIPT_COLUMN = "Source receipt"

DECISION_SECTIONS = (
    "Method rationale",
    "Assumptions",
    "Diagnostics",
    "Uncertainties",
    "Alternatives",
)
