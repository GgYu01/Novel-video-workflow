# Hybrid Shot Pipeline Design

## Status
Approved for implementation planning on 2026-04-03.

## Goal
Extend the current control-plane skeleton into a headless, remote-operable workflow that can turn a novel into a stitched video with multi-role voice tracks, subtitles, audio mix, deterministic review evidence, and scoped retries.

## Selected Approach
Three approaches were considered:

1. All-video generation for every shot.
2. Hybrid generation with image-first rendering and selective dynamic video rendering.
3. Cloud-first generation with local fallback.

The selected approach is option 2.

- Why: CPU-first execution on the shared remote host cannot sustain all-video generation at acceptable throughput or stability.
- Why: Most story shots are dialogue, atmosphere, or exposition shots that benefit more from strong visual consistency than from heavy motion.
- Why: Selective dynamic rendering keeps the system modular while allowing key moments to use `Wan2.2-TI2V-5B-GGUF`.

## Operating Model
The system remains internal single-tenant and stops at asset output. It does not auto-publish.

Agents are allowed to collaborate frequently, but only as control-plane workers:

- `codex`
- `claude_code`
- `openclaw`

They may:

- propose `StorySpec`, `CharacterBible`, `SceneBible`, and `ShotPlan` content
- suggest prompt repairs and retry hints
- review continuity and quality findings

They may not:

- mutate authoritative job state directly
- mark outputs deliverable
- bypass review or policy decisions

Authoritative state remains inside the workflow engine and persisted contracts.

## User-Facing Mental Model
Users should not see `ShotPlan` as a filmmaking term they must understand. In operator-facing language, it is the internal "shot execution sheet" generated automatically from the novel.

The external product flow is:

`novel -> story breakdown -> character/scene references -> shot execution sheet -> generated shot assets -> voices/subtitles -> final composition -> review -> output package`

## End-to-End Pipeline

### 1. Ingest
- Normalize the source text into `SourceDocument`.
- Split chapters, preserve provenance, and store immutable snapshots.

### 2. Story Synthesis
- Generate `StorySpec`.
- Extract `CharacterBible`, `SceneBible`, timeline anchors, style rules, and forbidden drift conditions.

### 3. Agent Swarm Proposal Stage
- Dispatch the current chapter bundle to the approved agent set.
- Collect structured proposals only.
- Require schema validation before any downstream use.

### 4. Shot Planning
- Build a `ShotPlanSet` from the story contracts.
- Each shot records narrative goal, duration target, character bindings, scene bindings, motion tier, render prompts, dialogue allocation, subtitle source, review targets, and fallback strategy.

### 5. Asset Generation
- Default path: generate a key image for each shot, then either keep it as a limited-motion shot or derive a short clip from it.
- `Wan` path: only for shots marked `motion_tier=wan_dynamic`.
- Optional user replacement is supported by binding a supplied asset to `shot_id` while preserving the rest of the automatic job.

### 6. Voice And Subtitle Timeline
- Build `VoiceCast` automatically for narrator and named roles.
- Split narration and dialogue into `DialogueTimeline` segments before TTS generation.
- Generate TTS per segment and use the resulting durations as the primary subtitle timing source.

### 7. Audio Mix
- Combine narrator, character dialogue, optional ambience, and optional BGM with deterministic loudness control and ducking.

### 8. Composition
- Stitch shot clips with `ffmpeg`.
- Burn a preview subtitle version and also emit sidecar subtitle files.
- Output chapter-level and job-level manifests.

### 9. Review
- Run technical QA first.
- Run frame-based semantic review next.
- Run continuity scoring across adjacent shots last.
- If quality fails, schedule scoped retry at `shot`, `scene`, or `chapter` scope only.

## Service Topology

### Core Services
- `av-api`: job submission, status, artifact lookup, and operator actions.
- `av-director`: durable orchestration entrypoint that assigns stage work and owns replay.
- `av-worker-planning`: ingest, story synthesis, and shot planning.
- `av-worker-render`: shot execution coordinator.
- `av-worker-audio`: voice casting, TTS generation, subtitle timing, and mix assembly.
- `av-worker-compose`: `ffmpeg` stitching, preview generation, and manifest assembly.
- `av-worker-review`: technical QA, semantic frame review, and continuity scoring.
- `av-agent-gateway`: guarded proposal ingress for `codex`, `claude_code`, and `openclaw`.

### Model Adapter Services
- `av-image-renderer`: local-first image generation API with future cloud fallback.
- `av-wan-renderer`: local asynchronous render-job API backed by packaged `ComfyUI` workflows and `QuantStack/Wan2.2-TI2V-5B-GGUF`.
- `av-tts-renderer`: local-first TTS API.
- `av-review-mm`: multimodal frame review API.

The workflow engine never calls ComfyUI or raw model runtimes directly. It calls stable internal adapter APIs.

## Key Contracts To Add
- `CharacterBible`
- `SceneBible`
- `ShotPlanSet`
- `VoiceCast`
- `DialogueTimeline`
- `ShotRenderJob`
- `ShotRenderResult`
- `AudioMixManifest`
- `ContinuityReviewCase`

Each contract must be immutable, versioned, and addressable by artifact reference.

## Rendering Strategy

### Motion Tiers
- `static`: still image with subtle zoom/pan or hold frame.
- `limited_motion`: image-derived motion clip, camera movement, or lightweight transform path.
- `wan_dynamic`: dynamic clip rendered by the local `Wan` backend.

### Selection Rules
- Dialogue and exposition default to `static` or `limited_motion`.
- Crowd surges, celebrations, fights, chases, or major emotional physical action may escalate to `wan_dynamic`.
- Retry logic may downgrade a failing `wan_dynamic` shot to `limited_motion` when the narrative impact stays acceptable.

## Voice Strategy
First implementation should support multi-role voice lines without reference voice cloning.

- `VoiceCast` assigns one stable local `voice_id` per narrator and per named role.
- The same character keeps the same voice across the job unless review explicitly requests reassignment.
- Dialogue and narration are generated as separate segments, not as one merged paragraph.
- User-provided replacement audio remains optional and shot-scoped.

This keeps the first version deterministic and CPU-stable while still delivering role differentiation.

## Review Strategy

### L1 Review
- Lightweight frame review using `unsloth/Qwen3.5-0.8B-GGUF`.
- Purpose: obvious visual defects, subtitle overlap, costume drift, scene drift, and missing shot intent.

### L2 Review
- Escalation path for uncertain or failed cases.
- May use a stronger multimodal endpoint, local or cloud.

### Non-Goals
- No legal, safety, or adult-content review in this workflow.
- Review only judges technical quality, continuity, and content-match against the intended shot.

## Storage Layout
Use local artifact storage first. Recommended path model:

- `runtime/jobs/<job_id>/source/`
- `runtime/jobs/<job_id>/planning/`
- `runtime/jobs/<job_id>/shots/<shot_id>/render/`
- `runtime/jobs/<job_id>/shots/<shot_id>/review/`
- `runtime/jobs/<job_id>/audio/`
- `runtime/jobs/<job_id>/compose/`
- `runtime/jobs/<job_id>/output/`

Artifact refs in contracts should remain storage-agnostic so the implementation can later move to object storage without contract churn.

## Default Output Preset
The first preset should be:

- `preview_720p24`
- `1280x720`
- `24 fps`
- `mp4` with `H.264`
- `AAC 48kHz stereo`
- sidecar `srt`
- optional `ass`
- burned-subtitle preview variant

This is the default because it is the safest CPU-first operating point for the current shared host.

## Failure And Retry Model
- Technical failures retry locally first.
- Prompt-quality failures retry the shot with adjusted prompts or alternate seeds.
- Continuity failures retry the minimal affected neighborhood, usually the current shot plus adjacent shots.
- Repeated `Wan` instability may downgrade the shot to `limited_motion` if policy allows.
- All retries must preserve prior artifacts and append new versions.

## Test Requirements
- Contract validation tests for all new models.
- Planner tests for motion-tier assignment and shot generation.
- Adapter tests for render-job request and status normalization.
- Audio tests for timeline building and subtitle generation.
- Composition tests for concat manifest creation and output packaging.
- Review tests for continuity scoring, retry scoping, and downgrade policy.
- End-to-end integration test using fixtures from the current demo novel.

## Immediate Implementation Boundary
Phase 2 should stop at reliable internal output generation for a chapter-sized sample. It should not add publishing, user accounts, or public multi-tenant access.
