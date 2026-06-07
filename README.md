# fritzlog

A containerised log collector for AVM Fritz!Box mesh networks.

Polls each Fritz!Box and mesh satellite via the TR-064 SOAP API, deduplicates entries using SQLite, and optionally forwards new entries as JSON to stdout (Grafana Alloy → Loki) and exposes Prometheus metrics.

## Quick start

```bash
docker run -d \
  --name fritzlog \
  -v fritzlog-data:/data \
  -v /path/to/config.yaml:/config/config.yaml:ro \
  ghcr.io/hoscchis/fritzbox-log-collector:latest
```

## Configuration

Copy `config.example.yaml`, fill in your box IPs and credentials, then mount it into the container at `/config/config.yaml`.

```yaml
poll_interval_seconds: 300

boxes:
  - name: HWR
    host: 192.168.178.1
    user: syslog-user
    password: secret

output:
  sqlite_path: /data/fritzlog.db
  stdout_json: false        # set true for Alloy/Loki ingestion
  # prometheus_port: 9877  # uncomment to enable /metrics
```

### Fritz!Box user setup

Create a dedicated user in the Fritz!Box web UI (*System → Fritz!Box users*) with the permission **"Access to the Fritz!Box settings"** (required for TR-064). No admin rights needed.

## Docker Compose

```yaml
services:
  fritzlog:
    image: ghcr.io/hoscchis/fritzbox-log-collector:latest
    restart: unless-stopped
    volumes:
      - fritzlog-data:/data
      - ./config.yaml:/config/config.yaml:ro
    ports:
      - "9877:9877"   # only needed if prometheus_port is set

volumes:
  fritzlog-data:
```

## Grafana / Loki integration

Set `stdout_json: true`. Grafana Alloy (or Promtail) picks up the Docker container logs and ships to Loki with no additional infrastructure. Each new entry is written as one JSON object:

```json
{"box": "HWR", "timestamp": "2026-06-07T10:23:17", "message": "Internetverbindung hergestellt.", "collected_at": "2026-06-07T10:25:01Z"}
```

## Prometheus metrics

| Metric | Type | Description |
|---|---|---|
| `fritzlog_entries_total{box}` | Counter | Total stored entries per box |
| `fritzlog_poll_success{box}` | Gauge | 1 if last poll succeeded, 0 if failed |
| `fritzlog_last_poll_timestamp{box}` | Gauge | Unix timestamp of last successful poll |
| `fritzlog_buffer_gap_detected{box}` | Gauge | 1 if the Fritz!Box buffer rolled over since last poll |

## Known limitations

- Fritz!OS does not support syslog push; polling is the only retrieval method.
- Mesh satellites must each have TR-064 enabled and credentials configured. If a satellite is unreachable, fritzlog logs a warning and continues polling the others.
- The Fritz!Box internal buffer holds approximately 500 entries. If the poll interval is too long relative to log volume, entries can be lost (detected via `fritzlog_buffer_gap_detected`).

## Development

```bash
# install uv then:
uv sync
uv run pytest
uv run ruff check src/ tests/
```
