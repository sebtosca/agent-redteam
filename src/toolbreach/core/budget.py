import threading
import time
from collections.abc import Callable

from pydantic import Field

from toolbreach.core.models import Frozen


class BudgetExceeded(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"budget exceeded: {reason}")


class Reservation(Frozen):
    est_tokens: int = Field(ge=0, description="Estimated tokens")
    est_usd: float = Field(ge=0.0, description="Estimated USD")


class Budget:
    def __init__(
        self,
        max_tokens: int,
        max_seconds: float,
        max_usd: float | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_tokens = max_tokens
        self.max_seconds = max_seconds
        self.max_usd = max_usd
        self._now = now
        self._deadline = now() + max_seconds
        self._lock = threading.Lock()
        self._spent_tokens = 0
        self._reserved_tokens = 0
        self._spent_usd = 0.0
        self._reserved_usd = 0.0

    def check(self) -> None:
        if self._now() >= self._deadline:
            raise BudgetExceeded("time")

    def reserve(self, est_tokens: int, est_usd: float = 0.0) -> Reservation:
        with self._lock:
            if self._now() >= self._deadline:
                raise BudgetExceeded("time")
            if self._spent_tokens + self._reserved_tokens + est_tokens > self.max_tokens:
                raise BudgetExceeded("tokens")
            if (
                self.max_usd is not None
                and self._spent_usd + self._reserved_usd + est_usd > self.max_usd
            ):
                raise BudgetExceeded("usd")
            self._reserved_tokens += est_tokens
            self._reserved_usd += est_usd
            return Reservation(est_tokens=est_tokens, est_usd=est_usd)

    def settle(self, reservation: Reservation, actual_tokens: int, actual_usd: float = 0.0) -> None:
        with self._lock:
            self._reserved_tokens -= reservation.est_tokens
            self._reserved_usd -= reservation.est_usd
            self._spent_tokens += actual_tokens
            self._spent_usd += actual_usd

    def split(self, n: int) -> list["Budget"]:
        if n < 1:
            raise ValueError("n must be at least 1")
        with self._lock:
            remaining_tokens = self.max_tokens - self._spent_tokens - self._reserved_tokens
            remaining_seconds = self._deadline - self._now()
            remaining_usd = None
            if self.max_usd is not None:
                remaining_usd = self.max_usd - self._spent_usd - self._reserved_usd
        return [
            Budget(
                max_tokens=remaining_tokens // n,
                max_seconds=remaining_seconds,
                max_usd=None if remaining_usd is None else remaining_usd / n,
                now=self._now,
            )
            for _ in range(n)
        ]
