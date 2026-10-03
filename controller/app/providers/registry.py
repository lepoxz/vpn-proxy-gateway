"""Provider registry. Register new adapters here."""

import httpx

from app.config import Settings
from app.providers.base import ProviderAdapter, ProviderError
from app.providers.catalog import GluetunServerCatalog
from app.providers.gluetun_openvpn import GluetunOpenVPNAdapter
from app.providers.nordvpn import NordVPNAdapter


class ProviderRegistry:
    def __init__(self, adapters: list[ProviderAdapter]):
        self._adapters = {a.name: a for a in adapters}

    def get(self, name: str) -> ProviderAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise ProviderError(f"Unsupported provider: {name}") from exc

    def all(self) -> list[ProviderAdapter]:
        return list(self._adapters.values())


def build_registry(settings: Settings, http: httpx.Client) -> ProviderRegistry:
    catalog = GluetunServerCatalog(settings.gluetun_servers_url, settings.data_dir, http)
    return ProviderRegistry(
        [
            NordVPNAdapter(settings.nordvpn_api_url, http),
            GluetunOpenVPNAdapter(
                "expressvpn",
                "ExpressVPN",
                8,
                catalog,
                credential_help="expressvpn.com → My Account → Manual Config → OpenVPN",
            ),
            # Extra providers through the same generic path. Device limits are defaults
            # and can be overridden per account.
            GluetunOpenVPNAdapter(
                "surfshark",
                "Surfshark",
                100,
                catalog,
                credential_help="Surfshark → VPN → Manual setup → Router/Other → Credentials",
            ),
            GluetunOpenVPNAdapter(
                "protonvpn",
                "ProtonVPN",
                10,
                catalog,
                credential_help="account.protonvpn.com → Account → OpenVPN/IKEv2 username",
            ),
            GluetunOpenVPNAdapter(
                "private internet access",
                "Private Internet Access",
                100,
                catalog,
                location_key="region",
                credential_help="Your PIA username (p1234567) and password",
            ),
        ]
    )
