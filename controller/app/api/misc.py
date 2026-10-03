"""Providers, events and dashboard overview."""

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.api.deps import get_state, require_auth
from app.db import get_session
from app.models import Account, Event, TrafficSample, Tunnel, utcnow
from app.providers.base import ProviderError
from app.schemas import EventOut
from app.state import AppState

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


@router.get("/providers", tags=["providers"])
def list_providers(state: AppState = Depends(get_state)):
    return [a.describe() for a in state.registry.all()]


@router.get("/providers/{name}/locations", tags=["providers"])
def provider_locations(name: str, state: AppState = Depends(get_state)):
    try:
        locs = state.registry.get(name).list_locations()
    except ProviderError as exc:
        raise HTTPException(400, str(exc)) from exc
    countries: dict[str, dict] = {}
    for loc in locs:
        entry = countries.setdefault(loc.country, {"country": loc.country, "code": loc.code, "cities": []})
        if loc.city and loc.city not in entry["cities"]:
            entry["cities"].append(loc.city)
    return sorted(countries.values(), key=lambda c: c["country"])


@router.get("/events", response_model=list[EventOut], tags=["events"])
def list_events(
    tunnel_id: int | None = None,
    level: str | None = Query(None, pattern="^(info|warning|error)$"),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    q = select(Event).order_by(Event.id.desc()).limit(limit)
    if tunnel_id is not None:
        q = q.where(Event.tunnel_id == tunnel_id)
    if level:
        q = q.where(Event.level == level)
    return session.exec(q).all()


@router.get("/overview", tags=["overview"])
def overview(state: AppState = Depends(get_state), session: Session = Depends(get_session)):
    tunnels = session.exec(select(Tunnel)).all()
    since = utcnow() - timedelta(hours=24)
    rx, tx = session.exec(
        select(
            func.coalesce(func.sum(TrafficSample.rx_bytes), 0),
            func.coalesce(func.sum(TrafficSample.tx_bytes), 0),
        ).where(TrafficSample.ts >= since)
    ).one()
    accounts = []
    for a in session.exec(select(Account).order_by(Account.id)).all():
        accounts.append(
            {
                "id": a.id,
                "name": a.name,
                "provider": a.provider,
                "used": sum(1 for t in tunnels if t.account_id == a.id),
                "allowed": state.manager.tunnels_allowed(a),
                "max_devices": a.max_devices,
            }
        )
    return {
        "tunnels_total": len(tunnels),
        "by_status": dict(Counter(t.status.value for t in tunnels)),
        "traffic_24h": {"rx_bytes": rx, "tx_bytes": tx},
        "accounts": accounts,
        "host_ip_known": state.health._real_ip is not None,
        "proxy_host": state.settings.public_host,
    }
