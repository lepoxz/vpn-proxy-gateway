"""Unit and integration tests for Tunnel lifecycle management."""

import pytest

from app.core.tunnels import TunnelError, TunnelManager
from app.db import session_scope
from app.models import Account, RotationMode, Tunnel, TunnelStatus
from app.schemas import TunnelCreate


def _create_test_account(app_state, name="test-vpn", max_devices=5, reserved=1):
    with session_scope() as session:
        creds_enc = app_state.vault.encrypt_json({"username": "vpn_user", "password": "vpn_password"})
        acc = Account(
            name=name,
            provider="expressvpn",
            credentials_enc=creds_enc,
            max_devices=max_devices,
            reserved_devices=reserved,
        )
        session.add(acc)
        session.commit()
        session.refresh(acc)
        return acc.id


def test_tunnel_creation_and_quota(app_state, monkeypatch):
    # Mock adapter list_locations & build_tunnel
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )
    account_id = _create_test_account(app_state, max_devices=3, reserved=1)
    # Allowed tunnels = 3 - 1 = 2

    manager: TunnelManager = app_state.manager

    # 1. Create first tunnel
    t1 = manager.create(
        TunnelCreate(
            name="tunnel-1",
            account_id=account_id,
            country="Japan",
            rotation_mode=RotationMode.MANUAL,
        )
    )
    assert t1.id is not None
    assert t1.socks_port == 11000
    assert t1.http_port == 12000
    assert t1.status == TunnelStatus.CONNECTING
    assert app_state.runtime.state(t1.id).vpn_running is True

    # 2. Create second tunnel
    t2 = manager.create(
        TunnelCreate(
            name="tunnel-2",
            account_id=account_id,
            country="Japan",
            rotation_mode=RotationMode.MANUAL,
        )
    )
    assert t2.socks_port == 11001
    assert t2.http_port == 12001

    # 3. Third tunnel should be rejected (quota exceeded: 2 used >= 2 allowed)
    with pytest.raises(TunnelError, match="Device limit reached"):
        manager.create(
            TunnelCreate(
                name="tunnel-3",
                account_id=account_id,
                country="Japan",
                rotation_mode=RotationMode.MANUAL,
            )
        )


def test_tunnel_duplicate_name(app_state, monkeypatch):
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )
    account_id = _create_test_account(app_state)
    manager: TunnelManager = app_state.manager

    manager.create(
        TunnelCreate(
            name="same-name",
            account_id=account_id,
            country="Japan",
        )
    )

    with pytest.raises(TunnelError, match="already exists"):
        manager.create(
            TunnelCreate(
                name="same-name",
                account_id=account_id,
                country="Japan",
            )
        )


def test_tunnel_rotation(app_state, monkeypatch):
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )
    account_id = _create_test_account(app_state)
    manager: TunnelManager = app_state.manager

    t = manager.create(
        TunnelCreate(
            name="rotate-me",
            account_id=account_id,
            country="Japan",
            proxy_user="myuser",
            proxy_password="mypassword123456",
        )
    )

    orig_socks = t.socks_port
    orig_http = t.http_port
    orig_user = t.proxy_user
    orig_pass = app_state.vault.decrypt(t.proxy_pass_enc)

    # Perform rotation
    rotated = manager.rotate(t.id, reason="test_rotate")

    # Verify ports and proxy credentials stay identical
    assert rotated.socks_port == orig_socks
    assert rotated.http_port == orig_http
    assert rotated.proxy_user == orig_user
    assert app_state.vault.decrypt(rotated.proxy_pass_enc) == orig_pass
    assert rotated.last_rotated_at is not None


def test_tunnel_stop_start_delete(app_state, monkeypatch):
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )
    account_id = _create_test_account(app_state)
    manager: TunnelManager = app_state.manager

    t = manager.create(
        TunnelCreate(
            name="lifecycle-tunnel",
            account_id=account_id,
            country="Japan",
        )
    )

    # Stop tunnel
    stopped = manager.stop(t.id)
    assert stopped.status == TunnelStatus.STOPPED
    assert app_state.runtime.state(t.id) is None

    # Start tunnel
    started = manager.start(t.id)
    assert started.status == TunnelStatus.CONNECTING
    assert app_state.runtime.state(t.id).vpn_running is True

    # Delete tunnel
    manager.delete(t.id)
    assert app_state.runtime.state(t.id) is None
    with session_scope() as session:
        assert session.get(Tunnel, t.id) is None


def test_log_redaction(app_state, monkeypatch):
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )
    account_id = _create_test_account(app_state)
    manager: TunnelManager = app_state.manager

    t = manager.create(
        TunnelCreate(
            name="log-tunnel",
            account_id=account_id,
            country="Japan",
            proxy_password="secretpassword999",
        )
    )

    logs = manager.logs(t.id)
    # The proxy password must be redacted
    assert "secretpassword999" not in logs
    assert "***" in logs
