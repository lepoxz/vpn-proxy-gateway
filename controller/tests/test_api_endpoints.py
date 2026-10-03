"""API integration tests for all REST endpoints."""


def test_auth_flow(client):
    # 1. Unauthenticated request
    res = client.get("/api/overview")
    assert res.status_code == 401

    # 2. Failed login
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401

    # 3. Successful login
    res = client.post("/api/auth/login", json={"username": "admin", "password": "testpassword123"})
    assert res.status_code == 200
    assert res.json()["username"] == "admin"

    # 4. Authenticated request
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["username"] == "admin"

    # 5. Logout
    res = client.post("/api/auth/logout")
    assert res.status_code == 200

    # 6. Request after logout fails
    res = client.get("/api/overview")
    assert res.status_code == 401


def test_accounts_crud(auth_client):
    # 1. Create account
    create_res = auth_client.post(
        "/api/accounts",
        json={
            "name": "my-vpn-account",
            "provider": "expressvpn",
            "credentials": {"username": "exp_u", "password": "exp_p"},
            "max_devices": 8,
            "reserved_devices": 2,
        },
    )
    assert create_res.status_code == 201
    acc_id = create_res.json()["id"]
    assert create_res.json()["tunnels_allowed"] == 6

    # 2. List accounts
    list_res = auth_client.get("/api/accounts")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Patch account
    patch_res = auth_client.patch(f"/api/accounts/{acc_id}", json={"name": "renamed-vpn"})
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "renamed-vpn"

    # 4. Delete account
    del_res = auth_client.delete(f"/api/accounts/{acc_id}")
    assert del_res.status_code == 204


def test_tunnels_api_flow(auth_client, monkeypatch, app_state):
    # Mock adapter locations
    adapter = app_state.registry.get("expressvpn")
    monkeypatch.setattr(
        adapter, "list_locations", lambda: [type("Loc", (), {"country": "Japan", "city": None})()]
    )

    # Create account first
    acc_res = auth_client.post(
        "/api/accounts",
        json={
            "name": "tun-test-acc",
            "provider": "expressvpn",
            "credentials": {"username": "u", "password": "p"},
            "max_devices": 5,
            "reserved_devices": 1,
        },
    )
    acc_id = acc_res.json()["id"]

    # 1. Create tunnel
    create_res = auth_client.post(
        "/api/tunnels",
        json={
            "name": "api-proxy-jp",
            "account_id": acc_id,
            "country": "Japan",
            "rotation_mode": "manual",
        },
    )
    assert create_res.status_code == 201
    tun_id = create_res.json()["id"]
    assert create_res.json()["proxy"]["socks_port"] == 11000
    assert create_res.json()["proxy"]["socks5_url"].startswith("socks5h://")

    # 2. List tunnels
    list_res = auth_client.get("/api/tunnels")
    assert list_res.status_code == 200
    assert any(t["id"] == tun_id for t in list_res.json())

    # 3. Rotate tunnel
    rotate_res = auth_client.post(f"/api/tunnels/{tun_id}/rotate")
    assert rotate_res.status_code == 200

    # 4. Check tunnel
    check_res = auth_client.post(f"/api/tunnels/{tun_id}/check")
    assert check_res.status_code == 200

    # 5. Get traffic
    traffic_res = auth_client.get(f"/api/tunnels/{tun_id}/traffic?range=24")
    assert traffic_res.status_code == 200
    assert "points" in traffic_res.json()

    # 6. Get logs
    logs_res = auth_client.get(f"/api/tunnels/{tun_id}/logs")
    assert logs_res.status_code == 200

    # 7. Stop and Start
    stop_res = auth_client.post(f"/api/tunnels/{tun_id}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "stopped"

    start_res = auth_client.post(f"/api/tunnels/{tun_id}/start")
    assert start_res.status_code == 200

    # 8. Delete tunnel
    del_res = auth_client.delete(f"/api/tunnels/{tun_id}")
    assert del_res.status_code == 204


def test_misc_endpoints(auth_client):
    # Overview
    ov_res = auth_client.get("/api/overview")
    assert ov_res.status_code == 200
    assert "tunnels_total" in ov_res.json()

    # Providers
    prov_res = auth_client.get("/api/providers")
    assert prov_res.status_code == 200
    assert len(prov_res.json()) >= 2

    # Events
    events_res = auth_client.get("/api/events")
    assert events_res.status_code == 200
    assert isinstance(events_res.json(), list)
