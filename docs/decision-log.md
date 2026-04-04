# Decision Log

Use this file for dated architectural and operational decisions that should remain understandable after implementation changes.

## 2026-04-03

### D-001: Build the system as an `infra-core` module, not as part of the root compose stack
- Decision: deploy the video workflow as `/mnt/hdo/infra-core/modules/av-workflow` and register it through `modules/registry.list`.
- Why: the remote host already uses module-based compose orchestration, and this keeps the new system isolated from unrelated gateway and utility services.

### D-002: Treat agents as control-plane operators, not as production truth sources
- Decision: `OpenClaw`, `Codex`, and `Claude Code` may generate proposals, plans, and repair suggestions, but only the workflow engine may create final state transitions and delivery decisions.
- Why: preview binaries are useful for automation, but their output must remain schema-validated and policy-gated.

### D-003: Base quality review on deterministic media checks plus image-level semantic review
- Decision: assume only image-capable multimodal review is required; do not depend on video-understanding models for the baseline architecture.
- Why: this keeps the platform compatible with the currently expected model access path while preserving a stable technical QA and review loop.

### D-004: Encode resumable control states in `Job.current_stage`
- Decision: when a job enters `retry_scheduled` or `manual_hold`, persist the resumable target stage inside `current_stage` using a deterministic prefix format such as `retry_scheduled:planned` or `manual_hold:render_ready`.
- Why: this keeps the first workflow engine deterministic and replayable without introducing Temporal-specific state metadata before the adapter and persistence layers are implemented.

### D-005: Use `SourceDocument` as the stable ingest-to-planning boundary
- Decision: normalize raw text into an immutable `SourceDocument` snapshot before any `StorySpec` or `ShotPlan` generation, and keep shot generation behind an injected planner interface.
- Why: this separates deterministic source cleanup from future model-backed planning logic while preserving a replayable contract for retries, audits, and regression tests.

### D-006: Separate `PolicyDecision.target_status` from retry-only `resume_at`
- Decision: `PolicyDecision` records the workflow state the policy wants to reach in `target_status`, while `resume_at` is only used when the action is `retry` and the workflow must later resume from a scoped stage such as `planned`.
- Why: this avoids overloading one field with both state transitions and retry resumption semantics, which keeps continue, quarantine, manual hold, and retry decisions unambiguous for the workflow engine.

### D-007: Keep the agent gateway proposal-only with explicit low-quality circuit breaking
- Decision: only `openclaw`, `codex`, and `claude_code` may submit a limited set of proposal types, forbidden workflow-state mutation keys are rejected at the gateway, and repeated low-quality proposals open a per-agent circuit breaker.
- Why: this keeps preview automation tools useful for control-plane assistance without allowing them to directly mutate production truth or silently degrade workflow quality. The gateway quality gate is intentionally separate from media review thresholds; if later made operator-configurable, it should live under its own `agent_gateway.*` config branch rather than reuse `review.threshold`.

### D-008: Support Dockerless static validation for local development containers
- Decision: `doctor.sh` and `deploy.sh` support `SKIP_DOCKER_CHECK=1` so the repository can still validate Python compilation, API/tests, and dry-run deployment flow in containers that do not expose Docker.
- Why: the current development environment may not provide Docker even though the target deployment runtime does, so lightweight validation must remain possible without forcing real compose execution.

### D-009: Keep the repository root deployable as the remote `infra-core` module payload
- Decision: treat the repository root as the canonical content for `/mnt/hdo/infra-core/modules/av-workflow`, with `docker-compose.yml`, `.env.example`, `.env.secrets.example`, and `build/Dockerfile.api` maintained together as one deployable module surface.
- Why: this removes drift between a separate packaging directory and the real source tree, keeps local dry-run validation aligned with remote module registration, and preserves layered configuration that operators can override without editing source files.

### D-010: Use one layered source of truth for API bind host and port
- Decision: the container entrypoint and compose healthcheck both resolve `AV_WORKFLOW_API_HOST` and `AV_WORKFLOW_API_PORT` at runtime instead of hard-coding `0.0.0.0:8080`.
- Why: this keeps image startup, health probing, and reverse-proxy wiring consistent when operators override bind settings through layered environment files.

### D-011: Externalize the Python base image for remote module builds
- Decision: the image build resolves `PYTHON_BASE_IMAGE` from layered configuration and defaults to `python:3.12-slim` instead of hard-coding a single base image inside the Dockerfile.
- Why: this keeps remote module deployment resilient when a host already caches one Python base image or reaches registry mirrors inconsistently, while still allowing operators to override the base image without editing source files.

### D-012: Use hybrid shot generation with image-first rendering and selective `Wan` escalation
- Decision: default all planned shots to image-first execution, and only escalate shots with meaningful physical motion or narrative impact to the local `Wan` rendering path.
- Why: this preserves visual consistency, reduces CPU pressure on the shared host, and keeps the system capable of finishing chapter-sized jobs without treating every shot as a full video-generation problem.

### D-013: Encapsulate local model runtimes behind internal asynchronous adapter APIs
- Decision: the workflow engine calls internal render, TTS, and review services rather than calling raw `ComfyUI`, CLI tools, or model runtimes directly.
- Why: stable adapter APIs make retries, audit trails, status polling, and future backend replacement manageable without coupling the core workflow to provider-specific runtime details.

### D-014: Derive subtitle timing from pre-segmented TTS output rather than post hoc ASR
- Decision: split narration and dialogue into timed segments before synthesis, generate TTS per segment, and use those measured durations as the primary source of subtitle timing.
- Why: this keeps subtitles aligned with the authoritative generated audio path and avoids drifting into a second timing system that has to re-infer what the workflow already knows.

### D-015: Support multi-role voice casting in the first implementation without reference voice cloning
- Decision: assign stable local `voice_id` values to narrator and named roles, keep those assignments job-stable, and allow shot-scoped replacement audio later without making reference voice cloning part of the first release.
- Why: this gives the user differentiated character voices immediately while keeping the first version deterministic, CPU-stable, and easier to review.

### D-016: Use lightweight multimodal review as L1 triage, not as final continuity authority
- Decision: use `unsloth/Qwen3.5-0.8B-GGUF` or an equivalent lightweight image-text model for frame-level triage and reserve stronger multimodal review for escalation cases.
- Why: the lightweight model is suitable for cheap visual defect detection, but continuity and final acceptance need a stricter policy path than a single small model can reliably provide.

### D-017: Expose workflow stage and artifact mutation through HTTP, not direct store mutation
- Decision: keep `InMemoryApiStore` as an internal persistence stub and expose `PATCH /v1/jobs/{job_id}/stage`, `PATCH /v1/jobs/{job_id}/artifacts`, and `PATCH /v1/jobs/{job_id}/shots/{shot_id}/artifacts` as the operator control surface.
- Why: external automation agents, smoke tests, and future deployment modules should all exercise the same schema-validated contract instead of mutating in-memory state directly.

### D-018: Keep `DeterministicStageRunner` as the control-plane baseline and move real file output into a separate execution service
- Decision: preserve `DeterministicStageRunner` as the in-memory orchestration baseline for workflow-state progression, and implement file-backed runtime output in `DeterministicLocalJobExecutionService` instead of folding execution side effects into the stage runner.
- Why: the control plane and the executable runtime have different failure modes and different test shapes. Keeping them separate prevents runtime filesystem and ffmpeg concerns from polluting the core workflow-state contract.

### D-019: Use `asset://runtime/jobs/...` as the canonical runtime artifact namespace
- Decision: all deterministic local provider outputs and execution-slice artifacts should resolve to runtime-scoped refs such as `asset://runtime/jobs/<job_id>/shots/...` and `asset://runtime/jobs/<job_id>/output/final.mp4`.
- Why: host-specific `file://` paths are hard to preserve across API boundaries and remote execution environments. Runtime-scoped asset refs keep artifacts traceable without leaking machine-local absolute paths into workflow contracts.

### D-020: Package `ffmpeg` inside the API image instead of assuming host binaries
- Decision: install `ffmpeg` in `build/Dockerfile.api` and treat the container image as the executable runtime boundary for compose/video stitching.
- Why: both the development container and the target host may differ in host-level media tooling. Packaging `ffmpeg` in the module image removes a hidden host dependency and keeps the execution contract reproducible.

### D-021: Placeholder local renders must fail closed and remain non-deliverable
- Decision: deterministic local render outputs are execution-contract fixtures only; they must carry explicit placeholder metadata, fail technical review, and leave the workflow in `manual_hold` rather than `completed`.
- Why: a stitched mp4 with valid streams is not sufficient evidence of usable video quality. The system must never treat placeholder media as a successful deliverable just because the runtime, concat, and audio pipeline executed.

### D-022: Real image and Wan providers should enter through API-backed render adapters
- Decision: the workflow keeps `ShotRenderJob` and `ShotRenderResult` as stable internal contracts, while real image and Wan backends are integrated through endpoint-configured API adapters and a backend-routing adapter.
- Why: this preserves the current workflow and review contracts, keeps provider-specific HTTP details out of orchestration code, and allows deterministic placeholder fallback, local model APIs, and future cloud fallback to share the same render-job surface.

### D-023: Render backend selection must be explicit in layered config
- Decision: add `render.mode` as a required layered config field with `deterministic_local` and `routed_api` as the only supported values.
- Why: silent fallback from real-provider mode to placeholder media is unacceptable. Operators need an explicit switch that keeps contract validation and real-render execution distinct.

### D-024: API job execution should use a job-scoped runtime factory
- Decision: expose `POST /v1/jobs/{job_id}/execute`, and construct the execution service through a job-scoped factory that resolves layered config, a runtime root, and job-bound TTS/render adapters at request time.
- Why: the runtime path needs per-job filesystem output and job-bound TTS assets, while the control plane still needs a stable app-level entrypoint. A factory keeps those concerns separated without hard-coding one global execution service instance.

### D-025: Ship dedicated internal renderer services before enabling real local model backends by default
- Decision: add `av-image-renderer` and `av-wan-renderer` as separate internal worker services, keep the API-facing render contract HTTP-based, and gate the first real image model behind an explicit `sd_cpp` backend mode instead of forcing heavy model pulls into the default module startup path.
- Why: the system needs a stable routed render topology and user-maintainable configuration before it can safely absorb CPU-heavy GGUF model runtimes. Shipping the worker surfaces first keeps the workflow modular, lets the API switch into routed mode via profile, and preserves a fail-closed placeholder path until real local model assets are deliberately mounted.

### D-026: Profiles must override module defaults in layered config
- Decision: apply config layers in this order: defaults, modules, profiles, environment overrides, runtime overrides.
- Why: modules carry reusable defaults, while profiles are operator-facing mode selections such as `routed_api_local`. If profiles load earlier than modules, explicit runtime switches silently fall back to placeholder behavior.

### D-027: Motion-tier inference must recognize Chinese action cues
- Decision: keep the heuristic planner lightweight, but treat Chinese action and crowd-motion phrases as first-class `wan_dynamic` cues alongside the existing English keywords.
- Why: the current target workload is Chinese long-form fiction. English-only keyword inference leaves dynamic scenes stuck on the image path and prevents routed Wan validation on real user input.

### D-028: Model the `Z-Image` image backend as a split `stable-diffusion.cpp` contract
- Decision: keep the `sd_cpp` backend name, but model `Z-Image` with three explicit operator paths: `diffusion_model_path`, `vae_path`, and `llm_path`.
- Why: the official `stable-diffusion.cpp` `Z-Image` surface is not a single `-m` checkpoint. Treating it as one model file creates a misleading configuration contract that looks complete in env files but cannot actually execute when the backend is enabled.

### D-029: Real render outputs must not auto-complete without explicit semantic review
- Decision: once the workflow is producing real image or video frames, `completed` must require a real semantic review result rather than treating technical QA as an implicit semantic pass.
- Why: technical QA only proves codec, duration, subtitle, and placeholder integrity. The first remote `Z-Image` smoke already showed that a visually weak frame can still pass those checks, so auto-completion without semantic review overstates delivery quality.

### D-030: Use Qwen-VL tiering with on-demand model launch for semantic review
- Decision: use `Qwen3-VL-8B-Instruct-GGUF` as the default L1 semantic triage and `Qwen3-VL-32B-Instruct-GGUF` as the final gate, both launched on-demand (no resident server). Keep `Qwen2-VL-2B-Instruct-GGUF` only as a low-cost fallback for non-critical triage.
- Why: the 8B GGUF sizes (Q4_K_M ~5.03 GB, Q8_0 ~8.71 GB) support frequent L1 checks, while the 32B Q4_K_M (~19.76 GB) fits the current remote CPU memory headroom for a stronger final judgment when scheduled sparingly. The on-demand launch pattern avoids continuous RAM pressure on the shared host.

### D-031: Keep `routed_api_local` on `Qwen3-VL-32B` for the current quality-first phase
- Decision: set the current operator-facing routed profile to `Qwen3-VL-32B-Instruct-Q4_K_M` plus `mmproj Q8_0`, and keep `8B` only as a lighter fallback profile.
- Why: the reviewer is launched on demand and exits after each check, so the host does not need to keep the model resident. The current shared host still has roughly `24 GiB` available after the resident containers, which is enough for a one-shot `32B Q4_K_M` semantic pass during this quality-first phase. Keep `config/profiles/routed_api_local_shared_8b.yaml` as the lighter fallback profile for operators who explicitly want a smaller reviewer.
