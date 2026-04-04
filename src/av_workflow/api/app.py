from __future__ import annotations

from fastapi import FastAPI

from av_workflow.api.routes import InMemoryApiStore, build_router
from av_workflow.runtime.bootstrap import (
    JobExecutionServiceFactory,
    build_job_execution_service_factory_from_env,
)


def create_app(
    *,
    store: InMemoryApiStore | None = None,
    execution_service_factory: JobExecutionServiceFactory | None = None,
) -> FastAPI:
    app = FastAPI(title="av-workflow", version="0.1.0")
    api_store = store or InMemoryApiStore()
    runtime_factory = execution_service_factory or build_job_execution_service_factory_from_env()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(build_router(store=api_store, execution_service_factory=runtime_factory))
    return app


app = create_app()
