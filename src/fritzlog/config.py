from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


@dataclass
class BoxConfig:
    name: str
    host: str
    user: str
    password: str


@dataclass
class OutputConfig:
    sqlite_path: str
    stdout_json: bool = False
    prometheus_port: int = 0


@dataclass
class Config:
    boxes: list[BoxConfig]
    output: OutputConfig
    poll_interval_seconds: int = 300


def _require_str(mapping: dict[str, object], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{context} must be a non-empty string")
    return value


def _parse_box(raw: dict[str, object], index: int) -> BoxConfig:
    ctx = f"boxes[{index}]"
    for key in ("name", "host", "user", "password"):
        if key not in raw:
            raise ConfigError(f"{ctx} missing required field '{key}'")
    return BoxConfig(
        name=_require_str(raw, "name", f"{ctx}.name"),
        host=_require_str(raw, "host", f"{ctx}.host"),
        user=_require_str(raw, "user", f"{ctx}.user"),
        password=_require_str(raw, "password", f"{ctx}.password"),
    )


def _parse_output(raw: dict[str, object]) -> OutputConfig:
    sqlite_path = _require_str(raw, "sqlite_path", "output.sqlite_path")
    stdout_json = raw.get("stdout_json", False)
    if not isinstance(stdout_json, bool):
        raise ConfigError("output.stdout_json must be a boolean")
    prometheus_port = raw.get("prometheus_port", 0)
    if not isinstance(prometheus_port, int):
        raise ConfigError("output.prometheus_port must be an integer")
    return OutputConfig(
        sqlite_path=sqlite_path,
        stdout_json=stdout_json,
        prometheus_port=prometheus_port,
    )


def load_config(path: str | Path) -> Config:
    try:
        text = Path(path).read_text()
    except OSError as exc:
        raise ConfigError(f"Cannot read config file: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping")

    if "boxes" not in raw or not raw["boxes"]:
        raise ConfigError("At least one box must be configured under 'boxes'")
    if "output" not in raw:
        raise ConfigError("'output' section is required")

    boxes = [_parse_box(b, i) for i, b in enumerate(raw["boxes"])]
    output = _parse_output(raw["output"])
    poll_interval = raw.get("poll_interval_seconds", 300)
    if not isinstance(poll_interval, int):
        raise ConfigError("poll_interval_seconds must be an integer")

    return Config(boxes=boxes, output=output, poll_interval_seconds=poll_interval)
