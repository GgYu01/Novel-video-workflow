from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from av_workflow.contracts.enums import JobStatus
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


class StageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    current_stage: str
    retry_count: int
    max_auto_retries: int


class ArtifactSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    final_video_ref: str | None = None
    audio_refs: list[str] = Field(default_factory=list)
    primary_audio_ref: str | None = None
    subtitle_refs: list[str] = Field(default_factory=list)
    preview_refs: list[str] = Field(default_factory=list)
    cover_refs: list[str] = Field(default_factory=list)
    shot_assets: list["ShotArtifactSummary"] = Field(default_factory=list)


class ShotArtifactSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    shot_id: str
    clip_ref: str
    frame_refs: list[str] = Field(default_factory=list)


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

    def update_job_stage(self, job_id: str, status: JobStatus, current_stage: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        updated = job.model_copy(update={"status": status, "current_stage": current_stage})
        self._jobs[job_id] = updated
        return updated

    def record_artifacts(
        self,
        job_id: str,
        *,
        subtitle_refs: list[str] | None = None,
        audio_refs: list[str] | None = None,
        primary_audio_ref: str | None = None,
        preview_refs: list[str] | None = None,
        cover_refs: list[str] | None = None,
        final_video_ref: str | None = None,
    ) -> ArtifactSummary:
        artifacts = self._artifacts.get(job_id)
        if artifacts is None:
            raise KeyError(job_id)
        updated = artifacts.model_copy(
            update={
                "subtitle_refs": subtitle_refs if subtitle_refs is not None else artifacts.subtitle_refs,
                "audio_refs": audio_refs if audio_refs is not None else artifacts.audio_refs,
                "primary_audio_ref": (
                    primary_audio_ref if primary_audio_ref is not None else artifacts.primary_audio_ref
                ),
                "preview_refs": preview_refs if preview_refs is not None else artifacts.preview_refs,
                "cover_refs": cover_refs if cover_refs is not None else artifacts.cover_refs,
                "final_video_ref": final_video_ref if final_video_ref is not None else artifacts.final_video_ref,
            }
        )
        self._artifacts[job_id] = updated
        return updated

    def record_shot_artifacts(
        self,
        job_id: str,
        *,
        shot_id: str,
        clip_ref: str,
        frame_refs: list[str],
    ) -> ShotArtifactSummary:
        artifacts = self._artifacts.get(job_id)
        if artifacts is None:
            raise KeyError(job_id)
        shot_artifact = ShotArtifactSummary(
            job_id=job_id,
            shot_id=shot_id,
            clip_ref=clip_ref,
            frame_refs=frame_refs,
        )
        shot_assets = [item for item in artifacts.shot_assets if item.shot_id != shot_id]
        shot_assets.append(shot_artifact)
        self._artifacts[job_id] = artifacts.model_copy(update={"shot_assets": shot_assets})
        return shot_artifact

    def get_shot_artifacts(self, job_id: str, shot_id: str) -> ShotArtifactSummary | None:
        artifacts = self._artifacts.get(job_id)
        if artifacts is None:
            return None
        for shot_artifact in artifacts.shot_assets:
            if shot_artifact.shot_id == shot_id:
                return shot_artifact
        return None


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

    @router.get("/jobs/{job_id}/stage", response_model=StageSummary)
    def get_stage(job_id: str) -> StageSummary:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
        return StageSummary(
            job_id=job.job_id,
            status=job.status.value,
            current_stage=job.current_stage,
            retry_count=job.retry_count,
            max_auto_retries=job.max_auto_retries,
        )

    @router.get("/jobs/{job_id}/artifacts", response_model=ArtifactSummary)
    def get_artifacts(job_id: str) -> ArtifactSummary:
        artifacts = store.get_artifacts(job_id)
        if artifacts is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
        return artifacts

    @router.get("/jobs/{job_id}/shots/{shot_id}/artifacts", response_model=ShotArtifactSummary)
    def get_shot_artifacts(job_id: str, shot_id: str) -> ShotArtifactSummary:
        shot_artifacts = store.get_shot_artifacts(job_id, shot_id)
        if shot_artifacts is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
        return shot_artifacts

    return router
