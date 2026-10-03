"""Dashboard login/logout."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import SESSION_COOKIE, get_state, require_auth
from app.schemas import LoginIn
from app.security import constant_time_equals, issue_session
from app.state import AppState

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, state: AppState = Depends(get_state)):
    s = state.settings
    client = request.client.host if request.client else "unknown"
    if state.throttle.is_locked(client):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts, try later")
    ok = constant_time_equals(body.username, s.admin_username) & constant_time_equals(
        body.password, s.admin_password
    )
    if not ok:
        state.throttle.record_failure(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    state.throttle.reset(client)
    token = issue_session(s.session_secret, body.username, s.session_ttl_hours)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=s.secure_cookies,
        samesite="strict",
        max_age=s.session_ttl_hours * 3600,
    )
    return {"username": body.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: str = Depends(require_auth)):
    return {"username": user}
