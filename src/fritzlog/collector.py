from datetime import datetime

from fritzconnection.core.fritzconnection import FritzConnection

from fritzlog.config import BoxConfig


def parse_log_line(line: str) -> tuple[datetime, str]:
    ts = datetime.strptime(line[:17], "%d.%m.%y %H:%M:%S")
    message = line[18:]
    return ts, message


_CONNECT_TIMEOUT = 10.0  # seconds; Fritz!Box is LAN-local so 10s is generous


def poll(box: BoxConfig) -> list[tuple[datetime, str]]:
    timeout = box.timeout_seconds if box.timeout_seconds is not None else _CONNECT_TIMEOUT
    fc = FritzConnection(
        address=box.host, user=box.user, password=box.password, timeout=timeout
    )
    raw: str = fc.call_action("DeviceInfo1", "GetDeviceLog")["NewDeviceLog"]
    lines = [line for line in raw.splitlines() if line.strip()]
    lines.reverse()
    return [parse_log_line(line) for line in lines]
