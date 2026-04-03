# ARCH 001: Internal Single-Tenant Automated Novel-to-Video Workflow

## Objective
Build a modular, CPU-stable, internal-only system that converts novels into reviewable video assets with subtitles and quality gates. The architecture optimizes for long-term maintainability, controlled automation, and auditability rather than shortest initial implementation effort.

## Constraints
- Runtime target is a remote host that already operates under `/mnt/hdo/infra-core`.
- Baseline deployment uses containers and module-level compose management.
- Baseline review assumes image-capable multimodal models, not full video-understanding models.
- The product stops at internal asset output and review completion; it does not auto-publish.
- `OpenClaw`, `Codex`, and `Claude Code` are allowed as automation runners but not as production truth sources.

## Topology
Deploy as a new module: `/mnt/hdo/infra-core/modules/av-workflow`.

Primary services:
- `av-api`: internal entry point for job submission, status, and artifact access.
- `av-temporal`: workflow engine for retries, fan-out, compensation, and replay.
- `av-postgres`: state, manifests, review records, and policy decisions.
- `av-minio`: artifact storage for text snapshots, frames, clips, subtitles, audio, and outputs.
- `av-worker-ingest`: source normalization and chapter extraction.
- `av-worker-plan`: `StorySpec` and `ShotPlan` generation.
- `av-worker-compose`: deterministic `ffmpeg` composition, subtitle packaging, audio merge, and frame extraction.
- `av-worker-review`: technical QA, image-frame semantic review, and policy evaluation.
- `av-render-adapter`, `av-review-adapter`, `av-tts-adapter`: controlled external API adapters.
- `av-agent-gateway`: controlled proposal entrypoint for `OpenClaw`, `Codex`, and `Claude Code`.

Network model:
- `infra_gateway_net`: only `av-api` joins this network for Traefik exposure.
- `av_workflow_net`: module-private traffic for API, workflow, storage, and workers.
- Module-level egress sidecar or controlled outbound adapter path for external model calls.

## Core Contracts
The production truth is the contract set, not free-form prompts:
- `Job`
- `SourceDocument`
- `StorySpec`
- `ShotPlan`
- `AssetManifest`
- `ReviewCase`
- `PolicyDecision`
- `OutputPackage`

All contracts must be versioned snapshots. Historical versions remain readable. New work may derive from prior versions but may not overwrite them.

## Review and Quality Loop
The baseline review loop has four gates:
1. Structure validation for source, story, shot, and subtitle contracts.
2. Deterministic media QA using local tools such as `ffprobe`, subtitle layout checks, and frame-level media checks.
3. Image semantic review on extracted frames from each shot.
4. Policy decision that chooses continue, scoped retry, quarantine, or manual hold.

The system must not depend on video-understanding models for the baseline path. Video-level semantic review remains an optional enhancement.

## Agent Control Plane
`OpenClaw`, `Codex`, and `Claude Code` may produce proposals, repair hints, plans, prompt revisions, and review summaries. They may not:
- mark output as deliverable
- directly update final workflow state
- delete immutable artifacts
- bypass policy evaluation

All agent output must pass through `av-agent-gateway`, schema validation, and policy gating before it can influence execution.

## Configuration Model
Use five layers:
- `config/defaults/`
- `config/profiles/`
- `config/modules/`
- secrets from runtime environment or mounted files
- scoped runtime overrides for approved fields only

Common user-maintained configuration should stay limited to presets, review thresholds, adapter choices, and job-level overrides.

## Review Checkpoints
Each phase requires explicit review:
- requirements review
- architecture review
- contract review
- test review
- operations review

Stable rules belong in `AGENTS.md`. Operator usage belongs in `README.md`. Dated rationale belongs in `docs/decision-log.md`. Recurring failures belong in `docs/issue_solution_log.md`.
