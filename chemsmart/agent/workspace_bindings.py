"""Host-owned workspace bindings for command-compiled workflows.

The model sees only stable artifact/project identifiers, display names, and
content hashes.  This module is the sole place where those opaque references
are resolved back to workspace-relative files for the deterministic command
compiler.  It deliberately does not parse a chemistry engine input, call an
engine, or infer molecular identity from a filename.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from chemsmart import __version__
from chemsmart.agent.geometry_identity import xyz_geometry_manifest


MAX_BINDABLE_FILE_BYTES = 32 * 1024 * 1024
_GEOMETRY_SUFFIXES = frozenset({".xyz", ".sdf", ".pdb", ".com", ".gjf", ".inp"})
_OUTPUT_SUFFIXES = frozenset({".out", ".log"})
_SKIP_DIRECTORIES = frozenset(
    {".git", ".venv", "__pycache__", "node_modules", "scratch"}
)
_MAX_DEPTH = 3


@dataclass(frozen=True)
class WorkspaceArtifactBinding:
    """A content-addressed local file with a model-safe public projection."""

    artifact_id: str
    sha256: str
    kind: str
    path: Path
    display_name: str
    ordered_geometry_sha256: str | None = None
    atom_count: int | None = None

    def public_dict(self) -> dict[str, str]:
        """Return model-safe fields only; host paths never leave this module."""

        result = {
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "kind": self.kind,
            "display_name": self.display_name,
        }
        if self.ordered_geometry_sha256 is not None:
            result["ordered_geometry_sha256"] = self.ordered_geometry_sha256
        if self.atom_count is not None:
            result["atom_count"] = str(self.atom_count)
        return result


@dataclass(frozen=True)
class WorkspaceProjectBinding:
    """A content-addressed project YAML reference selected by its safe name."""

    project_id: str
    sha256: str
    program: str
    command_value: str
    path: Path

    def public_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "sha256": self.sha256,
            "program": self.program,
            "project_name": self.command_value,
        }


@dataclass(frozen=True)
class WorkspaceBindings:
    """The trusted, per-request resolution table for compiler input."""

    workspace_root: Path
    artifacts: dict[str, WorkspaceArtifactBinding]
    projects: dict[str, WorkspaceProjectBinding]
    environment_digest: str

    def public_inventory(self) -> dict[str, list[dict[str, str]]]:
        artifacts = sorted(
            (binding.public_dict() for binding in self.artifacts.values()),
            key=lambda item: (item["kind"], item["display_name"], item["artifact_id"]),
        )
        return {
            "geometry_artifacts": [
                item for item in artifacts if item["kind"].startswith("geometry.")
            ],
            "native_input_artifacts": [
                item
                for item in artifacts
                if item["kind"].startswith("native_input.")
            ],
            "output_artifacts": [
                item
                for item in artifacts
                if item["kind"].startswith("native_output.")
            ],
            "project_artifacts": sorted(
                (binding.public_dict() for binding in self.projects.values()),
                key=lambda item: (item["program"], item["project_name"]),
            ),
        }


def discover_workspace_bindings(
    workspace_root: str | Path,
    *,
    max_file_bytes: int = MAX_BINDABLE_FILE_BYTES,
) -> WorkspaceBindings:
    """Discover bounded, content-addressed compiler inputs under one workspace.

    Symlink escapes, hidden runtime directories, and files exceeding the
    deterministic hashing limit are intentionally excluded.  A caller can
    report a missing binding as a clarification rather than accepting an
    arbitrary model-supplied path.
    """

    root = Path(workspace_root).resolve(strict=False)
    if not root.is_dir():
        raise ValueError("workspace_root must be an existing directory")
    if not isinstance(max_file_bytes, int) or max_file_bytes <= 0:
        raise ValueError("max_file_bytes must be a positive integer")

    artifacts: dict[str, WorkspaceArtifactBinding] = {}
    for path in _iter_candidate_files(root):
        kind = _artifact_kind(path)
        if kind is None:
            continue
        binding = _artifact_binding(path, root=root, kind=kind, max_file_bytes=max_file_bytes)
        if binding is None:
            continue
        # Identical content/kind is intentionally one identity.  Pick the
        # lexicographically first relative location deterministically.
        prior = artifacts.get(binding.artifact_id)
        if prior is None or binding.path.as_posix() < prior.path.as_posix():
            artifacts[binding.artifact_id] = binding

    projects = _discover_projects(root, max_file_bytes=max_file_bytes)
    return WorkspaceBindings(
        workspace_root=root,
        artifacts=artifacts,
        projects=projects,
        environment_digest=environment_digest(),
    )


def compilation_context(bindings: WorkspaceBindings):
    """Build the compiler's private resolver mapping from workspace bindings."""

    from chemsmart.agent.command_workflow import (
        CompilationContext,
        ResolvedArtifact,
        ResolvedProject,
    )

    return CompilationContext(
        workspace_root=bindings.workspace_root,
        environment_digest=bindings.environment_digest,
        artifacts={
            artifact_id: ResolvedArtifact(
                artifact_id=item.artifact_id,
                sha256=item.sha256,
                kind=item.kind,
                path=item.path,
            )
            for artifact_id, item in bindings.artifacts.items()
        },
        projects={
            project_id: ResolvedProject(
                project_id=item.project_id,
                sha256=item.sha256,
                program=item.program,
                command_value=item.command_value,
                path=item.path,
            )
            for project_id, item in bindings.projects.items()
        },
        max_artifact_bytes=MAX_BINDABLE_FILE_BYTES,
    )


def environment_digest() -> str:
    """Return a path-free digest of the local command-rendering environment."""

    payload = {
        "chemsmart_version": __version__,
        "implementation": platform.python_implementation(),
        "platform": platform.system(),
        "python": list(sys.version_info[:3]),
    }
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _iter_candidate_files(root: Path) -> Iterable[Path]:
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        try:
            relative = current_path.resolve(strict=False).relative_to(root)
        except ValueError:
            dirnames[:] = []
            continue
        depth = len(relative.parts)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in _SKIP_DIRECTORIES
            and not name.startswith(".")
            and depth < _MAX_DEPTH
        )
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = current_path / name
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError):
                continue
            if resolved.is_file():
                yield resolved


def _artifact_kind(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".xyz":
        return "geometry.xyz"
    if suffix == ".sdf":
        return "geometry.sdf"
    if suffix == ".pdb":
        return "geometry.pdb"
    if suffix in {".com", ".gjf"}:
        return "native_input.gaussian"
    if suffix == ".inp":
        return "native_input.orca"
    if suffix in _OUTPUT_SUFFIXES:
        return "native_output"
    return None


def _artifact_binding(
    path: Path,
    *,
    root: Path,
    kind: str,
    max_file_bytes: int,
) -> WorkspaceArtifactBinding | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > max_file_bytes:
        return None
    digest = _sha256_file(path)
    geometry_manifest = None
    if kind == "geometry.xyz":
        try:
            geometry_manifest = xyz_geometry_manifest(path)
        except ValueError:
            # The content hash remains useful for evidence inspection, but an
            # ambiguous/multi-frame XYZ is deliberately unavailable to the
            # M2 command compiler through its stricter scientific contract.
            geometry_manifest = None
    return WorkspaceArtifactBinding(
        artifact_id=f"artifact:{kind}:{digest}",
        sha256=digest,
        kind=kind,
        path=path,
        display_name=path.relative_to(root).as_posix(),
        ordered_geometry_sha256=(
            geometry_manifest.ordered_geometry_sha256
            if geometry_manifest is not None
            else None
        ),
        atom_count=(
            geometry_manifest.atom_count if geometry_manifest is not None else None
        ),
    )


def _discover_projects(
    root: Path,
    *,
    max_file_bytes: int,
) -> dict[str, WorkspaceProjectBinding]:
    projects: dict[str, WorkspaceProjectBinding] = {}
    for program in ("gaussian", "orca", "xtb"):
        directory = root / ".chemsmart" / program
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
                size = resolved.stat().st_size
            except (OSError, ValueError):
                continue
            if size > max_file_bytes:
                continue
            project_name = resolved.stem
            project_id = f"project:{program}:{project_name}"
            projects[project_id] = WorkspaceProjectBinding(
                project_id=project_id,
                sha256=_sha256_file(resolved),
                program=program,
                command_value=project_name,
                path=resolved,
            )
    return projects


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "MAX_BINDABLE_FILE_BYTES",
    "WorkspaceArtifactBinding",
    "WorkspaceBindings",
    "WorkspaceProjectBinding",
    "compilation_context",
    "discover_workspace_bindings",
    "environment_digest",
]
