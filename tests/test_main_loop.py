"""Integration tests for the poll loop logic in __main__.py."""
import concurrent.futures
import logging
import threading
from datetime import UTC, datetime
from unittest.mock import patch

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


def test_successful_poll_logs_info(
    store: Store, metrics: Metrics, caplog: pytest.LogCaptureFixture
) -> None:
    box = BoxConfig(name="HWR", host="192.168.178.1", user="u", password="p")
    cfg = _make_config([box])
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)
    entries = [
        (datetime(2026, 6, 7, 10, 0, 0), "Meldung A"),
        (datetime(2026, 6, 7, 10, 1, 0), "Meldung B"),
    ]

    with caplog.at_level(logging.INFO):
        with patch("fritzlog.__main__.poll", return_value=entries):
            poll_all_boxes(cfg, store, metrics, now=collected)

    messages = " ".join(r.message for r in caplog.records)
    assert "HWR" in messages
    assert "2" in messages  # batch size or new count visible in log


def test_boxes_polled_concurrently(store: Store, metrics: Metrics) -> None:
    """A slow box must not block polling of other boxes."""
    box_a = BoxConfig(name="A", host="192.168.178.1", user="u", password="p")
    box_b = BoxConfig(name="B", host="192.168.178.2", user="u", password="p")
    cfg = _make_config([box_a, box_b])
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)

    b_polled = threading.Event()
    a_can_finish = threading.Event()

    def side_effect(box: BoxConfig) -> list[tuple[datetime, str]]:
        if box.name == "A":
            a_can_finish.wait(timeout=2)
            return []
        b_polled.set()
        return [(datetime(2026, 6, 7, 10, 0, 0), "entry from B")]

    with patch("fritzlog.__main__.poll", side_effect=side_effect):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(poll_all_boxes, cfg, store, metrics, now=collected)
            b_was_polled = b_polled.wait(timeout=1)
            a_can_finish.set()
            future.result()

    assert b_was_polled, "Box B was not polled while Box A was blocking — polls are not concurrent"

    with store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM logs WHERE box='B'").fetchone()[0]
    assert count == 1
