"""Host-owned immutable source spans for paper protocol extraction.

The model-facing tool accepts only an opaque source identifier, the exact
document digest, and bounded line/column locators. Source text and filesystem paths
remain in a host-owned context so a model cannot promote a paraphrase into
canonical paper evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from chemsmart.agent.project_protocol import (
    ProjectProgram,
    ProjectRenderProfile,
    extract_project_protocol,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_SPANS = 8
_MAX_LINES_PER_SPAN = 200

EVIDENCE_CHARACTER_RANGE_V2_SCHEMA_VERSION = (
    "chemsmart.evidence-character-range.v2"
)

RULE_REGISTRY_MISSING = "paper.source.registry_missing"
RULE_SOURCE_MISSING = "paper.source.not_registered"
RULE_HASH_MISMATCH = "paper.source.sha256_mismatch"
RULE_RANGE_INVALID = "paper.source.line_range_invalid"


class EvidenceCharacterRangeV2(BaseModel):
    """Exact Unicode range inside a string selected by RFC 6901 pointer.

    Offsets are zero-based Unicode code-point offsets with a half-open
    ``[start, end)`` interval.  The artifact hash binds exact JSON bytes; the
    selected-text hash binds the exact UTF-8 bytes of the selected substring.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
        allow_inf_nan=False,
    )

    schema_version: Literal[
        "chemsmart.evidence-character-range.v2"
    ] = EVIDENCE_CHARACTER_RANGE_V2_SCHEMA_VERSION
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    json_pointer: str = Field(max_length=2048)
    unicode_start: int = Field(ge=0)
    unicode_end: int = Field(gt=0)
    selected_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_locator: str = Field(min_length=1, max_length=2300)
    range_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("json_pointer")
    @classmethod
    def _pointer_is_canonical(cls, value: str) -> str:
        _decode_json_pointer(value)
        return value

    @model_validator(mode="after")
    def _range_is_exact(self) -> "EvidenceCharacterRangeV2":
        if self.unicode_end <= self.unicode_start:
            raise ValueError("Unicode offsets must form a non-empty half-open range")
        expected_locator = render_evidence_character_locator_v2(
            artifact_sha256=self.artifact_sha256,
            json_pointer=self.json_pointer,
            unicode_start=self.unicode_start,
            unicode_end=self.unicode_end,
        )
        if self.rendered_locator != expected_locator:
            raise ValueError("evidence character locator is not canonical")
        if self.range_sha256 != evidence_character_range_v2_sha256(self):
            raise ValueError("evidence character range digest mismatch")
        return self


def build_evidence_character_range_v2(
    artifact_bytes: bytes,
    *,
    json_pointer: str,
    unicode_start: int,
    unicode_end: int,
) -> EvidenceCharacterRangeV2:
    """Build a content-addressed locator from exact JSON artifact bytes."""

    artifact, artifact_sha256 = _load_exact_json_artifact(artifact_bytes)
    selected_field = _resolve_json_pointer(artifact, json_pointer)
    if not isinstance(selected_field, str):
        raise ValueError("evidence JSON Pointer must resolve to a string")
    if (
        isinstance(unicode_start, bool)
        or isinstance(unicode_end, bool)
        or not isinstance(unicode_start, int)
        or not isinstance(unicode_end, int)
        or unicode_start < 0
        or unicode_end <= unicode_start
        or unicode_end > len(selected_field)
    ):
        raise ValueError("Unicode offsets are outside the selected JSON string")
    selected_text = selected_field[unicode_start:unicode_end]
    body = {
        "schema_version": EVIDENCE_CHARACTER_RANGE_V2_SCHEMA_VERSION,
        "artifact_sha256": artifact_sha256,
        "json_pointer": json_pointer,
        "unicode_start": unicode_start,
        "unicode_end": unicode_end,
        "selected_text_sha256": hashlib.sha256(
            selected_text.encode("utf-8", errors="strict")
        ).hexdigest(),
        "rendered_locator": render_evidence_character_locator_v2(
            artifact_sha256=artifact_sha256,
            json_pointer=json_pointer,
            unicode_start=unicode_start,
            unicode_end=unicode_end,
        ),
    }
    return EvidenceCharacterRangeV2.model_validate(
        {**body, "range_sha256": evidence_character_range_v2_sha256(body)}
    )


def verify_evidence_character_range_v2(
    artifact_bytes: bytes,
    evidence_range: EvidenceCharacterRangeV2,
) -> None:
    """Replay artifact, pointer, offsets, substring hash, and rendered locator."""

    evidence_range = EvidenceCharacterRangeV2.model_validate(
        evidence_range.model_dump(mode="json")
    )
    replayed = build_evidence_character_range_v2(
        artifact_bytes,
        json_pointer=evidence_range.json_pointer,
        unicode_start=evidence_range.unicode_start,
        unicode_end=evidence_range.unicode_end,
    )
    if replayed != evidence_range:
        raise ValueError("evidence character range does not replay")


def render_evidence_character_locator_v2(
    *,
    artifact_sha256: str,
    json_pointer: str,
    unicode_start: int,
    unicode_end: int,
) -> str:
    """Render a path-free locator with stable percent-encoding."""

    if _SHA256_RE.fullmatch(artifact_sha256) is None:
        raise ValueError("artifact SHA-256 is invalid")
    _decode_json_pointer(json_pointer)
    if (
        isinstance(unicode_start, bool)
        or isinstance(unicode_end, bool)
        or not isinstance(unicode_start, int)
        or not isinstance(unicode_end, int)
        or unicode_start < 0
        or unicode_end <= unicode_start
    ):
        raise ValueError("Unicode offsets are invalid")
    pointer = quote(json_pointer, safe="")
    return (
        f"sha256:{artifact_sha256}#json-pointer={pointer}"
        f"&unicode={unicode_start}:{unicode_end}"
    )


def evidence_character_range_v2_sha256(
    value: EvidenceCharacterRangeV2 | Mapping[str, Any],
) -> str:
    if isinstance(value, EvidenceCharacterRangeV2):
        body = value.model_dump(mode="json", exclude={"range_sha256"})
    else:
        body = dict(value)
        body.pop("range_sha256", None)
    return hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _text_sha256(text: str) -> str:
    try:
        encoded = text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("source document must be valid UTF-8 text") from exc
    return hashlib.sha256(encoded).hexdigest()


def _split_lf_lines(text: str) -> list[str]:
    """Split only on LF so PDF form-feed bytes remain source content."""

    parts = text.split("\n")
    lines = [f"{part}\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


@dataclass(frozen=True, slots=True)
class ImmutableSourceDocument:
    """An exact UTF-8 document registered by trusted host code."""

    source_id: str
    text: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be a non-empty opaque string")
        if not isinstance(self.text, str):
            raise TypeError("source document text must be a string")
        observed = _text_sha256(self.text)
        if not _SHA256_RE.fullmatch(self.sha256) or self.sha256 != observed:
            raise ValueError("source document SHA-256 does not match its UTF-8 bytes")

    @classmethod
    def from_text(cls, source_id: str, text: str) -> "ImmutableSourceDocument":
        """Create a document whose digest is computed from its exact UTF-8 bytes."""

        return cls(source_id=source_id, text=text, sha256=_text_sha256(text))


SourceRegistry = Mapping[str, ImmutableSourceDocument]
_CURRENT_SOURCE_REGISTRY: ContextVar[SourceRegistry | None] = ContextVar(
    "chemsmart_source_document_registry",
    default=None,
)


@dataclass(frozen=True, slots=True)
class EvidenceSelectionBinding:
    """Host-owned claim contract for one bounded evidence-selection task.

    Source identity, claim identifiers, and purpose are coordinator inputs, not
    model decisions.  The model is left with one degree of freedom: selecting
    exact spans from the host-rendered source view.
    """

    source_id: str
    source_sha256: str
    claim_ids: tuple[str, ...]
    purpose: str

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        if _SHA256_RE.fullmatch(self.source_sha256) is None:
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
        if (
            not 1 <= len(self.claim_ids) <= 16
            or tuple(sorted(set(self.claim_ids))) != self.claim_ids
            or any(
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", item)
                is None
                for item in self.claim_ids
            )
        ):
            raise ValueError("claim_ids must be unique, sorted stable identifiers")
        if not self.purpose.strip() or len(self.purpose) > 200:
            raise ValueError("purpose must be a bounded public label")


_CURRENT_EVIDENCE_BINDING: ContextVar[EvidenceSelectionBinding | None] = (
    ContextVar("chemsmart_evidence_selection_binding", default=None)
)


@contextmanager
def source_document_scope(
    documents: Iterable[ImmutableSourceDocument],
) -> Iterator[SourceRegistry]:
    """Register immutable source documents for one host-controlled tool scope."""

    registered: dict[str, ImmutableSourceDocument] = {}
    for document in documents:
        if not isinstance(document, ImmutableSourceDocument):
            raise TypeError("source registry accepts ImmutableSourceDocument values")
        # Re-run the digest check at registration so a future alternate
        # constructor cannot weaken the host boundary.
        if _text_sha256(document.text) != document.sha256:
            raise ValueError("source document changed before registration")
        if document.source_id in registered:
            raise ValueError(f"duplicate source_id: {document.source_id}")
        registered[document.source_id] = document
    immutable_registry: SourceRegistry = MappingProxyType(registered)
    token = _CURRENT_SOURCE_REGISTRY.set(immutable_registry)
    try:
        yield immutable_registry
    finally:
        _CURRENT_SOURCE_REGISTRY.reset(token)


@contextmanager
def evidence_selection_scope(
    binding: EvidenceSelectionBinding,
) -> Iterator[EvidenceSelectionBinding]:
    """Bind immutable coordinator-owned evidence inputs for one tool loop."""

    if not isinstance(binding, EvidenceSelectionBinding):
        raise TypeError("binding must be an EvidenceSelectionBinding")
    token = _CURRENT_EVIDENCE_BINDING.set(binding)
    try:
        yield binding
    finally:
        _CURRENT_EVIDENCE_BINDING.reset(token)


def extract_project_protocol_spans(
    source_id: str,
    source_sha256: str,
    spans: Sequence[Mapping[str, int]],
    project_name: str,
    program: ProjectProgram,
    profile: ProjectRenderProfile,
) -> dict[str, Any]:
    """Resolve exact registered spans and extract project protocol facts.

    ``spans`` are 1-based, inclusive, sorted, and non-overlapping. Optional
    column bounds isolate a substring on one PDF-text line. No source text or
    path crosses the model-facing boundary.
    """

    registry = _CURRENT_SOURCE_REGISTRY.get()
    if registry is None:
        return _blocked(
            RULE_REGISTRY_MISSING,
            "No host-owned source registry is active.",
            source_id=source_id,
        )
    document = registry.get(source_id)
    if document is None:
        return _blocked(
            RULE_SOURCE_MISSING,
            "The selected source_id is not registered in this tool scope.",
            source_id=source_id,
        )
    if (
        not isinstance(source_sha256, str)
        or not _SHA256_RE.fullmatch(source_sha256)
        or source_sha256 != document.sha256
    ):
        return _blocked(
            RULE_HASH_MISMATCH,
            "The selected digest does not match the registered UTF-8 document.",
            source_id=source_id,
        )

    source_lines = _split_lf_lines(document.text)
    normalized_spans, range_error = _validated_spans(spans, source_lines)
    if range_error is not None:
        return _blocked(
            RULE_RANGE_INVALID,
            range_error,
            source_id=source_id,
            document_sha256=document.sha256,
        )

    excerpts: list[str] = []
    locators: list[dict[str, Any]] = []
    for start_line, end_line, start_column, end_column in normalized_spans:
        if start_column is None:
            excerpt = "".join(source_lines[start_line - 1 : end_line])
        else:
            source_line = source_lines[start_line - 1].rstrip("\r\n")
            excerpt = source_line[start_column - 1 : end_column]
        excerpt_bytes = excerpt.encode("utf-8", errors="strict")
        excerpts.append(excerpt)
        locator = {
            "kind": (
                "line_column_range"
                if start_column is not None
                else "line_range"
            ),
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "byte_count": len(excerpt_bytes),
            "sha256": hashlib.sha256(excerpt_bytes).hexdigest(),
        }
        if start_column is not None:
            locator["start_column"] = start_column
            locator["end_column"] = end_column
        locators.append(locator)

    aggregate_excerpt = "\n".join(
        excerpt.rstrip("\r\n") for excerpt in excerpts
    ) + "\n"
    aggregate_bytes = aggregate_excerpt.encode("utf-8", errors="strict")
    result = dict(
        extract_project_protocol(
            aggregate_excerpt,
            project_name=project_name,
            program=program,
            profile=profile,
        )
    )
    result.pop("source_excerpt", None)
    result["source_evidence"] = {
        "kind": "immutable_utf8_line_spans",
        "source_id": source_id,
        "document_sha256": document.sha256,
        "locators": locators,
        "aggregate_excerpt_sha256": hashlib.sha256(aggregate_bytes).hexdigest(),
        "aggregation_rule": "utf8_spans_lf_join_v1",
        "aggregate_line_count": sum(
            locator["line_count"] for locator in locators
        ),
        "aggregate_byte_count": len(aggregate_bytes),
    }
    return result


def select_evidence_spans(
    source_id: str,
    source_sha256: str,
    spans: Sequence[Mapping[str, int]],
    claim_ids: Sequence[str],
    purpose: str,
) -> dict[str, Any]:
    """Bind general research claims to exact immutable source spans.

    The result intentionally omits source prose.  A model may select from a
    host-rendered numbered view, while the canonical receipt retains only
    locators and hashes.  This tool observes evidence; it does not decide that
    a scientific claim is true or that a workflow is ready.
    """

    registry = _CURRENT_SOURCE_REGISTRY.get()
    if registry is None:
        return _blocked(
            RULE_REGISTRY_MISSING,
            "No host-owned source registry is active.",
            source_id=source_id,
        )
    document = registry.get(source_id)
    if document is None:
        return _blocked(
            RULE_SOURCE_MISSING,
            "The selected source_id is not registered in this tool scope.",
            source_id=source_id,
        )
    if (
        not isinstance(source_sha256, str)
        or not _SHA256_RE.fullmatch(source_sha256)
        or source_sha256 != document.sha256
    ):
        return _blocked(
            RULE_HASH_MISMATCH,
            "The selected digest does not match the registered UTF-8 document.",
            source_id=source_id,
        )
    if (
        isinstance(claim_ids, (str, bytes))
        or not isinstance(claim_ids, Sequence)
        or not 1 <= len(claim_ids) <= 16
        or any(
            not isinstance(item, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", item) is None
            for item in claim_ids
        )
        or tuple(sorted(set(claim_ids))) != tuple(claim_ids)
    ):
        return _blocked(
            "paper.claim.claim_ids_invalid",
            "claim_ids must be unique, sorted, stable identifiers.",
            source_id=source_id,
            document_sha256=document.sha256,
        )
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 200:
        return _blocked(
            "paper.claim.purpose_invalid",
            "evidence selection requires a bounded public purpose label.",
            source_id=source_id,
            document_sha256=document.sha256,
        )

    source_lines = _split_lf_lines(document.text)
    normalized_spans, range_error = _validated_spans(spans, source_lines)
    if range_error is not None:
        return _blocked(
            RULE_RANGE_INVALID,
            range_error,
            source_id=source_id,
            document_sha256=document.sha256,
        )
    locators: list[dict[str, Any]] = []
    excerpts: list[str] = []
    for start_line, end_line, start_column, end_column in normalized_spans:
        if start_column is None:
            excerpt = "".join(source_lines[start_line - 1 : end_line])
        else:
            source_line = source_lines[start_line - 1].rstrip("\r\n")
            excerpt = source_line[start_column - 1 : end_column]
        encoded = excerpt.encode("utf-8", errors="strict")
        locator: dict[str, Any] = {
            "kind": (
                "line_column_range"
                if start_column is not None
                else "line_range"
            ),
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "byte_count": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        if start_column is not None:
            locator["start_column"] = start_column
            locator["end_column"] = end_column
        locators.append(locator)
        excerpts.append(excerpt.rstrip("\r\n"))
    aggregate = "\n".join(excerpts) + "\n"
    aggregate_bytes = aggregate.encode("utf-8", errors="strict")
    return {
        "ok": True,
        "status": "extracted",
        "claim_ids": list(claim_ids),
        "purpose_sha256": hashlib.sha256(
            purpose.strip().encode("utf-8")
        ).hexdigest(),
        "source_evidence": {
            "kind": "immutable_utf8_line_spans",
            "source_id": source_id,
            "document_sha256": document.sha256,
            "locators": locators,
            "aggregate_excerpt_sha256": hashlib.sha256(
                aggregate_bytes
            ).hexdigest(),
            "aggregation_rule": "utf8_spans_lf_join_v1",
            "aggregate_line_count": sum(
                locator["line_count"] for locator in locators
            ),
            "aggregate_byte_count": len(aggregate_bytes),
        },
    }


def select_bound_evidence_spans(
    spans: Sequence[Mapping[str, int]],
) -> dict[str, Any]:
    """Select spans while all claim-bearing fields remain host-owned.

    This narrow tool is intended for specialist task packets.  It prevents a
    model from silently changing the source digest, claim set, or task purpose
    while retaining the same deterministic span validation and receipt shape.
    """

    binding = _CURRENT_EVIDENCE_BINDING.get()
    if binding is None:
        return _blocked(
            "paper.claim.binding_missing",
            "No host-owned evidence-selection binding is active.",
        )
    return select_evidence_spans(
        source_id=binding.source_id,
        source_sha256=binding.source_sha256,
        spans=spans,
        claim_ids=binding.claim_ids,
        purpose=binding.purpose,
    )


def report_bound_evidence_gap(reason: str) -> dict[str, Any]:
    """Record an honest specialist stop without fabricating a source span."""

    binding = _CURRENT_EVIDENCE_BINDING.get()
    if binding is None:
        return _blocked(
            "paper.claim.binding_missing",
            "No host-owned evidence-selection binding is active.",
        )
    allowed = {
        "not_present_in_view",
        "source_conflict",
        "source_unreadable",
    }
    if reason not in allowed:
        return _blocked(
            "paper.claim.gap_reason_invalid",
            "Evidence-gap reason is outside the closed vocabulary.",
            source_id=binding.source_id,
            document_sha256=binding.source_sha256,
        )
    return {
        "ok": False,
        "status": "blocked_missing_evidence",
        "blocking_issues": [
            {
                "rule_id": "paper.claim.model_reported_gap",
                "reason": reason,
            }
        ],
        "claim_ids": list(binding.claim_ids),
        "source_evidence": {
            "source_id": binding.source_id,
            "document_sha256": binding.source_sha256,
            "locators": [],
        },
    }


def tool_input_json_schema(name: str) -> dict[str, Any] | None:
    """Return the explicit source-selector schema for provider tool calls."""

    if name == "report_bound_evidence_gap":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["reason"],
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "not_present_in_view",
                        "source_conflict",
                        "source_unreadable",
                    ],
                }
            },
        }

    if name == "select_bound_evidence_spans":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["spans"],
            "properties": {
                "spans": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": _MAX_SPANS,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["start_line", "end_line"],
                        "dependentRequired": {
                            "start_column": ["end_column"],
                            "end_column": ["start_column"],
                        },
                        "properties": {
                            "start_line": {"type": "integer", "minimum": 1},
                            "end_line": {"type": "integer", "minimum": 1},
                            "start_column": {"type": "integer", "minimum": 1},
                            "end_column": {"type": "integer", "minimum": 1},
                        },
                    },
                }
            },
        }

    if name == "select_evidence_spans":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "source_id",
                "source_sha256",
                "spans",
                "claim_ids",
                "purpose",
            ],
            "properties": {
                "source_id": {"type": "string", "minLength": 1, "maxLength": 256},
                "source_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "spans": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": _MAX_SPANS,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["start_line", "end_line"],
                        "dependentRequired": {
                            "start_column": ["end_column"],
                            "end_column": ["start_column"],
                        },
                        "properties": {
                            "start_line": {"type": "integer", "minimum": 1},
                            "end_line": {"type": "integer", "minimum": 1},
                            "start_column": {"type": "integer", "minimum": 1},
                            "end_column": {"type": "integer", "minimum": 1},
                        },
                    },
                },
                "claim_ids": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 16,
                    "items": {
                        "type": "string",
                        "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
                    },
                },
                "purpose": {"type": "string", "minLength": 1, "maxLength": 200},
            },
        }
    if name != "extract_project_protocol_spans":
        return None
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "source_id",
            "source_sha256",
            "spans",
            "project_name",
            "program",
            "profile",
        ],
        "properties": {
            "source_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "description": "Opaque identifier supplied by the host.",
            },
            "source_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
                "description": "Exact SHA-256 of the registered UTF-8 document.",
            },
            "spans": {
                "type": "array",
                "minItems": 1,
                "maxItems": _MAX_SPANS,
                "description": (
                    "Sorted, non-overlapping, 1-based inclusive line spans; "
                    f"each span contains at most {_MAX_LINES_PER_SPAN} lines."
                ),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["start_line", "end_line"],
                    "dependentRequired": {
                        "start_column": ["end_column"],
                        "end_column": ["start_column"],
                    },
                    "properties": {
                        "start_line": {"type": "integer", "minimum": 1},
                        "end_line": {"type": "integer", "minimum": 1},
                        "start_column": {"type": "integer", "minimum": 1},
                        "end_column": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "project_name": {"type": "string", "minLength": 1},
            "program": {
                "type": "string",
                "enum": ["gaussian", "orca", "xtb"],
            },
            "profile": {
                "type": "string",
                "enum": ["legacy", "paper"],
            },
        },
    }


def _validated_spans(
    spans: Sequence[Mapping[str, int]],
    source_lines: Sequence[str],
) -> tuple[list[tuple[int, int, int | None, int | None]], str | None]:
    document_line_count = len(source_lines)
    if isinstance(spans, (str, bytes)) or not isinstance(spans, Sequence):
        return [], "spans must be a sequence of line-range objects."
    if not 1 <= len(spans) <= _MAX_SPANS:
        return [], f"spans must contain between 1 and {_MAX_SPANS} entries."

    normalized: list[tuple[int, int, int | None, int | None]] = []
    previous_end = 0
    for index, span in enumerate(spans):
        allowed = {"start_line", "end_line", "start_column", "end_column"}
        if (
            not isinstance(span, Mapping)
            or not {"start_line", "end_line"}.issubset(span)
            or not set(span).issubset(allowed)
        ):
            return [], (
                f"span {index} must contain line bounds and optional paired "
                "column bounds only."
            )
        start_line = span.get("start_line")
        end_line = span.get("end_line")
        start_column = span.get("start_column")
        end_column = span.get("end_column")
        if (
            isinstance(start_line, bool)
            or isinstance(end_line, bool)
            or not isinstance(start_line, int)
            or not isinstance(end_line, int)
        ):
            return [], f"span {index} line bounds must be integers."
        if start_line < 1 or end_line < start_line:
            return [], f"span {index} has invalid 1-based inclusive bounds."
        if end_line - start_line + 1 > _MAX_LINES_PER_SPAN:
            return [], (
                f"span {index} exceeds the {_MAX_LINES_PER_SPAN}-line limit."
            )
        if start_line <= previous_end:
            return [], "spans must be sorted and non-overlapping."
        if end_line > document_line_count:
            return [], (
                f"span {index} ends beyond the registered document line count."
            )
        if (start_column is None) != (end_column is None):
            return [], f"span {index} column bounds must be supplied together."
        if start_column is not None:
            if start_line != end_line:
                return [], (
                    f"span {index} column bounds require a single source line."
                )
            if (
                isinstance(start_column, bool)
                or isinstance(end_column, bool)
                or not isinstance(start_column, int)
                or not isinstance(end_column, int)
                or start_column < 1
                or end_column < start_column
            ):
                return [], f"span {index} has invalid 1-based column bounds."
            line_length = len(source_lines[start_line - 1].rstrip("\r\n"))
            if end_column > line_length:
                return [], (
                    f"span {index} ends beyond the registered source line."
                )
        normalized.append((start_line, end_line, start_column, end_column))
        previous_end = end_line
    return normalized, None


def _load_exact_json_artifact(artifact_bytes: bytes) -> tuple[Any, str]:
    if not isinstance(artifact_bytes, bytes):
        raise TypeError("evidence artifact must be exact bytes")
    try:
        text = artifact_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("evidence artifact must be valid UTF-8 JSON") from exc

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("evidence JSON contains duplicate object keys")
            value[key] = item
        return value

    try:
        parsed = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError("evidence artifact must be valid JSON") from exc
    return parsed, hashlib.sha256(artifact_bytes).hexdigest()


def _decode_json_pointer(value: str) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise TypeError("JSON Pointer must be text")
    if value == "":
        return ()
    if not value.startswith("/"):
        raise ValueError("JSON Pointer must be empty or start with slash")
    decoded: list[str] = []
    for token in value[1:].split("/"):
        index = 0
        output: list[str] = []
        while index < len(token):
            if token[index] != "~":
                output.append(token[index])
                index += 1
                continue
            if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
                raise ValueError("JSON Pointer contains a non-canonical escape")
            output.append("~" if token[index + 1] == "0" else "/")
            index += 2
        decoded.append("".join(output))
    return tuple(decoded)


def _resolve_json_pointer(value: Any, pointer: str) -> Any:
    current = value
    for token in _decode_json_pointer(pointer):
        if isinstance(current, Mapping):
            if token not in current:
                raise ValueError("JSON Pointer object member does not exist")
            current = current[token]
        elif isinstance(current, list):
            if token == "-" or re.fullmatch(r"0|[1-9][0-9]*", token) is None:
                raise ValueError("JSON Pointer array index is invalid")
            index = int(token)
            if index >= len(current):
                raise ValueError("JSON Pointer array index is outside the artifact")
            current = current[index]
        else:
            raise ValueError("JSON Pointer traverses a scalar value")
    return current


def _blocked(
    rule_id: str,
    message: str,
    **evidence: Any,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked_missing_evidence",
        "blocking_issues": [
            {
                "rule_id": rule_id,
                "message": message,
            }
        ],
        "source_evidence": evidence,
    }


__all__ = [
    "EVIDENCE_CHARACTER_RANGE_V2_SCHEMA_VERSION",
    "EvidenceCharacterRangeV2",
    "EvidenceSelectionBinding",
    "ImmutableSourceDocument",
    "RULE_HASH_MISMATCH",
    "RULE_RANGE_INVALID",
    "RULE_REGISTRY_MISSING",
    "RULE_SOURCE_MISSING",
    "build_evidence_character_range_v2",
    "evidence_character_range_v2_sha256",
    "evidence_selection_scope",
    "extract_project_protocol_spans",
    "render_evidence_character_locator_v2",
    "report_bound_evidence_gap",
    "select_bound_evidence_spans",
    "select_evidence_spans",
    "source_document_scope",
    "tool_input_json_schema",
    "verify_evidence_character_range_v2",
]
