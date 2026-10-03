"""Request/response schemas for the REST API."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import RotationMode, TunnelStatus

PROXY_USER_RE = r"^[A-Za-z0-9_-]{3,32}$"
# Only URL-unreserved characters so credentials embed safely in proxy URLs.
PROXY_PASS_RE = r"^[A-Za-z0-9._~-]{12,64}$"
NAME_RE = r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$"


class LoginIn(BaseModel):
    username: str
    password: str


# --- Accounts ------------------------------------------------------------------


class AccountCreate(BaseModel):
    name: str = Field(pattern=NAME_RE)
    provider: str
    credentials: dict[str, str]
    max_devices: int | None = Field(default=None, ge=1, le=1000)
    reserved_devices: int = Field(default=2, ge=0, le=1000)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, pattern=NAME_RE)
    credentials: dict[str, str] | None = None
    max_devices: int | None = Field(default=None, ge=1, le=1000)
    reserved_devices: int | None = Field(default=None, ge=0, le=1000)


class AccountOut(BaseModel):
    id: int
    name: str
    provider: str
    max_devices: int
    reserved_devices: int
    tunnels_used: int
    tunnels_allowed: int
    created_at: datetime


# --- Tunnels -------------------------------------------------------------------


class RotationPolicy(BaseModel):
    rotation_mode: RotationMode = RotationMode.MANUAL
    rotation_interval_minutes: int | None = Field(default=None, ge=5, le=60 * 24 * 30)
    rotation_cron: str | None = None

    @field_validator("rotation_cron")
    @classmethod
    def _valid_cron(cls, v: str | None) -> str | None:
        if v:
            from apscheduler.triggers.cron import CronTrigger

            try:
                CronTrigger.from_crontab(v)
            except ValueError as exc:
                raise ValueError(f"Invalid cron expression: {exc}") from exc
        return v

    @model_validator(mode="after")
    def _consistent(self):
        if self.rotation_mode == RotationMode.INTERVAL and not self.rotation_interval_minutes:
            raise ValueError("rotation_interval_minutes is required for interval rotation")
        if self.rotation_mode == RotationMode.CRON and not self.rotation_cron:
            raise ValueError("rotation_cron is required for cron rotation")
        return self


class TunnelCreate(RotationPolicy):
    name: str = Field(pattern=NAME_RE)
    account_id: int
    country: str = Field(min_length=2, max_length=64)
    city: str | None = Field(default=None, max_length=64)
    protocol: str | None = None
    proxy_user: str | None = Field(default=None, pattern=PROXY_USER_RE)
    proxy_password: str | None = Field(default=None, pattern=PROXY_PASS_RE)


class TunnelUpdate(BaseModel):
    name: str | None = Field(default=None, pattern=NAME_RE)
    rotation: RotationPolicy | None = None


class ProxyInfo(BaseModel):
    host: str
    socks_port: int
    http_port: int
    username: str
    password: str
    socks5_url: str
    http_url: str


class TunnelOut(BaseModel):
    id: int
    name: str
    account_id: int
    account_name: str | None = None
    provider: str | None = None
    protocol: str
    country: str
    city: str | None
    server: str | None
    status: TunnelStatus
    status_detail: str | None
    current_ip: str | None
    last_check_at: datetime | None
    last_rotated_at: datetime | None
    rotation_mode: RotationMode
    rotation_interval_minutes: int | None
    rotation_cron: str | None
    proxy: ProxyInfo
    created_at: datetime


class TrafficPoint(BaseModel):
    ts: datetime
    rx_bytes: int
    tx_bytes: int


class TrafficOut(BaseModel):
    tunnel_id: int
    range_hours: int
    total_rx: int
    total_tx: int
    points: list[TrafficPoint]


class EventOut(BaseModel):
    id: int
    ts: datetime
    tunnel_id: int | None
    level: str
    kind: str
    message: str
