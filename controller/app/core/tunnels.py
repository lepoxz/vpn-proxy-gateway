"""Tunnel lifecycle: create, rotate, restart, stop, delete, reconcile."""

import logging
import secrets
import string
import threading
from collections import defaultdict
from collections.abc import Callable

from sqlmodel import Session, delete, func, select

from app.config import Settings
from app.core import ports
from app.core.events import EventLog
from app.core.runtime import ContainerRuntime, RuntimeError_, TunnelSpec
from app.db import session_scope
from app.models import Account, RotationMode, TrafficSample, Tunnel, TunnelStatus, utcnow
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
from app.schemas import ProxyInfo, RotationPolicy, TunnelCreate
from app.security import Vault, random_secret

log = logging.getLogger(__name__)


class TunnelError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class TunnelManager:
    def __init__(
        self,
        settings: Settings,
        vault: Vault,
        registry: ProviderRegistry,
        runtime: ContainerRuntime,
        events: EventLog,
    ):
        self.settings = settings
        self.vault = vault
        self.registry = registry
        self.runtime = runtime
        self.events = events
        self.socks_range = ports.parse_range(settings.socks_port_range)
        self.http_range = ports.parse_range(settings.http_port_range)
        self._locks: dict[int, threading.Lock] = defaultdict(threading.Lock)
        self._create_lock = threading.Lock()
        # Called after a tunnel's rotation policy changes or it is deleted (scheduler hook).
        self.on_policy_changed: Callable[[int], None] | None = None

    # -- helpers -----------------------------------------------------------------

    def lock(self, tunnel_id: int) -> threading.Lock:
        return self._locks[tunnel_id]

    @staticmethod
    def tunnels_used(session: Session, account_id: int) -> int:
        return session.exec(
            select(func.count()).select_from(Tunnel).where(Tunnel.account_id == account_id)
        ).one()

    @staticmethod
    def tunnels_allowed(account: Account) -> int:
        return max(0, account.max_devices - account.reserved_devices)

    def proxy_info(self, tunnel: Tunnel) -> ProxyInfo:
        host = self.settings.public_host
        pw = self.vault.decrypt(tunnel.proxy_pass_enc)
        auth = f"{tunnel.proxy_user}:{pw}"
        return ProxyInfo(
            host=host,
            socks_port=tunnel.socks_port,
            http_port=tunnel.http_port,
            username=tunnel.proxy_user,
            password=pw,
            socks5_url=f"socks5h://{auth}@{host}:{tunnel.socks_port}",
            http_url=f"http://{auth}@{host}:{tunnel.http_port}",
        )

    def _spec(self, tunnel: Tunnel, env: dict[str, str]) -> TunnelSpec:
        assert tunnel.id is not None
        return TunnelSpec(
            tunnel_id=tunnel.id,
            vpn_env=env,
            bind_ip=self.settings.proxy_bind_ip,
            socks_port=tunnel.socks_port,
            http_port=tunnel.http_port,
            proxy_user=tunnel.proxy_user,
            proxy_pass=self.vault.decrypt(tunnel.proxy_pass_enc),
        )

    def _deploy(self, session: Session, tunnel: Tunnel, exclude: frozenset[str]) -> None:
        """Pick a server and (re)create the tunnel containers. Raises ProviderError/RuntimeError_."""
        account = session.get(Account, tunnel.account_id)
        if account is None:
            raise TunnelError("Account no longer exists", 409)
        adapter = self.registry.get(account.provider)
        creds = self.vault.decrypt_json(account.credentials_enc)
        cfg = adapter.build_tunnel(creds, tunnel.protocol, tunnel.country, tunnel.city, exclude)
        self.runtime.start_tunnel(self._spec(tunnel, cfg.env))
        tunnel.server = cfg.server
        tunnel.status = TunnelStatus.CONNECTING
        tunnel.status_detail = None
        tunnel.consecutive_failures = 0
        tunnel.last_rotated_at = utcnow()
        session.add(tunnel)
        session.commit()

    def _notify_policy(self, tunnel_id: int) -> None:
        if self.on_policy_changed:
            self.on_policy_changed(tunnel_id)

    def _secrets_for(self, session: Session, tunnel: Tunnel) -> tuple[str, ...]:
        out = [self.vault.decrypt(tunnel.proxy_pass_enc)]
        account = session.get(Account, tunnel.account_id)
        if account:
            out += [v for v in self.vault.decrypt_json(account.credentials_enc).values() if v]
        return tuple(out)

    # -- lifecycle ---------------------------------------------------------------

    def create(self, data: TunnelCreate) -> Tunnel:
        with self._create_lock, session_scope() as session:
            account = session.get(Account, data.account_id)
            if account is None:
                raise TunnelError("Account not found", 404)
            try:
                adapter = self.registry.get(account.provider)
            except ProviderError as exc:
                raise TunnelError(str(exc)) from exc
            protocol = data.protocol or adapter.protocols[0]
            if protocol not in adapter.protocols:
                raise TunnelError(f"{adapter.display_name} supports: {', '.join(adapter.protocols)}")

            used = self.tunnels_used(session, account.id)
            allowed = self.tunnels_allowed(account)
            if used >= allowed:
                raise TunnelError(
                    f"Device limit reached for '{account.name}': {used}/{allowed} tunnels "
                    f"({account.reserved_devices} slot(s) reserved for your own devices)",
                    409,
                )
            if session.exec(select(Tunnel).where(Tunnel.name == data.name)).first():
                raise TunnelError(f"Tunnel name '{data.name}' already exists", 409)

            existing = session.exec(select(Tunnel.socks_port, Tunnel.http_port)).all()
            try:
                socks_port = ports.allocate(self.socks_range, {s for s, _ in existing})
                http_port = ports.allocate(self.http_range, {h for _, h in existing})
            except ports.PortExhausted as exc:
                raise TunnelError(str(exc), 409) from exc

            user = data.proxy_user or "u" + "".join(
                secrets.choice(string.ascii_lowercase + string.digits) for _ in range(7)
            )
            tunnel = Tunnel(
                name=data.name,
                account_id=account.id,
                protocol=protocol,
                country=data.country,
                city=data.city or None,
                socks_port=socks_port,
                http_port=http_port,
                proxy_user=user,
                proxy_pass_enc=self.vault.encrypt(data.proxy_password or random_secret(24)),
                rotation_mode=data.rotation_mode,
                rotation_interval_minutes=data.rotation_interval_minutes,
                rotation_cron=data.rotation_cron,
            )
            session.add(tunnel)
            session.commit()
            session.refresh(tunnel)

            try:
                self._deploy(session, tunnel, frozenset())
            except (ProviderError, RuntimeError_, TunnelError) as exc:
                self.runtime.remove_tunnel(tunnel.id)
                session.delete(tunnel)
                session.commit()
                raise TunnelError(f"Cannot create tunnel: {exc}") from exc

            self.events.record(
                session,
                "created",
                f"Tunnel '{tunnel.name}' created ({account.provider}/{protocol} {tunnel.country}"
                f"{' / ' + tunnel.city if tunnel.city else ''})",
                tunnel_id=tunnel.id,
            )
        self._notify_policy(tunnel.id)
        return tunnel

    def _redeploy(self, tunnel_id: int, *, new_server: bool, kind: str, reason: str) -> Tunnel:
        with self.lock(tunnel_id), session_scope() as session:
            tunnel = session.get(Tunnel, tunnel_id)
            if tunnel is None:
                raise TunnelError("Tunnel not found", 404)
            previous = tunnel.server
            exclude = frozenset({previous}) if new_server and previous else frozenset()
            try:
                self._deploy(session, tunnel, exclude)
            except (ProviderError, RuntimeError_, TunnelError) as exc:
                tunnel.status = TunnelStatus.ERROR
                tunnel.status_detail = str(exc)
                session.add(tunnel)
                session.commit()
                self.events.record(
                    session, f"{kind}_failed", f"'{tunnel.name}': {exc}", tunnel_id=tunnel_id, level="error"
                )
                raise TunnelError(str(exc)) from exc
            detail = f" → {tunnel.server}" if tunnel.server else ""
            self.events.record(
                session, kind, f"'{tunnel.name}' {kind} ({reason}){detail}", tunnel_id=tunnel_id
            )
            return tunnel

    def rotate(self, tunnel_id: int, reason: str = "manual") -> Tunnel:
        """Reconnect to a different server (new exit IP). Proxy port and credentials are unchanged."""
        return self._redeploy(tunnel_id, new_server=True, kind="rotated", reason=reason)

    def restart(self, tunnel_id: int, reason: str = "manual") -> Tunnel:
        """Recreate containers without explicitly excluding the current server."""
        return self._redeploy(tunnel_id, new_server=False, kind="restarted", reason=reason)

    def start(self, tunnel_id: int) -> Tunnel:
        return self._redeploy(tunnel_id, new_server=False, kind="started", reason="manual")

    def stop(self, tunnel_id: int) -> Tunnel:
        with self.lock(tunnel_id), session_scope() as session:
            tunnel = session.get(Tunnel, tunnel_id)
            if tunnel is None:
                raise TunnelError("Tunnel not found", 404)
            self.runtime.remove_tunnel(tunnel_id)
            tunnel.status = TunnelStatus.STOPPED
            tunnel.status_detail = None
            tunnel.current_ip = None
            session.add(tunnel)
            session.commit()
            self.events.record(session, "stopped", f"'{tunnel.name}' stopped", tunnel_id=tunnel_id)
            return tunnel

    def delete(self, tunnel_id: int) -> None:
        with self.lock(tunnel_id), session_scope() as session:
            tunnel = session.get(Tunnel, tunnel_id)
            if tunnel is None:
                raise TunnelError("Tunnel not found", 404)
            self.runtime.remove_tunnel(tunnel_id)
            session.exec(delete(TrafficSample).where(TrafficSample.tunnel_id == tunnel_id))
            session.delete(tunnel)
            session.commit()
            self.events.record(session, "deleted", f"Tunnel '{tunnel.name}' deleted", tunnel_id=tunnel_id)
        self._locks.pop(tunnel_id, None)
        self._notify_policy(tunnel_id)

    def update_policy(self, tunnel_id: int, policy: RotationPolicy | None, name: str | None) -> Tunnel:
        with self.lock(tunnel_id), session_scope() as session:
            tunnel = session.get(Tunnel, tunnel_id)
            if tunnel is None:
                raise TunnelError("Tunnel not found", 404)
            if name and name != tunnel.name:
                if session.exec(select(Tunnel).where(Tunnel.name == name)).first():
                    raise TunnelError(f"Tunnel name '{name}' already exists", 409)
                tunnel.name = name
            if policy is not None:
                tunnel.rotation_mode = policy.rotation_mode
                tunnel.rotation_interval_minutes = (
                    policy.rotation_interval_minutes if policy.rotation_mode == RotationMode.INTERVAL else None
                )
                tunnel.rotation_cron = policy.rotation_cron if policy.rotation_mode == RotationMode.CRON else None
            session.add(tunnel)
            session.commit()
        self._notify_policy(tunnel_id)
        return tunnel

    def logs(self, tunnel_id: int, tail: int = 200) -> str:
        with session_scope() as session:
            tunnel = session.get(Tunnel, tunnel_id)
            if tunnel is None:
                raise TunnelError("Tunnel not found", 404)
            return self.runtime.logs(tunnel_id, tail, redact=self._secrets_for(session, tunnel))

    # -- startup -----------------------------------------------------------------

    def reconcile(self) -> None:
        """Bring Docker in line with the database after a controller restart."""
        self.runtime.ensure_network()
        with session_scope() as session:
            tunnels = session.exec(select(Tunnel)).all()
            known = {t.id for t in tunnels}
            for orphan in self.runtime.list_tunnel_ids() - known:
                log.info("Removing orphan containers of tunnel %s", orphan)
                self.runtime.remove_tunnel(orphan)
            for t in tunnels:
                if t.status == TunnelStatus.STOPPED:
                    if self.runtime.state(t.id) is not None:
                        self.runtime.remove_tunnel(t.id)
                    continue
                if t.status == TunnelStatus.LEAK_BLOCKED:
                    # Keep the proxy down until the user explicitly restarts it.
                    self.runtime.stop_proxy(t.id)
                    continue
                if self.runtime.state(t.id) is None:
                    try:
                        self.restart(t.id, reason="reconcile")
                    except TunnelError as exc:
                        log.error("Reconcile failed for tunnel %s: %s", t.id, exc)
