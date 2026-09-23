"""Host-rendered claims over deterministic analysis receipts.

A claim copies one typed quantity -- a number, or a word a program
printed -- from a receipt the host minted. A finding is the session's
own conclusion bound to relations the host evaluated over claims it
rendered: the host owns every value and every truth value in it, and
never the sentence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from chemsmart.agent._contracts import (
    ContractError,
    canonical_data,
    canonical_sha256,
    require_identifier,
    require_sha256,
)

#: Quantity kinds whose value is a word the program printed rather than
#: a number: a stability verdict, an IRC branch word, a functional name.
TEXT_DATA_KINDS = frozenset({"text", "text_vector"})


@dataclass(frozen=True)
class AnalysisReportedQuantityV1:
    """One claim whose value is copied by the host from a typed quantity."""

    claim_id: str
    source_kind: str
    source_receipt_sha256: str
    quantity_id: str
    quantity_value_sha256: str
    display_value: Any
    display_unit: str
    canonical_value: Any
    canonical_unit: str
    dimension: tuple[int, ...]
    data_kind: str
    #: What the session attributes as this number's uncertainty, in the
    #: display unit, and whether it was measured here, inferred from a
    #: cited receipt, or asserted. Part of the claim rather than beside
    #: it: a number and the uncertainty its author gives it are one
    #: statement, so a corrected uncertainty is a different claim with a
    #: different receipt. While it lived outside the record, re-claiming
    #: with a corrected uncertainty produced the same digest, the same
    #: idempotency key and a different payload, and the event store
    #: refused it -- which made "claim it again with the uncertainty you
    #: measured", the route the sufficiency wake offers, unwalkable.
    uncertainty: float | None = None
    uncertainty_basis: str = ""
    #: Where the magnitude came from, and the terms it was built from.
    #: The host resolved the reference against its own receipt
    #: registries before admitting the word `measured` or `inferred`,
    #: and then dropped it: the only durable trace was one boolean, so
    #: nothing afterwards -- a human, a later cycle, an auditor --
    #: could ask which receipt backed the number that discharged the
    #: contract. They ride inside the digest for the same reason the
    #: uncertainty does: re-claiming the same value with a corrected
    #: budget must be a different receipt, not an idempotency
    #: collision.
    uncertainty_reference: str = ""
    uncertainty_components: tuple[Any, ...] = ()
    #: What the host observed about the cited magnitude while resolving
    #: it, and did not rule on. Three of these were refusals until the
    #: boundary was drawn (owner ruling, 2026-09-10): a chain naming a
    #: number the session supplied, a spread over a single receipt, and
    #: a magnitude of exactly zero. Each rejected legitimate science --
    #: a variance over many samples in one receipt, an equality symmetry
    #: enforces, a coefficient a definition fixes -- and none prevented
    #: the substitution it was aimed at, because an equivalent spelling
    #: walks past all three. So the host reports what it saw and the
    #: session owns what it means. They ride inside the digest with the
    #: reference and the components: what the host observed about a
    #: number is part of the statement that number appears in.
    uncertainty_observations: tuple[str, ...] = ()
    #: How the session combined its components into the total, what its
    #: inputs mean, what coverage the total claims, and what it assumes
    #: about dependence between the terms. The host copies it, renders
    #: it beside the verdict, and grades none of it: how the terms add
    #: is the science.
    #:
    #: Three windows in a row had the combination rule, not the
    #: evidence, decide the word: identical components gave a
    #: root-sum-square inside the tolerance and a linear sum outside it,
    #: and nothing in the assessment, the record or the settlement named
    #: which had produced the number a human read. Detecting a `sqrt`
    #: node would be the syntactic version -- an equivalent spelling
    #: walks past it -- and any host arithmetic relating a total to its
    #: components is forbidden, because magnitudes are signed and
    #: correlated terms may legitimately cancel. So the session declares
    #: it and the host carries it (SUFFICIENCY-5, 2026-09-10).
    uncertainty_combination: Mapping[str, Any] | None = None
    #: When this number approximates the declared quantity rather than
    #: being it: which declaration, by what relationship, on what
    #: basis. The relationship is the session's own words -- the host
    #: ships no closed vocabulary of chemistry kinds and never infers
    #: one from an identifier.
    #:
    #: A live claim delivered `quartet-minus-doublet-u0k-kjmol` against
    #: a declaration of `delta-g-quartet-minus-doublet`: a zero-point
    #: corrected electronic difference, evaluated on a structure the
    #: host had itself typed a first-order saddle, answering a
    #: declaration about a Gibbs difference between minima. Same id,
    #: same dimension, different quantity -- and the expectation row
    #: printed `agreed`. The number stays delivered, because a refusal
    #: that buries a finding is a defect in the refusal; what stops is
    #: the host asserting an unqualified agreement over an
    #: approximation (SUFFICIENCY-5, 2026-09-10).
    approximates: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        require_identifier(self.claim_id, "claim_id")
        if self.uncertainty_reference and self.uncertainty is None:
            raise ContractError(
                "an uncertainty_reference belongs to an uncertainty"
            )
        if self.source_kind not in {
            "quantity_extraction",
            "thermochemistry",
            "quantity_expression",
            "scientific_validation",
        }:
            raise ContractError("unsupported analysis claim source kind")
        require_sha256(self.source_receipt_sha256, "source_receipt_sha256")
        require_identifier(self.quantity_id, "quantity_id")
        require_sha256(self.quantity_value_sha256, "quantity_value_sha256")
        if self.uncertainty is not None:
            if float(self.uncertainty) < 0.0:
                raise ContractError(
                    "an uncertainty is a magnitude in the claim's display "
                    "unit and cannot be negative"
                )
            if self.uncertainty_basis not in {
                "measured",
                "inferred",
                "asserted",
            }:
                raise ContractError(
                    "an uncertainty needs uncertainty_basis: measured, "
                    "inferred, or asserted"
                )
        if len(self.dimension) not in {6, 7, 8, 9, 10} or not all(
            isinstance(value, int) for value in self.dimension
        ):
            raise ContractError(
                "analysis claim dimension must contain six legacy, seven "
                "dipole-extended, eight mass-extended, nine charge-extended, "
                "or ten ir-intensity-extended integers"
            )
        if self.data_kind in TEXT_DATA_KINDS:
            # A word the program printed, copied as the host read it. It
            # has no unit to convert and no magnitude to be uncertain
            # about; what it may never be is empty or a number in
            # disguise.
            _require_text_payload(self.display_value, "display_value")
            _require_text_payload(self.canonical_value, "canonical_value")
            if self.uncertainty is not None:
                raise ContractError("a word carries no uncertainty")
            return
        _require_finite_payload(self.display_value, "display_value")
        _require_finite_payload(self.canonical_value, "canonical_value")
        if not self.display_unit or not self.canonical_unit:
            raise ContractError("analysis claim units must not be empty")


@dataclass(frozen=True)
class AnalysisClaimRecordV1:
    """Task-bound set of exact numerical claims for reporting."""

    schema_version: str
    task_spec_sha256: str
    claims: tuple[AnalysisReportedQuantityV1, ...]
    status: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != "chemsmart.analysis-claim-record.v1":
            raise ContractError("unsupported analysis claim record schema")
        require_sha256(self.task_spec_sha256, "task_spec_sha256")
        if not self.claims:
            raise ContractError("analysis claim record requires claims")
        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if claim_ids != tuple(sorted(set(claim_ids))):
            raise ContractError("analysis claims must be sorted and unique")
        if self.status != "recorded":
            raise ContractError(
                "analysis claim record status must be recorded"
            )
        body = analysis_claim_record_body(self)
        if self.receipt_sha256 != canonical_sha256(body):
            raise ContractError("analysis claim record digest mismatch")


def analysis_claim_record_body(
    record: AnalysisClaimRecordV1,
) -> dict[str, Any]:
    return {
        "schema_version": record.schema_version,
        "task_spec_sha256": record.task_spec_sha256,
        "claims": record.claims,
        "status": record.status,
    }


def build_analysis_claim_record(
    *,
    task_spec_sha256: str,
    claims: tuple[AnalysisReportedQuantityV1, ...],
) -> AnalysisClaimRecordV1:
    body = {
        "schema_version": "chemsmart.analysis-claim-record.v1",
        "task_spec_sha256": task_spec_sha256,
        "claims": tuple(sorted(claims, key=lambda claim: claim.claim_id)),
        "status": "recorded",
    }
    return AnalysisClaimRecordV1(**body, receipt_sha256=canonical_sha256(body))


def analysis_claim_record_from_record(
    record: dict[str, Any], *, receipt_sha256: str
) -> AnalysisClaimRecordV1:
    """Rehydrate a host-rendered claim record from a Runtime V2 event."""

    values = dict(record)
    claims = []
    for item in values.get("claims") or ():
        claim = dict(item)
        claim["dimension"] = tuple(claim.get("dimension") or ())
        claim["uncertainty_components"] = tuple(
            claim.get("uncertainty_components") or ()
        )
        claims.append(AnalysisReportedQuantityV1(**claim))
    values["claims"] = tuple(claims)
    return AnalysisClaimRecordV1(**values, receipt_sha256=receipt_sha256)


def _require_text_payload(value: Any, field: str) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise ContractError(f"{field} must be a non-empty word")
        return
    if isinstance(value, (tuple, list)) and value:
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ContractError(f"{field} must be non-empty words")
        return
    raise ContractError(f"{field} must be a word or a list of words")


def _require_finite_payload(value: Any, field: str) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        raise ContractError(f"{field} must be numerical")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ContractError(f"{field} must be finite")
        return
    if isinstance(value, (tuple, list)) and value:
        for item in value:
            _require_finite_payload(item, field)
        return
    raise ContractError(f"{field} must be a finite numerical value or array")


#: The relations a finding may rest on. Orderings compare two scalars
#: of one dimension; equality compares words, or counts, exactly.
FINDING_RELATIONS = ("<", "<=", ">", ">=", "==", "!=")
_ORDERINGS = frozenset({"<", "<=", ">", ">="})


class FindingRelationError(ContractError):
    """A relation that cannot be evaluated on the operands it names."""


def claim_operand(claim: Any, *, claim_record_sha256: str) -> dict[str, Any]:
    """One side of a relation, as the host rendered it in a claim."""

    return {
        "claim_id": str(claim.claim_id),
        "claim_record_sha256": claim_record_sha256,
        "source_kind": str(claim.source_kind),
        "source_receipt_sha256": str(claim.source_receipt_sha256),
        "quantity_id": str(claim.quantity_id),
        "value": canonical_data(claim.display_value),
        "unit": str(claim.display_unit),
        "data_kind": str(claim.data_kind or "scalar"),
    }


def _scalar_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def evaluate_finding_relation(
    left: Any,
    relation: str,
    *,
    left_record_sha256: str,
    right: Any = None,
    right_record_sha256: str = "",
    literal: Any = None,
    literal_unit: str = "",
) -> dict[str, Any]:
    """Evaluate one relation over values the host rendered.

    ``left`` and ``right`` are claims; ``literal`` is a number or a word
    the session supplies, recorded as the session's. Numbers are compared
    in the left claim's display unit after the host's own conversion;
    words are compared case-insensitively. Nothing here reads the
    finding's sentence.
    """

    from chemsmart.analysis.quantity_expressions import (
        QuantityExpressionError,
        convert_normalized_value,
        normalize_numeric_value,
    )

    if relation not in FINDING_RELATIONS:
        raise FindingRelationError(
            f"relation {relation!r} is not one of {list(FINDING_RELATIONS)}"
        )
    if (right is None) == (literal is None):
        raise FindingRelationError(
            "a relation compares its claim with exactly one of: another "
            "claim (other_claim_id) or a value you state (value)"
        )
    left_kind = str(left.data_kind or "scalar")
    left_value = left.display_value
    row: dict[str, Any] = {
        "left": claim_operand(left, claim_record_sha256=left_record_sha256),
        "relation": relation,
    }
    if left_kind == "text_vector" or (
        right is not None and str(right.data_kind or "") == "text_vector"
    ):
        raise FindingRelationError(
            f"claim {left.claim_id!r} holds a list of words; a relation "
            "reads one word or one number"
        )
    if left_kind == "text":
        if relation not in {"==", "!="}:
            raise FindingRelationError(
                f"claim {left.claim_id!r} is a word; words are compared "
                "with == or !=, never ordered"
            )
        if right is not None:
            if str(right.data_kind or "") != "text":
                raise FindingRelationError(
                    f"claim {left.claim_id!r} is a word and claim "
                    f"{right.claim_id!r} is not"
                )
            other = str(right.display_value)
            row["right"] = claim_operand(
                right, claim_record_sha256=right_record_sha256
            )
        else:
            if not isinstance(literal, str) or not literal.strip():
                raise FindingRelationError(
                    f"claim {left.claim_id!r} is a word; compare it with "
                    "a word"
                )
            other = literal
            row["right"] = {"literal": literal, "supplied_by": "session"}
        equal = str(left_value).strip().casefold() == other.strip().casefold()
        row["holds"] = equal if relation == "==" else not equal
        return row
    if not _scalar_number(left_value):
        raise FindingRelationError(
            f"claim {left.claim_id!r} is not one number; a relation reads "
            "one scalar -- claim the element or the derived value you mean"
        )
    if right is not None:
        if str(right.data_kind or "") in TEXT_DATA_KINDS:
            raise FindingRelationError(
                f"claim {right.claim_id!r} is a word and claim "
                f"{left.claim_id!r} is a number"
            )
        if not _scalar_number(right.display_value):
            raise FindingRelationError(
                f"claim {right.claim_id!r} is not one number"
            )
        try:
            other_value = convert_normalized_value(
                right.canonical_value,
                tuple(right.dimension),
                str(left.display_unit),
            )
        except QuantityExpressionError as exc:
            raise FindingRelationError(
                f"claims {left.claim_id!r} ({left.display_unit}) and "
                f"{right.claim_id!r} ({right.display_unit}) are not one "
                f"dimension: {exc}"
            ) from None
        row["right"] = {
            **claim_operand(right, claim_record_sha256=right_record_sha256),
            "value_in_left_unit": float(other_value),
        }
        integer_pair = (
            left_kind == "integer" and str(right.data_kind or "") == "integer"
        )
    else:
        if not _scalar_number(literal):
            raise FindingRelationError(
                f"claim {left.claim_id!r} is a number; compare it with a "
                "number"
            )
        unit = str(literal_unit or "").strip() or str(left.display_unit)
        if unit != str(left.display_unit):
            try:
                canonical, _unit, dimension = normalize_numeric_value(
                    float(literal), unit
                )
                other_value = convert_normalized_value(
                    canonical, dimension, str(left.display_unit)
                )
            except QuantityExpressionError as exc:
                raise FindingRelationError(
                    f"value {literal!r} {unit!r} cannot be compared with "
                    f"claim {left.claim_id!r} in {left.display_unit!r}: "
                    f"{exc}"
                ) from None
        else:
            other_value = literal
        row["right"] = {
            "literal": canonical_data(literal),
            "unit": unit,
            "value_in_left_unit": float(other_value),
            "supplied_by": "session",
        }
        integer_pair = left_kind == "integer" and float(literal).is_integer()
    if relation in {"==", "!="} and not integer_pair:
        raise FindingRelationError(
            f"claim {left.claim_id!r} is a real number, and two real "
            "numbers are equal only to a precision you choose: state the "
            "band as two relations (> low and < high)"
        )
    a, b = float(left_value), float(other_value)
    row["holds"] = {
        "<": a < b,
        "<=": a <= b,
        ">": a > b,
        ">=": a >= b,
        "==": a == b,
        "!=": a != b,
    }[relation]
    return row


@dataclass(frozen=True)
class AnalysisFindingV1:
    """A conclusion of the session's, bound to relations the host checked.

    The statement is the session's and is never read. Every value in
    ``relations`` was rendered by the host from a claim, every truth
    value was computed by the host, and a relation that did not hold is
    never recorded here: it is refused where it is written, with the
    values the host read. ``host_signals`` names the anomalies the host
    had already recorded on the results this finding's evidence stands
    on, so a finding that restates a sensor is visibly one.

    ``standing`` is the host's, computed from what the evidence is:
    ``answers`` a declared category; ``on_the_request`` when every claim
    it rests on delivers a declaration -- the asked number restated or
    qualified; ``unrequested`` when at least one claim it rests on is
    evidence nobody declared. Only the last is an observation nobody
    asked for (the first development session typed its requested
    distance as a finding and the word said it had seen something).
    """

    schema_version: str
    task_spec_sha256: str
    finding_id: str
    statement: str
    answers_observable_id: str
    standing: str
    relations: tuple[Mapping[str, Any], ...]
    host_signals: tuple[str, ...]
    supersedes_finding_id: str
    receipt_sha256: str
    #: What a finding that answers a declared category delivers: the
    #: words the host read, each with the claim, selector and receipt it
    #: was read through. Empty exactly when the finding answers nothing.
    #: The statement is the session's interpretation of these words.
    answer: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "chemsmart.analysis-finding.v1":
            raise ContractError("unsupported analysis finding schema")
        require_sha256(self.task_spec_sha256, "task_spec_sha256")
        require_identifier(self.finding_id, "finding_id")
        if not str(self.statement).strip():
            raise ContractError("a finding states its conclusion")
        if self.standing not in FINDING_STANDINGS:
            raise ContractError(
                f"finding standing is one of {list(FINDING_STANDINGS)}"
            )
        if bool(self.answers_observable_id) != (self.standing == "answers"):
            raise ContractError(
                "a finding answers a declared question exactly when its "
                "standing says so"
            )
        if bool(self.answers_observable_id) != bool(self.answer):
            raise ContractError(
                "a finding answers a declared question exactly when it "
                "carries the words the host read for it"
            )
        for word in self.answer:
            if not isinstance(word.get("word"), str) or not word.get(
                "source_receipt_sha256"
            ):
                raise ContractError(
                    "a categorical answer is a word the host read, with "
                    "the receipt it was read from"
                )
        if self.answers_observable_id:
            require_identifier(
                self.answers_observable_id, "answers_observable_id"
            )
        if self.supersedes_finding_id:
            require_identifier(
                self.supersedes_finding_id, "supersedes_finding_id"
            )
        if not self.relations:
            raise ContractError(
                "a finding rests on at least one relation the host checked"
            )
        for relation in self.relations:
            if relation.get("holds") is not True:
                raise ContractError(
                    "a finding records only relations the host read as true"
                )
        if self.receipt_sha256 != canonical_sha256(
            analysis_finding_body(self)
        ):
            raise ContractError("analysis finding digest mismatch")


#: What a finding's evidence is, in the host's words.
FINDING_STANDINGS = ("answers", "on_the_request", "unrequested")


def analysis_finding_body(finding: AnalysisFindingV1) -> dict[str, Any]:
    return {
        "schema_version": finding.schema_version,
        "task_spec_sha256": finding.task_spec_sha256,
        "finding_id": finding.finding_id,
        "statement": finding.statement,
        "answers_observable_id": finding.answers_observable_id,
        "standing": finding.standing,
        "relations": finding.relations,
        "host_signals": finding.host_signals,
        "supersedes_finding_id": finding.supersedes_finding_id,
        # Present only on a finding that answers, so a finding minted
        # before the field existed verifies under the same arithmetic.
        **({"answer": finding.answer} if finding.answer else {}),
    }


def build_analysis_finding(
    *,
    task_spec_sha256: str,
    finding_id: str,
    statement: str,
    relations: Sequence[Mapping[str, Any]],
    standing: str,
    answers_observable_id: str = "",
    answer: Sequence[Mapping[str, Any]] = (),
    host_signals: Sequence[str] = (),
    supersedes_finding_id: str = "",
) -> AnalysisFindingV1:
    body = {
        "schema_version": "chemsmart.analysis-finding.v1",
        "task_spec_sha256": task_spec_sha256,
        "finding_id": finding_id,
        "statement": str(statement).strip(),
        "answers_observable_id": str(answers_observable_id or ""),
        "standing": standing,
        "relations": tuple(canonical_data(dict(item)) for item in relations),
        "host_signals": tuple(sorted(set(str(item) for item in host_signals))),
        "supersedes_finding_id": str(supersedes_finding_id or ""),
    }
    words = tuple(canonical_data(dict(item)) for item in answer)
    if words:
        body["answer"] = words
    return AnalysisFindingV1(**body, receipt_sha256=canonical_sha256(body))


def analysis_finding_from_record(
    record: Mapping[str, Any], *, receipt_sha256: str
) -> AnalysisFindingV1:
    """Rehydrate a finding from the decision event that carried it."""

    values = {
        key: record.get(key)
        for key in (
            "schema_version",
            "task_spec_sha256",
            "finding_id",
            "statement",
            "answers_observable_id",
            "standing",
            "supersedes_finding_id",
        )
    }
    values["answers_observable_id"] = str(
        values.get("answers_observable_id") or ""
    )
    values["supersedes_finding_id"] = str(
        values.get("supersedes_finding_id") or ""
    )
    values["relations"] = tuple(
        dict(item) for item in record.get("relations") or ()
    )
    values["host_signals"] = tuple(record.get("host_signals") or ())
    values["answer"] = tuple(dict(item) for item in record.get("answer") or ())
    return AnalysisFindingV1(**values, receipt_sha256=receipt_sha256)


__all__ = [
    "AnalysisClaimRecordV1",
    "AnalysisFindingV1",
    "AnalysisReportedQuantityV1",
    "FINDING_RELATIONS",
    "FINDING_STANDINGS",
    "FindingRelationError",
    "TEXT_DATA_KINDS",
    "analysis_claim_record_body",
    "analysis_claim_record_from_record",
    "analysis_finding_body",
    "analysis_finding_from_record",
    "build_analysis_claim_record",
    "build_analysis_finding",
    "claim_operand",
    "evaluate_finding_relation",
]
