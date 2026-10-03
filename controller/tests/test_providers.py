"""Unit tests for Provider Adapters."""

import httpx
import pytest
import respx

from app.providers.base import Location, ProviderError
from app.providers.catalog import GluetunServerCatalog
from app.providers.gluetun_openvpn import GluetunOpenVPNAdapter
from app.providers.nordvpn import NordVPNAdapter


@respx.mock
def test_nordvpn_normalize_credentials_success():
    http = httpx.Client()
    adapter = NordVPNAdapter("https://api.nordvpn.com", http)

    respx.get("https://api.nordvpn.com/v1/users/services/credentials").respond(
        status_code=200,
        json={
            "username": "nord_service_user",
            "password": "nord_service_password",
            "nordlynx_private_key": "private_key_base64_example=",
        },
    )

    creds = adapter.normalize_credentials({"access_token": "valid_token_123"})
    assert creds["service_username"] == "nord_service_user"
    assert creds["service_password"] == "nord_service_password"
    assert creds["wireguard_private_key"] == "private_key_base64_example="


@respx.mock
def test_nordvpn_normalize_credentials_invalid():
    http = httpx.Client()
    adapter = NordVPNAdapter("https://api.nordvpn.com", http)

    respx.get("https://api.nordvpn.com/v1/users/services/credentials").respond(
        status_code=401,
        json={"errors": ["Unauthorized"]},
    )

    with pytest.raises(ProviderError, match="NordVPN rejected the access token"):
        adapter.normalize_credentials({"access_token": "bad_token"})


@respx.mock
def test_nordvpn_list_locations():
    http = httpx.Client()
    adapter = NordVPNAdapter("https://api.nordvpn.com", http)

    respx.get("https://api.nordvpn.com/v1/servers/countries").respond(
        status_code=200,
        json=[
            {
                "id": 108,
                "name": "Japan",
                "code": "JP",
                "cities": [{"id": 1, "name": "Tokyo"}, {"id": 2, "name": "Osaka"}],
            }
        ],
    )

    locs = adapter.list_locations()
    assert len(locs) == 3  # Country + 2 cities
    assert locs[0] == Location(country="Japan", city=None, code="JP")
    assert locs[1] == Location(country="Japan", city="Tokyo", code="JP")
    assert locs[2] == Location(country="Japan", city="Osaka", code="JP")


@respx.mock
def test_nordvpn_build_tunnel_wireguard():
    http = httpx.Client()
    adapter = NordVPNAdapter("https://api.nordvpn.com", http)

    respx.get("https://api.nordvpn.com/v1/servers/countries").respond(
        status_code=200,
        json=[{"id": 108, "name": "Japan", "code": "JP", "cities": []}],
    )

    respx.get("https://api.nordvpn.com/v1/servers/recommendations").respond(
        status_code=200,
        json=[
            {
                "hostname": "jp100.nordvpn.com",
                "station": "198.51.100.10",
                "load": 15,
                "status": "online",
                "technologies": [
                    {
                        "identifier": "wireguard_udp",
                        "metadata": [{"name": "public_key", "value": "public_key_example="}],
                    }
                ],
            }
        ],
    )

    creds = {
        "service_username": "user",
        "service_password": "pass",
        "wireguard_private_key": "my_private_key=",
    }

    config = adapter.build_tunnel(creds, protocol="wireguard", country="Japan")
    assert config.server == "jp100.nordvpn.com"
    assert config.env["VPN_SERVICE_PROVIDER"] == "custom"
    assert config.env["VPN_TYPE"] == "wireguard"
    assert config.env["WIREGUARD_ENDPOINT_IP"] == "198.51.100.10"
    assert config.env["WIREGUARD_PUBLIC_KEY"] == "public_key_example="
    assert config.env["WIREGUARD_PRIVATE_KEY"] == "my_private_key="


def test_gluetun_openvpn_adapter(tmp_path):
    http = httpx.Client()
    catalog = GluetunServerCatalog("http://dummy/{provider}.json", str(tmp_path), http)
    # Mock memory cache in catalog
    catalog._mem["expressvpn"] = (
        9999999999.0,
        [
            {"country": "Japan", "city": "Tokyo", "hostname": "jp-tokyo.expressnetw.com"},
            {"country": "United States", "city": "New York", "hostname": "us-ny.expressnetw.com"},
        ],
    )

    adapter = GluetunOpenVPNAdapter("expressvpn", "ExpressVPN", 8, catalog)

    locs = adapter.list_locations()
    assert len(locs) == 2

    creds = adapter.normalize_credentials({"username": "exp_user", "password": "exp_password"})
    assert creds["username"] == "exp_user"

    cfg = adapter.build_tunnel(creds, protocol="openvpn", country="Japan", city="Tokyo")
    assert cfg.env["VPN_SERVICE_PROVIDER"] == "expressvpn"
    assert cfg.env["VPN_TYPE"] == "openvpn"
    assert cfg.env["OPENVPN_USER"] == "exp_user"
    assert cfg.env["SERVER_COUNTRIES"] == "Japan"
    assert cfg.env["SERVER_CITIES"] == "Tokyo"
