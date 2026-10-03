#!/usr/bin/env python3
"""Integration test script to verify with real VPN subscriptions on Linux / VPS.

Usage:
    export VPG_API_URL="http://localhost:8000"
    export VPG_ADMIN_USER="admin"
    export VPG_ADMIN_PASS="supersecretpassword"
    python scripts/test_live_vpn.py
"""

import os
import sys
import time
import httpx

API_URL = os.environ.get("VPG_API_URL", "http://localhost:8000").rstrip("/")
ADMIN_USER = os.environ.get("VPG_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("VPG_ADMIN_PASS", "supersecretpassword")


def log(msg, status="INFO"):
    icons = {"INFO": "ℹ️ ", "SUCCESS": "✅ ", "ERROR": "❌ ", "WARN": "⚠️ "}
    print(f"{icons.get(status, '')}[{status}] {msg}")


def main():
    log(f"Connecting to VPN Proxy Gateway at {API_URL}...")
    client = httpx.Client(base_url=API_URL, timeout=30)

    # 1. Login
    login_res = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    if login_res.status_code != 200:
        log(f"Login failed: {login_res.text}", "ERROR")
        sys.exit(1)
    log("Logged in successfully!", "SUCCESS")

    # 2. Get host public IP
    host_ip_res = httpx.get("https://api.ipify.org", timeout=10)
    host_ip = host_ip_res.text.strip()
    log(f"Server host real IP: {host_ip}", "INFO")

    # 3. Check registered accounts
    accounts = client.get("/api/accounts").json()
    if not accounts:
        log("No VPN accounts registered in the database. Please add an account first!", "WARN")
        return

    acc = accounts[0]
    log(f"Testing with account: {acc['name']} ({acc['provider'].upper()})", "INFO")

    # 4. List existing tunnels
    tunnels = client.get("/api/tunnels").json()
    log(f"Current tunnels count: {len(tunnels)}", "INFO")

    for t in tunnels:
        log(f"Checking tunnel '{t['name']}' (ID: {t['id']})...", "INFO")
        check_res = client.post(f"/api/tunnels/{t['id']}/check").json()
        egress_ip = check_res.get("current_ip")
        status = check_res.get("status")

        log(f"Tunnel Status: {status} | Egress IP: {egress_ip}", "INFO")

        # Kill-switch verification: egress IP must NOT equal host IP
        if egress_ip == host_ip:
            log(f"CRITICAL: Egress IP equals host real IP ({host_ip})! Kill-switch test failed!", "ERROR")
            sys.exit(1)
        elif egress_ip:
            log(f"Verified: Egress IP ({egress_ip}) is hidden and distinct from host IP ({host_ip})", "SUCCESS")

    log("Live VPN verification finished successfully!", "SUCCESS")


if __name__ == "__main__":
    main()
