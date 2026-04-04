# Task Plan

## Goal
Define and implement the next execution slice that turns the current control-plane skeleton into a runnable local-output workflow: executable composition, adapter-backed runtime calls, and a deterministic job-run entrypoint.

## Phases
| Phase | Status | Notes |
|---|---|---|
| 1. Explore current runtime boundary | complete | Current gap is executable runtime, not control-plane/API. |
| 2. Lock next-slice design | complete | Design approved and captured in `docs/plans/2026-04-03-local-execution-slice-design.md`. |
| 3. Implement with TDD | complete | Added runtime workspace, deterministic local providers, ffmpeg compose layer, and job execution service. |
| 4. Verify locally and remotely | complete | Local unit/integration verification passed; remote demo frame sampling confirmed placeholder solid-color renders, and the runtime now flags placeholder outputs in technical review. |
| 5. Capture root cause and fail-closed rules in project docs | complete | Root cause, fail-closed policy, and remaining real-provider gap are documented. |
| 6. Prepare real provider replacement slice | complete | Added render endpoint config, API-backed image/Wan adapter layer, explicit `render.mode`, job-scoped runtime bootstrap, API execution endpoint, routed render-service apps, compose topology, the `routed_api_local` profile, the corrected split-model `Z-Image` `sd_cpp` command contract, a formal remote provisioning script, and verified the first real CPU image-generation smoke on the remote host. |
| 7. Close the semantic quality gap for real renders | in_progress | Remote `Z-Image` smoke now completes end to end, but completion is still based on technical QA only. The next slice must add explicit semantic image review and a stricter delivery gate before real-image jobs are allowed to auto-complete. |

## Constraints
- Keep `xiaoshuo.txt` untracked.
- Preserve internal single-tenant assumptions.
- Prefer modular adapters and layered config over provider-specific leaks.
- Do not require real model pulls for default developer validation.
- Treat placeholder media as a hard failure in review/policy, not as acceptable output.
- Treat technical-only review as insufficient evidence of delivery quality once real image generation is enabled.
