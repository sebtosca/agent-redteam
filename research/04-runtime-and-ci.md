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
