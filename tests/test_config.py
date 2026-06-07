import textwrap
from pathlib import Path

import pytest

from fritzlog.config import Config, ConfigError, load_config


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_load_minimal_config(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        boxes:
          - name: HWR
            host: 192.168.178.1
            user: syslog-user
            password: secret

        output:
          sqlite_path: /data/fritzlog.db
        """,
    )

    cfg = load_config(cfg_file)

    assert isinstance(cfg, Config)
    assert len(cfg.boxes) == 1
    assert cfg.boxes[0].name == "HWR"
    assert cfg.boxes[0].host == "192.168.178.1"
    assert cfg.boxes[0].user == "syslog-user"
    assert cfg.boxes[0].password == "secret"
    assert cfg.output.sqlite_path == "/data/fritzlog.db"


def test_defaults_applied(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        boxes:
          - name: HWR
            host: 192.168.178.1
            user: syslog-user
            password: secret

        output:
          sqlite_path: /data/fritzlog.db
        """,
    )

    cfg = load_config(cfg_file)

    assert cfg.poll_interval_seconds == 300
    assert cfg.output.stdout_json is False
    assert cfg.output.prometheus_port == 0


def test_multiple_boxes_and_all_options(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        poll_interval_seconds: 60

        boxes:
          - name: HWR
            host: 192.168.178.1
            user: syslog-user
            password: secret1
          - name: Arbeitszimmer
            host: 192.168.178.60
            user: syslog-user
            password: secret2

        output:
          sqlite_path: /data/fritzlog.db
          stdout_json: true
          prometheus_port: 9877
        """,
    )

    cfg = load_config(cfg_file)

    assert cfg.poll_interval_seconds == 60
    assert len(cfg.boxes) == 2
    assert cfg.boxes[1].name == "Arbeitszimmer"
    assert cfg.boxes[1].host == "192.168.178.60"
    assert cfg.output.stdout_json is True
    assert cfg.output.prometheus_port == 9877


def test_missing_boxes_raises(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        output:
          sqlite_path: /data/fritzlog.db
        """,
    )
    with pytest.raises(ConfigError, match="boxes"):
        load_config(cfg_file)


def test_missing_sqlite_path_raises(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        boxes:
          - name: HWR
            host: 192.168.178.1
            user: syslog-user
            password: secret
        output: {}
        """,
    )
    with pytest.raises(ConfigError, match="sqlite_path"):
        load_config(cfg_file)


def test_missing_box_field_raises(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        boxes:
          - name: HWR
            host: 192.168.178.1
            user: syslog-user
        output:
          sqlite_path: /data/fritzlog.db
        """,
    )
    with pytest.raises(ConfigError, match="password"):
        load_config(cfg_file)


def test_file_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(tmp_path / "nonexistent.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("boxes: [unclosed")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(cfg_file)


def test_per_box_timeout_optional(tmp_path: Path) -> None:
    cfg_file = write_yaml(
        tmp_path,
        """
        boxes:
          - name: HWR
            host: 192.168.178.1
            user: syslog-user
            password: secret
          - name: Chrissi
            host: 192.168.178.17
            user: syslog-user
            password: secret
            timeout_seconds: 3
        output:
          sqlite_path: /data/fritzlog.db
        """,
    )

    cfg = load_config(cfg_file)

    assert cfg.boxes[0].timeout_seconds is None   # uses collector default
    assert cfg.boxes[1].timeout_seconds == 3
