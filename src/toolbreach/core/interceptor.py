import contextvars
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from typing import Any

from toolbreach.core.event_log import EventLog
from toolbreach.core.models import Decision, DecisionKind, ToolCall


def _default_fake_result(call: ToolCall) -> tuple[Any, str]:
    return {"status": "ok"}, "placeholder_result"


_active_interceptor: contextvars.ContextVar["Interceptor | None"] = contextvars.ContextVar(
    "toolbreach_active_interceptor", default=None
)


class Interceptor:
    def __init__(
        self,
        live_tools: frozenset[str] = frozenset(),
        make_fake: Callable[[ToolCall], tuple[Any, str]] = _default_fake_result,
        result_rewriter: Callable[[ToolCall, Any], tuple[Any, str] | None] | None = None,
        event_log: EventLog | None = None,
    ) -> None:
        self.live_tools = live_tools
        self._make_fake = make_fake
        self._result_rewriter = result_rewriter
        self.event_log = event_log or EventLog()

    def _make_decision(self, call: ToolCall) -> Decision:
        if call.tool_name in self.live_tools:
            return Decision(kind=DecisionKind.LIVE)
        result, source = self._make_fake(call)
        return Decision(kind=DecisionKind.INTERCEPTED, result=result, source=source)

    def _apply_and_record(self, call: ToolCall, decision: Decision, result: Any) -> Any:
        if self._result_rewriter is not None:
            result_rewrite = self._result_rewriter(call, result)
            if result_rewrite is not None:
                new_result, source = result_rewrite
                decision = Decision(kind=DecisionKind.INJECTED, result=new_result, source=source)
                result = new_result
        self.event_log.append(call, decision, result)
        return result

    # For sync tools e.g read_file
    def handle_tool_call(self, call: ToolCall, execute: Callable[[], Any]) -> Any:
        decision = self._make_decision(call)
        result = execute() if decision.kind is DecisionKind.LIVE else decision.result
        return self._apply_and_record(call, decision, result)

    # For async tools: anything bound to internet response
    async def ahandle_tool_call(self, call: ToolCall, execute: Callable[[], Awaitable[Any]]) -> Any:
        decision = self._make_decision(call)
        result = await execute() if decision.kind is DecisionKind.LIVE else decision.result
        return self._apply_and_record(call, decision, result)


@contextmanager
def bind(interceptor: Interceptor):
    reset_token = _active_interceptor.set(interceptor)
    try:
        yield interceptor
    finally:
        _active_interceptor.reset(reset_token)


def active_interceptor() -> "Interceptor | None":
    return _active_interceptor.get()


# Adapter front doors: no Run bound -> run the real tool (no-op in production).
def call_tool(call: ToolCall, execute: Callable[[], Any]) -> Any:
    active = _active_interceptor.get()
    return execute() if active is None else active.handle_tool_call(call, execute)


async def acall_tool(call: ToolCall, execute: Callable[[], Awaitable[Any]]) -> Any:
    active = _active_interceptor.get()
    if active is None:
        return await execute()
    return await active.ahandle_tool_call(call, execute)
