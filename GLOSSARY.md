# toolbreach

An open-source tool that AI engineers run, mostly in CI, to attack their own LLM agents with cooperating attacker agents and turn every failure into a regression test.

## Language

### The thing under test

**Target**:
The LLM application being attacked: a tool-using agent, or a plain chat endpoint, which is treated as an agent with no tools.
_Avoid_: System under test, victim, app, bot

**Target Profile**:
What the harness has been told about a Target: its system prompt, its tool schemas and its Policy.
_Avoid_: Spec, manifest, recon report

**Policy**:
The Target owner's statement of what the Target must and must not do, and the standard every attack outcome is judged against.
_Avoid_: Rules, guardrails, safety spec

**Adapter**:
The thin layer that connects one kind of Target, such as a framework, a homemade loop or an HTTP endpoint, to the harness.
_Avoid_: Integration, connector, plugin, driver

**Instrumented Tool**:
A Target tool that the harness can observe and whose return values it can replace, which is how attacks arrive through untrusted tool output.
_Avoid_: Hooked tool, mocked tool, wrapped tool

**Intercepted Tool**:
An Instrumented Tool whose calls are recorded but never executed, and which returns a plausible fake result. This is the default for any tool with side effects.
_Avoid_: Mocked tool, stubbed tool, dry-run tool

**Live Tool**:
An Instrumented Tool that the user has marked safe to execute for real during attacks, usually because it is read-only.
_Avoid_: Real tool, passthrough tool

### Running

**Authorization**:
The user's explicit declaration that they own the Target or are permitted to test it. No Run starts without one.
_Avoid_: Consent, permission, license

**Run**:
One bounded execution of the harness against one Target.
_Avoid_: Scan, session, job, campaign

**Budget**:
The hard limit on what a Run may spend, after which it stops. A token cap and a time cap are always set; a money cap is optional.
_Avoid_: Quota, limit, cap

**Explore**:
The Run mode that searches for new Breaches. It's slow and nondeterministic, and it runs on a schedule or on demand.
_Avoid_: Scan, fuzz, discovery run

**Replay**:
The Run mode that re-executes saved Regression Cases to gate a change.
_Avoid_: Regression run, re-test, CI mode

### Agent roles

**Planner**:
The supervising role that turns a Target Profile into Objectives, splits the Budget across them, and routes each Objective to the right Specialist.
_Avoid_: Strategist, orchestrator, coordinator, supervisor

**Attacker**:
Any role that interacts with the Target to try to achieve an Objective. Every Attacker is a Specialist.
_Avoid_: Red agent, adversary, probe

**Specialist**:
An Attacker dedicated to one family of Attack Patterns: the Injector, the Social Engineer, the Extractor or the Tool Abuser.
_Avoid_: Sub-agent, worker, expert

**Injector**:
The Specialist that plants attacks in Intercepted Tool results.
_Avoid_: Poisoner, indirect attacker

**Social Engineer**:
The Specialist that pursues an Objective through multi-turn persuasion in the user channel.
_Avoid_: Jailbreaker, persona attacker

**Extractor**:
The Specialist that tries to make the Target reveal its system prompt, secrets or canaries.
_Avoid_: Leaker, prompt stealer

**Tool Abuser**:
The Specialist that tries to make the Target call tools with forbidden arguments or chain tools to gain privilege.
_Avoid_: Escalator, agency attacker

**Judge**:
The role that decides, using an LLM, whether an outcome violates the Policy when no Check can decide it.
_Avoid_: Grader, evaluator, scorer

**Progress Scorer**:
The role that rates how close an Attacker's latest turn came to its Objective, to steer the next attempt. It never decides whether a Breach happened.
_Avoid_: Reward model, critic, heuristic judge

**Review**:
The step where a human accepts or rejects each Pending Case at the end of Explore.
_Avoid_: Triage, approval, sign-off

### Outcomes

**Objective**:
One concrete thing an attack tries to make the Target do, such as calling a given tool with given arguments.
_Avoid_: Goal, attack goal, scenario

**Check**:
A deterministic test of an outcome, such as an assertion on an Instrumented Tool call or a leaked canary.
_Avoid_: Assertion, detector, rule

**Breach**:
A single observed instance of the Target failing under attack.
_Avoid_: Failure, hit, exploit, jailbreak

**Objective Breach**:
A Breach that shows up in the Target's outbound tool-call arguments: the Target took an action an Objective was aiming for. This is the most severe kind.
_Avoid_: Action breach, critical breach

**Policy Breach**:
A Breach that shows up only in the Target's own text: it said something the Policy forbids without taking a forbidden action.
_Avoid_: Content breach, soft breach

**Finding**:
A deduplicated group of Breaches that share one root cause, and the unit that gets reported.
_Avoid_: Issue, vulnerability, bug, alert

**Regression Case**:
A saved, re-runnable attack derived from a Finding, which Replay uses to confirm the Finding stays fixed.
_Avoid_: Test case, fixture, saved attack

**Frozen Case**:
A Regression Case that replays exactly the recorded Attacker messages and injected payloads. This is the default.
_Avoid_: Static case, scripted case

**Adaptive Case**:
A Regression Case that stores an Objective and the strategy that worked, and lets an Attacker try again on a small Budget.
_Avoid_: Dynamic case, live case

**Trial**:
One execution of a Regression Case during Replay. A case fails if any of its Trials produces a Breach.
_Avoid_: Attempt, iteration, sample

**Pending Case**:
A Regression Case that Explore has proposed but the user has not yet accepted into the suite.
_Avoid_: Candidate, draft, suggestion

**Attack Pattern**:
A reusable technique from the built-in library, such as a payload injected through a tool result, that the Planner uses to build Objectives for a specific Target.
_Avoid_: Template, recipe, technique, playbook
