from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import Field, StrictBool, field_validator

from toolbreach.core.models import Frozen


class Authorization(Frozen):
    accepted: StrictBool
    owner_declaration: str = Field(min_length=1)

    @field_validator("owner_declaration", mode="before")
    @classmethod
    def _reject_blank(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("owner_declaration must not be blank")
        return value


class AuthorizationError(Exception):
    """Raised when a Run is attempted without an accepted Authorization."""


class AuthorizationRecord(Frozen):
    owner_declaration: str = Field(min_length=1)
    accepted_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


def require_authorization(
    auth: Authorization,
    now: Callable[[], datetime] = _utc_now,
) -> AuthorizationRecord:
    if auth.accepted is not True:
        raise AuthorizationError("Authorization must be accepted (accepted: true)")
    return AuthorizationRecord(
        owner_declaration=auth.owner_declaration,
        accepted_at=now(),
    )
