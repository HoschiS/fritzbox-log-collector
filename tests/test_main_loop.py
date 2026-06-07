"""Integration tests for the poll loop logic in __main__.py."""
import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry

from fritzlog.__main__ import poll_all_boxes
from fritzlog.config import BoxConfig, Config, OutputConfig
from fritzlog.output import Metrics
from fritzlog.store import Store


@pytest.fixture
def store() -> Store:
    return Store(":memory:")


@pytest.fixture
def metrics() -> Metrics:
    return Metrics(registry=CollectorRegistry())


def _make_config(boxes: list[BoxConfig], stdout_json: bool = False) -> Config:
    return Config(
        boxes=boxes,
        output=OutputConfig(sqlite_path=":memory:", stdout_json=stdout_json),
    )


def _mock_poll(entries: list[tuple[datetime, str]]) -> MagicMock:
    m = MagicMock(return_value=entries)
    return m


def test_new_entries_are_stored(store: Store, metrics: Metrics) -> None:
    box = BoxConfig(name="HWR", host="192.168.178.1", user="u", password="p")
    cfg = _make_config([box])
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)
    entries = [(datetime(2026, 6, 7, 10, 0, 0), "Meldung A")]

    with patch("fritzlog.__main__.poll", return_value=entries):
        poll_all_boxes(cfg, store, metrics, now=collected)

    with store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    assert count == 1


def test_duplicate_entries_not_stored_twice(store: Store, metrics: Metrics) -> None:
    box = BoxConfig(name="HWR", host="192.168.178.1", user="u", password="p")
    cfg = _make_config([box])
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)
    entries = [(datetime(2026, 6, 7, 10, 0, 0), "Meldung A")]

    with patch("fritzlog.__main__.poll", return_value=entries):
        poll_all_boxes(cfg, store, metrics, now=collected)
        poll_all_boxes(cfg, store, metrics, now=collected)

    with store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    assert count == 1


def test_poll_failure_logs_warning_and_continues(
    store: Store, metrics: Metrics, caplog: pytest.LogCaptureFixture
) -> None:
    box_ok = BoxConfig(name="HWR", host="192.168.178.1", user="u", password="p")
    box_fail = BoxConfig(name="Offline", host="192.168.178.99", user="u", password="p")
    cfg = _make_config([box_fail, box_ok])
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)

    def side_effect(box: BoxConfig) -> list[tuple[datetime, str]]:
        if box.name == "Offline":
            raise ConnectionError("unreachable")
        return [(datetime(2026, 6, 7, 10, 0, 0), "OK")]

    with caplog.at_level(logging.WARNING):
        with patch("fritzlog.__main__.poll", side_effect=side_effect):
            poll_all_boxes(cfg, store, metrics, now=collected)

    assert any("Offline" in r.message for r in caplog.records)

    with store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    assert count == 1
