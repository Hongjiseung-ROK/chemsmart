"""A sentence that says what the host admits or refuses is a claim about
the host, and it is asked of the host.

The pyscf leaf told every session "No Hessian exists for an excited or a
correlated surface" for five days after 44499f2a made the project loader
admit a Hessian on an excited root; a second sentence, on the project
tool, still called PySCF ``td`` preview-only a week after it became
executable. Nothing went red for either, because a rule was "tested" when
it rendered. The evidence graph recorded the first contradiction by hand
as a ``supersedes`` edge and the model kept reading it.

So a rule that states a settings boundary carries the sections that make
it true, and each is put through ``render_project_yaml`` -- the handler
behind the model's own ``project_yaml`` call, which runs the live program
loader and ``validate()``. The day the host moves, the sentence goes red
here instead of misleading a session.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.projects import project_document, render_project_yaml
from chemsmart.agent.rules import POLICY_RULES, rules_by_id

pytestmark = pytest.mark.capability(
    "rule:leaf.pyscf.a_hessian_is_the_curvature_of_the_surface_it_names",
    "rule:leaf.pyscf.correlated_methods_are_ab_initio_values",
    "rule:leaf.pyscf.a_converged_reference_can_be_a_saddle",
    "rule:project.stage_keys_and_phases",
)


def _asked_of_the_host(boundary) -> tuple[str, str]:
    """What the model's project path does with this section."""

    document = project_document(
        program=boundary.program,
        sections={boundary.section: dict(boundary.settings)},
    )
    try:
        render_project_yaml(document)
    except (ContractError, ValueError) as exc:
        return "refused", f"{type(exc).__name__}: {exc}"
    return "admitted", ""


def _cases():
    return [
        pytest.param(
            rule.rule_id,
            boundary,
            id=f"{rule.rule_id}:{boundary.section}:{index}",
        )
        for rule in POLICY_RULES
        for index, boundary in enumerate(rule.boundaries)
    ]


@pytest.mark.parametrize("rule_id,boundary", _cases())
def test_a_stated_boundary_is_where_the_host_draws_it(rule_id, boundary):
    observed, reason = _asked_of_the_host(boundary)

    assert observed == boundary.verdict, (
        f"rule {rule_id} tells the model that {boundary.program} "
        f"{boundary.section} {dict(boundary.settings)} is "
        f"{boundary.verdict}, and the host {observed} it {reason}; the "
        "sentence is stale -- change the words, not the boundary"
    )


def test_the_sentences_that_state_pyscf_limits_carry_their_boundaries():
    """Guard the instrument: a rule that names what PySCF cannot do and
    carries nothing to check it with is the state this file exists to end."""

    rules = rules_by_id()
    for rule_id in (
        "leaf.pyscf.a_hessian_is_the_curvature_of_the_surface_it_names",
        "leaf.pyscf.correlated_methods_are_ab_initio_values",
        "project.stage_keys_and_phases",
    ):
        verdicts = {item.verdict for item in rules[rule_id].boundaries}
        assert verdicts == {"admitted", "refused"}, rule_id


def test_an_excited_root_hessian_is_refused_the_analytic_derivative():
    """The refusal a boundary above rests on, with the reason it gives.

    Before it, ``hessian_derivative: analytic`` on an excited root ran
    ``mf.Hessian()``: CUHK job 2140014 validated, with no finding, the
    ground state's all-real spectrum of planar formaldehyde under a
    surface record naming S1 root 1 and beside S1's own 9.1e-06 Eh/Bohr
    gradient, where the difference Hessian of that root has an imaginary
    mode at -503.9 cm-1 -- a saddle certified as a minimum.
    """

    (boundary,) = [
        item
        for item in rules_by_id()[
            "leaf.pyscf.a_hessian_is_the_curvature_of_the_surface_it_names"
        ].boundaries
        if dict(item.settings).get("hessian_derivative") == "analytic"
    ]
    observed, reason = _asked_of_the_host(boundary)

    assert observed == "refused"
    assert "reference's curvature" in reason
    assert "finite_difference" in reason
