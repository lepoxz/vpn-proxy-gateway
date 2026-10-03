"""Tests for Health checking, Layer-2 Kill-switch, and Traffic accounting."""

from datetime import timedelta

from sqlmodel import select

from app.core.monitor import HealthChecker, TrafficCollector, parse_gost_metrics
from app.core.tunnels import TunnelManager
from app.db import session_scope
from app.models import Account, RotationMode, TrafficSample, Tunnel, TunnelStatus, utcnow
from app.schemas import TunnelCreate


def _setup_tunnel(app_state, monkeypatch):
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )
    with session_scope() as session:
        acc = Account(
            name="acc-monitor",
            provider="expressvpn",
            credentials_enc=app_state.vault.encrypt_json({"username": "u", "password": "p"}),
            max_devices=5,
        )
        session.add(acc)
        session.commit()
        session.refresh(acc)
        acc_id = acc.id

    manager: TunnelManager = app_state.manager
    return manager.create(
        TunnelCreate(
            name="test-monitor-tun",
            account_id=acc_id,
            country="Japan",
            rotation_mode=RotationMode.MANUAL,
        )
    )


def test_health_check_healthy(app_state, monkeypatch):
    tun = _setup_tunnel(app_state, monkeypatch)

    # Health check with mock_ip_fetcher: proxy returns "198.51.100.99", host IP is "1.2.3.4"
    checker: HealthChecker = app_state.health
    checker.check_tunnel(tun.id)

    with session_scope() as session:
        t = session.get(Tunnel, tun.id)
        assert t.status == TunnelStatus.HEALTHY
        assert t.current_ip == "198.51.100.99"
        assert t.consecutive_failures == 0


def test_layer2_killswitch_leak_blocked(app_state, monkeypatch):
    tun = _setup_tunnel(app_state, monkeypatch)

    # Simulate IP leak: proxy returns the exact same IP as the host ("1.2.3.4")
    def leaking_ip_fetcher(urls, timeout, proxy=None):
        return "1.2.3.4"

    checker = HealthChecker(
        app_state.settings,
        app_state.manager,
        app_state.runtime,
        ip_fetcher=leaking_ip_fetcher,
    )

    # Trigger health check
    checker.check_tunnel(tun.id)

    # 1. Status must become LEAK_BLOCKED
    with session_scope() as session:
        t = session.get(Tunnel, tun.id)
        assert t.status == TunnelStatus.LEAK_BLOCKED
        assert "equals host IP" in (t.status_detail or "")
        assert t.current_ip is None

    # 2. Proxy container MUST be immediately stopped by runtime
    state = app_state.runtime.state(tun.id)
    assert state.proxy_running is False


def test_health_check_degraded_and_down_and_autorotate(app_state, monkeypatch):
    tun = _setup_tunnel(app_state, monkeypatch)

    # Simulate failing proxy probe
    def failing_ip_fetcher(urls, timeout, proxy=None):
        if proxy is None:
            return "1.2.3.4"
        return None  # Proxy probe fails

    checker = HealthChecker(
        app_state.settings,
        app_state.manager,
        app_state.runtime,
        ip_fetcher=failing_ip_fetcher,
    )

    # Bypass the initial connection grace period
    with session_scope() as session:
        t = session.get(Tunnel, tun.id)
        t.last_rotated_at = utcnow() - timedelta(minutes=10)
        session.add(t)
        session.commit()

    # Check 1: 1 failure -> DEGRADED
    checker.check_tunnel(tun.id)
    with session_scope() as session:
        t = session.get(Tunnel, tun.id)
        assert t.status == TunnelStatus.DEGRADED
        assert t.consecutive_failures == 1

    # Check 2: 2 failures -> DOWN
    checker.check_tunnel(tun.id)
    with session_scope() as session:
        t = session.get(Tunnel, tun.id)
        assert t.status == TunnelStatus.DOWN
        assert t.consecutive_failures == 2

    # Check 3 & 4: reach auto-rotate threshold (4 failures)
    checker.check_tunnel(tun.id)
    checker.check_tunnel(tun.id)

    with session_scope() as session:
        t = session.get(Tunnel, tun.id)
        # Auto-rotate was triggered -> status reset to CONNECTING, failures reset to 0
        assert t.status == TunnelStatus.CONNECTING
        assert t.consecutive_failures == 0


def test_parse_gost_metrics():
    sample_prometheus = """
# HELP gost_service_transfer_output_bytes_total Total transferred output bytes
# TYPE gost_service_transfer_output_bytes_total counter
gost_service_transfer_output_bytes_total{service="socks"} 10485760
# HELP gost_service_transfer_input_bytes_total Total transferred input bytes
# TYPE gost_service_transfer_input_bytes_total counter
gost_service_transfer_input_bytes_total{service="socks"} 5242880
"""
    rx, tx = parse_gost_metrics(sample_prometheus)
    assert rx == 10485760  # 10 MB
    assert tx == 5242880  # 5 MB


def test_traffic_collector_recording(app_state):
    collector = TrafficCollector(app_state.settings, app_state.http)

    with session_scope() as session:
        # First reading: establishes baseline, no delta recorded yet
        collector.record(session, tunnel_id=1, counters=(1000, 500))
        samples = session.exec(select(TrafficSample)).all()
        assert len(samples) == 0

        # Second reading: delta is 500 rx, 200 tx
        collector.record(session, tunnel_id=1, counters=(1500, 700))
        session.commit()
        samples = session.exec(select(TrafficSample)).all()
        assert len(samples) == 1
        assert samples[0].rx_bytes == 500
        assert samples[0].tx_bytes == 200

        # Counter reset (e.g. proxy restart): new counters (300, 100)
        collector.record(session, tunnel_id=1, counters=(300, 100))
        session.commit()
        samples = session.exec(select(TrafficSample)).all()
        assert len(samples) == 2
        assert samples[1].rx_bytes == 300
        assert samples[1].tx_bytes == 100
