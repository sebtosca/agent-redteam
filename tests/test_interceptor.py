"""Tests for the Interceptor (P1.T5).

What's worth testing here is the Interceptor's own logic and its safety
guarantees, not pydantic or contextvars themselves:

  - LIVE runs the real tool; INTERCEPTED never does (the core safety property).
  - a result_rewriter can inject; returning None leaves the result alone.
  - call_tool is a no-op outside a Run, and delegates inside one.
  - bind restores the previous context.
  - the sync and async paths behave identically, and the sync path works even
    when called from inside a running event loop (i.e. no asyncio.run).
"""

from toolbreach.core.interceptor import (
    Interceptor,
    acall_tool,
    active_interceptor,
    bind,
    call_tool,
)
from toolbreach.core.models import DecisionKind, ToolCall

LIVE_CALL = ToolCall(tool_name="search_kb", tool_call_id="c1", arguments={"q": "orders"})
SIDE_EFFECT_CALL = ToolCall(tool_name="send_email", tool_call_id="c2", arguments={"to": "x"})
LIVE_TOOLS = frozenset({"search_kb"})


def _counting_execute(value):
    """A fake real tool: returns `value` and records how often it ran."""
    calls = {"n": 0}

    def execute():
        calls["n"] += 1
        return value

    return execute, calls


# --- LIVE vs INTERCEPTED: the core safety property ------------------------

def test_live_tool_executes_for_real() -> None:
    ic = Interceptor(live_tools=LIVE_TOOLS)
    execute, calls = _counting_execute("real result")

    result = ic.handle_tool_call(LIVE_CALL, execute)

    assert result == "real result"
    assert calls["n"] == 1
    assert ic.event_log.events[-1].decision.kind is DecisionKind.LIVE


def test_intercepted_tool_never_executes() -> None:
    # send_email is not in live_tools -> intercepted. The real tool must never run.
    ic = Interceptor(live_tools=LIVE_TOOLS)
    execute, calls = _counting_execute("SHOULD NOT HAPPEN")

    result = ic.handle_tool_call(SIDE_EFFECT_CALL, execute)

    assert calls["n"] == 0               # <- the guarantee: no real side effect
    assert result == {"status": "ok"}    # the fake came back instead
    decision = ic.event_log.events[-1].decision
    assert decision.kind is DecisionKind.INTERCEPTED
    assert decision.source == "placeholder_result"


# --- injection ------------------------------------------------------------

def test_result_rewriter_injects() -> None:
    ic = Interceptor(
        live_tools=LIVE_TOOLS,
        result_rewriter=lambda call, result: ("attacker payload", "P1"),
    )
    execute, _ = _counting_execute("ignored")

    result = ic.handle_tool_call(SIDE_EFFECT_CALL, execute)

    assert result == "attacker payload"
    decision = ic.event_log.events[-1].decision
    assert decision.kind is DecisionKind.INJECTED
    assert decision.source == "P1"


def test_result_rewriter_returning_none_leaves_result_untouched() -> None:
    ic = Interceptor(
        live_tools=LIVE_TOOLS,
        result_rewriter=lambda call, result: None,
    )
    execute, _ = _counting_execute("ignored")

    result = ic.handle_tool_call(SIDE_EFFECT_CALL, execute)

    assert result == {"status": "ok"}
    assert ic.event_log.events[-1].decision.kind is DecisionKind.INTERCEPTED


# --- the call_tool front door ---------------------------------------------

def test_call_tool_is_a_noop_without_a_run() -> None:
    # No interceptor bound: the real tool just runs, nothing is intercepted.
    execute, calls = _counting_execute("real result")

    assert active_interceptor() is None
    result = call_tool(SIDE_EFFECT_CALL, execute)

    assert result == "real result"
    assert calls["n"] == 1


def test_call_tool_delegates_to_the_bound_interceptor() -> None:
    ic = Interceptor(live_tools=LIVE_TOOLS)
    execute, calls = _counting_execute("SHOULD NOT HAPPEN")

    with bind(ic):
        result = call_tool(SIDE_EFFECT_CALL, execute)

    assert calls["n"] == 0               # intercepted via the bound interceptor
    assert result == {"status": "ok"}
    assert len(ic.event_log.events) == 1


def test_bind_restores_previous_context() -> None:
    assert active_interceptor() is None
    ic = Interceptor()

    with bind(ic):
        assert active_interceptor() is ic

    assert active_interceptor() is None  # reset on exit


# --- sync / async parity --------------------------------------------------

async def test_async_path_matches_sync() -> None:
    ic = Interceptor(live_tools=LIVE_TOOLS)

    async def aexecute():
        return "real result"

    live = await ic.ahandle_tool_call(LIVE_CALL, aexecute)
    intercepted = await ic.ahandle_tool_call(SIDE_EFFECT_CALL, aexecute)

    assert live == "real result"
    assert intercepted == {"status": "ok"}
    kinds = [e.decision.kind for e in ic.event_log.events]
    assert kinds == [DecisionKind.LIVE, DecisionKind.INTERCEPTED]


async def test_sync_call_works_inside_a_running_loop() -> None:
    # This test runs inside an event loop (asyncio_mode = auto). The sync path
    # must not start its own loop (no asyncio.run), or this would raise.
    ic = Interceptor(live_tools=LIVE_TOOLS)
    execute, calls = _counting_execute("real result")

    with bind(ic):
        result = call_tool(LIVE_CALL, execute)

    assert result == "real result"
    assert calls["n"] == 1


async def test_acall_tool_is_a_noop_without_a_run() -> None:
    async def aexecute():
        return "real result"

    assert active_interceptor() is None
    result = await acall_tool(SIDE_EFFECT_CALL, aexecute)

    assert result == "real result"
