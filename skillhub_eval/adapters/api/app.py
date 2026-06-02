"""
FastAPI application factory.

Using a factory function (create_app) rather than a module-level singleton
makes it trivial to inject test overrides via app.dependency_overrides
without touching global state.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from skillhub_eval.adapters.api.routes.eval import router as eval_router
from skillhub_eval.adapters.api.routes.bundle import router as bundle_router


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

    # ── static UI (Task 11) ────────────────────────────────────────────────────
    ui_static = Path(__file__).parent.parent / "ui" / "static"
    if ui_static.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_static), html=True), name="ui")

    # ── routers ───────────────────────────────────────────────────────────────
    app.include_router(eval_router)
    app.include_router(bundle_router)

    # ── health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": "skillhub-eval", "version": "0.1.0"}

    return app


# Module-level instance used by uvicorn entrypoint:
#   uvicorn skillhub_eval.adapters.api.app:app
app = create_app()
