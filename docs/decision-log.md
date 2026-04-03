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
