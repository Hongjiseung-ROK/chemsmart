# chemsmart multi-tool agent design
Status: research-only design note
Authoring stance: Anthropic Agents research style
Date: 2026-05-10
Scope: convert the current chemsmart planner/critic/executor stack into a true model-driven tool loop with explicit permission handling and an autonomous driving mode.
Repository note:
- This docs worktree (`session/cs-60`, commit `36f13c6e`) does not contain `chemsmart/agent/*` yet.
- The verified code references below were therefore taken from the canonical local checkout at `/Users/hongjiseung/developer/chemsmart`, where the required agent files exist.
- All file:line citations below refer to that checkout and use repository-relative paths.
Non-goals:
- This report does not propose chemistry-domain behavior changes.
- This report does not redesign the 10 current chemistry tools from scratch.
- This report does not add subagents.
- This report does not assume cloud-only execution.
Design invariants:
- The model must receive the full JSON-schema tool catalog on every model step.
- The model, not the harness, chooses which tool to call next.
- Permission Mode must surface every tool call to the user with three actions: allow once, allow always for this tool in this session, or deny.
- Driving Mode must run autonomously, but `run_local` and `submit_hpc` stay blocked unless the user explicitly enables a `--yolo`-style override.
- Anthropic and OpenAI providers must expose equivalent harness behavior even though their wire formats differ.
- Tool failures and denials must be returned to the model as tool results whenever possible, rather than immediately crashing the run.
- The system must remain resumable and observable through `DecisionLog`.
- User-facing chemistry indexing stays 1-based, consistent with repository conventions.
Terminology used in this report:
- **Current system** = the existing planner JSON call, critic JSON call, and sequential executor.
- **Target system** = a provider-native tool loop where the model emits tool calls directly.
- **Inherit** = behavior chemsmart can keep.
- **Invent** = new harness machinery chemsmart does not currently have.
- **Provider turn** = one raw Anthropic or OpenAI API response.
- **Tool round-trip** = assistant emits tool use, harness executes tool, harness returns tool result, model continues.
Source set:
- Local code: `chemsmart/agent/core.py`, `registry.py`, `providers.py`, `tools.py`, `services/conversation_memory.py`, `tui/screens/chat.py`, `tui/widgets/composer.py`, plus the approval overlay because it materially defines current permission UX.
- Web research: Anthropic tool-use docs, Anthropic streaming docs, Claude Code Agent SDK permission and hook docs, OpenAI Responses/function-calling docs, OpenAI Codex loop docs, Continue docs, Goose docs, Aider docs, smolagents docs.
## 1. Current vs Target Architecture (Plan-then-Execute → Tool-Loop)
### Current architecture in one sentence
chemsmart currently uses a two-LLM-fronted, one-pass execution pipeline:
1. planner turns the user request into a static `Plan`,
2. executor runs non-risky steps,
3. critic judges dry-run artifacts,
4. executor optionally pauses before risky tools,
5. executor finishes the rest of the static plan.
That is visible in `AgentSession.run()` and `_continue_run()`.
- `run()` logs the request, calls `_planner_call()`, stores the returned `Plan`, and then hands the plan to `_continue_run()` (`chemsmart/agent/core.py:235-276`).
- `_continue_run()` walks `plan.steps` in order, stops at the first risky tool, optionally previews submission, calls the critic once, maybe pauses, then resumes linear execution (`chemsmart/agent/core.py:278-500`).
### Target architecture in one sentence
chemsmart should become a true tool-using agent loop:
1. user message + tool catalog go to the model,
2. model emits zero, one, or many tool calls,
3. harness approves or denies them per mode,
4. harness executes approved tools,
5. harness returns tool results to the model,
6. loop repeats until the model emits a final assistant answer.
### What Claude Code does today, and what matters here
Claude Code already operates as a tool loop rather than a plan-then-execute batch.
- Anthropic documents the same core loop in the Agent SDK: tools are sent with the request, Claude chooses tools, permissions govern execution, tool results go back into the loop, and the model may continue with more tool calls or a final answer ([Claude Code Agent SDK loop](https://code.claude.com/docs/en/agent-sdk/agent-loop)).
- Anthropic also documents that when multiple tool calls appear in one turn, read-only tools may run concurrently while mutating tools stay sequential ([Claude Code Agent SDK loop](https://code.claude.com/docs/en/agent-sdk/agent-loop)).
- Claude’s lower-level Messages API has the same assistant `tool_use` → user `tool_result` structure, with strict formatting rules ([Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)).
### What Codex CLI does today, and what matters here
Codex’s public architecture write-up describes the exact harness pattern chemsmart now needs.
- Codex calls the model, executes tool calls, appends outputs, and repeats until the model ends with an assistant message ([OpenAI Codex loop](https://openai.com/index/unrolling-the-codex-agent-loop/)).
- Codex’s public docs also center approval modes and sandboxing as first-class runtime controls, not afterthought UI switches ([Codex CLI docs](https://developers.openai.com/codex/cli)).
### What chemsmart can inherit
From the current implementation, chemsmart can keep:
- the `AgentSession` state machine shell,
- the `DecisionLog` file format idea,
- the 10 chemistry tools and their business logic,
- the TUI tailing/logging model,
- the `ConversationMemory` summarization layer,
- deterministic guards around malformed chemistry inputs,
- the existing notion that `run_local` and `submit_hpc` are high-risk.
### What chemsmart must invent
A real tool loop requires new harness concepts that the current system does not yet possess.
1. A provider-neutral representation of assistant tool calls.
2. A provider-neutral representation of tool results and denials.
3. A resumable per-turn loop state, not just a stored static plan.
4. A permission engine that can intercept every tool call, not only risky ones.
5. A concurrency scheduler for parallel read-only tool calls.
6. A handle system for opaque Python objects such as `Molecule`, settings objects, and `Job` objects.
7. A truncation/summarization strategy for oversized tool outputs.
8. A turn budget and loop budget system.
9. A cooperative interrupt path.
10. A better catalog boundary between user-facing tool parameters and harness-only/internal parameters.
### Why the handle system is the key hidden blocker
This is the most important architectural fact that is easy to miss.
The current planner can emit `$stepN` references because the harness resolves them later with `_resolve_refs()` and `_resolve_ref_string()` (`chemsmart/agent/core.py:1549-1577`).
That hidden reference system is doing crucial work:
- it lets the planner talk about Python objects that are not JSON-native,
- it keeps tool schemas superficially simple even when the real runtime objects are complex,
- it allows later steps to consume a prior `Molecule`, settings object, or `Job` instance without ever serializing those objects through the model.
A true provider-native tool loop cannot rely on ad hoc `$stepN` strings alone.
Why not:
- Anthropic and OpenAI will validate tool inputs against JSON-schema-like contracts.
- The model will call tools incrementally across multiple provider turns, not inside one planner blob.
- The harness must have stable, serializable, resumable references across pauses, resumes, and approval denials.
So the target architecture is not just “turn on tools.”
It is “replace hidden `$stepN` object passing with explicit runtime handles.”
### Recommended target mental model
The clean target is:
- Tools return either plain JSON values or typed **artifact handles**.
- Later tools accept handles, not raw Python objects.
- The harness maintains an object store that maps handle IDs to in-memory or on-disk objects.
- The model never sees the raw Python object graph.
Example handle vocabulary:
- `mol_0001`
- `gset_0002`
- `oset_0003`
- `job_0004`
- `dryrun_0005`
- `runtime_0006`
This is the main invention needed to make the rest of the design coherent.
### Recommended verdict for section 1
Move from **plan-then-execute** to **tool-loop with typed handles**.
Do not try to preserve the current static planner as the primary brain.
Keep planner-like summaries only as compatibility shims or optional observability surfaces.
## 2. Verified Architectural Findings (file:line refs)
### Reading note
This section is intentionally evidence-heavy.
It separates facts from recommendations.
### `chemsmart/agent/core.py`
#### Session skeleton and current orchestration
- `DecisionLog` is append-only JSONL with `kind`, `payload`, `rationale`, and timestamp (`chemsmart/agent/core.py:130-155`).
- `AgentSession` owns provider, registry, transport, session root, state, session dir, decision log, conversation history, and LLM stats (`chemsmart/agent/core.py:157-176`).
- `run()` starts or continues a turn, writes a `request` entry, refreshes conversation history, calls `_planner_call()`, stores the plan, logs it, and then executes `_continue_run()` (`chemsmart/agent/core.py:235-276`).
- `_continue_run()` is the real orchestrator. It has explicit parameters for `dry_submit`, `pause_before_risky`, `allow_remote_unknown`, `allow_critic_override`, and `rerender_plan` (`chemsmart/agent/core.py:278-286`).
#### Risk gating
- Risky tools are hard-coded as `_RISKY_TOOLS = {"run_local", "submit_hpc"}` (`chemsmart/agent/core.py:26`).
- `_continue_run()` runs non-risky steps first and breaks at the first risky step (`chemsmart/agent/core.py:351-358`).
- If `pause_before_risky` is enabled, the run returns `pending_approval=True` and `next_risky_tool` before risky execution proceeds (`chemsmart/agent/core.py:421-443`).
- In dry-submit mode, `submit_hpc` is not actually executed; it is recorded as skipped (`chemsmart/agent/core.py:445-459`).
#### Planner and critic
- `_planner_call()` loads `planner.md`, serializes the current tool list with `self.registry.openai_tool_defs()`, and embeds it into the user JSON payload (`chemsmart/agent/core.py:507-535`).
- `_critic_call()` loads `critic.md` and passes the plan plus dry-run inputs as JSON (`chemsmart/agent/core.py:537-560`).
- `_llm_json_call()` always calls `provider.chat(..., tools=None, ...)` even though providers support a `tools` argument (`chemsmart/agent/core.py:562-608`).
This is the single clearest proof that the current system is **not** yet a direct tool-using agent.
The system sends the tool schema to the model as prompt content, but explicitly disables tool calling at the provider layer.
#### Current step execution contract
- `_execute_step()` resolves `$stepN` references before execution (`chemsmart/agent/core.py:703-715`, `1549-1577`).
- It writes `tool_call`, invokes `registry.call()`, writes `tool_error` or `tool_result`, and raises on error (`chemsmart/agent/core.py:717-778`).
- Because `_execute_step()` raises on tool error, the current harness aborts the run instead of giving the model a chance to self-correct.
- `_preview_submit_step()` is a special non-mutating preflight for `submit_hpc`, forcing `execute=False` and logging `tool_preview` plus `tool_preview_result` (`chemsmart/agent/core.py:780-827`).
- `_record_skipped_step()` logs a `tool_skipped` entry for dry-submit skips (`chemsmart/agent/core.py:829-844`).
#### Current response parsing is JSON-only, not tool-aware
- `_parse_json_response()` expects parsed JSON, direct JSON content, or raw text that can be JSON-decoded (`chemsmart/agent/core.py:1367-1396`).
- `_extract_text()` knows how to pull text from Anthropic text blocks or OpenAI chat content, but it does not normalize tool calls into a first-class internal structure (`chemsmart/agent/core.py:1469-1495`).
This matters because the current provider abstraction cannot yet interpret assistant tool calls at all.
#### Current hidden step-reference system
- `_REFERENCE_RE` defines the `$stepN` pattern (`chemsmart/agent/core.py:29-31`).
- `_resolve_refs()` recursively replaces reference strings in args (`chemsmart/agent/core.py:1549-1559`).
- `_resolve_ref_string()` restores prior tool results or sub-fields of prior results (`chemsmart/agent/core.py:1562-1577`).
This is a planner-era convenience that needs replacement with explicit handles in the new loop.
### `chemsmart/agent/registry.py`
#### Tool catalog assembly
- `ToolSpec.openai_tool_def()` builds OpenAI-style tool definitions by using the input model’s JSON schema and the function docstring as description (`chemsmart/agent/registry.py:25-55`).
- `ToolRegistry.default()` registers exactly 10 tools: `build_molecule`, `recommend_method`, `build_gaussian_settings`, `build_orca_settings`, `build_job`, `dry_run_input`, `validate_runtime`, `run_local`, `extract_optimized_geometry`, and `submit_hpc` (`chemsmart/agent/registry.py:61-80`).
- `openai_tool_defs()` simply maps all specs through `openai_tool_def()` (`chemsmart/agent/registry.py:82-86`).
#### Validation behavior
- `normalize_args()` attempts model validation but falls back to the original payload on validation failure (`chemsmart/agent/registry.py:88-106`).
- `call()` validates again, returns structured `{"ok": False, "error": ...}` on validation errors, and returns the same structured error wrapper on runtime exceptions (`chemsmart/agent/registry.py:108-143`).
This split is workable for a tool loop, but it implies two design decisions:
- normalization is lenient,
- actual execution is guarded but error-returning.
The current executor then turns those returned errors into exceptions.
#### Schema weakness for opaque types
- `_schema_friendly_annotation()` falls back to `Any` when a type is not JSON-schema-friendly, logging a warning (`chemsmart/agent/registry.py:216-232`).
This is the direct cause of weak tool schemas for `Molecule`, `Job`, and transport-like parameters.
### `chemsmart/agent/providers.py`
#### Provider capability already exists
- `AnthropicProvider.chat()` accepts `tools`, passes them through to `messages.create()` when present, and returns `model_dump()` (`chemsmart/agent/providers.py:41-69`).
- `OpenAIProvider.chat()` accepts `tools`, passes them through to `chat.completions.create()` when present, and returns `model_dump()` (`chemsmart/agent/providers.py:90-117`).
So the provider layer is **not** the main blocker.
The blocker is the core loop above it.
#### Usage extraction
- `extract_response_usage()` already normalizes Anthropic `input_tokens` / `output_tokens` and OpenAI `prompt_tokens` / `completion_tokens` into one shape (`chemsmart/agent/providers.py:190-209`).
That logic can stay.
### `chemsmart/agent/tools.py`
#### Current 10-tool surface
The 10 currently exposed tools are real chemistry-domain capabilities, not toy stubs.
- `build_molecule()` loads a molecule from file (`chemsmart/agent/tools.py:160-166`).
- `build_gaussian_settings()` constructs validated Gaussian settings and also handles `scan_definition` normalization (`chemsmart/agent/tools.py:169-217`).
- `build_orca_settings()` constructs validated ORCA settings and also infers some ab initio cases (`chemsmart/agent/tools.py:220-320`).
- `build_job()` turns molecule + settings into a canonical job kind (`chemsmart/agent/tools.py:403-445`).
- `dry_run_input()` renders the input file and returns path + text (`chemsmart/agent/tools.py:447-468`).
- `validate_runtime()` inspects local requirements and remote unknowns (`chemsmart/agent/tools.py:471-558`).
- `run_local()` executes locally and returns output summaries (`chemsmart/agent/tools.py:561-597`).
- `extract_optimized_geometry()` parses a completed log to recover a final structure (`chemsmart/agent/tools.py:600-625`).
- `submit_hpc()` reconstructs a real submission path and may execute transport (`chemsmart/agent/tools.py:627-679`).
- `recommend_method()` maps project/task information to chemistry method suggestions (`chemsmart/agent/tools.py:682-772`).
#### Hidden model-facing problems inside the current signatures
Some parameters are appropriate for a static planner but bad for direct tool calling.
- `build_job()` takes raw `Molecule` and settings objects (`chemsmart/agent/tools.py:403-409`).
- `dry_run_input()`, `validate_runtime()`, `run_local()`, `extract_optimized_geometry()`, and `submit_hpc()` all take raw `Job` objects (`chemsmart/agent/tools.py:447-475`, `561-633`).
- `submit_hpc()` also exposes `transport` and `execute`, which are harness concerns, not model intent (`chemsmart/agent/tools.py:627-633`).
- `build_job()` exposes `jobrunner`, which is also an internal/runtime concern (`chemsmart/agent/tools.py:403-409`).
These signatures are compatible with the current hidden reference mechanism.
They are poor fits for strict, user-visible, provider-native tool schemas.
#### Risk semantics already encoded in behavior
- `validate_runtime()` returns `ok`, `local_issues`, and `remote_unknown`, which is already a useful preflight surface (`chemsmart/agent/tools.py:471-558`, `907-923`).
- `run_local()` actually executes the job (`chemsmart/agent/tools.py:561-597`).
- `submit_hpc()` can reconstruct and submit a real script, and `execute=False` is an important non-mutating path (`chemsmart/agent/tools.py:627-679`, `1073-1081`).
- `submit_hpc()` also performs duplicate-check logic (`chemsmart/agent/tools.py:638-647`, `1084-1096`).
These are strong building blocks for driving-mode policy.
### `chemsmart/agent/services/conversation_memory.py`
#### Current memory model
- `ConversationMemory` stores turn summaries, not raw provider message histories (`chemsmart/agent/services/conversation_memory.py:55-169`).
- `prompt_context()` keeps recent turns, older turn summaries, and an approximate token budget (`chemsmart/agent/services/conversation_memory.py:118-151`).
- `_DEFAULT_TOKEN_BUDGET` is 900 tokens, and several per-field truncation constants cap request/rationale/result lengths (`chemsmart/agent/services/conversation_memory.py:12-17`).
- `_trim_context_to_budget()` aggressively removes older summaries, reusable results, rationale, and finally truncates requests when needed (`chemsmart/agent/services/conversation_memory.py:170-217`).
#### What is summarized today
- Tool summaries are derived from `tool_result` plus the earlier `tool_call` args (`chemsmart/agent/services/conversation_memory.py:94-108`, `220-260`).
- Session completion status is derived from `session_summary` (`chemsmart/agent/services/conversation_memory.py:110-116`).
This means current memory is already optimized for **summaries of tool work**, which is a good fit for a tool loop.
But:
- it does not preserve provider-native tool call IDs,
- it does not preserve raw assistant tool-use messages,
- it is not sufficient by itself to reconstruct an in-progress provider turn.
### `chemsmart/agent/tui/screens/chat.py`
#### Current execution split between planning and approval
- `run_agent_session()` calls `AgentSession.run(..., dry_submit=True, pause_before_risky=True)` (`chemsmart/agent/tui/screens/chat.py:193-210`).
- `resume_agent_session()` continues a paused session in the same dry, approval-first mode (`chemsmart/agent/tui/screens/chat.py:212-235`).
- `execute_agent_session()` resumes with `dry_submit=False` and `pause_before_risky=False` (`chemsmart/agent/tui/screens/chat.py:237-254`).
This is the current two-phase UX:
- first pass = prepare and pause,
- second pass = actually execute.
#### Current approval state
- The screen tracks `_pending_approval`, `_pending_risky_tool`, and `_approval_session_granted` (`chemsmart/agent/tui/screens/chat.py:113-118`).
- On worker success with `pending_approval`, the footer switches to “Approval required for X” (`chemsmart/agent/tui/screens/chat.py:327-343`).
- `_request_approval()` pushes an `ApprovalOverlay` for the expected tool (`chemsmart/agent/tui/screens/chat.py:1101-1117`).
- `_handle_approval_result()` supports deny, approve once, approve for session, or revise (`chemsmart/agent/tui/screens/chat.py:1119-1134`).
- `_approve_current_request()` resumes real execution on the paused session (`chemsmart/agent/tui/screens/chat.py:1135-1146`).
#### Current command surface
- `/submit` and `/run` are the current approval entry points, with plain-mode variants `yes|session|no|revise <instruction>` (`chemsmart/agent/tui/screens/chat.py:924-959`).
- Help text explicitly describes `/submit` as approving pending HPC submission and `/run` as approving pending local execution (`chemsmart/agent/tui/screens/chat.py:963-980`).
#### Current interrupt semantics
- `action_soft_cancel()` is a double-`Ctrl+C` quit affordance, not a genuine agent interrupt (`chemsmart/agent/tui/screens/chat.py:383-402`).
- The screen explicitly tells the user the current step may still finish because the agent run is “not cooperatively interruptible yet” (`chemsmart/agent/tui/screens/chat.py:394-399`).
- `action_dismiss_overlay()` only dismisses modal overlays; it is not a loop interrupt (`chemsmart/agent/tui/screens/chat.py:414-416`).
This is direct evidence that an ESC-style interrupt does not exist today.
### `chemsmart/agent/tui/widgets/composer.py`
- The composer binds `enter`, `ctrl+j`, `shift+enter`, `ctrl+g`, and `@` (`chemsmart/agent/tui/widgets/composer.py:25-31`).
- There is no approval or interrupt binding here.
- There is no mode toggle or inline permission affordance here.
So the current permission UX lives above the composer, not within it.
### `chemsmart/agent/tui/widgets/popups/approval.py`
This file was not on the user’s required list, but it is decisive evidence for the current permission model.
- `ApprovalOverlay` offers `y` approve once, `n` deny, `s` approve session, `r` revise, and `escape` cancel (`chemsmart/agent/tui/widgets/popups/approval.py:21-31`).
- The copy says `y once · n deny · s this-session · r decline-and-revise` (`chemsmart/agent/tui/widgets/popups/approval.py:63-80`).
- The overlay is currently designed around **risky step approval**, not **every tool-call approval** (`chemsmart/agent/tui/widgets/popups/approval.py:138-155`).
### Verified synthesis
The local evidence supports five precise conclusions.
1. The provider layer already accepts tools.
2. The core loop explicitly disables provider-native tool use.
3. The current runtime depends on hidden `$stepN` reference resolution for opaque objects.
4. The current UI only asks approval for the first risky tool, not every tool call.
5. The current system treats tool errors as terminal executor failures, not model-visible observations.
Those five facts drive the entire recommendation.
## 3. Tool-Loop Design — turn structure (assistant → tool_use → tool_result → next assistant), parallel tool_use handling, max-iter guard, provider parity (Anthropic content blocks vs OpenAI tool_calls)
### Recommendation summary
Adopt a **single orchestrator loop** with a provider adapter layer.
The loop should be provider-neutral at the core and provider-specific only at the edges.
### Core loop state machine
Each user turn should have these phases:
1. `user_input_received`
2. `model_step_requested`
3. `assistant_message_received`
4. `tool_requests_extracted`
5. `permission_resolution`
6. `tool_execution`
7. `tool_results_recorded`
8. `model_step_requested` again
9. `final_assistant_message_received`
10. `turn_completed`
### Proposed internal objects
Use explicit internal types.
#### `ToolRequest`
Fields:
- `request_id`
- `provider`
- `provider_call_id`
- `name`
- `arguments_json`
- `arguments`
- `is_read_only`
- `risk_level`
- `parallel_group`
- `raw_provider_payload`
#### `ToolOutcome`
Fields:
- `request_id`
- `provider_call_id`
- `name`
- `status` = `ok | denied | error | skipped | interrupted`
- `result`
- `display_result`
- `raw_result`
- `error_type`
- `error_message`
#### `ArtifactHandle`
Fields:
- `handle_id`
- `kind` = `molecule | gaussian_settings | orca_settings | job | dry_run | runtime | run_result | submission_preview`
- `storage_ref`
- `summary`
### The new core algorithm
Pseudo-flow:
1. Build provider messages for the current turn.
2. Pass the full tool catalog in the provider’s native `tools` field.
3. Receive the assistant response.
4. Normalize it into:
   - assistant text blocks,
   - zero or more `ToolRequest` objects,
   - provider stop reason,
   - usage,
   - raw payload.
5. If there are no tool requests:
   - record assistant output,
   - finalize the turn.
6. If there are tool requests:
   - classify read-only vs mutating,
   - resolve permission policy,
   - execute approved requests,
   - synthesize denial/error outcomes for the rest,
   - send the resulting tool outcomes back to the model,
   - iterate.
### Why one loop is better than keeping planner plus executor
A single tool loop removes duplicated reasoning surfaces.
Today:
- planner reasons once,
- critic reasons once,
- executor is blind and procedural.
In the target design:
- the main model reasons with live tool observations,
- the harness handles safety, permissions, and deterministic validation,
- any separate critic becomes optional and evidence-aware.
### Required provider-neutral invariants
The orchestrator should enforce these invariants regardless of provider.
1. Every assistant tool request is either followed by a matching tool result, a matching denial, or a matching interrupt result.
2. No tool request is silently dropped.
3. Every tool result is written to disk before being returned to the model.
4. Parallel execution is limited to tools marked read-only.
5. Mutating tools are always serialized.
6. The loop stops if it exceeds configured turn or tool budgets.
7. The loop stops if it sees repeated no-progress patterns.
8. The loop can resume after approval pauses without losing call IDs.
9. The loop can reconstruct current-turn provider history from persisted events.
### Anthropic path
Anthropic’s Messages API represents tool calls as `tool_use` content blocks and expects the harness to reply with a `user` message containing `tool_result` blocks.
Relevant external facts:
- Claude client tools are defined in the request `tools` parameter with `name`, `description`, and `input_schema` ([Anthropic define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)).
- Tool use returns a `stop_reason` of `tool_use` plus one or more `tool_use` blocks ([Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)).
- Tool result blocks must immediately follow the assistant tool-use message; no interleaving messages are allowed ([Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)).
- For parallel tool use, all `tool_result` blocks must be sent back in one `user` message ([Anthropic parallel tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)).
- Anthropic supports fine-grained streaming for tool arguments, but warns that partial or invalid JSON may appear while streaming ([Anthropic fine-grained tool streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming)).
#### Anthropic normalization rules
Map Anthropic responses into the internal loop as follows.
- Assistant `text` blocks become assistant display content.
- Assistant `tool_use` blocks become `ToolRequest` objects.
- `tool_use.id` becomes `provider_call_id`.
- `tool_use.input` becomes parsed arguments.
- `stop_reason=tool_use` means “the model is waiting for tool outcomes.”
#### Anthropic reply rules
When chemsmart returns tool outcomes:
- send one `user` message,
- place all `tool_result` blocks first,
- optionally append text after the tool results,
- never insert an unrelated assistant or user message between tool use and tool result.
#### Anthropic denial shape
A denied tool should still produce a `tool_result` block.
Recommended content:
- `tool_use_id`: original tool-use id,
- `is_error`: `true`,
- `content`: a concise JSON string or text payload explaining the denial.
Example payload idea:
- `{"ok": false, "error": {"type": "PermissionDenied", "message": "User denied submit_hpc in Permission Mode."}}`
This satisfies Anthropic’s requirement that the model see a result for every emitted tool call.
### OpenAI path
OpenAI’s best fit for this design is the Responses API, even though chemsmart’s current provider uses `chat.completions.create()`.
Relevant external facts:
- OpenAI’s function-calling guidance explicitly assumes zero, one, or multiple function calls in a response ([OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)).
- The standard loop is: preserve response output, execute each function, append a `function_call_output` item with matching `call_id`, and call the model again ([OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)).
- For reasoning models, reasoning items returned with tool calls should also be passed back with tool outputs ([OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)).
- OpenAI’s own agent-loop write-up says the client orchestrator gets model output, invokes tools, and passes results back until completion ([OpenAI Responses loop](https://openai.com/index/equip-responses-api-computer-environment/)).
#### OpenAI normalization rules
Map OpenAI responses into the internal loop as follows.
- assistant text or `output_text` becomes assistant display content,
- each `function_call` item becomes a `ToolRequest`,
- `call_id` becomes `provider_call_id`,
- JSON-decoded `arguments` become parsed args,
- preserve all reasoning items and tool call items inside current-turn provider history.
#### OpenAI reply rules
When chemsmart returns tool outcomes:
- append all prior response output items for the current tool round,
- append one `function_call_output` item per tool call,
- keep `call_id` stable,
- call the model again.
#### OpenAI denial shape
A denied tool should return a `function_call_output`, not a harness-side silent block.
Recommended output string:
- `{"ok": false, "error": {"type": "PermissionDenied", "message": "Denied by user in Permission Mode"}}`
The model can then:
- choose another tool,
- ask for a different path,
- explain that it is blocked.
### Provider parity contract
The internal loop must present the same semantics to the rest of chemsmart.
That means:
- both providers surface `ToolRequest[]`,
- both providers accept `ToolOutcome[]`,
- both providers can stream assistant text,
- both providers can return multiple tool requests per turn,
- both providers support final assistant completion without tool calls.
### Suggested adapter boundary
Add an adapter layer with two operations.
#### `provider_step(request)`
Input:
- provider-specific messages/history,
- full tool catalog,
- model options,
- budget state.
Output:
- normalized assistant text,
- normalized tool requests,
- provider continuation state,
- usage,
- raw payload.
#### `provider_tool_result_inputs(outcomes)`
Input:
- `ToolOutcome[]`
Output:
- provider-native tool-result message/items to feed into the next provider step.
### Parallel tool-use policy
Do not blindly execute all parallel tool calls in parallel.
Use a three-bucket scheduler.
#### Bucket A: safely parallel
Parallelize only tools marked both:
- read-only,
- side-effect free.
For the current 10 tools, the likely safe-parallel bucket is small.
Conservatively classify as parallel-safe only after refactoring signatures to handle-based inputs and after reviewing filesystem side effects.
Initial recommendation:
- `recommend_method`: parallel-safe.
- maybe `validate_runtime`: parallel-safe only if it is parameterized on independent handles and does not mutate files.
- maybe `dry_run_input`: keep sequential at first because it writes files.
- everything else: sequential.
#### Bucket B: sequential non-risky
Execute sequentially:
- `build_molecule`
- `build_gaussian_settings`
- `build_orca_settings`
- `build_job`
- `dry_run_input`
- `extract_optimized_geometry`
Even if some are logically side-effect free, keeping them sequential early reduces handle-store complexity.
#### Bucket C: serialized risky
Always serialized and approval-aware:
- `run_local`
- `submit_hpc`
### Why not parallelize more aggressively in wave 1
Chemistry workflows are dependency-heavy.
A speculative parallelizer that misclassifies file-writing or handle-creating steps will cause subtle bugs.
Codex and Claude Code can parallelize because many of their common tools are read-only search/navigation tools.
chemsmart’s tool catalog is more stateful.
### Max-iteration guard
Add explicit loop guardrails.
Recommended defaults for one user turn:
- `max_model_steps_per_turn = 12`
- `max_total_tool_calls_per_turn = 32`
- `max_consecutive_tool_errors = 4`
- `max_same_signature_retries = 2`
- `max_parallel_tool_calls_in_one_step = 4`
Reasoning:
- typical chemistry workflows should finish well below 12 model steps,
- 32 total tool calls leaves room for retries without allowing endless loops,
- two identical retries is enough for self-correction but stops degenerate repetition.
### No-progress detector
Stop the loop early if the harness sees any of these patterns twice.
1. Same tool name + same normalized args + same denial outcome.
2. Same tool name + same normalized args + same validation error.
3. Assistant emits a tool call whose required handle does not exist, twice in a row.
4. Assistant alternates between two equivalent failing tool calls.
When triggered:
- write a loop-limit or no-progress event,
- return a final assistant-visible tool error summary,
- ask the model for a final explanation rather than another tool call.
### Oversized tool-result strategy inside the loop
A tool loop fails if raw outputs consume all context.
Follow the Codex/Responses pattern of bounded tool outputs and keep full payloads on disk.
Recommended policy:
- persist full tool result artifact to session storage,
- produce a model-facing summary capped to `12_000` characters per tool,
- keep both the beginning and end when truncating,
- include `truncated=true`, `full_artifact_path`, and maybe `sha256`.
This directly addresses one of the required edge cases: oversized outputs.
### Streaming strategy
#### Anthropic
- Support text streaming immediately.
- Support tool-call streaming in wave 2.
- For fine-grained tool streaming, buffer until a complete JSON object is available.
- If the stream ends with partial JSON, emit a provider-parse tool denial/error result to the model rather than crashing the session.
#### OpenAI
- Stream assistant text when possible.
- Buffer function-call arguments until `response.function_call_arguments.done` or equivalent completion ([OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)).
- Preserve reasoning items and raw output items during streaming for the next step.
### Recommended “turn transcript” persistence
Persist both:
- provider-agnostic events for TUI/logging,
- provider-native raw turn payloads for exact replay and debugging.
That lets chemsmart:
- show a clean UI,
- resume accurately,
- debug provider drift.
### Recommendation for section 3
Implement a **provider-neutral tool loop with provider-specific adapters, explicit artifact handles, conservative parallelism, and strict no-progress guards**.
That is the minimum design that behaves like Claude Code or Codex without inheriting their exact tool surfaces.
## 4. Permission Mode UX — TUI flow, three actions (allow-once / allow-always-this-tool-this-session / deny), how denial returns to model
### Target product definition
Permission Mode is the fully explicit mode.
Every tool call pauses before execution.
The user must choose one of exactly three primary actions:
1. allow once
2. allow always for this tool in this session
3. deny
### Why this differs from the current TUI
Today the TUI only pauses for the first risky tool in a prepared plan.
Evidence:
- planning pass runs with `pause_before_risky=True` (`chemsmart/agent/tui/screens/chat.py:193-210`),
- approval state is keyed to `_pending_risky_tool` (`chemsmart/agent/tui/screens/chat.py:113-118`),
- `/run` and `/submit` are risky-tool-specific approval verbs (`chemsmart/agent/tui/screens/chat.py:924-959`),
- the popup copy is written around one risky action (`chemsmart/agent/tui/widgets/popups/approval.py:63-80`).
Permission Mode must generalize this from “first risky step” to “every tool request.”
### Recommended TUI flow
#### Step 1: assistant emits tool request(s)
As soon as the model emits one or more tool calls:
- render the assistant text,
- append pending tool request cards to the transcript,
- open the approval panel.
#### Step 2: approval panel shows one request at a time
Why one at a time:
- the current tool catalog is small,
- it preserves clarity,
- it simplifies session-scoped allow rules,
- it is easier to implement than a batch multi-select UI.
If the assistant emits multiple tool calls in one provider step:
- queue them in emission order,
- only auto-batch if all are read-only and identical in risk class,
- otherwise ask per tool.
### Recommended approval card contents
Each card should display:
- tool name,
- short tool description,
- normalized args,
- risk badge,
- side-effect summary,
- whether the tool is read-only or mutating,
- session rule currently in effect, if any.
For current chemistry tools, useful side-effect summaries include:
- `build_molecule`: reads structure file
- `dry_run_input`: writes input file
- `validate_runtime`: checks local/runtime state
- `run_local`: starts a local job
- `submit_hpc`: may submit to remote queue
### Recommended three-button mapping
#### allow once
- executes this exact tool request,
- no persistent approval rule added.
#### allow always for this tool in this session
- adds a temporary session rule keyed by tool name,
- future calls to the same tool auto-execute for the rest of the session,
- does not persist across sessions.
#### deny
- does not execute the tool,
- creates a denial outcome returned to the model,
- leaves the session alive.
### What to do with the current “revise” path
The current UI supports `r` revise (`chemsmart/agent/tui/widgets/popups/approval.py:22-31`, `119-132`).
I recommend **not** making revise one of the three primary actions in Permission Mode.
Reason:
- the user explicitly asked for a three-action model,
- revise is better represented as a normal follow-up user message,
- denial already gives the model a chance to react.
Recommended replacement:
- keep revise as a secondary keyboard shortcut or slash command,
- but do not present it as a primary approval button.
### Session rule model
Maintain two in-memory maps.
#### `session_allow_tools`
- key: tool name
- value: approval scope metadata
#### `session_deny_tools` (optional future extension)
- not required for wave 1,
- future-proof if the team later wants “always deny this tool.”
For the user’s requested design, wave 1 only needs the allow map plus per-request deny.
### Denial return path to the model
This part matters a lot.
The harness should not just stop and say “permission denied” to the human.
It should synthesize a proper tool result back to the model.
#### Anthropic denial reply
Return a `tool_result` block with:
- matching `tool_use_id`,
- `is_error=true`,
- concise JSON or text denial content.
#### OpenAI denial reply
Return a `function_call_output` item with:
- matching `call_id`,
- output string containing a structured denial payload.
### Why denial should return to the model
Claude Code and Continue both treat approvals as part of the live loop, not as a terminal harness exception.
- Claude Code’s SDK says denied tools are surfaced back to Claude, which usually adjusts course or reports that it cannot proceed ([Claude permissions](https://code.claude.com/docs/en/agent-sdk/permissions), [Claude agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop)).
- Continue’s handshake explicitly has permission before tool execution and then tool result back into the loop ([Continue Agent Mode](https://docs.continue.dev/ide-extensions/agent/how-it-works)).
chemsmart should do the same.
### TUI transcript representation for denial
Write three observable events.
1. `tool_use_request`
2. `tool_use_denied`
3. a provider-visible denial tool result
In the transcript:
- show the pending card,
- mark it denied in red,
- append a short system note like “Denied by user; model will be asked to continue without this action.”
### Example denial sequence
1. assistant requests `submit_hpc(job_handle="job_0004")`
2. user clicks deny
3. TUI marks request denied
4. harness sends denial as tool result to model
5. model may:
   - suggest `dry_run_input` or `validate_runtime` again,
   - ask the user for a different execution path,
   - end with “I cannot submit without approval.”
### Permission Mode and multi-call turns
If the model emits three read-only tool calls in one turn, Permission Mode still requires approval for each because that is the user’s stated requirement.
Recommended nuance:
- show “1 of 3”, “2 of 3”, “3 of 3”,
- allow the user to apply “allow always this tool this session” mid-queue,
- auto-skip later requests for that same tool if the session rule now matches.
### Suggested slash commands
Keep the current `/run` and `/submit` for compatibility, but add generic approval commands.
Suggested additions:
- `/allow`
- `/allow-session`
- `/deny`
- `/permissions`
These are clearer once approvals are no longer only about `run_local` or `submit_hpc`.
### Recommended footer states
Add explicit footer phases:
- `APPROVAL_PENDING`
- `APPROVAL_QUEUE`
- `APPROVAL_DENIED_CONTINUING`
This avoids overloading `DRY_RUN_READY` for all approval states.
### Recommended section 4 verdict
Permission Mode should become a **generic per-tool approval queue** with exactly three primary actions and denial-as-tool-result semantics.
Do not keep the current risky-tool-only approval surface as the long-term UX.
## 5. Driving Mode — autonomous loop, risky-tool allowlist (forbid run_local + submit_hpc unless --yolo), token/iter budget, ESC interrupt
### Target product definition
Driving Mode is the autonomous mode.
The agent runs without per-tool prompts.
But autonomy is policy-bounded, not absolute.
### Recommended default rule set
Without `--yolo`:
- auto-allow safe tools,
- auto-deny `run_local`,
- auto-deny `submit_hpc`,
- return denials to the model as tool results.
With `--yolo`:
- allow `run_local`,
- allow `submit_hpc`,
- still apply deterministic guardrails,
- still preserve interrupt support,
- still log every approval decision as synthetic auto-approval events.
### Why the `--yolo` gate is necessary
The current code already encodes these tools as risky (`chemsmart/agent/core.py:26`).
The behavior of the tools justifies that classification.
- `run_local()` can execute a real local job (`chemsmart/agent/tools.py:561-597`).
- `submit_hpc()` can submit to a real remote queue (`chemsmart/agent/tools.py:627-679`).
Driving Mode without a stronger gate would be less safe than the current system.
### What Claude Code does today that we should inherit conceptually
Claude’s SDK separates:
- allow rules,
- deny rules,
- permission modes,
- runtime approval callbacks,
- hooks.
It also supports model-classified `auto` mode in TypeScript, but still keeps deny rules and hooks in front of it ([Claude permissions](https://code.claude.com/docs/en/agent-sdk/permissions)).
What chemsmart should inherit:
- allowlist/denylist precedence,
- mode-based behavior,
- runtime observability.
What chemsmart should **not** inherit blindly:
- model-classified approval for chemistry execution in wave 1.
For chemsmart, a deterministic `--yolo` gate is better than a learned approval classifier in the first version.
### Driving Mode allow policy
Recommended wave-1 auto-allow list:
- `build_molecule`
- `recommend_method`
- `build_gaussian_settings`
- `build_orca_settings`
- `build_job`
- `dry_run_input`
- `validate_runtime`
- `extract_optimized_geometry`
Recommended wave-1 auto-deny list unless `--yolo`:
- `run_local`
- `submit_hpc`
### Why `dry_run_input` is allowed in Driving Mode even though it writes files
Because it is bounded, local, reversible, and already core to the current preflight workflow.
Still, the tool should be marked `mutates_state=true` in metadata even if it is not “risky.”
Driving Mode is not “read-only.”
It is “autonomous within a bounded safe set.”
### Token budget
The catalog must be sent every turn.
A local measurement on 2026-05-10 from `ToolRegistry.default().openai_tool_defs()` produced:
- 10 tools,
- 7,155 JSON characters,
- roughly 1,789 tokens.
Per-tool size outliers:
- `build_orca_settings` was the largest at about 607 approximate tokens.
- `build_gaussian_settings` was about 345 approximate tokens.
Implications:
- full-catalog-per-turn is acceptable today,
- but repeated loops still make the catalog a major fixed prompt cost,
- so Driving Mode needs loop budgets to prevent runaway catalog replay.
### Recommended budgets for Driving Mode
Per user turn:
- `max_model_steps_per_turn = 10`
- `max_total_tool_calls_per_turn = 24`
- `max_prompt_tokens_from_history = 4_000`
- `max_model_output_tokens_per_step = 2_048`
- `max_total_tool_result_chars_in_context = 32_000`
Per session:
- `max_consecutive_denials = 5`
- `max_consecutive_no_progress_steps = 3`
### Budget exhaustion behavior
On limit hit:
1. write a `loop_limit_exceeded` decision event,
2. stop executing further tools,
3. ask the model for one final user-facing response summarizing what it did and why it stopped,
4. return that final answer plus the limit reason.
### ESC interrupt design
The current TUI has no cooperative interrupt path and tells the user as much (`chemsmart/agent/tui/screens/chat.py:394-399`).
Driving Mode needs one.
### Recommended interrupt semantics
Bind `Esc` at the chat-screen level to `interrupt_agent_loop`.
On press:
- set `interrupt_requested=True` on the active session,
- stop scheduling new tool calls,
- if a tool is not yet running, mark it interrupted,
- if a tool is already running, let the tool boundary finish in wave 1,
- once control returns to the harness, send an interrupt result back to the model or finalize immediately.
### Why not kill the subprocess immediately in wave 1
Because the current tools do not expose uniform cancellation hooks.
`run_local` may already have launched external chemistry software.
A sloppy hard kill risks leaving partial outputs in worse shape than a controlled stop.
Wave-1 cooperative interrupt should therefore mean:
- stop after the current tool boundary,
- do not start the next tool.
### Future interrupt refinement
Wave 3 can add tool-specific cancellation hooks, for example:
- local subprocess cancellation for `run_local`,
- queue cancellation or no-submit interruption for `submit_hpc` previews,
- job-state synchronization with the jobs panel.
### Driving Mode and current dry-submit split
Driving Mode should not keep the current “run once in dry mode, then rerun in execute mode” UX.
Instead:
- safe tools run immediately,
- risky tools are denied unless `--yolo`,
- if `--yolo`, the model may proceed directly,
- `submit_hpc` can still route through a non-mutating preview substep internally before real execution.
### Recommended internal policy table
| Tool | Default Driving Mode | Driving Mode with `--yolo` | Notes |
| --- | --- | --- | --- |
| build_molecule | allow | allow | read-only file load |
| recommend_method | allow | allow | advisory |
| build_gaussian_settings | allow | allow | pure object build |
| build_orca_settings | allow | allow | pure object build |
| build_job | allow | allow | creates handle |
| dry_run_input | allow | allow | writes local input file |
| validate_runtime | allow | allow | local checks + remote unknown summary |
| extract_optimized_geometry | allow | allow | reads output logs |
| run_local | deny | allow | stateful local execution |
| submit_hpc | deny | allow | remote queue effect |
### Driving Mode verdict
Driving Mode should be **autonomous but deny-by-default for `run_local` and `submit_hpc` unless explicit `--yolo`**.
That is the right midpoint between current chemsmart caution and Claude/Codex-style autonomy.
## 6. Critic Role Change — pre-plan critic → post-tool-result critic; or drop; tradeoffs
### Current critic role
Today the critic is a one-shot post-dry-run gate inside a static plan executor.
- `_critic_call()` gets the plan plus dry-run inputs (`chemsmart/agent/core.py:537-560`).
- `_continue_run()` calls the critic after non-risky steps and before risky execution (`chemsmart/agent/core.py:379-397`).
- `_apply_deterministic_gates()` then merges runtime failures, malformed route-line checks, IRC keyword checks, and duplicate submit preview checks (`chemsmart/agent/core.py:1143-1218`).
### What changes in a real tool loop
Once the main model can see live tool results, the critic is no longer the only evidence-aware model.
The main model itself can now:
- inspect dry-run input text,
- inspect runtime validation summaries,
- see extracted geometry handoff evidence,
- react to denials or errors.
That weakens the case for a mandatory separate pre-risk gate on every request.
### Option A — keep critic, but move it post-tool-result
This is the safest migration path.
How it works:
1. main model drives tools,
2. after certain milestone results appear, harness invokes critic,
3. critic sees real tool outputs, not hypothetical planned steps,
4. critic verdict becomes one more tool result or gate event.
Recommended critic trigger points:
- after the first `dry_run_input` + `validate_runtime` pair,
- before `run_local`,
- before `submit_hpc`,
- after a denial if the model keeps pushing toward risky execution.
Advantages:
- preserves chemistry safety culture,
- critic sees actual evidence,
- avoids judging tools that were never executed,
- lower prompt drift because the plan is no longer the only artifact.
Disadvantages:
- still adds latency and cost,
- duplicates some reasoning the main agent could do,
- introduces another moving part in the loop.
### Option B — drop critic entirely
This is the cleanest architecture, but not the safest first migration.
Replace critic with:
- deterministic validators,
- permission policy,
- tool-result self-correction by the main model.
Advantages:
- simpler loop,
- fewer models or fewer model turns,
- less duplicated reasoning.
Disadvantages:
- chemistry-quality review depends more on tool descriptions and main-model competence,
- some current safety posture is lost,
- the team loses an explicit veto surface it already understands.
### Option C — convert critic into a callable internal tool
This is the most elegant long-term design.
Treat critic as a harness-owned diagnostic tool such as:
- `review_current_workflow`
It would be:
- invisible to users as a normal chemistry action,
- callable by the harness automatically,
- optionally callable by the main model in advanced mode.
Advantages:
- critic becomes just another loop participant,
- review output is tool-shaped and easier to log,
- better composability.
Disadvantages:
- more design work,
- easy to overcomplicate wave 1.
### My recommendation
Keep the critic in migration waves, but change its role.
#### Recommended role
- not a pre-plan critic,
- not a planner auditor,
- not a mandatory model for every advisory/chitchat turn,
- instead, a **post-tool-result chemistry reviewer** invoked before irreversible or expensive actions.
#### Recommended inputs
- normalized tool transcript for the current turn,
- latest dry-run input(s),
- latest runtime validation summary,
- current handle summaries,
- maybe the user request.
#### Recommended outputs
- `ok | warn | reject`,
- short rationale,
- concrete issues,
- optional “suggested next tool” hint for the main model.
### Where this differs from Claude Code and Codex
Claude Code and Codex do not usually insert a second general-purpose critic model in front of every tool action.
That is one thing chemsmart should **not** copy blindly.
The chemistry domain justifies a narrower reviewer layer.
So:
- inherit the tool loop,
- invent a chemistry-specific reviewer only where it is safety-positive.
### Section 6 verdict
Do **not** keep the current pre-plan critic shape.
Either:
- migrate it into a post-tool-result review stage before risky actions, or
- drop it after metrics prove the deterministic checks plus main-model loop are sufficient.
For the first migration, I recommend the first path.
## 7. Backward Compatibility — AgentSession.run() return shape; new DecisionLog kinds (tool_use_request, tool_use_approved, tool_use_denied)
### Compatibility principle
Do not force the TUI and CLI to rewrite everything at once.
Preserve the outer `AgentSession.run()` contract while gradually enriching it.
### Current return shape
Across the various branches in `run()` and `_continue_run()`, the session returns combinations of:
- `session_id`
- `session_dir`
- `plan`
- `plan_text`
- `critic_verdict`
- `completed_steps`
- `blocked`
- `dry_run_result`
- `dry_run_results`
- `runtime_result`
- `preview_submit`
- sometimes `results`
- sometimes `pending_approval`
- sometimes `next_risky_tool`
- sometimes `advisory_only`
- sometimes `is_chitchat`
Evidence appears in the main return sites in `_continue_run()` (`chemsmart/agent/core.py:313-328`, `333-346`, `407-419`, `429-443`, `475-488`).
### Recommended compatibility strategy
Keep existing keys in wave 1.
Add new keys rather than replacing old ones.
#### Keep
- `session_id`
- `session_dir`
- `critic_verdict`
- `blocked`
- `pending_approval`
- `next_risky_tool`
- `dry_run_results`
- `runtime_result`
- `preview_submit`
#### Add
- `assistant_output`
- `tool_requests`
- `tool_outcomes`
- `loop_state`
- `final_message`
- `approval_mode`
- `driver_mode`
- `interrupted`
- `limit_reason`
### What to do with `plan` and `plan_text`
Do not delete them in wave 1.
Instead, redefine them as compatibility projections.
#### `plan`
Synthetic projection of:
- tool calls already emitted this turn,
- pending tool requests queued for approval,
- maybe a tentative next-step summary if the model has described one in text.
#### `plan_text`
A human-readable transcript summary, not necessarily a full upfront plan.
This keeps older transcript cells useful while the UI migrates.
### Recommended new DecisionLog kinds
Keep the current kinds.
Add new ones.
#### Existing useful kinds to preserve
- `request`
- `plan`
- `tool_call`
- `tool_result`
- `tool_error`
- `tool_preview`
- `tool_preview_result`
- `tool_skipped`
- `critic_verdict`
- `llm_error`
- `session_summary`
Evidence for these comes from `run()`, `_execute_step()`, `_preview_submit_step()`, `_record_skipped_step()`, and `_log_llm_failure()` (`chemsmart/agent/core.py:252-265`, `393-397`, `685-700`, `717-844`).
#### New kinds to add
- `assistant_turn`
- `tool_use_request`
- `tool_use_approved`
- `tool_use_denied`
- `tool_use_interrupted`
- `tool_use_result`
- `tool_use_batch`
- `loop_limit_exceeded`
- `interrupt_requested`
- `provider_turn_raw`
### Why keep both `tool_call` and `tool_use_request`
Because they are not identical.
- `tool_use_request` means “model asked for this.”
- `tool_call` means “harness actually invoked this.”
That distinction matters for:
- denials,
- approvals,
- policy skips,
- interrupted queues,
- debugging hallucinated tool calls.
### Recommended approval event payloads
#### `tool_use_request`
- turn index
- provider
- provider call id
- tool
- args
- read_only
- risk_level
#### `tool_use_approved`
- turn index
- provider call id
- tool
- approval_scope = `once | session`
- source = `user | driving_mode | yolo_policy`
#### `tool_use_denied`
- turn index
- provider call id
- tool
- mode = `permission | driving`
- reason = `user_denied | policy_denied | missing_yolo`
### Session summary compatibility
`session_summary` should remain the final roll-up event.
Add fields rather than replace fields.
Suggested additions:
- `model_steps`
- `tool_requests_emitted`
- `tool_calls_executed`
- `tool_calls_denied`
- `tool_calls_failed`
- `approval_mode`
- `driving_mode`
- `interrupted`
- `loop_limit_reason`
### Resume compatibility
Current resume logic uses session files and decision log replay (`chemsmart/agent/core.py:191-204`, `206-233`, `1061-1095`).
That is an asset.
For tool-loop mode, resume must also persist:
- current provider turn history,
- unresolved tool requests,
- current approval queue,
- current handle store metadata.
### Section 7 verdict
Preserve `AgentSession.run()` shape in wave 1 by **adding** loop fields and keeping synthetic `plan` compatibility.
Extend `DecisionLog`; do not replace it.
## 8. Tool Catalog Hygiene — schema size, description quality, omitting irrelevant tools
### Hard requirement tension
The user requirement says the full JSON-schema tool catalog must be sent each turn.
That is the rule this report follows.
Section 8 therefore focuses on hygiene, not heuristic hiding.
### Current catalog size
Local measurement on 2026-05-10:
- 10 tools,
- 7,155 JSON characters,
- about 1,789 approximate tokens.
That is acceptable for today’s catalog.
It is not free.
At 6 tool rounds, the fixed catalog replay cost alone is around 10k+ prompt tokens.
### Current description quality
Tool descriptions come from docstrings via `inspect.getdoc(self.func)` (`chemsmart/agent/registry.py:47-53`).
Many current docstrings are short one-liners.
Examples:
- `build_molecule`: “Load one molecule from a structure file using chemsmart parsing.” (`chemsmart/agent/tools.py:160-166`)
- `dry_run_input`: “Render a job input file and return its absolute path and contents.” (`chemsmart/agent/tools.py:447-468`)
- `submit_hpc`: “Generate and optionally submit an HPC script for a prepared job.” (`chemsmart/agent/tools.py:627-633`)
Anthropic’s tool docs explicitly recommend detailed descriptions and explain that better descriptions materially improve tool selection quality ([Anthropic define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)).
### What should move out of prompts and into tool descriptions
Today the planner prompt likely carries a lot of tool-specific operational guidance.
In a true tool loop, more of that guidance should live in the tool catalog itself.
Examples:
- when to use `gaussian.opt` vs `gaussian.ts` vs `gaussian.sp`,
- that `run_local` is expensive and should follow validation,
- that `submit_hpc` is remote and queue-affecting,
- that `extract_optimized_geometry` requires a completed optimization output,
- that `build_orca_settings` should receive `ab_initio` or DFT choices carefully.
### Internal-only parameters should leave the model-facing catalog
Current examples of poor catalog hygiene:
- `submit_hpc.transport`
- `submit_hpc.execute`
- `build_job.jobrunner`
These are harness/runtime controls, not user-intent parameters.
Because `ToolSpec.openai_tool_def()` is schema-derived, they leak into the catalog automatically.
Recommendation:
- introduce `model_visible=False` metadata per parameter, or
- define provider-facing wrapper tools with clean signatures.
### Opaque object parameters should become handle parameters
Current bad schema shapes stem from `Any` fallback for complex annotations (`chemsmart/agent/registry.py:216-232`).
Recommendation:
- replace `job: Job` with `job_handle: str`,
- replace `molecule: Molecule` with `molecule_handle: str`,
- replace raw settings objects with settings handles.
This is both schema hygiene and architecture correctness.
### Strict full-catalog interpretation
Because the user explicitly asked for the full catalog each turn, I do **not** recommend silently omitting tools based on model heuristics in the initial design.
Instead:
- send the full current eligible catalog every turn,
- keep risky tools in the catalog even when policy will deny them,
- let the model discover denials through tool outcomes.
Why keep denied tools visible:
- it preserves truthful capability boundaries,
- it lets the model explain “I could do this if you enable `--yolo`,”
- it avoids hidden-mode behavior differences.
### Narrow exception: policy-ineligible tools
There is one acceptable exception.
If the runtime mode genuinely makes a tool unavailable, chemsmart may either:
1. still expose it and return deterministic denial results, or
2. expose it with an availability note in the description.
I prefer option 1 in wave 1.
It is clearer and better for debugging.
### Schema evolution recommendation
Add a registry layer that can emit provider-facing specs with:
- concise but richer descriptions,
- explicit handle parameter names,
- hidden internal params removed,
- mode/risk metadata stored out of band for the harness.
### Suggested metadata not sent to providers
Maintain a sidecar registry table with:
- `risk_level`
- `mutates_filesystem`
- `mutates_remote_state`
- `parallel_safe`
- `returns_handle_kind`
- `accepts_handle_kind[]`
- `display_name`
- `approval_copy`
This lets the harness make good decisions without bloating provider schemas.
### Section 8 verdict
Keep the full catalog each turn for now, but make it **cleaner, handle-based, more descriptive, and stripped of harness-only parameters**.
That is how chemsmart inherits provider-native tool use without inheriting schema sloppiness.
## 9. Failure Modes — loops, malformed tool_use, oversized results, partial JSON
### Design goal
Failures should degrade into visible, recoverable loop state whenever possible.
Crashing the whole session should be the fallback, not the default.
### Failure mode 1 — repeated loops with no progress
Symptoms:
- same tool call repeated,
- same denial repeated,
- same schema error repeated,
- same missing-handle error repeated.
Mitigation:
- same-signature retry cap,
- no-progress detector,
- final assistant summarization step,
- explicit `loop_limit_exceeded` log event.
### Failure mode 2 — assistant emits malformed tool call
Examples:
- unknown tool name,
- missing call id,
- non-JSON arguments,
- wrong arg types,
- provider response shape drift.
Mitigation:
- provider adapter validates raw provider tool objects,
- create a synthetic `ToolOutcome(status="error")`,
- feed that error back to the model as tool result,
- log `tool_use_parse_error` or `provider_turn_raw` for debugging.
### Failure mode 3 — tool_use without tool_result
This is a must-handle edge case explicitly called out in the task.
Invariant:
- every emitted tool request must end in one of: approved result, denied result, error result, interrupted result.
Mitigation:
- approval denial synthesizes a tool result,
- execution exception synthesizes a tool result,
- interrupt synthesizes a tool result when possible,
- only after outcome synthesis does the loop proceed.
For Anthropic this is especially important because the API contract expects the next user message to contain matching `tool_result` blocks ([Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)).
### Failure mode 4 — partial JSON during streaming
Anthropic fine-grained tool streaming explicitly warns that streamed argument chunks may not be valid JSON until completion ([Anthropic fine-grained tool streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming)).
Mitigation:
- buffer streamed arguments by call id,
- parse only at content-block completion,
- if final parse fails, create a tool error result for the model,
- never execute on partially parsed arguments.
### Failure mode 5 — oversized results
Examples:
- huge ORCA/Gaussian input previews,
- large runtime diagnostics,
- verbose logs accidentally returned by tools.
Mitigation:
- artifact persistence on disk,
- model-facing truncation budget,
- include artifact path and summary,
- store raw payload only in files and raw-event logs.
### Failure mode 6 — schema drift
This is already visible in today’s architecture because prompt instructions and actual tool signatures can drift independently.
Root cause today:
- the planner prompt carries schema-like instructions,
- the registry separately generates tool definitions,
- the planner call still works through prompt JSON, not provider-enforced tool semantics.
Mitigation in the new design:
- the model uses the registry-derived tool catalog directly,
- prompt guidance becomes high-level and tool-agnostic,
- tool behavior truth lives in the registry and tool descriptions.
### Failure mode 7 — tool error causes session abort too early
Current behavior:
- `registry.call()` returns structured error dicts (`chemsmart/agent/registry.py:108-143`),
- `_execute_step()` converts those into exceptions and aborts the run (`chemsmart/agent/core.py:728-745`).
Mitigation:
- do not raise on normal tool validation/runtime errors inside the loop,
- instead convert them into tool outcomes and let the model decide whether to retry or reroute,
- reserve hard exceptions for harness invariants or corrupted state.
### Failure mode 8 — provider drift
Examples:
- Anthropic changes block shapes,
- OpenAI changes reasoning item naming,
- usage fields move,
- chat-completions and Responses diverge.
Mitigation:
- isolate all provider parsing to adapter modules,
- persist raw provider payloads,
- test adapters with recorded fixtures,
- do not spread provider-specific conditionals across `AgentSession`.
### Failure mode 9 — resumed session has unresolved handles
A tool loop with handle-based objects introduces new resume risks.
Examples:
- handle exists in log but artifact file missing,
- in-memory object not reconstructible,
- paused approval queue references unknown handle.
Mitigation:
- persist enough materialized state to rebuild handles,
- make handles point at artifact files plus schema tags,
- on resume, validate the handle store before continuing,
- if reconstruction fails, return an advisory assistant message instead of silent corruption.
### Failure mode 10 — parallel tool calls race on the filesystem
Examples:
- two `dry_run_input` calls writing into same job folder,
- two job builders resolving same label unexpectedly,
- output parser reading a file while another tool rewrites it.
Mitigation:
- conservative parallel classification,
- job-folder uniqueness guarantees,
- optional per-handle lock or per-path lock.
### Failure mode 11 — denial loops in Driving Mode
Example:
- model keeps requesting `submit_hpc` without `--yolo`,
- harness keeps denying,
- loop never reaches a final answer.
Mitigation:
- after the second identical denial, inject a stronger denial message,
- after the third, force a final assistant response request.
### Failure mode 12 — tool result too semantically weak
If tool-result summaries are overly truncated, the model may lose the evidence it needs to recover.
Mitigation:
- keep structured summaries, not only plain text,
- preserve key fields like `ok`, `returncode`, `inputfile`, `local_issues`, `remote_unknown`, `job_id`, `duplicate_check`,
- truncate long text payloads, not core fields.
### Section 9 verdict
The failure strategy should be:
- **turn tool and permission failures into model-visible outcomes**,
- **crash only on harness corruption or impossible state**,
- **log raw payloads for replay**,
- **bound loops aggressively**.
## 10. Reference Designs — ≥3 cited (Claude Code, Codex CLI, Aider, Goose, Continue, smolagents) with URLs
### Reference 1 — Claude Code / Claude Agent SDK
URLs:
- https://code.claude.com/docs/en/agent-sdk/agent-loop
- https://code.claude.com/docs/en/agent-sdk/permissions
- https://code.claude.com/docs/en/agent-sdk/hooks
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming
What it contributes:
- the clearest permission-aware tool loop design,
- explicit allow/deny rules and runtime hooks,
- correct parallel-tool semantics,
- correct streaming caution around partial tool JSON.
What chemsmart should inherit:
- tool request → permission → tool result → next assistant loop,
- provider-aware formatting invariants,
- read-only parallelism only,
- denied tool returns to model.
What chemsmart should invent instead:
- chemistry-specific reviewer placement,
- handle-based object passing for molecules/jobs.
### Reference 2 — OpenAI Responses / Codex
URLs:
- https://developers.openai.com/api/docs/guides/function-calling
- https://openai.com/index/equip-responses-api-computer-environment/
- https://openai.com/index/unrolling-the-codex-agent-loop/
- https://developers.openai.com/codex/cli
What it contributes:
- modern OpenAI tool-loop pattern,
- `function_call_output` continuation semantics,
- reasoning-item preservation,
- client-orchestrated loop architecture,
- approval and sandbox concepts in a CLI agent.
What chemsmart should inherit:
- provider adapter for iterative tool continuation,
- bounded tool outputs with artifacts persisted outside the model context,
- approval mode as a first-class runtime concern.
What chemsmart should invent instead:
- chemistry-domain policies for when execution is too dangerous to auto-run,
- stronger typed handles rather than file-only reasoning.
### Reference 3 — Continue Agent Mode
URL:
- https://docs.continue.dev/ide-extensions/agent/how-it-works
What it contributes:
- a simple, legible tool-permission handshake,
- an explicit “available tools are sent with user requests” model,
- permission before execution, then tool result back into the model.
What chemsmart should inherit:
- visible handshake simplicity,
- keeping human approval understandable.
What chemsmart should not over-copy:
- overly IDE-specific mental models.
### Reference 4 — Goose
URL:
- https://block.github.io/goose/docs/getting-started/using-extensions/
- https://block.github.io/goose/docs/guides/running-commands/
- https://block.github.io/goose/docs/guides/working-with-files/
- https://block.github.io/goose/docs/experimental/smart-approvals/
What it contributes:
- explicit command/file tool surfaces,
- smart-approval concepts,
- a spectrum from manual approvals to more autonomous behavior.
What chemsmart should inherit:
- mode as policy, not as prompt text,
- clear user expectation that autonomy level affects approval burden.
### Reference 5 — Aider
URL:
- https://aider.chat/docs/usage/modes.html
- https://aider.chat/docs/usage/architect.html
What it contributes:
- a sharp distinction between “plan/advice” and “edit/act” modes,
- a useful contrast case showing when a separated planner is still helpful.
Why it matters here:
Aider is evidence that a two-role design can work, but only when the roles are explicit product modes.
chemsmart’s current planner/critic split is not that.
It is an internal orchestration trick.
### Reference 6 — smolagents
URL:
- https://huggingface.co/docs/smolagents/reference/agents
What it contributes:
- a useful contrast between `CodeAgent` and `ToolCallingAgent`.
Interpretation for chemsmart:
- `CodeAgent` is powerful when the agent should synthesize little programs and use Python as the latent action language.
- `ToolCallingAgent` is cleaner when the product requires strict approval hooks, explicit schemas, and provider-native tool auditing.
Recommendation from this contrast:
chemsmart should align with **ToolCallingAgent**, not CodeAgent.
The chemistry tools are already explicit, and the main problem is safe orchestration, not giving the model a general Python REPL.
### Cross-reference conclusion
Across these systems, three patterns repeat.
1. Tool loops outperform static planner JSON when the environment is interactive.
2. Permissions belong in runtime policy, not only in prompt wording.
3. Tool results should return to the model, even when they represent denials or errors.
chemsmart should follow those patterns.
## 11. Migration Plan — Wave 1/2/3 with PR boundaries
### Migration philosophy
Do not attempt a single PR that replaces the entire planner/critic/executor path.
The right migration is staged.
### Wave 1 — tool-loop foundation, no UX heroics
#### Goal
Replace static planner primacy with a provider-neutral tool loop core while preserving existing session/TUI contracts as much as possible.
#### Scope
- add provider adapters for normalized tool-call extraction,
- add handle store and handle-based tool wrappers,
- keep full tool catalog passed every model step,
- implement loop budgets and no-progress guards,
- keep synthetic `plan` compatibility,
- keep current approval UI shape for risky tools only as a temporary compatibility layer,
- keep critic but invoke it after evidence-producing tool results.
#### Explicit non-goals
- no batch approval UI,
- no full per-tool permission mode yet,
- no cooperative ESC interrupt yet,
- no OpenAI Responses API migration if chat-completions can be bridged first.
#### PR boundary
One PR that touches:
- `core.py`
- `registry.py`
- provider adapters
- maybe tool wrapper surface
- tests for loop orchestration and resume
Deliverable:
- real tool loop works in headless/CLI form,
- current TUI still functions via compatibility projection.
### Wave 2 — permission mode and driving mode UX
#### Goal
Make the product actually feel like a Claude/Codex-style agent.
#### Scope
- generic per-tool approval queue,
- session-scoped allow rules,
- new approval events in `DecisionLog`,
- driving mode policy engine,
- `--yolo` gate for `run_local` and `submit_hpc`,
- new slash commands and mode toggles,
- transcript cards for tool requests and denials.
#### Explicit non-goals
- no advanced smart approval classifier,
- no tool-side cancellation of long subprocesses yet.
#### PR boundary
One PR focused on:
- `tui/screens/chat.py`
- approval overlay/widgets
- session runner services
- decision-event parsing
- mode-specific CLI flags
Deliverable:
- user can choose Permission Mode or Driving Mode,
- every tool call is surfaced in Permission Mode,
- risky tools are policy-gated in Driving Mode.
### Wave 3 — critic refinement, interruptibility, provider polish
#### Goal
Finish the architecture and remove transitional compromises.
#### Scope
- move OpenAI path to Responses API if not already done,
- add streaming-aware tool parsing,
- add cooperative ESC interrupt support,
- optionally add tool-specific cancellation hooks,
- slim the synthetic `plan` compatibility layer,
- convert critic into post-tool-result reviewer or optional internal tool,
- improve catalog descriptions and schema wrappers.
#### PR boundary
One PR focused on:
- provider polish,
- interrupt behavior,
- critic redesign,
- performance and observability.
Deliverable:
- final production-quality loop behavior,
- less reliance on planner-era abstractions.
### What not to do in any wave
Do not:
- expose raw Python object parameters directly to provider-native tools,
- make `submit_hpc.execute` model-controlled in the public schema,
- parallelize all tools at once,
- hide denied tools silently from the catalog in wave 1,
- remove `DecisionLog` compatibility before the TUI catches up.
### Section 11 verdict
Three waves are enough.
Wave 1 = loop foundation.
Wave 2 = user-facing modes.
Wave 3 = polish and critic/interrupt maturity.
## 12. Open Questions for the User
1. Do you want the model to see risky tools in Driving Mode even when `--yolo` is off, with deterministic denial results, or do you want those tools hidden entirely in that mode?
2. Do you want the current “revise” path to remain as a visible approval action, or should it become a separate normal follow-up message flow outside the three primary actions?
3. Should `dry_run_input` count as “safe enough to auto-run” in Driving Mode, even though it writes input files, or do you want a stricter read-only-only autonomous subset?
4. For OpenAI parity, do you want wave 1 to bridge from current `chat.completions` tool calls first, or do you want an immediate move to the Responses API despite the larger provider change?
5. Should the critic remain enabled by default in Permission Mode and Driving Mode, or only before `run_local` / `submit_hpc`?
6. Do you want handle IDs to be user-visible in transcript/UI cards, or should they remain mostly internal with human-readable summaries shown instead?
7. Should approval rules be keyed only by tool name, or by tool name plus a coarse risk class or argument pattern?
8. Is “full JSON-schema catalog each turn” intended to mean literally every registered tool regardless of mode, or every tool that is genuinely available in the current runtime mode?
9. Do you want denied tool calls to count against the per-turn loop budget the same way executed tool calls do?
10. Should the final product preserve a visible “plan” panel for user comprehension, even if the underlying architecture no longer depends on a static upfront plan?
## 13. Recommendation — verdict + one paragraph
My recommendation is to replace the current planner-first pipeline with a provider-native, handle-based tool loop, keep the full tool catalog on every model step, add a generic permission engine with explicit Permission Mode and policy-bounded Driving Mode, and demote the critic from a pre-plan judge to a post-tool-result reviewer before expensive or irreversible actions. In practice, chemsmart should inherit Claude/Codex-style orchestration, denial-as-tool-result behavior, and provider adapters, while inventing one domain-specific mechanism those systems do not need: explicit artifact handles for molecules, settings, and jobs. That single design choice resolves the current hidden `$stepN` dependency, unlocks proper JSON-schema tool calling, and gives you a clean foundation for approvals, resumability, and future chemistry-safe autonomy.
