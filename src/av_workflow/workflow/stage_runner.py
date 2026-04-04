from __future__ import annotations

from dataclasses import dataclass

from av_workflow.contracts.enums import JobStatus, PolicyAction
from av_workflow.contracts.models import (
    AssetManifest,
    AudioMixManifest,
    Job,
    OutputPackage,
    PolicyDecision,
    ReviewCase,
    ShotPlan,
    ShotPlanSet,
    ShotRenderResult,
    SourceDocument,
    StorySpec,
    VoiceCast,
)
from av_workflow.services.audio_mix import build_audio_mix_manifest
from av_workflow.services.audio_timeline import DeterministicAudioTimelineService
from av_workflow.services.compose import assemble_output_package, build_asset_manifest
from av_workflow.services.ingest import normalize_source
from av_workflow.services.planning import DeterministicPlanningService
from av_workflow.services.render_jobs import DeterministicRenderJobService
from av_workflow.services.review.technical import evaluate_asset_manifest
from av_workflow.policy.engine import PolicyEngine
from av_workflow.workflow.engine import WorkflowEngine


@dataclass(frozen=True)
class StageRunResult:
    initial_job: Job
    final_job: Job
    source_document: SourceDocument
    story_spec: StorySpec
    shot_plan_set: ShotPlanSet
    voice_cast: VoiceCast
    render_results: dict[str, ShotRenderResult]
    audio_mix_manifest: AudioMixManifest
    asset_manifest: AssetManifest
    review_case: ReviewCase
    output_package: OutputPackage


class DeterministicStageRunner:
    def __init__(
        self,
        *,
        workflow_engine: WorkflowEngine | None = None,
        planning_service: DeterministicPlanningService | None = None,
        audio_timeline_service: DeterministicAudioTimelineService | None = None,
        render_job_service: DeterministicRenderJobService | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.workflow_engine = workflow_engine or WorkflowEngine()
        self.planning_service = planning_service
        self.audio_timeline_service = audio_timeline_service
        self.render_job_service = render_job_service
        self.policy_engine = policy_engine or PolicyEngine(semantic_threshold=0.9)

    def normalize(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.NORMALIZED)

    def plan(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.PLANNED)

    def request_render(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.RENDER_REQUESTED)

    def mark_render_ready(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.RENDER_READY)

    def mark_audio_ready(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.AUDIO_READY)

    def mark_composed(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.COMPOSED)

    def mark_technical_review_passed(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.QA_TECHNICAL_PASSED)

    def mark_semantic_review_passed(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.QA_SEMANTIC_PASSED)

    def mark_output_ready(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.OUTPUT_READY)

    def complete(self, job: Job) -> Job:
        return self.workflow_engine.advance(job, JobStatus.COMPLETED)

    def run(self, *, job: Job, raw_text: str) -> StageRunResult:
        if not self.planning_service or not self.audio_timeline_service or not self.render_job_service:
            raise ValueError("Stage runner requires planning, audio, and render services for run().")
        source_document = normalize_source(job, raw_text)
        normalized_job = self.normalize(job)
        story_spec = self.planning_service.build_story_spec(source_document)
        shot_plan_set = self.planning_service.generate_shot_plan_set(
            source_document=source_document,
            story_spec=story_spec,
            output_preset=job.output_preset,
        )
        planned_job = self.plan(normalized_job)
        voice_cast = self.audio_timeline_service.build_voice_cast(
            source_document=source_document,
            story_spec=story_spec,
        )
        render_requested_job = self.request_render(planned_job)

        render_results: dict[str, ShotRenderResult] = {}
        rendered_shots: dict[str, dict[str, object]] = {}
        subtitle_refs: list[str] = []
        narration_refs: list[str] = []
        dialogue_refs: list[str] = []
        total_duration_ms = 0

        for shot_plan in shot_plan_set.shots:
            render_request = self.render_job_service.build_render_request(
                job_id=render_requested_job.job_id,
                shot_plan=shot_plan,
            )
            render_result = self.render_job_service.submit_render_request(render_request)
            render_results[shot_plan.shot_id] = render_result
            rendered_shots[shot_plan.shot_id] = {
                "clip_ref": render_result.clip_ref,
                "frame_refs": list(render_result.frame_refs),
                "render_metadata": dict(render_result.metadata),
            }

            timeline = self.audio_timeline_service.build_timeline(
                shot_plan=shot_plan,
                voice_cast=voice_cast,
            )
            total_duration_ms += timeline.total_duration_ms
            subtitle_refs.append(f"asset://subtitles/{job.job_id}/{shot_plan.shot_id}.srt")
            for segment in timeline.segments:
                audio_ref = segment.get("audio_ref")
                if not audio_ref:
                    continue
                if segment.get("speaker") == "narration":
                    narration_refs.append(str(audio_ref))
                else:
                    dialogue_refs.append(str(audio_ref))

        audio_mix_manifest = build_audio_mix_manifest(
            job=render_requested_job,
            narration_refs=narration_refs,
            dialogue_refs=dialogue_refs,
            duration_ms=total_duration_ms,
            bgm_ref=None,
            ambience_refs=[],
        )
        render_ready_job = self.mark_render_ready(render_requested_job)
        audio_ready_job = self.mark_audio_ready(render_ready_job)
        asset_manifest = build_asset_manifest(
            job=audio_ready_job,
            shot_plans=shot_plan_set.shots,
            rendered_shots=rendered_shots,
            subtitle_refs=subtitle_refs,
            audio_refs=[*narration_refs, *dialogue_refs],
            audio_mix_ref=audio_mix_manifest.mix_ref,
            preview_refs=[f"asset://preview/{job.job_id}.png"],
            cover_refs=[f"asset://cover/{job.job_id}.png"],
            final_video_ref=f"asset://video/{job.job_id}/final.mp4",
        )
        composed_job = self.mark_composed(audio_ready_job)
        review_case = evaluate_asset_manifest(
            job=composed_job,
            manifest=asset_manifest,
            media_metadata={
                asset_manifest.final_video_ref: {
                    "duration_sec": max(total_duration_ms / 1000.0, 1.0),
                    "video_streams": [{"width": 1280, "height": 720}],
                    "audio_streams": [{"sample_rate": 48000}],
                },
                audio_mix_manifest.mix_ref: {
                    "audio_streams": [{"sample_rate": 48000}],
                },
            },
            subtitle_reports={
                subtitle_ref: {
                    "cue_count": len(shot_plan_set.shots),
                    "max_line_length": 24,
                }
                for subtitle_ref in subtitle_refs
            },
        )
        reviewed_job = self.apply_review_case(composed_job, review_case)
        if reviewed_job.status is JobStatus.QA_TECHNICAL_PASSED:
            reviewed_job = self.mark_semantic_review_passed(reviewed_job)
            reviewed_job = self.mark_output_ready(reviewed_job)
            completed_job = self.complete(reviewed_job)
        else:
            completed_job = reviewed_job
        output_package = assemble_output_package(
            manifest=asset_manifest,
            review_summary_ref=f"asset://reviews/{job.job_id}/technical.json",
        )

        return StageRunResult(
            initial_job=job,
            final_job=completed_job,
            source_document=source_document,
            story_spec=story_spec,
            shot_plan_set=shot_plan_set,
            voice_cast=voice_cast,
            render_results=render_results,
            audio_mix_manifest=audio_mix_manifest,
            asset_manifest=asset_manifest,
            review_case=review_case,
            output_package=output_package,
        )

    def apply_review_case(self, job: Job, review_case: ReviewCase) -> Job:
        decision = self.policy_engine.evaluate_review(job, review_case)
        if decision.action is PolicyAction.CONTINUE:
            return self.mark_technical_review_passed(job)
        return self._apply_policy_decision(job, decision)

    def _apply_policy_decision(self, job: Job, decision: PolicyDecision) -> Job:
        if decision.action is PolicyAction.RETRY:
            if decision.resume_at is None:
                raise ValueError("Retry decisions require a resume_at status.")
            return self.workflow_engine.schedule_retry(job, resume_at=decision.resume_at)
        if decision.action is PolicyAction.MANUAL_HOLD:
            return self.workflow_engine.place_on_hold(job)
        if decision.action is PolicyAction.QUARANTINE:
            return self.workflow_engine.quarantine(job, reason=decision.reason_text)
        raise ValueError(f"Unsupported review policy action: {decision.action.value}")
