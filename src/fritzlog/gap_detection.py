from datetime import datetime


def detect_gap(
    entries: list[tuple[datetime, str]],
    *,
    last_stored: datetime | None,
) -> bool:
    """Return True if the Fritz!Box buffer rolled over and entries were lost.

    A gap is detected when the oldest entry in the current poll batch is
    strictly newer than the most recent entry we have stored — meaning some
    entries between them were evicted from the box's ~500-entry ring buffer.
    """
    if not entries or last_stored is None:
        return False
    oldest_in_batch = entries[0][0]
    return oldest_in_batch > last_stored
