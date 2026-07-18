"""Public facade for deterministic Gaussian and ORCA command contracts.

The program- and job-specific rules live in ``command_rules``. This module
keeps the established import path and dispatch order stable for callers.
"""

from __future__ import annotations

from pathlib import Path

from chemsmart.agent.harness.command_rules.coordinates import (
    coordinate_contract_issues,
)
from chemsmart.agent.harness.command_rules.gaussian import (
    dias_contract_issues,
    selection_contract_issues,
    td_project_issue,
)
from chemsmart.agent.harness.command_rules.models import (
    CommandContractIssue,
    ContractSeverity,
    reject,
)
from chemsmart.agent.harness.command_rules.qmmm import qmmm_contract_issues
from chemsmart.agent.harness.command_rules.tokens import has_option, token_index


def check_command_contracts(
    *,
    program: str,
    job: str,
    program_tokens: list[str],
    job_tokens: list[str],
    cwd: str | Path | None = None,
) -> tuple[CommandContractIssue, ...]:
    """Return semantic contract violations for one computational command."""

    normalized_program = str(program).strip().lower()
    normalized_job = str(job).strip().lower()
    issues: list[CommandContractIssue] = []

    if normalized_job == "qmmm":
        return (
            reject(
                "cmd.contract.qmmm_parent_job",
                (
                    "qmmm is a nested chemsmart subcommand and requires a "
                    "parent calculation such as opt, ts, sp, scan, or modred"
                ),
                {"program": normalized_program, "job": normalized_job},
                ("parent computational job before qmmm",),
            ),
        )

    if normalized_program == "gaussian":
        issues.extend(selection_contract_issues(normalized_job, job_tokens))

    if normalized_job in {"scan", "modred"}:
        issues.extend(
            coordinate_contract_issues(
                normalized_program,
                normalized_job,
                job_tokens[1:],
                program_tokens=program_tokens,
                cwd=cwd,
            )
        )

    if normalized_program == "gaussian" and normalized_job == "dias":
        issues.extend(
            dias_contract_issues(
                job_tokens[1:],
                program_tokens=program_tokens,
                cwd=cwd,
            )
        )

    qmmm_index = token_index(job_tokens[1:], "qmmm")
    if qmmm_index is not None:
        issues.extend(
            qmmm_contract_issues(
                normalized_program,
                normalized_job,
                program_tokens,
                job_tokens[qmmm_index + 2 :],
                cwd=cwd,
            )
        )

    if normalized_program == "gaussian" and normalized_job == "td":
        issue = td_project_issue(program_tokens, cwd=cwd)
        if issue is not None:
            issues.append(issue)

    if normalized_program == "xtb":
        has_model = has_option(
            program_tokens,
            ("-sm", "--solvent-model"),
        )
        has_solvent = has_option(
            program_tokens,
            ("-si", "--solvent-id"),
        )
        if has_model != has_solvent:
            issues.append(
                reject(
                    "cmd.contract.xtb_solvent_pair",
                    (
                        "xTB solvation requires both --solvent-model and "
                        "--solvent-id"
                    ),
                    {
                        "program": normalized_program,
                        "job": normalized_job,
                        "solvent_model_present": has_model,
                        "solvent_id_present": has_solvent,
                    },
                    ("xTB solvent model and solvent identifier",),
                )
            )

    if normalized_program == "orca" and normalized_job == "neb":
        neb_tokens = job_tokens[1:]
        has_restart = has_option(
            neb_tokens,
            ("-r", "--restarting-xyzfile"),
        )
        has_endpoint = has_option(
            neb_tokens,
            ("-e", "--ending-xyzfile"),
        )
        has_intermediate = has_option(
            neb_tokens,
            ("-i", "--intermediate-xyzfile"),
        )
        if has_restart and (has_endpoint or has_intermediate):
            issues.append(
                reject(
                    "cmd.contract.orca_neb_restart_exclusive",
                    (
                        "ORCA NEB restart mode cannot be combined with ending "
                        "or intermediate geometry files"
                    ),
                    {
                        "restart": has_restart,
                        "endpoint": has_endpoint,
                        "intermediate": has_intermediate,
                    },
                    ("restart alone, or endpoint with optional TS guess",),
                )
            )

    return tuple(issues)


# Preserve the historical public class identity for repr, pickling, and
# introspection while keeping its implementation dependency-light.
CommandContractIssue.__module__ = __name__


__all__ = [
    "CommandContractIssue",
    "ContractSeverity",
    "check_command_contracts",
]
