"""NordVPN adapter.

* Credentials: a NordVPN **access token** (Dashboard -> Manual setup -> Generate token).
  From it we fetch the OpenVPN service credentials and the NordLynx (WireGuard)
  private key via ``/v1/users/services/credentials``.
* WireGuard: we pick a concrete server from NordVPN's recommendation API and pass
  its endpoint + public key to gluetun's ``custom`` provider. This does not depend
  on gluetun's bundled server list and lets rotation pick a *different* server.
* OpenVPN: we let gluetun choose a random server in the requested country/city.
"""

import random
import threading
import time

import httpx

from app.providers.base import CredentialField, Location, ProviderAdapter, ProviderError, TunnelConfig

NORDLYNX_ADDRESS = "10.5.0.2/32"
NORDLYNX_PORT = "51820"
CACHE_TTL = 6 * 3600


class NordVPNAdapter(ProviderAdapter):
    name = "nordvpn"
    display_name = "NordVPN"
    default_max_devices = 10
    protocols = ("wireguard", "openvpn")
    credential_fields = (
        CredentialField(
            "access_token",
            "Access token",
            help="NordVPN Dashboard → Manual setup → Set up NordVPN manually → Generate new token",
        ),
    )

    def __init__(self, api_url: str, http: httpx.Client):
        self.api = api_url.rstrip("/")
        self.http = http
        self._countries: list[dict] | None = None
        self._countries_at = 0.0
        self._lock = threading.Lock()

    # -- credentials ---------------------------------------------------------

    def normalize_credentials(self, creds: dict) -> dict:
        self._require(creds, "access_token")
        token = creds["access_token"].strip()
        try:
            resp = self.http.get(
                f"{self.api}/v1/users/services/credentials", auth=("token", token), timeout=20
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cannot reach NordVPN API: {exc}") from exc
        if resp.status_code in (401, 403):
            raise ProviderError("NordVPN rejected the access token")
        if resp.status_code != 200:
            raise ProviderError(f"NordVPN API error {resp.status_code}")
        data = resp.json()
        out = {
            "access_token": token,
            "service_username": data.get("username", ""),
            "service_password": data.get("password", ""),
            "wireguard_private_key": data.get("nordlynx_private_key", ""),
        }
        if not out["service_username"] or not out["wireguard_private_key"]:
            raise ProviderError("NordVPN API returned incomplete credentials")
        return out

    # -- locations -----------------------------------------------------------

    def _country_list(self) -> list[dict]:
        with self._lock:
            if self._countries is None or time.time() - self._countries_at > CACHE_TTL:
                try:
                    resp = self.http.get(f"{self.api}/v1/servers/countries", timeout=20)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    if self._countries is None:
                        raise ProviderError(f"Cannot fetch NordVPN countries: {exc}") from exc
                else:
                    self._countries = resp.json()
                    self._countries_at = time.time()
            return self._countries  # type: ignore[return-value]

    def list_locations(self) -> list[Location]:
        out: list[Location] = []
        for c in self._country_list():
            out.append(Location(country=c["name"], code=c.get("code")))
            for city in c.get("cities", []):
                out.append(Location(country=c["name"], city=city["name"], code=c.get("code")))
        return out

    def _country(self, country: str) -> dict:
        key = country.strip().lower()
        for c in self._country_list():
            if c["name"].lower() == key or (c.get("code") or "").lower() == key:
                return c
        raise ProviderError(f"Unknown NordVPN country: {country}")

    # -- tunnel --------------------------------------------------------------

    def _pick_server(self, country: dict, city: str | None, tech: str, exclude: frozenset[str]) -> dict:
        params = {
            "filters[country_id]": country["id"],
            "filters[servers_technologies][identifier]": tech,
            "limit": 50,
        }
        try:
            resp = self.http.get(f"{self.api}/v1/servers/recommendations", params=params, timeout=20)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cannot fetch NordVPN servers: {exc}") from exc

        servers = [s for s in resp.json() if s.get("status") == "online"]
        if city:
            servers = [
                s
                for s in servers
                if any(
                    (loc.get("country", {}).get("city", {}) or {}).get("name", "").lower() == city.lower()
                    for loc in s.get("locations", [])
                )
            ]
        if not servers:
            raise ProviderError(f"No online NordVPN {tech} server in {country['name']} {city or ''}".strip())

        candidates = [s for s in servers if s["hostname"] not in exclude and s["station"] not in exclude]
        candidates = candidates or servers  # only one server available: reuse it
        candidates.sort(key=lambda s: s.get("load", 100))
        # Spread across the least-loaded few instead of always hammering the top one.
        return random.choice(candidates[:5])

    @staticmethod
    def _public_key(server: dict) -> str:
        for tech in server.get("technologies", []):
            if tech.get("identifier") == "wireguard_udp":
                for meta in tech.get("metadata", []):
                    if meta.get("name") == "public_key":
                        return meta["value"]
        raise ProviderError(f"Server {server.get('hostname')} has no WireGuard public key")

    def build_tunnel(self, creds, protocol, country, city=None, exclude_servers=frozenset()):
        self._check_protocol(protocol)
        c = self._country(country)

        if protocol == "wireguard":
            srv = self._pick_server(c, city, "wireguard_udp", exclude_servers)
            return TunnelConfig(
                server=srv["hostname"],
                env={
                    "VPN_SERVICE_PROVIDER": "custom",
                    "VPN_TYPE": "wireguard",
                    "WIREGUARD_ENDPOINT_IP": srv["station"],
                    "WIREGUARD_ENDPOINT_PORT": NORDLYNX_PORT,
                    "WIREGUARD_PUBLIC_KEY": self._public_key(srv),
                    "WIREGUARD_PRIVATE_KEY": creds["wireguard_private_key"],
                    "WIREGUARD_ADDRESSES": NORDLYNX_ADDRESS,
                },
            )

        env = {
            "VPN_SERVICE_PROVIDER": "nordvpn",
            "VPN_TYPE": "openvpn",
            "OPENVPN_USER": creds["service_username"],
            "OPENVPN_PASSWORD": creds["service_password"],
            "SERVER_COUNTRIES": c["name"],
        }
        if city:
            env["SERVER_CITIES"] = city
        return TunnelConfig(env=env)
