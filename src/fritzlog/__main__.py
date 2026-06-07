import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from fritzlog.collector import poll
from fritzlog.config import Config, ConfigError, load_config
from fritzlog.gap_detection import detect_gap
from fritzlog.output import Metrics, write_entry
from fritzlog.store import Store

logger = logging.getLogger(__name__)


def poll_all_boxes(
    cfg: Config,
    store: Store,
    metrics: Metrics,
    *,
    now: datetime,
) -> None:
    for box in cfg.boxes:
        logger.info("Polling %s (%s)…", box.name, box.host)
        try:
            entries = poll(box)
        except Exception as exc:
            logger.warning("Poll failed for box %r: %s", box.name, exc)
            metrics.record_poll_failure(box.name)
            continue

        last_stored = store.most_recent_timestamp(box.name)
        gap = detect_gap(entries, last_stored=last_stored)
        if gap:
            logger.warning(
                "Buffer gap detected for box %r — entries may have been lost", box.name
            )

        added = 0
        for ts, message in entries:
            inserted = store.insert(box.name, ts, message, now)
            if inserted:
                added += 1
                if cfg.output.stdout_json:
                    write_entry(box.name, ts, message, now)

        logger.info("%s: %d new of %d entries in batch", box.name, added, len(entries))
        metrics.record_poll_success(box.name, entries_added=added, timestamp=now, gap_detected=gap)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/config/config.yaml")

    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    store = Store(cfg.output.sqlite_path)
    metrics = Metrics(registry=None)

    if cfg.output.prometheus_port:
        metrics.start_server(cfg.output.prometheus_port)
        logger.info("Prometheus metrics available on port %d", cfg.output.prometheus_port)

    logger.info(
        "Starting fritzlog: %d box(es), polling every %ds",
        len(cfg.boxes),
        cfg.poll_interval_seconds,
    )

    while True:
        now = datetime.now(tz=UTC)
        poll_all_boxes(cfg, store, metrics, now=now)
        time.sleep(cfg.poll_interval_seconds)


if __name__ == "__main__":
    main()
