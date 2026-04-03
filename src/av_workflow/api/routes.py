from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from av_workflow.contracts.models import Job


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_mode: str
    source_ref: str
    output_preset: str
    profile_id: str
    language: str
    review_level: str


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    current_stage: str
    source_ref: str
    output_preset: str
    profile_id: str


class ArtifactSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    final_video_ref: str | None = None
    subtitle_refs: list[str] = Field(default_factory=list)
    preview_refs: list[str] = Field(default_factory=list)
    cover_refs: list[str] = Field(default_factory=list)


class InMemoryApiStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._artifacts: dict[str, ArtifactSummary] = {}
        self._counter = 0

    def create_job(self, request: JobCreateRequest) -> Job:
        self._counter += 1
        job_id = f"job-{self._counter:04d}"
        job = Job(
            job_id=job_id,
            input_mode=request.input_mode,
            source_ref=request.source_ref,
            output_preset=request.output_preset,
            profile_id=request.profile_id,
            language=request.language,
            review_level=request.review_level,
        )
        self._jobs[job_id] = job
        self._artifacts[job_id] = ArtifactSummary(job_id=job_id)
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def get_artifacts(self, job_id: str) -> ArtifactSummary | None:
        return self._artifacts.get(job_id)


def build_router(*, store: InMemoryApiStore) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["workflow"])

    @router.post("/jobs", response_model=JobSummary, status_code=status.HTTP_201_CREATED)
    def create_job(request: JobCreateRequest) -> JobSummary:
        job = store.create_job(request)
        return JobSummary(
            job_id=job.job_id,
            status=job.status.value,
            current_stage=job.current_stage,
            source_ref=job.source_ref,
            output_preset=job.output_preset,
            profile_id=job.profile_id,
        )

    @router.get("/jobs/{job_id}", response_model=JobSummary)
    def get_job(job_id: str) -> JobSummary:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
        return JobSummary(
            job_id=job.job_id,
            status=job.status.value,
            current_stage=job.current_stage,
            source_ref=job.source_ref,
            output_preset=job.output_preset,
            profile_id=job.profile_id,
        )

    @router.get("/jobs/{job_id}/artifacts", response_model=ArtifactSummary)
    def get_artifacts(job_id: str) -> ArtifactSummary:
        artifacts = store.get_artifacts(job_id)
        if artifacts is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
        return artifacts

    return router
