"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import accounts, auth, misc, tunnels
from app.config import get_settings
from app.core.runtime import DockerRuntime, FakeRuntime
from app.db import init_engine
from app.state import build_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("vpg")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine(settings.database_url)

    # Use DockerRuntime by default; if running in test/mock mode without docker socket, can fall back
    try:
        runtime = DockerRuntime(
            network=settings.docker_network,
            gluetun_image=settings.gluetun_image,
            gost_image=settings.gost_image,
        )
    except Exception as exc:
        log.warning("Could not initialize Docker runtime (%s), using FakeRuntime", exc)
        runtime = FakeRuntime()

    state = build_state(settings, runtime)
    app.state.vpg = state

    # Reconcile any existing containers
    try:
        state.manager.reconcile()
    except Exception as exc:
        log.warning("Reconcile on startup error: %s", exc)

    if settings.enable_scheduler:
        state.jobs.start()

    yield

    if settings.enable_scheduler:
        state.jobs.shutdown()
    if hasattr(state, "http") and state.http:
        state.http.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="VPN Proxy Gateway",
        description="Turn paid VPN subscriptions into authenticated SOCKS5/HTTP proxies with kill-switch.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(tunnels.router)
    app.include_router(misc.router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        from fastapi.responses import FileResponse

        @app.get("/")
        async def index():
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url="/docs")

        @app.get("/{full_path:path}")
        async def catch_all(full_path: str):
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not Found")

    return app


app = create_app()
