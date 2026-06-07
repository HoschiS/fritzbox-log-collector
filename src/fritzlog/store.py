import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    box          TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    message      TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    UNIQUE(box, timestamp, message)
);

CREATE INDEX IF NOT EXISTS idx_logs_box_ts ON logs(box, timestamp);
"""


class Store:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        yield self._conn

    def insert(self, box: str, timestamp: datetime, message: str, collected_at: datetime) -> bool:
        """Insert an entry. Returns True if inserted, False if it was a duplicate."""
        ts_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        collected_iso = collected_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO logs (box, timestamp, message, collected_at) VALUES (?, ?, ?, ?)",
            (box, ts_iso, message, collected_iso),
        )
        self._conn.commit()
        return cursor.rowcount == 1

    def most_recent_timestamp(self, box: str) -> datetime | None:
        row = self._conn.execute(
            "SELECT MAX(timestamp) FROM logs WHERE box = ?", (box,)
        ).fetchone()
        if row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def close(self) -> None:
        self._conn.close()
