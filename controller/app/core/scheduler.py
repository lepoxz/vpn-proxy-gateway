"""Background jobs: health checks, traffic sampling, retention, scheduled rotations."""

import logging

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import select

from app.config import Settings
from app.core.monitor import HealthChecker, TrafficCollector
from app.core.tunnels import TunnelError, TunnelManager
from app.db import session_scope
from app.models import RotationMode, Tunnel, TunnelStatus

log = logging.getLogger(__name__)


def _rotation_job_id(tunnel_id: int) -> str:
    return f"rotate-{tunnel_id}"


class Jobs:
    def __init__(
        self,
        settings: Settings,
        manager: TunnelManager,
        health: HealthChecker,
        traffic: TrafficCollector,
    ):
        self.settings = settings
        self.manager = manager
        self.health = health
        self.traffic = traffic
        self.scheduler = BackgroundScheduler(
            timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 30}
        )
        manager.on_policy_changed = self.sync_rotation

    def start(self) -> None:
        s = self.settings
        self.scheduler.add_job(self.health.check_all, IntervalTrigger(seconds=s.health_interval_seconds),
                               id="health")
        self.scheduler.add_job(self.traffic.collect, IntervalTrigger(seconds=s.traffic_interval_seconds),
                               id="traffic")
        self.scheduler.add_job(self.traffic.cleanup, CronTrigger(hour=3, minute=17), id="cleanup")
        with session_scope() as session:
            for t in session.exec(select(Tunnel)).all():
                self._apply_rotation(t)
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # -- rotation ------------------------------------------------------------------

    def _rotate(self, tunnel_id: int) -> None:
        with session_scope() as session:
            t = session.get(Tunnel, tunnel_id)
            if t is None or t.status in (TunnelStatus.STOPPED, TunnelStatus.LEAK_BLOCKED):
                return
        try:
            self.manager.rotate(tunnel_id, reason="scheduled")
        except TunnelError as exc:
            log.error("Scheduled rotation failed for tunnel %s: %s", tunnel_id, exc)

    def _apply_rotation(self, t: Tunnel) -> None:
        job_id = _rotation_job_id(t.id)
        try:
            self.scheduler.remove_job(job_id)
        except JobLookupError:
            pass
        trigger = None
        if t.rotation_mode == RotationMode.INTERVAL and t.rotation_interval_minutes:
            trigger = IntervalTrigger(minutes=t.rotation_interval_minutes)
        elif t.rotation_mode == RotationMode.CRON and t.rotation_cron:
            trigger = CronTrigger.from_crontab(t.rotation_cron, timezone="UTC")
        if trigger:
            self.scheduler.add_job(self._rotate, trigger, args=[t.id], id=job_id, replace_existing=True)

    def sync_rotation(self, tunnel_id: int) -> None:
        with session_scope() as session:
            t = session.get(Tunnel, tunnel_id)
        if t is None:
            try:
                self.scheduler.remove_job(_rotation_job_id(tunnel_id))
            except JobLookupError:
                pass
            return
        self._apply_rotation(t)

    def next_rotation(self, tunnel_id: int):
        job = self.scheduler.get_job(_rotation_job_id(tunnel_id))
        return job.next_run_time if job else None
