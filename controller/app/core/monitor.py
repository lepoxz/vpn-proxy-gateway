"""Health checking (with the layer-2 kill-switch) and traffic accounting."""

import ipaddress
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
from sqlmodel import delete, select

from app.config import Settings
from app.core.runtime import (
    METRICS_INTERNAL_PORT,
    SOCKS_INTERNAL_PORT,
    ContainerRuntime,
    TunnelSpec,
    vpn_name,
)
from app.core.tunnels import TunnelError, TunnelManager
from app.db import session_scope
from app.models import Event, TrafficSample, Tunnel, TunnelStatus, utcnow

log = logging.getLogger(__name__)

SKIP_STATUSES = (TunnelStatus.STOPPED, TunnelStatus.LEAK_BLOCKED)
REAL_IP_TTL = 3600


def _valid_ip(text: str) -> str | None:
    text = text.strip()
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None


def fetch_ip(urls: list[str], timeout: float, proxy: str | None = None) -> str | None:
    """Return the public IP seen by the first IP-echo service that answers."""
    try:
        with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            for url in urls:
                try:
                    resp = client.get(url)
                    if resp.status_code == 200 and (ip := _valid_ip(resp.text)):
                        return ip
                except httpx.HTTPError:
                    continue
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: bad proxy URL
        log.debug("IP fetch failed: %s", exc)
    return None


class HealthChecker:
    def __init__(
        self,
        settings: Settings,
        manager: TunnelManager,
        runtime: ContainerRuntime,
        ip_fetcher: Callable[..., str | None] = fetch_ip,
    ):
        self.settings = settings
        self.manager = manager
        self.runtime = runtime
        self.ip_fetcher = ip_fetcher
        self._real_ip: str | None = None
        self._real_ip_at = 0.0
        self._real_ip_lock = threading.Lock()
        self._warned_no_real_ip = False

    # -- real IP (layer-2 kill-switch reference) -----------------------------------

    @property
    def real_ip(self) -> str | None:
        with self._real_ip_lock:
            if self._real_ip is None or time.time() - self._real_ip_at > REAL_IP_TTL:
                ip = self.ip_fetcher(self.settings.ip_check_urls, self.settings.health_timeout_seconds)
                if ip:
                    self._real_ip, self._real_ip_at = ip, time.time()
                elif not self._warned_no_real_ip:
                    log.warning("Cannot determine host public IP; leak detection is degraded")
                    self._warned_no_real_ip = True
            return self._real_ip

    # -- probing -----------------------------------------------------------------

    def proxy_url(self, tunnel: Tunnel) -> str:
        pw = self.manager.vault.decrypt(tunnel.proxy_pass_enc)
        if self.settings.tunnel_access == "docker_network":
            host, port = vpn_name(tunnel.id), SOCKS_INTERNAL_PORT
        else:
            host, port = self.settings.proxy_bind_ip, tunnel.socks_port
        # socks5h: DNS is resolved inside the tunnel, exercising the leak-free path.
        return f"socks5h://{tunnel.proxy_user}:{pw}@{host}:{port}"

    def probe(self, tunnel: Tunnel) -> str | None:
        return self.ip_fetcher(
            self.settings.ip_check_urls, self.settings.health_timeout_seconds, proxy=self.proxy_url(tunnel)
        )

    def _proxy_spec(self, tunnel: Tunnel) -> TunnelSpec:
        return TunnelSpec(
            tunnel_id=tunnel.id,
            vpn_env={},
            bind_ip=self.settings.proxy_bind_ip,
            socks_port=tunnel.socks_port,
            http_port=tunnel.http_port,
            proxy_user=tunnel.proxy_user,
            proxy_pass=self.manager.vault.decrypt(tunnel.proxy_pass_enc),
        )

    # -- checks ------------------------------------------------------------------

    def check_all(self) -> None:
        with session_scope() as session:
            ids = [t.id for t in session.exec(select(Tunnel)).all() if t.status not in SKIP_STATUSES]
        if not ids:
            return
        _ = self.real_ip  # refresh once, before fanning out
        with ThreadPoolExecutor(max_workers=min(8, len(ids))) as pool:
            list(pool.map(self.check_tunnel, ids))

    def check_tunnel(self, tunnel_id: int) -> None:
        lock = self.manager.lock(tunnel_id)
        if not lock.acquire(blocking=False):
            return  # rotation/restart in progress
        rotate_reason: str | None = None
        try:
            rotate_reason = self._check_locked(tunnel_id)
        except Exception:  # noqa: BLE001 - never let one tunnel kill the job
            log.exception("Health check crashed for tunnel %s", tunnel_id)
        finally:
            lock.release()
        if rotate_reason:
            try:
                self.manager.rotate(tunnel_id, reason=rotate_reason)
            except TunnelError as exc:
                log.error("Auto-rotate failed for tunnel %s: %s", tunnel_id, exc)

    def _check_locked(self, tunnel_id: int) -> str | None:
        s = self.settings
        events = self.manager.events
        with session_scope() as session:
            t = session.get(Tunnel, tunnel_id)
            if t is None or t.status in SKIP_STATUSES:
                return None
            now = utcnow()
            in_grace = bool(
                t.last_rotated_at and (now - t.last_rotated_at).total_seconds() < s.connect_grace_seconds
            )
            old_status, old_ip = t.status, t.current_ip
            state = self.runtime.state(tunnel_id)
            ip: str | None = None
            problem: str | None = None

            if state is None:
                problem = "containers missing"
            elif not state.vpn_running:
                problem = "VPN container not running" + (f": {state.vpn_error}" if state.vpn_error else "")
            else:
                if not state.proxy_running and state.vpn_health == "healthy":
                    self.runtime.start_proxy(self._proxy_spec(t))
                    events.record(session, "proxy_repaired", f"'{t.name}': proxy restarted", tunnel_id=t.id)
                ip = self.probe(t)
                if ip is None:
                    problem = f"proxy probe failed (VPN health: {state.vpn_health or 'unknown'})"
                    # gluetun restarted under gost (shared netns lost): recreate the sidecar.
                    if state.vpn_health == "healthy" and t.consecutive_failures >= 1 and not in_grace:
                        self.runtime.start_proxy(self._proxy_spec(t))

            t.last_check_at = now
            rotate_reason = None

            if ip is not None:
                real = self.real_ip
                if real and ip == real:
                    # ---- Layer-2 kill-switch -------------------------------------------
                    self.runtime.stop_proxy(tunnel_id)
                    t.status = TunnelStatus.LEAK_BLOCKED
                    t.status_detail = f"Egress IP {ip} equals host IP; proxy stopped"
                    t.current_ip = None
                    session.add(t)
                    session.commit()
                    events.record(
                        session,
                        "leak_blocked",
                        f"'{t.name}': traffic was leaving with the real IP {ip}. Proxy stopped; "
                        "investigate and restart manually.",
                        tunnel_id=t.id,
                        level="error",
                    )
                    return None
                t.status = TunnelStatus.HEALTHY
                t.status_detail = None
                t.consecutive_failures = 0
                t.current_ip = ip
            elif in_grace:
                t.status = TunnelStatus.CONNECTING
                t.status_detail = problem
            else:
                t.consecutive_failures += 1
                t.status = TunnelStatus.DOWN if t.consecutive_failures >= 2 else TunnelStatus.DEGRADED
                t.status_detail = problem
                if t.consecutive_failures >= s.auto_rotate_after_failures:
                    rotate_reason = f"auto: {t.consecutive_failures} failed checks"

            session.add(t)
            session.commit()

            if t.status != old_status:
                if t.status == TunnelStatus.DOWN:
                    events.record(
                        session, "down", f"'{t.name}' is down: {problem}", tunnel_id=t.id, level="warning"
                    )
                elif t.status == TunnelStatus.HEALTHY and old_status in (
                    TunnelStatus.DOWN,
                    TunnelStatus.DEGRADED,
                ):
                    events.record(session, "recovered", f"'{t.name}' recovered", tunnel_id=t.id, alert=True)
            if ip and ip != old_ip:
                events.record(session, "ip_changed", f"'{t.name}' exit IP is now {ip}", tunnel_id=t.id)
            return rotate_reason


# --- Traffic -----------------------------------------------------------------------

RX_METRIC = "gost_service_transfer_output_bytes_total"  # proxy -> client (download)
TX_METRIC = "gost_service_transfer_input_bytes_total"  # client -> proxy (upload)


def parse_gost_metrics(text: str) -> tuple[int, int]:
    rx = tx = 0.0
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name = line.split("{", 1)[0].split(" ", 1)[0]
        if name not in (RX_METRIC, TX_METRIC):
            continue
        try:
            value = float(line.rsplit(" ", 1)[-1])
        except ValueError:
            continue
        if name == RX_METRIC:
            rx += value
        else:
            tx += value
    return int(rx), int(tx)


class TrafficCollector:
    def __init__(self, settings: Settings, http: httpx.Client):
        self.settings = settings
        self.http = http
        self._last: dict[int, tuple[int, int]] = {}

    def _fetch(self, tunnel_id: int) -> tuple[int, int] | None:
        url = f"http://{vpn_name(tunnel_id)}:{METRICS_INTERNAL_PORT}/metrics"
        try:
            resp = self.http.get(url, timeout=5)
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        return parse_gost_metrics(resp.text)

    def collect(self) -> None:
        if self.settings.tunnel_access != "docker_network":
            return
        with session_scope() as session:
            tunnels = [t for t in session.exec(select(Tunnel)).all() if t.status not in SKIP_STATUSES]
            for t in tunnels:
                counters = self._fetch(t.id)
                if counters is None:
                    continue
                self.record(session, t.id, counters)
            session.commit()

    def record(self, session, tunnel_id: int, counters: tuple[int, int]) -> None:
        prev = self._last.get(tunnel_id)
        self._last[tunnel_id] = counters
        if prev is None:
            return  # first observation: baseline only
        # Counter reset (proxy container recreated) -> the new counter value is the delta.
        drx = counters[0] - prev[0] if counters[0] >= prev[0] else counters[0]
        dtx = counters[1] - prev[1] if counters[1] >= prev[1] else counters[1]
        if drx or dtx:
            session.add(TrafficSample(tunnel_id=tunnel_id, rx_bytes=drx, tx_bytes=dtx))

    def cleanup(self) -> None:
        cutoff = utcnow() - timedelta(days=self.settings.traffic_retention_days)
        with session_scope() as session:
            session.exec(delete(TrafficSample).where(TrafficSample.ts < cutoff))
            session.exec(delete(Event).where(Event.ts < cutoff - timedelta(days=60)))
            session.commit()
