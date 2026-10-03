"""Provider adapter interface.

An adapter knows how to turn a user's VPN subscription credentials plus a desired
location into the environment variables for a gluetun container. Adding a new
provider means implementing this interface and registering it in ``registry.py``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Raised for invalid credentials, unknown locations or upstream API failures."""


@dataclass(frozen=True)
class CredentialField:
    name: str
    label: str
    secret: bool = True
    required: bool = True
    help: str = ""


@dataclass(frozen=True)
class Location:
    country: str
    city: str | None = None
    code: str | None = None


@dataclass
class TunnelConfig:
    """Result of ``ProviderAdapter.build_tunnel``."""

    env: dict[str, str]
    # Concrete server pinned for this connection (hostname / IP) or None if gluetun picks one.
    server: str | None = None
    extra: dict = field(default_factory=dict)


class ProviderAdapter(ABC):
    name: str
    display_name: str
    default_max_devices: int
    protocols: tuple[str, ...]
    credential_fields: tuple[CredentialField, ...]

    @abstractmethod
    def normalize_credentials(self, creds: dict) -> dict:
        """Validate user input and return the credential dict to store (encrypted)."""

    @abstractmethod
    def list_locations(self) -> list[Location]:
        """Countries/cities the user can choose from."""

    @abstractmethod
    def build_tunnel(
        self,
        creds: dict,
        protocol: str,
        country: str,
        city: str | None = None,
        exclude_servers: frozenset[str] = frozenset(),
    ) -> TunnelConfig:
        """Return gluetun env for a connection. ``exclude_servers`` lets rotation pick a new server."""

    # Shared helpers -----------------------------------------------------------

    def _require(self, creds: dict, *keys: str) -> None:
        missing = [k for k in keys if not str(creds.get(k) or "").strip()]
        if missing:
            raise ProviderError(f"Missing credential field(s): {', '.join(missing)}")

    def _check_protocol(self, protocol: str) -> None:
        if protocol not in self.protocols:
            raise ProviderError(
                f"{self.display_name} does not support protocol '{protocol}' "
                f"(supported: {', '.join(self.protocols)})"
            )

    def describe(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "default_max_devices": self.default_max_devices,
            "protocols": list(self.protocols),
            "credential_fields": [f.__dict__ for f in self.credential_fields],
        }
