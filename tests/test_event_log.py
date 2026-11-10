from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from toolbreach.core.event_log import Event, EventLog
from toolbreach.core.models import Decision, DecisionKind, ToolCall

FIXED_TS = datetime(2026, 11, 10, tzinfo=UTC)
CALL = ToolCall(tool_name="send_email", tool_call_id="c1")
DECISION = Decision(kind=DecisionKind.LIVE)

def _event(**fields):
    data = dict(
        run_id="run1",
        seq=1,
        ts=FIXED_TS,
        call=CALL,
        decision=DECISION,
        result={"ok": True},
    )
    data.update(fields)
    return Event(**data)

def test_valid_event_build() -> None: 
    event = _event()
    assert event.seq == 1
    assert event.ts.tzinfo is not None
    assert event.decision.kind is DecisionKind.LIVE

def test_seq_under_1_rejected() -> None:
    with pytest.raises(ValidationError):
        _event(seq=0)

def test_append_assigns_incrementing_seq() -> None: 
    log = EventLog(run_id="r1", now=lambda: FIXED_TS)

    e1 = log.append(CALL, DECISION, None)
    e2 = log.append(CALL, DECISION, None)
    e3 = log.append(CALL, DECISION, None)

    assert (e1.seq, e2.seq, e3.seq) == (1, 2, 3)
    assert e1.ts == FIXED_TS


# every event carries the log's run_id (the report's correlation key)
def test_events_share_run_id() -> None:
    log = EventLog(run_id="r1")

    log.append(CALL, DECISION, None)
    log.append(CALL, DECISION, None)

    assert all(e.run_id == "r1" for e in log.events)


# log.events returns a snapshot copy; it can't be used to mutate the log
def test_events_is_a_copy() -> None:
    log = EventLog(run_id="r1")
    log.append(CALL, DECISION, None)

    snapshot = log.events
    assert isinstance(snapshot, tuple)

    log.append(CALL, DECISION, None)
    assert len(snapshot) == 1      # the earlier snapshot is unchanged
    assert len(log.events) == 2    # the log itself grew


# 50 concurrent appends -> seqs are exactly 1..50, unique (the lock works)
def test_parallel_appends_keep_unique_contiguous_seqs() -> None:
    log = EventLog(run_id="r1")

    def do_append(_: int) -> None:
        log.append(CALL, DECISION, None)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(do_append, range(50)))

    seqs = sorted(e.seq for e in log.events)
    assert seqs == list(range(1, 51))
