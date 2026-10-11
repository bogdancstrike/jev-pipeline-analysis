"""Composition root: settings -> platform (core + enabled modules) -> HTTP app."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.api.admin import router as admin_router
from .core.api.routes import router
from .core.config import Settings, get_settings
from .core.errors import install_error_handlers
from .core.modules import Module
from .core.observability import RequestIdMiddleware, configure_logging
from .core.platform import Platform
from .modules import CATALOG


def create_app(settings: Settings | None = None, catalog: list[type[Module]] | None = None,
               platform: Platform | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        p = platform or Platform.build(settings, catalog or CATALOG)
        app.state.platform = p
        await p.start()
        yield
        await p.stop()

    app = FastAPI(title="Text triage", version="2.0.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(RequestIdMiddleware)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                           allow_methods=["*"], allow_headers=["*"], expose_headers=["x-request-id"])
    install_error_handlers(app)
    app.include_router(router)
    app.include_router(admin_router)
    return app

