"""
FastAPI application factory.

Using a factory function (create_app) rather than a module-level singleton
makes it trivial to inject test overrides via app.dependency_overrides
without touching global state.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from skillhub_eval.adapters.api.routes.eval import router as eval_router
from skillhub_eval.adapters.api.routes.bundle import router as bundle_router
from skillhub_eval.adapters.api.routes.taxonomy import router as taxonomy_router
from skillhub_eval.adapters.api.routes.conversations import router as conversations_router
from skillhub_eval.adapters.api.routes.chat import router as chat_router
from skillhub_eval.adapters.api.routes.exec import router as exec_router
from skillhub_eval.execution.consent import hydrate_exec_consent_from_db


class _NoCacheUiHtmlMiddleware(BaseHTTPMiddleware):
    """Prevent stale UI assets during active iteration (html + js)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        if (
            path.endswith(".html")
            or path.endswith(".js")
            or path.rstrip("/") == "/ui"
        ):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="SkillHub Evaluation Engine",
        version="0.1.0",
        description=(
            "Evaluation engine for SkillHub Skill bundles. "
            "Implements 1.3 v0.2 protocol contract."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(_NoCacheUiHtmlMiddleware)
    hydrate_exec_consent_from_db()

    # ── static UI (Task 11) ────────────────────────────────────────────────────
    ui_static = Path(__file__).parent.parent / "ui" / "static"
    if ui_static.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_static), html=True), name="ui")

    # ── routers ───────────────────────────────────────────────────────────────
    app.include_router(eval_router)
    app.include_router(exec_router)
    app.include_router(bundle_router)
    app.include_router(taxonomy_router)
    app.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
    app.include_router(chat_router, prefix="/conversations", tags=["conversations"])

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """确认台入口；根路径无页面，避免 404。"""
        return RedirectResponse(url="/ui/index.html")

    # ── health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": "skillhub-eval", "version": "0.1.0"}

    return app


# Module-level instance used by uvicorn entrypoint:
#   uvicorn skillhub_eval.adapters.api.app:app
app = create_app()
