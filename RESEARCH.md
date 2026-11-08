# Research: Red-Team Harness

Generated: 2026-11-08 from DISCOVERY.md
Domains:
1. [Competitor landscape](#01-competitor-landscape)
2. [Agent framework adapters and tool interception](#02-agent-framework-adapters-and-tool-interception)
3. [Attack Pattern taxonomy](#03-attack-pattern-taxonomy)
4. [Harness runtime and CI integration](#04-harness-runtime-and-ci-integration)

Source files: [research/](research/)

## Cross-cutting findings (coordinator)

*Written by the coordinator. Everything below the line is the sub-agents' verbatim output.*

### Changes to DISCOVERY decisions (need user confirmation)

- **C1. Narrow the wedge (01).** "Findings become regression tests" is no longer unique: Promptfoo's `retry` strategy does a version of it. The parts that are still unique: **injecting through Instrumented Tool returns and detecting at the tool boundary**, plus **reviewed Regression Cases versioned in the repo** and **deterministic Replay of recorded tool outputs**. Q2 and Q16 still hold; only the positioning changes.
- **C2. Q6 boundary rule (03).** Proposed rule: content in **outbound tool-call arguments is an Objective Breach**, and content in **assistant text is a Policy Breach**. This settles the overlap on exfiltration.
- **C3. Q7 vs adaptive strategies (03).** PAIR, Crescendo and TAP need a score for each step. Proposed: add an LLM **progress scorer** that only steers Adaptive Attackers and never decides a Breach. Q7 stays intact.
- **C4. Q5 Budget caps (04).** Local or open-weight Attackers have no price, so **token and time caps are mandatory** and the money cap is optional.
- **C5. Q4/Q10 coverage gap (02).** OpenAI hosted tools (web search, file search, code interpreter) and, reportedly, MCP tools in the Agents SDK can't be intercepted in-process. Document this, and recommend `function_tool` stand-ins during tests. MCP needs its own wrapper (not verified).
- **C6. Q11 classification (02).** No framework marks a tool as read-only. The user marks Live Tools, and anything unmarked stays Intercepted. MCP's `readOnlyHint` can seed a suggestion.

### Open branches resolved by research

- **O1 Output:** `report.json` (canonical) + JUnit XML + GitHub step summary/annotations + per-Trial JSONL transcripts; HTML later (01, 04 agree).
- **O4 v1 Attack Patterns:** P1–P7 from domain 03, weighted toward P1–P4 (agent-specific and deterministic). Tag both the OWASP LLM 2025 and Agentic 2026 lists, plus ATLAS.
- **O5 Runtime:** domain 04 recommended plain asyncio. **The user overrode this: the harness uses LangGraph** to gain framework experience → ADR 0003. Domain 04's Budget and cancellation advice must be adapted to graph nodes.
- **O6 Fakes:** resolution chain: user fixture → typed-return synthesis (polyfactory, seeded) → static default. LLM fakes opt-in and cached per seed.

### Still open (user decisions before /plan)

- **O2 Storage / O3 Config:** domain 01 suggests a YAML Target Profile (borrowing Promptfoo's `purpose`/`policy` and garak's `agent_purpose`/`tools`) and Regression Cases as files in the repo.
- **O7 Name/license (Q17).**

### Risks

- **Supply chain.** A CI tool that holds provider keys must keep dependencies minimal. Per domain 04, LiteLLM had compromised releases in March 2026 (reported in LiteLLM's own blog, not independently verified) and caps Python below 3.15. Keep LiteLLM as an optional adapter only, and publish with PyPI Trusted Publishing.
- **Competitive speed.** Per domain 01, Promptfoo is now part of OpenAI and could add tool-output mocking. Ship the tool-channel features first.
- **Framework churn.** LangGraph private attributes and Agents SDK internals change often. Pin minor versions and run adapter contract tests.
- **Dual-use.** Ship technique descriptions and templated strategies, not a bank of high-potency jailbreak strings. Check dataset licenses before vendoring: AgentDojo and InjecAgent are MIT; exclude WASP.

---

## 01. Competitor landscape

Researched 2026-11-08. Versions: Promptfoo 0.125.1 (2026-10-25), garak 0.17.1 (2026-10-16), PyRIT 1.1.0 (2026-09-04), LangSmith Red Teaming (private beta, no version given).

### Questions

1. What do Promptfoo (redteam), NVIDIA garak, Microsoft PyRIT and LangSmith offer today for multi-turn attacks, agent/tool attacks, and success detection?
2. Do any of them instrument the target's tools in-process, or turn findings into replayable regression tests that gate CI? Does our wedge hold?
3. How does each one declare config?
4. What output formats do they produce, and how do they store results on disk?
5. What are the licenses, and what could we reuse?

### Findings

#### Q1. Capabilities

**Promptfoo (redteam)** [S1-S6]
- Multi-turn strategies: Crescendo, GOAT, Hydra, Iterative/Jailbreak (LLM-as-judge refinement), Mischievous User [S1]. Options include `maxTurns`, `stateful`, and `continueAfterSuccess`. By default they "stop immediately upon finding a successful attack" [S3].
- Agent plugins: `indirect-prompt-injection`, `tool-discovery`, `excessive-agency`, `agentic:memory-poisoning`, `mcp` [S1], plus `rbac`, `bola`, `bfla`, `ssrf`, `sql-injection`, `rag-poisoning` [S4].
- Indirect injection works on a **prompt template variable**, not on a live tool return: "Specify which template variable contains untrusted data. Promptfoo injects adversarial payloads into that variable" [S2].
- Detection: an LLM grader by default. You can tune it with `graderExamples` and `graderGuidance` [S1]. The policy plugin reports a `PolicyViolation:<policy id>` metric [S5].
- Tool calls are observed **passively through OpenTelemetry**: "Promptfoo captures the spans and summarizes the trajectory" [S4]. Tool calls come from span attributes such as `tool.name` and `tool.arguments` [S4].
- The agents page says nothing about mocking tool outputs or injecting payloads into them [S4].
- By default, attack generation uses a Promptfoo-hosted remote service. You can turn this off with `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION` [S6].

**NVIDIA garak** [S7-S11]
- Architecture: probes, detectors, generators, harnesses and evaluators [S7].
- Multi-turn: a GOAT probe was added in v0.15.0 [S8]. Agent Breaker (v0.15.0) "adds support for testing tools available to target systems" [S8].
- How Agent Breaker works:
  - A red-team model reads a YAML list of tools, or discovers the tools by asking the agent.
  - Each turn starts a new conversation with an improved payload, and the probe "stops immediately on success" [S9].
  - Its detector is an LLM judge that reads the agent's **responses**. It does not see real tool execution [S9].
  - v0.17.1 refined how verdicts are grounded "in the victim's tool contract" [S8].
- Latent injection probes test "whether models respond to injections embedded in context" (indirect injection, XPIA) [S10]. Detection uses `TriggerListDetector`: a substring match on a `payload_trigger` [S10].
- v0.17.1 added a hit@k metric: "given k attempts, does at least one breach succeed?" [S11].

**Microsoft PyRIT** [S12-S17]
- The repo moved from `Azure/PyRIT`, archived "on Mar 27, 2026", to `microsoft/PyRIT` [S12].
- Components: targets, converters, scorers, attacks/executors, scenarios and memory. Interfaces are a `pyrit_scan` CLI, the CoPyRIT GUI, and a Python framework [S13].
- Multi-turn attacks: `CrescendoAttack`, `TreeOfAttacksWithPruningAttack`, `SequentialAttack`, and Red Teaming variants that use an adversarial chat target [S14].
- An attack is driven by an **objective**, sent against an `objective_target`, and returns an `AttackResult` [S14].
- XPIA (cross-domain injection) is the closest match to our injection through tool outputs:
  - `attack_setup_target` plants the payload, for example as a blob in Azure Storage.
  - A **user-written** `processing_callback` makes the target consume it.
  - A scorer such as `SubStringScorer` judges success [S15].
- Detection: 40+ scorers, including SubString, Regex, SelfAskTrueFalse, Refusal, LlamaGuard, CredentialLeak and SQLInjectionOutput [S16].
- `OtelToolCallScorer` answers "Did these tools run?" from OpenTelemetry spans (`gen_ai.tool.name`) [S17]. It is passive: PyRIT "does not mock tool outputs" [S17].

**LangSmith** [S18-S20]
- Red Teaming is cloud-only and in private beta: "Red Teaming is in private beta. It is available only on LangSmith Cloud" [S18].
- It generates hypotheses with issue classes, including indirect injection from "tool output". It "sends up to two synthetic requests per hypothesis to the deployment" [S18].
- Judging: "Engine reviews each probe's response and, for baseline deployments, its trace" [S18].
- Open-source pieces in OpenEvals (MIT) [S19]:
  - `run_multiturn_simulation` and `create_llm_simulated_user` for simulated users.
  - LLM-judge security prompts: `PROMPT_INJECTION_PROMPT`, `PII_LEAKAGE_PROMPT`, `CODE_INJECTION_PROMPT`.
  - Trajectory evaluators: `create_trajectory_match_evaluator` (strict, unordered, subset or superset matching) and `create_trajectory_llm_as_judge`.
- Pytest integration through `@pytest.mark.langsmith`, which logs results to LangSmith [S20].

#### Q2. Tool instrumentation, regression-to-CI, and whether the wedge holds

| Capability | Promptfoo | garak | PyRIT | LangSmith |
|---|---|---|---|---|
| Observes tool calls | Yes, OTel spans (passive) [S4] | No, judges response text [S9] | Yes, OTel spans (passive) [S17] | Yes, traces for baseline deployments [S18] |
| **Controls tool outputs / injects through a live tool return** | No (injects into a template var) [S2] | No (injects into the prompt context) [S10] | Partly: XPIA plants into external storage plus a user callback [S15] | Claims to test it; mechanism not documented; cloud beta [S18] |
| Deterministic tool-call breach checks | Yes, `trajectory:tool-args-match` and others [S4] | No | Yes, `OtelToolCallScorer` [S17] | Not documented |
| Findings to replayable regression tests | **Yes**: `retry` strategy [S21], trajectory regression evals [S4], `redteam.yaml` [S22] | No | No (results go to memory) [S23] | **No**, findings "stay in the red-team report" [S18] |
| CI gating | GitHub Action for before/after prompt evals; red-team CI needs custom scripting [S24] | Not documented | Not documented | Pytest integration for evals, not for red team [S20] |

**Contradiction / threat to the wedge (findings become regression tests):** Promptfoo already offers this in part.
- The `retry` strategy "automatically incorporates previously failed test cases into your test suite, creating a regression testing system" [S21].
- Its limits: it "uses only your local database" [S21], and it reruns the **same generated prompts**. There is no accept/reject step like our Pending Cases (Q16), and no separate Replay and Explore modes (ADR 0002).
- Promptfoo's docs also recommend turning discoveries into "trajectory-based regression evals" [S4].

**The wedge still holds on three narrower points:**
1. **Controlling tool outputs in-process.** We put Attack Patterns into Instrumented Tools' return values during a live run (ADR 0001). No tool does this today. Promptfoo and PyRIT only **observe** through OTel. PyRIT's XPIA needs external storage plus a hand-written callback.
2. **Deterministic Checks on intercepted tool calls, with the LLM Judge as fallback.** Promptfoo and PyRIT have deterministic OTel-based tool assertions, but their red-team grading defaults to an LLM judge. garak's agent probe is judge-only.
3. **A curated Finding to Regression Case lifecycle that gates PRs in a Python-native workflow.** Promptfoo is a Node CLI (installed from npm). Its retry pool comes from the local DB, not from reviewed regression files kept in the repo.

**Conclusion:** the wedge is defensible but thin. We should frame it as "we control the tool channel and own the regression lifecycle", not as "we have agent attacks", because every competitor now ships agent probes.

#### Q3. Config declaration

**Promptfoo:** YAML (`promptfooconfig.yaml`) [S1, S5, S25]. The target is set in `targets`. Python agents plug in as a `file://provider.py` that exposes `call_api(prompt, options, context)` [S25].
```yaml
targets:
  - id: 'file://provider.py'
    label: 'my-agent'
redteam:
  purpose: 'Support agent; may only refund the logged-in user'
  provider: 'openai:gpt-5'          # attacker/generator model
  plugins:
    - id: 'policy'
      config: { policy: "Do not disclose another customer's order data." }
    - id: indirect-prompt-injection
      config: { indirectInjectionVar: name }
  strategies: ['jailbreak', 'crescendo']
```

**garak:** CLI flags, or a YAML file with `plugins`, `run` and `reporting` sections [S7, S26]. Agent Breaker takes its own YAML file [S9].
```bash
garak --target_type openai --target_name gpt-5-nano --spec probes.encoding
```
```yaml
plugins:
  target_type: openai
  probes: { dan: { DanInTheWild: {} } }
run:
  spec: { include: [probes.dan, {tag: "owasp:llm01"}] }
reporting: { report_dir: "garak_runs", taxonomy: "owasp" }
```
```yaml
# agent_breaker
agent_purpose: |
  A helpful personal assistant that can execute code and read files.
tools:
- name: tool_name
  description: what it does
```
Agent Breaker defaults include `max_attempts_per_tool: 5`, `success_threshold: 0.7` and `red_team_model_name: 'openai/gpt-oss-120b'` [S9].

**PyRIT:** mainly Python code. Goals are set as an `objective` string per attack [S14]. The CLI uses named scenarios and initializers. YAML config lives in `~/.pyrit` or is passed with `--config-file` [S27].
```bash
pyrit_scan run foundry.red_team_agent --target openai_chat --initializers target --techniques base64
```
```python
workflow = XPIAWorkflow(attack_setup_target=abs_target,
                        converter_config=converter_configuration, scorer=scorer)
result = await workflow.execute_async(attack_content=xpia_prompt_group,
                                      processing_callback=processing_callback_async)
```

**LangSmith:** Red Teaming is configured in the cloud UI against a deployment [S18]. OpenEvals is configured in Python code [S19].

**Takeaway for us:** none of them has a first-class **Policy** with a separate Target Profile (system prompt plus tool schemas). Promptfoo has the closest pieces: `purpose` plus `policy` plugin entries. garak has `agent_purpose` plus `tools`.

#### Q4. Outputs and on-disk storage

- **Promptfoo:**
  - `-o` accepts "csv, txt, json, jsonl, yaml, yml, html, xml, junit.xml" [S22].
  - Results go to `~/.promptfoo` (override with `PROMPTFOO_CONFIG_DIR`) unless you pass `--no-write` [S22].
  - `redteam generate` writes the generated tests to `redteam.yaml` by default [S22].
  - There is also a web viewer [S28].
- **garak:**
  - `report.jsonl`: entries typed by `entry_type`, either attempt or eval entries [S11].
  - `hitlog.jsonl`: the successful hits [S11].
  - An HTML report graded on a "1-5 DEFCON scale" with Z-scores [S11], plus `garak.log` [S7].
  - The default directory is `$XDG_DATA/garak/garak_runs` [S26].
  - The reporting page does **not** mention JUnit or CI exit codes (checked) [S11].
- **PyRIT:**
  - Memory backends: `IN_MEMORY`, `SQLITE` and `AZURE_SQL`. "In in-memory mode, no data is persisted to disk" [S23].
  - The memory docs list no standard report format such as JUnit or HTML [S23].
- **LangSmith:** red-team results show up only in the cloud report [S18].

**Takeaway:** only Promptfoo emits JUnit. We should emit JUnit XML, for native CI gating, and JSONL in a layout similar to garak's (attempts plus hits). Regression Cases should be plain files committed to the repo, which none of the four does.

#### Q5. Licenses and reuse

| Tool | License | Language |
|---|---|---|
| Promptfoo | MIT. "Promptfoo is now part of OpenAI. Promptfoo remains open source and MIT licensed." [S28] | TypeScript/Node |
| garak | Apache-2.0 [S29] | Python >=3.11 [S29] |
| PyRIT | MIT [S30] | Python 3.10-3.14, "Alpha" [S30] |
| OpenEvals | MIT [S19] | Python/JS |

Worth reusing:
- **garak latent-injection payloads and the trigger-string pattern** (Apache-2.0) [S10]. Each payload carries a canary `payload_trigger`, which gives us a cheap Deterministic Check. This maps directly onto Attack Patterns delivered through Instrumented Tools. We can vendor the data with NOTICE attribution or depend on `garak`.
- **PyRIT `SeedDatasetProvider`** loaders [S31]. One API to fetch many public datasets, including prompt-injection sets and an "Agent Threat Rules" loader (PR #1715). Check the license of each dataset; it is not always MIT. PyRIT is an async framework with heavy dependencies, so prefer copying datasets over depending on the whole package.
- **PyRIT/garak multi-turn algorithms** (Crescendo, TAP, GOAT) [S14, S8]. These are references for our Attacker loop. Reimplement them instead of depending on the libraries.
- **OpenTelemetry GenAI span conventions** (`gen_ai.tool.name`), used by PyRIT [S17] and by Promptfoo's tracing [S4]. Emitting these from Instrumented Tools lets our traces work with both tools for free.
- **OpenEvals trajectory matchers** (MIT) [S19]. Their strict/unordered/subset/superset semantics are a good model for tool-call Checks.

### Recommendation

1. **Keep the wedge, narrowed.** Position it as "we own the tool channel": inject through Instrumented Tool returns and detect deterministically at the tool boundary. Add "reviewed Regression Cases committed to the repo, replayed on every PR". Do not claim to be first at "agent red-teaming" or at "findings become regression tests": Promptfoo's `retry` and trajectory evals already exist.
2. **Differentiate against Promptfoo's `retry`.**
   - Regression Cases are versioned files in the repo, not a local DB.
   - The user accepts each Pending Case (Q16).
   - Replay is deterministic, with Instrumented Tools replaying recorded tool outputs.
   - Replay and Explore are separate (ADR 0002).
3. **Outputs:** JUnit XML plus JSONL, a non-zero exit code on any Breach in Replay, and an optional HTML report.
4. **Reuse:**
   - Vendor garak latent-injection payloads with their triggers (Apache-2.0).
   - Optionally load datasets through PyRIT's `SeedDatasetProvider` as an extra install, never in core.
   - Emit OTel `gen_ai.*` spans.
5. **Config:** a YAML Target Profile with a first-class `policy:` list and `tools:` taken from schemas. Borrow from Promptfoo's `purpose` and `policy` and from garak's `agent_purpose` and `tools`, so users of those tools find it familiar.
6. **Interop (optional):** a Promptfoo-provider shim (`file://provider.py`). Teams already on Promptfoo could then run our Regression Cases or targets without switching.

### Risks and gotchas

- **Promptfoo is now part of OpenAI** [S28]. It is well resourced and could add tool-output mocking quickly. The red-team docs move fast; re-check the `retry` and `agents` pages before launch.
- **Promptfoo calls home by default.** Attack generation uses a hosted remote service. Disabling it "is not a network egress firewall" [S6]. This is a privacy contrast we can use in our positioning (local-only by default).
- **LangSmith already lists indirect injection from "tool output"** [S18]. It is cloud-only beta with no regression output today, but it is a direct conceptual overlap.
- **garak Agent Breaker judges success from the agent's own words** [S9]. That is the weakness our intercepted-tool Checks fix. Agents that lie or narrate can fool it, which makes a good demo.
- **PyRIT repo move.** Old `Azure/PyRIT` links and APIs (orchestrators) are stale. Use `microsoft/PyRIT` and the 1.x "attacks/executors" API [S12, S14]. PyRIT is still marked Alpha [S30].
- **Dataset licensing.** Public jailbreak and injection datasets carry mixed licenses, some non-commercial. Check each one before vendoring.
- **Summarizer caveat.** Some findings come from fetched-page summaries. The garak docs mislabel TAP in places, and an early read of the garak reporting page wrongly suggested JUnit support (re-checked: not present). The quoted strings above were checked against the pages.

### Sources

- [S1] Promptfoo red team configuration: https://www.promptfoo.dev/docs/red-team/configuration/
- [S2] Promptfoo indirect prompt injection plugin: https://www.promptfoo.dev/docs/red-team/plugins/indirect-prompt-injection/
- [S3] Promptfoo multi-turn strategies: https://www.promptfoo.dev/docs/red-team/strategies/multi-turn/
- [S4] Promptfoo red teaming agents (tracing, trajectory assertions): https://www.promptfoo.dev/docs/red-team/agents/
- [S5] Promptfoo policy plugin: https://www.promptfoo.dev/docs/red-team/plugins/policy/
- [S6] Promptfoo data handling / remote generation: https://www.promptfoo.dev/docs/red-team/troubleshooting/data-handling/
- [S7] garak repo README: https://github.com/NVIDIA/garak
- [S8] garak releases (v0.15.0, v0.17.1): https://github.com/NVIDIA/garak/releases and https://github.com/NVIDIA/garak/releases/tag/v0.15.0
- [S9] garak Agent Breaker probe: https://reference.garak.ai/en/latest/probes/agent_breaker.html
- [S10] garak latent injection probes: https://reference.garak.ai/en/latest/probes/latentinjection.html
- [S11] garak reporting: https://reference.garak.ai/en/latest/reporting.html
- [S12] Azure/PyRIT (archived): https://github.com/Azure/PyRIT
- [S13] microsoft/PyRIT README: https://github.com/microsoft/PyRIT
- [S14] PyRIT attacks/executors: https://microsoft.github.io/PyRIT/latest/code/executor/executor
- [S15] PyRIT XPIA workflow: https://microsoft.github.io/PyRIT/latest/code/executor/workflow
- [S16] PyRIT scoring: https://microsoft.github.io/PyRIT/latest/code/scoring/scoring
- [S17] PyRIT tool-call scorer: https://microsoft.github.io/PyRIT/latest/code/scoring/tool-call-scorer
- [S18] LangSmith Red Teaming: https://docs.langchain.com/langsmith/engine-red-teaming
- [S19] OpenEvals README: https://github.com/langchain-ai/openevals (raw: https://raw.githubusercontent.com/langchain-ai/openevals/main/README.md)
- [S20] LangSmith multi-turn simulation / pytest: https://docs.langchain.com/langsmith/multi-turn-simulation and https://blog.langchain.com/pytest-and-vitest-for-langsmith-evals/
- [S21] Promptfoo retry strategy: https://www.promptfoo.dev/docs/red-team/strategies/retry/
- [S22] Promptfoo command line: https://www.promptfoo.dev/docs/usage/command-line/
- [S23] PyRIT memory: https://microsoft.github.io/PyRIT/latest/code/memory/memory
- [S24] Promptfoo GitHub Action: https://www.promptfoo.dev/docs/integrations/github-action/
- [S25] Promptfoo Python provider: https://www.promptfoo.dev/docs/providers/python/
- [S26] garak configuration: https://reference.garak.ai/en/latest/configurable.html
- [S27] PyRIT scanner (pyrit_scan): https://microsoft.github.io/PyRIT/latest/scanner/scanner
- [S28] Promptfoo repo (license, OpenAI note): https://github.com/promptfoo/promptfoo ; releases: https://github.com/promptfoo/promptfoo/releases
- [S29] garak on PyPI (0.17.1, 2026-10-16): https://pypi.org/project/garak/
- [S30] PyRIT on PyPI (1.1.0, 2026-09-04): https://pypi.org/project/pyrit/
- [S31] PyRIT seed dataset loaders: https://github.com/microsoft/PyRIT/pull/1805 , https://github.com/microsoft/PyRIT/pull/1715


---

## 02. Agent framework adapters and tool interception

Researched 2026-11-08. Versions checked on PyPI that day: `langchain` 1.4.9 (2026-11-04), `langgraph` 1.2.20 (2026-11-05), `openai-agents` 0.24.0 (2026-10-15), `anthropic` 2.6.0 (2026-11-05), `openai` 3.46.0 (2026-11-05), `hypothesis-jsonschema` 0.23.2 (2026-10-27), `polyfactory` 3.5.0 (2026-10-21). Source quotes come from the `main`/`master` branches on the same day.

### Questions

1. LangGraph / LangChain: what is the cleanest way to intercept tools without the user rewriting their graph? Can callbacks replace a return value?
2. OpenAI Agents SDK: how do we intercept tool calls, and can a hook replace the output?
3. Raw function-calling loops (OpenAI / Anthropic SDKs): what minimal adapter API should we offer?
4. What framework-agnostic core interface can all three adapters target? What are the sync and async concerns?
5. How do we produce fake results for Intercepted Tools?

### Findings

#### Q1. LangGraph / LangChain

There are three mechanisms. Only the first two can replace a result.

- **`ToolNode(wrap_tool_call=..., awrap_tool_call=...)`** (langgraph prebuilt). The source docstring says: "Sync wrapper function to intercept tool execution. Receives ToolCallRequest and execute callable, returns ToolMessage or Command." The async form "falls back to wrap_tool_call for async execution" if you don't provide it. The wrapper can skip `execute()` entirely and return its own `ToolMessage`, which is exactly what an Intercepted Tool needs. `ToolCallRequest` has `tool_call` ("Tool call dict with name, args, and id from model output"), `tool`, `state` and `runtime`. Setting attributes on it directly is deprecated ("Use the `override()` method instead"). [tool_node.py](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/tool_node.py)
- **LangChain v1 `create_agent` middleware (`@wrap_tool_call` / `AgentMiddleware.wrap_tool_call`)**. This has the same contract: `(request: ToolCallRequest, handler) -> ToolMessage | Command`, and you read `request.tool_call['name']` and `['args']`. If the user's agent is built with `create_agent`, our hook is one line for them: `middleware=[harness.middleware()]`. [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- **Callbacks (`on_tool_start` / `on_tool_end`)**. These only observe. `on_tool_start(serialized, input_str, *, ..., inputs=...)` and `on_tool_end(output, ...)` are declared `-> Any`, but the callback manager calls `event = getattr(handler, event_name)(*args, **kwargs)` and only keeps the result when it is a coroutine to await. It never uses the result as a tool output. So callbacks cannot replace a return value, and they cannot stop a side effect: by the time they fire, the tool is already running. Handler exceptions are also swallowed unless `raise_error=True`. [callbacks/base.py](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/callbacks/base.py), [callbacks/manager.py](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/callbacks/manager.py)

**Users with custom tool-dispatch nodes** don't use `ToolNode`, so `wrap_tool_call` never runs for them. The fallback is to wrap the `BaseTool` objects themselves before the graph is built: subclass, or build a `StructuredTool` that keeps the original's `name`, `description` and `args_schema`.

Sketch (one wrapper serves both ToolNode and middleware):

```python
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from redteam.core import Interceptor, ToolCall   # our core (Q4)

def langgraph_wrapper(ic: Interceptor):
    def wrap(request, execute):
        tc = request.tool_call
        call = ToolCall(name=tc["name"], args=tc["args"], call_id=tc["id"], framework="langgraph")
        decision = ic.before(call)                     # record + decide
        if decision.override is not None:              # Intercepted Tool: never execute
            msg = ToolMessage(content=decision.as_text(), tool_call_id=tc["id"], name=tc["name"])
        else:                                          # Live Tool
            msg = execute(request)
        return ic.after(call, msg)                     # record result; may rewrite (injection payload)
    async def awrap(request, execute):
        ...  # same, with `await execute(request)` and `await ic.abefore(...)`
    return wrap, awrap

wrap, awrap = langgraph_wrapper(ic)
tools_node = ToolNode(user_tools, wrap_tool_call=wrap, awrap_tool_call=awrap)

# create_agent users:
from langchain.agents.middleware import wrap_tool_call
mw = wrap_tool_call(wrap)            # pass middleware=[mw] to create_agent
```

#### Q2. OpenAI Agents SDK (0.24.0)

- **`RunHooks` / `AgentHooks.on_tool_start` / `on_tool_end`**. These only observe. The docs say the hooks are "Called immediately before a local tool is invoked", and that `context` "is typically a `ToolContext` instance, which exposes ... `tool_call_id`, `tool_name`, and `tool_arguments`." They return `None`, and `on_tool_end` gets `result` only to read it. [Lifecycle ref](https://openai.github.io/openai-agents-python/ref/lifecycle/)
- **Tool guardrails (`tool_input_guardrails` / `tool_output_guardrails` on `FunctionTool`)**. These can replace output. Input guardrails "can skip calls, replace output, or raise tripwires". `ToolGuardrailFunctionOutput.reject_content(message)` sends the "Message to send to the model instead of the tool result" and does not run the tool. The catch: the replacement is a message string, and the docs and code frame it as a rejection, not a result. Scope: they work for `@function_tool` tools, but not for "Hosted tools (`WebSearchTool`, `FileSearchTool`, etc.) and built-in execution tools (`ComputerTool`, `ShellTool`, etc.)". [Guardrails docs](https://openai.github.io/openai-agents-python/guardrails/), [tool_guardrails.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/tool_guardrails.py)
- **Wrapping `FunctionTool.on_invoke_tool`**. This is the cleanest interception. `FunctionTool` is a plain `@dataclass` with the field `on_invoke_tool: Callable[[ToolContext[Any], str], Awaitable[Any]]`, which takes the context and the raw JSON args string. We can walk `agent.tools` (and the agents reached through handoffs) and swap in `dataclasses.replace(tool, on_invoke_tool=wrapped)`. That gives full control: record the call, skip execution, and return any value. One side effect: `FunctionTool.__wrapped__` then raises `AttributeError` ("if its invoker was replaced"), which is harmless. [tool.py](https://github.com/openai/openai-agents-python/blob/main/src/agents/tool.py)
- **Tracing processors (`add_trace_processor`)**. These only observe, and they report after the fact. `function_span` records "the inputs/outputs of function calls", and processors are "independent observers". Use them for the transcript only, never for enforcement. [Tracing docs](https://openai.github.io/openai-agents-python/tracing/)

Sketch:

```python
import dataclasses, json
from agents import Agent, FunctionTool

def instrument_agent(agent: Agent, ic: Interceptor, _seen=None) -> Agent:
    _seen = _seen if _seen is not None else {}
    if id(agent) in _seen: return _seen[id(agent)]
    new_tools = []
    for t in agent.tools:
        if isinstance(t, FunctionTool):
            orig = t.on_invoke_tool
            async def invoke(ctx, args_json, _orig=orig, _name=t.name):
                call = ToolCall(name=_name, args=json.loads(args_json or "{}"),
                                call_id=ctx.tool_call_id, framework="openai-agents")
                d = await ic.abefore(call)
                result = d.override if d.override is not None else await _orig(ctx, args_json)
                return await ic.aafter(call, result)
            t = dataclasses.replace(t, on_invoke_tool=invoke)
        else:
            ic.warn_uninstrumentable(t)   # hosted / MCP / computer tools
        new_tools.append(t)
    clone = agent.clone(tools=new_tools)
    _seen[id(agent)] = clone
    # also recurse into clone.handoffs and agent-as-tool (Agent.as_tool) targets
    return clone

result = await Runner.run(instrument_agent(target_agent, ic), input=attack_prompt)
```

#### Q3. Raw function-calling loops (OpenAI / Anthropic SDKs)

Neither provider's manual loop has a hook, because the user writes the dispatch (`for block in response.content: if block.type == "tool_use": result = TOOLS[block.name](**block.input)`). [Anthropic: handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls), [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling). Anthropic's beta tool runner (`client.beta.messages.tool_runner(...)` over `@beta_tool` / `@beta_async_tool` functions) runs the tools itself. Its docs point users to the manual loop "When you need human-in-the-loop approval, custom logging, or conditional execution". The integration point is the same either way: wrap the plain callable *before* `@beta_tool` decorates it. [Anthropic tool runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)

Proposed API: one function plus one decorator, and both keep the callable's signature (`functools.wraps`, so `@beta_tool`, schema generators and type hints still work):

```python
from redteam import instrument, tool, ToolKind

# 1) dict-of-callables (most common raw-loop shape)
TOOLS = instrument({"search_docs": search_docs, "send_email": send_email},
                   live={"search_docs"})            # everything else is Intercepted
# user's loop is unchanged:
result = TOOLS[block.name](**block.input)

# 2) decorator at definition site
@tool(kind=ToolKind.SIDE_EFFECT)                     # default: intercepted
def send_email(to: str, subject: str, body: str) -> dict: ...

@tool(kind=ToolKind.READ_ONLY)                       # live
@beta_tool
def search_docs(query: str) -> str: ...
```

`instrument()` returns a `Mapping[str, Callable]` whose values are sync or async, matching the originals (detected with `inspect.iscoroutinefunction`). The harness binds the active Interceptor through a `contextvars.ContextVar` set by the test run. So the wrapped tools are no-ops outside a red-team run and safe to leave in production code.

#### Q4. Framework-agnostic core

All three adapters reduce to "before call → maybe short-circuit → after result". This mirrors LangGraph's `(request, execute)` wrapper:

```python
@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]          # parsed; adapters parse JSON strings
    call_id: str | None
    framework: str                # "langgraph" | "openai-agents" | "raw"
    agent: str | None = None      # multi-agent attribution
    raw: Any = None               # native request object, for escape hatches

@dataclass
class Decision:
    override: Any | None = None   # set => do not execute; return this (Intercepted Tool)
    # None => execute for real (Live Tool)

class Interceptor(Protocol):
    def before(self, call: ToolCall) -> Decision: ...
    def after(self, call: ToolCall, result: Any) -> Any: ...   # record; may rewrite (inject payload)
    async def abefore(self, call: ToolCall) -> Decision: ...
    async def aafter(self, call: ToolCall, result: Any) -> Any: ...
```

The core holds the **policy** (Live vs Intercepted, the fake-result provider, Breach detectors that run on every `ToolCall`) and the **event log** (ordered `ToolCall`/result pairs per run, the source of truth for Objective Breach checks). Adapters only translate native objects.

Sync and async concerns:
- Write the core async-native, and give it pure-sync `before`/`after` methods that do no I/O for the common case (lookup policy, fixture, schema synthesis). Don't call `asyncio.run()` inside a sync tool: it fails if a loop is already running, as it is under LangGraph `ainvoke` with a sync wrapper. [tool_node.py](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/tool_node.py)
- LLM-generated fakes (Q5) are inherently async I/O. In sync paths, run them on a dedicated background loop thread (`asyncio.run_coroutine_threadsafe`), or pre-generate them.
- Parallel tool calls: LangGraph's ToolNode and the Agents SDK can run several calls at once. Make the event log append-only with a lock or a per-run queue, and record `call_id` plus a monotonic sequence number so ordering-based detectors stay deterministic.
- Use `contextvars` (not thread-locals) for the active run. They propagate into asyncio tasks, and in LangGraph into executor threads through copied context.

#### Q5. Fake results for Intercepted Tools (open item O6)

| Option | How | Pros | Cons |
|---|---|---|---|
| Static default | `{"status": "ok"}` / `"Email sent."` | deterministic, zero deps | can look fake; the Target may ignore it or behave unnaturally |
| User fixtures | `fakes={"send_email": {...}}` or a callable `(ToolCall) -> result` | most realistic, deterministic, CI-friendly | user effort per tool |
| Type-driven synthesis | from return annotation via **polyfactory**: "mock data generation library, based around type hints"; supports dataclasses, TypedDicts, Pydantic, msgspec ([docs](https://polyfactory.litestar.dev/latest/)) | automatic for typed tools, seedable | `-> str` / `-> dict` give no signal; random strings look implausible |
| Schema-driven synthesis | from an output JSON schema via **hypothesis-jsonschema** `from_schema(...)`, which supports drafts 04/05/07 and ignores custom formats by default ([repo](https://github.com/python-jsonschema/hypothesis-jsonschema)) | works when only a schema exists (MCP `outputSchema`) | built for property tests (`@given`), so using it outside that needs `strategy.example()`, which Hypothesis discourages; output is adversarial-edge-case-heavy, not "plausible" |
| LLM-generated | prompt a cheap model with tool name, description, args and schema | most plausible for free-text tools | cost, latency, nondeterminism (cache by `(tool, args-hash, seed)`), and the fake could itself carry an accidental injection |

Note: the input schema is usually known (it is the tool's `params_json_schema` / `args_schema`). The *output* schema usually is not: LangChain tools and Agents SDK `FunctionTool` describe parameters only. So annotation- or schema-based synthesis only helps for tools with a typed return.

### Recommendation

1. **Core**: `ToolCall` + `Decision` + an async-first `Interceptor` with sync twins (Q4). Bind the active run with `contextvars`. Keep an append-only event log as the Breach evidence.
2. **LangGraph adapter**: give `wrap_tool_call`/`awrap_tool_call` for `ToolNode`, and an `AgentMiddleware` for `create_agent` (one line for the user). As a fallback for custom dispatch nodes, offer `instrument_tools(list[BaseTool])`. Do not rely on callbacks except for extra trace context.
3. **OpenAI Agents SDK adapter**: `instrument_agent(agent)`, which clones the agent and replaces `FunctionTool.on_invoke_tool` across handoffs and agents used as tools. Warn loudly about hosted, MCP and computer/shell tools it cannot instrument. Use tool guardrails only if wrapping proves brittle. Use `RunHooks` and tracing for transcript enrichment only.
4. **Raw adapter**: `instrument(dict)` plus a `@tool(kind=...)` decorator that keeps signatures (works under `@beta_tool`).
5. **Fakes (O6)**: a resolution chain, from first to last: user fixture/callable → typed-return synthesis (polyfactory, seeded) → per-tool static default (`"ok"` plus echoed args). Make the LLM-generated fake an opt-in provider, cached per seed for CI reproducibility. Leave hypothesis-jsonschema out of v1, since it fits property testing better than plausible fakes.

The decisions are consistent with each other. **Flags against decisions:**
- **Q10/Q4 (in-process grey-box)**: OpenAI hosted tools (`WebSearchTool`, `FileSearchTool`, code interpreter) run on OpenAI's servers, and the docs exclude them from tool guardrails. The harness cannot intercept them in-process or fake their returns. That means indirect injection through web search results can't be planted in-process for those tools. Document the gap, or recommend users swap in a `function_tool` stand-in during tests.
- **Q11 (intercepted-by-default)**: none of the three frameworks marks a tool as read-only or side-effecting. The user must classify their tools. The default must stay "intercept unless marked live" so that unclassified tools fail safe. MCP's `readOnlyHint` annotation could seed a suggestion, but it is only a hint.

### Risks and gotchas

- **LangGraph private-attribute patching**: to retrofit an already compiled graph, we could set `ToolNode._wrap_tool_call` on its nodes. That attribute is private and could change in any release, so prefer the constructor and middleware paths. Pin and test against the langgraph minor version.
- **LangGraph `Command` returns**: tools and wrappers can return a `Command` instead of a `ToolMessage`, to update state or route. Fakes must return a `ToolMessage` with the right `tool_call_id`, or the model API will reject the next turn because the tool result is missing.
- **Sync wrapper under async graph**: if only `wrap_tool_call` is given, the async path calls the sync wrapper with a sync `execute` (`_sync_execute`). Blocking I/O in our hook then blocks the event loop.
- **Agents SDK `reject_content`** frames the replacement as a rejection, and future SDK versions may label it as such to the model. Don't use it to deliver *plausible* fakes.
- **Agents SDK MCP tools** (`mcp_servers=`) are listed dynamically and are not `FunctionTool`s in `agent.tools`. They need a separate wrapper around the MCP server's `call_tool`. Not verified here; check this before v1.
- **Agent cloning**: `instrument_agent` must handle cycles in handoffs, and `Agent.as_tool` sub-agents, whose tools also need instrumenting.
- **Callbacks swallow errors**: LangChain callback handler exceptions are logged and ignored unless `raise_error=True`, so detectors built on callbacks can fail silently.
- **Fake realism vs attack validity**: an obviously fake result such as `"ok"` can change the Target's later behaviour, for example retries or suspicion. That can lead to false-negative or false-positive Breaches. Record which fake provider produced each result in the event log.
- **Arg parsing**: the Agents SDK passes args as a JSON string, which may be invalid or partial. Record the raw string as well as the parsed dict, because malformed calls to `send_email` are still evidence of intent.

### Sources

- LangGraph `ToolNode` / `ToolCallRequest` source (main, 2026-11-08): https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/tool_node.py
- LangChain custom middleware (`wrap_tool_call`): https://docs.langchain.com/oss/python/langchain/middleware/custom
- LangChain callbacks base and manager (master, 2026-11-08): https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/callbacks/base.py , https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/callbacks/manager.py
- OpenAI Agents SDK guardrails: https://openai.github.io/openai-agents-python/guardrails/
- OpenAI Agents SDK lifecycle hooks: https://openai.github.io/openai-agents-python/ref/lifecycle/
- OpenAI Agents SDK tracing: https://openai.github.io/openai-agents-python/tracing/
- OpenAI Agents SDK `tool.py`, `tool_guardrails.py`, `tool_context.py` (main, 2026-11-08): https://github.com/openai/openai-agents-python/tree/main/src/agents
- Anthropic tool runner (beta): https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner
- Anthropic manual tool loop: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- OpenAI function calling guide: https://platform.openai.com/docs/guides/function-calling
- hypothesis-jsonschema: https://github.com/python-jsonschema/hypothesis-jsonschema
- polyfactory: https://polyfactory.litestar.dev/latest/
- PyPI version metadata (2026-11-08): https://pypi.org/project/langgraph/ , https://pypi.org/project/openai-agents/ , https://pypi.org/project/langchain/ , https://pypi.org/project/anthropic/ , https://pypi.org/project/openai/


---

## 03. Attack Pattern taxonomy

Researched 2026-11-08. Scope: categories and technique descriptions only. No working payloads.

### Questions

1. What are the current OWASP Top 10 for LLM Applications and OWASP Top 10 for Agentic Applications (IDs, names, dates)?
2. Which categories matter for tool-using agents and can be tested automatically? MITRE ATLAS mappings?
3. Proposed v1 Attack Patterns (6-8): OWASP mapping, vector, Check, Frozen vs Adaptive.
4. Permissively licensed agent-injection datasets/benchmarks usable as seeds (license, size).
5. Multi-turn attack strategies (Crescendo, PAIR, TAP) as Attacker-loop strategies.

### Findings

#### Q1. OWASP lists (latest editions)

**OWASP Top 10 for LLM Applications, 2025 edition** (the "2025 Top 10 Risk & Mitigations for LLMs and Gen AI Apps"; the OWASP page gives March 12, 2025). Source: https://genai.owasp.org/llm-top-10/

| ID | Name |
|---|---|
| LLM01:2025 | Prompt Injection |
| LLM02:2025 | Sensitive Information Disclosure |
| LLM03:2025 | Supply Chain |
| LLM04:2025 | Data and Model Poisoning |
| LLM05:2025 | Improper Output Handling |
| LLM06:2025 | Excessive Agency |
| LLM07:2025 | System Prompt Leakage |
| LLM08:2025 | Vector and Embedding Weaknesses |
| LLM09:2025 | Misinformation |
| LLM10:2025 | Unbounded Consumption |

**OWASP Top 10 for Agentic Applications 2026**, released December 9, 2025 by the OWASP GenAI Security Project (Agentic Security Initiative). Sources: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ and the launch post https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agent

| ID | Name (launch-post example incident) |
|---|---|
| ASI01 | Agent Goal Hijack (EchoLeak) |
| ASI02 | Tool Misuse & Exploitation (Amazon Q) |
| ASI03 | Identity & Privilege Abuse |
| ASI04 | Agentic Supply Chain Vulnerabilities (GitHub MCP exploit) |
| ASI05 | Unexpected Code Execution (RCE) (AutoGPT RCE) |
| ASI06 | Memory & Context Poisoning (Gemini Memory Attack) |
| ASI07 | Insecure Inter-Agent Communication |
| ASI08 | Cascading Failures |
| ASI09 | Human-Agent Trust Exploitation |
| ASI10 | Rogue Agents (Replit meltdown) |

The launch post calls ASI02 just "Tool Misuse". The longer name "Tool Misuse & Exploitation" comes from a secondary summary (https://goteleport.com/blog/owasp-top-10-agentic-applications). The full PDF sits behind a download link, so I could not fetch it to check the exact wording. Launch post quote: "Once AI began taking actions, the nature of security changed forever."

**Older list, now superseded for our use:** "Agentic AI – Threats and Mitigations" v1.0 (Feb 2025) lists 15 threats T1-T15, including T1 Memory Poisoning, T2 Tool Misuse and T3 Privilege Compromise, each mapped back to LLM04/LLM06 (summary at https://www.aigl.blog/agentic-ai-threats-and-mitigations/). The ASI list replaces it as the headline taxonomy. Map to ASI IDs, not T-numbers.

#### Q2. Relevance to tool-using agents and automatic testability

| Category | Relevant to tool agents? | Auto-testable in CI? | Notes |
|---|---|---|---|
| LLM01 / ASI01 Prompt injection, goal hijack | Core | Yes | Success = a forbidden tool call or a canary leak, so a deterministic Check works |
| ASI02 Tool Misuse | Core | Yes | Assertions on intercepted tool name and arguments |
| LLM06 Excessive Agency / ASI03 Identity & Privilege Abuse | Core | Yes | Calls outside the Policy's allowed set, or outside the user's scope |
| LLM02 Sensitive Info Disclosure | High | Yes | Canary strings and PII/regex in output or in outbound tool arguments |
| LLM07 System Prompt Leakage | High | Yes | Plant a canary in the system prompt, then detect it in output |
| LLM05 Improper Output Handling | Medium | Partly | Detect markup/URLs/SQL in outputs that feed downstream sinks |
| ASI06 Memory & Context Poisoning | Medium | Partly | Needs multi-session state. Fits Adaptive cases, later version |
| LLM10 Unbounded Consumption / ASI08 Cascading | Medium | Yes (cheap) | Tool-call count, loop, or token-budget assertions |
| ASI05 Unexpected Code Execution | Only if the agent has a code/shell tool | Yes | Assert no exec-tool call, or a sandbox canary file |
| ASI09 Human-Agent Trust Exploitation | Low | Judge only | Persuasion quality is fuzzy |
| LLM09 Misinformation | Low | Judge only | Out of scope for v1 |
| LLM03/ASI04 Supply chain, LLM04 poisoning, LLM08 embeddings, ASI07 inter-agent, ASI10 rogue | Low for v1 | Mostly no | Build-time or infrastructure concerns. Skip for v1 (ASI07 later, for multi-agent Targets) |

**MITRE ATLAS** IDs, checked against `mitre-atlas/atlas-data` `dist/ATLAS.yaml` v5.6.0 (https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml; the file says it is deprecated, current data is at https://github.com/mitre-atlas/atlas-data):
- AML.T0051 LLM Prompt Injection, with sub-techniques .000 Direct and .001 Indirect
- AML.T0054 LLM Jailbreak
- AML.T0056 Extract LLM System Prompt
- AML.T0053 AI Agent Tool Invocation
- AML.T0057 LLM Data Leakage

Newer agent-specific ATLAS techniques were added in late 2025. They were not in the file I could read. Check IDs against the current release before hard-coding them.

#### Q3. Proposed v1 Attack Patterns

"Frozen" = a fixed, replayable case (deterministic, cheap, good for regression in CI). "Adaptive" = the Attacker LLM generates turns live, using the Target's replies.

| # | Attack Pattern | OWASP | ATLAS | Vector | Check (deterministic first) | Breach type | Case |
|---|---|---|---|---|---|---|---|
| P1 | **Indirect injection via tool output**: attacker text sits in data a tool returns (email, web page, ticket, RAG doc) and tells the agent to take an action | LLM01, ASI01 | T0051.001 | Tool output (mocked tool returns a poisoned record) | `ToolCallCheck`: a forbidden tool was called, or a tool got forbidden arguments, after the poisoned observation | Objective | Frozen (seedable from AgentDojo/InjecAgent). Adaptive variant can rewrite the injected text |
| P2 | **Tool-argument manipulation**: push a permitted tool past its Policy limits (amount > cap, someone else's account ID, wildcard query) | ASI02, LLM06 | T0053 | Direct user turn | `ToolArgCheck`: predicate on intercepted arguments, e.g. `refund.amount > 500` or `account_id != session.user` | Objective | Both. Planner generates the predicate from the schema plus the Policy |
| P3 | **Privilege escalation across a tool chain**: chain allowed tools to reach a forbidden outcome (lookup, then admin action; read, then write) or act outside the user's identity scope | LLM06, ASI03, ASI02 | T0053 | Direct, multi-step | `ToolSequenceCheck`: forbidden call order, a call to a tool outside the allowlist, or a call missing a required confirmation step | Objective | Adaptive (needs planning). Frozen once a winning trace is found |
| P4 | **Data exfiltration via tools**: get secret/PII data written into an outbound tool's arguments (send_email, http_get URL, create_ticket) | LLM02, ASI02, ASI01 | T0057, T0053 | Tool output or direct | `CanaryCheck` / `PIIRegexCheck` run on outbound tool-call arguments, not only on chat text. Includes markdown-image or URL egress in the output | Objective | Frozen (canaries planted in fixtures) plus Adaptive |
| P5 | **System-prompt extraction** | LLM07 | T0056 | Direct | `CanaryCheck`: unique token planted in the system prompt shows up in output. Optional fuzzy n-gram overlap with the system prompt | Policy | Frozen bank of extraction techniques (role-play, translation, "repeat above", encoding) plus Adaptive |
| P6 | **Multi-turn goal hijacking / gradual escalation**: build up over several benign turns, then move the agent toward a forbidden action or statement | ASI01, LLM01 | T0051.000, T0054 | Direct, multi-turn | If the Objective is an action: `ToolCallCheck`. If it is speech: Judge against the Policy clause | Objective or Policy | Adaptive only (Crescendo/PAIR-style loop, see Q5) |
| P7 | **Policy-violating speech** (forbidden topics, unauthorized promises, discount commitments, off-brand claims) | LLM01, LLM09 | T0054 | Direct | Regex/keyword where the Policy is crisp (e.g. "guarantee", price patterns). Otherwise Judge | Policy | Both |
| P8 (optional) | **Resource abuse / loop induction**: get the agent to repeat or fan out tool calls | LLM10, ASI08 | none | Direct or tool output | `BudgetCheck`: tool calls per turn, total tokens, or a repeated identical call | Objective | Frozen |

Notes:
- P1 and P4 need the harness to control tool **responses**, not just observe calls. The tool interception layer must support stubbing/mocking returns.
- P1-P4 and P8 are fully deterministic. P5 is deterministic if a canary is planted. Only P6 (speech branch) and P7 need the Judge. This supports Q7.

#### Q4. Seed datasets and benchmarks

| Name | Size | License | Fit |
|---|---|---|---|
| **AgentDojo** (ETH SPY Lab, arXiv 2406.13352; NeurIPS 2024 D&B, venue not verified here) | "97 realistic tasks … 629 security test cases" over workspace, banking, travel and Slack suites; v1 has 27 injection tasks | MIT (repo) | Best fit. It is a Python environment with tool stubs, user tasks, injection tasks and checks on environment state. Its utility/security check design matches our deterministic Checks |
| **InjecAgent** (UIUC, arXiv 2403.02691) | "1,054 test cases that span 17 different user tools and 62 attacker tools". Two classes: direct harm and data stealing. Base and "enhanced" settings | MIT (repo) | Good Frozen seeds for P1/P4. JSONL format, easy to import |
| **Agent Security Bench (ASB)** (ICLR 2025, arXiv 2410.02644) | 10 scenarios. Attacks: direct PI, observation PI, memory poisoning, PoT backdoor, mixed | MIT (repo) | Seeds for P1/P6. Taxonomy cross-check |
| **BIPIA** (Microsoft) | 5 tasks (email, web, table QA, summarization, code QA) | Repo has a LICENSE file, but its type was NOT confirmed (likely MIT, verify). Some source data (Web QA, Summarization) must be downloaded separately under upstream terms. Labelled research-only | Text-only injection, no tools. Useful only for P1 payload styles. Do not redistribute the data |
| **WASP** (Meta, NeurIPS 2025 D&B) | Web-agent injection scenarios | **CC-BY-NC 4.0** for the code and data | Non-commercial. Do NOT bundle it. At most, link to it |

Gotcha: check license files in each repo at the pinned commit before vendoring data. GitHub API calls were blocked from this sandbox, so licenses come from the repo pages.

#### Q5. Multi-turn and automated strategies the Attacker loop can implement

- **PAIR** (Chao et al., arXiv 2310.08419, Oct 2023): an attacker LLM "automatically generate[s] jailbreaks for a separate targeted LLM without human intervention", refining one prompt per iteration based on the target's reply and a judge score, "often in fewer than twenty queries". Fit: the simplest Adaptive loop. Attacker plus Objective plus feedback from a Check or Judge score. https://arxiv.org/abs/2310.08419
- **TAP** (Mehrotra et al., arXiv 2312.02119, Dec 2023): tree search over candidate prompts. It assesses candidates "and prune[s] the ones unlikely to result in jailbreaks, reducing the number of queries". Fit: PAIR with branching and pruning (off-topic pruning before querying, score pruning after). Higher cost. Make it an optional strategy behind a budget. https://arxiv.org/abs/2312.02119
- **Crescendo** (Russinovich et al., Microsoft, arXiv 2404.01833, Apr 2024): starts general, then "gradually escalates the dialogue by referencing the model's replies". Fit: a true multi-turn strategy (PAIR/TAP are mostly single-shot refinement). The Attacker keeps the conversation going and backtracks on refusal. This is the natural basis for P6. https://arxiv.org/abs/2404.01833
- Strategy interface sketch: `Strategy.next_turn(objective, history, last_feedback) -> message | stop`. PAIR = linear refinement with reset. TAP = beam with pruning. Crescendo = a stateful conversation with backtracking. PyRIT (Microsoft) ships Crescendo, PAIR and TAP orchestrators as a reference (https://github.com/Azure/PyRIT; license not checked here).

### Recommendation

- Ship **P1-P7 in v1** (P8 if cheap). This settles O4. Weight toward P1-P4: they are agent-specific, map to ASI01/ASI02/ASI03, and are fully deterministic.
- Tag every Attack Pattern with **both** LLM Top 10 2025 and Agentic Top 10 2026 IDs, plus an ATLAS ID. Use the ASI list as the primary tag for agent patterns. Q14 says "OWASP categories" without saying which list, so tagging both resolves it.
- Build the tool-interception layer to **mock tool returns** (needed for P1/P4) and to run Checks on **outbound tool-call arguments** (needed for P4).
- Use **AgentDojo** (environment design plus injection tasks) and **InjecAgent** (Frozen seeds) as MIT-licensed seeds. Exclude WASP. Treat BIPIA as reference only.
- Adaptive strategies in this order: PAIR first (simple), then Crescendo (multi-turn, P6), then TAP (optional, budgeted). Feed deterministic Check results back as the attacker's reward signal wherever possible. Use the Judge only when no Check applies.

### Risks and gotchas

- **Possible tension with Q6:** P4 (exfiltration via a tool) and Policy-speech leaks overlap. A secret in chat text is a Policy Breach, the same secret in `send_email` arguments is an Objective Breach. Define the rule explicitly: outbound tool argument = Objective, assistant text = Policy.
- **Tension with Q7:** PAIR/TAP/Crescendo as published use an LLM judge to score each step. Our Checks are binary, so a deterministic success signal gives little gradient. The Adaptive loop probably still needs an LLM "progress scorer" separate from the final Breach verdict. Keep that scorer out of the Breach decision so Q7 holds.
- Indirect injection (P1) depends on the Target actually calling the poisoned tool. If the Attacker cannot steer the user task, the case never fires. Frozen cases need a fixed user task (as in AgentDojo).
- Canary checks give false negatives when the model paraphrases, translates or encodes the secret. Add normalized and encoded variants (base64, spacing).
- Frozen cases go stale as models are patched, and published benchmark injections may be in training data. Use them for regression, not as a measure of robustness.
- OWASP Agentic names differ slightly between sources ("Tool Misuse" vs "Tool Misuse & Exploitation"). Pin to the PDF wording before publishing tags.
- ATLAS IDs change between releases. The data file I read (v5.6.0) is marked deprecated.
- Dual-use: ship technique *descriptions* and templated strategies, not a large bank of high-potency jailbreak strings.

### Sources

- OWASP Top 10 for LLM Applications 2025: https://genai.owasp.org/llm-top-10/
- OWASP Top 10 for Agentic Applications 2026 (resource page): https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- OWASP Agentic launch post (Dec 9, 2025): https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agent
- ASI names and short descriptions (secondary): https://goteleport.com/blog/owasp-top-10-agentic-applications
- OWASP Agentic AI Threats and Mitigations v1.0 summary (secondary): https://www.aigl.blog/agentic-ai-threats-and-mitigations/
- MITRE ATLAS data: https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml and https://github.com/mitre-atlas/atlas-data
- AgentDojo: https://arxiv.org/abs/2406.13352 and https://github.com/ethz-spylab/agentdojo
- InjecAgent: https://github.com/uiuc-kang-lab/InjecAgent
- Agent Security Bench: https://github.com/agiresearch/ASB and https://huggingface.co/papers/2410.02644
- BIPIA: https://github.com/microsoft/BIPIA
- WASP: https://github.com/facebookresearch/wasp
- PAIR: https://arxiv.org/abs/2310.08419
- TAP: https://arxiv.org/abs/2312.02119
- Crescendo: https://arxiv.org/abs/2404.01833
- PyRIT: https://github.com/Azure/PyRIT


---

## 04. Harness runtime and CI integration

Researched 2026-11-08. Versions are from the PyPI JSON API on that date.

### Questions

1. Orchestration for the harness's own agents: plain asyncio vs LangGraph vs pydantic-ai. Which suits a light, deterministic library?
2. Provider-agnostic LLM client: LiteLLM vs pydantic-ai vs a thin custom protocol over the openai/anthropic SDKs. Cover local models, token/cost accounting, retries and rate limits.
3. Budget enforcement: counting tokens and cost across providers, and stopping a Run cleanly at the cap.
4. pytest plugin: one item per Regression Case, Trials, transcripts in failure reports, `--junitxml`.
5. CI output: JUnit XML, GitHub job summary and annotations, JSON/HTML. What do comparable tools emit?
6. Packaging: uv, build backend, Python floor, Typer vs Click.

### Findings

#### Q1. Orchestration

| Option | Version (date) | Notes |
|---|---|---|
| asyncio `TaskGroup` + `Semaphore` | stdlib, 3.11+ | No dependency. Structured concurrency. |
| LangGraph | 1.2.20 (2026-11-05) | Pulls in `langchain-core`, `langgraph-checkpoint`, `langgraph-prebuilt` and `langgraph-sdk` ([PyPI](https://pypi.org/pypi/langgraph/json)). |
| pydantic-ai (`pydantic-ai-slim`) | 2.66.0 (2026-11-04) | Agent framework, plus `pydantic-graph`. Requires Python >=3.11 ([PyPI](https://pypi.org/pypi/pydantic-ai-slim/json)). |

- LangGraph describes itself as "a low-level orchestration framework and runtime for long-running, stateful agents". Its main features are durable execution ("checkpoint state and resume after failures or pauses") and human-in-the-loop ([docs](https://docs.langchain.com/oss/python/langgraph/overview)). A CI Run lasts minutes and is thrown away afterwards, so it needs neither. The docs say "LangGraph does not require LangChain", yet the package still depends on `langchain-core` ([PyPI](https://pypi.org/pypi/langgraph/json)).
- TaskGroup semantics fit "a Budget cap stops everything": "The first time any of the tasks belonging to the group fails with an exception other than `asyncio.CancelledError`, the remaining tasks in the group are cancelled". The failures are then "combined in an `ExceptionGroup`" ([Python docs](https://docs.python.org/3/library/asyncio-task.html)). TaskGroup was "Added in version 3.11". `TaskGroup.cancel()` arrives in 3.15 (same page).
- Determinism: LLM output is never deterministic. What the harness can control is scheduling, seeds and the order of results. With plain asyncio you own the loop, so you can sort results by `(objective_id, attacker_idx)` no matter which task finishes first. Graph frameworks add their own scheduling layer on top.

**Verdict: plain asyncio.** For each Attacker's multi-turn loop, a while-loop of about 30 lines that calls the LLM client protocol is simpler than adopting an agent framework.

```python
import asyncio
from dataclasses import dataclass

class BudgetExceeded(Exception): ...

@dataclass
class Objective:
    id: str
    goal: str

async def run_explore(planner, attacker_factory, target, budget, *, concurrency: int = 4):
    objectives: list[Objective] = await planner.plan(target.description)
    sem = asyncio.Semaphore(concurrency)        # bounded Attacker pool
    results: dict[str, "AttackResult"] = {}

    async def one(obj: Objective) -> None:
        async with sem:
            budget.check()                      # raises BudgetExceeded -> TaskGroup cancels siblings
            attacker = attacker_factory(obj)
            results[obj.id] = await attacker.attack(target, budget)

    try:
        async with asyncio.timeout(budget.wall_clock_s):
            async with asyncio.TaskGroup() as tg:
                for obj in objectives:
                    tg.create_task(one(obj))
    except* BudgetExceeded:
        pass                                    # partial results; Run marked "budget_exhausted"
    except TimeoutError:
        pass
    return [results[o.id] for o in objectives if o.id in results]   # stable order
```

#### Q2. Provider-agnostic LLM client

| | LiteLLM | pydantic-ai | Thin custom protocol |
|---|---|---|---|
| Version | 1.108.3 (2026-11-07), Python `>=3.10,<3.15` | 2.66.0 (2026-11-04), Python `>=3.11` | openai 3.46.0, anthropic 2.6.0 (2026-11-05) |
| Ollama | `ollama_chat/` prefix with `api_base="http://localhost:11434"` ([docs](https://docs.litellm.ai/docs/providers/ollama)) | Has its own Ollama provider guide ([docs](https://pydantic.dev/docs/ai/models/compatible-apis/)) | Use Ollama's OpenAI-compatible endpoint via `openai` with `base_url` |
| vLLM | `model="hosted_vllm/<name>"` plus `api_base` ([docs](https://docs.litellm.ai/docs/providers/vllm)) | "Connect with `VLLMProvider`, setting `base_url` directly or through `VLLM_BASE_URL`" ([docs](https://pydantic.dev/docs/ai/models/compatible-apis/)) | Same, via `openai` with `base_url` |
| Cost | `completion_cost` returns USD. "Uses the live list from `api.litellm.ai`". `LITELLM_LOCAL_MODEL_COST_MAP="True"` uses the bundled copy instead ([docs](https://docs.litellm.ai/docs/completion/token_usage)) | `RunUsage.cost` is "a best-effort estimate ... calculated from each request's usage with genai-prices" ([docs](https://pydantic.dev/docs/ai/core-concepts/agent/)) | Read `usage` from each response and price it yourself, e.g. with `genai-prices` 0.2.1 ([PyPI](https://pypi.org/pypi/genai-prices/json)) |
| Limits | None per call | `UsageLimits` covers "tokens, requests, tool calls, and cost" and raises `UsageLimitExceeded` ([docs](https://pydantic.dev/docs/ai/core-concepts/agent/)) | You build it (Q3) |
| Retries | `completion(..num_retries=2)`, plus fallbacks. Backoff and cooldowns need the Router ([docs](https://docs.litellm.ai/docs/completion/reliable_completions)) | The client "defaults to `max_retries=2` ... it retries status 408, 409, 429 or 5xx" ([docs](https://pydantic.dev/docs/ai/models/openai/)) | Both official SDKs retry 429/5xx themselves (`max_retries`) |
| Footprint | Heavy. Hard-depends on `openai`, `tiktoken`, `tokenizers`, `huggingface-hub`, `aiohttp`, `jinja2`, `click` and more ([PyPI](https://pypi.org/pypi/litellm/json)) | Moderate. `pydantic`, `genai-prices`, `opentelemetry-api`, `pydantic-graph`, ... ([PyPI](https://pypi.org/pypi/pydantic-ai-slim/json)) | Minimal. Provider SDKs go in extras. |

Supply-chain note: on 2026-03-24, PyPI releases `litellm==1.82.7` and `1.82.8` were compromised. The attacker got in through a compromised Trivy step in LiteLLM's CI ([LiteLLM blog](https://docs.litellm.ai/blog/tags/supply-chain)). Afterwards LiteLLM rebuilt its release pipeline (same source). That matters for a security tool that users install inside CI next to their provider keys.

**Verdict:** define our own small `ChatModel` protocol, `async complete(messages, tools, **opts) -> Completion(text, tool_calls, usage)`. Ship adapters as extras: `[openai]` covers OpenAI plus every OpenAI-compatible server (Ollama, vLLM, OpenRouter), `[anthropic]` covers Anthropic, and an optional `[litellm]` adapter is the long-tail escape hatch. This keeps per-role pluggability (Q8) and the user's own API key, with no hard dependency on a framework.

#### Q3. Budget enforcement

- **Counting.** Take tokens from the provider's `usage` field on each response rather than counting with a local tokenizer. LiteLLM's `token_counter` itself "defaults to tiktoken if no model-specific tokenizer is available", so local counts are only an approximation for non-OpenAI models ([docs](https://docs.litellm.ai/docs/completion/token_usage)).
- **Cost.** Use a price table: `genai-prices`, LiteLLM's model cost map, or a user override in config. Local and open-weight models have no price, so count them as $0 and let the token, request and time caps bound them.
- **Pre-flight reservation.** A single call can overshoot the cap. Before each call, reserve `max_tokens × output price` plus the estimated input cost, then settle against the actual usage. pydantic-ai does a similar check ("Tools can access remaining budgets via `ctx.usage_limits`", [docs](https://pydantic.dev/docs/ai/core-concepts/agent/)).
- **Clean stop.** A shared `Budget` object holds an `asyncio.Lock` and counters for tokens, USD, requests and a wall-clock deadline. It raises `BudgetExceeded`, which TaskGroup turns into cancellation of the sibling tasks (Q1). Catch it with `except*`, then write the partial report with `status=budget_exhausted`. Exit codes:
  - Replay: a Budget stop is an error, not a pass.
  - Explore: report what was found.
- **Rate limits.** Wrap each role's client in an `aiolimiter`-style token bucket (RPM/TPM), and let the SDK's own retries handle 429s. The `Semaphore` bounds concurrency.

```python
class Budget:
    def __init__(self, max_usd, max_tokens, max_requests, wall_clock_s): ...
    async def reserve(self, est_usd: float, est_tokens: int) -> "Reservation":
        async with self._lock:
            if self.spent_usd + self.reserved_usd + est_usd > self.max_usd: raise BudgetExceeded("usd")
            ...
    async def settle(self, r: "Reservation", usage, price) -> None: ...
```

#### Q4. pytest plugin

Pattern: follow pytest's documented non-Python test collection example, which uses `pytest_collect_file` with a `pytest.File` subclass and a custom `pytest.Item` that implements `runtest`, `repr_failure` and `reportinfo` ([docs](https://docs.pytest.org/en/stable/example/nonpython.html)). pytest is at 9.2.0 (2026-10-27).

- **One item per Regression Case.** The Case runs its N=3 Trials inside `runtest`. The test fails if any Trial is a Breach (Q13), and JUnit gets one `<testcase>` per Case.
- **One item per Trial** (an alternative): `case.yaml::trial[2]`. This is noisier and makes "any Breach fails" a cross-item rule. Not recommended. Attach Trial outcomes as properties instead.
- **Transcripts.** Whatever `repr_failure` returns becomes the `<failure>` body in JUnit. Put a short transcript excerpt and the path to the full transcript artifact there.
- **JUnit gotcha.** `junit_family` defaults to `xunit2`. The `record_property` fixture warns that it "is incompatible with junit_family 'xunit2' (use 'legacy' or 'xunit1')". However, pytest still writes `report.user_properties` as `<property>` elements in all families ([source](https://github.com/pytest-dev/pytest/blob/main/src/_pytest/junitxml.py)). Setting `item.user_properties` directly therefore works without the warning. Custom report sections (`add_report_section`) do not go into JUnit. Only captured out/err/log do, and only with `junit_logging` set (same source).

```python
# harness/pytest_plugin.py  (registered via [project.entry-points.pytest11])
import pytest, yaml

def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".yaml" and file_path.parent.name == "regression_cases":
        return CaseFile.from_parent(parent, path=file_path)

class CaseFile(pytest.File):
    def collect(self):
        case = yaml.safe_load(self.path.read_text())
        yield CaseItem.from_parent(self, name=case["id"], case=case)

class BreachFound(Exception): ...

class CaseItem(pytest.Item):
    def __init__(self, *, case, **kw):
        super().__init__(**kw)
        self.case = case
        self.add_marker(pytest.mark.redteam)
        for tag in case.get("tags", []):
            self.add_marker(tag)

    def runtest(self):
        cfg = self.config
        trials = run_replay(self.case, n=cfg.getoption("redteam_trials"))  # asyncio.run inside
        breaches = [t for t in trials if t.breach]
        self.user_properties += [("trials", len(trials)), ("breaches", len(breaches)),
                                 ("transcript", str(trials[0].transcript_path))]
        if breaches:
            raise BreachFound(breaches)

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, BreachFound):
            b = excinfo.value.args[0][0]
            return f"Breach in {len(excinfo.value.args[0])} trial(s): {b.check}\n{b.excerpt}\nfull: {b.transcript_path}"
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return self.path, 0, f"regression case: {self.name}"

def pytest_addoption(parser):
    parser.addoption("--redteam-trials", dest="redteam_trials", type=int, default=3)
```

Running `pytest --junitxml=redteam.xml` then works with no extra code. With `pytest-xdist`, keep the Run's Budget per worker or in a shared file lock. Note that a per-Run Budget does not stretch naturally across xdist workers.

#### Q5. CI output

What comparable tools emit:
- **promptfoo** writes JSON, HTML ("a visual, shareable report"), CSV, YAML, JSONL and **JUnit XML** ("Compact CI test-report output") ([docs](https://www.promptfoo.dev/docs/configuration/outputs/)).
- **garak** writes `garak.<uuid>.report.jsonl`, an HTML report, and a JSONL hit log "describing all the attempts from the run that were scored successful" ([docs](https://reference.garak.ai/en/latest/reporting.html)).

GitHub Actions:
- Job summary through `$GITHUB_STEP_SUMMARY`. It supports "GitHub flavored Markdown". Each step "is restricted to a maximum size of 1MiB", and at most "20 job summaries from steps are displayed per job" ([docs](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)).
- Annotations: `::error file={name},line={line},endLine={endLine},title={title}::{message}` (same page). Point these at the Regression Case YAML file.
- GitHub does not render JUnit natively. Third-party actions do it, e.g. [mikepenz/action-junit-report](https://github.com/mikepenz/action-junit-report). Leave that to the user's workflow.

**Minimal v1 set (this partly resolves O1):**
1. **JSON report** (`report.json`, schema-versioned). This is the canonical artifact: Run metadata, Budget spent, Findings, Trials and transcript paths. Every other format is derived from it.
2. **JUnit XML**. Through pytest it comes for free. The CLI writes it from the JSON so the CLI-only path matches.
3. **GitHub step summary Markdown plus `::error` annotations**, emitted when `GITHUB_ACTIONS=true`.
4. **Transcripts** as JSONL files, one per Trial, for upload with `actions/upload-artifact`.
- Defer: HTML report (v1.x, a static render of the JSON), SARIF, CSV.

#### Q6. Packaging

- **Python floor: 3.11.** 3.10 reached end-of-life on 2026-10-01. 3.11 is security-only until 2027-10, and 3.14 and 3.15 are in bugfix ([devguide](https://devguide.python.org/versions/)). 3.11 also brings `TaskGroup`, `asyncio.timeout` and `except*`, and matches pydantic-ai's floor.
- **uv 0.13.7** (2026-11-03) for envs, lockfile and publishing. Its `uv_build` backend is the `uv init` default, but it "currently only supports pure Python code" ([docs](https://docs.astral.sh/uv/concepts/build-backend/)). We are pure Python, so either backend works:
  - **hatchling 1.33.0** (2026-10-28) is the more mature choice, with plugins such as hatch-vcs for git-tag versions.
  - `uv_build` needs a pinned upper bound (`uv_build>=0.13.7,<0.14`).
- **CLI: Typer 0.28.0** (2026-11-06). It is "Based on Python type hints" and since 0.26.0 has "vendored Click" ([docs](https://typer.tiangolo.com/)). It depends on `rich` and `shellingham`. Click 8.5.1 is leaner. Typer suits `<tool> run --mode replay|explore` with an `Enum` and gives nicer help. Choose Click if dependency count matters more.
- **Entry points:**
  - `[project.scripts] <tool> = "<pkg>.cli:app"`
  - `[project.entry-points.pytest11] <tool> = "<pkg>.pytest_plugin"`
  - extras `openai`, `anthropic`, `litellm`

### Recommendation

- **Runtime.** Use plain asyncio (TaskGroup + Semaphore + `asyncio.timeout`) with a hand-written Attacker loop, and no agent framework. This answers **O5**.
- **LLM access.** Use our own `ChatModel` protocol, with adapters over the `openai` SDK (which also covers Ollama, vLLM and OpenRouter through `base_url`) and the `anthropic` SDK, as extras. LiteLLM is an optional adapter only.
- **Budget.** A single shared `Budget` with reserve/settle accounting, based on provider-reported `usage` and a pinned local price table. `BudgetExceeded` cancels the TaskGroup, and a partial report is written either way.
- **pytest.** `pytest_collect_file` with one custom Item per Regression Case. N Trials run inside the Item, and any Breach fails it. Transcripts are attached through `repr_failure` and `user_properties`. Rely on the built-in `--junitxml`.
- **Output v1** (answers **O1**):
  - `report.json`, the canonical format
  - JUnit XML
  - GitHub step summary and annotations
  - per-Trial JSONL transcripts
  - HTML later
- **Packaging.**
  - Python >=3.11
  - uv for workflow, hatchling as build backend
  - Typer for the CLI
  - provider SDKs as optional extras

Conflicts with decisions: none of Q5, Q8, Q9, Q10 or Q13 is contradicted. Two tensions:
- **Q8 and the Budget.** If "pluggable models" is implemented by wrapping LiteLLM, the Budget's cost accuracy depends on LiteLLM's remote cost map ("Uses the live list from `api.litellm.ai`"). That fetch is non-deterministic and needs network access in CI. Pin a local map.
- **Q5 money caps and open-weight Attackers.** Local Attackers have no price, so a money cap does not bound them. The token and time caps must be mandatory, not optional.

### Risks and gotchas

- **LiteLLM caps Python below 3.15** (`requires-python <3.15`), and 3.15 is already a supported release ([PyPI](https://pypi.org/pypi/litellm/json), [devguide](https://devguide.python.org/versions/)). Any hard LiteLLM dependency blocks users on 3.15.
- **Supply chain.** LiteLLM releases were compromised in March 2026 ([blog](https://docs.litellm.ai/blog/tags/supply-chain)). Minimise transitive dependencies in a tool that runs in CI with provider keys. Publish with PyPI Trusted Publishing and document hash-pinned installs.
- **Release churn.** pydantic-ai is at 2.66 and LiteLLM at 1.108, and both release several times a week. Pin upper bounds on any adapter dependency.
- **Budget overshoot.** Concurrent Attackers can overshoot the cap between check and spend. Reserve before each call, and treat `max_tokens` as mandatory on every request.
- **Cancellation.** If an exception is swallowed inside an Attacker, TaskGroup cannot cancel its siblings. Never catch bare `Exception` around `await`s. Let `CancelledError` and `BudgetExceeded` propagate.
- **`asyncio.run` inside a pytest Item.** This conflicts with pytest-asyncio or anyio if the user's suite already runs a loop. Run the Replay in a fresh loop inside a worker thread, or document the incompatibility.
- **xdist.** A per-Run Budget does not cover multiple workers. Pass a per-worker cap (total / N) or use a file-locked ledger.
- **JUnit properties.** `record_property` warns under the default `xunit2`. Set `item.user_properties` directly. Some strict JUnit consumers reject `<properties>` on testcases ([pytest docs](https://docs.pytest.org/en/stable/how-to/output.html)). Keep the essential information in the `<failure>` message.
- **Step summary limit.** 1 MiB per step, so link to transcripts and do not inline them.
- **Typer vendoring Click** (since 0.26). Click plugins and extensions written against an external `click` may not interoperate with Typer's vendored copy.

### Sources

- Python asyncio tasks (TaskGroup, timeout): https://docs.python.org/3/library/asyncio-task.html
- Python version status: https://devguide.python.org/versions/
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview ; PyPI https://pypi.org/pypi/langgraph/json (1.2.20, 2026-11-05)
- pydantic-ai agents and UsageLimits: https://pydantic.dev/docs/ai/core-concepts/agent/
- pydantic-ai OpenAI model and retries: https://pydantic.dev/docs/ai/models/openai/
- pydantic-ai compatible APIs (vLLM, Ollama): https://pydantic.dev/docs/ai/models/compatible-apis/
- pydantic-ai-slim PyPI (2.66.0, 2026-11-04): https://pypi.org/pypi/pydantic-ai-slim/json
- LiteLLM token usage and cost: https://docs.litellm.ai/docs/completion/token_usage
- LiteLLM reliability: https://docs.litellm.ai/docs/completion/reliable_completions
- LiteLLM Ollama: https://docs.litellm.ai/docs/providers/ollama ; vLLM: https://docs.litellm.ai/docs/providers/vllm
- LiteLLM PyPI (1.108.3, 2026-11-07): https://pypi.org/pypi/litellm/json
- LiteLLM supply-chain incident: https://docs.litellm.ai/blog/tags/supply-chain
- genai-prices PyPI (0.2.1): https://pypi.org/pypi/genai-prices/json
- openai 3.46.0 / anthropic 2.6.0 PyPI: https://pypi.org/pypi/openai/json , https://pypi.org/pypi/anthropic/json
- pytest non-Python tests: https://docs.pytest.org/en/stable/example/nonpython.html
- pytest output and JUnit: https://docs.pytest.org/en/stable/how-to/output.html
- pytest junitxml source: https://github.com/pytest-dev/pytest/blob/main/src/_pytest/junitxml.py
- GitHub workflow commands and job summaries: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- mikepenz/action-junit-report: https://github.com/mikepenz/action-junit-report
- promptfoo outputs: https://www.promptfoo.dev/docs/configuration/outputs/
- garak reporting: https://reference.garak.ai/en/latest/reporting.html
- uv build backend: https://docs.astral.sh/uv/concepts/build-backend/
- Typer: https://typer.tiangolo.com/
- PyPI versions (typer 0.28.0, click 8.5.1, hatchling 1.33.0, uv 0.13.7, pytest 9.2.0): https://pypi.org/pypi/<name>/json


---

