from datetime import datetime

from fritzlog.gap_detection import detect_gap


def test_no_gap_when_store_is_empty() -> None:
    entries = [(datetime(2026, 6, 7, 10, 0, 0), "msg")]
    assert detect_gap(entries, last_stored=None) is False


def test_no_gap_when_oldest_entry_not_newer_than_last_stored() -> None:
    # Box returns from 9:00; we already have data up to 9:30 → buffer still covers us
    entries = [
        (datetime(2026, 6, 7, 9, 0, 0), "older"),
        (datetime(2026, 6, 7, 10, 0, 0), "newer"),
    ]
    last_stored = datetime(2026, 6, 7, 9, 30, 0)

    assert detect_gap(entries, last_stored=last_stored) is False


def test_gap_detected_when_oldest_entry_newer_than_last_stored() -> None:
    entries = [
        (datetime(2026, 6, 7, 10, 0, 0), "oldest in batch"),
        (datetime(2026, 6, 7, 11, 0, 0), "newest in batch"),
    ]
    last_stored = datetime(2026, 6, 7, 9, 0, 0)

    assert detect_gap(entries, last_stored=last_stored) is True


def test_no_gap_when_entries_list_is_empty() -> None:
    assert detect_gap([], last_stored=datetime(2026, 6, 7, 10, 0, 0)) is False
