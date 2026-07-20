"""P8.1 component gallery: every primitive in every appearance mode.

Renders the complete P8.1 primitive vocabulary in representative states and
writes one screenshot per appearance mode plus a JSON receipt with SHA-256
hashes into ``docs/design/evidence/p8_1``. This is presentation evidence
only — no task, provider, chemistry executable, or user configuration is
touched.

Run from the repository root:

    QT_QPA_PLATFORM=offscreen python -m chemsmart.gui.diagnostics.component_gallery
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_MODES = (
    ("light", False),
    ("dark", False),
    ("light-hc", True),
    ("dark-hc", True),
)


def build_gallery(tokens):
    """A scrollable widget holding all primitives in labeled sections."""
    from PySide6.QtWidgets import (
        QLabel,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from chemsmart.gui.design import typography
    from chemsmart.gui.widgets.actions import (
        DestructiveActionButton,
        LabeledToggle,
        PrimaryActionButton,
        SecondaryActionButton,
        SegmentedModeControl,
    )
    from chemsmart.gui.widgets.empty_state import EmptyState
    from chemsmart.gui.widgets.feedback import TaskStrip
    from chemsmart.gui.widgets.fields import (
        CommandSurface,
        FieldMessage,
        ScientificValue,
    )
    from chemsmart.gui.widgets.receipts import (
        DisclosureSection,
        ReceiptCard,
    )
    from chemsmart.gui.widgets.status import InlineMessage, StatusBadge

    content = QWidget()
    content.setObjectName("GalleryContent")
    content.setStyleSheet(
        f"QWidget#GalleryContent {{ background: {tokens.canvas}; }}"
    )
    layout = QVBoxLayout(content)
    pad = typography.SPACE_UNIT * 4
    layout.setContentsMargins(pad, pad, pad, pad)
    layout.setSpacing(typography.SPACE_UNIT * 3)
    scale = typography.type_scale()

    def section(title: str) -> None:
        label = QLabel(title, content)
        label.setStyleSheet(
            f"color: {tokens.text_tertiary}; font-size: {scale.caption}pt;"
            " font-weight: 600; background: transparent;"
        )
        layout.addWidget(label)

    section("GALLERY FIXTURE · NO TASK EXECUTED")

    section("Actions")
    primary = PrimaryActionButton(
        "Generate verified input", icon_name="play", tokens=tokens
    )
    disabled_primary = PrimaryActionButton("Disabled primary", tokens=tokens)
    disabled_primary.setEnabled(False)
    for widget in (
        primary,
        disabled_primary,
        SecondaryActionButton("Details", tokens=tokens),
        DestructiveActionButton("Discard draft", tokens=tokens),
    ):
        layout.addWidget(widget)
    segmented = SegmentedModeControl(
        [("interactive", "Interactive 3D"), ("pymol", "PyMOL render")],
        tokens=tokens,
    )
    segmented.set_mode_enabled("pymol", False, "PyMOL is not installed")
    layout.addWidget(segmented)
    toggle = LabeledToggle("Optional PyMOL rendering", tokens=tokens)
    toggle.set_checked(True)
    layout.addWidget(toggle)

    section("Status")
    for kind, text in (
        ("info", "Running"),
        ("verified", "Gate passed"),
        ("warning", "Waiting for you"),
        ("blocked", "Project required"),
        ("danger", "Failed"),
        ("neutral", "Idle"),
    ):
        layout.addWidget(StatusBadge(kind, text, tokens=tokens))
    layout.addWidget(
        InlineMessage(
            "blocked",
            "No project selected",
            "Safe preview needs a project; choose one to continue.",
            action_text="Choose project",
            tokens=tokens,
        )
    )

    section("Task feedback")
    running = TaskStrip(tokens=tokens)
    running.set_task("Validating ORCA input for water.xyz")
    running.set_state(
        "running",
        phase="invoking frozen-safe CLI",
        completed=3,
        total=5,
        cancellable=True,
    )
    layout.addWidget(running)
    failed = TaskStrip(tokens=tokens)
    failed.set_task("Safe preview for benzene.com")
    failed.set_state("failed", phase="exit status 1", retryable=True)
    layout.addWidget(failed)

    section("Fields and facts")
    field = FieldMessage(tokens=tokens)
    field.set_message("error", "Charge must be an integer")
    layout.addWidget(field)
    layout.addWidget(
        ScientificValue("SHA-256", "d28fe2f31721704b", tokens=tokens)
    )
    layout.addWidget(
        CommandSurface(
            "chemsmart run --fake --no-scratch gaussian opt -f water.xyz",
            tokens=tokens,
        )
    )

    section("Receipts and disclosure")
    card = ReceiptCard(
        "Safe preview receipt",
        verdict_kind="verified",
        verdict_text="verified",
        tokens=tokens,
    )
    card.add_fact("command", "chemsmart run --fake --no-scratch ...")
    card.add_fact("artifact", "water_opt.com")
    layout.addWidget(card)
    disclosure = DisclosureSection(
        "Advanced options", QLabel("advanced content"), tokens=tokens
    )
    disclosure.set_blocked_note("1 invalid value inside")
    layout.addWidget(disclosure)

    section("Empty state")
    layout.addWidget(
        EmptyState(
            "flask-conical",
            "No job yet",
            "Pick a molecule file to start a verified draft.",
            primary_text="Open molecule",
            secondary_text="Use sample",
            tokens=tokens,
        )
    )

    layout.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidget(content)
    scroll.setWidgetResizable(True)
    scroll.resize(760, 1400)
    return scroll


def _save(widget, destination: Path) -> dict[str, Any]:
    image = widget.grab().toImage()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(destination), "PNG"):
        raise RuntimeError(f"could not write screenshot: {destination}")
    data = destination.read_bytes()
    nonblank = 0
    for x in range(0, image.width(), 16):
        for y in range(0, image.height(), 16):
            if image.pixelColor(x, y).alpha() > 0:
                nonblank += 1
    return {
        "path": str(destination),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "width": image.width(),
        "height": image.height(),
        "sampled_nonblank": nonblank,
    }


def main(output_dir: Path | None = None) -> Path:
    from PySide6.QtWidgets import QApplication

    from chemsmart.gui.design.tokens import resolve_tokens

    application = QApplication.instance() or QApplication(sys.argv[:1])
    if output_dir is None:
        output_dir = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "design"
            / "evidence"
            / "p8_1"
        )
    receipt: dict[str, Any] = {"screenshots": {}}
    for mode, increased in _MODES:
        tokens = resolve_tokens(
            mode.split("-")[0], increased_contrast=increased
        )
        gallery = build_gallery(tokens)
        gallery.show()
        application.processEvents()
        receipt["screenshots"][mode] = _save(
            gallery, output_dir / f"component_gallery_{mode}.png"
        )
        gallery.close()
        gallery.deleteLater()
        application.processEvents()
    receipt_path = output_dir / "component_gallery.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt_path


if __name__ == "__main__":
    print(main())
