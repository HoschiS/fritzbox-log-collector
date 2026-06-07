import logging
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from fritzlog.collector import poll
from fritzlog.config import BoxConfig, Config, ConfigError, load_config
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
    def _poll_box(box: BoxConfig) -> list[tuple[datetime, str]]:
        logger.info("Polling %s (%s)…", box.name, box.host)
        return poll(box)

    with ThreadPoolExecutor(max_workers=len(cfg.boxes)) as executor:
        futures = {executor.submit(_poll_box, box): box for box in cfg.boxes}

        for future in as_completed(futures):
            box = futures[future]
            try:
                entries = future.result()
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
            metrics.record_poll_success(
                box.name, entries_added=added, timestamp=now, gap_detected=gap
            )


def run_loop(
    cfg: Config,
    store: Store,
    metrics: Metrics,
    *,
    shutdown: threading.Event,
    poll_interval: int,
) -> None:
    while not shutdown.is_set():
        now = datetime.now(tz=UTC)
        poll_all_boxes(cfg, store, metrics, now=now)
        shutdown.wait(timeout=poll_interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # fritzconnection logs connection errors at ERROR before raising — we re-log them as
    # WARNING ourselves, so suppress the library's own output to avoid duplicate lines.
    logging.getLogger("fritzconnection").setLevel(logging.CRITICAL)

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

    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())

    logger.info(
        "Starting fritzlog: %d box(es), polling every %ds",
        len(cfg.boxes),
        cfg.poll_interval_seconds,
    )

    run_loop(cfg, store, metrics, shutdown=shutdown, poll_interval=cfg.poll_interval_seconds)
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
