# Task Plan

## Goal
Converge the real semantic-review path into a quality-first, on-demand reviewer flow: multi-frame Qwen-VL checks, explicit tiering for the shared host, and remote validation of the chosen default model without making it resident.

## Phases
| Phase | Status | Notes |
|---|---|---|
| 1. Explore current runtime boundary | complete | Current gap is executable runtime, not control-plane/API. |
| 2. Lock next-slice design | complete | Design approved and captured in `docs/plans/2026-04-03-local-execution-slice-design.md`. |
| 3. Implement with TDD | complete | Added runtime workspace, deterministic local providers, ffmpeg compose layer, and job execution service. |
| 4. Verify locally and remotely | complete | Local unit/integration verification passed; remote demo frame sampling confirmed placeholder solid-color renders, and the runtime now flags placeholder outputs in technical review. |
| 5. Capture root cause and fail-closed rules in project docs | complete | Root cause, fail-closed policy, and remaining real-provider gap are documented. |
| 6. Prepare real provider replacement slice | complete | Added render endpoint config, API-backed image/Wan adapter layer, explicit `render.mode`, job-scoped runtime bootstrap, API execution endpoint, routed render-service apps, compose topology, the `routed_api_local` profile, the corrected split-model `Z-Image` `sd_cpp` command contract, a formal remote provisioning script, and verified the first real CPU image-generation smoke on the remote host. |
| 7. Close the semantic quality gap for real renders | complete | Added an explicit semantic review gate, a fail-closed review service, and an on-demand `llama.cpp` semantic-review backend surface. Real-image jobs can no longer auto-complete on technical QA alone. |
| 8. Provision and validate the on-demand Qwen reviewer on the remote host | in_progress | Keep the shared host stable: prefer `Qwen3-VL-32B Q4_K_M + mmproj Q8_0` as the current default, keep `config/profiles/routed_api_local_shared_8b.yaml` as the lighter fallback profile, and validate that the reviewer still runs as a one-shot subprocess instead of a resident server. Local code now samples multiple frames per shot; remote asset provisioning and smoke validation are the remaining checks. |

## Constraints
- Keep `xiaoshuo.txt` untracked.
- Preserve internal single-tenant assumptions.
- Prefer modular adapters and layered config over provider-specific leaks.
- Do not require real model pulls for default developer validation.
- Treat placeholder media as a hard failure in review/policy, not as acceptable output.
- Treat technical-only review as insufficient evidence of delivery quality once real image generation is enabled.
