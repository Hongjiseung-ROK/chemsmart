"""Behavior contracts for the P8.1 primitive widgets.

Covers the master-plan gates the primitives must hold before any screen
adopts them: honest progress, safe-by-default decisions, non-color state,
appearance re-theming without rebuild, and a 1,000-cycle state/theme stress.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel

from chemsmart.gui.design.tokens import resolve_tokens
from chemsmart.gui.widgets.actions import (
    DestructiveActionButton,
    LabeledToggle,
    PrimaryActionButton,
    SecondaryActionButton,
    SegmentedModeControl,
)
from chemsmart.gui.widgets.empty_state import EmptyState
from chemsmart.gui.widgets.feedback import (
    TASK_STATES,
    DecisionDialog,
    TaskStrip,
)
from chemsmart.gui.widgets.fields import (
    CommandSurface,
    FieldMessage,
    ScientificValue,
)
from chemsmart.gui.widgets.receipts import DisclosureSection, ReceiptCard
from chemsmart.gui.widgets.status import InlineMessage, StatusBadge

LIGHT = resolve_tokens("light")
DARK = resolve_tokens("dark")
LIGHT_HC = resolve_tokens("light", increased_contrast=True)
DARK_HC = resolve_tokens("dark", increased_contrast=True)
ALL_MODES = (LIGHT, DARK, LIGHT_HC, DARK_HC)


def _all_primitives(tokens):
    return [
        PrimaryActionButton("Generate", icon_name="play", tokens=tokens),
        SecondaryActionButton("Details", tokens=tokens),
        DestructiveActionButton("Discard", tokens=tokens),
        SegmentedModeControl(
            [("a", "Interactive 3D"), ("b", "PyMOL render")], tokens=tokens
        ),
        LabeledToggle("Optional PyMOL", tokens=tokens),
        StatusBadge("verified", "Gate passed", tokens=tokens),
        InlineMessage(
            "warning",
            "Blocked",
            "Pick a project first.",
            action_text="Choose",
            tokens=tokens,
        ),
        TaskStrip(tokens=tokens),
        FieldMessage(tokens=tokens),
        ScientificValue("SHA-256", "d28fe2f3", tokens=tokens),
        CommandSurface("chemsmart run --fake --no-scratch", tokens=tokens),
        ReceiptCard("Receipt", tokens=tokens),
        DisclosureSection("Advanced", QLabel("body"), tokens=tokens),
        EmptyState(
            "flask-conical",
            "No job",
            "Pick a molecule.",
            primary_text="Open",
            secondary_text="Sample",
            tokens=tokens,
        ),
    ]


@pytest.mark.parametrize(
    "mode_tokens", ALL_MODES, ids=("light", "dark", "light-hc", "dark-hc")
)
def test_every_primitive_builds_and_retheme_in_place(
    qapp, mode_tokens
) -> None:
    widgets = _all_primitives(mode_tokens)
    for widget in widgets:
        for other in ALL_MODES:
            widget.apply_tokens(other)
        widget.apply_tokens(mode_tokens)
        assert widget.tokens() is mode_tokens
        widget.deleteLater()


# -- actions ------------------------------------------------------------- #


def test_segmented_control_emits_only_real_changes(qapp) -> None:
    control = SegmentedModeControl([("a", "A"), ("b", "B")], tokens=LIGHT)
    seen: list[str] = []
    control.mode_changed.connect(seen.append)
    control.set_mode("a")  # already current: no event
    control.set_mode("b")
    control.set_mode("b")  # repeated: no event
    assert seen == ["b"]
    assert control.current_mode() == "b"
    with pytest.raises(KeyError):
        control.set_mode("nope")


def test_segmented_control_disabled_mode_names_its_reason(qapp) -> None:
    control = SegmentedModeControl(
        [("a", "A"), ("b", "PyMOL render")], tokens=LIGHT
    )
    control.set_mode_enabled("b", False, "PyMOL is not installed")
    button = control._buttons["b"]
    assert not button.isEnabled()
    assert button.toolTip() == "PyMOL is not installed"
    assert button.accessibleDescription() == "PyMOL is not installed"
    control.set_mode_enabled("b", True)
    assert button.isEnabled() and button.toolTip() == ""


def test_labeled_toggle_writes_state_as_text(qapp) -> None:
    toggle = LabeledToggle("Feature", on_text="Enabled", off_text="Disabled")
    assert toggle._state_label.text() == "Disabled"
    events: list[bool] = []
    toggle.toggled.connect(events.append)
    toggle.set_checked(True)
    assert toggle._state_label.text() == "Enabled"
    assert events == [True]


def test_primary_button_focus_is_visible_on_the_accent_fill(qapp) -> None:
    """Review finding H1: focus_ring == accent made the primary button's
    focus indicator invisible (1:1 contrast on its own fill). The ring now
    uses accent_on_fill, which is contrast-verified against accent."""
    from chemsmart.gui.design.tokens import contrast_ratio

    for mode_tokens in ALL_MODES:
        assert (
            contrast_ratio(mode_tokens.accent_on_fill, mode_tokens.accent)
            >= 3.0
        )
        button = PrimaryActionButton("Generate", tokens=mode_tokens)
        assert mode_tokens.accent_on_fill in button.styleSheet()
        button.deleteLater()

    button = PrimaryActionButton("Generate", tokens=LIGHT)
    button.show()
    button.activateWindow()
    qapp.processEvents()
    # A lone top-level button takes focus on activation; clear it first so
    # the "unfocused" snapshot is genuinely unfocused.
    button.clearFocus()
    qapp.processEvents()
    assert not button.hasFocus()
    unfocused = button.grab().toImage()
    button.setFocus()
    qapp.processEvents()
    assert button.hasFocus(), "offscreen focus could not be established"
    focused = button.grab().toImage()
    assert focused != unfocused, "focus produced no visible change"
    button.close()


def test_segmented_control_uses_supported_corner_selectors(qapp) -> None:
    """Review finding L2: Qt QSS ignores :first-child/:last-child, so the
    outer corners must round via explicit object names."""
    control = SegmentedModeControl(
        [("a", "A"), ("b", "B"), ("c", "C")], tokens=LIGHT
    )
    assert ":first-child" not in control.styleSheet()
    assert ":last-child" not in control.styleSheet()
    names = [control._buttons[key].objectName() for key in ("a", "b", "c")]
    assert names == ["SegmentFirst", "SegmentMiddle", "SegmentLast"]
    single = SegmentedModeControl([("only", "Only")], tokens=LIGHT)
    assert single._buttons["only"].objectName() == "SegmentOnly"


# -- status -------------------------------------------------------------- #


def test_status_badge_rejects_unknown_kind(qapp) -> None:
    with pytest.raises(ValueError):
        StatusBadge("sparkly", "??", tokens=LIGHT)
    badge = StatusBadge("info", "Running", tokens=LIGHT)
    with pytest.raises(ValueError):
        badge.set_state("sparkly", "??")


def test_status_badge_updates_accessible_state(qapp) -> None:
    badge = StatusBadge("info", "Running", tokens=LIGHT)
    badge.set_state("danger", "Failed")
    assert badge.kind() == "danger"
    assert badge.text() == "Failed"
    assert badge.accessibleName() == "Failed"
    assert "danger" in badge.accessibleDescription()


def test_inline_message_action_emits_intent(qapp) -> None:
    message = InlineMessage(
        "blocked", "No provider", action_text="Configure", tokens=LIGHT
    )
    fired: list[bool] = []
    message.action_triggered.connect(lambda: fired.append(True))
    message._action.click()
    assert fired == [True]


# -- feedback ------------------------------------------------------------ #


def test_task_strip_progress_is_honest(qapp) -> None:
    strip = TaskStrip(tokens=LIGHT)
    strip.set_task("Validating ORCA input for water.xyz")

    strip.set_state("running", phase="staging workspace")
    assert strip._progress.minimum() == 0
    assert strip._progress.maximum() == 0  # indeterminate without a total

    strip.set_state("running", phase="inspecting", completed=3, total=5)
    assert strip._progress.maximum() == 5
    assert strip._progress.value() == 3

    strip.set_state("running", completed=99, total=5)
    assert strip._progress.value() == 5  # clamped, never over-reports


def test_task_strip_cancel_and_retry_visibility(qapp) -> None:
    strip = TaskStrip(tokens=LIGHT)
    strip.set_state("running", cancellable=True)
    assert strip._cancel_button.isVisibleTo(strip)
    assert strip._cancel_button.isEnabled()

    strip.set_state("cancelling", cancellable=True)
    assert not strip._cancel_button.isEnabled()  # no double-cancel

    strip.set_state("failed", retryable=True)
    assert not strip._cancel_button.isVisibleTo(strip)
    assert strip._retry_button.isVisibleTo(strip)

    strip.set_state("succeeded")
    assert not strip._retry_button.isVisibleTo(strip)

    with pytest.raises(ValueError):
        strip.set_state("exploded")


def test_task_strip_emits_typed_intent(qapp) -> None:
    strip = TaskStrip(tokens=LIGHT)
    cancels: list[bool] = []
    retries: list[bool] = []
    details: list[bool] = []
    strip.cancel_requested.connect(lambda: cancels.append(True))
    strip.retry_requested.connect(lambda: retries.append(True))
    strip.details_toggled.connect(details.append)
    strip.set_state("running", cancellable=True)
    strip._cancel_button.click()
    strip.set_state("failed", retryable=True)
    strip._retry_button.click()
    strip._details_button.click()
    strip._details_button.click()
    assert cancels == [True]
    assert retries == [True]
    assert details == [True, False]


def test_decision_dialog_defaults_to_the_safe_choice(qapp) -> None:
    dialog = DecisionDialog(
        "Allow tool?",
        "The agent asks to read files.",
        [("allow", "Allow", "primary"), ("deny", "Deny", "secondary")],
        safe_choice="deny",
        tokens=DARK,
    )
    assert dialog.chosen() == "deny"
    dialog.reject()  # Escape / close can never grant
    assert dialog.chosen() == "deny"


def test_decision_dialog_records_an_explicit_choice(qapp) -> None:
    dialog = DecisionDialog(
        "Allow tool?",
        "body",
        [("allow", "Allow", "primary"), ("deny", "Deny", "secondary")],
        safe_choice="deny",
        tokens=LIGHT,
    )
    dialog._choose("allow")
    assert dialog.chosen() == "allow"


def test_decision_dialog_validates_choices(qapp) -> None:
    with pytest.raises(ValueError):
        DecisionDialog(
            "t",
            "b",
            [("a", "A", "primary")],
            safe_choice="missing",
            tokens=LIGHT,
        )
    with pytest.raises(ValueError):
        DecisionDialog(
            "t",
            "b",
            [("a", "A", "sparkly")],
            safe_choice="a",
            tokens=LIGHT,
        )


def test_decision_dialog_body_contrast_in_dark_mode(qapp) -> None:
    """Regression for the P8.0 finding: dark-mode decision text invisible."""
    from chemsmart.gui.design.tokens import contrast_ratio

    dialog = DecisionDialog(
        "Allow?",
        "body",
        [("deny", "Deny", "secondary")],
        safe_choice="deny",
        tokens=DARK,
    )
    ratio = contrast_ratio(DARK.text_primary, DARK.elevated)
    assert ratio >= 4.5
    assert DARK.elevated.lower() in dialog.styleSheet().lower()


# -- fields -------------------------------------------------------------- #


def test_field_message_kinds_and_clearing(qapp) -> None:
    message = FieldMessage(tokens=LIGHT)
    assert not message.isVisibleTo(None)
    message.set_message("error", "Charge must be an integer")
    assert message.kind() == "error"
    assert message.text() == "Charge must be an integer"
    message.clear_message()
    assert message.text() == ""
    with pytest.raises(ValueError):
        message.set_message("sparkly", "??")


def test_scientific_value_copies_exactly(qapp) -> None:
    value = ScientificValue("SHA-256", "d28fe2f31721", tokens=LIGHT)
    copies: list[str] = []
    value.copied.connect(copies.append)
    value._on_copy()
    assert copies == ["d28fe2f31721"]
    assert qapp.clipboard().text() == "d28fe2f31721"


def test_command_surface_is_read_only_and_copies_exactly(qapp) -> None:
    command = "chemsmart run --fake --no-scratch gaussian opt -f water.xyz"
    surface = CommandSurface(command, tokens=LIGHT)
    assert surface._edit.isReadOnly()
    copies: list[str] = []
    surface.copied.connect(copies.append)
    surface._on_copy()
    assert copies == [command]
    assert surface.text() == command


# -- receipts ------------------------------------------------------------ #


def test_disclosure_section_toggles_and_reports(qapp) -> None:
    section = DisclosureSection("Advanced", QLabel("body"), tokens=LIGHT)
    events: list[bool] = []
    section.toggled.connect(events.append)
    assert not section.is_expanded()
    section.set_expanded(True)
    section.set_expanded(True)  # idempotent: one event
    section.set_expanded(False)
    assert events == [True, False]


def test_disclosure_section_never_hides_a_blocker(qapp) -> None:
    section = DisclosureSection("Advanced", QLabel("body"), tokens=LIGHT)
    section.set_blocked_note("1 invalid value inside")
    assert section._blocker_badge.isVisibleTo(section)  # visible collapsed
    section.set_expanded(True)
    assert not section._blocker_badge.isVisibleTo(section)  # field shows it
    section.set_expanded(False)
    assert section._blocker_badge.isVisibleTo(section)
    section.set_blocked_note("")
    assert not section._blocker_badge.isVisibleTo(section)


def test_receipt_card_facts_lifecycle(qapp) -> None:
    card = ReceiptCard(
        "Safe preview",
        verdict_kind="verified",
        verdict_text="verified",
        tokens=LIGHT,
    )
    card.add_fact("command", "chemsmart run --fake")
    card.add_fact("hash", "abc123")
    assert card.fact_count() == 2
    card.clear_facts()
    assert card.fact_count() == 0
    card.set_verdict("danger", "gate failed")
    assert card._badge.kind() == "danger"


def test_empty_state_emits_both_intents(qapp) -> None:
    state = EmptyState(
        "flask-conical",
        "No job",
        "Pick a molecule.",
        primary_text="Open",
        secondary_text="Sample",
        tokens=LIGHT,
    )
    fired: list[str] = []
    state.primary_activated.connect(lambda: fired.append("primary"))
    state.secondary_activated.connect(lambda: fired.append("secondary"))
    state._primary.click()
    state._secondary.click()
    assert fired == ["primary", "secondary"]


# -- painted backgrounds ------------------------------------------------- #


def _dominant_color(widget) -> str:
    """The most common rendered pixel color across the whole widget."""
    from collections import Counter

    image = widget.grab().toImage()
    counts = Counter(
        image.pixelColor(x, y).name()
        for x in range(image.width())
        for y in range(image.height())
    )
    return counts.most_common(1)[0][0]


def test_status_badge_paints_its_tint(qapp) -> None:
    """Regression: stylesheet backgrounds on QWidget subclasses were
    intermittently dropped under widget churn, silently erasing status
    pills; surfaces now paint their fill directly (PaintedSurface).

    The uniform pill fill must dominate the rendered pixels; an unpainted
    surface renders the default window fill instead of the semantic tint.
    """
    badge = StatusBadge("verified", "Gate passed", tokens=LIGHT)
    badge.show()
    qapp.processEvents()
    badge.adjustSize()
    dominant = _dominant_color(badge)
    assert (
        dominant == LIGHT.verified.bg
    ), f"pill tint not painted; dominant color is {dominant}"
    badge.close()


def test_inline_message_and_panels_paint_backgrounds(qapp) -> None:
    message = InlineMessage("warning", "Blocked", "body", tokens=LIGHT)
    strip = TaskStrip(tokens=LIGHT)
    card = ReceiptCard("Receipt", tokens=LIGHT)
    for widget, expected in (
        (message, LIGHT.warning.bg),
        (strip, LIGHT.panel),
        (card, LIGHT.panel),
    ):
        widget.resize(400, 80)
        widget.show()
        qapp.processEvents()
        image = widget.grab().toImage()
        seen = {
            image.pixelColor(x, y).name()
            for x in range(4, image.width() - 4, 8)
            for y in range(4, image.height() - 4, 8)
        }
        assert expected in seen, (
            f"{type(widget).__name__} background {expected} not painted;"
            f" saw {len(seen)} colors"
        )
        widget.close()


def test_status_badge_hugs_its_content(qapp) -> None:
    from PySide6.QtWidgets import QSizePolicy

    badge = StatusBadge("info", "Running", tokens=LIGHT)
    assert badge.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Maximum


# -- stress -------------------------------------------------------------- #


def test_thousand_state_and_theme_cycles_stay_consistent(qapp) -> None:
    """1,000 mixed state changes and theme flips without stale style/state."""
    strip = TaskStrip(tokens=LIGHT)
    badge = StatusBadge("info", "start", tokens=LIGHT)
    section = DisclosureSection("Advanced", QLabel("body"), tokens=LIGHT)
    states = list(TASK_STATES)
    kinds = ("info", "verified", "warning", "blocked", "danger", "neutral")
    for i in range(1000):
        strip.set_state(
            states[i % len(states)],
            phase=f"phase {i}",
            cancellable=bool(i % 2),
            retryable=bool(i % 3),
        )
        badge.set_state(kinds[i % len(kinds)], f"state {i}")
        section.set_expanded(i % 2 == 0)
        mode = ALL_MODES[i % len(ALL_MODES)]
        for widget in (strip, badge, section):
            widget.apply_tokens(mode)
    assert strip.state() == states[999 % len(states)]
    assert badge.text() == "state 999"
    assert badge.kind() == kinds[999 % len(kinds)]
    assert not section.is_expanded()
