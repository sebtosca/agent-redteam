import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from toolbreach.core.models import Decision, Frozen, ToolCall


def _utc_now() -> datetime:
    return datetime.now(UTC)

class Event(Frozen):
    run_id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    ts: datetime
    call: ToolCall
    decision: Decision
    result: Any

class EventLog:
    def __init__(self, run_id: str | None = None, now: Callable[[], datetime] = _utc_now) -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self._now = now
        self._events: list[Event] = []
        self._lock = threading.Lock()

    def append(self, call: ToolCall, decision: Decision, result: Any) -> Event:
        with self._lock: 
            event = Event(
                run_id=self.run_id,
                seq=len(self._events) + 1,
                ts=self._now(),
                call=call,
                decision=decision,
                result=result,
            )
            self._events.append(event)
            return event

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)
    


