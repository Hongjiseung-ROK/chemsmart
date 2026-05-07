from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model

from chemsmart.agent import tools as agent_tools


class ToolInputModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Any
    input_schema: type[ToolInputModel]
    accepts_kwargs: bool = False

    def openai_tool_def(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": self.accepts_kwargs,
        }
        for field_name, field_info in self.input_schema.model_fields.items():
            schema["properties"][field_name] = _annotation_to_schema(
                field_info.annotation,
                field_info.description,
            )
            if field_info.is_required():
                schema["required"].append(field_name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": inspect.getdoc(self.func) or self.name,
                "parameters": schema,
            },
        }


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec]):
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    def default(cls) -> "ToolRegistry":
        tool_names = [
            "build_molecule",
            "recommend_method",
            "build_gaussian_settings",
            "build_orca_settings",
            "build_job",
            "dry_run_input",
            "validate_runtime",
            "run_local",
            "submit_hpc",
        ]
        return cls(
            [
                _build_tool_spec(
                    getattr(agent_tools, name), registered_name=name
                )
                for name in tool_names
            ]
        )

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def openai_tool_defs(self) -> list[dict[str, Any]]:
        return [tool.openai_tool_def() for tool in self.list_tools()]

    def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        if name not in self._tools:
            known = ", ".join(sorted(self._tools))
            raise ValueError(
                f"Unknown tool {name!r}. Registered tools: {known}"
            )

        tool = self._tools[name]
        args = args or {}
        try:
            validated = tool.input_schema.model_validate(args)
        except Exception as exc:
            return {
                "ok": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "tool": name,
                },
            }

        payload = dict(validated.model_dump())
        if tool.accepts_kwargs and validated.model_extra:
            payload.update(validated.model_extra)

        try:
            return tool.func(**payload)
        except Exception as exc:
            return {
                "ok": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "tool": name,
                },
            }


def _build_tool_spec(
    func: Any,
    registered_name: str | None = None,
) -> ToolSpec:
    fields: dict[str, Any] = {}
    accepts_kwargs = False
    signature = inspect.signature(func)
    resolved_hints = get_type_hints(func)
    for param in signature.parameters.values():
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_kwargs = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        annotation = resolved_hints.get(param.name, param.annotation)
        if annotation is inspect.Signature.empty:
            annotation = Any
        default = param.default
        if default is inspect.Signature.empty:
            fields[param.name] = (annotation, Field(...))
        else:
            fields[param.name] = (annotation, Field(default=default))

    schema_name = "".join(
        part.capitalize() for part in func.__name__.split("_")
    )
    model = create_model(
        f"{schema_name}Input",
        __base__=ToolInputModel,
        **fields,
    )
    model.model_rebuild()
    return ToolSpec(
        name=registered_name or func.__name__,
        func=func,
        input_schema=model,
        accepts_kwargs=accepts_kwargs,
    )


def _annotation_to_schema(
    annotation: Any,
    description: str | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    if annotation in {str}:
        schema["type"] = "string"
    elif annotation in {int}:
        schema["type"] = "integer"
    elif annotation in {float}:
        schema["type"] = "number"
    elif annotation in {bool}:
        schema["type"] = "boolean"
    elif origin in {list, tuple}:
        schema["type"] = "array"
        item_annotation = args[0] if args else Any
        schema["items"] = _annotation_to_schema(item_annotation)
    elif origin is dict:
        schema["type"] = "object"
    elif origin is None and annotation is Any:
        schema["type"] = "object"
    elif origin in {types.UnionType} or str(annotation).startswith(
        "typing.Union"
    ):
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1:
            schema = _annotation_to_schema(non_none[0])
        else:
            schema["type"] = "object"
    else:
        schema["type"] = "object"

    if description:
        schema["description"] = description
    return schema
