"""VPN account management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_state, require_auth
from app.db import get_session
from app.models import Account
from app.providers.base import ProviderError
from app.schemas import AccountCreate, AccountOut, AccountUpdate
from app.state import AppState

router = APIRouter(prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(require_auth)])


def _out(state: AppState, session: Session, a: Account) -> AccountOut:
    return AccountOut(
        id=a.id,
        name=a.name,
        provider=a.provider,
        max_devices=a.max_devices,
        reserved_devices=a.reserved_devices,
        tunnels_used=state.manager.tunnels_used(session, a.id),
        tunnels_allowed=state.manager.tunnels_allowed(a),
        created_at=a.created_at,
    )


@router.get("", response_model=list[AccountOut])
def list_accounts(state: AppState = Depends(get_state), session: Session = Depends(get_session)):
    return [_out(state, session, a) for a in session.exec(select(Account).order_by(Account.id)).all()]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    body: AccountCreate, state: AppState = Depends(get_state), session: Session = Depends(get_session)
):
    if session.exec(select(Account).where(Account.name == body.name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Account '{body.name}' already exists")
    try:
        adapter = state.registry.get(body.provider)
        creds = adapter.normalize_credentials(body.credentials)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    max_devices = body.max_devices or adapter.default_max_devices
    if body.reserved_devices >= max_devices:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "reserved_devices must be lower than max_devices")
    account = Account(
        name=body.name,
        provider=adapter.name,
        credentials_enc=state.vault.encrypt_json(creds),
        max_devices=max_devices,
        reserved_devices=body.reserved_devices,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    state.events.record(session, "account_added", f"Account '{account.name}' ({adapter.display_name}) added")
    return _out(state, session, account)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    body: AccountUpdate,
    state: AppState = Depends(get_state),
    session: Session = Depends(get_session),
):
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    if body.name and body.name != account.name:
        if session.exec(select(Account).where(Account.name == body.name)).first():
            raise HTTPException(status.HTTP_409_CONFLICT, f"Account '{body.name}' already exists")
        account.name = body.name
    if body.credentials:
        try:
            creds = state.registry.get(account.provider).normalize_credentials(body.credentials)
        except ProviderError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        account.credentials_enc = state.vault.encrypt_json(creds)
    if body.max_devices is not None:
        account.max_devices = body.max_devices
    if body.reserved_devices is not None:
        account.reserved_devices = body.reserved_devices
    if account.reserved_devices >= account.max_devices:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "reserved_devices must be lower than max_devices")
    session.add(account)
    session.commit()
    return _out(state, session, account)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: int, state: AppState = Depends(get_state), session: Session = Depends(get_session)
):
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    if state.manager.tunnels_used(session, account_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Delete this account's tunnels first")
    session.delete(account)
    session.commit()
    state.events.record(session, "account_deleted", f"Account '{account.name}' deleted")
