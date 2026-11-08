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
