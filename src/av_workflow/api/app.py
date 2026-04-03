from __future__ import annotations

from fastapi import FastAPI

from av_workflow.api.routes import InMemoryApiStore, build_router


def create_app(*, store: InMemoryApiStore | None = None) -> FastAPI:
    app = FastAPI(title="av-workflow", version="0.1.0")
    api_store = store or InMemoryApiStore()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(build_router(store=api_store))
    return app


app = create_app()
