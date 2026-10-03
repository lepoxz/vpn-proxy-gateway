"""Server catalogue sourced from gluetun's server data (github.com/qdm12/gluetun-servers).

gluetun embeds one JSON file per provider listing all servers. We read the same
files to populate the location picker for providers without a public API
(ExpressVPN, Surfshark, ...), which also guarantees the country/city names match
what gluetun's ``SERVER_COUNTRIES`` / ``SERVER_CITIES`` expect. Files are cached on
disk and refreshed daily.
"""

import json
import logging
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.providers.base import Location, ProviderError

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 24 * 3600


class GluetunServerCatalog:
    def __init__(self, url_template: str, cache_dir: str, http: httpx.Client):
        """``url_template`` contains ``{provider}``, e.g. ``.../pkg/servers/{provider}.json``."""
        self.url_template = url_template
        self.cache_dir = Path(cache_dir) / "gluetun-servers"
        self.http = http
        self._mem: dict[str, tuple[float, list[dict]]] = {}
        self._lock = threading.Lock()

    def servers(self, provider: str) -> list[dict]:
        with self._lock:
            now = time.time()
            cached = self._mem.get(provider)
            if cached and now - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]

            path = self.cache_dir / f"{provider}.json"
            fresh = path.exists() and now - path.stat().st_mtime < CACHE_TTL_SECONDS
            if not fresh:
                url = self.url_template.format(provider=quote(provider))
                try:
                    resp = self.http.get(url, timeout=60, follow_redirects=True)
                    resp.raise_for_status()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(resp.content)
                except (httpx.HTTPError, OSError) as exc:
                    log.warning("Could not refresh server list for %s: %s", provider, exc)

            if not path.exists():
                raise ProviderError(f"Server list for {provider} unavailable (no network and no cache)")
            servers = json.loads(path.read_text()).get("servers", [])
            self._mem[provider] = (now, servers)
            return servers

    def locations(self, provider: str, country_key: str = "country") -> list[Location]:
        seen: set[tuple[str, str | None]] = set()
        for srv in self.servers(provider):
            country = srv.get(country_key)
            if country:
                seen.add((country, srv.get("city") or None))
        return [Location(country=c, city=city) for c, city in sorted(seen, key=lambda x: (x[0], x[1] or ""))]
