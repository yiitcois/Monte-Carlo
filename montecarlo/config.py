"""Configuration utilities for the simulator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore


class ConfigError(RuntimeError):
    """Raised when the configuration file cannot be processed."""


_DEFAULT_CONFIDENCE = [0.5, 0.75, 0.9]


def load_config(path: Path) -> Dict[str, Any]:
    """Load and validate a YAML configuration file."""
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    text = path.read_text(encoding="utf-8")
    data: Dict[str, Any]

    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is not None:
            data = yaml.safe_load(text)
        else:
            data = _parse_basic_yaml(text)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ConfigError("Unsupported configuration format. Use YAML or JSON.")

    if not isinstance(data, dict):
        raise ConfigError("Configuration must be a mapping of keys to values.")

    required = {"tasks"}
    missing = [key for key in required if key not in data]
    if missing:
        raise ConfigError(f"Missing required configuration keys: {', '.join(missing)}")

    data.setdefault("confidence_levels", _DEFAULT_CONFIDENCE.copy())
    return data


def _parse_basic_yaml(text: str) -> Dict[str, Any]:
    """Very small YAML parser that supports the subset used by our configs."""

    result: Dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ConfigError(f"Invalid line in configuration: {raw_line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        result[key] = _convert_scalar(value)
    return result


def _convert_scalar(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_convert_scalar(item.strip()) for item in inner.split(",")]

    lowered = value.lower()
    if lowered in {"null", "none"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


__all__ = ["load_config", "ConfigError"]
