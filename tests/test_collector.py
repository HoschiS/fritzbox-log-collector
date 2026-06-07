from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from fritzlog.collector import parse_log_line, poll
from fritzlog.config import BoxConfig


def test_parse_log_line_returns_datetime_and_message() -> None:
    line = "07.06.26 10:23:17 Internetverbindung hergestellt. IP-Adresse: 93.184.216.34"

    ts, msg = parse_log_line(line)

    assert ts == datetime(2026, 6, 7, 10, 23, 17)
    assert msg == "Internetverbindung hergestellt. IP-Adresse: 93.184.216.34"


def test_parse_log_line_two_digit_year_is_2000_plus() -> None:
    line = "06.06.26 23:58:01 Anmeldung erfolgreich."

    ts, _ = parse_log_line(line)

    assert ts.year == 2026


def _make_box() -> BoxConfig:
    return BoxConfig(name="HWR", host="192.168.178.1", user="u", password="p")


def test_poll_returns_entries_oldest_first() -> None:
    raw_log = (
        "07.06.26 10:23:17 Neueste Meldung.\n"
        "07.06.26 09:15:42 Ältere Meldung.\n"
        "06.06.26 23:58:01 Älteste Meldung.\n"
    )
    mock_fc = MagicMock()
    mock_fc.call_action.return_value = {"NewDeviceLog": raw_log}

    with patch("fritzlog.collector.FritzConnection", return_value=mock_fc):
        entries = poll(_make_box())

    assert len(entries) == 3
    assert entries[0][0] == datetime(2026, 6, 6, 23, 58, 1)
    assert entries[0][1] == "Älteste Meldung."
    assert entries[2][0] == datetime(2026, 6, 7, 10, 23, 17)
    assert entries[2][1] == "Neueste Meldung."


def test_poll_skips_blank_lines() -> None:
    raw_log = "\n07.06.26 10:23:17 Einzige Meldung.\n\n"
    mock_fc = MagicMock()
    mock_fc.call_action.return_value = {"NewDeviceLog": raw_log}

    with patch("fritzlog.collector.FritzConnection", return_value=mock_fc):
        entries = poll(_make_box())

    assert len(entries) == 1
    assert entries[0][1] == "Einzige Meldung."
