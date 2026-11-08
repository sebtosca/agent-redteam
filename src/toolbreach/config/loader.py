from pathlib import Path

import yaml

from toolbreach.config.schema import Config


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"config not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config must be a YAML mapping, got {type(data).__name__}")
    return Config.model_validate(data)
