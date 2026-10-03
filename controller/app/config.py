"""Application settings, loaded from environment variables prefixed with ``VPG_``."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VPG_", env_file=".env", extra="ignore")

    # --- Security -----------------------------------------------------------
    # Fernet key used to encrypt VPN credentials and proxy passwords at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    master_key: str = Field(..., min_length=44)
    admin_username: str = "admin"
    admin_password: str = Field(..., min_length=10)
    # Secret used to sign dashboard session tokens.
    session_secret: str = Field(..., min_length=32)
    session_ttl_hours: int = 12
    # Optional static API key for scripts (header ``X-API-Key``).
    api_key: str | None = None
    # Set to false only when the dashboard is served over plain HTTP on a trusted LAN.
    secure_cookies: bool = True

    # --- Storage ------------------------------------------------------------
    database_url: str = "sqlite:////data/vpg.db"
    # Cache directory (provider server lists, ...).
    data_dir: str = "/data"
    traffic_retention_days: int = 30

    # --- Docker / tunnels ---------------------------------------------------
    docker_network: str = "vpg-tunnels"
    gluetun_image: str = "qmcgaw/gluetun:v3.41.3"
    gost_image: str = "gogost/gost:3.3.0"
    # Host IP the proxy ports are published on. Use your LAN IP, never 0.0.0.0 on a public VPS.
    proxy_bind_ip: str = "127.0.0.1"
    # Address that clients should use in generated proxy URLs (defaults to proxy_bind_ip).
    proxy_public_host: str | None = None
    socks_port_range: str = "11000-11099"
    http_port_range: str = "12000-12099"
    # How the controller reaches tunnels for health checks / metrics:
    #   "docker_network" – via container names on ``docker_network`` (controller runs in Docker; default)
    #   "host_ports"     – via proxy_bind_ip + published ports (controller runs on the host; no metrics)
    tunnel_access: str = Field(default="docker_network", pattern="^(docker_network|host_ports)$")

    # --- Health / rotation --------------------------------------------------
    health_interval_seconds: int = 30
    health_timeout_seconds: float = 10.0
    traffic_interval_seconds: int = 60
    # Consecutive failed checks before a tunnel is auto-rotated.
    auto_rotate_after_failures: int = 4
    # Grace period after (re)creating a tunnel before failures count.
    connect_grace_seconds: int = 60
    ip_check_urls: list[str] = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]

    # --- Server lists -------------------------------------------------------
    # ``{provider}`` is replaced by the gluetun provider name (URL-encoded).
    gluetun_servers_url: str = (
        "https://raw.githubusercontent.com/qdm12/gluetun-servers/main/pkg/servers/{provider}.json"
    )
    nordvpn_api_url: str = "https://api.nordvpn.com"

    # --- Alerts -------------------------------------------------------------
    webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # --- Misc ---------------------------------------------------------------
    # Disable background jobs (used by tests).
    enable_scheduler: bool = True

    @property
    def public_host(self) -> str:
        return self.proxy_public_host or self.proxy_bind_ip


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
