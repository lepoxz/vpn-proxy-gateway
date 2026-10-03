"""Database models."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TunnelStatus(StrEnum):
    CREATING = "creating"
    CONNECTING = "connecting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    # Layer-2 kill-switch tripped: egress IP equalled the host's real IP, proxy was stopped.
    LEAK_BLOCKED = "leak_blocked"
    STOPPED = "stopped"
    ERROR = "error"


class RotationMode(StrEnum):
    MANUAL = "manual"
    INTERVAL = "interval"
    CRON = "cron"


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    provider: str = Field(index=True)
    # Fernet-encrypted JSON blob with provider-specific credentials.
    credentials_enc: str
    max_devices: int
    # Slots kept free for the user's own phones/laptops on the same subscription.
    reserved_devices: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Tunnel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    protocol: str  # "wireguard" | "openvpn"
    country: str
    city: str | None = None
    # Concrete server currently in use (hostname or endpoint IP), if the provider pins one.
    server: str | None = None

    socks_port: int = Field(unique=True)
    http_port: int = Field(unique=True)
    proxy_user: str
    proxy_pass_enc: str

    status: TunnelStatus = TunnelStatus.CREATING
    status_detail: str | None = None
    current_ip: str | None = None
    consecutive_failures: int = 0
    last_check_at: datetime | None = None
    last_rotated_at: datetime | None = None

    rotation_mode: RotationMode = RotationMode.MANUAL
    rotation_interval_minutes: int | None = None
    rotation_cron: str | None = None

    created_at: datetime = Field(default_factory=utcnow)


class TrafficSample(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tunnel_id: int = Field(foreign_key="tunnel.id", index=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    # Bytes transferred during the sample window (deltas, not counters).
    rx_bytes: int = 0
    tx_bytes: int = 0


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    tunnel_id: int | None = Field(default=None, index=True)
    level: str = "info"  # info | warning | error
    kind: str  # created, rotated, status_changed, leak_blocked, ...
    message: str
