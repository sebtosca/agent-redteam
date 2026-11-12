
from concurrent.futures import ThreadPoolExecutor

import pytest

from toolbreach.core.budget import Budget, BudgetExceeded


def _budget(max_tokens=1000, max_seconds=10.0, max_usd=None, clock=None):
    now = (lambda: clock["t"]) if clock is not None else None
    kwargs = {"max_tokens": max_tokens, "max_seconds": max_seconds, "max_usd": max_usd}
    if now is not None:
        kwargs["now"] = now
    return Budget(**kwargs)


# --- reserve / settle accounting ------------------------------------------

def test_reserve_then_settle_updates_spent() -> None:
    b = _budget()
    r = b.reserve(100, 0.0)
    assert b._reserved_tokens == 100

    b.settle(r, 80, 0.0)
    assert b._spent_tokens == 80
    assert b._reserved_tokens == 0


def test_settle_frees_capacity_for_a_later_reserve() -> None:
    b = _budget(max_tokens=100)
    r = b.reserve(100)          # reserves the whole cap
    b.settle(r, 10)             # but only 10 were actually used

    # 90 capacity is free again, so this fits:
    b.reserve(90)
    assert b._spent_tokens + b._reserved_tokens == 100


# --- caps trip with the right reason --------------------------------------

def test_token_cap_blocks_over_reservation() -> None:
    b = _budget(max_tokens=100)
    with pytest.raises(BudgetExceeded) as exc:
        b.reserve(101)
    assert exc.value.reason == "tokens"


def test_usd_cap_blocks_when_set() -> None:
    b = _budget(max_usd=1.0)
    with pytest.raises(BudgetExceeded) as exc:
        b.reserve(10, est_usd=2.0)
    assert exc.value.reason == "usd"


def test_no_money_cap_means_usd_never_trips() -> None:
    b = _budget(max_usd=None)
    # a huge dollar estimate is fine; only tokens/time bound the Run
    b.reserve(10, est_usd=1_000_000.0)
    assert b._reserved_usd == 1_000_000.0


def test_time_cap_trips_on_check_and_reserve() -> None:
    clock = {"t": 0.0}
    b = _budget(max_seconds=10.0, clock=clock)

    clock["t"] = 11.0  # past the deadline
    with pytest.raises(BudgetExceeded) as exc:
        b.check()
    assert exc.value.reason == "time"

    with pytest.raises(BudgetExceeded) as exc:
        b.reserve(1)
    assert exc.value.reason == "time"


# --- concurrency: the core "done when" ------------------------------------

def test_concurrent_reservations_cannot_overshoot() -> None:
    # cap 1000, each worker reserves 100 -> at most 10 can succeed.
    b = _budget(max_tokens=1000)

    def try_reserve(_: int) -> bool:
        try:
            b.reserve(100)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=16) as pool:
        granted = list(pool.map(try_reserve, range(50)))

    assert sum(granted) == 10                    # exactly cap / slice
    assert b._reserved_tokens == 1000            # never overshot
    assert b._reserved_tokens <= b.max_tokens


# --- split -----------------------------------------------------------------

def test_split_divides_remaining_capacity() -> None:
    b = _budget(max_tokens=1000)
    b.reserve(200)  # 800 remaining

    children = b.split(4)
    assert len(children) == 4
    assert all(c.max_tokens == 200 for c in children)      # 800 / 4
    assert sum(c.max_tokens for c in children) <= 800
