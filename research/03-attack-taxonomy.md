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
