"""Container runtime abstraction.

Each tunnel is two containers sharing one network namespace:

* ``vpg-t<id>-vpn``   – gluetun: VPN client + firewall kill-switch + DNS over TLS.
                        Publishes the proxy ports on the host.
* ``vpg-t<id>-proxy`` – gost: SOCKS5 (:1080) + HTTP (:8080) with auth, metrics on :9000.
                        Runs with ``network_mode=container:vpg-t<id>-vpn`` so its only
                        route to the Internet is the VPN interface.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)

SOCKS_INTERNAL_PORT = 1080
HTTP_INTERNAL_PORT = 8080
METRICS_INTERNAL_PORT = 9000
LABEL_TUNNEL = "vpg.tunnel_id"
LABEL_ROLE = "vpg.role"


def vpn_name(tunnel_id: int) -> str:
    return f"vpg-t{tunnel_id}-vpn"


def proxy_name(tunnel_id: int) -> str:
    return f"vpg-t{tunnel_id}-proxy"


@dataclass
class TunnelSpec:
    tunnel_id: int
    vpn_env: dict[str, str]
    bind_ip: str
    socks_port: int
    http_port: int
    proxy_user: str
    proxy_pass: str


@dataclass
class RuntimeState:
    vpn_running: bool
    proxy_running: bool
    # Docker healthcheck of gluetun: "starting" | "healthy" | "unhealthy" | None
    vpn_health: str | None = None
    vpn_error: str | None = None


class RuntimeError_(Exception):
    pass


class ContainerRuntime(Protocol):
    def ensure_network(self) -> None: ...
    def start_tunnel(self, spec: TunnelSpec) -> None: ...
    def start_proxy(self, spec: TunnelSpec) -> None: ...
    def stop_proxy(self, tunnel_id: int) -> None: ...
    def remove_tunnel(self, tunnel_id: int) -> None: ...
    def state(self, tunnel_id: int) -> RuntimeState | None: ...
    def list_tunnel_ids(self) -> set[int]: ...
    def logs(self, tunnel_id: int, tail: int = 200, redact: tuple[str, ...] = ()) -> str: ...


def redact_text(text: str, secrets: tuple[str, ...]) -> str:
    for s in secrets:
        if s and len(s) >= 4:
            text = text.replace(s, "***")
    return text


def gost_command(spec: TunnelSpec) -> list[str]:
    auth = f"{spec.proxy_user}:{spec.proxy_pass}"
    return [
        "-L",
        f"socks5://{auth}@:{SOCKS_INTERNAL_PORT}",
        "-L",
        f"http://{auth}@:{HTTP_INTERNAL_PORT}",
        "-metrics",
        f":{METRICS_INTERNAL_PORT}",
    ]


def gluetun_env(spec: TunnelSpec) -> dict[str, str]:
    env = dict(spec.vpn_env)
    # Allow inbound connections to the proxy/metrics ports through gluetun's firewall.
    env["FIREWALL_INPUT_PORTS"] = f"{SOCKS_INTERNAL_PORT},{HTTP_INTERNAL_PORT},{METRICS_INTERNAL_PORT}"
    # Never let the kill-switch be disabled by user-supplied env.
    env["FIREWALL_ENABLED_DISABLING_IT_SHOOTS_YOU_IN_YOUR_FOOT"] = "on"
    env.setdefault("DNS_UPSTREAM_IPV6", "off")
    env.setdefault("HEALTH_RESTART_VPN", "on")
    return env


class DockerRuntime:
    def __init__(self, network: str, gluetun_image: str, gost_image: str, client=None):
        import docker

        self.client = client or docker.from_env()
        self.network = network
        self.gluetun_image = gluetun_image
        self.gost_image = gost_image

    # -- helpers ---------------------------------------------------------------

    def _get(self, name: str):
        from docker.errors import NotFound

        try:
            return self.client.containers.get(name)
        except NotFound:
            return None

    def _remove(self, name: str) -> None:
        c = self._get(name)
        if c is not None:
            c.remove(force=True)

    def _pull_if_missing(self, image: str) -> None:
        from docker.errors import ImageNotFound

        try:
            self.client.images.get(image)
        except ImageNotFound:
            log.info("Pulling %s", image)
            self.client.images.pull(image)

    # -- API -------------------------------------------------------------------

    def ensure_network(self) -> None:
        if not self.client.networks.list(names=[self.network]):
            self.client.networks.create(self.network, driver="bridge")

    def start_tunnel(self, spec: TunnelSpec) -> None:
        from docker.errors import APIError

        self.remove_tunnel(spec.tunnel_id)
        self._pull_if_missing(self.gluetun_image)
        labels = {LABEL_TUNNEL: str(spec.tunnel_id), LABEL_ROLE: "vpn"}
        try:
            self.client.containers.run(
                self.gluetun_image,
                name=vpn_name(spec.tunnel_id),
                detach=True,
                environment=gluetun_env(spec),
                cap_add=["NET_ADMIN"],
                devices=["/dev/net/tun:/dev/net/tun"],
                sysctls={"net.ipv6.conf.all.disable_ipv6": "1"},
                ports={
                    f"{SOCKS_INTERNAL_PORT}/tcp": (spec.bind_ip, spec.socks_port),
                    f"{HTTP_INTERNAL_PORT}/tcp": (spec.bind_ip, spec.http_port),
                },
                network=self.network,
                labels=labels,
                restart_policy={"Name": "unless-stopped"},
            )
        except APIError as exc:
            self.remove_tunnel(spec.tunnel_id)
            raise RuntimeError_(f"Cannot start VPN container: {exc.explanation or exc}") from exc
        self.start_proxy(spec)

    def start_proxy(self, spec: TunnelSpec) -> None:
        from docker.errors import APIError

        self._remove(proxy_name(spec.tunnel_id))
        self._pull_if_missing(self.gost_image)
        try:
            self.client.containers.run(
                self.gost_image,
                name=proxy_name(spec.tunnel_id),
                command=gost_command(spec),
                detach=True,
                network_mode=f"container:{vpn_name(spec.tunnel_id)}",
                labels={LABEL_TUNNEL: str(spec.tunnel_id), LABEL_ROLE: "proxy"},
                restart_policy={"Name": "unless-stopped"},
            )
        except APIError as exc:
            raise RuntimeError_(f"Cannot start proxy container: {exc.explanation or exc}") from exc

    def stop_proxy(self, tunnel_id: int) -> None:
        self._remove(proxy_name(tunnel_id))

    def remove_tunnel(self, tunnel_id: int) -> None:
        self._remove(proxy_name(tunnel_id))
        self._remove(vpn_name(tunnel_id))

    def state(self, tunnel_id: int) -> RuntimeState | None:
        vpn = self._get(vpn_name(tunnel_id))
        if vpn is None:
            return None
        proxy = self._get(proxy_name(tunnel_id))
        st = vpn.attrs.get("State", {})
        return RuntimeState(
            vpn_running=st.get("Running", False),
            proxy_running=bool(proxy and proxy.attrs.get("State", {}).get("Running")),
            vpn_health=(st.get("Health") or {}).get("Status"),
            vpn_error=st.get("Error") or None,
        )

    def list_tunnel_ids(self) -> set[int]:
        ids = set()
        for c in self.client.containers.list(all=True, filters={"label": LABEL_TUNNEL}):
            try:
                ids.add(int(c.labels[LABEL_TUNNEL]))
            except (KeyError, ValueError):
                continue
        return ids

    def logs(self, tunnel_id: int, tail: int = 200, redact: tuple[str, ...] = ()) -> str:
        out = []
        for name in (vpn_name(tunnel_id), proxy_name(tunnel_id)):
            c = self._get(name)
            if c is not None:
                text = c.logs(tail=tail).decode(errors="replace")
                out.append(f"===== {name} =====\n{text}")
        return redact_text("\n".join(out), redact)


class FakeRuntime:
    """In-memory runtime for tests and dry runs."""

    def __init__(self):
        self.tunnels: dict[int, dict] = {}
        self.fail_next_start = False

    def ensure_network(self) -> None:
        pass

    def start_tunnel(self, spec: TunnelSpec) -> None:
        if self.fail_next_start:
            self.fail_next_start = False
            raise RuntimeError_("simulated failure")
        self.tunnels[spec.tunnel_id] = {
            "spec": spec,
            "state": RuntimeState(vpn_running=True, proxy_running=True, vpn_health="healthy"),
            "starts": self.tunnels.get(spec.tunnel_id, {}).get("starts", 0) + 1,
        }

    def start_proxy(self, spec: TunnelSpec) -> None:
        self.tunnels[spec.tunnel_id]["state"].proxy_running = True

    def stop_proxy(self, tunnel_id: int) -> None:
        if tunnel_id in self.tunnels:
            self.tunnels[tunnel_id]["state"].proxy_running = False

    def remove_tunnel(self, tunnel_id: int) -> None:
        self.tunnels.pop(tunnel_id, None)

    def state(self, tunnel_id: int) -> RuntimeState | None:
        t = self.tunnels.get(tunnel_id)
        return t["state"] if t else None

    def list_tunnel_ids(self) -> set[int]:
        return set(self.tunnels)

    def logs(self, tunnel_id: int, tail: int = 200, redact: tuple[str, ...] = ()) -> str:
        spec = self.tunnels.get(tunnel_id, {}).get("spec")
        text = f"fake logs for {tunnel_id} pass={spec.proxy_pass if spec else ''}"
        return redact_text(text, redact)
