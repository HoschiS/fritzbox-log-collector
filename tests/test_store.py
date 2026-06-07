from datetime import UTC, datetime

import pytest

from fritzlog.store import Store


@pytest.fixture
def store() -> Store:
    return Store(":memory:")


def test_schema_created_on_init(store: Store) -> None:
    with store.connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }

    assert "logs" in tables
    assert "idx_logs_box_ts" in indexes


def test_insert_new_entry_persists(store: Store) -> None:
    ts = datetime(2026, 6, 7, 10, 23, 17)
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)

    store.insert("HWR", ts, "Internetverbindung hergestellt.", collected)

    with store.connection() as conn:
        rows = conn.execute("SELECT box, timestamp, message, collected_at FROM logs").fetchall()

    assert len(rows) == 1
    box, timestamp, message, collected_at = rows[0]
    assert box == "HWR"
    assert timestamp == "2026-06-07T10:23:17"
    assert message == "Internetverbindung hergestellt."
    assert collected_at == "2026-06-07T10:25:00Z"


def test_duplicate_entry_is_ignored(store: Store) -> None:
    ts = datetime(2026, 6, 7, 10, 23, 17)
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)

    first = store.insert("HWR", ts, "Verbindung hergestellt.", collected)
    second = store.insert("HWR", ts, "Verbindung hergestellt.", collected)

    assert first is True
    assert second is False

    with store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    assert count == 1


def test_same_entry_different_boxes_both_stored(store: Store) -> None:
    ts = datetime(2026, 6, 7, 10, 23, 17)
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)

    store.insert("HWR", ts, "WLAN-Gerät angemeldet.", collected)
    store.insert("Arbeitszimmer", ts, "WLAN-Gerät angemeldet.", collected)

    with store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    assert count == 2


def test_most_recent_timestamp_returns_latest(store: Store) -> None:
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)
    store.insert("HWR", datetime(2026, 6, 7, 9, 0, 0), "older", collected)
    store.insert("HWR", datetime(2026, 6, 7, 10, 0, 0), "newer", collected)

    result = store.most_recent_timestamp("HWR")

    assert result == datetime(2026, 6, 7, 10, 0, 0)


def test_most_recent_timestamp_none_when_empty(store: Store) -> None:
    assert store.most_recent_timestamp("HWR") is None


def test_most_recent_timestamp_scoped_to_box(store: Store) -> None:
    collected = datetime(2026, 6, 7, 10, 25, 0, tzinfo=UTC)
    store.insert("HWR", datetime(2026, 6, 7, 10, 0, 0), "msg", collected)
    store.insert("Arbeitszimmer", datetime(2026, 6, 7, 11, 0, 0), "msg", collected)

    assert store.most_recent_timestamp("HWR") == datetime(2026, 6, 7, 10, 0, 0)
    assert store.most_recent_timestamp("Arbeitszimmer") == datetime(2026, 6, 7, 11, 0, 0)
