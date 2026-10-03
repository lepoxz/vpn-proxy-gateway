"""Tunnel management, rotation, traffic and logs."""

from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from app.api.deps import get_state, require_auth
from app.core.tunnels import TunnelError
from app.db import get_session
from app.models import Account, TrafficSample, Tunnel, utcnow
from app.schemas import TrafficOut, TrafficPoint, TunnelCreate, TunnelOut, TunnelUpdate
from app.state import AppState

router = APIRouter(prefix="/api/tunnels", tags=["tunnels"], dependencies=[Depends(require_auth)])


def _http_error(exc: TunnelError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


def to_out(state: AppState, t: Tunnel, account: Account | None = None) -> TunnelOut:
    return TunnelOut(
        id=t.id,
        name=t.name,
        account_id=t.account_id,
        account_name=account.name if account else None,
        provider=account.provider if account else None,
        protocol=t.protocol,
        country=t.country,
        city=t.city,
        server=t.server,
        status=t.status,
        status_detail=t.status_detail,
        current_ip=t.current_ip,
        last_check_at=t.last_check_at,
        last_rotated_at=t.last_rotated_at,
        rotation_mode=t.rotation_mode,
        rotation_interval_minutes=t.rotation_interval_minutes,
        rotation_cron=t.rotation_cron,
        proxy=state.manager.proxy_info(t),
        created_at=t.created_at,
    )


def _get(session: Session, tunnel_id: int) -> Tunnel:
    t = session.get(Tunnel, tunnel_id)
    if t is None:
        raise HTTPException(404, "Tunnel not found")
    return t


def _fresh(state: AppState, session: Session, tunnel_id: int) -> TunnelOut:
    session.expire_all()
    t = _get(session, tunnel_id)
    return to_out(state, t, session.get(Account, t.account_id))


@router.get("", response_model=list[TunnelOut])
def list_tunnels(state: AppState = Depends(get_state), session: Session = Depends(get_session)):
    accounts = {a.id: a for a in session.exec(select(Account)).all()}
    tunnels = session.exec(select(Tunnel).order_by(Tunnel.id)).all()
    return [to_out(state, t, accounts.get(t.account_id)) for t in tunnels]


@router.post("", response_model=TunnelOut, status_code=201)
def create_tunnel(
    body: TunnelCreate, state: AppState = Depends(get_state), session: Session = Depends(get_session)
):
    try:
        t = state.manager.create(body)
    except TunnelError as exc:
        raise _http_error(exc) from exc
    return _fresh(state, session, t.id)


@router.get("/{tunnel_id}", response_model=TunnelOut)
def get_tunnel(tunnel_id: int, state: AppState = Depends(get_state), session: Session = Depends(get_session)):
    return _fresh(state, session, tunnel_id)


@router.patch("/{tunnel_id}", response_model=TunnelOut)
def update_tunnel(
    tunnel_id: int,
    body: TunnelUpdate,
    state: AppState = Depends(get_state),
    session: Session = Depends(get_session),
):
    try:
        state.manager.update_policy(tunnel_id, body.rotation, body.name)
    except TunnelError as exc:
        raise _http_error(exc) from exc
    return _fresh(state, session, tunnel_id)


@router.delete("/{tunnel_id}", status_code=204)
def delete_tunnel(tunnel_id: int, state: AppState = Depends(get_state)):
    try:
        state.manager.delete(tunnel_id)
    except TunnelError as exc:
        raise _http_error(exc) from exc


def _action(name: str):
    def handler(
        tunnel_id: int, state: AppState = Depends(get_state), session: Session = Depends(get_session)
    ):
        try:
            getattr(state.manager, name)(tunnel_id)
        except TunnelError as exc:
            raise _http_error(exc) from exc
        return _fresh(state, session, tunnel_id)

    handler.__name__ = f"{name}_tunnel"
    return handler


for _name, _doc in (
    ("rotate", "Reconnect to a different server (new exit IP). Port and credentials stay the same."),
    ("restart", "Recreate the tunnel containers."),
    ("stop", "Stop the tunnel and release its VPN device slot."),
    ("start", "Start a stopped (or leak-blocked) tunnel."),
):
    router.add_api_route(
        f"/{{tunnel_id}}/{_name}", _action(_name), methods=["POST"], response_model=TunnelOut, summary=_doc
    )


@router.post("/{tunnel_id}/check", response_model=TunnelOut)
def check_tunnel(
    tunnel_id: int, state: AppState = Depends(get_state), session: Session = Depends(get_session)
):
    """Run a health check immediately."""
    _get(session, tunnel_id)
    state.health.check_tunnel(tunnel_id)
    return _fresh(state, session, tunnel_id)


@router.get("/{tunnel_id}/traffic", response_model=TrafficOut)
def tunnel_traffic(
    tunnel_id: int,
    range_hours: int = Query(24, alias="range", ge=1, le=24 * 30),
    session: Session = Depends(get_session),
):
    _get(session, tunnel_id)
    since = utcnow() - timedelta(hours=range_hours)
    samples = session.exec(
        select(TrafficSample)
        .where(TrafficSample.tunnel_id == tunnel_id, TrafficSample.ts >= since)
        .order_by(TrafficSample.ts)
    ).all()
    # Bucket into ~120 points for charting.
    bucket = max(60, range_hours * 3600 // 120)
    agg: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for s in samples:
        key = int((s.ts - since).total_seconds() // bucket)
        agg[key][0] += s.rx_bytes
        agg[key][1] += s.tx_bytes
    n_buckets = range_hours * 3600 // bucket
    points = [
        TrafficPoint(ts=since + timedelta(seconds=i * bucket), rx_bytes=agg[i][0], tx_bytes=agg[i][1])
        for i in range(n_buckets + 1)
    ]
    return TrafficOut(
        tunnel_id=tunnel_id,
        range_hours=range_hours,
        total_rx=sum(s.rx_bytes for s in samples),
        total_tx=sum(s.tx_bytes for s in samples),
        points=points,
    )


@router.get("/{tunnel_id}/logs", response_class=PlainTextResponse)
def tunnel_logs(tunnel_id: int, tail: int = Query(200, ge=10, le=2000), state: AppState = Depends(get_state)):
    try:
        return state.manager.logs(tunnel_id, tail)
    except TunnelError as exc:
        raise _http_error(exc) from exc
