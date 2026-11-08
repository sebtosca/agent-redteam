"""Tests for the config schema + loader (P1.T3).

The two validations that are the point of T3: Judge != Attacker (Q8) and
mandatory budget caps (C4). Plus the loader's own error handling.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from toolbreach.config import Config, ToolMode, load_config

FIXTURES = Path(__file__).parent / "fixtures" / "config"


def _valid_data() -> dict:
    """The valid fixture as a plain dict, for tests that mutate one field."""
    return yaml.safe_load((FIXTURES / "valid.yaml").read_text(encoding="utf-8"))


# --- the happy path -------------------------------------------------------

def test_valid_config_loads() -> None:
    cfg = load_config(FIXTURES / "valid.yaml")
    assert isinstance(cfg, Config)
    assert cfg.authorization.owner_declaration.startswith("I own")
    assert cfg.budget.max_tokens == 200000
    assert cfg.budget.max_usd == 5.0
    assert cfg.replay.trials == 3
    assert cfg.models.judge != cfg.models.attacker


def test_tool_mode_defaults_to_intercepted() -> None:
    cfg = load_config(FIXTURES / "valid.yaml")
    by_name = {t.name: t.mode for t in cfg.target.tools}
    assert by_name["search_kb"] is ToolMode.LIVE
    assert by_name["send_email"] is ToolMode.INTERCEPTED
    assert by_name["lookup_customer"] is ToolMode.INTERCEPTED  # no mode in yaml -> safe default


def test_empty_tools_is_valid_chat_endpoint() -> None:
    data = _valid_data()
    data["target"]["tools"] = []
    cfg = Config.model_validate(data)
    assert cfg.target.tools == ()


def test_replay_defaults_when_section_absent() -> None:
    data = _valid_data()
    del data["replay"]
    cfg = Config.model_validate(data)
    assert cfg.replay.trials == 3


# --- the two required validations -----------------------------------------

def test_judge_equal_to_attacker_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Judge cannot be an Attacker"):
        load_config(FIXTURES / "judge_equals_attacker.yaml")


def test_missing_time_cap_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        load_config(FIXTURES / "missing_time_cap.yaml")
    assert "max_seconds" in str(exc.value)


def test_missing_token_cap_is_rejected() -> None:
    data = _valid_data()
    del data["budget"]["max_tokens"]
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(data)
    assert "max_tokens" in str(exc.value)


def test_money_cap_is_optional() -> None:
    data = _valid_data()
    del data["budget"]["max_usd"]
    cfg = Config.model_validate(data)
    assert cfg.budget.max_usd is None


# --- loader + schema error handling ---------------------------------------

def test_missing_file_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_config(FIXTURES / "does_not_exist.yaml")


def test_empty_file_raises_clear_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_config(empty)


def test_extra_top_level_key_is_rejected() -> None:
    data = _valid_data()
    data["unexpected"] = True
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_invalid_tool_mode_is_rejected() -> None:
    data = _valid_data()
    data["target"]["tools"][0]["mode"] = "bogus"
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_empty_owner_declaration_is_rejected() -> None:
    data = _valid_data()
    data["authorization"]["owner_declaration"] = ""
    with pytest.raises(ValidationError):
        Config.model_validate(data)
