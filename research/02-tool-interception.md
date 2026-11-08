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
