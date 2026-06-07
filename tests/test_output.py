import json
from datetime import datetime, timezone

from prometheus_client import CollectorRegistry, generate_latest

from fritzlog.output import format_entry_as_json, Metrics


def _metric_value(registry: CollectorRegistry, name: str, box: str) -> float:
    text = generate_latest(registry).decode()
    for line in text.splitlines():
        if line.startswith(f'{name}{{box="{box}"}}'):
            return float(line.split(" ")[1])
    raise KeyError(f"{name}{{box={box!r}}} not found in metrics output")


def test_format_entry_as_json_structure() -> None:
    ts = datetime(2026, 6, 7, 10, 23, 17)
    collected = datetime(2026, 6, 7, 10, 25, 1, tzinfo=timezone.utc)

    line = format_entry_as_json("HWR", ts, "Internetverbindung hergestellt.", collected)
    obj = json.loads(line)

    assert obj["box"] == "HWR"
    assert obj["timestamp"] == "2026-06-07T10:23:17"
    assert obj["message"] == "Internetverbindung hergestellt."
    assert obj["collected_at"] == "2026-06-07T10:25:01Z"


def test_metrics_record_successful_poll() -> None:
    reg = CollectorRegistry()
    metrics = Metrics(registry=reg)
    now = datetime(2026, 6, 7, 10, 25, 1, tzinfo=timezone.utc)

    metrics.record_poll_success("HWR", entries_added=3, timestamp=now)

    assert _metric_value(reg, "fritzlog_poll_success", "HWR") == 1.0
    assert _metric_value(reg, "fritzlog_entries_total", "HWR") == 3.0
    assert _metric_value(reg, "fritzlog_last_poll_timestamp", "HWR") == now.timestamp()
    assert _metric_value(reg, "fritzlog_buffer_gap_detected", "HWR") == 0.0


def test_metrics_record_failed_poll() -> None:
    reg = CollectorRegistry()
    metrics = Metrics(registry=reg)

    metrics.record_poll_failure("HWR")

    assert _metric_value(reg, "fritzlog_poll_success", "HWR") == 0.0


def test_metrics_record_gap_detected() -> None:
    reg = CollectorRegistry()
    metrics = Metrics(registry=reg)
    now = datetime(2026, 6, 7, 10, 25, 1, tzinfo=timezone.utc)

    metrics.record_poll_success("HWR", entries_added=0, timestamp=now, gap_detected=True)

    assert _metric_value(reg, "fritzlog_buffer_gap_detected", "HWR") == 1.0


def test_metrics_accumulate_entries_across_polls() -> None:
    reg = CollectorRegistry()
    metrics = Metrics(registry=reg)
    now = datetime(2026, 6, 7, 10, 25, 1, tzinfo=timezone.utc)

    metrics.record_poll_success("HWR", entries_added=5, timestamp=now)
    metrics.record_poll_success("HWR", entries_added=2, timestamp=now)

    assert _metric_value(reg, "fritzlog_entries_total", "HWR") == 7.0
