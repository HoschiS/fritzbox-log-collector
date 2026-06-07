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


def _parse_box(raw: dict[str, object], index: int) -> BoxConfig:
    for key in ("name", "host", "user", "password"):
        if key not in raw:
            raise ConfigError(f"boxes[{index}] missing required field '{key}'")
    return BoxConfig(
        name=raw["name"],
        host=raw["host"],
        user=raw["user"],
        password=raw["password"],
    )


def _parse_output(raw: dict[str, object]) -> OutputConfig:
    if "sqlite_path" not in raw:
        raise ConfigError("output.sqlite_path is required")
    return OutputConfig(
        sqlite_path=raw["sqlite_path"],
        stdout_json=raw.get("stdout_json", False),
        prometheus_port=raw.get("prometheus_port", 0),
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

    return Config(boxes=boxes, output=output, poll_interval_seconds=poll_interval)
