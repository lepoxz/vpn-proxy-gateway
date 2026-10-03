"""FastAPI dependencies: app state and authentication."""

from fastapi import Depends, HTTPException, Request, status

from app.security import constant_time_equals, verify_session
from app.state import AppState

SESSION_COOKIE = "vpg_session"


def get_state(request: Request) -> AppState:
    return request.app.state.vpg


def require_auth(request: Request, state: AppState = Depends(get_state)) -> str:
    """Accept a dashboard session cookie, ``X-API-Key`` header, or ``Authorization: Bearer <api key>``."""
    s = state.settings
    api_key = request.headers.get("x-api-key")
    auth = request.headers.get("authorization", "")
    if not api_key and auth.lower().startswith("bearer "):
        api_key = auth[7:].strip()
    if api_key:
        if s.api_key and constant_time_equals(api_key, s.api_key):
            return "api"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    token = request.cookies.get(SESSION_COOKIE)
    if token and (user := verify_session(s.session_secret, token)):
        return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
