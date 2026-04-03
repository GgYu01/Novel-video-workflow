# REQ 001: Internal Single-Tenant Automated Novel-to-Video Workflow

## Background
The project targets an internal single-tenant workflow that turns novels or story-like text into reviewable video assets. The system runs on a remote CPU-first host and may call external image, video, TTS, and multimodal review APIs through controlled adapters.

## Scope
- Accept internal text input from upload, URL, or controlled crawler.
- Produce internal video assets, subtitles, covers, preview frames, and review summaries.
- Run fully automated planning, rendering, composition, and review workflows.
- Support `OpenClaw`, `Codex`, and `Claude Code` as control-plane automation tools.
- Maintain long-lived docs, requirements, decisions, plans, and recurring issue evidence in-repo.

## Out of Scope
- Public multi-tenant access.
- Automatic publishing to external platforms.
- Baseline dependence on local GPU inference.
- Baseline dependence on video-understanding review models.

## Functional Requirements
1. The system must manage work as versioned jobs with immutable artifacts and explicit state transitions.
2. The system must split text processing, planning, rendering, composition, review, and policy decisions into separate modules.
3. The system must support local deterministic media QA and image-based semantic review from extracted frames.
4. The system must support partial retries at `shot`, `scene`, or `chapter` scope without restarting the full job.
5. The system must store all assets and review evidence in traceable manifests.
6. The system must expose a single internal API for job submission, status lookup, and artifact retrieval.
7. Agents may submit proposals, but only the workflow engine may commit delivery decisions.
8. Configuration must be layered into defaults, profiles, modules, secrets, and runtime overrides.

## Non-Functional Requirements
- Stable on a CPU-first remote host.
- Safe to operate alongside existing `infra-core` services.
- Configurable without editing source code for common operator tasks.
- Auditable through structured logs, review records, and decision logs.
- Test-driven for contracts, workflow state transitions, retry behavior, and media QA gates.

## Acceptance Criteria
- A sample job can progress from source normalization to output package creation using stub adapters.
- Failed review can trigger a scoped retry without corrupting existing artifacts.
- All core contracts are schema-validated and versioned.
- Module deployment can be described as a standalone `infra-core` compose stack.
