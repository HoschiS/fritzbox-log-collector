import json
from datetime import datetime
from typing import Optional

from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server


def format_entry_as_json(box: str, timestamp: datetime, message: str, collected_at: datetime) -> str:
    return json.dumps(
        {
            "box": box,
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
            "message": message,
            "collected_at": collected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )


def write_entry(box: str, timestamp: datetime, message: str, collected_at: datetime) -> None:
    print(format_entry_as_json(box, timestamp, message, collected_at), flush=True)


class Metrics:
    def __init__(self, registry: Optional[CollectorRegistry]) -> None:
        reg = registry if registry is not None else CollectorRegistry()
        self._entries_total = Counter(
            "fritzlog_entries",
            "Total stored log entries",
            ["box"],
            registry=reg,
        )
        self._poll_success = Gauge(
            "fritzlog_poll_success",
            "1 if last poll succeeded, 0 if failed",
            ["box"],
            registry=reg,
        )
        self._last_poll_timestamp = Gauge(
            "fritzlog_last_poll_timestamp",
            "Unix timestamp of last successful poll",
            ["box"],
            registry=reg,
        )
        self._buffer_gap_detected = Gauge(
            "fritzlog_buffer_gap_detected",
            "1 if a buffer gap was detected on last poll",
            ["box"],
            registry=reg,
        )

    def record_poll_success(
        self,
        box: str,
        *,
        entries_added: int,
        timestamp: datetime,
        gap_detected: bool = False,
    ) -> None:
        self._entries_total.labels(box=box).inc(entries_added)
        self._poll_success.labels(box=box).set(1)
        self._last_poll_timestamp.labels(box=box).set(timestamp.timestamp())
        self._buffer_gap_detected.labels(box=box).set(1 if gap_detected else 0)

    def record_poll_failure(self, box: str) -> None:
        self._poll_success.labels(box=box).set(0)

    def start_server(self, port: int) -> None:
        start_http_server(port)
