# Plan: toolbreach

Generated: 2026-11-08 from DISCOVERY.md + RESEARCH.md

This is a milestone-level plan. Attack-technique specifics (the P1–P7 pattern set, adaptive strategies, dataset licenses) live in [RESEARCH.md](RESEARCH.md) §03 and are cited by reference, not restated here. Decisions are fixed in [docs/adr/](docs/adr/) and [DISCOVERY.md](DISCOVERY.md); plan within them.

## Goal

An open-source Python tool, `toolbreach`, that AI engineers run (mostly in CI) to red-team their own authorized LLM agents. The harness is a LangGraph multi-agent system — a Planner supervisor routes Objectives to specialist Attackers, a Judge and deterministic Checks detect Breaches. Its edge is owning the **tool channel**: it instruments the target's tools in-process, injects through tool returns, and detects breaches at the tool boundary. Explore discovers Breaches and proposes Regression Cases; a human reviews them; Replay enforces the accepted suite on every PR.

## Tech stack

| Choice | Version (2026-11-08) | Source |
|---|---|---|
| Python | ≥3.11 | RESEARCH §04 |
| uv + hatchling | uv 0.13.7, hatchling 1.33.0 | RESEARCH §04 |
| LangGraph (harness orchestration) | pin `>=1.2.20,<1.3` | ADR 0003, Q18 |
| LangChain `init_chat_model` (harness models) | langchain 1.4.x | Q20 |
| genai-prices (money caps) | 0.2.1 | RESEARCH §04 |
| Typer (CLI) / pytest (plugin host) | 0.28 / 9.2 | RESEARCH §04 |
| polyfactory (fake synthesis) | 3.5.0 | RESEARCH §02 |
| Adapter targets | langgraph/langchain, openai-agents 0.24.x, raw callables, httpx | Q24, RESEARCH §02 |
| License / distribution | Apache-2.0, PyPI as `toolbreach` | Q17 |

## Architecture overview

Package `src/toolbreach/`:

| Path | Contents |
|---|---|
| `core/` | domain models, Interceptor, Event Log, Budget, Authorization |
| `config/` | YAML config schema + loader |
| `adapters/` | `langgraph.py`, `raw.py`, `openai_agents.py`, `http.py` |
| `fakes/` | fake-result resolution chain |
| `checks/` | deterministic Checks |
| `patterns/` | Attack Pattern library (YAML) + registry |
| `graph/` | harness graph: state, nodes, specialists, build |
| `llm.py` | per-role models + usage tracking |
| `findings/` · `cases/` · `report/` | grouping, case store + replay, JSON/JUnit/GitHub output |
| `cli.py` · `pytest_plugin.py` | entry points |
| `examples/demo_support_agent/` | deliberately vulnerable LangGraph target for tests + demos |

**Import-boundary rule (ADR 0003 guardrail):** LangGraph/LangChain may be imported only in `graph/`, `llm.py` and `adapters/langgraph.py`. `core/`, `checks/`, `findings/`, `cases/` and `report/` stay plain Python, testable without LangGraph. Enforced by an import-linter contract in CI.

Data flow:
```
toolbreach.yaml → CLI/pytest → harness graph (LangGraph)
  planner(supervisor) ─Send(Objective)→ specialist Attacker ×N → aggregate → group_findings
                                           ↑ call_target ↓
  adapter → Target; every tool call → Interceptor (Live | Intercepted+fake | Injected) → Event Log
  Checks read Event Log + text → Breach (Objective | Policy) → Pending Cases → review(interrupt) → report
Replay: cases/*.yaml → N Trials → Checks → report.json · JUnit · GitHub summary
```

## Decisions (made during planning)

- **D1 — On-disk layout in the user's repo:** `toolbreach.yaml` (config); `toolbreach/cases/*.yaml` (accepted cases, committed); `toolbreach/cases/pending/*.yaml` (committed only after review); `.toolbreach/runs/<id>/` (reports + transcripts, git-ignored).
- **D2 — Regression Case = one YAML file:** id, Objective, pattern id + OWASP/ATLAS tags, kind (`frozen`|`adaptive`), user task, attacker messages + injected payloads (frozen) or strategy + budget (adaptive), Checks, source Finding id, schema version.
- **D3 — Budget under LangGraph:** a usage-tracking callback on every role model feeds a shared, framework-free Budget; a `budget_ok` conditional edge ends each specialist loop; `max_tokens` mandatory per call; token + time caps required, money cap optional (C4); Replay treats a budget stop as an error, Explore writes a partial report.
- **D4 — Determinism:** aggregate reducer sorts Breaches by `(objective_id, specialist, attempt)`; frozen Replay with fixtures + seeded synthesis never calls the harness's own LLMs.
- **D5 — Review checkpointer:** in-process CLI review uses `InMemorySaver`; `toolbreach review` resuming later uses `SqliteSaver` in `.toolbreach/`.
- **D6 — Test doubles:** harness unit tests use a fake chat model for every role, so toolbreach's own CI needs no API keys; live-model smoke tests opt-in (`-m live`).
- **D7 — Demo target:** a LangGraph support bot with a live read-only tool and intercepted side-effecting tools, deliberately vulnerable, with an env flag that hardens it so the "fix → green" demo works.
- **D8 — Dual-use posture:** ship technique descriptions + templated strategies, not a bank of high-potency jailbreak strings; vendor only Apache/MIT payloads with NOTICE attribution (RESEARCH §03).

## Out of scope (v1)

Hosted/multi-tenant service or web dashboard (Q1); TypeScript SDK and CrewAI/Pydantic-AI/AutoGen/MCP adapters (Q24, phase-2 backlog); intercepting OpenAI *hosted* tools — impossible in-process, documented with `function_tool` stand-ins (C5); supply-chain/poisoning/embedding/misinformation categories not testable at runtime (RESEARCH §03); bundling non-commercial datasets e.g. WASP (RESEARCH §03); SARIF/CSV output; pointing at targets without Authorization (Q5, refused by design).

## Phases at a glance

| Phase | Name | Outcome |
|---|---|---|
| 1 | Foundations | installable package; config + Authorization gate; Interceptor core; Budget; repo CI — all framework-free |
| 2 | Tracer bullet | `run --mode explore` finds one indirect-injection Objective Breach against the demo agent and writes `report.json` |
| 3 | Regression lifecycle | Explore → Findings → Pending Cases → review `interrupt()` → Replay in CLI + pytest, with JUnit + GitHub output |
| 4 | Full multi-agent system | Planner supervisor, specialist Attackers, P1–P7 library, Judge, Progress Scorer, adaptive strategies, streaming/Studio |
| 5 | Adapters & fakes | raw function-calling, OpenAI Agents SDK, HTTP adapters; full fake-result chain |
| 6 | Hardening | MIT-licensed seed datasets, xdist/pytest-asyncio compatibility, security self-review, OTel observability |
| 7 | Launch (v1.0) | docs, examples, positioning, Trusted Publishing release on PyPI |
| 8 | Phase-2 backlog | attacker handoffs, attack memory, checkpoint replay, RemoteGraph, HTML report, GitHub Action |

---

## Phase 1 — Foundations
**Outcome:** `uv sync && uv run pytest` green; `toolbreach --help` works; a config loads and validates; a Run without Authorization is refused; the Interceptor records and can short-circuit tool calls; the Budget enforces caps. No LangGraph used yet.
**Depends on:** none

- **P1.T1 — Packaging scaffold.** uv project, hatchling backend, `src/` layout, `requires-python=">=3.11"`, core deps + extras, CLI + pytest11 entry points, Apache-2.0 LICENSE/NOTICE, ruff + pyright. *Done when* `uv sync --all-extras` and `uv build` succeed. (Q10, Q17; RESEARCH §04)
- **P1.T2 — Domain models.** Frozen models named per GLOSSARY: ToolCall, Decision, Objective, Breach (objective|policy), Finding, RegressionCase, Trial. No LangChain imports. *Done when* JSON round-trips and an import-boundary test passes. (Q6/Q12/Q13/C2; GLOSSARY)
- **P1.T3 — Config schema + loader.** pydantic schema for `toolbreach.yaml` (target, profile+policy, tools live/intercepted, budget, authorization, per-role models, explore/replay); validation rejects Judge==Attacker and missing mandatory caps. *Done when* a valid fixture loads and bad fixtures raise clear errors. (O2/O3, Q5/Q8/Q11/C4; RESEARCH §01)
- **P1.T4 — Authorization gate.** No Run starts without an accepted ownership declaration; it's copied into every report. *Done when* tests show refuse/accept/record. (Q5)
- **P1.T5 — Interceptor core + Event Log.** Async-first with sync twins; active Run bound via contextvars (no-op outside a Run); Decision resolution (Live executes, Intercepted returns a fake, injection can rewrite a result); append-only log with lock, monotonic seq, provider provenance, raw args. *Done when* tests cover each path incl. parallel ordering and no `asyncio.run` from sync paths. (RESEARCH §02; Q11/C6)
- **P1.T6 — Budget.** Reserve/settle under a lock; genai-prices table; unknown/local models = $0 but bounded by tokens/time; `split(n)`. *Done when* concurrent reservations can't overshoot and the time cap trips. (RESEARCH §04; Q5/C4)
- **P1.T7 — CLI skeleton.** Typer app (`run`, `review`, `cases list`, `init`); only `init` functional; exit codes 0/1/2/3. *Done when* `init` scaffolds config + case folders + gitignore, and an unauthorized `run` exits 2. (Q10; D1)
- **P1.T8 — Repo CI.** GitHub Actions: ruff + pyright + pytest on 3.11 & 3.14; import-boundary contract. *Done when* CI is green and a deliberate `import langgraph` in `core/` fails it. (ADR 0003; D6)

**Checkpoint:** `uv run pytest` green; `toolbreach run --mode explore` without Authorization exits 2.

---

## Phase 2 — Tracer bullet
**Outcome:** `toolbreach run --mode explore` against the demo agent instruments its tools, has one Attacker plant an indirect-injection payload in a tool's output, detects the resulting intercepted side-effecting call as an **Objective Breach**, and writes `report.json` + a transcript. Minimal: one pattern (P1), a hard-coded Objective, a linear graph.
**Depends on:** Phase 1

- **P2.T1 — Demo vulnerable target** (LangGraph support bot; env flag hardens it; accepts a scripted fake model). (D7; Q3)
- **P2.T2 — LangGraph target adapter** (`middleware()` one-liner + `ToolNode` wrapper + `instrument_tools` fallback; fakes returned as `ToolMessage` with correct id; handle `Command` returns and sync-under-async). (RESEARCH §02; Q24)
- **P2.T3 — Harness model layer** (`init_chat_model` per role; usage callback feeds Budget; injectable model for tests). (Q20/C4; D3/D6)
- **P2.T4 — ToolCallCheck + Check framework** (safe arg-predicate DSL, no `eval`; tool-arg content → Objective Breach). (Q7/C2; RESEARCH §03 P1)
- **P2.T5 — Harness graph v0** (linear: planner_stub → `Send` → injector subgraph loop → report; sorted-breaches reducer). (ADR 0003; Q25-A minimal)
- **P2.T6 — Fake chain v0** (fixture → static default; provider recorded). (O6; RESEARCH §02)
- **P2.T7 — report.json + transcripts** (schema-versioned; JSONL transcripts in seq order; shipped JSON Schema). (O1; RESEARCH §04)
- **P2.T8 — Wire `run --mode explore`** (load config → authorize → build Budget → adapter → graph → report → console summary). (Q9/Q10)

**Checkpoint:** against the vulnerable demo, the newest `report.json` shows 1 Objective Breach; with the demo hardened, 0.

---

## Phase 3 — Regression lifecycle
**Outcome:** Explore groups Breaches into Findings and writes Pending Cases; the graph pauses at a Review `interrupt()` to accept/reject; accepted cases move into the committed suite; `run --mode replay` and `pytest` replay them (N=3 Trials, any Breach fails) emitting JUnit + GitHub summary; hardening the demo turns Replay green.
**Depends on:** Phase 2

- **P3.T1 — Finding grouping** (deterministic, keyed on objective/pattern/vector/check; Objective outranks Policy; stable hashed id). (Q15/Q6)
- **P3.T2 — Finding summary** (one LLM call per Finding; skipped in Replay; `--no-summary`). (Q15)
- **P3.T3 — Case store + Pending Case writer** (serialize best Breach to a frozen case YAML per D2; accept/reject moves files). (Q12/Q16; D1/D2; RESEARCH §01)
- **P3.T4 — Review as `interrupt()`** (one interrupt per Pending Case; in-process render + `Command(resume=…)`; `toolbreach review ID` resumes from SqliteSaver; `--no-review`). (Q16/Q25-C; D5)
- **P3.T5 — Frozen Replay runner** (N Trials, verbatim replay + recorded payloads, case Checks, no harness LLMs; `not_triggered` surfaced as a warning). (Q12/Q13; ADR 0002; RESEARCH §03)
- **P3.T6 — `run --mode replay`** (select by case/tag; per-case Trial outcomes; exit codes; budget stop = error). (Q9/Q13; RESEARCH §04)
- **P3.T7 — pytest plugin** (`pytest_collect_file` → one item per case; fresh-loop-in-thread if a loop is running; transcript in `repr_failure`; markers per tag; `--toolbreach-trials/-config`). (Q10; RESEARCH §04)
- **P3.T8 — JUnit + GitHub output** (`--junit` from report.json; step summary under 1 MiB + `::error` annotations when `GITHUB_ACTIONS=true`). (O1; RESEARCH §04)
- **P3.T9 — Example CI workflow** (Replay on PR, Explore on schedule, Pending Cases + transcripts uploaded). (ADR 0002; Q2/Q9)

**Checkpoint:** accept a Finding during Explore; Replay exits 1; pytest fails one item and writes JUnit; hardened Replay exits 0.

---

## Phase 4 — Full multi-agent system
**Outcome:** Explore runs the real harness — Planner supervisor derives Objectives from Policy + tool schemas via the P1–P7 pattern library and routes each to a specialist Attacker; adaptive specialists use the strategies in RESEARCH §03 steered by the Progress Scorer; the Judge decides fuzzy Policy Breaches; Adaptive Cases can be saved/replayed; progress streams to the CLI and opens in LangGraph Studio.
**Depends on:** Phase 3

- **P4.T1 — Attack Pattern library P1–P7** (one YAML each: id, technique-level description per D8, vector, specialist, Check templates, frozen/adaptive suitability, OWASP 2025 + Agentic 2026 + ATLAS tags pinned per RESEARCH §03). (Q14/O4)
- **P4.T2 — Remaining deterministic Checks** (tool-arg predicate, tool-sequence, canary with encoding variants on both channels per C2, PII-regex, keyword). (RESEARCH §03; Q7/C2; D8)
- **P4.T3 — Planner supervisor** (derive Objectives from profile + schemas + library; split Budget; route via `Command`/`Send`; user add/pin/exclude). (Q14/Q25-A)
- **P4.T4 — Four specialist Attackers** (one subgraph per specialty from GLOSSARY; focused prompts). (Q25-A)
- **P4.T5 — Judge** (different model from Attackers, enforced by config; only when no Check decides). (Q7/Q8)
- **P4.T6 — Progress Scorer** (rates each turn to steer adaptive loops; never decides a Breach, keeping Q7 intact). (Q25-E/C3)
- **P4.T7 — Adaptive strategies** (implement the RESEARCH §03 strategy order behind per-strategy budgets; deterministic Check results fed back as reward where available). (RESEARCH §03)
- **P4.T8 — Adaptive Cases** (store Objective + winning strategy; Replay retries on a small Budget). (Q12)
- **P4.T9 — Streaming + Studio** (`stream_mode` events to the CLI; ship `langgraph.json`; LangSmith tracing opt-in via env var only). (Q25-F/Q23)

**Checkpoint:** Explore on the demo produces Findings across ≥3 patterns via ≥2 specialists; Studio opens the graph; tracing stays off unless the env var is set.

---

## Phase 5 — Adapters & fakes
**Outcome:** targets beyond LangGraph work; the fake-result chain is complete.
**Depends on:** Phase 2 (core), Phase 4 (patterns to exercise)

- **P5.T1 — Raw function-calling adapter** (`instrument(dict)` + `@tool(kind=…)` keeping signatures via `functools.wraps`; works under Anthropic `@beta_tool`). (Q24; RESEARCH §02)
- **P5.T2 — OpenAI Agents SDK adapter** (`instrument_agent`: clone + replace `on_invoke_tool` across handoffs/agent-as-tool; warn loudly on hosted/MCP/computer tools). (Q24/C5; RESEARCH §02)
- **P5.T3 — HTTP endpoint adapter** (target = URL; chat-level attacks only, no tool channel per ADR 0001). (Q24)
- **P5.T4 — Adapter contract tests** (shared suite every adapter passes). (RESEARCH §02 risks)
- **P5.T5 — Full fake chain** (fixture → polyfactory typed-return synthesis (seeded) → static default; LLM fake opt-in, cached per seed). (O6; RESEARCH §02)

**Checkpoint:** the same Objective breaches a raw-loop target and an Agents-SDK target; the HTTP adapter runs chat-level attacks and reports no tool-channel attempts.

---

## Phase 6 — Hardening
**Outcome:** robust, observable, and safe to run widely.
**Depends on:** Phase 4

- **P6.T1 — Seed datasets** (import MIT-licensed sets from RESEARCH §03 as optional `[datasets]` extra; license check per dataset; none bundled in core).
- **P6.T2 — Canary robustness** (normalized/encoded variants wired into CanaryCheck; false-negative tests). (RESEARCH §03)
- **P6.T3 — xdist + pytest-asyncio compatibility** (per-worker Budget; fresh-loop handling verified). (RESEARCH §04 risks)
- **P6.T4 — OTel `gen_ai.*` spans** from Instrumented Tools (interop with other tracers). (RESEARCH §01)
- **P6.T5 — Security self-review** (run the `security-review` / threat-model skills over the harness; supply-chain: Trusted Publishing, pinned upper bounds, minimal transitive deps). (RESEARCH §04 risks)
- **P6.T6 — Budget/cancellation stress tests** (overshoot, timeout, clean partial reports).

**Checkpoint:** a parallel (`-n auto`) pytest run stays within Budget; spans appear; the security review has no open highs.

---

## Phase 7 — Launch (v1.0)
**Outcome:** a documented, installable v1.0 on PyPI.
**Depends on:** Phases 1–6

- **P7.T1 — README + positioning** (the narrowed wedge from DISCOVERY C1: own the tool channel + reviewed repo-versioned cases; local-first contrast).
- **P7.T2 — Docs** (quickstart, config reference, writing Attack Patterns, CI integration, the hosted-tool limitation).
- **P7.T3 — Examples** (the demo agent + a second framework example).
- **P7.T4 — Authorization & responsible-use doc** (restate Q5; dual-use posture D8).
- **P7.T5 — Release pipeline** (PyPI Trusted Publishing, hatch-vcs version, changelog).
- **P7.T6 — v1.0 tag + publish**, name confirmed free at release time (re-check `toolbreach` on PyPI).

**Checkpoint:** `pip install toolbreach` from PyPI, then the quickstart runs end-to-end against the demo.

---

## Phase 8 — Phase-2 backlog (v1.x)
Not scheduled; each is a self-contained follow-up. Attacker **handoffs** (Q25-B, `Command(goto,update)`); **attack memory** across Runs via LangGraph `Store` (Q25-D); **checkpoint replay** for LangGraph targets (Q22); **RemoteGraph** targets, chat-level only (Q21); **HTML report** from report.json (O1); **GitHub Action** wrapper (Q17); PR-based case proposals (Q16-c); additional adapters (CrewAI, Pydantic-AI, AutoGen, MCP) and a TypeScript SDK (Q24).

---

## Next step

The `prd` skill turns this plan plus DISCOVERY/RESEARCH into a PRD. The PRD, ARCHITECTURE, THREAT-MODEL and AGENTS steps may append tasks here; task IDs are never renumbered.
