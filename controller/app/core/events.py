"""Event log + outbound alerts (webhook / Telegram)."""

import logging
import threading

import httpx
from sqlmodel import Session

from app.config import Settings
from app.models import Event

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, settings: Settings, http: httpx.Client):
        self.settings = settings
        self.http = http

    @property
    def enabled(self) -> bool:
        s = self.settings
        return bool(s.webhook_url or (s.telegram_bot_token and s.telegram_chat_id))

    def send(self, level: str, kind: str, message: str, tunnel_id: int | None = None) -> None:
        if not self.enabled:
            return
        # Fire-and-forget so a slow webhook never blocks health checks.
        threading.Thread(
            target=self._send, args=(level, kind, message, tunnel_id), daemon=True
        ).start()

    def _send(self, level: str, kind: str, message: str, tunnel_id: int | None) -> None:
        s = self.settings
        try:
            if s.webhook_url:
                self.http.post(
                    s.webhook_url,
                    json={"level": level, "kind": kind, "message": message, "tunnel_id": tunnel_id},
                    timeout=10,
                )
            if s.telegram_bot_token and s.telegram_chat_id:
                icon = {"error": "🔴", "warning": "🟠"}.get(level, "🔵")
                self.http.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                    json={"chat_id": s.telegram_chat_id, "text": f"{icon} [VPG] {message}"},
                    timeout=10,
                )
        except httpx.HTTPError as exc:
            log.warning("Alert delivery failed: %s", exc)


class EventLog:
    def __init__(self, notifier: Notifier):
        self.notifier = notifier

    def record(
        self,
        session: Session,
        kind: str,
        message: str,
        *,
        tunnel_id: int | None = None,
        level: str = "info",
        alert: bool | None = None,
    ) -> None:
        session.add(Event(kind=kind, message=message, tunnel_id=tunnel_id, level=level))
        session.commit()
        log.log(
            {"error": logging.ERROR, "warning": logging.WARNING}.get(level, logging.INFO),
            "[%s] %s",
            kind,
            message,
        )
        should_alert = alert if alert is not None else level in ("warning", "error")
        if should_alert:
            self.notifier.send(level, kind, message, tunnel_id)
