"""Generic adapter for any gluetun-supported provider using OpenVPN username/password.

Used for ExpressVPN (whose Lightway protocol has no manual configuration) and as
the plugin path for other providers (Surfshark, ProtonVPN, PIA, ...). Server
selection is delegated to gluetun via ``SERVER_COUNTRIES`` / ``SERVER_CITIES``
(or ``SERVER_REGIONS``), so each rotation lands on a random server in that location.
"""

from app.providers.base import CredentialField, Location, ProviderAdapter, ProviderError, TunnelConfig
from app.providers.catalog import GluetunServerCatalog


class GluetunOpenVPNAdapter(ProviderAdapter):
    protocols = ("openvpn",)

    def __init__(
        self,
        name: str,
        display_name: str,
        default_max_devices: int,
        catalog: GluetunServerCatalog,
        *,
        location_key: str = "country",
        credential_help: str = "",
    ):
        self.name = name
        self.display_name = display_name
        self.default_max_devices = default_max_devices
        self.catalog = catalog
        # Field in gluetun's server list used as the "country" level (PIA uses "region").
        self.location_key = location_key
        self.credential_fields = (
            CredentialField("username", "OpenVPN username", secret=False, help=credential_help),
            CredentialField("password", "OpenVPN password", help=credential_help),
        )

    def normalize_credentials(self, creds: dict) -> dict:
        # These providers expose no API to validate manual credentials; a bad pair
        # surfaces as an AUTH_FAILED tunnel error on first connect.
        self._require(creds, "username", "password")
        return {"username": creds["username"].strip(), "password": creds["password"].strip()}

    def list_locations(self) -> list[Location]:
        return self.catalog.locations(self.name, self.location_key)

    def _canonical(self, country: str, city: str | None) -> tuple[str, str | None]:
        """Match user input case-insensitively against gluetun's names."""
        locs = self.list_locations()
        match_country = next((loc.country for loc in locs if loc.country.lower() == country.lower()), None)
        if not match_country:
            raise ProviderError(f"Unknown {self.display_name} location: {country}")
        if not city:
            return match_country, None
        match_city = next(
            (
                loc.city
                for loc in locs
                if loc.country == match_country and loc.city and loc.city.lower() == city.lower()
            ),
            None,
        )
        if not match_city:
            raise ProviderError(f"Unknown {self.display_name} city: {city} ({match_country})")
        return match_country, match_city

    def build_tunnel(self, creds, protocol, country, city=None, exclude_servers=frozenset()):
        self._check_protocol(protocol)
        country, city = self._canonical(country, city)
        selector = "SERVER_REGIONS" if self.location_key == "region" else "SERVER_COUNTRIES"
        env = {
            "VPN_SERVICE_PROVIDER": self.name,
            "VPN_TYPE": "openvpn",
            "OPENVPN_USER": creds["username"],
            "OPENVPN_PASSWORD": creds["password"],
            selector: country,
        }
        if city:
            env["SERVER_CITIES"] = city
        return TunnelConfig(env=env)
