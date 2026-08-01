"""Deterministic M2 observations for direct-string versus typed-command IR.

This module deliberately does not call a model, execute a chemistry engine, or
choose a winning frontend.  It projects already captured M1 direct-command
evidence (A0) and a ``CommandWorkflowReceipt`` (A1) into the same path-free
metric record.  M5 owns paired provider trials, costs, confidence intervals,
and any efficacy decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from chemsmart.agent.harness.command_semantics import CommandSemanticResult
from chemsmart.agent.harness.intent import IntentResult
from chemsmart.agent.model_command_parser import parse_model_command


FrontEnd = Literal["A0_direct_string", "A1_typed_ir"]
ObservationStatus = Literal["accepted", "rejected", "not_observed"]
_FIXTURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHELL_MARKERS = (";", "&&", "||", "|", "<", ">", "`", "$(", "${")


@dataclass(frozen=True)
class FrontEndObservation:
    """Path-free result for one frontend on one fixed fixture.

    ``schema_valid`` means the existing strict Click-backed semantic gate did
    not report a schema/parser failure; it does not mean that the calculation
    is scientifically valid.  No command text, provider payload, artifact
    path, native input, or secret is retained in the public observation.
    """

    fixture_id: str
    fixture_sha256: str
    front_end: FrontEnd
    status: ObservationStatus
    schema_valid: bool
    parser_accepted: bool
    safe_preview_ok: bool
    intent_preserved: bool
    canonical_rendering: bool
    native_input_authored: bool
    shell_injection_observed: bool
    hallucinated_option_observed: bool
    repair_count: int
    rule_ids: tuple[str, ...]
    observation_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_sha256": self.fixture_sha256,
            "front_end": self.front_end,
            "status": self.status,
            "schema_valid": self.schema_valid,
            "parser_accepted": self.parser_accepted,
            "safe_preview_ok": self.safe_preview_ok,
            "intent_preserved": self.intent_preserved,
            "canonical_rendering": self.canonical_rendering,
            "native_input_authored": self.native_input_authored,
            "shell_injection_observed": self.shell_injection_observed,
            "hallucinated_option_observed": self.hallucinated_option_observed,
            "repair_count": self.repair_count,
            "rule_ids": list(self.rule_ids),
            "observation_sha256": self.observation_sha256,
        }


@dataclass(frozen=True)
class FrontEndComparison:
    """A same-fixture A0/A1 pairing that is intentionally non-adoptive."""

    fixture_id: str
    fixture_sha256: str
    direct: FrontEndObservation
    typed: FrontEndObservation
    paired: bool
    efficacy_decision: Literal["experimental_not_adopted"]
    decision_reason: str
    comparison_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_sha256": self.fixture_sha256,
            "direct": self.direct.to_dict(),
            "typed": self.typed.to_dict(),
            "paired": self.paired,
            "efficacy_decision": self.efficacy_decision,
            "decision_reason": self.decision_reason,
            "comparison_sha256": self.comparison_sha256,
        }


def observe_direct_command(
    *,
    fixture_id: str,
    fixture_sha256: str,
    semantic: CommandSemanticResult,
    intent: IntentResult,
    parser_cwd: str | None = None,
    repair_count: int = 0,
    native_input_authored: bool = False,
) -> FrontEndObservation:
    """Project a captured A0 direct-string trace without rerunning it.

    The caller must supply the already captured safe-preview and independent
    intent evidence.  This function uses the independent model-command parser
    only to classify the stored command observation; it never sends the string
    to a shell or chemistry program.
    """

    _validate_fixture(fixture_id, fixture_sha256)
    _validate_repair_count(repair_count)
    parsed = parse_model_command(semantic.command, cwd=parser_cwd)
    rule_ids = _unique([*semantic.failed_rule_ids, *intent.failed_rule_ids])
    strict_schema_failure = any(
        rule in {"cmd.semantic.strict_parser", "cmd.semantic.option_order"}
        or rule.startswith("cmd.schema.")
        for rule in rule_ids
    )
    shell = any(marker in semantic.command for marker in _SHELL_MARKERS) or any(
        "shell" in rule or "injection" in rule for rule in rule_ids
    )
    observation = {
        "fixture_id": fixture_id,
        "fixture_sha256": fixture_sha256,
        "front_end": "A0_direct_string",
        "schema_valid": semantic.verdict != "reject" and not strict_schema_failure,
        "parser_accepted": parsed.parse_error is None,
        "safe_preview_ok": semantic.verdict == "ok",
        "intent_preserved": intent.verdict == "ok",
        "canonical_rendering": False,
        "native_input_authored": bool(native_input_authored),
        "shell_injection_observed": shell,
        "hallucinated_option_observed": _hallucinated_option(rule_ids),
        "repair_count": repair_count,
        "rule_ids": list(rule_ids),
    }
    return _observation_from_body(observation)


def observe_typed_workflow(
    *,
    fixture_id: str,
    fixture_sha256: str,
    receipt: Mapping[str, Any],
    repair_count: int = 0,
) -> FrontEndObservation:
    """Project an A1 command-workflow receipt into the same metric surface.

    The receipt is required to be path-free and produced by the deterministic
    compiler path.  A malformed or incomplete receipt becomes
    ``not_observed`` rather than being made comparable to a successful A0
    trace.
    """

    _validate_fixture(fixture_id, fixture_sha256)
    _validate_repair_count(repair_count)
    invocations = receipt.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        return _not_observed(
            fixture_id, fixture_sha256, "A1_typed_ir", repair_count,
            "cmd.ablation.typed_receipt_missing",
        )
    receipt_status = str(receipt.get("status") or "")
    compilation_status = str(receipt.get("compilation_status") or "")
    schema_digest = str(receipt.get("cli_schema_digest") or "")
    render_digest = str(receipt.get("render_digest") or "")
    rule_ids = _receipt_rule_ids(receipt)
    parser_accepted = all(
        isinstance(item, Mapping)
        and isinstance(item.get("parser"), Mapping)
        and item["parser"].get("verdict") == "ok"
        and item["parser"].get("matches_invocation") is True
        for item in invocations
    )
    intent_preserved = all(
        isinstance(item, Mapping)
        and isinstance(item.get("intent"), Mapping)
        and item["intent"].get("verdict") == "ok"
        for item in invocations
    )
    safe_preview_ok = all(
        isinstance(item, Mapping)
        and isinstance(item.get("safe_preview"), Mapping)
        and item["safe_preview"].get("verdict") == "ok"
        for item in invocations
    )
    observation = {
        "fixture_id": fixture_id,
        "fixture_sha256": fixture_sha256,
        "front_end": "A1_typed_ir",
        "schema_valid": (
            compilation_status == "previewable"
            and bool(_SHA256.fullmatch(schema_digest))
        ),
        "parser_accepted": parser_accepted,
        "safe_preview_ok": safe_preview_ok and receipt_status == "previewed",
        "intent_preserved": intent_preserved,
        "canonical_rendering": bool(_SHA256.fullmatch(render_digest)),
        # The typed contract contains no native-input text field.  Its absence
        # is recorded as a contract fact, not inferred from a model response.
        "native_input_authored": False,
        "shell_injection_observed": any(
            "shell" in rule or "injection" in rule for rule in rule_ids
        ),
        "hallucinated_option_observed": _hallucinated_option(rule_ids),
        "repair_count": repair_count,
        "rule_ids": list(rule_ids),
    }
    return _observation_from_body(observation)


def compare_frontends(
    direct: FrontEndObservation,
    typed: FrontEndObservation,
) -> FrontEndComparison:
    """Join one A0 and one A1 observation for a fixed fixture.

    This function intentionally always returns an experimental decision.  It
    cannot see model identity, prompts, cost, task order, or repeated trials,
    so it lacks the preregistered evidence required to declare A1 effective.
    """

    if direct.front_end != "A0_direct_string":
        raise ValueError("direct observation must be A0_direct_string")
    if typed.front_end != "A1_typed_ir":
        raise ValueError("typed observation must be A1_typed_ir")
    paired = (
        direct.fixture_id == typed.fixture_id
        and direct.fixture_sha256 == typed.fixture_sha256
    )
    if not paired:
        raise ValueError("A0 and A1 observations must use the same fixture")
    body = {
        "fixture_id": direct.fixture_id,
        "fixture_sha256": direct.fixture_sha256,
        "direct": direct.to_dict(),
        "typed": typed.to_dict(),
        "paired": True,
        "efficacy_decision": "experimental_not_adopted",
        "decision_reason": (
            "M2 records deterministic fixture evidence only; M5 must run the "
            "frozen paired provider study before any efficacy claim."
        ),
    }
    return FrontEndComparison(
        fixture_id=direct.fixture_id,
        fixture_sha256=direct.fixture_sha256,
        direct=direct,
        typed=typed,
        paired=True,
        efficacy_decision="experimental_not_adopted",
        decision_reason=body["decision_reason"],
        comparison_sha256=_sha256_json(body),
    )


def _observation_from_body(body: Mapping[str, Any]) -> FrontEndObservation:
    status: ObservationStatus
    if all(
        bool(body[field])
        for field in (
            "schema_valid",
            "parser_accepted",
            "safe_preview_ok",
            "intent_preserved",
        )
    ) and not any(
        bool(body[field])
        for field in (
            "native_input_authored",
            "shell_injection_observed",
            "hallucinated_option_observed",
        )
    ):
        status = "accepted"
    else:
        status = "rejected"
    normalized = {**body, "status": status}
    return FrontEndObservation(
        fixture_id=str(normalized["fixture_id"]),
        fixture_sha256=str(normalized["fixture_sha256"]),
        front_end=normalized["front_end"],
        status=status,
        schema_valid=bool(normalized["schema_valid"]),
        parser_accepted=bool(normalized["parser_accepted"]),
        safe_preview_ok=bool(normalized["safe_preview_ok"]),
        intent_preserved=bool(normalized["intent_preserved"]),
        canonical_rendering=bool(normalized["canonical_rendering"]),
        native_input_authored=bool(normalized["native_input_authored"]),
        shell_injection_observed=bool(normalized["shell_injection_observed"]),
        hallucinated_option_observed=bool(
            normalized["hallucinated_option_observed"]
        ),
        repair_count=int(normalized["repair_count"]),
        rule_ids=tuple(str(item) for item in normalized["rule_ids"]),
        observation_sha256=_sha256_json(normalized),
    )


def _not_observed(
    fixture_id: str,
    fixture_sha256: str,
    front_end: FrontEnd,
    repair_count: int,
    rule_id: str,
) -> FrontEndObservation:
    body = {
        "fixture_id": fixture_id,
        "fixture_sha256": fixture_sha256,
        "front_end": front_end,
        "status": "not_observed",
        "schema_valid": False,
        "parser_accepted": False,
        "safe_preview_ok": False,
        "intent_preserved": False,
        "canonical_rendering": False,
        "native_input_authored": False,
        "shell_injection_observed": False,
        "hallucinated_option_observed": False,
        "repair_count": repair_count,
        "rule_ids": [rule_id],
    }
    return FrontEndObservation(
        fixture_id=fixture_id,
        fixture_sha256=fixture_sha256,
        front_end=front_end,
        status="not_observed",
        schema_valid=False,
        parser_accepted=False,
        safe_preview_ok=False,
        intent_preserved=False,
        canonical_rendering=False,
        native_input_authored=False,
        shell_injection_observed=False,
        hallucinated_option_observed=False,
        repair_count=repair_count,
        rule_ids=(rule_id,),
        observation_sha256=_sha256_json(body),
    )


def _receipt_rule_ids(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for finding in receipt.get("compiler_findings") or []:
        if isinstance(finding, Mapping) and isinstance(finding.get("rule_id"), str):
            values.append(finding["rule_id"])
    for invocation in receipt.get("invocations") or []:
        if not isinstance(invocation, Mapping):
            continue
        for finding in invocation.get("findings") or []:
            if isinstance(finding, Mapping) and isinstance(finding.get("rule_id"), str):
                values.append(finding["rule_id"])
        for section in ("intent", "safe_preview"):
            payload = invocation.get(section)
            if isinstance(payload, Mapping):
                values.extend(
                    str(item) for item in payload.get("failed_rule_ids", [])
                )
                values.extend(str(item) for item in payload.get("rule_ids", []))
    return _unique(values)


def _hallucinated_option(rule_ids: Sequence[str]) -> bool:
    return any(
        rule.startswith("cmd.schema.")
        or rule.startswith("cmd.ir.unknown")
        or rule == "cmd.semantic.strict_parser"
        for rule in rule_ids
    )


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _validate_fixture(fixture_id: str, fixture_sha256: str) -> None:
    if not isinstance(fixture_id, str) or _FIXTURE_ID.fullmatch(fixture_id) is None:
        raise ValueError("fixture_id must be a stable identifier")
    if not isinstance(fixture_sha256, str) or _SHA256.fullmatch(fixture_sha256) is None:
        raise ValueError("fixture_sha256 must be a SHA-256 digest")


def _validate_repair_count(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 2:
        raise ValueError("repair_count must be an integer from 0 through 2")


def _sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FrontEndComparison",
    "FrontEndObservation",
    "compare_frontends",
    "observe_direct_command",
    "observe_typed_workflow",
]
