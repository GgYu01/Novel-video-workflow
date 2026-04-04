from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from av_workflow.adapters.render import (
    ApiRenderBackendAdapter,
    DeterministicLocalRenderAdapter,
    RenderAdapter,
    RoutingRenderAdapter,
)
from av_workflow.adapters.tts import DeterministicLocalTTSAdapter
from av_workflow.config.loader import ConfigLoader
from av_workflow.config.models import AppConfig
from av_workflow.runtime.ffmpeg import FfmpegExecutor, SubprocessFfmpegExecutor
from av_workflow.runtime.workspace import RuntimeWorkspace
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.job_execution import DeterministicLocalJobExecutionService
from av_workflow.services.planning import DeterministicPlanningService, HeuristicChapterShotPlanner
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.story_bible import DeterministicStoryBibleService


@dataclass(frozen=True)
class JobExecutionServiceFactory:
    config: AppConfig
    runtime_root: Path
    ffmpeg_executor: FfmpegExecutor

    def create(self, *, job_id: str) -> DeterministicLocalJobExecutionService:
        workspace = RuntimeWorkspace(root_dir=self.runtime_root)
        render_adapter = build_render_adapter(
            config=self.config,
            workspace=workspace,
            ffmpeg_executor=self.ffmpeg_executor,
        )
        render_job_service = DeterministicRenderJobService(render_adapter=render_adapter)
        planning_service = DeterministicPlanningService(
            shot_planner=HeuristicChapterShotPlanner(),
            story_bible_service=DeterministicStoryBibleService(),
        )
        audio_timeline_service = DeterministicAudioTimelineService(
            tts_adapter=DeterministicLocalTTSAdapter(workspace=workspace, job_id=job_id)
        )
        return DeterministicLocalJobExecutionService(
            runtime_root=self.runtime_root,
            planning_service=planning_service,
            render_job_service=render_job_service,
            audio_timeline_service=audio_timeline_service,
            ffmpeg_executor=self.ffmpeg_executor,
        )


def build_job_execution_service_factory(
    *,
    config_root: str | Path,
    runtime_root: str | Path,
    profile_name: str | None = None,
    module_names: Sequence[str] | None = None,
    ffmpeg_executor: FfmpegExecutor | None = None,
) -> JobExecutionServiceFactory:
    loader = ConfigLoader(config_root)
    config = loader.load(
        profile_name=profile_name,
        module_names=list(module_names or ["render", "audio", "review"]),
    )
    return JobExecutionServiceFactory(
        config=config,
        runtime_root=Path(runtime_root),
        ffmpeg_executor=ffmpeg_executor or SubprocessFfmpegExecutor(),
    )


def build_job_execution_service_factory_from_env() -> JobExecutionServiceFactory:
    repo_root = Path(__file__).resolve().parents[3]
    config_root = Path(os.environ.get("AV_WORKFLOW_CONFIG_ROOT", str(repo_root / "config")))
    runtime_root = Path(os.environ.get("AV_WORKFLOW_RUNTIME_ROOT", str(repo_root / "runtime")))
    profile_name = os.environ.get("AV_WORKFLOW_CONFIG_PROFILE") or None
    module_names = _parse_module_names(os.environ.get("AV_WORKFLOW_CONFIG_MODULES"))
    return build_job_execution_service_factory(
        config_root=config_root,
        runtime_root=runtime_root,
        profile_name=profile_name,
        module_names=module_names,
    )


def build_render_adapter(
    *,
    config: AppConfig,
    workspace: RuntimeWorkspace,
    ffmpeg_executor: FfmpegExecutor,
) -> RenderAdapter:
    if config.render.mode == "deterministic_local":
        return DeterministicLocalRenderAdapter(
            workspace=workspace,
            ffmpeg_executor=ffmpeg_executor,
        )
    if config.render.mode == "routed_api":
        return RoutingRenderAdapter(
            image_adapter=ApiRenderBackendAdapter(
                base_url=config.render.image_endpoint.base_url,
                submit_path=config.render.image_endpoint.submit_path,
                timeout_sec=config.render.image_endpoint.timeout_sec,
            ),
            wan_adapter=ApiRenderBackendAdapter(
                base_url=config.render.wan_endpoint.base_url,
                submit_path=config.render.wan_endpoint.submit_path,
                timeout_sec=config.render.wan_endpoint.timeout_sec,
            ),
        )
    raise ValueError(f"Unsupported render mode: {config.render.mode}")


def _parse_module_names(value: str | None) -> list[str]:
    if value is None:
        return ["render", "audio", "review"]
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or ["render", "audio", "review"]
