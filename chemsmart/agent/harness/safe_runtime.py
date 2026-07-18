from __future__ import annotations

import os
import shlex
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from chemsmart.agent.harness.extractors import (
    extract_cartesian_state,
    extract_gaussian_route,
    extract_orca_route,
)

_INPUT_SUFFIXES = {
    "gaussian": (".com", ".gjf"),
    "orca": (".inp",),
    "xtb": (".xyz",),
}
DEFAULT_MAX_GENERATED_FILE_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_GENERATED_TOTAL_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_GENERATED_COUNT = 256


def absolutize_file_args(argv: list[str], base: Path) -> list[str]:
    """Resolve existing file arguments before entering an isolated cwd."""
    resolved: list[str] = []
    for token in argv:
        if (
            token
            and not token.startswith("-")
            and not os.path.isabs(token)
            and (os.sep in token or os.path.splitext(token)[1])
            and (base / token).exists()
        ):
            resolved.append(str((base / token).resolve()))
        else:
            resolved.append(token)
    return resolved


def safe_execution_argv(
    tokens: list[str],
    top_index: int,
    top_level: str,
) -> list[str]:
    """Build a non-destructive CLI invocation for runtime validation."""
    argv = _with_no_verbose(tokens)
    # ``--no-verbose`` may have shifted the top-level command by one token.
    top_index = _top_level_index(argv, top_level)
    insert_at = top_index + 1
    additions: list[str] = []
    if top_level == "run":
        if "--fake" not in argv[insert_at:]:
            additions.append("--fake")
        if (
            "--scratch" not in argv[insert_at:]
            and "--no-scratch" not in argv[insert_at:]
        ):
            additions.append("--no-scratch")
    elif top_level == "sub":
        if "--test" not in argv[insert_at:]:
            additions.append("--test")
        if "--fake" not in argv[insert_at:]:
            additions.append("--fake")
    cli_args = argv[1:insert_at] + additions + argv[insert_at:]
    return [sys.executable, "-m", "chemsmart.cli.main", *cli_args]


def prepare_safe_runtime_environment(
    *,
    base_cwd: Path,
    workdir: Path,
    top_level: str,
) -> dict[str, str]:
    """Mirror workspace state and isolate local fake-run configuration.

    ``chemsmart run`` falls back to ``~/.chemsmart/server/local.yaml``. A
    semantic gate must not pass or fail according to an unrelated user HOME,
    so fake local runs receive a minimal run-local profile. ``sub`` keeps the
    caller HOME because its named server fixture is part of submission intent.
    """
    _mirror_workspace_config(base_cwd, workdir)
    env = _subprocess_env()
    if top_level != "run":
        return env

    gate_home = workdir / ".gate-home"
    server_dir = gate_home / ".chemsmart" / "server"
    server_dir.mkdir(parents=True, exist_ok=True)
    fake_bin = workdir / ".fake-executables"
    fake_bin.mkdir(exist_ok=True)
    local_server = {
        "SERVER": {
            "SCHEDULER": None,
            "QUEUE_NAME": None,
            "NUM_HOURS": None,
            "MEM_GB": 40,
            "NUM_CORES": 12,
            "NUM_GPUS": 0,
            "NUM_THREADS": 12,
            "SUBMIT_COMMAND": None,
            "SCRATCH_DIR": None,
            "USE_HOSTS": False,
        },
        "GAUSSIAN": {
            "EXEFOLDER": str(fake_bin),
            "LOCAL_RUN": True,
            "SCRATCH": False,
        },
        "ORCA": {
            "EXEFOLDER": str(fake_bin),
            "LOCAL_RUN": True,
            "SCRATCH": False,
        },
        "XTB": {
            "EXEFOLDER": None,
            "LOCAL_RUN": True,
            "SCRATCH": False,
        },
    }
    (server_dir / "local.yaml").write_text(
        yaml.safe_dump(local_server, sort_keys=False),
        encoding="utf-8",
    )
    env["HOME"] = str(gate_home)
    return env


def input_snapshot(
    workdir: Path,
    *,
    software: str | None = None,
) -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    if not workdir.exists():
        return snapshot
    for suffix in _suffixes(software):
        for path in workdir.glob(f"*{suffix}"):
            try:
                snapshot[path.resolve()] = path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
    return snapshot


def generated_inputs(
    workdir: Path,
    before: dict[Path, int],
    *,
    software: str | None = None,
    command: str | None = None,
    max_file_bytes: int = DEFAULT_MAX_GENERATED_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_GENERATED_TOTAL_BYTES,
    max_count: int = DEFAULT_MAX_GENERATED_COUNT,
) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    total_bytes = 0
    workdir_root = workdir.resolve()
    if not workdir.exists():
        return generated
    for suffix in _suffixes(software):
        for path in sorted(workdir.glob(f"*{suffix}")):
            try:
                resolved = path.resolve()
                stat = path.stat()
            except FileNotFoundError:
                continue
            if path.is_symlink() or resolved.parent != workdir_root:
                raise RuntimeError(
                    "Generated input escaped the safe runtime workspace."
                )
            mtime = stat.st_mtime_ns
            if before.get(resolved) == mtime:
                continue
            if len(generated) >= max_count:
                raise RuntimeError("Too many generated inputs for one safe run.")
            if stat.st_size > max_file_bytes:
                raise RuntimeError(
                    "Generated input exceeds the safe runtime file limit."
                )
            total_bytes += stat.st_size
            if total_bytes > max_total_bytes:
                raise RuntimeError(
                    "Generated inputs exceed the safe runtime total limit."
                )
            with path.open("rb") as handle:
                payload = handle.read(max_file_bytes + 1)
            if len(payload) > max_file_bytes:
                raise RuntimeError(
                    "Generated input grew beyond the safe runtime file limit."
                )
            content = payload.decode("utf-8", errors="replace")
            detected = software or (
                "gaussian" if suffix in {".com", ".gjf"} else "orca"
            )
            if detected == "gaussian":
                route = extract_gaussian_route(content)
                state = extract_cartesian_state(content, software=detected)
            elif detected == "orca":
                route = extract_orca_route(content)
                state = extract_cartesian_state(content, software=detected)
            else:
                xtb_tokens = _xtb_program_call(path, command)
                route = shlex.join(xtb_tokens) if xtb_tokens else None
                state = _extract_xtb_state(content, xtb_tokens)
            state_evidence: dict[str, Any] = {}
            if state:
                state_evidence = {
                    "charge": state["charge"],
                    "multiplicity": state["multiplicity"],
                    "element_counts": dict(
                        sorted(Counter(state["element_symbols"]).items())
                    ),
                }
                for key in (
                    "charge_multiplicity_pairs",
                    "atom_layers",
                    "layer_atoms",
                ):
                    if key in state:
                        state_evidence[key] = state[key]
            generated.append(
                {
                    "path": str(path),
                    "software": detected,
                    "route": route,
                    "content_tail": input_excerpt(content),
                    **state_evidence,
                }
            )
    return generated


def _suffixes(software: str | None) -> tuple[str, ...]:
    if software is not None:
        return _INPUT_SUFFIXES.get(software, ())
    # Preserve the historical default so staged ORCA .xyz dependencies are
    # never mistaken for generated inputs. xTB callers must opt in explicitly.
    return (*_INPUT_SUFFIXES["gaussian"], *_INPUT_SUFFIXES["orca"])


def _xtb_program_call(path: Path, command: str | None) -> list[str]:
    output_stem = path.stem.removesuffix("_fake")
    output_paths = (
        path.with_suffix(".out"),
        path.with_name(f"{output_stem}.out"),
    )
    for output_path in output_paths:
        if not output_path.is_file():
            continue
        for line in output_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if line.lower().startswith("program call") and ":" in line:
                return shlex.split(line.split(":", 1)[1].strip())
    if not command:
        return []
    tokens = shlex.split(command)
    try:
        program_index = tokens.index("xtb")
    except ValueError:
        return []
    return tokens[program_index:]


def _extract_xtb_state(
    content: str,
    program_call: list[str],
) -> dict[str, Any] | None:
    lines = content.splitlines()
    if len(lines) < 3:
        return None
    try:
        atom_count = int(lines[0].strip())
    except ValueError:
        return None
    symbols = [
        line.split()[0]
        for line in lines[2 : 2 + atom_count]
        if line.split()
    ]
    charge = _integer_option(program_call, ("--chrg",))
    unpaired = _integer_option(program_call, ("--uhf",))
    multiplicity = unpaired + 1 if unpaired is not None else None
    if charge is None or multiplicity is None or len(symbols) != atom_count:
        return None
    return {
        "charge": charge,
        "multiplicity": multiplicity,
        "element_symbols": symbols,
    }


def _integer_option(tokens: list[str], flags: tuple[str, ...]) -> int | None:
    for flag in flags:
        try:
            value = tokens[tokens.index(flag) + 1]
        except (ValueError, IndexError):
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _top_level_index(argv: list[str], top_level: str) -> int:
    try:
        return argv.index(top_level, 1)
    except ValueError as exc:  # pragma: no cover - caller already validated it
        raise ValueError(f"missing top-level command: {top_level}") from exc


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    source_root = str(Path(__file__).resolve().parents[3])
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_root if not existing else f"{source_root}{os.pathsep}{existing}"
    )
    return env


def _with_no_verbose(tokens: list[str]) -> list[str]:
    if "--verbose" in tokens[:3] or "--no-verbose" in tokens[:3]:
        return list(tokens)
    return [tokens[0], "--no-verbose", *tokens[1:]]


def _mirror_workspace_config(base_cwd: Path, workdir: Path) -> None:
    source = base_cwd / ".chemsmart"
    if source.is_dir():
        shutil.copytree(source, workdir / ".chemsmart", dirs_exist_ok=True)


def input_excerpt(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""
    text = (
        value.decode("utf-8", errors="replace")
        if isinstance(value, bytes)
        else str(value)
    )
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...<content omitted>...\n{text[-half:]}"


__all__ = [
    "DEFAULT_MAX_GENERATED_COUNT",
    "DEFAULT_MAX_GENERATED_FILE_BYTES",
    "DEFAULT_MAX_GENERATED_TOTAL_BYTES",
    "absolutize_file_args",
    "generated_inputs",
    "input_excerpt",
    "input_snapshot",
    "prepare_safe_runtime_environment",
    "safe_execution_argv",
]
