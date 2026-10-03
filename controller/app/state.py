"""Application wiring: a single container object built at startup."""

from dataclasses import dataclass

import httpx

from app.config import Settings
from app.core.events import EventLog, Notifier
from app.core.monitor import HealthChecker, TrafficCollector
from app.core.runtime import ContainerRuntime
from app.core.scheduler import Jobs
from app.core.tunnels import TunnelManager
from app.providers.registry import ProviderRegistry, build_registry
from app.security import LoginThrottle, Vault


@dataclass
class AppState:
    settings: Settings
    http: httpx.Client
    vault: Vault
    registry: ProviderRegistry
    runtime: ContainerRuntime
    events: EventLog
    manager: TunnelManager
    health: HealthChecker
    traffic: TrafficCollector
    jobs: Jobs
    throttle: LoginThrottle


def build_state(
    settings: Settings,
    runtime: ContainerRuntime,
    *,
    registry: ProviderRegistry | None = None,
    http: httpx.Client | None = None,
    ip_fetcher=None,
) -> AppState:
    http = http or httpx.Client(headers={"User-Agent": "vpn-proxy-gateway/0.1"})
    vault = Vault(settings.master_key)
    registry = registry or build_registry(settings, http)
    events = EventLog(Notifier(settings, http))
    manager = TunnelManager(settings, vault, registry, runtime, events)
    health = HealthChecker(settings, manager, runtime, **({"ip_fetcher": ip_fetcher} if ip_fetcher else {}))
    traffic = TrafficCollector(settings, http)
    jobs = Jobs(settings, manager, health, traffic)
    return AppState(
        settings=settings,
        http=http,
        vault=vault,
        registry=registry,
        runtime=runtime,
        events=events,
        manager=manager,
        health=health,
        traffic=traffic,
        jobs=jobs,
        throttle=LoginThrottle(),
    )
