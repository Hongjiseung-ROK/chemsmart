"""A node whose input ChemSmart refused reaches the session with the reason.

The compile reply, the frontier and the review answer one question for such
a node -- why no input was written -- and the safe preview kept only the
exception's class. broken_symmetry on a triplet is refused by every
program's writer with both legal routes in the sentence; the session read
"ValueError", findings that restate rule ids, and an observation asserting
the singlet translation that had just been refused, while the review said
"compiled, not previewed" and routed to compiling again. Gaussian's refused
writer also left a 0-byte input whose read-back named five fields that were
never the problem. Measured through this path on the base (R10 Q26): 8 of
13 refusals reached the session as a class name. An archived session met
two such failures and went on to write ORCA's FlipSpin as native route
words (R10 Q15 g1, CUHK Slurm 2152875).

Driven through ``run_live_agent_session`` with only the provider transport
replaced by a script, so every reply asserted on is the one a model reads.
The oracle is the settings module's own refusal function, never a copy of
its words.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from chemsmart.jobs.settings import broken_symmetry_refusal

pytestmark = pytest.mark.capability(
    "tool:compile_command",
    "tool:inspect_workflow_frontier",
    "setting:orca:broken_symmetry",
    "setting:gaussian:broken_symmetry",
)

O2 = "2\ndioxygen\nO 0.0 0.0 0.0\nO 0.0 0.0 1.208\n"
WATER = (
    "3\nwater\nO 0.0 0.0 0.1173\nH 0.0 0.7572 -0.4692\n"
    "H 0.0 -0.7572 -0.4692\n"
)
STUB = "#!/bin/sh\n# ChemSmart agent-harness DISCOVERY STUB\nexit 1\n"
LEVEL = {
    "gaussian": {"functional": "b3lyp", "basis": "def2svp"},
    "orca": {"functional": "b3lyp", "basis": "def2-svp"},
}


def _fenced_host(monkeypatch, tmp_path):
    """A home whose server declares Gaussian and ORCA as discovery stubs,
    and a provider profile whose key is a placeholder no provider sees."""

    home = tmp_path / "home"
    config = home / ".chemsmart"
    (config / "server").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CHEMSMART_CONFIG_DIR", str(config))
    monkeypatch.delenv("CHEMSMART_AGENT_SERVER", raising=False)
    blocks = []
    for program, executable in (("gaussian", "g16"), ("orca", "orca")):
        folder = home / "stubs" / program
        folder.mkdir(parents=True)
        (folder / executable).write_text(STUB)
        (folder / executable).chmod(0o755)
        blocks.append(
            f"{program.upper()}:\n    EXEFOLDER: {folder}\n"
            "    LOCAL_RUN: true\n    SCRATCH: false\n"
        )
    (config / "server" / "local.yaml").write_text(
        "SERVER:\n    SCHEDULER: null\n    NUM_CORES: 4\n    MEM_GB: 8\n"
        "    NUM_HOURS: 1\n" + "".join(blocks)
    )
    agent = home / "agent.yaml"
    agent.write_text(
        "active: alibaba-token-plan\nfallback: []\nproviders:\n"
        "  alibaba-token-plan:\n    type: openai\n"
        "    api_key_env: ALIBABA_TOKEN_PLAN_KEY\n"
        "    model: deepseek-v4-flash-0731\n    context_tokens: 1000000\n"
        "    max_output_tokens: 262144\n"
        "    base_url: https://token-plan.ap-southeast-1.maas.aliyuncs.com"
        "/compatible-mode/v1\n"
        "    reasoning_effort: max\n    preserve_thinking: true\n"
    )
    keys = home / "keys.env"
    keys.write_text("ALIBABA_TOKEN_PLAN_KEY=sk-sp-placeholder-not-a-key\n")
    keys.chmod(0o600)
    return agent, keys


class _ScriptedModel:
    """Plays the model's tool calls, one list per turn, reading replies."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.replies: list[tuple[str, dict, str]] = []
        self._pending: list[tuple[str, str, dict]] = []

    def transport(self):
        model = self

        class Transport:
            turn = 0

            def __init__(self, **_kwargs):
                pass

            def set_timeout_seconds(self, _value):
                pass

            def close(self):
                pass

            def __call__(self, payload):
                seen = {
                    m.get("tool_call_id"): m.get("content")
                    for m in payload.get("messages") or ()
                    if m.get("role") == "tool"
                }
                for call_id, name, args in model._pending:
                    model.replies.append((name, args, seen.get(call_id)))
                model._pending = []
                Transport.turn += 1
                step = model.steps.pop(0) if model.steps else None
                calls = step(model) if step else "done"
                if isinstance(calls, str):
                    message = {"role": "assistant", "content": calls}
                else:
                    message = {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "",
                        "tool_calls": [],
                    }
                    for number, (name, args) in enumerate(calls):
                        call_id = f"call-{Transport.turn}-{number}"
                        model._pending.append((call_id, name, args))
                        message["tool_calls"].append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(args),
                                },
                            }
                        )
                return {
                    "id": f"scripted-{Transport.turn}",
                    "model": payload.get("model"),
                    "choices": [
                        {
                            "finish_reason": (
                                "tool_calls"
                                if message.get("tool_calls")
                                else "stop"
                            ),
                            "message": message,
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }

        return Transport

    def read(self, tool: str) -> list[str]:
        return [
            reply or "" for name, _args, reply in self.replies if name == tool
        ]


def _geometry_id(path) -> str:
    return "geometry-" + hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _stage(node, program, role, artifact):
    return {
        "node_id": node,
        "program": program,
        "jobtype": "sp",
        "project_role": role,
        "dependencies": [],
        "inputs": [
            {
                "binding_id": "filename",
                "artifact_class": "geometry_xyz",
                "artifact_id": artifact,
                "producer_node_id": "",
                "producer_output_id": "",
            }
        ],
        "expected_outputs": [
            {"output_id": "result", "artifact_class": f"{program}_output"}
        ],
        "unresolved_fields": [],
        "produces_observables": [],
        "support_state": "planned",
        "blocked_reason": "",
    }


def _session(monkeypatch, tmp_path, program):
    """A triplet broken-symmetry node beside a valid singlet node, compiled
    and read back through the frontier, in one scripted live session."""

    import chemsmart.agent.runtime.alibaba as alibaba
    from chemsmart.agent.live_session import run_live_agent_session

    agent, keys = _fenced_host(monkeypatch, tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "o2.xyz").write_text(O2)
    (workspace / "water.xyz").write_text(WATER)
    triplet = _geometry_id(workspace / "o2.xyz")
    singlet = _geometry_id(workspace / "water.xyz")
    envelope = tmp_path / "envelope.yaml"
    envelope.write_text(
        "schema_version: chemsmart.bounded-execution-envelope.v1\n"
        "mode: bounded-local\n"
        f"allowed_program_engines:\n  {program}: [cpu]\n"
        "resources:\n  execution_target: run\n  cores: 4\n  memory_gb: 8\n"
        "  gpu_count: 0\n  scratch_policy: server\n"
        "  node_timeout_seconds: 3000\n"
        "episode_wall_time_seconds: 5400\n"
        "postprocess_reserve_seconds: 600\nmax_engine_calls: 4\n"
        f"scratch_root: {tmp_path / 'scratch'}\n"
    )

    def capability(model):
        return json.loads(model.read("inspect_program")[-1])["result"][
            "capability"
        ]["receipt_sha256"]

    def establish(model, role, sections):
        return (
            "project_yaml",
            {
                "action": "establish",
                "program": program,
                "artifact_id": role,
                "capability_receipt_sha256": capability(model),
                "sections": {"gas": sections},
            },
        )

    script = _ScriptedModel(
        [
            lambda m: [
                (
                    "inspect_program",
                    {"program": program, "jobtype": "sp", "engine": "cpu"},
                )
            ],
            lambda m: [
                (
                    "bind_scientific_identity",
                    {
                        "input_artifact_id": triplet,
                        "charge": 0,
                        "multiplicity": 3,
                    },
                ),
                (
                    "bind_scientific_identity",
                    {
                        "input_artifact_id": singlet,
                        "charge": 0,
                        "multiplicity": 1,
                    },
                ),
                establish(
                    m, "bs-level", {**LEVEL[program], "broken_symmetry": True}
                ),
                establish(m, "plain-level", LEVEL[program]),
            ],
            lambda m: [
                (
                    "plan_calculation_stages",
                    {
                        "workflow_id": "wf",
                        "stages": [
                            _stage("o2-bs", program, "bs-level", triplet),
                            _stage("water", program, "plain-level", singlet),
                        ],
                    },
                )
            ],
            lambda m: [
                (
                    "plan_scientific_workflow",
                    {
                        "plan_id": "plan",
                        "workflow_id": "wf",
                        "required_output_ids": [],
                    },
                )
            ],
            lambda m: [
                ("compile_command", {"workflow_id": "wf", "node_id": "o2-bs"}),
                ("compile_command", {"workflow_id": "wf", "node_id": "water"}),
            ],
            lambda m: [("inspect_workflow_frontier", {"workflow_id": "wf"})],
            lambda m: "done",
        ]
    )
    monkeypatch.setattr(
        alibaba, "AlibabaTokenPlanHttpsTransport", script.transport()
    )
    result = run_live_agent_session(
        task="Compile both planned single points and stop.",
        provider="alibaba-token-plan",
        provider_config_file=agent,
        secret_file=keys,
        workspace=workspace,
        execution_enabled=False,
        approval_file=None,
        execution_envelope_file=envelope,
        exposure_mode="eager",
    )
    return script, result


@pytest.mark.parametrize("program", ["orca", "gaussian"])
def test_the_refusal_reaches_the_reply_the_frontier_and_the_review(
    monkeypatch, tmp_path, program
):
    """The program's own sentence, in all three places the session reads."""

    script, result = _session(monkeypatch, tmp_path, program)
    sentence = broken_symmetry_refusal(True, 3)
    assert sentence

    refused, previewed = script.read("compile_command")
    reply = json.loads(refused)["result"]
    assert json.loads(previewed)["result"]["status"] == "previewed"
    assert reply["status"] == "preview_failed"
    assert sentence in reply["refusal"], reply.get("refusal")

    frontier = json.loads(script.read("inspect_workflow_frontier")[-1])
    rows = frontier["result"]["approval_readiness"]["nodes"]
    blocking = next(row for row in rows if row["node_id"] == "o2-bs")
    assert sentence in blocking["blocking_reason"], blocking
    # The review's word is the same sentence, not "compiled, not previewed".
    assert sentence in result.final_text, result.final_text


def test_a_refused_writer_leaves_nothing_for_the_read_back_to_misread(
    monkeypatch, tmp_path
):
    """Gaussian refuses inside its writer, after the file is opened.

    The file it left was read back as an input that had dropped the
    functional, the basis, the state and broken_symmetry itself.
    """

    script, _result = _session(monkeypatch, tmp_path, "gaussian")
    reply = json.loads(script.read("compile_command")[0])["result"]
    receipt = reply["preview"]["safe_preview"]
    assert receipt["artifacts"] == [], receipt["artifacts"]
    assert not [
        finding
        for finding in reply["preview"]["critical_findings"]
        if finding["rule_id"] == "preview.semantic.mismatch"
    ], reply["preview"]["critical_findings"]


def test_a_refusal_carries_no_host_path_and_no_key():
    """The gate on what a refusal may say: the program's words, with each
    host path replaced by its role and nothing shaped like a key."""

    from chemsmart.agent.preview import public_refusal_message

    workspace = "/private/var/folders/xx/T/tmpabc123"
    said = public_refusal_message(
        f"Cannot read {workspace}/job/mol.xyz or /Users/someone/.chemsmart/"
        "server/local.yaml with key sk-sp-abcdef0123456789; B3LYP/G and "
        "wB97X-D3(BJ)/def2-SVP are method words, def2/J a basis",
        roles={workspace: "<preview-workspace>"},
    )
    assert "/private/var" not in said and "/Users/" not in said, said
    assert "<preview-workspace>/job/mol.xyz" in said, said
    assert "sk-sp-abcdef" not in said, said
    for words in ("B3LYP/G", "wB97X-D3(BJ)/def2-SVP", "def2/J"):
        assert words in said, said
    assert len(public_refusal_message("x" * 5000, roles={})) <= 800
