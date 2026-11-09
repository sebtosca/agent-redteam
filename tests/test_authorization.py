"""Tests for the Authorization gate (P1.T4): refuse / accept / record."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from toolbreach.config import load_config
from toolbreach.core.authorization import (
    Authorization,
    AuthorizationError,
    AuthorizationRecord,
    require_authorization,
)

FIXTURES = Path(__file__).parent / "fixtures" / "config"
FIXED_NOW = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)


def _fake_now() -> datetime:
    return FIXED_NOW


def _auth(**overrides) -> Authorization:
    data = {"owner_declaration": "I own or am permitted to test this target.", "accepted": True}
    data.update(overrides)
    return Authorization(**data)


# --- refuse ---------------------------------------------------------------

def test_not_accepted_is_refused() -> None:
    with pytest.raises(AuthorizationError):
        require_authorization(_auth(accepted=False), now=_fake_now)


def test_missing_accepted_fails_validation() -> None:
    with pytest.raises(ValidationError):
        Authorization(owner_declaration="I own this target.")  # type: ignore[call-arg]


@pytest.mark.parametrize("value", ["yes", "true", 1])
def test_accepted_must_be_a_real_bool(value) -> None:
    with pytest.raises(ValidationError):
        _auth(accepted=value)


@pytest.mark.parametrize("value", ["", " ", "\n\t "])
def test_blank_declaration_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        _auth(owner_declaration=value)


# --- accept ---------------------------------------------------------------

def test_accepted_returns_record() -> None:
    record = require_authorization(_auth(), now=_fake_now)
    assert isinstance(record, AuthorizationRecord)


# --- record ---------------------------------------------------------------

def test_record_copies_declaration_and_timestamp() -> None:
    auth = _auth(owner_declaration="I own ACME's support agent.")
    record = require_authorization(auth, now=_fake_now)
    assert record.owner_declaration == "I own ACME's support agent."
    assert record.accepted_at == FIXED_NOW


def test_record_is_report_ready_json() -> None:
    record = require_authorization(_auth(), now=_fake_now)
    dumped = record.model_dump(mode="json")
    assert set(dumped) == {"owner_declaration", "accepted_at"}
    assert isinstance(dumped["accepted_at"], str)


def test_record_is_frozen() -> None:
    record = require_authorization(_auth(), now=_fake_now)
    with pytest.raises(ValidationError):
        record.owner_declaration = "tampered"  # type: ignore[misc]


def test_default_clock_is_timezone_aware_utc() -> None:
    record = require_authorization(_auth())
    assert record.accepted_at.tzinfo is not None
    assert record.accepted_at.utcoffset().total_seconds() == 0


# --- config integration ---------------------------------------------------

def test_valid_config_passes_the_gate() -> None:
    cfg = load_config(FIXTURES / "valid.yaml")
    record = require_authorization(cfg.authorization, now=_fake_now)
    assert record.owner_declaration == cfg.authorization.owner_declaration


def test_unaccepted_config_loads_but_gate_refuses() -> None:
    cfg = load_config(FIXTURES / "unaccepted.yaml")
    with pytest.raises(AuthorizationError):
        require_authorization(cfg.authorization, now=_fake_now)
